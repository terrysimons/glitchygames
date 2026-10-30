import Foundation
import Testing

@testable import SpriteCore

// Every Golden/<name>.toml is drawn by SpriteCore and compared with Golden/<name>.json, the
// frames the engine's own loader produced for it (tools/dump_engine_frames.py). Regenerate the
// JSON with that tool; never edit it by hand.

private struct GoldenSprite: Decodable {
    struct Animation: Decodable {
        let name: String
        let loop: Bool?
        let frames: [Frame]
    }

    struct Frame: Decodable {
        let width: Int
        let height: Int
        let duration: Double
        let pixels: [[UInt8]]
    }

    let animations: [Animation]
}

private let goldenDirectory = Bundle.module.resourceURL!.appendingPathComponent("Golden")

private let goldenFixtureNames: [String] = {
    let files = (try? FileManager.default.contentsOfDirectory(atPath: goldenDirectory.path)) ?? []
    return files.filter { $0.hasSuffix(".toml") }.map { String($0.dropLast(".toml".count)) }.sorted()
}()

@Test func goldenFixturesArePresent() {
    #expect(goldenFixtureNames.count >= 9)
}

/// True when every line break in the data is CRLF (and there is at least one)
private func hasOnlyCRLFLineEndings(_ data: Data) -> Bool {
    let bytes = [UInt8](data)
    let lineFeedPositions = bytes.indices.filter { bytes[$0] == 0x0A }
    return !lineFeedPositions.isEmpty && lineFeedPositions.allSatisfy { $0 > 0 && bytes[$0 - 1] == 0x0D }
}

@Test func lineFeedOnlyDataIsNotCRLF() {
    #expect(!hasOnlyCRLFLineEndings(Data("a\nb\n".utf8)))
    #expect(!hasOnlyCRLFLineEndings(Data("a\r\nb\n".utf8)))
    #expect(hasOnlyCRLFLineEndings(Data("a\r\nb\r\n".utf8)))
}

/// The CRLF fixtures only test CRLF handling while they really are CRLF: a formatter or a git
/// line-ending conversion would turn them into LF and the golden tests would still pass
@Test(arguments: ["crlf-static", "crlf-animated"])
func crlfFixturesStillHaveCRLFLineEndings(fixtureName: String) throws {
    let data = try Data(contentsOf: goldenDirectory.appendingPathComponent("\(fixtureName).toml"))
    #expect(hasOnlyCRLFLineEndings(data))
}

@Test(arguments: goldenFixtureNames)
func everyGoldenFixtureMatchesTheEngine(fixtureName: String) throws {
    let tomlData = try Data(contentsOf: goldenDirectory.appendingPathComponent("\(fixtureName).toml"))
    let jsonData = try Data(contentsOf: goldenDirectory.appendingPathComponent("\(fixtureName).json"))
    let golden = try JSONDecoder().decode(GoldenSprite.self, from: jsonData)

    guard case .sprite(let sprite) = SpriteLoader.load(data: tomlData) else {
        Issue.record("\(fixtureName): SpriteCore did not load it as a sprite")
        return
    }
    try #require(sprite.animations.map(\.name) == golden.animations.map(\.name))
    for (animation, goldenAnimation) in zip(sprite.animations, golden.animations) {
        if let goldenLoop = goldenAnimation.loop {
            #expect(animation.loop == goldenLoop, "\(fixtureName)/\(animation.name) loop")
        }
        try #require(
            animation.frames.count == goldenAnimation.frames.count,
            "\(fixtureName)/\(animation.name) frame count"
        )
        for (frameNumber, (frame, goldenFrame)) in zip(animation.frames, goldenAnimation.frames).enumerated() {
            let label = "\(fixtureName)/\(animation.name)/frame \(frameNumber)"
            #expect(frame.width == goldenFrame.width, "\(label) width")
            #expect(frame.height == goldenFrame.height, "\(label) height")
            #expect(abs(frame.duration - goldenFrame.duration) < 1e-9, "\(label) duration")
            let goldenPixels = goldenFrame.pixels.map {
                RGBA(red: $0[0], green: $0[1], blue: $0[2], alpha: $0[3])
            }
            if frame.pixels != goldenPixels {
                let firstDifference = zip(frame.pixels, goldenPixels).enumerated().first { $0.element.0 != $0.element.1 }?.offset
                Issue.record("\(label) pixels differ (counts \(frame.pixels.count)/\(goldenPixels.count), first at \(String(describing: firstDifference)))")
            }
        }
    }
}
