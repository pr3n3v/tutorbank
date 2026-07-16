// Tutor UI root: Subject → Unit → Question → Answer from cache, plus a free-chat
// Ask entry on the Subjects screen (§7). One NavigationStack — a TabView inside the
// presenting .sheet does not render reliably on watchOS.
import SwiftUI

struct TutorRootView: View {
    @EnvironmentObject private var store: BankStore

    var body: some View {
        NavigationStack {
            SubjectListView()
                .navigationDestination(for: Subject.self) { UnitListView(subject: $0) }
                .navigationDestination(for: Unit.self) { QuestionListView(unit: $0) }
                .navigationDestination(for: Question.self) { AnswerView(question: $0) }
        }
    }
}

struct SubjectListView: View {
    @EnvironmentObject private var store: BankStore

    var body: some View {
        Group {
            if let subjects = store.bank?.subjects, !subjects.isEmpty {
                List {
                    // Free-form live chat (§7 "chat tab") — reachable from the top.
                    NavigationLink {
                        AskView(contextQuestion: nil)
                    } label: {
                        Label("Ask a question", systemImage: "sparkles")
                    }
                    ForEach(subjects) { subject in
                        NavigationLink(value: subject) {
                            VStack(alignment: .leading) {
                                Text(subject.code).font(.headline)
                                Text(subject.name).font(.caption2).foregroundStyle(.secondary)
                            }
                        }
                    }
                    footer
                }
            } else {
                VStack(spacing: 8) {
                    Text(store.lastError ?? "No cached content yet.")
                        .font(.footnote)
                        .multilineTextAlignment(.center)
                    syncButton
                }
            }
        }
        .navigationTitle("Subjects")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) { syncButton }
        }
    }

    private var syncButton: some View {
        Button {
            Task { await store.sync() }
        } label: {
            if store.isSyncing {
                ProgressView()
            } else {
                Image(systemName: "arrow.triangle.2.circlepath")
            }
        }
        .disabled(store.isSyncing)
    }

    @ViewBuilder
    private var footer: some View {
        if let lastSync = store.lastSync {
            Text("Synced \(lastSync.formatted(date: .omitted, time: .shortened))")
                .font(.caption2).foregroundStyle(.secondary)
        }
        if let error = store.lastError {
            Text(error).font(.caption2).foregroundStyle(.red)
        }
    }
}

struct UnitListView: View {
    let subject: Subject

    var body: some View {
        List(subject.units.sorted(by: { $0.position < $1.position })) { unit in
            NavigationLink(value: unit) {
                Text(unit.name)
            }
        }
        .navigationTitle(subject.code)
        .overlay {
            if subject.units.isEmpty {
                Text("No units yet.").font(.footnote).foregroundStyle(.secondary)
            }
        }
    }
}

struct QuestionListView: View {
    let unit: Unit

    var body: some View {
        List(unit.questions.sorted(by: { $0.position < $1.position })) { question in
            NavigationLink(value: question) {
                Text(question.text)
                    .font(.footnote)
                    .lineLimit(3)
            }
        }
        .navigationTitle(unit.name)
        .overlay {
            if unit.questions.isEmpty {
                Text("No questions yet.").font(.footnote).foregroundStyle(.secondary)
            }
        }
    }
}
