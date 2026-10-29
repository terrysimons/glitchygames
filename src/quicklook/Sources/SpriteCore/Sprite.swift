// A sprite resolved the way the engine resolves it: every animation in file order, every frame's
// pixels looked up in the palette (see SpriteLoader).

public struct SpriteFrame: Equatable, Sendable {
    public let width: Int
    public let height: Int
    /// Row-major; count == width * height. The engine's raw colors: transparency is decided at
    /// draw time by RGBA.isTransparent, exactly as the engine's is_color_transparent decides it.
    public let pixels: [RGBA]
    /// Seconds this frame stays on screen.
    public let duration: Double
}

public struct SpriteAnimation: Equatable, Sendable {
    public let name: String
    public let loop: Bool
    /// Never empty.
    public let frames: [SpriteFrame]
}

public struct Sprite: Equatable, Sendable {
    public let name: String
    /// Never empty; file order (the first one plays first).
    public let animations: [SpriteAnimation]
}
