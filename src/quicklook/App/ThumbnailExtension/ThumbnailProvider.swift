import CoreGraphics
import Foundation
import QuickLookThumbnailing
import SpriteCore

/// Finder thumbnails for sprite .toml files: the first frame of the first animation, crisp,
/// transparent where the sprite is. Any other .toml is declined, so Finder keeps its own icon.
final class ThumbnailProvider: QLThumbnailProvider {
    private struct NotASpriteError: Error {}

    override func provideThumbnail(
        for request: QLFileThumbnailRequest,
        _ handler: @escaping (QLThumbnailReply?, (any Error)?) -> Void
    ) {
        let data: Data
        do {
            data = try Data(contentsOf: request.fileURL)
        } catch {
            handler(nil, error)
            return
        }
        guard case .sprite(let sprite) = SpriteLoader.load(data: data) else {
            handler(nil, NotASpriteError())
            return
        }
        // maximumSize is in points; fit the sprite to the pixels it will really get (twice as many
        // on a Retina display), and hand QuickLook a context sized back in points. The image is
        // the whole requested size with the sprite centered: Finder anchors a smaller context at
        // the bottom left.
        let maximumPixelSize = CGSize(
            width: request.maximumSize.width * request.scale,
            height: request.maximumSize.height * request.scale
        )
        let image = SpriteRenderer.thumbnailImage(for: sprite, maximumSize: maximumPixelSize)
        let contextSize = CGSize(
            width: CGFloat(image.width) / request.scale,
            height: CGFloat(image.height) / request.scale
        )
        let reply = QLThumbnailReply(contextSize: contextSize) { context in
            SpriteRenderer.drawFillingContext(image, in: context)
            return true
        }
        handler(reply, nil)
    }
}
