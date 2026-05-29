import SwiftUI
import AppKit
import CoreGraphics

@main
struct TimeWidgetApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var loader = DataLoader()

    var body: some Scene {
        WindowGroup {
            TimelineView(
                data: loader.data,
                weekOffset: loader.weekOffset,
                onPreviousWeek: { loader.navigateWeek(loader.weekOffset - 1) },
                onNextWeek: {
                    if loader.weekOffset < 0 {
                        loader.navigateWeek(loader.weekOffset + 1)
                    }
                },
                onResetToCurrentWeek: { loader.navigateWeek(0) }
            )
                .frame(minWidth: 120, minHeight: 400)
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentSize)
        .defaultSize(width: 820, height: 1060)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        if let window = NSApplication.shared.windows.first {
            setupWindow(window)
            positionWindow(window)
        }
        NotificationCenter.default.addObserver(
            forName: NSApplication.didChangeScreenParametersNotification,
            object: nil, queue: .main) { _ in
                if let w = NSApplication.shared.windows.first {
                    self.positionWindow(w)
                }
            }
    }

    func setupWindow(_ window: NSWindow) {
        window.isOpaque = false
        window.backgroundColor = .clear
        let desk = CGWindowLevelForKey(.desktopIconWindow)
        window.level = NSWindow.Level(rawValue: Int(desk + 1))
        window.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle]
        window.hasShadow = false
        window.canHide = false
        window.titlebarAppearsTransparent = true
        window.isMovable = false
        window.isMovableByWindowBackground = false
        window.ignoresMouseEvents = false
        window.standardWindowButton(.closeButton)?.isHidden = true
        window.standardWindowButton(.miniaturizeButton)?.isHidden = true
        window.standardWindowButton(.zoomButton)?.isHidden = true
    }

    func positionWindow(_ window: NSWindow) {
        guard let builtin = NSScreen.screens.first else { return }
        let f = builtin.visibleFrame
        let w: CGFloat = min(f.width * 0.45, 820)
        let h: CGFloat = min(f.height * 0.92, 1060)
        let y = (f.minY + f.maxY - h) / 2
        window.setFrame(
            NSRect(x: f.maxX - w - 16, y: y, width: w, height: h),
            display: true, animate: false)
    }
}
