// THE glance screen (CLAUDE.md §1, §7): the one-line summary in large type,
// plus the watch-sized diagram PNG when one exists. No steps, no pedagogy.
// (Value-swap numeric input arrives in M5.)
import SwiftUI

struct AnswerView: View {
    @EnvironmentObject private var store: BankStore
    let question: Question

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
                        Image(uiImage: image)
                            .resizable()
                            .scaledToFit()
                            .frame(maxWidth: .infinity)
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
}
