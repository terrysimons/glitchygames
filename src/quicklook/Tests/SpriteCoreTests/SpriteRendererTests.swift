import CoreGraphics
import Testing

@testable import SpriteCore

private let red = RGBA(red: 200, green: 10, blue: 20, alpha: 255)
private let green = RGBA(red: 10, green: 200, blue: 20, alpha: 255)

private func frame(width: Int, height: Int, pixels: [RGBA]) -> SpriteFrame {
    SpriteFrame(width: width, height: height, pixels: pixels, duration: 0.5)
}

/// Read an image back as premultiplied RGBA bytes, top row first
private func pixels(of image: CGImage) -> [RGBA] {
    let width = image.width
    let height = image.height
    var bytes = [UInt8](repeating: 0, count: width * height * 4)
    let context = CGContext(
        data: &bytes,
        width: width,
        height: height,
        bitsPerComponent: 8,
        bytesPerRow: width * 4,
        space: CGColorSpace(name: CGColorSpace.sRGB)!,
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    )!
    context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
    return stride(from: 0, to: bytes.count, by: 4).map {
        RGBA(red: bytes[$0], green: bytes[$0 + 1], blue: bytes[$0 + 2], alpha: bytes[$0 + 3])
    }
}

@Test func opaquePixelKeepsColor() {
    let image = SpriteRenderer.image(for: frame(width: 2, height: 1, pixels: [red, green]))
    #expect(image.width == 2)
    #expect(image.height == 1)
    #expect(pixels(of: image) == [red, green])
}

@Test func magentaPixelIsClear() {
    let image = SpriteRenderer.image(for: frame(width: 1, height: 1, pixels: [RGBA.magenta]))
    #expect(pixels(of: image) == [RGBA(red: 0, green: 0, blue: 0, alpha: 0)])
}

@Test func halfAlphaIsPremultiplied() {
    let half = RGBA(red: 200, green: 100, blue: 0, alpha: 128)
    let image = SpriteRenderer.image(for: frame(width: 1, height: 1, pixels: [half]))
    let drawn = pixels(of: image)[0]
    #expect(drawn.alpha == 128)
    #expect(abs(Int(drawn.red) - 100) <= 1)
    #expect(abs(Int(drawn.green) - 50) <= 1)
}

@Test func firstRowIsTop() {
    let image = SpriteRenderer.image(for: frame(width: 1, height: 2, pixels: [red, green]))
    #expect(pixels(of: image) == [red, green])
}

@Test func scaledImageRepeatsEachPixelInABlock() {
    let image = SpriteRenderer.scaledImage(for: frame(width: 2, height: 1, pixels: [red, green]), scale: 3)
    #expect(image.width == 6)
    #expect(image.height == 3)
    let row = [red, red, red, green, green, green]
    #expect(pixels(of: image) == row + row + row)
}

@Test func scaledImageKeepsTransparencyClear() {
    let image = SpriteRenderer.scaledImage(for: frame(width: 1, height: 1, pixels: [RGBA.magenta]), scale: 2)
    #expect(Set(pixels(of: image)) == [RGBA(red: 0, green: 0, blue: 0, alpha: 0)])
}

@Test func prescaleFactorUsesThePixelScaleWhenSmall() {
    #expect(SpriteRenderer.prescaleFactor(frameSize: CGSize(width: 16, height: 16), pixelScale: 4) == 4)
}

@Test func prescaleFactorCapsTheLongSideAt512() {
    // 16 px at a full-screen pixel scale of 176 would be 2816 px a side (~32 MB a frame)
    #expect(SpriteRenderer.prescaleFactor(frameSize: CGSize(width: 16, height: 8), pixelScale: 176) == 32)
    #expect(SpriteRenderer.prescaleFactor(frameSize: CGSize(width: 256, height: 256), pixelScale: 8) == 2)
}

@Test func prescaleFactorIsNeverBelowOne() {
    #expect(SpriteRenderer.prescaleFactor(frameSize: CGSize(width: 4096, height: 4096), pixelScale: 3) == 1)
    #expect(SpriteRenderer.prescaleFactor(frameSize: CGSize(width: 16, height: 16), pixelScale: 0) == 1)
}

@Test func displayScaleIsAWholeNumberWhenTheSpriteFits() {
    #expect(SpriteRenderer.displayScale(contentSize: CGSize(width: 16, height: 16), fitting: CGSize(width: 100, height: 60)) == 3)
}

@Test func displayScaleShrinksASpriteBiggerThanTheSpace() {
    #expect(SpriteRenderer.displayScale(contentSize: CGSize(width: 1000, height: 500), fitting: CGSize(width: 500, height: 500)) == 0.5)
}

@Test func integerScaleFloors() {
    #expect(SpriteRenderer.integerScale(contentSize: CGSize(width: 16, height: 16), fitting: CGSize(width: 100, height: 60)) == 3)
}

@Test func integerScaleNeverBelowOne() {
    #expect(SpriteRenderer.integerScale(contentSize: CGSize(width: 64, height: 64), fitting: CGSize(width: 10, height: 10)) == 1)
}

@Test func integerScaleOfEmptyContentIsOne() {
    #expect(SpriteRenderer.integerScale(contentSize: .zero, fitting: CGSize(width: 10, height: 10)) == 1)
}

@Test func largestFrameSizeUsesWidestAndTallest() {
    let animation = SpriteAnimation(name: "a", loop: true, frames: [
        frame(width: 8, height: 16, pixels: Array(repeating: red, count: 128)),
        frame(width: 16, height: 8, pixels: Array(repeating: red, count: 128)),
    ])
    #expect(SpriteRenderer.largestFrameSize(of: animation) == CGSize(width: 16, height: 16))
}

@Test func thumbnailIsFirstFrameScaled() {
    let sprite = Sprite(name: "s", animations: [
        SpriteAnimation(name: "a", loop: true, frames: [
            frame(width: 2, height: 2, pixels: [red, green, green, red]),
            frame(width: 2, height: 2, pixels: [green, green, green, green]),
        ]),
    ])
    let image = SpriteRenderer.thumbnailImage(for: sprite, maximumSize: CGSize(width: 64, height: 64))
    #expect(image.width == 64)
    #expect(image.height == 64)
    let drawn = pixels(of: image)
    #expect(drawn[0] == red)
    #expect(drawn[63] == green)
    #expect(drawn[63 * 64] == green)
    #expect(drawn[63 * 64 + 63] == red)
}

@Test func thumbnailFillsTheRequestedSizeWithTheSpriteCentered() {
    // Finder places a thumbnail's context at the bottom left of the icon space, so the image
    // must be the whole requested size with the sprite centered in it
    let sprite = Sprite(name: "s", animations: [
        SpriteAnimation(name: "a", loop: true, frames: [frame(width: 2, height: 1, pixels: [RGBA.magenta, red])]),
    ])
    let image = SpriteRenderer.thumbnailImage(for: sprite, maximumSize: CGSize(width: 8, height: 8))
    #expect(image.width == 8)
    #expect(image.height == 8)
    let drawn = pixels(of: image)
    // The 8x4 sprite sits on rows 2-5; everything else, and its magenta half, is transparent
    #expect(drawn[0 * 8 + 7].alpha == 0)
    #expect(drawn[1 * 8 + 7].alpha == 0)
    #expect(drawn[2 * 8 + 0].alpha == 0)
    #expect(drawn[2 * 8 + 7] == red)
    #expect(drawn[5 * 8 + 4] == red)
    #expect(drawn[6 * 8 + 7].alpha == 0)
}

@Test func thumbnailCentersATallSpriteHorizontally() {
    let sprite = Sprite(name: "s", animations: [
        SpriteAnimation(name: "a", loop: true, frames: [frame(width: 1, height: 2, pixels: [red, green])]),
    ])
    let image = SpriteRenderer.thumbnailImage(for: sprite, maximumSize: CGSize(width: 8, height: 8))
    #expect(image.width == 8)
    #expect(image.height == 8)
    let drawn = pixels(of: image)
    // 4x8 sprite on columns 2-5, red on top
    #expect(drawn[0 * 8 + 1].alpha == 0)
    #expect(drawn[0 * 8 + 2] == red)
    #expect(drawn[7 * 8 + 5] == green)
    #expect(drawn[7 * 8 + 6].alpha == 0)
}

@Test func thumbnailOfLargeSpriteScalesDownWithoutBlending() {
    var checker: [RGBA] = []
    for row in 0..<256 {
        for column in 0..<256 {
            checker.append((row + column) % 2 == 0 ? red : green)
        }
    }
    let sprite = Sprite(name: "s", animations: [
        SpriteAnimation(name: "a", loop: true, frames: [frame(width: 256, height: 256, pixels: checker)]),
    ])
    let image = SpriteRenderer.thumbnailImage(for: sprite, maximumSize: CGSize(width: 100, height: 100))
    #expect(image.width == 100)
    #expect(image.height == 100)
    let drawn = Set(pixels(of: image))
    #expect(drawn.isSubset(of: [red, green]))
}

@Test func checkerboardIsTwoCellsSquare() {
    let image = SpriteRenderer.checkerboardImage(cellSize: 8)
    #expect(image.width == 16)
    #expect(image.height == 16)
    let drawn = pixels(of: image)
    #expect(drawn[0] != drawn[8])
    #expect(drawn[0] == drawn[8 * 16 + 8])
}

private func context(pixelWidth: Int, pixelHeight: Int, userSpaceScale: CGFloat) -> CGContext {
    let context = CGContext(
        data: nil,
        width: pixelWidth,
        height: pixelHeight,
        bitsPerComponent: 8,
        bytesPerRow: 0,
        space: CGColorSpace(name: CGColorSpace.sRGB)!,
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    )!
    context.scaleBy(x: userSpaceScale, y: userSpaceScale)
    return context
}

@Test(arguments: [1.0, 2.0])
func drawFillingContextCoversTheWholeContext(userSpaceScale: CGFloat) {
    // QuickLook's thumbnail context is 2x its contextSize on Retina; whichever units its
    // drawing space is in, the thumbnail must fill all of it, not the bottom-left quarter
    let image = SpriteRenderer.image(for: frame(width: 2, height: 2, pixels: [red, red, red, red]))
    let target = context(pixelWidth: 8, pixelHeight: 8, userSpaceScale: userSpaceScale)
    SpriteRenderer.drawFillingContext(image, in: target)
    let drawn = pixels(of: target.makeImage()!)
    #expect(Set(drawn) == [red])
}
