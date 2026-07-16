// Full-screen diagram viewer (CLAUDE.md §6, §7): large automata are READ on the watch.
// Digital Crown zooms, drag pans. Uses the high-res detail PNG when cached, so text
// stays legible at high zoom.
import SwiftUI

struct DiagramZoomView: View {
    let image: UIImage

    @State private var zoom: Double = 1.0
    @State private var offset: CGSize = .zero
    @State private var dragBase: CGSize = .zero

    var body: some View {
        Image(uiImage: image)
            .resizable()
            .scaledToFit()
            .scaleEffect(zoom)
            .offset(offset)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .clipped()
            .gesture(
                DragGesture()
                    .onChanged { value in
                        offset = CGSize(
                            width: dragBase.width + value.translation.width,
                            height: dragBase.height + value.translation.height
                        )
                    }
                    .onEnded { _ in dragBase = offset }
            )
            .focusable(true)
            .digitalCrownRotation(
                $zoom,
                from: 1.0,
                through: 8.0,
                by: 0.1,
                sensitivity: .medium,
                isContinuous: false,
                isHapticFeedbackEnabled: true
            )
            .onChange(of: zoom) { _, newZoom in
                // Zooming back out re-centers so the diagram can't get lost off-screen.
                if newZoom <= 1.05 {
                    offset = .zero
                    dragBase = .zero
                }
            }
            .ignoresSafeArea()
            .navigationTitle("Diagram")
    }
}
