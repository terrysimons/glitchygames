import AppKit
import QuartzCore
import SpriteCore

/// The film strip preview (spec goal 6) in a vertical scroller, for when the rows are taller
/// than the panel. The strip always takes the scroller's width, so frames wrap instead of
/// scrolling sideways.
final class FilmStripScrollView: NSScrollView {
    private let filmStrip: FilmStripView

    init(sprite: Sprite) {
        filmStrip = FilmStripView(sprite: sprite)
        super.init(frame: .zero)
        hasVerticalScroller = true
        autohidesScrollers = true
        drawsBackground = false
        documentView = filmStrip
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) is not used")
    }

    /// The panel size to ask QuickLook for: the given width, and as tall as the rows up to
    /// maximumHeight (the rest scrolls)
    func preferredContentSize(width: CGFloat, maximumHeight: CGFloat) -> NSSize {
        let height = filmStrip.layoutSize(forWidth: width).height
        return NSSize(width: width, height: min(height, maximumHeight))
    }

    override func tile() {
        super.tile()
        let visible = contentView.bounds.size
        let fitted = filmStrip.layoutSize(forWidth: visible.width)
        filmStrip.setFrameSize(NSSize(width: fitted.width, height: max(fitted.height, visible.height)))
    }
}

/// Every animation of a sprite as a row: its name, every frame (number above, duration below),
/// and the animation playing live at the right end on a checkerboard, with the frame on screen
/// outlined in its strip. Every row plays at once from the moment the preview is on screen.
/// Laid out by SpriteCore's FilmStripLayout, which works top-down, so this view is flipped.
final class FilmStripView: NSView {
    fileprivate static let nameFont = NSFont.boldSystemFont(ofSize: 12)
    fileprivate static let numberFont = NSFont.systemFont(ofSize: 10, weight: .semibold)
    fileprivate static let detailFont = NSFont.monospacedDigitSystemFont(ofSize: 10, weight: .regular)
    private static let maximumNameWidth: CGFloat = 140
    fileprivate static let highlightWidth: CGFloat = 2
    /// How far the outline of the frame on screen sits outside its box
    fileprivate static let highlightOutset: CGFloat = 4

    private let sprite: Sprite
    private let nameWidth: CGFloat
    private let rows: [FilmStripRow]
    private var startTime = CACurrentMediaTime()
    private var displayLink: CADisplayLink?

    override var isFlipped: Bool { true }

    init(sprite: Sprite) {
        self.sprite = sprite
        rows = sprite.animations.map(FilmStripRow.init(animation:))
        // Measured from the labels themselves: a text field draws with padding beyond its text's
        // own width, so the bare text width truncates every name
        let widestName = rows.map { $0.nameLabel.fittingSize.width.rounded(.up) }.max() ?? 0
        nameWidth = min(widestName, Self.maximumNameWidth)
        super.init(frame: .zero)

        wantsLayer = true
        for row in rows {
            layer?.addSublayer(row.separatorLayer)
            for cell in row.cells {
                layer?.addSublayer(cell.checkerboardLayer)
                layer?.addSublayer(cell.frameLayer)
                addSubview(cell.numberLabel)
                addSubview(cell.durationLabel)
            }
            layer?.addSublayer(row.highlightLayer)
            layer?.addSublayer(row.liveCheckerboardLayer)
            layer?.addSublayer(row.liveFrameLayer)
            addSubview(row.nameLabel)
            addSubview(row.liveLabel)
        }
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) is not used")
    }

    func layoutSize(forWidth width: CGFloat) -> CGSize {
        FilmStripLayout(sprite: sprite, width: width, nameWidth: nameWidth).size
    }

    // MARK: Playback

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        displayLink?.invalidate()
        displayLink = nil
        guard window != nil else { return }
        // Auto-play: start every row the moment the preview is on screen
        startTime = CACurrentMediaTime()
        showCurrentFrames(force: true)
        let link = displayLink(target: self, selector: #selector(displayLinkFired(_:)))
        link.add(to: .main, forMode: .common)
        displayLink = link
    }

    @objc private func displayLinkFired(_ link: CADisplayLink) {
        showCurrentFrames(force: false)
        // Every row finished (one frame, or non-looping and done): stop waking up on every
        // display refresh
        let elapsed = CACurrentMediaTime() - startTime
        if rows.allSatisfy({ $0.clock.nextChange(after: elapsed) == nil }) {
            link.isPaused = true
        }
    }

    private func showCurrentFrames(force: Bool) {
        let elapsed = CACurrentMediaTime() - startTime
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        for row in rows {
            let frameNumber = row.clock.frameIndex(at: elapsed)
            if force || frameNumber != row.shownFrameNumber {
                row.shownFrameNumber = frameNumber
                row.showFrame()
            }
        }
        CATransaction.commit()
    }

    // MARK: Layout

    override func viewDidChangeEffectiveAppearance() {
        super.viewDidChangeEffectiveAppearance()
        needsLayout = true
    }

    override func viewDidChangeBackingProperties() {
        super.viewDidChangeBackingProperties()
        needsLayout = true
    }

    override func layout() {
        super.layout()
        let filmStripLayout = FilmStripLayout(sprite: sprite, width: bounds.width, nameWidth: nameWidth)
        let backingScale = max(1, (window?.backingScaleFactor ?? 2).rounded())
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        // Colors resolved here, not once in init, so they follow light and dark mode
        effectiveAppearance.performAsCurrentDrawingAppearance {
            layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor
            for row in rows {
                row.separatorLayer.backgroundColor = NSColor.separatorColor.cgColor
                row.highlightLayer.borderColor = NSColor.systemBlue.cgColor
            }
        }
        for (rowLayout, row) in zip(filmStripLayout.rows, rows) {
            row.apply(
                rowLayout,
                isLast: rowLayout.animationNumber == rows.count - 1,
                cellScale: filmStripLayout.cellScale,
                liveScale: filmStripLayout.liveScale,
                backingScale: backingScale
            )
        }
        CATransaction.commit()
    }

    fileprivate static func label(_ text: String, font: NSFont, color: NSColor, alignment: NSTextAlignment) -> NSTextField {
        let label = NSTextField(labelWithString: text)
        label.font = font
        label.textColor = color
        label.alignment = alignment
        label.lineBreakMode = .byTruncatingTail
        return label
    }

    fileprivate static func pixelLayer() -> CALayer {
        let layer = CALayer()
        layer.magnificationFilter = .nearest
        layer.minificationFilter = .nearest
        layer.contentsGravity = .resize
        return layer
    }

    fileprivate static func checkerboardLayer() -> CALayer {
        let layer = CALayer()
        layer.backgroundColor = SpritePlayerView.checkerboardColor()
        return layer
    }
}

/// One frame's place in a strip: its checkerboard box, the frame, and its two labels
@MainActor
private struct FilmStripCell {
    let checkerboardLayer = FilmStripView.checkerboardLayer()
    let frameLayer = FilmStripView.pixelLayer()
    let numberLabel: NSTextField
    let durationLabel: NSTextField
}

/// The layers, labels, clock and pre-scaled images for one animation's row
@MainActor
private final class FilmStripRow {
    let animation: SpriteAnimation
    let clock: AnimationClock
    var shownFrameNumber = -1

    let nameLabel: NSTextField
    let cells: [FilmStripCell]
    let highlightLayer = CALayer()
    let liveCheckerboardLayer = FilmStripView.checkerboardLayer()
    let liveFrameLayer = FilmStripView.pixelLayer()
    let liveLabel: NSTextField
    let separatorLayer = CALayer()

    /// Each frame pre-scaled with nearest neighbor toward the backing pixels it fills, for the
    /// strip and for the live view (capped at SpriteRenderer.maximumPrescaledSide); rebuilt when
    /// the factor changes
    private var stripImages: [CGImage] = []
    private var stripPrescaleFactor = 0
    private var liveImages: [CGImage] = []
    private var livePrescaleFactor = 0
    private var liveBox = CGRect.zero
    private var liveScale: CGFloat = 1
    private var cellFrameBoxes: [CGRect] = []

    init(animation: SpriteAnimation) {
        self.animation = animation
        clock = SpritePlayerView.clock(for: animation)
        nameLabel = FilmStripView.label(animation.name, font: FilmStripView.nameFont, color: .labelColor, alignment: .left)
        cells = animation.frames.enumerated().map { frameNumber, frame in
            FilmStripCell(
                numberLabel: FilmStripView.label(
                    String(frameNumber),
                    font: FilmStripView.numberFont,
                    color: .labelColor,
                    alignment: .center
                ),
                durationLabel: FilmStripView.label(
                    FilmStripLayout.durationText(frame.duration),
                    font: FilmStripView.detailFont,
                    color: .secondaryLabelColor,
                    alignment: .center
                )
            )
        }
        liveLabel = FilmStripView.label(
            FilmStripLayout.liveLabelText(for: animation),
            font: FilmStripView.detailFont,
            color: .secondaryLabelColor,
            alignment: .center
        )
        highlightLayer.borderWidth = FilmStripView.highlightWidth
    }

    func apply(_ rowLayout: FilmStripLayout.Row, isLast: Bool, cellScale: CGFloat, liveScale: CGFloat, backingScale: CGFloat) {
        let boxSize = SpriteRenderer.largestFrameSize(of: animation)
        nameLabel.frame = rowLayout.nameLabel
        separatorLayer.isHidden = isLast
        separatorLayer.frame = CGRect(
            x: FilmStripLayout.margin,
            y: rowLayout.frame.maxY - 1,
            width: max(0, rowLayout.frame.width - 2 * FilmStripLayout.margin),
            height: 1
        )

        let stripFactor = SpriteRenderer.prescaleFactor(
            frameSize: boxSize,
            pixelScale: Int((cellScale * backingScale).rounded(.down))
        )
        if stripFactor != stripPrescaleFactor {
            stripImages = animation.frames.map { SpriteRenderer.scaledImage(for: $0, scale: stripFactor) }
            stripPrescaleFactor = stripFactor
        }
        cellFrameBoxes = rowLayout.cells.map(\.frameBox)
        for (frameNumber, (cellLayout, cell)) in zip(rowLayout.cells, cells).enumerated() {
            let frame = animation.frames[frameNumber]
            cell.numberLabel.frame = cellLayout.numberLabel
            cell.durationLabel.frame = cellLayout.durationLabel
            cell.checkerboardLayer.frame = cellLayout.frameBox
            cell.frameLayer.frame = Self.frameRect(frame, scale: cellScale, inBox: cellLayout.frameBox)
            cell.frameLayer.contents = stripImages[frameNumber]
        }

        let liveFactor = SpriteRenderer.prescaleFactor(
            frameSize: boxSize,
            pixelScale: Int((liveScale * backingScale).rounded(.down))
        )
        if liveFactor != livePrescaleFactor {
            liveImages = animation.frames.map { SpriteRenderer.scaledImage(for: $0, scale: liveFactor) }
            livePrescaleFactor = liveFactor
        }
        liveBox = rowLayout.liveBox
        self.liveScale = liveScale
        liveCheckerboardLayer.frame = liveBox
        liveLabel.frame = rowLayout.liveLabel
        showFrame()
    }

    /// Show shownFrameNumber in the live view and outline it in the strip
    func showFrame() {
        guard !cellFrameBoxes.isEmpty, !liveImages.isEmpty else { return }
        let frameNumber = min(max(0, shownFrameNumber), animation.frames.count - 1)
        liveFrameLayer.frame = Self.frameRect(animation.frames[frameNumber], scale: liveScale, inBox: liveBox)
        liveFrameLayer.contents = liveImages[frameNumber]
        highlightLayer.frame = cellFrameBoxes[frameNumber].insetBy(dx: -FilmStripView.highlightOutset, dy: -FilmStripView.highlightOutset)
    }

    /// A frame smaller than the row's largest sits at its box's top left, where the engine draws
    /// a frame from (the box is top-down: minY is its top)
    private static func frameRect(_ frame: SpriteFrame, scale: CGFloat, inBox box: CGRect) -> CGRect {
        CGRect(x: box.minX, y: box.minY, width: CGFloat(frame.width) * scale, height: CGFloat(frame.height) * scale)
    }
}
