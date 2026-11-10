// The engine's one rule for turning a pixels string into rows of glyphs, used for static sprites
// and animation frames alike: normalize_pixel_rows in src/glitchygames/sprites/pixel_utils.py
// (docs/specs/2026-10-30-unified-pixel-rows-design.md). Change the two together; the golden
// frames (Tests/SpriteCoreTests/Golden) prove they agree.
//
// Everything works on Unicode scalars: Python iterates str by code point, and Swift's Character
// would merge "\r\n" into one glyph.

enum PixelRows {
    /// A padded pixel. It has no palette glyph, so it draws as the magenta transparency key, as
    /// the engine's PADDING_GLYPH does; ColorPalette drops a U+0000 key so nothing can color it.
    static let paddingGlyph: Unicode.Scalar = "\u{0}"

    private static let newline: Unicode.Scalar = "\n"
    /// Trimmed from the end of every line: spaces, tabs and Windows line endings' \r
    private static let trailingWhitespace: Set<Unicode.Scalar> = [" ", "\t", "\r"]
    /// Removed from the start of every line when all non-blank lines share it
    private static let indentation: Set<Unicode.Scalar> = [" ", "\t"]

    /// Split on U+000A; trim trailing spaces, tabs and carriage returns from each line; drop blank
    /// lines at the top and bottom; remove the leading spaces and tabs every non-blank line
    /// shares, scalar for scalar; then pad every row at the end with paddingGlyph to the longest.
    /// A blank line between rows becomes a row of padding. Nothing is ever cut off.
    static func rows(_ pixels: String) -> [[Unicode.Scalar]] {
        let trimmedLines = Array(pixels.unicodeScalars)
            .split(separator: newline, omittingEmptySubsequences: false)
            .map { line -> [Unicode.Scalar] in
                var trimmed = Array(line)
                while let last = trimmed.last, trailingWhitespace.contains(last) {
                    trimmed.removeLast()
                }
                return trimmed
            }
        guard let first = trimmedLines.firstIndex(where: { !$0.isEmpty }),
              let last = trimmedLines.lastIndex(where: { !$0.isEmpty })
        else {
            return []
        }
        let lines = Array(trimmedLines[first...last])
        let prefixLength = sharedIndentationLength(lines.filter { !$0.isEmpty })
        let rows = lines.map { $0.isEmpty ? $0 : Array($0.dropFirst(prefixLength)) }
        let width = rows.map(\.count).max() ?? 0
        return rows.map { $0 + Array(repeating: paddingGlyph, count: width - $0.count) }
    }

    /// How many leading spaces and tabs every line shares, scalar for scalar
    private static func sharedIndentationLength(_ lines: [[Unicode.Scalar]]) -> Int {
        guard let shortest = lines.map(\.count).min() else {
            return 0
        }
        var length = 0
        while length < shortest {
            let scalar = lines[0][length]
            guard indentation.contains(scalar), lines.allSatisfy({ $0[length] == scalar }) else {
                break
            }
            length += 1
        }
        return length
    }
}
