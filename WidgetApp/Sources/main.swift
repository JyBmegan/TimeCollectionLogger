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
        .defaultSize(width: 830, height: 1030)
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
                let w: CGFloat = 830, h: CGFloat = 1030
                let f = builtin.visibleFrame
                let y = f.minY + 40   // 固定上边距 40px
                window.setFrame(
                    NSRect(x: f.maxX - w - 20, y: y,
                           width: w, height: h), display: true)
            }
        }
    }
}
