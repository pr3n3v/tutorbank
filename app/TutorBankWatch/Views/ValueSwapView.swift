// "Change values" (§5, §7): edit a question's template variables, then live-solve
// the swapped instance via /ask (deepseek-v4-pro, solve mode).
import SwiftUI

struct ValueSwapView: View {
    let question: Question
    @StateObject private var model = LiveAnswerModel()
    @State private var values: [String: String] = [:]
    @State private var showResult = false

    private var variables: [Variable] { question.variables ?? [] }

    var body: some View {
        Form {
            // No section header here — the nav title already says "Change values";
            // repeating it as a header wasted a full row of vertical space on a
            // screen this small.
            Section {
                ForEach(variables) { v in
                    HStack {
                        Text(v.name).font(.footnote)
                        Spacer()
                        TextField(v.defaultText, text: binding(for: v))
                            .multilineTextAlignment(.trailing)
                            .frame(maxWidth: 90)
                    }
                }
            }
            Section {
                NavigationLink(isActive: $showResult) {
                    LiveResultView(title: "Result", model: model, retry: solve, isCode: question.isCode)
                } label: {
                    Label("Solve", systemImage: "function")
                }
                .disabled(model.isLoading || !allFilled)
                .simultaneousGesture(TapGesture().onEnded { solve() })
            }
        }
        .navigationTitle("Change values")
        .onAppear {
            for v in variables where values[v.name] == nil { values[v.name] = v.defaultText }
        }
    }

    /// A field's effective value: what's typed, or the default when left blank.
    private func value(for v: Variable) -> String {
        let typed = (values[v.name] ?? v.defaultText).trimmingCharacters(in: .whitespaces)
        return typed.isEmpty ? v.defaultText : typed
    }

    private var allFilled: Bool {
        variables.allSatisfy { !value(for: $0).isEmpty }
    }

    private func binding(for v: Variable) -> Binding<String> {
        Binding(
            get: { values[v.name] ?? v.defaultText },
            set: { values[v.name] = $0 }
        )
    }

    private func solve() {
        let changes = variables
            .map { "\($0.name) = \(value(for: $0))" }
            .joined(separator: ", ")
        // Send the question ONCE — as context; the prompt is just the swap instruction
        // (the backend counts prompt+context against its 4000-char cap).
        let prompt = "Re-solve this exam question using these values: \(changes)."
        showResult = true
        model.start(prompt: prompt, mode: .solve, context: question.text)
    }
}
