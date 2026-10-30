import Foundation
import TOMLDecoder

// A Decodable mirror of the parts of a sprite TOML file the engine draws from
// (AnimatedSprite._load_toml in src/glitchygames/sprites/animated.py). Every field is optional,
// as the engine reads them all with .get() and defaults; keys it doesn't draw from (hitbox,
// transition, swatches, description, frame_anchor) are not decoded, so they are ignored.

struct SpriteDocument: Decodable, Equatable {
    var sprite: SpriteSection?
    var colors: [String: ColorEntry]?
    var animation: [AnimationSection]?

    static func decode(from data: Data) throws -> SpriteDocument {
        try TOMLDecoder().decode(SpriteDocument.self, from: normalizingLineEndings(data))
    }

    /// tomllib (what the engine reads with) turns each CRLF inside a multi-line string into LF;
    /// TOMLDecoder keeps the CR. Outside strings a CRLF is only a line break, and a single-line
    /// string can't hold a raw one, so turning every CRLF in the file into LF matches tomllib.
    private static func normalizingLineEndings(_ data: Data) -> Data {
        let carriageReturn: UInt8 = 0x0D
        let lineFeed: UInt8 = 0x0A
        guard data.contains(carriageReturn) else {
            return data
        }
        var normalized = Data(capacity: data.count)
        var index = data.startIndex
        while index < data.endIndex {
            let byte = data[index]
            let nextIndex = data.index(after: index)
            if byte == carriageReturn, nextIndex < data.endIndex, data[nextIndex] == lineFeed {
                index = nextIndex
                continue
            }
            normalized.append(byte)
            index = nextIndex
        }
        return normalized
    }
}

struct SpriteSection: Decodable, Equatable {
    var name: String?
    var pixels: String?
}

struct ColorEntry: Decodable, Equatable {
    var red: Int?
    var green: Int?
    var blue: Int?
    var alpha: Int?

    enum CodingKeys: String, CodingKey {
        case red, green, blue, alpha
    }

    init(red: Int? = nil, green: Int? = nil, blue: Int? = nil, alpha: Int? = nil) {
        self.red = red
        self.green = green
        self.blue = blue
        self.alpha = alpha
    }

    init(from decoder: any Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        red = try decodeChannel(container, forKey: .red)
        green = try decodeChannel(container, forKey: .green)
        blue = try decodeChannel(container, forKey: .blue)
        alpha = try decodeChannel(container, forKey: .alpha)
    }
}

/// A color channel may be a TOML integer or float: the engine hands either to pygame, which
/// truncates a float toward zero (set_at((10.9, 0, 0)) draws red 10)
private func decodeChannel<Key: CodingKey>(
    _ container: KeyedDecodingContainer<Key>,
    forKey key: Key
) throws -> Int? {
    if let channel = try? container.decodeIfPresent(Int.self, forKey: key) {
        return channel
    }
    guard let channel = try container.decodeIfPresent(Double.self, forKey: key) else {
        return nil
    }
    guard channel.isFinite else {
        throw DecodingError.dataCorruptedError(
            forKey: key,
            in: container,
            debugDescription: "color channel \(channel) is not a finite number"
        )
    }
    return Int(channel.rounded(.towardZero).clamped(to: -1_000_000...1_000_000))
}

private extension Double {
    func clamped(to range: ClosedRange<Double>) -> Double {
        Swift.min(Swift.max(self, range.lowerBound), range.upperBound)
    }
}

struct AnimationSection: Decodable, Equatable {
    var namespace: String?
    var frameInterval: Double?
    var loop: Bool?
    var frame: [FrameSection]?

    enum CodingKeys: String, CodingKey {
        case namespace
        case frameInterval = "frame_interval"
        case loop
        case frame
    }

    init(from decoder: any Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        namespace = try container.decodeIfPresent(String.self, forKey: .namespace)
        frameInterval = try decodeSeconds(container, forKey: .frameInterval)
        loop = try container.decodeIfPresent(Bool.self, forKey: .loop)
        frame = try container.decodeIfPresent([FrameSection].self, forKey: .frame)
    }
}

struct FrameSection: Decodable, Equatable {
    // frame_index is not decoded: the engine never uses it (see SpriteLoader.resolveFrames)
    var frameInterval: Double?
    var pixels: String?

    enum CodingKeys: String, CodingKey {
        case frameInterval = "frame_interval"
        case pixels
    }

    init(from decoder: any Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        frameInterval = try decodeSeconds(container, forKey: .frameInterval)
        pixels = try container.decodeIfPresent(String.self, forKey: .pixels)
    }
}

/// A frame_interval may be written as a TOML float (0.5) or integer (1); Python reads both as
/// numbers, so a file with `frame_interval = 1` must not fail to decode.
private func decodeSeconds<Key: CodingKey>(
    _ container: KeyedDecodingContainer<Key>,
    forKey key: Key
) throws -> Double? {
    if let seconds = try? container.decodeIfPresent(Double.self, forKey: key) {
        return seconds
    }
    return try container.decodeIfPresent(Int.self, forKey: key).map(Double.init)
}
