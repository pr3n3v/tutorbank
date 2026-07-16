// Reusable answer-rendering pieces, shared by the cached AnswerView and the live
// results from /ask (ValueSwapView, AskView). Keeps rendering identical everywhere.
import SwiftUI

/// The boxed one-line result, large type (the glance).
struct SummaryText: View {
    let summary: String
    var body: some View {
        Text(summary)
            .font(.title3.weight(.semibold))
            .minimumScaleFactor(0.6)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Full working: prose proportional, ```-fenced code/pseudocode monospaced (§7a).
struct WorkingView: View {
    let working: String
    /// Whole-answer monospace fallback for pure code answers that lack fences.
    var forceMono = false

    var body: some View {
        if working.contains("```") {
            VStack(alignment: .leading, spacing: 6) {
                ForEach(Array(Self.segments(working).enumerated()), id: \.offset) { _, seg in
                    if seg.isCode {
                        Text(seg.text)
                            .font(.system(size: 13, design: .monospaced))
                            .frame(maxWidth: .infinity, alignment: .leading)
                    } else {
                        Text(seg.text)
                            .font(.footnote)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
        } else {
            Text(working)
                .font(forceMono ? .system(.footnote, design: .monospaced) : .footnote)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    /// Split on ``` fences into alternating prose / code segments, dropping a
    /// leading language hint (```java) and empty pieces.
    static func segments(_ text: String) -> [(text: String, isCode: Bool)] {
        var out: [(String, Bool)] = []
        for (i, part) in text.components(separatedBy: "```").enumerated() {
            var s = part
            let isCode = i % 2 == 1
            if isCode, let nl = s.firstIndex(of: "\n") {
                let hint = s[..<nl].trimmingCharacters(in: .whitespaces)
                if !hint.isEmpty, !hint.contains(" "), hint.count < 12 {
                    s = String(s[s.index(after: nl)...])
                }
            }
            let trimmed = s.trimmingCharacters(in: .newlines)
            if !trimmed.isEmpty { out.append((trimmed, isCode)) }
        }
        return out
    }
}

struct FollowupsView: View {
    let followups: [Followup]
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            ForEach(followups, id: \.q) { followup in
                VStack(alignment: .leading, spacing: 2) {
                    Text(followup.q).font(.caption2).foregroundStyle(.secondary)
                    Text(followup.a).font(.footnote)
                }
            }
        }
    }
}
