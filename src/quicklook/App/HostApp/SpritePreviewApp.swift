import AppKit
import SwiftUI

// The host app only exists to carry the QuickLook extensions; opening it once registers them.

@main
struct SpritePreviewApp: App {
    var body: some Scene {
        WindowGroup("GlitchyGames Sprite Preview") {
            InstructionsView()
        }
        .windowResizability(.contentSize)
    }
}

struct InstructionsView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("GlitchyGames Sprite Preview")
                .font(.title)
            Text("Select a GlitchyGames sprite .toml in Finder and press space to see it drawn, with animations playing. Finder thumbnails show the sprite too.")
            Text("If nothing changes, turn on the GlitchyGames Sprite Preview extensions under Login Items & Extensions → Quick Look in System Settings.")
            Button("Open Extension Settings") {
                if let url = URL(string: "x-apple.systempreferences:com.apple.ExtensionsPreferences") {
                    NSWorkspace.shared.open(url)
                }
            }
        }
        .padding(24)
        .frame(width: 440)
    }
}
