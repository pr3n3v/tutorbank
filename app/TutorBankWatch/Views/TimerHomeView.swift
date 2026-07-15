// The landing screen IS a working study-session timer (CLAUDE.md §7) — boring and
// plausible on a tutor's wrist. Long-press the timer face to enter the tutor UI;
// leaving the app (wrist down, backgrounding) always returns here.
import SwiftUI

@MainActor
final class StudyTimer: ObservableObject {
    @Published private(set) var isRunning = false
    private var accumulated: TimeInterval = 0
    private var startedAt: Date?

    // watchOS terminates suspended apps routinely; state persists so a running
    // session resumes exactly (wall-clock math) after relaunch — spec §7 gotchas.
    private static let stateKey = "studyTimer.state.v1"

    init() {
        // UI tests pass -uitestReset for a hermetic 00:00 starting state.
        if ProcessInfo.processInfo.arguments.contains("-uitestReset") {
            UserDefaults.standard.removeObject(forKey: Self.stateKey)
        }
        restore()
    }

    func elapsed(at date: Date) -> TimeInterval {
        accumulated + (startedAt.map { max(0, date.timeIntervalSince($0)) } ?? 0)
    }

    func startPause() {
        if isRunning {
            accumulated = elapsed(at: Date())
            startedAt = nil
        } else {
            startedAt = Date()
        }
        isRunning.toggle()
        persist()
    }

    func reset() {
        accumulated = 0
        startedAt = nil
        isRunning = false
        persist()
    }

    private func persist() {
        UserDefaults.standard.set(
            [
                "accumulated": accumulated,
                "startedAt": startedAt?.timeIntervalSince1970 ?? -1,
            ] as [String: Double],
            forKey: Self.stateKey
        )
    }

    private func restore() {
        guard let state = UserDefaults.standard.dictionary(forKey: Self.stateKey)
            as? [String: Double] else { return }
        accumulated = state["accumulated"] ?? 0
        if let started = state["startedAt"], started > 0 {
            startedAt = Date(timeIntervalSince1970: started)
            isRunning = true
        }
    }
}

struct TimerHomeView: View {
    @EnvironmentObject private var store: BankStore
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var timer = StudyTimer()
    @State private var showTutor = false

    var body: some View {
        VStack(spacing: 12) {
            // Date-based elapsed time survives watchOS suspending the app mid-session.
            TimelineView(.periodic(from: .now, by: 0.5)) { context in
                Text(Self.format(timer.elapsed(at: context.date)))
                    .font(.system(size: 44, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                    .contentShape(Rectangle())
                    .onLongPressGesture(minimumDuration: 1.2) {
                        showTutor = true
                    }
                    .accessibilityIdentifier("timerDisplay")
            }

            HStack(spacing: 8) {
                Button(timer.isRunning ? "Pause" : "Start") { timer.startPause() }
                    .tint(timer.isRunning ? .orange : .green)
                Button("Reset") { timer.reset() }
                    .tint(.gray)
            }
            .buttonStyle(.borderedProminent)
        }
        .navigationTitle("Study")
        .sheet(isPresented: $showTutor) {
            TutorRootView()
                .environmentObject(store)
        }
        .onChange(of: scenePhase) { _, phase in
            // Auto-return to the timer whenever the app deactivates (spec §7).
            if phase != .active { showTutor = false }
        }
    }

    private static func format(_ interval: TimeInterval) -> String {
        let total = Int(interval)
        let h = total / 3600, m = (total % 3600) / 60, s = total % 60
        return h > 0
            ? String(format: "%d:%02d:%02d", h, m, s)
            : String(format: "%02d:%02d", m, s)
    }
}
