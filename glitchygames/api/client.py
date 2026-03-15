"""CLI client for the GlitchyGames Sprite Generation API."""

import argparse
import base64
import io
import json
import logging
import sys
from pathlib import Path

import httpx
import toml
from apng import APNG, PNG
from glitchygames.tools.ascii_renderer import ASCIIRenderer

LOG = logging.getLogger("glitchygames.api.client")

DEFAULT_SERVER_URL = "http://localhost:8000"
DEFAULT_OUTPUT_FORMATS = ["toml", "png"]

MAX_FILE_NUMBERING_ATTEMPTS = 1000


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI client.

    Returns:
        Configured argument parser

    """
    parser = argparse.ArgumentParser(
        prog="glitchygames-client",
        description="CLI client for GlitchyGames Sprite Generation API",
    )

    parser.add_argument(
        "prompt",
        nargs="?",  # Optional when using --extract-frames
        help="Text description of the sprite to generate",
    )

    parser.add_argument(
        "--extract-frames",
        metavar="APNG_PATH",
        help="Extract frames from an APNG file instead of generating a sprite",
    )

    parser.add_argument(
        "--server-url",
        default=DEFAULT_SERVER_URL,
        help=f"Server URL (default: {DEFAULT_SERVER_URL})",
    )

    parser.add_argument(
        "--output-format",
        "-f",
        action="append",
        choices=["toml", "png"],
        dest="output_formats",
        help="Output format (can be specified multiple times). Default: toml and png",
    )

    parser.add_argument(
        "--output-path",
        "-o",
        help="Directory to save output files. Created if it doesn't exist.",
    )

    parser.add_argument(
        "--width",
        type=int,
        help="Sprite width in pixels (1-64)",
    )

    parser.add_argument(
        "--height",
        type=int,
        help="Sprite height in pixels (1-64)",
    )

    parser.add_argument(
        "--frame-count",
        type=int,
        help="Number of frames per animation (1-32)",
    )

    parser.add_argument(
        "--film-strip-count",
        type=int,
        help="Number of film strips/animations to create (1-8)",
    )

    parser.add_argument(
        "--animation-duration",
        type=float,
        help="Duration of animation in seconds",
    )

    parser.add_argument(
        "--png-scale",
        type=int,
        default=1,
        help="Scale factor for PNG output (1-10, default: 1)",
    )

    parser.add_argument(
        "--extract-scale",
        type=int,
        default=8,
        help="Scale factor for extracted PNG frames using nearest-neighbor (default: 8)",
    )

    parser.add_argument(
        "--animation-language-model",
        metavar="MODEL",
        help=(
            "Override the AI model for generation "
            "(aisuite format, e.g., 'anthropic:claude-sonnet-4-5')"
        ),
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress output except errors",
    )

    return parser


def extract_apng_frames(
    server_url: str,
    apng_path: str,
) -> dict:
    """Extract frames and metadata from an APNG file.

    Args:
        server_url: Base URL of the API server
        apng_path: Path to the APNG file

    Returns:
        API response with frames and metadata

    """
    url = f"{server_url.rstrip('/')}/sprites/extract-frames"

    # Read and encode the APNG file
    apng_bytes = Path(apng_path).read_bytes()
    apng_base64 = base64.b64encode(apng_bytes).decode("utf-8")

    payload = {
        "apng_base64": apng_base64,
    }

    LOG.debug(f"Sending extract request to {url}")

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def generate_sprite(
    server_url: str,
    prompt: str,
    output_formats: list[str],
    output_path: str | None = None,
    width: int | None = None,
    height: int | None = None,
    frame_count: int | None = None,
    film_strip_count: int | None = None,
    animation_duration: float | None = None,
    png_scale: int = 1,
    model: str | None = None,
) -> dict:
    """Generate a sprite via the API.

    Args:
        server_url: Base URL of the API server
        prompt: Text description of the sprite
        output_formats: List of output formats ('toml', 'png')
        output_path: Directory to save files (optional)
        width: Sprite width in pixels (optional)
        height: Sprite height in pixels (optional)
        frame_count: Number of frames per animation (default: 1)
        film_strip_count: Number of film strips to create (optional)
        animation_duration: Duration of animation in seconds (optional)
        png_scale: Scale factor for PNG output
        model: AI model override in aisuite format (e.g., 'anthropic:claude-sonnet-4-5')

    Returns:
        API response as a dictionary

    """
    url = f"{server_url.rstrip('/')}/sprites/generate"

    # Default frame_count to 1
    effective_frame_count = frame_count or 1

    payload = {
        "prompt": prompt,
        "output_format": output_formats,
        "png_scale": png_scale,
        "frame_count": effective_frame_count,
    }

    if output_path:
        payload["output_path"] = output_path
    if width:
        payload["width"] = width
    if height:
        payload["height"] = height
    if film_strip_count:
        payload["film_strip_count"] = film_strip_count
    if animation_duration:
        payload["animation_duration"] = animation_duration
    if model:
        payload["model"] = model

    LOG.debug(f"Sending request to {url}")
    LOG.debug(f"Payload: {json.dumps(payload, indent=2)}")

    with httpx.Client(timeout=300.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def display_sprite_ascii(toml_content: str) -> None:
    """Display the sprite as colorized ASCII art in the terminal.

    Args:
        toml_content: TOML content of the sprite

    """
    try:
        sprite_data = toml.loads(toml_content)
        renderer = ASCIIRenderer()
        colors = renderer._extract_colors_from_toml(sprite_data)

        # Check if it's an animated sprite
        if sprite_data.get("animation"):
            animations = sprite_data["animation"]
            for anim_index, animation in enumerate(animations):
                anim_name = animation.get("namespace", f"animation-{anim_index}")
                frames = animation.get("frame", [])

                print(f"\n=== Animation: {anim_name} ({len(frames)} frames) ===")  # noqa: T201

                for frame_index, frame in enumerate(frames):
                    pixels = frame.get("pixels", "")
                    if pixels:
                        print(f"\n--- Frame {frame_index} ---")  # noqa: T201
                        colorized = renderer._colorize_pixels(pixels, colors)
                        print(colorized)  # noqa: T201
        else:
            # Static sprite
            pixels = renderer._extract_pixels_from_toml(sprite_data)
            if pixels:
                print("\n=== Sprite Preview ===")  # noqa: T201
                colorized = renderer._colorize_pixels(pixels, colors)
                print(colorized)  # noqa: T201

        print()  # noqa: T201  # Empty line after output

    except (ValueError, KeyError, TypeError, AttributeError) as e:
        LOG.warning(f"Could not render ASCII preview: {e}")


def create_apng_from_frames(
    frames_base64: list[str],
    frame_delay_ms: int = 100,
) -> bytes:
    """Create an APNG (Animated PNG) from a list of base64-encoded PNG frames.

    Args:
        frames_base64: List of base64-encoded PNG frame data
        frame_delay_ms: Delay between frames in milliseconds

    Returns:
        APNG file content as bytes

    """
    apng = APNG()

    for frame_base64 in frames_base64:
        frame_bytes = base64.b64decode(frame_base64)
        # Create PNG from bytes
        png = PNG.from_bytes(frame_bytes)
        # Add frame with delay (delay is in milliseconds, APNG uses delay/delay_den)
        apng.append(png, delay=frame_delay_ms, delay_den=1000)

    # Write to bytes buffer
    buffer = io.BytesIO()
    apng.save(buffer)
    return buffer.getvalue()


def find_available_path(base_path: Path) -> Path:
    """Find an available file path, auto-incrementing if necessary.

    If the base path doesn't exist, returns it unchanged.
    If it exists, tries base_001, base_002, etc. until finding an available name.

    Args:
        base_path: The desired file path

    Returns:
        An available file path (either the original or with _NNN suffix)

    """
    if not base_path.exists():
        return base_path

    # File exists, find next available number
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent

    counter = 1
    while counter < MAX_FILE_NUMBERING_ATTEMPTS:  # Safety limit
        new_path = parent / f"{stem}_{counter:03d}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1

    # Fallback: use timestamp if we somehow hit 999 files
    import time

    timestamp = int(time.time())
    return parent / f"{stem}_{timestamp}{suffix}"


def find_available_directory(base_dir: Path) -> Path:
    """Find an available directory path with incremented number.

    Always uses numbered format: base-001, base-002, etc.
    Finds the next available number.

    Args:
        base_dir: The base directory path (without number)

    Returns:
        An available directory path with -NNN suffix

    """
    name = base_dir.name
    parent = base_dir.parent

    counter = 1
    while counter < MAX_FILE_NUMBERING_ATTEMPTS:  # Safety limit
        new_dir = parent / f"{name}-{counter:03d}"
        if not new_dir.exists():
            return new_dir
        counter += 1

    # Fallback: use timestamp if we somehow hit 999 directories
    import time

    timestamp = int(time.time())
    return parent / f"{name}-{timestamp}"


def save_files_locally(
    response: dict,
    output_path: str,
    output_formats: list[str],
    animation_duration: float | None = None,
    extract_scale: int = 8,
    model_used: str | None = None,
) -> list[str]:
    """Save files locally from the API response.

    Creates a directory for each sprite containing:
    - The .toml file
    - The .apng file (if animated)
    - An 'extracted' subdirectory with individual frame PNGs (upscaled nearest-neighbor)

    Args:
        response: API response dictionary
        output_path: Base directory to save files
        output_formats: List of requested output formats
        animation_duration: Total animation duration in seconds (for APNG timing)
        extract_scale: Scale factor for extracted frames (nearest-neighbor, default: 8)
        model_used: AI model used for generation (embedded in PNG metadata)

    Returns:
        List of saved file paths

    """
    saved_files = []
    base_output_dir = Path(output_path)
    base_output_dir.mkdir(parents=True, exist_ok=True)

    sprite_name = response.get("sprite_name", "sprite")
    # Sanitize sprite name for directory/filename
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in sprite_name)
    if not safe_name:
        safe_name = "sprite"

    # Create a directory for this sprite
    sprite_dir = find_available_directory(base_output_dir / safe_name)
    sprite_dir.mkdir(parents=True, exist_ok=True)
    LOG.info(f"Created sprite directory: {sprite_dir}")

    # Save TOML if requested and available
    if "toml" in output_formats and response.get("toml_content"):
        toml_path = sprite_dir / f"{safe_name}.toml"
        toml_path.write_text(response["toml_content"], encoding="utf-8")
        saved_files.append(str(toml_path))
        LOG.info(f"Saved TOML: {toml_path}")

    # Save APNG and extracted frames if animation frames are available
    if response.get("all_frames_png_base64"):
        frames = response["all_frames_png_base64"]
        rendered_frames = response.get("rendered_frames", [])
        frame_count = len(frames)

        # Calculate frame delay for APNG
        # Use animation_duration if provided, otherwise default to 100ms per frame
        if animation_duration and frame_count > 0:
            frame_delay_ms = int((animation_duration * 1000) / frame_count)
        else:
            frame_delay_ms = 100  # Default: 10 FPS

        # Create and save APNG
        apng_path = sprite_dir / f"{safe_name}.apng"
        apng_bytes = create_apng_from_frames(frames, frame_delay_ms=frame_delay_ms)
        apng_path.write_bytes(apng_bytes)
        saved_files.append(str(apng_path))
        LOG.info(f"Saved APNG: {apng_path} ({frame_count} frames, {frame_delay_ms}ms/frame)")

        # Create extracted directory and save individual frames with metadata
        extracted_dir = sprite_dir / "extracted"
        extracted_dir.mkdir(exist_ok=True)

        from PIL import Image, PngImagePlugin

        # Use rendered_frames for proper animation-#-frame-#.png naming
        if rendered_frames:
            for frame_info in rendered_frames:
                animation_index = frame_info.get("animation_index", 0)
                frame_index = frame_info.get("frame_index", 0)
                frame_base64 = frame_info.get("png_base64", "")

                frame_name = f"animation-{animation_index}-frame-{frame_index}"
                frame_path = extracted_dir / f"{frame_name}.png"
                frame_bytes = base64.b64decode(frame_base64)

                # Load PNG
                frame_image = Image.open(io.BytesIO(frame_bytes))

                # Upscale using nearest-neighbor to keep pixels crisp
                if extract_scale > 1:
                    original_size = frame_image.size
                    new_size = (
                        original_size[0] * extract_scale,
                        original_size[1] * extract_scale,
                    )
                    frame_image = frame_image.resize(new_size, Image.NEAREST)

                # Create PNG metadata
                png_metadata = PngImagePlugin.PngInfo()
                png_metadata.add_text("FrameName", frame_name)
                png_metadata.add_text("AnimationIndex", str(animation_index))
                png_metadata.add_text("FrameIndex", str(frame_index))
                png_metadata.add_text("FrameCount", str(frame_count))
                png_metadata.add_text("DelayMs", str(frame_delay_ms))
                png_metadata.add_text("ExtractScale", str(extract_scale))
                if model_used:
                    png_metadata.add_text("AIModel", model_used)

                # Save with metadata (uncompressed)
                with frame_path.open("wb") as f:
                    frame_image.save(f, format="PNG", compress_level=0, pnginfo=png_metadata)

                saved_files.append(str(frame_path))
        else:
            # Fallback to old naming if rendered_frames not available
            for i, frame_base64 in enumerate(frames):
                frame_name = f"animation-0-frame-{i}"
                frame_path = extracted_dir / f"{frame_name}.png"
                frame_bytes = base64.b64decode(frame_base64)

                # Load PNG
                frame_image = Image.open(io.BytesIO(frame_bytes))

                # Upscale using nearest-neighbor to keep pixels crisp
                if extract_scale > 1:
                    original_size = frame_image.size
                    new_size = (
                        original_size[0] * extract_scale,
                        original_size[1] * extract_scale,
                    )
                    frame_image = frame_image.resize(new_size, Image.NEAREST)

                # Create PNG metadata
                png_metadata = PngImagePlugin.PngInfo()
                png_metadata.add_text("FrameName", frame_name)
                png_metadata.add_text("AnimationIndex", "0")
                png_metadata.add_text("FrameIndex", str(i))
                png_metadata.add_text("FrameCount", str(frame_count))
                png_metadata.add_text("DelayMs", str(frame_delay_ms))
                png_metadata.add_text("ExtractScale", str(extract_scale))
                if model_used:
                    png_metadata.add_text("AIModel", model_used)

                # Save with metadata (uncompressed)
                with frame_path.open("wb") as f:
                    frame_image.save(f, format="PNG", compress_level=0, pnginfo=png_metadata)

                saved_files.append(str(frame_path))

        LOG.info(f"Saved {frame_count} frames to: {extracted_dir} (scale: {extract_scale}x)")

    # Save single PNG if requested, available, and no animation frames
    elif "png" in output_formats and response.get("png_base64"):
        png_path = sprite_dir / f"{safe_name}.png"
        png_bytes = base64.b64decode(response["png_base64"])
        png_path.write_bytes(png_bytes)
        saved_files.append(str(png_path))
        LOG.info(f"Saved PNG: {png_path}")

    return saved_files


def _handle_extract_frames(parsed_args: argparse.Namespace) -> int:
    """Handle the --extract-frames command.

    Args:
        parsed_args: Parsed command line arguments

    Returns:
        Exit code (0 for success, non-zero for errors)

    """
    apng_path = parsed_args.extract_frames

    try:
        LOG.info(f"Extracting frames from: {apng_path}")
        response = extract_apng_frames(
            server_url=parsed_args.server_url,
            apng_path=apng_path,
        )

        if not response.get("success"):
            LOG.error(f"Extraction failed: {response.get('error', 'Unknown error')}")
            return 1

        # Display metadata
        LOG.info(f"Extracted {response.get('frame_count')} frames")
        if response.get("width") and response.get("height"):
            LOG.info(f"  Canvas size: {response.get('width')}x{response.get('height')} pixels")
        if response.get("total_duration_ms"):
            LOG.info(f"  Total duration: {response.get('total_duration_ms')}ms")
        if response.get("loop_count") is not None:
            loops = response.get("loop_count")
            LOG.info(f"  Loop count: {'infinite' if loops == 0 else loops}")

        # Save extracted frames if output_path specified
        if parsed_args.output_path:
            output_dir = Path(parsed_args.output_path)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Get base name from APNG file
            apng_name = Path(apng_path).stem
            saved_files = []

            for frame_info in response.get("frames", []):
                frame_path = output_dir / f"{apng_name}_frame_{frame_info['index']:03d}.png"
                frame_bytes = base64.b64decode(frame_info["png_base64"])
                frame_path.write_bytes(frame_bytes)
                saved_files.append(str(frame_path))
                LOG.debug(f"Saved frame: {frame_path}")

            LOG.info(f"Saved {len(saved_files)} frames to {output_dir}")

        # Output JSON to stdout if verbose or no output path
        if parsed_args.verbose or not parsed_args.output_path:
            import json

            # Remove base64 data from output for readability unless verbose
            output_data = response.copy()
            if not parsed_args.verbose:
                for frame in output_data.get("frames", []):
                    frame["png_base64"] = f"<{len(frame.get('png_base64', ''))} chars>"
            print(json.dumps(output_data, indent=2))  # noqa: T201

        return 0

    except FileNotFoundError:
        LOG.error(f"APNG file not found: {apng_path}")  # noqa: TRY400
        return 1
    except httpx.ConnectError:
        LOG.error(f"Could not connect to server at {parsed_args.server_url}")  # noqa: TRY400
        LOG.error("Is the server running? Start it with: glitchygames-server")  # noqa: TRY400
        return 1
    except httpx.HTTPStatusError as e:
        LOG.error(f"HTTP error: {e.response.status_code} - {e.response.text}")  # noqa: TRY400
        return 1
    except (OSError, ValueError, KeyError, TypeError) as e:
        LOG.error(f"Error: {e}")  # noqa: TRY400
        if parsed_args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def main(args: list[str] | None = None) -> int:
    """Run the CLI client.

    Args:
        args: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for errors)

    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # Set up logging
    if parsed_args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    elif parsed_args.quiet:
        logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Handle --extract-frames mode
    if parsed_args.extract_frames:
        return _handle_extract_frames(parsed_args)

    # Validate that prompt is provided for generation
    if not parsed_args.prompt:
        parser.error("prompt is required unless using --extract-frames")

    # Use default output formats if none specified
    output_formats = parsed_args.output_formats or DEFAULT_OUTPUT_FORMATS

    try:
        # Generate sprite (don't pass output_path to server - we save locally)
        LOG.info(f"Generating sprite: {parsed_args.prompt}")
        if parsed_args.animation_language_model:
            LOG.info(f"Using model: {parsed_args.animation_language_model}")
        response = generate_sprite(
            server_url=parsed_args.server_url,
            prompt=parsed_args.prompt,
            output_formats=output_formats,
            output_path=None,  # Always save locally, not on server
            width=parsed_args.width,
            height=parsed_args.height,
            frame_count=parsed_args.frame_count,
            film_strip_count=parsed_args.film_strip_count,
            animation_duration=parsed_args.animation_duration,
            png_scale=parsed_args.png_scale,
            model=parsed_args.animation_language_model,
        )

        if not response.get("success"):
            LOG.error(f"Generation failed: {response.get('error', 'Unknown error')}")
            return 1

        # Display results
        LOG.info(f"Generated sprite: {response.get('sprite_name')}")
        if response.get("is_animated"):
            LOG.info(f"  Animated: {response.get('frame_count')} frames")
        if response.get("width") and response.get("height"):
            LOG.info(f"  Size: {response.get('width')}x{response.get('height')} pixels")

        # Display colorized ASCII preview of the sprite
        if response.get("toml_content"):
            display_sprite_ascii(response["toml_content"])

        # Save files locally if output_path specified
        if parsed_args.output_path:
            saved_files = save_files_locally(
                response=response,
                output_path=parsed_args.output_path,
                output_formats=output_formats,
                animation_duration=parsed_args.animation_duration,
                extract_scale=parsed_args.extract_scale,
                model_used=parsed_args.animation_language_model,
            )
            if saved_files:
                LOG.info("Saved files:")
                for filepath in saved_files:
                    LOG.info(f"  {filepath}")

        # Output TOML to stdout if no output path specified
        if (
            not parsed_args.output_path
            and "toml" in output_formats
            and response.get("toml_content")
        ):
            if not parsed_args.quiet:
                print("\n--- TOML Content ---")  # noqa: T201
            print(response["toml_content"])  # noqa: T201

        return 0

    except httpx.ConnectError:
        LOG.error(f"Could not connect to server at {parsed_args.server_url}")  # noqa: TRY400
        LOG.error("Is the server running? Start it with: glitchygames-server")  # noqa: TRY400
        return 1
    except httpx.HTTPStatusError as e:
        LOG.error(f"HTTP error: {e.response.status_code} - {e.response.text}")  # noqa: TRY400
        return 1
    except (OSError, ValueError, KeyError, TypeError) as e:
        LOG.error(f"Error: {e}")  # noqa: TRY400
        if parsed_args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def run() -> None:
    """Entry point for the CLI client."""
    sys.exit(main())


if __name__ == "__main__":
    run()
