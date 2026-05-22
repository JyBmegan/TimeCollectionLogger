import SwiftUI
import AppKit
import CoreGraphics

@main
struct TimeWidgetApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var loader = DataLoader()

    var body: some Scene {
        WindowGroup {
            TimelineView(data: loader.data)
                .frame(minWidth: 120, minHeight: 400)
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentSize)
        .defaultSize(width: 800, height: 960)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        if let window = NSApplication.shared.windows.first {
            window.isOpaque = false
            window.backgroundColor = .clear
            let desk = CGWindowLevelForKey(.desktopIconWindow)
            window.level = NSWindow.Level(rawValue: Int(desk))
            window.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle]
            window.hasShadow = false
            window.canHide = false
            window.titlebarAppearsTransparent = true
            window.isMovableByWindowBackground = true
            // .nonactivatingPanel 不兼容 NSWindow，已移除

            // 隐藏红绿灯
            window.standardWindowButton(.closeButton)?.isHidden = true
            window.standardWindowButton(.miniaturizeButton)?.isHidden = true
            window.standardWindowButton(.zoomButton)?.isHidden = true

            if let builtin = NSScreen.screens.first {
                let w: CGFloat = 800, h: CGFloat = 960
                let f = builtin.visibleFrame
                window.setFrame(
                    NSRect(x: f.maxX - w - 6, y: f.midY - h / 2,
                           width: w, height: h), display: true)
            }
        }
    }
}
