import Foundation

public enum SpriteLoadResult: Sendable {
    case sprite(Sprite)
    /// Not a sprite file at all (pyproject.toml, .taplo.toml, ...): show it as text.
    case notSprite
    /// Looks like a sprite file but can't be drawn; reason is shown above the text.
    case failed(reason: String)
}

public enum SpriteLoader {
    public static func load(data: Data) -> SpriteLoadResult {
        guard let text = String(data: data, encoding: .utf8) else {
            return .notSprite
        }
        let document: SpriteDocument
        do {
            document = try SpriteDocument.decode(from: data)
        } catch {
            // A broken file only counts as a sprite when it says it is one
            if declaresSpriteTables(text) {
                return .failed(reason: String(describing: error))
            }
            return .notSprite
        }
        guard isSprite(document) else {
            return .notSprite
        }
        guard let sprite = resolve(document) else {
            return .failed(reason: "no frames")
        }
        return .sprite(sprite)
    }

    /// Whether a line opens one of the sprite format's own tables ([sprite], [sprite.hitbox],
    /// [[animation]], [[animation.frame]], ...), not merely mentions one ([sprites], a comment)
    static func declaresSpriteTables(_ text: String) -> Bool {
        let tableHeaders = ["[sprite]", "[sprite.", "[[animation]]", "[[animation."]
        return text.split(whereSeparator: \.isNewline).contains { line in
            let trimmed = line.drop(while: { $0 == " " || $0 == "\t" })
            return tableHeaders.contains { trimmed.hasPrefix($0) }
        }
    }

    /// R1: a sprite has a non-empty [[animation]] array or [sprite] pixels.
    static func isSprite(_ document: SpriteDocument) -> Bool {
        !(document.animation ?? []).isEmpty || document.sprite?.pixels != nil
    }

    // The engine's defaults (AnimatedSprite._load_toml and _process_toml_animation)
    private static let defaultFrameInterval = 0.5
    private static let defaultSpriteName = "animated_sprite"
    private static let defaultStaticAnimationName = "idle"
    private static let defaultNamespace = "default"

    private static func resolve(_ document: SpriteDocument) -> Sprite? {
        let palette = ColorPalette(colors: document.colors ?? [:])
        let animationSections = document.animation ?? []
        // R1: static only when there are no animations at all
        if animationSections.isEmpty, let pixels = document.sprite?.pixels {
            return resolveStatic(name: document.sprite?.name, pixels: pixels, palette: palette)
        }
        let animations = resolveAnimations(animationSections, palette: palette)
        guard !animations.isEmpty else {
            return nil
        }
        return Sprite(
            name: document.sprite?.name ?? defaultSpriteName,
            animations: animations
        )
    }

    /// R7 (AnimatedSprite._convert_static_sprite)
    private static func resolveStatic(name: String?, pixels: String, palette: ColorPalette) -> Sprite? {
        guard let frame = makeFrame(
            rows: PixelRows.staticSpriteRows(pixels),
            palette: palette,
            duration: defaultFrameInterval
        ) else {
            return nil
        }
        let animationName = name ?? defaultStaticAnimationName
        return Sprite(
            name: name ?? defaultSpriteName,
            animations: [SpriteAnimation(name: animationName, loop: true, frames: [frame])]
        )
    }

    /// R6 and R8 (AnimatedSprite._load_toml's loop over [[animation]])
    private static func resolveAnimations(
        _ sections: [AnimationSection],
        palette: ColorPalette
    ) -> [SpriteAnimation] {
        var namesInOrder: [String] = []
        var framesByName: [String: [SpriteFrame]] = [:]
        var loopByName: [String: Bool] = [:]
        for section in sections {
            let name = section.namespace ?? defaultNamespace
            // The engine records loop for every table, even one with no frames
            // (self._loop_flags[anim_name] = loop_setting), but stores frames only when there are some
            loopByName[name] = section.loop ?? true
            let frames = resolveFrames(section, palette: palette)
            guard !frames.isEmpty else { continue }
            if framesByName[name] == nil {
                namesInOrder.append(name)
            }
            framesByName[name] = frames
        }
        return namesInOrder.map { name in
            SpriteAnimation(name: name, loop: loopByName[name] ?? true, frames: framesByName[name] ?? [])
        }
    }

    private static func resolveFrames(_ section: AnimationSection, palette: ColorPalette) -> [SpriteFrame] {
        let animationInterval = section.frameInterval ?? defaultFrameInterval
        // Frames play in file order; frame_index is ignored. The engine does sort them, with
        // frames.sort(key=lambda f: getattr(f, 'frame_index', 0)), but SpriteFrame never has a
        // frame_index attribute, so every key is 0 and the stable sort changes nothing
        // (plans/future-work.md, "Bugs found and not fixed yet")
        return (section.frame ?? []).compactMap { frameSection in
            makeFrame(
                rows: PixelRows.animatedFrameRows(frameSection.pixels ?? ""),
                palette: palette,
                duration: frameSection.frameInterval ?? animationInterval
            )
        }
    }

    /// Rows must already share one width (PixelRows does that); nil when there is nothing to draw.
    private static func makeFrame(
        rows: [[Unicode.Scalar]],
        palette: ColorPalette,
        duration: Double
    ) -> SpriteFrame? {
        guard let width = rows.first?.count, width > 0 else {
            return nil
        }
        return SpriteFrame(
            width: width,
            height: rows.count,
            pixels: rows.flatMap { $0.map(palette.color(for:)) },
            duration: duration
        )
    }
}
