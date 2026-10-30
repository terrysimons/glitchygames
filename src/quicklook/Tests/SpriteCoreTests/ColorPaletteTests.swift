import Testing

@testable import SpriteCore

private func color(_ entry: ColorEntry, glyph: Unicode.Scalar = "a") -> RGBA {
    ColorPalette(colors: [String(glyph): entry]).color(for: glyph)
}

@Test func missingAlphaIsOpaque() {
    #expect(color(ColorEntry(red: 1, green: 2, blue: 3)) == RGBA(red: 1, green: 2, blue: 3, alpha: 255))
}

@Test func alpha254Kept() {
    #expect(color(ColorEntry(red: 1, green: 2, blue: 3, alpha: 254)).alpha == 254)
}

@Test func alpha255Opaque() {
    #expect(color(ColorEntry(red: 1, green: 2, blue: 3, alpha: 255)).alpha == 255)
}

@Test func alpha300BecomesOpaque() {
    #expect(color(ColorEntry(red: 1, green: 2, blue: 3, alpha: 300)).alpha == 255)
}

@Test func missingChannelIsZero() {
    #expect(color(ColorEntry(red: 9)) == RGBA(red: 9, green: 0, blue: 0, alpha: 255))
}

@Test func unknownGlyphIsMagenta() {
    #expect(ColorPalette(colors: [:]).color(for: "z") == RGBA.magenta)
}

@Test func multiScalarKeyIgnored() {
    let palette = ColorPalette(colors: ["ab": ColorEntry(red: 1, green: 2, blue: 3)])
    #expect(palette.color(for: "a") == RGBA.magenta)
}

@Test func magentaIsTransparent() {
    #expect(RGBA(red: 255, green: 0, blue: 255, alpha: 255).isTransparent)
}

@Test func alphaZeroIsTransparent() {
    #expect(RGBA(red: 10, green: 20, blue: 30, alpha: 0).isTransparent)
}

@Test func magentaWithAlpha128IsNotTransparent() {
    #expect(!RGBA(red: 255, green: 0, blue: 255, alpha: 128).isTransparent)
}
