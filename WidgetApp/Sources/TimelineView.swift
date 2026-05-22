import SwiftUI

// MARK: - 主时间轴

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
            HStack(spacing: 0) {
                hourLabels
                ForEach(days, id: \.self) { day in
                    DayColumn(date: day, entries: byDay[day] ?? [],
                              hourStart: hourStart, totalHours: totalHours,
                              hourHeight: hourHeight)
                }
            }
            .padding(.top, 24)
            .padding(.horizontal, 8)
        } else {
            Text("等待数据...")
                .font(.system(size: 13, weight: .light))
                .foregroundColor(.white.opacity(0.4))
        }
    }

    private var hourLabels: some View {
        VStack(alignment: .trailing, spacing: 0) {
            Text("").frame(height: 22) // 对齐日期头
            ForEach(hourStart..<hourEnd, id: \.self) { h in
                Text(String(format: "%02d:00", h))
                    .font(.system(size: 9, weight: .light, design: .monospaced))
                    .foregroundColor(.white.opacity(0.3))
                    .frame(height: hourHeight, alignment: .top)
            }
        }
        .frame(width: 36)
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
        Dictionary(grouping: entries) { String($0.start.prefix(10)) }
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
        GeometryReader { geo in
            let w = geo.size.width
            VStack(spacing: 0) {
                dayHeader.frame(width: w, height: 22)
                ZStack(alignment: .topLeading) {
                    gridLines
                    ForEach(entries) { entry in
                        TimeBlock(entry: entry, colW: w, hourStart: hourStart,
                                  hourHeight: hourHeight)
                    }
                }
                .frame(width: w)
            }
        }
    }

    private var dayHeader: some View {
        let fmt = DateFormatter(); fmt.dateFormat = "yyyy-MM-dd"
        guard let d = fmt.date(from: date) else { return AnyView(Text(date)) }
        let df = DateFormatter(); df.dateFormat = "E"
        let dayName = df.string(from: d)
        let cal = Calendar.current
        let dayNum = cal.component(.day, from: d)

        return AnyView(
            VStack(spacing: 1) {
                Text(dayName)
                    .font(.system(size: 9, weight: .medium))
                    .foregroundColor(.white.opacity(isToday ? 0.9 : 0.45))
                Text(String(format: "%02d", dayNum))
                    .font(.system(size: 14, weight: isToday ? .bold : .regular, design: .rounded))
                    .foregroundColor(isToday ? .white : .white.opacity(0.55))
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
                    .fill(Color.white.opacity(i % 3 == 0 ? 0.06 : 0.025))
                    .frame(height: hourHeight)
            }
        }
    }
}

// MARK: - 时间色块

struct TimeBlock: View {
    let entry: TimeEntry
    let colW: CGFloat
    let hourStart: Int
    let hourHeight: CGFloat

    var body: some View {
        let (y, h) = layout(for: entry)
        let w = max(colW - 3, 0)
        let blockH = max(h - 2, 8)

        VStack(alignment: .leading, spacing: 0) {
            Text(entry.name)
                .font(.system(size: 8, weight: .medium))
                .lineLimit(1)
                .shadow(color: .black.opacity(0.5), radius: 0, y: 0.5)
            if blockH > 20 {
                Text("\(entry.category) · \(entry.project)")
                    .font(.system(size: 7, weight: .light))
                    .lineLimit(1)
                    .foregroundColor(.white.opacity(0.7))
                    .shadow(color: .black.opacity(0.4), radius: 0, y: 0.5)
            }
        }
        .padding(.horizontal, 4)
        .padding(.vertical, 2)
        .frame(width: w, height: blockH, alignment: .topLeading)
        .background(blockColor(entry.category))
        .cornerRadius(4)
        .overlay(
            RoundedRectangle(cornerRadius: 4)
                .stroke(blockColor(entry.category).opacity(0.6), lineWidth: 0.5)
        )
        .offset(y: y)
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

// MARK: - 分类配色

func blockColor(_ cat: String) -> Color {
    switch cat {
    case "Research":       return Color(red: 0.30, green: 0.45, blue: 0.90).opacity(0.50)
    case "Work":           return Color(red: 0.20, green: 0.65, blue: 0.55).opacity(0.50)
    case "Entertainment":  return Color(red: 0.85, green: 0.45, blue: 0.55).opacity(0.50)
    case "Entertainmen":   return Color(red: 0.85, green: 0.45, blue: 0.55).opacity(0.50)
    case "Web":            return Color(red: 0.50, green: 0.55, blue: 0.65).opacity(0.45)
    case "Offline":        return Color.white.opacity(0.18)
    default:               return Color.white.opacity(0.28)
    }
}
