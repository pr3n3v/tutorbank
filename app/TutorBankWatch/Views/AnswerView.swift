// THE glance screen (CLAUDE.md §1, §7): the one-line summary in large type,
// plus the watch-sized diagram PNG when one exists. No steps, no pedagogy.
// (Value-swap numeric input arrives in M5.)
import SwiftUI

struct AnswerView: View {
    @EnvironmentObject private var store: BankStore
    let question: Question

    private var isCodeQuestion: Bool {
        question.qtype == "program" || question.qtype == "predict_output"
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                if let answer = question.defaultAnswer {
                    Text(answer.summary)
                        .font(.title3.weight(.semibold))
                        .minimumScaleFactor(0.6)

                    // Gate on the bank, not just file existence — a cached PNG whose
                    // answer no longer has a watch diagram is stale, not decoration.
                    if answer.diagramWatchUrl != nil,
                       let image = store.diagramImage(for: answer.id) {
                        // Tap → full-screen zoom/pan viewer (§7); large automata are
                        // read here on the watch, backed by the high-res detail PNG.
                        NavigationLink {
                            DiagramZoomView(
                                image: store.diagramDetailImage(for: answer.id) ?? image
                            )
                        } label: {
                            Image(uiImage: image)
                                .resizable()
                                .scaledToFit()
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.plain)
                    }

                    // The full exam-scoring working (§1, §7a) — the marks live here.
                    if let working = answer.answer, !working.isEmpty {
                        Divider()
                        workingView(working)
                    }

                    if let followups = answer.followups, !followups.isEmpty {
                        Divider()
                        ForEach(followups, id: \.q) { followup in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(followup.q).font(.caption2).foregroundStyle(.secondary)
                                Text(followup.a).font(.footnote)
                            }
                        }
                    }
                } else {
                    Text("No answer cached for this question.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle("Answer")
    }

    // Renders prose proportional and ```-fenced code/pseudocode monospaced (§7a),
    // so algorithm blocks keep their alignment on the small screen.
    @ViewBuilder
    private func workingView(_ working: String) -> some View {
        if working.contains("```") {
            ForEach(Array(codeSegments(working).enumerated()), id: \.offset) { _, seg in
                if seg.isCode {
                    Text(seg.text)
                        .font(.system(size: 13, design: .monospaced))
                        .frame(maxWidth: .infinity, alignment: .leading)
                } else {
                    Text(seg.text).font(.footnote)
                }
            }
        } else {
            // No fences: whole-answer monospace only for pure code/output questions.
            Text(working)
                .font(isCodeQuestion ? .system(.footnote, design: .monospaced) : .footnote)
        }
    }

    /// Split on ``` fences into alternating prose / code segments, dropping a
    /// leading language hint (```java) and empty pieces.
    private func codeSegments(_ text: String) -> [(text: String, isCode: Bool)] {
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
