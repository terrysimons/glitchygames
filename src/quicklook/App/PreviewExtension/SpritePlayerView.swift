import AppKit
import QuartzCore
import SpriteCore

/// Draws a sprite crisp, centered on a checkerboard so transparency shows, and plays its first
/// animation from the moment it is on screen. Used for static sprites; anything with more frames
/// or animations gets FilmStripView (spec goal 6).
final class SpritePlayerView: NSView {
    static let checkerboardCellSize = 8
    private static let margin: CGFloat = 16

    /// The transparency background, shared with FilmStripView
    static func checkerboardColor() -> CGColor {
        let checkerboard = NSImage(
            cgImage: SpriteRenderer.checkerboardImage(cellSize: checkerboardCellSize),
            size: .zero
        )
        return NSColor(patternImage: checkerboard).cgColor
    }

    private let sprite: Sprite
    /// Each frame pre-scaled with nearest neighbor toward the backing pixels it fills, capped at
    /// SpriteRenderer.maximumPrescaledSide so a full-screen preview stays small; the layer's
    /// nearest-neighbor filter does the rest. Rebuilt when the factor changes (resize, or a move
    /// to a screen with another backing scale).
    private var scaledFrameImages: [CGImage] = []
    private var scaledFramePrescaleFactor = 0
    private let checkerboardLayer = CALayer()
    private let frameLayer = CALayer()

    private let animationNumber = 0
    private var clock: AnimationClock
    private var startTime = CACurrentMediaTime()
    private var shownFrameNumber = -1
    private var displayLink: CADisplayLink?

    init(sprite: Sprite) {
        self.sprite = sprite
        clock = Self.clock(for: sprite.animations[0])
        super.init(frame: .zero)

        wantsLayer = true
        checkerboardLayer.backgroundColor = Self.checkerboardColor()
        frameLayer.magnificationFilter = .nearest
        frameLayer.minificationFilter = .nearest
        frameLayer.contentsGravity = .resize
        layer?.addSublayer(checkerboardLayer)
        layer?.addSublayer(frameLayer)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) is not used")
    }

    // MARK: Playback

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        displayLink?.invalidate()
        displayLink = nil
        guard window != nil else { return }
        // Auto-play: start the moment the preview is on screen
        restartAnimation()
        let link = displayLink(target: self, selector: #selector(displayLinkFired(_:)))
        link.add(to: .main, forMode: .common)
        displayLink = link
    }

    @objc private func displayLinkFired(_ link: CADisplayLink) {
        showCurrentFrame()
        // Nothing left to change (one frame, or a non-looping animation that has finished):
        // stop waking up on every display refresh
        if clock.nextChange(after: CACurrentMediaTime() - startTime) == nil {
            link.isPaused = true
        }
    }

    private func restartAnimation() {
        startTime = CACurrentMediaTime()
        shownFrameNumber = -1
        showCurrentFrame()
    }

    private func showCurrentFrame() {
        let frameNumber = clock.frameIndex(at: CACurrentMediaTime() - startTime)
        guard frameNumber != shownFrameNumber else { return }
        shownFrameNumber = frameNumber
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        layoutFrameLayer()
        CATransaction.commit()
    }

    static func clock(for animation: SpriteAnimation) -> AnimationClock {
        AnimationClock(durations: animation.frames.map(\.duration), loop: animation.loop)
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
        // Resolved here, not once in init, so it follows light and dark mode
        effectiveAppearance.performAsCurrentDrawingAppearance {
            layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor
        }
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        layoutFrameLayer()
        CATransaction.commit()
    }

    /// Every frame of the animation shares one scale, from its largest frame, so the sprite
    /// doesn't jump when frame sizes differ; smaller frames sit at the box's top left, where
    /// the engine draws a frame from. A sprite too big for the view is shrunk to fit.
    private func layoutFrameLayer() {
        let animation = sprite.animations[animationNumber]
        let boxSize = SpriteRenderer.largestFrameSize(of: animation)
        let available = bounds.insetBy(dx: Self.margin, dy: Self.margin)
        // Nothing to draw into yet (before the first layout): don't build images for it
        guard available.width > 0, available.height > 0 else { return }
        let scale = SpriteRenderer.displayScale(contentSize: boxSize, fitting: available.size)
        let box = NSRect(
            x: (available.midX - boxSize.width * scale / 2).rounded(),
            y: (available.midY - boxSize.height * scale / 2).rounded(),
            width: boxSize.width * scale,
            height: boxSize.height * scale
        )
        checkerboardLayer.frame = box
        let frameNumber = min(max(0, shownFrameNumber), animation.frames.count - 1)
        let frame = animation.frames[frameNumber]
        let frameHeight = CGFloat(frame.height) * scale
        frameLayer.frame = NSRect(
            x: box.minX,
            y: box.maxY - frameHeight,
            width: CGFloat(frame.width) * scale,
            height: frameHeight
        )
        let backingScale = max(1, (window?.backingScaleFactor ?? 2).rounded())
        let prescaleFactor = SpriteRenderer.prescaleFactor(
            frameSize: boxSize,
            pixelScale: Int((scale * backingScale).rounded(.down))
        )
        if prescaleFactor != scaledFramePrescaleFactor {
            scaledFrameImages = animation.frames.map {
                SpriteRenderer.scaledImage(for: $0, scale: prescaleFactor)
            }
            scaledFramePrescaleFactor = prescaleFactor
        }
        frameLayer.contents = scaledFrameImages[frameNumber]
    }
}
