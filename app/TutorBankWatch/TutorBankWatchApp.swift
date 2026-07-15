import SwiftUI

@main
struct TutorBankWatchApp: App {
    @StateObject private var store = BankStore()

    var body: some Scene {
        WindowGroup {
            TimerHomeView()
                .environmentObject(store)
                // Best-effort launch refresh (spec §7 "on launch/sync"); cached
                // content already loaded — failure here changes nothing visible.
                .task { await store.sync() }
        }
    }
}
