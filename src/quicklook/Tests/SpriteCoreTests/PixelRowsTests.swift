import Testing

@testable import SpriteCore

private func rows(_ text: String...) -> [[Unicode.Scalar]] {
    text.map { Array($0.unicodeScalars) }
}

@Test func animatedStripsEachLineAndDropsEmpty() {
    #expect(PixelRows.animatedFrameRows("\n  ab \n\n cd\n") == rows("ab", "cd"))
}

@Test func animatedTruncatesAndPadsToModeLength() {
    #expect(PixelRows.animatedFrameRows("abc\nabc\nab\nabcd") == rows("abc", "abc", "abb", "abc"))
}

@Test func animatedModeTieGoesToFirstSeenLength() {
    #expect(PixelRows.animatedFrameRows("ab\nabc") == rows("ab", "ab"))
}

@Test func animatedCRLFStripsCarriageReturn() {
    #expect(PixelRows.animatedFrameRows("ab\r\ncd\r\n") == rows("ab", "cd"))
}

@Test func animatedEmptyHasNoRows() {
    #expect(PixelRows.animatedFrameRows(" \n\n ").isEmpty)
}

@Test func staticPadsWithMostCommonScalarToLongestRow() {
    #expect(PixelRows.staticSpriteRows("abb\nb") == rows("abb", "bbb"))
}

@Test func staticPadTieGoesToFirstSeenScalar() {
    #expect(PixelRows.staticSpriteRows("aab\nb") == rows("aab", "baa"))
}

@Test func staticDoesNotStripLines() {
    // The leading space stays a glyph; the tie between all five glyphs pads with a (seen first)
    #expect(PixelRows.staticSpriteRows("ab\n cd") == rows("aba", " cd"))
}

@Test func staticStripsTheWholeString() {
    #expect(PixelRows.staticSpriteRows("\n  ab\ncd  \n") == rows("ab", "cd"))
}

@Test func staticKeepsCarriageReturnAsGlyph() {
    // Every glyph appears once, so the first seen (a) pads: Python Counter.most_common(1)
    #expect(PixelRows.staticSpriteRows("ab\r\ncd") == rows("ab\r", "cda"))
}

@Test func unicodeGlyphIsOneScalar() {
    #expect(PixelRows.animatedFrameRows("█o█") == rows("█o█"))
    #expect(PixelRows.animatedFrameRows("█o█").first?.count == 3)
}

@Test func pythonStripRemovesFileSeparator() {
    let scalars = Array("\u{1C}ab\u{1F}".unicodeScalars)
    #expect(PixelRows.pythonStrip(scalars) == Array("ab".unicodeScalars))
}

@Test func pythonStripKeepsNonBreakingSpaceRules() {
    // Python's str.isspace() is true for U+00A0 and U+3000, so strip() removes them
    let scalars = Array("\u{A0}ab\u{3000}".unicodeScalars)
    #expect(PixelRows.pythonStrip(scalars) == Array("ab".unicodeScalars))
}
