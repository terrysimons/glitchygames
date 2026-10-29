import CoreGraphics
import Foundation

/// Turns sprite frames into images. Pixel art is never smoothed: every scaled draw uses
/// interpolationQuality .none (nearest neighbor).
public enum SpriteRenderer {
    private static let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)!
    private static let bytesPerPixel = 4

    /// The frame at its native size: sRGB, premultiplied alpha, transparent pixels (R3) clear.
    public static func image(for frame: SpriteFrame) -> CGImage {
        var bytes = [UInt8]()
        bytes.reserveCapacity(frame.width * frame.height * bytesPerPixel)
        for pixel in frame.pixels {
            if pixel.isTransparent {
                bytes.append(contentsOf: [0, 0, 0, 0])
                continue
            }
            bytes.append(contentsOf: [
                premultiply(pixel.red, by: pixel.alpha),
                premultiply(pixel.green, by: pixel.alpha),
                premultiply(pixel.blue, by: pixel.alpha),
                pixel.alpha,
            ])
        }
        let provider = CGDataProvider(data: Data(bytes) as CFData)!
        return CGImage(
            width: frame.width,
            height: frame.height,
            bitsPerComponent: 8,
            bitsPerPixel: 8 * bytesPerPixel,
            bytesPerRow: frame.width * bytesPerPixel,
            space: colorSpace,
            bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.premultipliedLast.rawValue),
            provider: provider,
            decode: nil,
            shouldInterpolate: false,
            intent: .defaultIntent
        )!
    }

    /// The frame scaled up by a whole number, each pixel a scale x scale block. The preview
    /// shows this at exactly its pixel size, so the result is crisp whatever filter the
    /// window or QuickLook would otherwise apply.
    public static func scaledImage(for frame: SpriteFrame, scale: Int) -> CGImage {
        let width = frame.width * scale
        let height = frame.height * scale
        let context = CGContext(
            data: nil,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: 0,
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        )!
        context.interpolationQuality = .none
        context.draw(image(for: frame), in: CGRect(x: 0, y: 0, width: width, height: height))
        return context.makeImage()!
    }

    /// The longest side, in pixels, a pre-scaled frame image may have. The layer's nearest-neighbor
    /// filter takes it the rest of the way, so a full-screen preview doesn't hold a ~32 MB image
    /// per frame.
    public static let maximumPrescaledSide = 512

    /// The whole-number factor to pre-scale a frame by for a given on-screen pixel scale:
    /// the pixel scale itself, capped so the image's long side stays within maximumPrescaledSide.
    public static func prescaleFactor(frameSize: CGSize, pixelScale: Int) -> Int {
        let longSide = Int(max(frameSize.width, frameSize.height))
        guard longSide > 0 else {
            return 1
        }
        return max(1, min(pixelScale, maximumPrescaledSide / longSide))
    }

    /// The scale to show content at in available space: a whole number when it fits, so pixels
    /// stay square blocks, otherwise the fraction that fits it, so nothing is cropped.
    public static func displayScale(contentSize: CGSize, fitting available: CGSize) -> CGFloat {
        guard contentSize.width > 0, contentSize.height > 0 else {
            return 1
        }
        let fit = min(available.width / contentSize.width, available.height / contentSize.height)
        if fit >= 1 {
            return fit.rounded(.down)
        }
        return max(fit, 0)
    }

    /// The widest and tallest of an animation's frames, so every frame shares one scale and the
    /// sprite doesn't jump when frame sizes differ.
    public static func largestFrameSize(of animation: SpriteAnimation) -> CGSize {
        CGSize(
            width: animation.frames.map(\.width).max() ?? 0,
            height: animation.frames.map(\.height).max() ?? 0
        )
    }

    /// The largest whole-number scale at which content fits in available; never below 1.
    public static func integerScale(contentSize: CGSize, fitting available: CGSize) -> Int {
        guard contentSize.width > 0, contentSize.height > 0 else {
            return 1
        }
        let fit = min(available.width / contentSize.width, available.height / contentSize.height)
        return max(1, Int(fit.rounded(.down)))
    }

    /// The first frame of the first animation (the one the preview starts on), centered on a
    /// transparent canvas of exactly maximumSize: scaled up by a whole number when it fits,
    /// otherwise scaled down to fit. The canvas is the whole size because Finder places a
    /// thumbnail's context at the bottom left of the icon space; transparent pixels stay
    /// transparent so the thumbnail sits on Finder's own background.
    public static func thumbnailImage(for sprite: Sprite, maximumSize: CGSize) -> CGImage {
        let frame = sprite.animations[0].frames[0]
        let frameSize = CGSize(width: frame.width, height: frame.height)
        let scale: CGFloat
        if frameSize.width <= maximumSize.width, frameSize.height <= maximumSize.height {
            scale = CGFloat(integerScale(contentSize: frameSize, fitting: maximumSize))
        } else {
            scale = min(maximumSize.width / frameSize.width, maximumSize.height / frameSize.height)
        }
        let canvasWidth = max(1, Int(maximumSize.width.rounded(.down)))
        let canvasHeight = max(1, Int(maximumSize.height.rounded(.down)))
        let spriteWidth = min(canvasWidth, max(1, Int((frameSize.width * scale).rounded())))
        let spriteHeight = min(canvasHeight, max(1, Int((frameSize.height * scale).rounded())))
        let context = CGContext(
            data: nil,
            width: canvasWidth,
            height: canvasHeight,
            bitsPerComponent: 8,
            bytesPerRow: 0,
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        )!
        context.interpolationQuality = .none
        // Whole-pixel offsets keep every sprite pixel on the canvas grid
        let spriteRect = CGRect(
            x: (canvasWidth - spriteWidth) / 2,
            y: (canvasHeight - spriteHeight) / 2,
            width: spriteWidth,
            height: spriteHeight
        )
        context.draw(image(for: frame), in: spriteRect)
        return context.makeImage()!
    }

    /// Draw an image over the whole of a context, nearest neighbor. The context's drawable
    /// bounds are used rather than any size handed in alongside it: QuickLook's thumbnail
    /// context is in pixels (2x its contextSize on Retina), so drawing into contextSize filled
    /// only its bottom-left quarter.
    public static func drawFillingContext(_ image: CGImage, in context: CGContext) {
        context.interpolationQuality = .none
        context.draw(image, in: context.boundingBoxOfClipPath)
    }

    /// One tile of the preview's transparency background: 2x2 cells of two light grays.
    public static func checkerboardImage(cellSize: Int) -> CGImage {
        let side = cellSize * 2
        let context = CGContext(
            data: nil,
            width: side,
            height: side,
            bitsPerComponent: 8,
            bytesPerRow: 0,
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        )!
        context.setFillColor(CGColor(gray: 0.85, alpha: 1))
        context.fill(CGRect(x: 0, y: 0, width: side, height: side))
        context.setFillColor(CGColor(gray: 0.65, alpha: 1))
        context.fill(CGRect(x: 0, y: 0, width: cellSize, height: cellSize))
        context.fill(CGRect(x: cellSize, y: cellSize, width: cellSize, height: cellSize))
        return context.makeImage()!
    }

    private static func premultiply(_ channel: UInt8, by alpha: UInt8) -> UInt8 {
        UInt8((Int(channel) * Int(alpha) + 127) / 255)
    }
}
