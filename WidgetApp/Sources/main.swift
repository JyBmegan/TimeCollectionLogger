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
        .defaultSize(width: 370, height: 1060)
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
                let w: CGFloat = 370, h: CGFloat = 1060
                let f = builtin.visibleFrame
                window.setFrame(
                    NSRect(x: f.maxX - w - 6, y: f.maxY - h - 6,
                           width: w, height: h), display: true)
            }
        }
    }
}
