import CoreGraphics
import Testing

@testable import SpriteCore

private let red = RGBA(red: 200, green: 10, blue: 20, alpha: 255)

private func frame(width: Int, height: Int, duration: Double = 0.5) -> SpriteFrame {
    SpriteFrame(width: width, height: height, pixels: Array(repeating: red, count: width * height), duration: duration)
}

private func animation(_ name: String, frameCount: Int, width: Int = 16, height: Int = 16, loop: Bool = true) -> SpriteAnimation {
    SpriteAnimation(name: name, loop: loop, frames: (0..<frameCount).map { _ in frame(width: width, height: height) })
}

private let nameWidth: CGFloat = 60

// MARK: Which sprites get a film strip

@Test func staticSpriteHasNoFilmStrip() {
    let sprite = Sprite(name: "s", animations: [animation("idle", frameCount: 1)])
    #expect(!FilmStripLayout.showsFilmStrip(for: sprite))
}

@Test func animationWithSeveralFramesHasAFilmStrip() {
    let sprite = Sprite(name: "s", animations: [animation("walk", frameCount: 2)])
    #expect(FilmStripLayout.showsFilmStrip(for: sprite))
}

@Test func severalOneFrameAnimationsHaveAFilmStrip() {
    let sprite = Sprite(name: "s", animations: [animation("jump", frameCount: 1), animation("fall", frameCount: 1)])
    #expect(FilmStripLayout.showsFilmStrip(for: sprite))
}

// MARK: Labels

@Test func durationTextHasTwoDecimals() {
    #expect(FilmStripLayout.durationText(0.5) == "0.50s")
    #expect(FilmStripLayout.durationText(1.0 / 3.0) == "0.33s")
    #expect(FilmStripLayout.durationText(2) == "2.00s")
}

@Test func liveLabelSaysHowTheAnimationPlays() {
    #expect(FilmStripLayout.liveLabelText(for: animation("walk", frameCount: 2)) == "playing")
    #expect(FilmStripLayout.liveLabelText(for: animation("die", frameCount: 2, loop: false)) == "playing (once)")
    #expect(FilmStripLayout.liveLabelText(for: animation("jump", frameCount: 1)) == "still")
}

// MARK: Scales

@Test func smallSpriteFitsTheCellAndLiveBoxesAtWholeNumberScales() {
    let sprite = Sprite(name: "s", animations: [animation("walk", frameCount: 2, width: 20, height: 28)])
    let layout = FilmStripLayout(sprite: sprite, width: 800, nameWidth: nameWidth)
    // 64 / 28 = 2.3 and 192 / 28 = 6.9
    #expect(layout.cellScale == 2)
    #expect(layout.liveScale == 6)
    #expect(layout.rows[0].cells[0].frameBox.size == CGSize(width: 40, height: 56))
    #expect(layout.rows[0].liveBox.size == CGSize(width: 120, height: 168))
}

@Test func everyRowSharesTheSpritesLargestFrameScale() {
    let sprite = Sprite(name: "s", animations: [
        animation("small", frameCount: 2, width: 8, height: 8),
        animation("big", frameCount: 2, width: 32, height: 32),
    ])
    let layout = FilmStripLayout(sprite: sprite, width: 800, nameWidth: nameWidth)
    #expect(layout.cellScale == 2)
    #expect(layout.rows[0].cells[0].frameBox.size == CGSize(width: 64, height: 64))
    #expect(layout.rows[1].cells[0].frameBox.size == CGSize(width: 64, height: 64))
}

@Test func spriteBiggerThanTheCellShrinksToFit() {
    let sprite = Sprite(name: "s", animations: [animation("walk", frameCount: 2, width: 128, height: 64)])
    let layout = FilmStripLayout(sprite: sprite, width: 800, nameWidth: nameWidth)
    #expect(layout.cellScale == 0.5)
    #expect(layout.rows[0].cells[0].frameBox.size == CGSize(width: 64, height: 32))
    #expect(layout.liveScale == 1)
}

// MARK: Placement

@Test func rowsStackInFileOrderFromTheTopMargin() {
    let sprite = Sprite(name: "s", animations: [animation("a", frameCount: 2), animation("b", frameCount: 3)])
    let layout = FilmStripLayout(sprite: sprite, width: 800, nameWidth: nameWidth)
    #expect(layout.rows.map(\.animationNumber) == [0, 1])
    #expect(layout.rows.map(\.cells.count) == [2, 3])
    #expect(layout.rows[0].frame.minY == FilmStripLayout.margin)
    #expect(layout.rows[1].frame.minY == layout.rows[0].frame.maxY)
    #expect(layout.size.height == layout.rows[1].frame.maxY + FilmStripLayout.margin)
}

@Test func numberIsAboveTheFrameAndDurationBelowIt() {
    let sprite = Sprite(name: "s", animations: [animation("walk", frameCount: 2)])
    let cell = FilmStripLayout(sprite: sprite, width: 800, nameWidth: nameWidth).rows[0].cells[0]
    // Top-down coordinates: smaller y is higher up
    #expect(cell.numberLabel.maxY <= cell.frameBox.minY)
    #expect(cell.durationLabel.minY >= cell.frameBox.maxY)
    #expect(cell.numberLabel.midX == cell.frameBox.midX)
    #expect(cell.durationLabel.midX == cell.frameBox.midX)
}

@Test func nameThenFramesThenLiveViewLeftToRight() {
    let sprite = Sprite(name: "s", animations: [animation("walk", frameCount: 2)])
    let layout = FilmStripLayout(sprite: sprite, width: 800, nameWidth: nameWidth)
    let row = layout.rows[0]
    #expect(row.nameLabel.minX == FilmStripLayout.margin)
    #expect(row.nameLabel.width == nameWidth)
    #expect(row.cells[0].numberLabel.minX > row.nameLabel.maxX)
    #expect(row.cells[1].numberLabel.minX > row.cells[0].numberLabel.maxX)
    #expect(row.liveBox.minX > row.cells[1].numberLabel.maxX)
    // The live view sits at the right end of the row
    #expect(row.liveLabel.maxX == 800 - FilmStripLayout.margin)
    #expect(row.liveLabel.minY >= row.liveBox.maxY)
}

@Test func longAnimationWrapsOntoMoreLinesInsteadOfWidening() {
    let sprite = Sprite(name: "s", animations: [animation("jump", frameCount: 20)])
    let layout = FilmStripLayout(sprite: sprite, width: 600, nameWidth: nameWidth)
    #expect(layout.size.width == 600)
    let cells = layout.rows[0].cells
    #expect(cells.allSatisfy { $0.numberLabel.maxX <= layout.rows[0].liveBox.minX })
    let lineTops = Set(cells.map(\.numberLabel.minY))
    #expect(lineTops.count > 1)
    // Frames keep reading order: left to right, then the next line down
    for (earlier, later) in zip(cells, cells.dropFirst()) {
        let sameLine = earlier.numberLabel.minY == later.numberLabel.minY
        #expect(sameLine ? later.numberLabel.minX > earlier.numberLabel.minX : later.numberLabel.minY > earlier.numberLabel.minY)
    }
    #expect(cells.allSatisfy { layout.rows[0].frame.contains($0.durationLabel) })
}

@Test func tooNarrowAWidthStillFitsOneFramePerLine() {
    let sprite = Sprite(name: "s", animations: [animation("walk", frameCount: 3)])
    let layout = FilmStripLayout(sprite: sprite, width: 10, nameWidth: nameWidth)
    let row = layout.rows[0]
    #expect(Set(row.cells.map(\.numberLabel.minX)).count == 1)
    #expect(row.cells[0].numberLabel.minX > row.nameLabel.maxX)
    #expect(row.liveBox.minX > row.cells[0].numberLabel.maxX)
    #expect(layout.size.width == row.liveLabel.maxX + FilmStripLayout.margin)
}

@Test func liveViewAndNameAreCenteredInTheirRow() {
    let sprite = Sprite(name: "s", animations: [animation("walk", frameCount: 2)])
    let row = FilmStripLayout(sprite: sprite, width: 800, nameWidth: nameWidth).rows[0]
    #expect(abs(row.nameLabel.midY - row.frame.midY) <= 0.5)
    let liveTop = row.liveBox.minY
    let liveBottom = row.liveLabel.maxY
    #expect(abs((liveTop + liveBottom) / 2 - row.frame.midY) <= 0.5)
}
