// Runs a live /ask call and renders the two-tier result the same way cached
// answers render (§7). Used by ValueSwapView (solve) and AskView (chat).
import SwiftUI

@MainActor
final class LiveAnswerModel: ObservableObject {
    @Published var reply: AskReply?
    @Published var isLoading = false
    @Published var error: String?

    private var task: Task<Void, Never>?

    /// Start (or restart) a live call, cancelling any in-flight one.
    func start(prompt: String, mode: AskMode, context: String?) {
        task?.cancel()
        task = Task { await run(prompt: prompt, mode: mode, context: context) }
    }

    /// Cancel an in-flight call (e.g. the user navigated away) and clear loading.
    func cancel() {
        task?.cancel()
        task = nil
        isLoading = false
    }

    private func run(prompt: String, mode: AskMode, context: String?) async {
        isLoading = true
        error = nil
        reply = nil
        defer { isLoading = false }
        do {
            let result = try await AskService.ask(prompt: prompt, mode: mode, context: context)
            if Task.isCancelled { return }   // user left mid-call — drop the result
            reply = result
        } catch is CancellationError {
            // navigated away; nothing to show
        } catch {
            if !Task.isCancelled { self.error = error.localizedDescription }
        }
    }
}

/// Shows loading → result/error for a live /ask answer.
struct LiveResultView: View {
    let title: String
    @ObservedObject var model: LiveAnswerModel
    /// Called when the user taps retry.
    let retry: () -> Void

    var body: some View {
        Group {
            if let reply = model.reply {
                ScrollView {
                    VStack(alignment: .leading, spacing: 10) {
                        SummaryText(summary: reply.summary)
                        if !reply.answer.isEmpty {
                            Divider()
                            WorkingView(working: reply.answer)
                        }
                    }
                }
            } else if let error = model.error {
                VStack(spacing: 10) {
                    Text(error)
                        .font(.footnote)
                        .foregroundStyle(.red)
                        .multilineTextAlignment(.center)
                    Button("Retry", action: retry)
                }
                .frame(maxWidth: .infinity, minHeight: 120)
            } else {
                // Loading (and the initial pre-start state) — sized so the view
                // reliably appears and its .task fires.
                VStack(spacing: 8) {
                    ProgressView()
                    Text("Solving…").font(.footnote).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, minHeight: 140)
            }
        }
        .navigationTitle(title)
        // Leaving the result cancels an in-flight call and frees the parent's button.
        .onDisappear { model.cancel() }
    }
}
