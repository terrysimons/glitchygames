import Foundation
import Testing

@testable import SpriteCore

private let palette = """
    [colors."X"]
    red = 1
    [colors."Y"]
    red = 2
    [colors."Z"]
    red = 3

    """

private func loadSprite(_ text: String) throws -> Sprite {
    switch SpriteLoader.load(data: Data((palette + text).utf8)) {
    case .sprite(let sprite):
        return sprite
    case let other:
        Issue.record("expected a sprite, got \(other)")
        throw CancellationError()
    }
}

private func loadResult(_ text: String) -> SpriteLoadResult {
    SpriteLoader.load(data: Data((palette + text).utf8))
}

/// The red channel of each frame's first pixel, which these tests use to tell frames apart
private func frameMarkers(_ animation: SpriteAnimation) -> [UInt8] {
    animation.frames.map { $0.pixels[0].red }
}

@Test func staticSpriteBecomesOneFrameIdle() throws {
    let sprite = try loadSprite("[sprite]\npixels = \"\"\"\nXY\nYX\n\"\"\"\n")
    #expect(sprite.animations.count == 1)
    let animation = sprite.animations[0]
    #expect(animation.name == "idle")
    #expect(animation.loop)
    #expect(animation.frames.count == 1)
    #expect(animation.frames[0].width == 2)
    #expect(animation.frames[0].height == 2)
    #expect(animation.frames[0].duration == 0.5)
    #expect(animation.frames[0].pixels.map(\.red) == [1, 2, 2, 1])
}

@Test func staticSpriteUsesSpriteName() throws {
    let sprite = try loadSprite("[sprite]\nname = \"heart\"\npixels = \"X\"\n")
    #expect(sprite.name == "heart")
    #expect(sprite.animations[0].name == "heart")
}

@Test func animationsWinOverSpritePixels() throws {
    let sprite = try loadSprite("""
        [sprite]
        pixels = "X"
        [[animation]]
        namespace = "walk"
        [[animation.frame]]
        pixels = "Y"
        """)
    #expect(sprite.animations.map(\.name) == ["walk"])
    #expect(frameMarkers(sprite.animations[0]) == [2])
}

@Test func defaultsNamespaceIntervalLoop() throws {
    let sprite = try loadSprite("[[animation]]\n[[animation.frame]]\npixels = \"X\"\n")
    let animation = sprite.animations[0]
    #expect(animation.name == "default")
    #expect(animation.loop)
    #expect(animation.frames[0].duration == 0.5)
}

@Test func perFrameIntervalOverrides() throws {
    let sprite = try loadSprite("""
        [[animation]]
        frame_interval = 0.25
        [[animation.frame]]
        pixels = "X"
        [[animation.frame]]
        pixels = "X"
        [[animation.frame]]
        frame_interval = 0.1
        pixels = "X"
        """)
    #expect(sprite.animations[0].frames.map(\.duration) == [0.25, 0.25, 0.1])
}

@Test func framesPlayInFileOrderIgnoringFrameIndex() throws {
    // The engine sorts by getattr(frame, 'frame_index', 0), but SpriteFrame never has a
    // frame_index attribute, so every key is 0 and the stable sort keeps file order
    // (plans/future-work.md, "Bugs found and not fixed yet")
    let sprite = try loadSprite("""
        [[animation]]
        [[animation.frame]]
        frame_index = 2
        pixels = "X"
        [[animation.frame]]
        frame_index = 0
        pixels = "Y"
        [[animation.frame]]
        frame_index = 1
        pixels = "Z"
        """)
    #expect(frameMarkers(sprite.animations[0]) == [1, 2, 3])
}

@Test func emptyFrameSkipped() throws {
    let sprite = try loadSprite("""
        [[animation]]
        [[animation.frame]]
        pixels = ""
        [[animation.frame]]
        pixels = "X"
        [[animation.frame]]
        frame_index = 0
        pixels = "Y"
        """)
    #expect(frameMarkers(sprite.animations[0]) == [1, 2])
}

@Test func crlfInMultilineStringsBecomesLF() throws {
    // tomllib turns a CRLF inside a multi-line string into LF; the static rule would otherwise
    // keep the carriage return as a glyph
    let sprite = try loadSprite("[sprite]\r\npixels = \"\"\"\r\nXY\r\nYX\r\n\"\"\"\r\n")
    #expect(sprite.animations[0].frames[0].width == 2)
    #expect(sprite.animations[0].frames[0].pixels.map(\.red) == [1, 2, 2, 1])
}

@Test func animationWithOnlyEmptyFramesDropped() throws {
    let sprite = try loadSprite("""
        [[animation]]
        namespace = "empty"
        [[animation.frame]]
        pixels = "   "
        [[animation]]
        namespace = "full"
        [[animation.frame]]
        pixels = "X"
        """)
    #expect(sprite.animations.map(\.name) == ["full"])
}

@Test func allAnimationsEmptyFails() {
    let result = loadResult("[[animation]]\nnamespace = \"empty\"\n[[animation.frame]]\npixels = \"\"\n")
    guard case .failed(let reason) = result else {
        Issue.record("expected failure, got \(result)")
        return
    }
    #expect(reason == "no frames")
}

@Test func emptyStaticSpriteFails() {
    let result = loadResult("[sprite]\npixels = \"  \"\n")
    guard case .failed(let reason) = result else {
        Issue.record("expected failure, got \(result)")
        return
    }
    #expect(reason == "no frames")
}

@Test func duplicateNamespaceKeepsFirstPositionLastData() throws {
    let sprite = try loadSprite("""
        [[animation]]
        namespace = "walk"
        loop = true
        [[animation.frame]]
        pixels = "X"
        [[animation]]
        namespace = "run"
        [[animation.frame]]
        pixels = "Y"
        [[animation]]
        namespace = "walk"
        loop = false
        frame_interval = 0.2
        [[animation.frame]]
        pixels = "Z"
        """)
    #expect(sprite.animations.map(\.name) == ["walk", "run"])
    #expect(frameMarkers(sprite.animations[0]) == [3])
    #expect(sprite.animations[0].loop == false)
    #expect(sprite.animations[0].frames[0].duration == 0.2)
}

@Test func loopFalseKept() throws {
    let sprite = try loadSprite("[[animation]]\nloop = false\n[[animation.frame]]\npixels = \"X\"\n")
    #expect(sprite.animations[0].loop == false)
}

@Test func unknownGlyphIsMagentaPixel() throws {
    let sprite = try loadSprite("[[animation]]\n[[animation.frame]]\npixels = \"Xq\"\n")
    #expect(sprite.animations[0].frames[0].pixels[1] == RGBA.magenta)
}

@Test func staticSpriteWithoutNameUsesTheEngineDefaults() throws {
    // AnimatedSprite: self.name defaults to 'animated_sprite', the one animation to 'idle'
    let sprite = try loadSprite("[sprite]\npixels = \"X\"\n")
    #expect(sprite.name == "animated_sprite")
    #expect(sprite.animations[0].name == "idle")
}
