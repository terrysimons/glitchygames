// swift-tools-version: 6.0
// SpriteCore: the GlitchyGames sprite TOML reader and renderer shared by the QuickLook extensions
// (docs/specs/2026-10-29-sprite-quicklook-design.md)

import PackageDescription

let package = Package(
    name: "SpriteCore",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "SpriteCore", targets: ["SpriteCore"]),
    ],
    dependencies: [
        .package(url: "https://github.com/dduan/TOMLDecoder", exact: "0.4.5"),
    ],
    targets: [
        .target(
            name: "SpriteCore",
            dependencies: [.product(name: "TOMLDecoder", package: "TOMLDecoder")]
        ),
        .testTarget(
            name: "SpriteCoreTests",
            dependencies: ["SpriteCore"],
            // Sprite TOMLs and the frames the engine draws for them (tools/dump_engine_frames.py)
            resources: [.copy("Golden")]
        ),
    ]
)
