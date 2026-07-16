import SwiftUI

@main
struct TutorBankWatchApp: App {
    @StateObject private var store = BankStore()

    private var root: some View {
        TimerHomeView()
            .environmentObject(store)
            // Best-effort launch refresh (spec §7 "on launch/sync"); cached
            // content already loaded — failure here changes nothing visible.
            .task { await store.sync() }
    }

    #if DEBUG
    private var previewMode: String? {
        let args = ProcessInfo.processInfo.arguments
        if args.contains("-uitestPreviewDiagram") { return "diagram" }
        if args.contains("-uitestPreviewVarAnswer") { return "varanswer" }
        if args.contains("-uitestPreviewValueSwap") { return "valueswap" }
        if args.contains("-uitestPreviewLiveSolve") { return "livesolve" }
        if args.contains("-uitestPreviewLiveAsk") { return "liveask" }
        if args.contains("-uitestPreviewTutorRoot") { return "tutorroot" }
        if args.contains("-uitestPreviewAnswer") { return "answer" }
        return nil
    }
    #endif

    var body: some Scene {
        WindowGroup {
            #if DEBUG
            if let mode = previewMode {
                PreviewHarness(mode: mode).environmentObject(store)
            } else {
                root
            }
            #else
            root
            #endif
        }
    }
}
