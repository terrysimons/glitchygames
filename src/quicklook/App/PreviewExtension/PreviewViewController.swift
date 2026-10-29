import AppKit
import Quartz
import SpriteCore

/// The QuickLook preview for every .toml file: a static sprite is drawn as one image, any other
/// sprite as a film strip of every animation playing, and anything else is shown as text, since macOS gives every .toml the one type public.toml.
final class PreviewViewController: NSViewController, QLPreviewingController {
    private static let spritePreviewSize = NSSize(width: 512, height: 512)
    private static let textPreviewSize = NSSize(width: 800, height: 600)
    /// The film strip asks for this width, and to be as tall as its rows up to the maximum
    /// (taller ones scroll)
    private static let filmStripPreviewWidth: CGFloat = 720
    private static let filmStripMaximumHeight: CGFloat = 720

    override func loadView() {
        view = NSView()
    }

    func preparePreviewOfFile(at url: URL) async throws {
        let data = try Data(contentsOf: url)
        let contentView: NSView
        switch SpriteLoader.load(data: data) {
        case .sprite(let sprite) where FilmStripLayout.showsFilmStrip(for: sprite):
            let filmStrip = FilmStripScrollView(sprite: sprite)
            contentView = filmStrip
            preferredContentSize = filmStrip.preferredContentSize(
                width: Self.filmStripPreviewWidth,
                maximumHeight: Self.filmStripMaximumHeight
            )
        case .sprite(let sprite):
            contentView = SpritePlayerView(sprite: sprite)
            preferredContentSize = Self.spritePreviewSize
        case .notSprite:
            contentView = PlainTextView(data: data)
            preferredContentSize = Self.textPreviewSize
        case .failed(let reason):
            contentView = Self.failureView(reason: reason, data: data)
            preferredContentSize = Self.textPreviewSize
        }
        show(contentView)
    }

    private func show(_ contentView: NSView) {
        view.subviews.forEach { $0.removeFromSuperview() }
        contentView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(contentView)
        NSLayoutConstraint.activate([
            contentView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            contentView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            contentView.topAnchor.constraint(equalTo: view.topAnchor),
            contentView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])
    }

    /// A sprite file that can't be drawn: the reason in red above the file's text
    private static func failureView(reason: String, data: Data) -> NSView {
        let banner = NSTextField(wrappingLabelWithString: "Can't draw this sprite: \(reason)")
        banner.textColor = .systemRed
        banner.setContentCompressionResistancePriority(.required, for: .vertical)
        let stack = NSStackView(views: [banner, PlainTextView(data: data)])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 8
        stack.edgeInsets = NSEdgeInsets(top: 8, left: 8, bottom: 0, right: 0)
        return stack
    }
}
