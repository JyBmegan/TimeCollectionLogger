import SwiftUI

struct TimelineView: View {
    let data: WidgetData?
    private let hourStart = 6
    private let hourEnd = 24
    private var totalHours: Int { hourEnd - hourStart }
    private let hourHeight: CGFloat = 44

    var body: some View {
        if let data = data {
            let days = buildDays(from: data.weekStart)
            let byDay = groupByDay(data.entries)

            VStack(spacing: 0) {
                // 条目计数（调试用，确定后删掉）
                Text("\(data.entries.count) 条记录")
                    .font(.system(size: 9, weight: .light))
                    .foregroundColor(.white.opacity(0.5))
                    .padding(.bottom, 6)

                HStack(spacing: 0) {
                    hourLabels
                    ForEach(days, id: \.self) { day in
                        DayColumn(date: day, entries: byDay[day] ?? [],
                                  hourStart: hourStart, totalHours: totalHours,
                                  hourHeight: hourHeight)
                    }
                }
            }
            .padding(12)
            .background(Color.black.opacity(0.22))
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .padding(6)
        } else {
            Text("加载中...")
                .font(.system(size: 13))
                .foregroundColor(.white.opacity(0.4))
        }
    }

    private var hourLabels: some View {
        VStack(alignment: .trailing, spacing: 0) {
            Text("").frame(height: 22)
            ForEach(hourStart..<hourEnd, id: \.self) { h in
                Text(String(format: "%02d:00", h))
                    .font(.system(size: 9, weight: .medium, design: .monospaced))
                    .foregroundColor(.white.opacity(0.6))
                    .frame(height: hourHeight, alignment: .top)
            }
        }
        .frame(width: 34)
        .padding(.trailing, 4)
    }

    private func buildDays(from ws: String) -> [String] {
        let fmt = DateFormatter(); fmt.dateFormat = "yyyy-MM-dd"
        guard let start = fmt.date(from: ws) else { return [] }
        return (0..<7).map {
            fmt.string(from: Calendar.current.date(byAdding: .day, value: $0, to: start)!)
        }
    }

    private func groupByDay(_ entries: [TimeEntry]) -> [String: [TimeEntry]] {
        let iso = ISO8601DateFormatter()
        let dayFmt = DateFormatter(); dayFmt.dateFormat = "yyyy-MM-dd"
        var result: [String: [TimeEntry]] = [:]
        for e in entries {
            guard let d = iso.date(from: e.start) else { continue }
            result[dayFmt.string(from: d), default: []].append(e)
        }
        return result
    }
}

// MARK: - 单日列

struct DayColumn: View {
    let date: String
    let entries: [TimeEntry]
    let hourStart: Int
    let totalHours: Int
    let hourHeight: CGFloat

    private var isToday: Bool {
        let fmt = DateFormatter(); fmt.dateFormat = "yyyy-MM-dd"
        return date == fmt.string(from: Date())
    }

    var body: some View {
        VStack(spacing: 0) {
            dayHeader.frame(height: 22)
            ZStack(alignment: .topLeading) {
                gridLines
                ForEach(entries) { entry in
                    TimeBlock(entry: entry, hourStart: hourStart, hourHeight: hourHeight)
                }
            }
        }
    }

    private var dayHeader: some View {
        let fmt = DateFormatter(); fmt.dateFormat = "yyyy-MM-dd"
        guard let d = fmt.date(from: date) else { return AnyView(Text(date)) }
        let df = DateFormatter(); df.dateFormat = "E"
        let dayName = df.string(from: d)
        let dayNum = Calendar.current.component(.day, from: d)

        return AnyView(
            VStack(spacing: 1) {
                Text(dayName)
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundColor(.white.opacity(isToday ? 1.0 : 0.7))
                Text(String(format: "%02d", dayNum))
                    .font(.system(size: 14, weight: isToday ? .bold : .regular, design: .rounded))
                    .foregroundColor(isToday ? .white : .white.opacity(0.75))
            }
            .frame(maxWidth: .infinity)
            .background(isToday ? Color.white.opacity(0.15) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 6))
        )
    }

    private var gridLines: some View {
        VStack(spacing: 0) {
            ForEach(0..<totalHours, id: \.self) { i in
                Rectangle()
                    .fill(Color.white.opacity(i % 3 == 0 ? 0.05 : 0.02))
                    .frame(height: hourHeight)
            }
        }
    }
}

// MARK: - 时间色块

struct TimeBlock: View {
    let entry: TimeEntry
    let hourStart: Int
    let hourHeight: CGFloat

    var body: some View {
        GeometryReader { geo in
            let (y, h) = layout(for: entry)
            let blockH = max(h - 1, 8)

            VStack(alignment: .leading, spacing: 0) {
                Text(entry.name)
                    .font(.system(size: 9, weight: .semibold))
                    .lineLimit(1)
                if blockH > 16 {
                    Text("\(entry.category) · \(entry.project)")
                        .font(.system(size: 8))
                        .lineLimit(1)
                        .foregroundColor(.white.opacity(0.8))
                }
            }
            .padding(.horizontal, 3)
            .padding(.vertical, 1)
            .frame(width: max(geo.size.width - 1, 0), height: blockH, alignment: .topLeading)
            .background(blockColor(entry.category))
            .cornerRadius(4)
            .overlay(RoundedRectangle(cornerRadius: 4)
                .stroke(blockColor(entry.category).opacity(0.5), lineWidth: 0.5))
            .offset(y: y)
        }
    }

    private func layout(for e: TimeEntry) -> (CGFloat, CGFloat) {
        let iso = ISO8601DateFormatter()
        guard let s = iso.date(from: e.start),
              let ed = iso.date(from: e.end) else { return (0, 10) }
        let cal = Calendar.current
        let top = (CGFloat(cal.component(.hour, from: s) - hourStart) * 60
                   + CGFloat(cal.component(.minute, from: s))) / 60 * hourHeight
        let bot = (CGFloat(cal.component(.hour, from: ed) - hourStart) * 60
                   + CGFloat(cal.component(.minute, from: ed))) / 60 * hourHeight
        return (max(0, top), max(6, bot - top))
    }
}

// MARK: - 配色

func blockColor(_ cat: String) -> Color {
    switch cat {
    case "Research":       return Color(red: 0.30, green: 0.45, blue: 0.90).opacity(0.55)
    case "Work":           return Color(red: 0.20, green: 0.65, blue: 0.55).opacity(0.55)
    case "Entertainment":  return Color(red: 0.85, green: 0.45, blue: 0.55).opacity(0.55)
    case "Entertainmen":   return Color(red: 0.85, green: 0.45, blue: 0.55).opacity(0.55)
    case "Web":            return Color(red: 0.50, green: 0.55, blue: 0.65).opacity(0.52)
    case "Offline":        return Color.white.opacity(0.20)
    default:               return Color.white.opacity(0.30)
    }
}
