import SwiftUI

private let hourStart = 8
private let hourEnd = 27
private let totalHours = hourEnd - hourStart
private let hourHeight: CGFloat = 40
private let colW: CGFloat = 80
private let blockFontSize: CGFloat = 10

private let dayFmt: DateFormatter = {
    let f = DateFormatter()
    f.locale = Locale(identifier: "en_US_POSIX")
    f.dateFormat = "yyyy-MM-dd"
    return f
}()

struct TimelineView: View {
    let data: WidgetData?

    var body: some View {
        VStack(spacing: 0) {
            if let data = data {
                let days = buildDays(from: data.weekStart)
                // 过滤碎片（<3min）并清理显示名
                let cleaned = data.entries.filter { $0.durationMin >= 3 }.map(cleanEntry)
                let byDay = groupByDay(cleaned)
                let mergedByDay = byDay.mapValues { mergeAdjacent($0) }

                HStack(alignment: .top, spacing: 0) {
                    VStack(alignment: .trailing, spacing: 0) {
                        Color.clear.frame(height: 24)
                        ForEach(hourStart..<hourEnd, id: \.self) { h in
                            let d = h <= 24 ? h : h - 24
                            Text(String(format: "%02d:00", d))
                                .font(.system(size: 8, weight: .medium, design: .monospaced))
                                .foregroundColor(.white.opacity(0.55))
                                .frame(height: hourHeight, alignment: .top)
                        }
                    }
                    .frame(width: 30)
                    .padding(.trailing, 3)

                    ForEach(days, id: \.self) { day in
                        DayColumn(date: day, entries: mergedByDay[day] ?? [])
                            .frame(width: colW)
                    }
                }
                .frame(height: CGFloat(totalHours) * hourHeight + 24)
            } else {
                Text("加载中...")
                    .font(.system(size: 13))
                    .foregroundColor(.white.opacity(0.4))
            }
        }
        .padding(10)
        .background(Color.black.opacity(0.22))
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .padding(6)
        .frame(width: 660, height: 840)
    }

    /// 清理显示名：去 "VSCode: "、"Web: " 等前缀，直接用项目/域名
    private func cleanEntry(_ e: TimeEntry) -> TimeEntry {
        var name = e.name
        for prefix in ["VSCode: ", "Web: ", "Notion: ", "Microsoft Excel: "] {
            if name.hasPrefix(prefix) { name = String(name.dropFirst(prefix.count)) }
        }
        return TimeEntry(category: e.category, project: e.project,
                         start: e.start, end: e.end, name: name,
                         durationMin: e.durationMin)
    }

    private func buildDays(from ws: String) -> [String] {
        guard let start = dayFmt.date(from: ws) else { return [] }
        return (0..<7).map {
            dayFmt.string(from: Calendar.current.date(byAdding: .day, value: $0, to: start)!)
        }
    }

    private func groupByDay(_ entries: [TimeEntry]) -> [String: [TimeEntry]] {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var result: [String: [TimeEntry]] = [:]
        for e in entries {
            guard let d = iso.date(from: e.start) else { continue }
            result[dayFmt.string(from: d), default: []].append(e)
        }
        return result
    }

    /// 合并同列中同 name + 同 category 且时间相邻的条目
    private func mergeAdjacent(_ entries: [TimeEntry]) -> [TimeEntry] {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let sorted = entries.sorted { a, b in
            (iso.date(from: a.start) ?? Date.distantPast) < (iso.date(from: b.start) ?? Date.distantPast)
        }
        var merged: [TimeEntry] = []
        for e in sorted {
            if var last = merged.last,
               last.name == e.name,
               last.category == e.category,
               last.project == e.project,
               let lastEnd = iso.date(from: last.end),
               let thisStart = iso.date(from: e.start),
               thisStart.timeIntervalSince(lastEnd) < 600 {  // gap < 10min
                // 合并
                merged[merged.count - 1] = TimeEntry(
                    category: last.category, project: last.project,
                    start: last.start, end: e.end, name: last.name,
                    durationMin: last.durationMin + e.durationMin)
            } else {
                merged.append(e)
            }
        }
        return merged
    }
}

// MARK: - 单日列

struct DayColumn: View {
    let date: String
    let entries: [TimeEntry]

    private var isToday: Bool {
        return date == dayFmt.string(from: Date())
    }

    var body: some View {
        VStack(spacing: 0) {
            dayHeaderView
                .frame(width: colW, height: 24)

            ZStack(alignment: .topLeading) {
                VStack(spacing: 0) {
                    ForEach(0..<totalHours, id: \.self) { i in
                        Rectangle()
                            .fill(Color.white.opacity(i % 3 == 0 ? 0.06 : 0.025))
                            .frame(width: colW, height: hourHeight)
                    }
                }

                let groups = overlapGroups(entries)
                ForEach(0..<groups.count, id: \.self) { gi in
                    let group = groups[gi]
                    ForEach(0..<group.count, id: \.self) { ei in
                        TimeBlockView(entry: group[ei], groupCount: group.count, groupIndex: ei)
                    }
                }
            }
            .frame(width: colW)
        }
    }

    /// 将重叠条目分组，同组内水平分割宽度
    private func overlapGroups(_ entries: [TimeEntry]) -> [[TimeEntry]] {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let sorted = entries.sorted { a, _ in (iso.date(from: a.start) ?? Date.distantPast) < (iso.date(from: a.start) ?? Date.distantPast) }
        var groups: [[TimeEntry]] = []
        for e in sorted {
            let s = iso.date(from: e.start)
            let ed = iso.date(from: e.end)
            if s == nil || ed == nil {
                groups.append([e])
                continue
            }
            var placed = false
            for i in 0..<groups.count {
                let lastInGroup = groups[i].last!
                if let glastEnd = iso.date(from: lastInGroup.end), s! >= glastEnd {
                    groups[i].append(e)
                    placed = true
                    break
                }
            }
            if !placed { groups.append([e]) }
        }
        return groups
    }

    private var dayHeaderView: some View {
        guard let d = dayFmt.date(from: date) else { return AnyView(Text(date)) }
        let en = Locale(identifier: "en_US")
        let df = DateFormatter(); df.locale = en; df.dateFormat = "EEE"
        let dn = df.string(from: d)
        let num = Calendar.current.component(.day, from: d)

        return AnyView(
            VStack(spacing: -1) {
                Text(dn)
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundColor(.white.opacity(isToday ? 0.95 : 0.65))
                Text(String(format: "%02d", num))
                    .font(.system(size: 13, weight: isToday ? .bold : .regular, design: .rounded))
                    .foregroundColor(isToday ? .white : .white.opacity(0.7))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 2)
            .background(isToday ? Color.white.opacity(0.15) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 5))
        )
    }
}

// MARK: - 色块

struct TimeBlockView: View {
    let entry: TimeEntry
    let groupCount: Int
    let groupIndex: Int

    var body: some View {
        let (y, h) = layout()
        let blockH = max(h - 1, 10)
        let subW = (colW - 2) / CGFloat(groupCount)
        let xOff = CGFloat(groupIndex) * subW + 1

        VStack(alignment: .leading, spacing: 0) {
            Text(entry.name)
                .font(.system(size: blockFontSize, weight: .semibold))
                .lineLimit(1)
                .foregroundColor(.white)
            if blockH > 14 {
                Text("\(entry.category) · \(entry.project)")
                    .font(.system(size: blockFontSize - 1))
                    .lineLimit(1)
                    .foregroundColor(.white.opacity(0.85))
            }
        }
        .padding(.horizontal, 2)
        .padding(.vertical, 1)
        .frame(width: max(subW - 1, 20), height: blockH, alignment: .topLeading)
        .background(morandiColor(entry.category))
        .cornerRadius(3)
        .offset(x: xOff, y: y)
    }

    private func layout() -> (CGFloat, CGFloat) {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let s = iso.date(from: entry.start),
              let ed = iso.date(from: entry.end) else { return (120, 30) }
        let cal = Calendar.current
        let sh = CGFloat(cal.component(.hour, from: s))
        let sm = CGFloat(cal.component(.minute, from: s))
        let eh = CGFloat(cal.component(.hour, from: ed))
        let em = CGFloat(cal.component(.minute, from: ed))
        let startH = CGFloat(hourStart)
        var top = ((sh - startH) * 60 + sm) / 60 * hourHeight
        var bot = ((eh - startH) * 60 + em) / 60 * hourHeight
        if sh < startH { top += 24 * hourHeight }
        if eh < startH { bot += 24 * hourHeight }
        return (max(0, top), max(8, bot - top))
    }
}

// MARK: - 莫兰迪色系

func morandiColor(_ cat: String) -> Color {
    switch cat {
    case "Research":       return Color(red: 0.48, green: 0.56, blue: 0.63).opacity(0.55)
    case "Work":           return Color(red: 0.56, green: 0.68, blue: 0.54).opacity(0.55)
    case "Entertainment":  return Color(red: 0.76, green: 0.58, blue: 0.58).opacity(0.55)
    case "Entertainmen":   return Color(red: 0.76, green: 0.58, blue: 0.58).opacity(0.55)
    case "Web":            return Color(red: 0.68, green: 0.64, blue: 0.62).opacity(0.52)
    case "Offline":        return Color(red: 0.58, green: 0.58, blue: 0.58).opacity(0.45)
    default:               return Color(red: 0.72, green: 0.68, blue: 0.72).opacity(0.45)
    }
}
