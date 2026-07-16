#if DEBUG
// Launch-argument-gated preview for screenshots/UI tests only (never in release).
//   -uitestPreviewAnswer   → AnswerView for the most code-heavy cached question
//   -uitestPreviewDiagram  → DiagramZoomView for that question's diagram
//   -uitestPreviewVarAnswer→ AnswerView for a question with variables (shows actions)
//   -uitestPreviewValueSwap→ ValueSwapView for that question
//   -uitestPreviewLiveSolve→ auto-runs a live solve, shows the result
//   -uitestPreviewLiveAsk  → auto-runs a live chat ask, shows the result
import SwiftUI

struct PreviewHarness: View {
    @EnvironmentObject private var store: BankStore
    let mode: String

    private var allQuestions: [Question] {
        store.bank?.subjects.flatMap { $0.units }.flatMap { $0.questions } ?? []
    }
    private var firstDiagramQuestion: Question? {
        allQuestions.first { q in
            q.answers.contains { ($0.diagramWatchUrl != nil) && (($0.answer ?? "").isEmpty == false) }
        }
    }
    private var codeHeavyQuestion: Question? {
        let programs = allQuestions.filter { $0.qtype == "program" && fenceCount($0) > 0 }
        return (programs.max { fenceCount($0) < fenceCount($1) }) ?? allQuestions.max { fenceCount($0) < fenceCount($1) }
    }
    private var variableQuestion: Question? { allQuestions.first { $0.hasVariables } }
    private func fenceCount(_ q: Question) -> Int {
        (q.defaultAnswer?.answer ?? "").components(separatedBy: "```").count - 1
    }

    var body: some View {
        NavigationStack {
            switch mode {
            case "diagram":
                if let q = codeHeavyQuestion ?? firstDiagramQuestion, let a = q.defaultAnswer,
                   let img = store.diagramDetailImage(for: a.id) ?? store.diagramImage(for: a.id) {
                    DiagramZoomView(image: img)
                } else { missing }
            case "varanswer":
                if let q = variableQuestion { AnswerView(question: q).environmentObject(store) } else { missing }
            case "valueswap":
                if let q = variableQuestion { ValueSwapView(question: q) } else { missing }
            case "livesolve":
                if let q = variableQuestion { AutoLive(prompt: solvePrompt(q), mode: .solve, context: q.text, title: "Result") } else { missing }
            case "liveask":
                AutoLive(prompt: "What is the time complexity of binary search, and why?", mode: .chat, context: nil, title: "Answer")
            case "tutorroot":
                TutorRootView().environmentObject(store)
            default: // "answer"
                if let q = codeHeavyQuestion, let a = q.defaultAnswer, !(a.answer ?? "").isEmpty {
                    AnswerView(question: q).environmentObject(store)
                } else { missing }
            }
        }
    }

    private func solvePrompt(_ q: Question) -> String {
        let v = q.variables?.first
        let name = v?.name ?? "value"
        // bump the default to exercise a genuinely different instance
        let bumped = (Int(v?.defaultText ?? "") ?? 0) + 10
        return "Re-solve this exam question using these values: \(name) = \(bumped)."
    }

    private var missing: some View { Text("no matching content").font(.footnote) }
}

/// Runs a live /ask call as soon as it appears — for screenshotting the live result.
private struct AutoLive: View {
    let prompt: String
    let mode: AskMode
    let context: String?
    let title: String
    @StateObject private var model = LiveAnswerModel()

    var body: some View {
        LiveResultView(title: title, model: model) {
            model.start(prompt: prompt, mode: mode, context: context)
        }
        .task { model.start(prompt: prompt, mode: mode, context: context) }
    }
}
#endif
