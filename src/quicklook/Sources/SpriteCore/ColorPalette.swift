// The engine's color rules (AnimatedSprite.build_color_map in src/glitchygames/sprites/animated.py
// and is_color_transparent in src/glitchygames/sprites/pixel_utils.py).

public struct RGBA: Equatable, Hashable, Sendable {
    public var red: UInt8
    public var green: UInt8
    public var blue: UInt8
    public var alpha: UInt8

    public init(red: UInt8, green: UInt8, blue: UInt8, alpha: UInt8) {
        self.red = red
        self.green = green
        self.blue = blue
        self.alpha = alpha
    }

    /// The engine's transparency key, and the color of any glyph missing from [colors]
    public static let magenta = RGBA(red: 255, green: 0, blue: 255, alpha: 255)

    /// R3: alpha 0, or opaque magenta (an RGB magenta is stored here with alpha 255)
    public var isTransparent: Bool {
        alpha == 0 || self == RGBA.magenta
    }
}

struct ColorPalette {
    private let colorsByGlyph: [Unicode.Scalar: RGBA]

    init(colors: [String: ColorEntry]) {
        var colorsByGlyph: [Unicode.Scalar: RGBA] = [:]
        for (key, entry) in colors {
            // A glyph is one code point (Python iterates str by code point), and U+0000 is the
            // padding glyph, which nothing may color (the engine's build_color_map drops it too)
            let scalars = Array(key.unicodeScalars)
            guard scalars.count == 1, scalars[0] != PixelRows.paddingGlyph else { continue }
            colorsByGlyph[scalars[0]] = ColorPalette.color(of: entry)
        }
        self.colorsByGlyph = colorsByGlyph
    }

    func color(for glyph: Unicode.Scalar) -> RGBA {
        colorsByGlyph[glyph] ?? RGBA.magenta
    }

    /// R2: missing channels are 0; alpha 0-254 is kept, anything else (or none) is opaque
    private static func color(of entry: ColorEntry) -> RGBA {
        let alpha = entry.alpha.flatMap { (0...254).contains($0) ? UInt8($0) : nil } ?? 255
        return RGBA(
            red: channel(entry.red),
            green: channel(entry.green),
            blue: channel(entry.blue),
            alpha: alpha
        )
    }

    private static func channel(_ value: Int?) -> UInt8 {
        UInt8(clamping: value ?? 0)
    }
}
