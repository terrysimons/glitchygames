import CoreGraphics
import Foundation

/// Where everything goes in the film strip preview (spec goal 6): one row per animation, in file
/// order, with the animation's name on the left, every frame left to right (its number above it,
/// its duration below it, wrapping onto more lines rather than widening), and the live animation
/// at the right end of the row.
///
/// Coordinates are top-down, in points: the origin is the top left and y grows downward, so the
/// view drawing this must be flipped.
public struct FilmStripLayout: Equatable, Sendable {
    public static let margin: CGFloat = 16
    /// Strip frames are scaled to fit a square this size, the live view one of liveFitSide
    public static let cellFitSide: CGFloat = 64
    public static let liveFitSide: CGFloat = 192
    /// Between frames on a line, and between wrapped lines
    public static let frameGap: CGFloat = 6
    /// Between the name, the strip and the live view
    public static let columnGap: CGFloat = 14
    public static let labelHeight: CGFloat = 16
    public static let labelGap: CGFloat = 2
    public static let rowPadding: CGFloat = 8
    /// Wide enough for a duration label ("0.50s") under a frame narrower than it
    public static let minimumCellWidth: CGFloat = 36
    /// Wide enough for "playing (once)" under a live view narrower than it
    public static let minimumLiveWidth: CGFloat = 96

    public struct Cell: Equatable, Sendable {
        public let numberLabel: CGRect
        /// The box for the sprite's largest frame; a smaller frame sits at its top left
        public let frameBox: CGRect
        public let durationLabel: CGRect
    }

    public struct Row: Equatable, Sendable {
        /// Index into Sprite.animations
        public let animationNumber: Int
        /// The whole row, full width, for drawing separators between rows
        public let frame: CGRect
        public let nameLabel: CGRect
        public let cells: [Cell]
        public let liveBox: CGRect
        public let liveLabel: CGRect
    }

    /// Points per sprite pixel in the strip and in the live view: whole numbers when the
    /// sprite's largest frame fits, otherwise the fraction that fits it
    public let cellScale: CGFloat
    public let liveScale: CGFloat
    public let rows: [Row]
    /// The width asked for, or wider when that can't hold one frame per line; and the height
    /// of every row with the margins
    public let size: CGSize

    /// A static sprite (one animation of one frame) keeps the single large view: a one-frame
    /// strip beside it would only repeat it
    public static func showsFilmStrip(for sprite: Sprite) -> Bool {
        sprite.animations.count > 1 || sprite.animations[0].frames.count > 1
    }

    public static func durationText(_ seconds: Double) -> String {
        String(format: "%.2fs", seconds)
    }

    public static func liveLabelText(for animation: SpriteAnimation) -> String {
        if animation.frames.count == 1 {
            return "still"
        }
        return animation.loop ? "playing" : "playing (once)"
    }

    /// - Parameter nameWidth: the width of the name column, measured by the view from its font
    public init(sprite: Sprite, width: CGFloat, nameWidth: CGFloat) {
        // One scale for every row, from the sprite's largest frame, so all rows line up
        let largestFrame = CGSize(
            width: sprite.animations.map { SpriteRenderer.largestFrameSize(of: $0).width }.max() ?? 0,
            height: sprite.animations.map { SpriteRenderer.largestFrameSize(of: $0).height }.max() ?? 0
        )
        cellScale = SpriteRenderer.displayScale(
            contentSize: largestFrame,
            fitting: CGSize(width: Self.cellFitSide, height: Self.cellFitSide)
        )
        liveScale = SpriteRenderer.displayScale(
            contentSize: largestFrame,
            fitting: CGSize(width: Self.liveFitSide, height: Self.liveFitSide)
        )
        let frameBoxSize = CGSize(width: largestFrame.width * cellScale, height: largestFrame.height * cellScale)
        let liveBoxSize = CGSize(width: largestFrame.width * liveScale, height: largestFrame.height * liveScale)
        let cellWidth = max(frameBoxSize.width, Self.minimumCellWidth)
        let cellHeight = Self.labelHeight + Self.labelGap + frameBoxSize.height + Self.labelGap + Self.labelHeight
        let liveWidth = max(liveBoxSize.width, Self.minimumLiveWidth)
        let liveHeight = liveBoxSize.height + Self.labelGap + Self.labelHeight

        let minimumWidth = 2 * Self.margin + nameWidth + Self.columnGap + cellWidth + Self.columnGap + liveWidth
        let contentWidth = max(width, minimumWidth)
        let stripX = Self.margin + nameWidth + Self.columnGap
        let liveX = contentWidth - Self.margin - liveWidth
        let stripWidth = liveX - Self.columnGap - stripX
        let framesPerLine = max(1, Int(((stripWidth + Self.frameGap) / (cellWidth + Self.frameGap)).rounded(.down)))

        var rows: [Row] = []
        var rowTop = Self.margin
        for (animationNumber, animation) in sprite.animations.enumerated() {
            let lineCount = (animation.frames.count + framesPerLine - 1) / framesPerLine
            let stripHeight = CGFloat(lineCount) * cellHeight + CGFloat(lineCount - 1) * Self.frameGap
            let contentHeight = max(stripHeight, liveHeight)
            let rowFrame = CGRect(x: 0, y: rowTop, width: contentWidth, height: contentHeight + 2 * Self.rowPadding)
            let contentTop = rowTop + Self.rowPadding

            let stripTop = contentTop + ((contentHeight - stripHeight) / 2).rounded()
            let cells = animation.frames.indices.map { frameNumber in
                let cellX = stripX + CGFloat(frameNumber % framesPerLine) * (cellWidth + Self.frameGap)
                let cellY = stripTop + CGFloat(frameNumber / framesPerLine) * (cellHeight + Self.frameGap)
                let frameBox = CGRect(
                    x: cellX + (cellWidth - frameBoxSize.width) / 2,
                    y: cellY + Self.labelHeight + Self.labelGap,
                    width: frameBoxSize.width,
                    height: frameBoxSize.height
                )
                return Cell(
                    numberLabel: CGRect(x: cellX, y: cellY, width: cellWidth, height: Self.labelHeight),
                    frameBox: frameBox,
                    durationLabel: CGRect(
                        x: cellX,
                        y: frameBox.maxY + Self.labelGap,
                        width: cellWidth,
                        height: Self.labelHeight
                    )
                )
            }

            let liveTop = contentTop + ((contentHeight - liveHeight) / 2).rounded()
            let liveBox = CGRect(
                x: liveX + (liveWidth - liveBoxSize.width) / 2,
                y: liveTop,
                width: liveBoxSize.width,
                height: liveBoxSize.height
            )
            rows.append(Row(
                animationNumber: animationNumber,
                frame: rowFrame,
                nameLabel: CGRect(
                    x: Self.margin,
                    y: (rowFrame.midY - Self.labelHeight / 2).rounded(),
                    width: nameWidth,
                    height: Self.labelHeight
                ),
                cells: cells,
                liveBox: liveBox,
                liveLabel: CGRect(x: liveX, y: liveBox.maxY + Self.labelGap, width: liveWidth, height: Self.labelHeight)
            ))
            rowTop = rowFrame.maxY
        }
        self.rows = rows
        size = CGSize(width: contentWidth, height: rowTop + Self.margin)
    }
}
