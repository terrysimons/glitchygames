// Ask QuickLook for thumbnails the way Finder does (QLThumbnailGenerator) and save them as PNGs.
//
// Use this, not `qlmanage -t`, to check the thumbnail extension: on current macOS `qlmanage -t`
// only uses the old QuickLook generator plug-ins, never app-extension thumbnail providers, and
// it hangs on any file type that has no generator (found 2026-10-29; plans/future-work.md).
//
// Usage: swift tools/make_thumbnails.swift <out-directory> <file>...
// Prints, per file, whether QuickLook made a real thumbnail or fell back to the file's icon.

import AppKit
import QuickLookThumbnailing

let thumbnailSize = CGSize(width: 256, height: 256)
let timeoutSeconds = 20.0

let outDirectory = URL(fileURLWithPath: CommandLine.arguments[1])
try FileManager.default.createDirectory(at: outDirectory, withIntermediateDirectories: true)
let files = CommandLine.arguments.dropFirst(2).map { URL(fileURLWithPath: $0) }
let group = DispatchGroup()

for file in files {
    group.enter()
    let request = QLThumbnailGenerator.Request(
        fileAt: file,
        size: thumbnailSize,
        scale: 1,
        representationTypes: .all
    )
    QLThumbnailGenerator.shared.generateBestRepresentation(for: request) { representation, error in
        defer { group.leave() }
        guard let representation else {
            print("\(file.lastPathComponent): error \(String(describing: error))")
            return
        }
        let kind = representation.type == .thumbnail ? "thumbnail" : "icon (no thumbnail)"
        let image = representation.cgImage
        let outFile = outDirectory.appendingPathComponent(file.lastPathComponent + ".png")
        let pngData = NSBitmapImageRep(cgImage: image).representation(using: .png, properties: [:])
        do {
            try pngData?.write(to: outFile)
        } catch {
            print("\(file.lastPathComponent): could not write \(outFile.path): \(error)")
            return
        }
        print("\(file.lastPathComponent): \(kind) \(image.width)x\(image.height) -> \(outFile.path)")
    }
}

if group.wait(timeout: .now() + timeoutSeconds) == .timedOut {
    print("timed out after \(timeoutSeconds) seconds")
    exit(1)
}
