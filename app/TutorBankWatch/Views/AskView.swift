// "Ask" (§7): dictation/Scribble a question → /ask (deepseek-v4-flash, chat) →
// one-tier-plus-working reply. Used both as a contextual "ask about this" and as
// the standalone chat tab (context == nil).
import SwiftUI

struct AskView: View {
    /// When set, the question this ask is about (context for the model).
    var contextQuestion: Question?

    @StateObject private var model = LiveAnswerModel()
    @State private var query = ""
    @State private var showResult = false

    var body: some View {
        Form {
            Section(contextQuestion == nil ? "Ask a question" : "Ask about this") {
                TextField("Type or dictate…", text: $query)
                if let q = contextQuestion {
                    Text(q.text).font(.caption2).foregroundStyle(.secondary).lineLimit(2)
                }
            }
            Section {
                NavigationLink(isActive: $showResult) {
                    LiveResultView(title: "Answer", model: model, retry: send)
                } label: {
                    Label("Ask", systemImage: "sparkles")
                }
                .disabled(query.trimmingCharacters(in: .whitespaces).isEmpty || model.isLoading)
                .simultaneousGesture(TapGesture().onEnded(send))
            }
        }
        .navigationTitle("Ask")
    }

    private func send() {
        let prompt = query.trimmingCharacters(in: .whitespaces)
        guard !prompt.isEmpty else { return }
        showResult = true
        model.start(prompt: prompt, mode: .chat, context: contextQuestion?.text)
    }
}
