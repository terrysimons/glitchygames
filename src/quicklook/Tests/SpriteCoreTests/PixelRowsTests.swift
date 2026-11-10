import Testing

@testable import SpriteCore

// The same inputs and rows as the engine's TestNormalizePixelRows
// (tests/sprites/test_pixel_utils.py); "\u{0}" is a padded, transparent pixel.

private func rows(_ text: String...) -> [[Unicode.Scalar]] {
    text.map { Array($0.unicodeScalars) }
}

@Test func rectangleIsUnchanged() {
    #expect(PixelRows.rows("ab\nab") == rows("ab", "ab"))
}

@Test func longRowWidensNeverTruncates() {
    #expect(PixelRows.rows("x\nxxxx\nx\nx") == rows("x\u{0}\u{0}\u{0}", "xxxx", "x\u{0}\u{0}\u{0}", "x\u{0}\u{0}\u{0}"))
}

@Test func modeCannotCutARow() {
    #expect(PixelRows.rows("abcd\nab\nab").first == Array("abcd".unicodeScalars))
}

@Test func blankInteriorLineIsATransparentRow() {
    #expect(PixelRows.rows("ab\n\nab") == rows("ab", "\u{0}\u{0}", "ab"))
}

@Test func outerBlankLinesAndTrailingWhitespaceAreTidied() {
    #expect(PixelRows.rows("\n\nab  \n ab\t\n\n") == rows("ab\u{0}", " ab"))
}

@Test func sharedIndentationIsRemoved() {
    #expect(PixelRows.rows("    ab\n    ab") == rows("ab", "ab"))
    #expect(PixelRows.rows("\tab\n\tab") == rows("ab", "ab"))
}

@Test func unsharedIndentationStays() {
    #expect(PixelRows.rows("  x  \n xxx \nxxxxx") == rows("  x\u{0}\u{0}", " xxx\u{0}", "xxxxx"))
}

@Test func mixedPrefixCharactersAreNotShared() {
    #expect(PixelRows.rows(" \tab\n\t ab") == rows(" \tab", "\t ab"))
}

@Test func crlfIsTidied() {
    #expect(PixelRows.rows("ab\r\nab\r\n") == rows("ab", "ab"))
}

@Test func blankTextHasNoRows() {
    #expect(PixelRows.rows("").isEmpty)
    #expect(PixelRows.rows("\n  \n").isEmpty)
}

@Test func eachCodePointIsOnePixel() {
    #expect(PixelRows.rows("e\u{301}e").first?.count == 3)
    #expect(PixelRows.rows("\u{2764}\u{FE0F}").first?.count == 2)
    #expect(PixelRows.rows("█o█") == rows("█o█"))
}
