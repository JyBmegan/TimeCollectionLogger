import Foundation

struct TimeEntry: Codable, Identifiable {
    var id: String { "\(category)_\(project)_\(start)_\(end)" }
    let category: String
    let project: String
    let start: String
    let end: String
    let name: String
    let durationMin: Int
}

struct WidgetData: Codable {
    let updated: String
    let weekStart: String
    let entries: [TimeEntry]
}

struct BufferDump: Codable {
    let entries: [TimeEntry]
}

class DataLoader: ObservableObject {
    @Published var data: WidgetData?
    @Published var error: String?

    private let cachePath = NSHomeDirectory() + "/.timecollectionlogger/widget_data.json"
    private let bufferPath = NSHomeDirectory() + "/.timecollectionlogger/buffer_dump.json"
    private var timer: Timer?

    init() {
        load()
        timer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            self?.load()
        }
    }

    func load() {
        var entries: [TimeEntry] = []
        var updated = ""
        var weekStart = ""

        // 1. 读 Notion 数据
        if let d = _loadWidgetData() {
            entries = d.entries
            updated = d.updated
            weekStart = d.weekStart
        }

        // 2. 合并今天缓冲区未推送数据
        if let buf = _loadBuffer() {
            entries += buf.entries
        }

        // 3. 如果 weekStart 为空（Notion 未同步），用当前周一
        if weekStart.isEmpty {
            let cal = Calendar.current
            let today = Date()
            let monday = cal.date(from: cal.dateComponents([.yearForWeekOfYear, .weekOfYear], from: today))!
            let fmt = DateFormatter(); fmt.dateFormat = "yyyy-MM-dd"
            weekStart = fmt.string(from: monday)
        }

        data = WidgetData(updated: updated, weekStart: weekStart, entries: entries)
    }

    private func _loadWidgetData() -> WidgetData? {
        guard FileManager.default.fileExists(atPath: cachePath) else { return nil }
        do {
            let raw = try Data(contentsOf: URL(fileURLWithPath: cachePath))
            return try JSONDecoder().decode(WidgetData.self, from: raw)
        } catch { return nil }
    }

    private func _loadBuffer() -> BufferDump? {
        guard FileManager.default.fileExists(atPath: bufferPath) else { return nil }
        do {
            let raw = try Data(contentsOf: URL(fileURLWithPath: bufferPath))
            return try JSONDecoder().decode(BufferDump.self, from: raw)
        } catch { return nil }
    }
}
