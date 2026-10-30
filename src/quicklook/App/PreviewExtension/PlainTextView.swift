import AppKit

/// A scrollable, read-only, monospaced view of a file's text (the fallback for .toml files that
/// aren't sprites; it can't hand them back to Apple's own text preview).
final class PlainTextView: NSScrollView {
    init(data: Data) {
        super.init(frame: .zero)
        let textView = NSTextView()
        textView.isEditable = false
        textView.isSelectable = true
        textView.isRichText = false
        textView.font = .monospacedSystemFont(ofSize: NSFont.systemFontSize, weight: .regular)
        textView.textContainerInset = NSSize(width: 8, height: 8)
        textView.autoresizingMask = [.width]
        textView.isVerticallyResizable = true
        textView.textContainer?.widthTracksTextView = true
        // UTF-8 first; Latin-1 decodes any bytes at all, so something always shows
        textView.string = String(data: data, encoding: .utf8)
            ?? String(data: data, encoding: .isoLatin1)
            ?? ""
        documentView = textView
        hasVerticalScroller = true
        hasHorizontalScroller = false
        autohidesScrollers = true
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) is not used")
    }
}
