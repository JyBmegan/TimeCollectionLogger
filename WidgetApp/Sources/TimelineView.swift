import SwiftUI
import AppKit

private let hourStart = 8
private let hourEnd = 27
private let totalHours = hourEnd - hourStart
private let blockFontSize: CGFloat = 11

private let dayFmt: DateFormatter = {
    let f = DateFormatter()
    f.locale = Locale(identifier: "en_US_POSIX")
    f.dateFormat = "yyyy-MM-dd"
    return f
}()

struct TimelineView: View {
    let data: WidgetData?

    var body: some View {
        if let data = data {
            GeometryReader { geo in
                let colW: CGFloat = max(60, (geo.size.width - 40) / 7 - 4)
                let hourH: CGFloat = max(28, (geo.size.height - 60) / CGFloat(totalHours))

                let byDay = buildFilteredDict(data.entries)
                let days = buildDays(from: data.weekStart)

                HStack(alignment: .top, spacing: 4) {
                    VStack(alignment: .trailing, spacing: 0) {
                        Color.clear.frame(height: 32)
                        ForEach(hourStart..<hourEnd, id: \.self) { h in
                            let d = h <= 24 ? h : h - 24
                            Text(String(format: "%02d:00", d))
                                .font(.system(size: 10, weight: .medium, design: .monospaced))
                                .foregroundColor(.white.opacity(0.55))
                                .frame(height: hourH, alignment: .top)
                        }
                    }
                    .frame(width: 34)
                    .padding(.trailing, 4)

                    ForEach(days, id: \.self) { day in
                        DayColumn(date: day, entries: byDay[day] ?? [],
                                  colW: colW, hourHeight: hourH)
                    }
                }
                .frame(height: CGFloat(totalHours) * hourH + 32)
            }
        } else {
            Text("加载中...")
                .font(.system(size: 13))
                .foregroundColor(.white.opacity(0.4))
        }
    }

    private func buildFilteredDict(_ entries: [TimeEntry]) -> [String: [TimeEntry]] {
        let cleaned = entries.filter { $0.durationMin >= 3 }.map(cleanEntry)
        let allByDay = groupByDay(cleaned)
        var result: [String: [TimeEntry]] = [:]
        for (day, dayEntries) in allByDay {
            result[day] = mergeAdjacent(dayEntries)
        }
        return result
    }

    private func cleanEntry(_ e: TimeEntry) -> TimeEntry {
        var name = e.name
        for p in ["VSCode: ", "Web: ", "Notion: ", "Microsoft Excel: "] {
            if name.hasPrefix(p) { name = String(name.dropFirst(p.count)) }
        }
        return TimeEntry(category: e.category, project: e.project,
                         start: e.start, end: e.end, name: name, durationMin: e.durationMin)
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

    private func mergeGap(for category: String) -> TimeInterval {
        switch category {
        case "Research", "Exploration", "Work": return 1800
        case "Entertainment", "Entertainmen", "Web": return 300
        default: return 600
        }
    }

    private func mergeAdjacent(_ entries: [TimeEntry]) -> [TimeEntry] {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let sorted = entries.sorted { a, _ in
            (iso.date(from: a.start) ?? Date.distantPast) < (iso.date(from: a.start) ?? Date.distantPast)
        }
        var merged: [TimeEntry] = []
        for e in sorted {
            var found = false
            for i in merged.indices.reversed() {
                let prev = merged[i]
                guard prev.category == e.category, prev.project == e.project,
                      let prevEnd = iso.date(from: prev.end),
                      let thisStart = iso.date(from: e.start),
                      thisStart.timeIntervalSince(prevEnd) < mergeGap(for: e.category)
                else { continue }
                merged[i] = TimeEntry(category: prev.category, project: prev.project,
                    start: prev.start, end: maxIso(prev.end, e.end),
                    name: prev.name.count >= e.name.count ? prev.name : e.name,
                    durationMin: prev.durationMin + e.durationMin)
                found = true; break
            }
            if !found { merged.append(e) }
        }
        return merged
    }

    private func maxIso(_ a: String, _ b: String) -> String {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let da = iso.date(from: a), let db = iso.date(from: b) else { return a }
        return da >= db ? a : b
    }
}

// MARK: - 单日列

struct DayColumn: View {
    let date: String
    let entries: [TimeEntry]
    let colW: CGFloat
    let hourHeight: CGFloat

    private var isToday: Bool {
        return date == dayFmt.string(from: Date())
    }

    var body: some View {
        VStack(spacing: 0) {
            dayHeaderView
                .frame(width: colW, height: 32)

            ZStack(alignment: .topLeading) {
                VStack(spacing: 0) {
                    ForEach(0..<totalHours, id: \.self) { i in
                        Rectangle()
                            .fill(Color.white.opacity(i % 2 == 0 ? 0.06 : 0.025))
                            .frame(width: colW, height: hourHeight)
                    }
                }

                let slices = buildTimeSlices(entries)
                ForEach(0..<slices.count, id: \.self) { i in
                    let sl = slices[i]
                    ForEach(0..<sl.entries.count, id: \.self) { j in
                        TimeBlockView(entry: sl.entries[j],
                                      groupCount: sl.entries.count,
                                      groupIndex: j,
                                      colW: colW, hourHeight: hourHeight,
                                      sliceStart: sl.start, sliceEnd: sl.end)
                    }
                }
            }
            .frame(width: colW)
        }
    }

    struct TimeSlice { let start: String; let end: String; let entries: [TimeEntry] }

    private func buildTimeSlices(_ entries: [TimeEntry]) -> [TimeSlice] {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard !entries.isEmpty else { return [] }
        var points = Set<String>()
        for e in entries { points.insert(e.start); points.insert(e.end) }
        let sorted = points.sorted { a, b in
            (iso.date(from: a) ?? Date.distantPast) < (iso.date(from: b) ?? Date.distantPast)
        }
        var slices: [TimeSlice] = []
        for i in 0..<(sorted.count - 1) {
            let t1 = sorted[i], t2 = sorted[i+1]
            guard let d1 = iso.date(from: t1), let d2 = iso.date(from: t2), d2 > d1 else { continue }
            let active = entries.filter { e in
                guard let es = iso.date(from: e.start), let ee = iso.date(from: e.end) else { return false }
                return es <= d1 && ee >= d2
            }
            if !active.isEmpty {
                slices.append(TimeSlice(start: t1, end: t2, entries: active))
            }
        }
        return slices
    }

    private var dayHeaderView: some View {
        guard let d = dayFmt.date(from: date) else { return AnyView(Text(date)) }
        let en = Locale(identifier: "en_US")
        let df = DateFormatter(); df.locale = en; df.dateFormat = "EEE M/d"
        return AnyView(
            Text(df.string(from: d))
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(.white.opacity(0.85))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 4)
                .background(Color.white.opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 5))
        )
    }
}

// MARK: - 色块

struct TimeBlockView: View {
    let entry: TimeEntry
    let groupCount: Int
    let groupIndex: Int
    let colW: CGFloat
    let hourHeight: CGFloat
    let sliceStart: String
    let sliceEnd: String

    var body: some View {
        let (y, h) = sliceLayout()
        let blockH = max(h - 1, 2)
        let subW = (colW - 2) / CGFloat(groupCount)
        let xOff = CGFloat(groupIndex) * subW + 1

        Button(action: {
            NSWorkspace.shared.open(URL(string: "https://www.notion.so/36679f2dabbc8034b450e66d5596cc22")!)
        }) {
            Text(entry.project)
                .font(.system(size: min(blockFontSize, colW / 9), weight: .semibold))
                .lineLimit(1)
                .truncationMode(.tail)
                .minimumScaleFactor(0.6)
                .foregroundColor(.white)
                .padding(.horizontal, 3)
                .padding(.vertical, 2)
                .frame(width: max(subW - 1, 24), height: blockH, alignment: .topLeading)
                .background(blockColor(entry.category))
                .cornerRadius(3)
        }
        .buttonStyle(.plain)
        .offset(x: xOff, y: y)
    }

    private func sliceLayout() -> (CGFloat, CGFloat) {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let s = iso.date(from: sliceStart),
              let ed = iso.date(from: sliceEnd) else { return (0, 10) }
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
        return (max(0, top), max(0, bot - top))
    }
}

// MARK: - 配色

func blockColor(_ cat: String) -> Color {
    switch cat {
    case "Research":       return Color(red: 0.38, green: 0.50, blue: 0.72).opacity(0.70)
    case "Exploration":    return Color(red: 0.55, green: 0.45, blue: 0.70).opacity(0.70)
    case "Trivia":         return Color(red: 0.62, green: 0.58, blue: 0.52).opacity(0.70)
    case "Work":           return Color(red: 0.56, green: 0.68, blue: 0.54).opacity(0.70)
    case "Entertainment":  return Color(red: 0.76, green: 0.58, blue: 0.58).opacity(0.70)
    case "Entertainmen":   return Color(red: 0.76, green: 0.58, blue: 0.58).opacity(0.70)
    case "Web":            return Color(red: 0.68, green: 0.64, blue: 0.62).opacity(0.60)
    case "Offline":        return Color(red: 0.58, green: 0.58, blue: 0.58).opacity(0.45)
    default:               return Color(red: 0.72, green: 0.68, blue: 0.72).opacity(0.45)
    }
}
