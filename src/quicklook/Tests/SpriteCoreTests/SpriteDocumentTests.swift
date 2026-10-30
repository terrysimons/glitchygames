import Foundation
import Testing

@testable import SpriteCore

private func decodeDocument(_ text: String) throws -> SpriteDocument {
    try SpriteDocument.decode(from: Data(text.utf8))
}

private func isNotSprite(_ result: SpriteLoadResult) -> Bool {
    if case .notSprite = result { return true }
    return false
}

private func isFailed(_ result: SpriteLoadResult) -> Bool {
    if case .failed = result { return true }
    return false
}

@Test func decodesSubTableColors() throws {
    let document = try decodeDocument("""
        [colors."a"]
        red = 255
        green = 215
        blue = 0
        """)
    #expect(document.colors?["a"] == ColorEntry(red: 255, green: 215, blue: 0, alpha: nil))
}

@Test func decodesInlineTableColorsWithUnicodeKey() throws {
    let document = try decodeDocument("""
        [colors]
        "█" = { red = 255, green = 0, blue = 255 }
        """)
    #expect(document.colors?["█"] == ColorEntry(red: 255, green: 0, blue: 255, alpha: nil))
}

@Test func decodesIntegerFrameInterval() throws {
    let document = try decodeDocument("""
        [[animation]]
        namespace = "jump"
        frame_interval = 1

        [[animation.frame]]
        frame_index = 0
        frame_interval = 2
        pixels = "a"
        """)
    #expect(document.animation?.first?.frameInterval == 1.0)
    #expect(document.animation?.first?.frame?.first?.frameInterval == 2.0)
}

@Test func pyprojectIsNotSprite() {
    let result = SpriteLoader.load(data: Data("[project]\nname = \"x\"\n".utf8))
    #expect(isNotSprite(result))
}

@Test func brokenSpriteTomlFails() {
    let result = SpriteLoader.load(data: Data("[sprite]\nname = ".utf8))
    #expect(isFailed(result))
}

@Test func brokenPlainTomlIsNotSprite() {
    let result = SpriteLoader.load(data: Data("[tool\n".utf8))
    #expect(isNotSprite(result))
}

@Test func nonUTF8IsNotSprite() {
    let result = SpriteLoader.load(data: Data([0xFF, 0xFE, 0x00, 0x5B]))
    #expect(isNotSprite(result))
}

@Test func staticAndAnimatedAreSprites() {
    let staticSprite = SpriteLoader.load(data: Data("[sprite]\npixels = \"\"\"\nab\n\"\"\"\n".utf8))
    let animatedSprite = SpriteLoader.load(data: Data("""
        [[animation]]
        [[animation.frame]]
        pixels = "ab"
        """.utf8))
    #expect(!isNotSprite(staticSprite))
    #expect(!isNotSprite(animatedSprite))
}

@Test func decodesFloatColorChannels() throws {
    // The engine passes floats straight to pygame, which draws them; they must not fail the file
    let document = try decodeDocument("""
        [colors."a"]
        red = 255.0
        green = 10.9
        blue = 0
        alpha = 128.0
        """)
    #expect(document.colors?["a"] == ColorEntry(red: 255, green: 10, blue: 0, alpha: 128))
}

@Test func spriteLikeWordsInOtherFilesAreNotSprites() {
    // Broken TOML that only mentions [sprites] or [sprite_sheet] isn't a sprite file
    #expect(isNotSprite(SpriteLoader.load(data: Data("[sprites]\nname = \n".utf8))))
    #expect(isNotSprite(SpriteLoader.load(data: Data("# see [sprite] docs\n[tool\n".utf8))))
    #expect(isNotSprite(SpriteLoader.load(data: Data("[sprite_sheet]\nx = \n".utf8))))
}

@Test func brokenAnimationTomlFails() {
    #expect(isFailed(SpriteLoader.load(data: Data("  [[animation]]\nnamespace = \n".utf8))))
    #expect(isFailed(SpriteLoader.load(data: Data("[sprite.hitbox]\nx = \n".utf8))))
}
