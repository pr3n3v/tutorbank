#if DEBUG
// Launch-argument-gated preview for screenshots/UI tests only (never in release).
// -uitestPreviewAnswer  → AnswerView for the first cached diagram question
// -uitestPreviewDiagram → DiagramZoomView for that question's diagram
import SwiftUI

struct PreviewHarness: View {
    @EnvironmentObject private var store: BankStore
    let mode: String

    private var firstDiagramQuestion: Question? {
        store.bank?.subjects
            .flatMap { $0.units }
            .flatMap { $0.questions }
            .first { q in
                q.answers.contains { ($0.diagramWatchUrl != nil) && (($0.answer ?? "").isEmpty == false) }
            }
    }

    // The answer with the most ```-fenced blocks — best shows the monospaced code fix.
    private var codeHeavyQuestion: Question? {
        store.bank?.subjects
            .flatMap { $0.units }
            .flatMap { $0.questions }
            .max { a, b in fenceCount(a) < fenceCount(b) }
    }

    private func fenceCount(_ q: Question) -> Int {
        (q.defaultAnswer?.answer ?? "").components(separatedBy: "```").count - 1
    }

    var body: some View {
        NavigationStack {
            if let q = codeHeavyQuestion ?? firstDiagramQuestion, let a = q.defaultAnswer {
                if mode == "diagram",
                   let img = store.diagramDetailImage(for: a.id) ?? store.diagramImage(for: a.id) {
                    DiagramZoomView(image: img)
                } else {
                    AnswerView(question: q)
                }
            } else {
                Text("no cached diagram content").font(.footnote)
            }
        }
    }
}
#endif
