// THE answer screen (CLAUDE.md §1, §7): boxed summary, diagram (tap→zoom), full
// worked solution, then Change-values (if the question has variables) and Ask.
import SwiftUI

struct AnswerView: View {
    @EnvironmentObject private var store: BankStore
    let question: Question

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                if let answer = question.defaultAnswer {
                    // Lift the 4-line cap when no Working section follows (diagram-only
                    // or summary-only answers) — else the glance line silently truncates
                    // with nothing below to carry the rest (mirrors LiveResultView).
                    SummaryText(summary: answer.summary, unbounded: (answer.answer ?? "").isEmpty)

                    // Gate on the bank, not just file existence — a cached PNG whose
                    // answer no longer has a watch diagram is stale, not decoration.
                    if answer.diagramWatchUrl != nil,
                       let image = store.diagramImage(for: answer.id) {
                        // Tap → full-screen zoom/pan viewer (§7).
                        NavigationLink {
                            DiagramZoomView(
                                image: store.diagramDetailImage(for: answer.id) ?? image
                            )
                        } label: {
                            VStack(spacing: 2) {
                                Image(uiImage: image)
                                    .resizable()
                                    .scaledToFit()
                                    .frame(maxWidth: .infinity)
                                // Nothing else marks this as interactive at a glance —
                                // spell it out so the zoom viewer is discoverable.
                                Text("tap to zoom")
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity)
                            // Without this, .buttonStyle(.plain) only makes the
                            // leaf subviews tappable — the gap and the margin
                            // around the shorter, centered caption go dead.
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }

                    // The full exam-scoring working (§1, §7a) — the marks live here.
                    if let working = answer.answer, !working.isEmpty {
                        Divider()
                        WorkingView(working: working, forceMono: question.isCode)
                    }

                    if let followups = answer.followups, !followups.isEmpty {
                        Divider()
                        FollowupsView(followups: followups)
                    }

                    Divider()
                    actions
                } else {
                    Text("No answer cached for this question.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    actions
                }
            }
        }
        .navigationTitle("Answer")
    }

    @ViewBuilder
    private var actions: some View {
        VStack(spacing: 6) {
            if question.hasVariables {
                NavigationLink {
                    ValueSwapView(question: question)
                } label: {
                    Label("Change values", systemImage: "slider.horizontal.3")
                }
                .buttonStyle(.bordered)
            }
            NavigationLink {
                AskView(contextQuestion: question)
            } label: {
                Label("Ask about this", systemImage: "sparkles")
            }
            .buttonStyle(.bordered)
        }
    }
}
