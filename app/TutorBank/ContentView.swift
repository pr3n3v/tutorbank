// iOS companion placeholder — M4 brings full answers, the verification queue,
// and the content browser (CLAUDE.md §7, §9).
import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "applewatch")
                .font(.system(size: 48))
                .foregroundStyle(.tint)
            Text("TutorBank")
                .font(.title.weight(.semibold))
            Text("Companion features arrive in M4.\nThe watch app carries the bank.")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
    }
}
