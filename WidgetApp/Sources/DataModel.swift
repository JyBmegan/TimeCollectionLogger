import Foundation

struct TimeEntry: Codable, Identifiable {
    let id: String
    let category: String
    let project: String
    let start: String
    let end: String
    let name: String
    let durationMin: Int

    init(category: String, project: String, start: String, end: String, name: String, durationMin: Int) {
        self.category = category
        self.project = project
        self.start = start
        self.end = end
        self.name = name
        self.durationMin = durationMin
        self.id = "\(name)|\(start)|\(end)"
    }

    enum CodingKeys: String, CodingKey {
        case category, project, start, end, name, durationMin
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        category = try c.decode(String.self, forKey: .category)
        project = try c.decode(String.self, forKey: .project)
        start = try c.decode(String.self, forKey: .start)
        end = try c.decode(String.self, forKey: .end)
        name = try c.decode(String.self, forKey: .name)
        durationMin = try c.decode(Int.self, forKey: .durationMin)
        id = "\(name)|\(start)|\(end)"
    }
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

        // 2. 如果 weekStart 为空（Notion 未同步），用当前周一
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
