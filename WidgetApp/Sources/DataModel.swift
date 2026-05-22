import Foundation

// MARK: - 从 JSON 文件读取的数据模型

struct TimeEntry: Codable, Identifiable {
    var id: String { "\(category)_\(project)_\(start)_\(end)" }
    let category: String
    let project: String
    let start: String   // ISO 8601
    let end: String
    let name: String
    let durationMin: Int
}

struct WidgetData: Codable {
    let updated: String
    let weekStart: String  // "2026-05-18" (Monday)
    let entries: [TimeEntry]
}

// MARK: - JSON 加载

class DataLoader: ObservableObject {
    @Published var data: WidgetData?
    @Published var error: String?

    private let cachePath = NSHomeDirectory() + "/.timecollectionlogger/widget_data.json"
    private var timer: Timer?
    private var lastModified: Date?

    init() {
        load()
        timer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in
            self?.checkAndReload()
        }
    }

    func load() {
        guard FileManager.default.fileExists(atPath: cachePath) else {
            error = "数据文件不存在 (首次运行请先同步 Notion)"
            return
        }
        do {
            let raw = try Data(contentsOf: URL(fileURLWithPath: cachePath))
            data = try JSONDecoder().decode(WidgetData.self, from: raw)
            error = nil
            lastModified = try FileManager.default
                .attributesOfItem(atPath: cachePath)[.modificationDate] as? Date
        } catch let e {
            error = "数据解析失败: \(e.localizedDescription)"
        }
    }

    func checkAndReload() {
        guard let path = try? FileManager.default
            .attributesOfItem(atPath: cachePath)[.modificationDate] as? Date,
              path != lastModified else { return }
        load()
    }
}
