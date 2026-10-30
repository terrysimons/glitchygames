// The engine's two ways of turning a pixels string into rows of glyphs. They differ, and the
// preview copies both so it draws what the game draws (plans/future-work.md tracks unifying the
// engine; change these together with it).
//
// Everything works on Unicode scalars: Python iterates str by code point, and Swift's Character
// would merge "\r\n" into one glyph.

enum PixelRows {
    private static let newline: Unicode.Scalar = "\n"

    /// R4, animated frames (AnimatedSprite.parse_toml_pixel_lines and
    /// _validate_toml_frame_dimensions): strip each line, drop the empty ones, then make every line
    /// the most common length, truncating longer ones and padding shorter ones with their own
    /// last glyph.
    static func animatedFrameRows(_ pixels: String) -> [[Unicode.Scalar]] {
        let lines = split(Array(pixels.unicodeScalars))
            .map { pythonStrip($0) }
            .filter { !$0.isEmpty }
        guard let width = mostCommon(lines.map(\.count)) else {
            return []
        }
        return lines.map { line in
            if line.count >= width {
                return Array(line.prefix(width))
            }
            return line + Array(repeating: line[line.count - 1], count: width - line.count)
        }
    }

    /// R5, static sprites (AnimatedSprite._convert_static_sprite): strip the whole string only,
    /// then pad shorter rows to the longest with the most common glyph in the sprite.
    static func staticSpriteRows(_ pixels: String) -> [[Unicode.Scalar]] {
        let rows = split(pythonStrip(Array(pixels.unicodeScalars)))
        let width = rows.map(\.count).max() ?? 0
        guard let padGlyph = mostCommon(rows.flatMap { $0 }) else {
            return rows
        }
        return rows.map { row in
            row + Array(repeating: padGlyph, count: width - row.count)
        }
    }

    /// Python's str.strip(): removes characters where str.isspace() is true, which is Unicode
    /// White_Space plus U+001C-U+001F (the file, group, record and unit separators).
    static func pythonStrip(_ scalars: some Collection<Unicode.Scalar>) -> [Unicode.Scalar] {
        let characters = Array(scalars)
        guard let first = characters.firstIndex(where: { !isPythonSpace($0) }),
              let last = characters.lastIndex(where: { !isPythonSpace($0) })
        else {
            return []
        }
        return Array(characters[first...last])
    }

    private static func isPythonSpace(_ scalar: Unicode.Scalar) -> Bool {
        scalar.properties.isWhitespace || (0x1C...0x1F).contains(scalar.value)
    }

    /// Python's str.split('\n'): only U+000A splits, and empty pieces are kept.
    private static func split(_ scalars: [Unicode.Scalar]) -> [[Unicode.Scalar]] {
        scalars.split(separator: newline, omittingEmptySubsequences: false).map(Array.init)
    }

    /// Counter(values).most_common(1): the highest count, ties going to the value seen first.
    private static func mostCommon<Value: Hashable>(_ values: [Value]) -> Value? {
        var counts: [Value: Int] = [:]
        var firstSeenOrder: [Value] = []
        for value in values {
            if counts[value] == nil {
                firstSeenOrder.append(value)
            }
            counts[value, default: 0] += 1
        }
        var best: Value?
        var bestCount = 0
        for value in firstSeenOrder where counts[value, default: 0] > bestCount {
            best = value
            bestCount = counts[value, default: 0]
        }
        return best
    }
}
