"""CLI client for the GlitchyGames Sprite Generation API.

Exit codes (``ExitCode``, glitchygames/exit_codes.py; logged as ``Exiting with ...``):

- ``SUCCESS``.
- ``GENERATION_REJECTED`` / ``EXTRACTION_REJECTED``: the server answered an error status (other
  than 503) or a response that says the request failed.
- ``SERVICE_UNAVAILABLE``: the server cannot be reached, stops answering, or answers 503.
- ``OPTIONS_REFUSED``: --server-url is not a usable URL.
- ``MISSING_INPUT``: the APNG to extract does not exist.
- ``UNUSABLE_INPUT``: an input file that cannot be read, or a response that cannot be decoded
  or is malformed (a missing field or one of the wrong type counts as the server's fault).
- ``CANNOT_WRITE_OUTPUT``: an output file or directory cannot be written.
- ``INTERNAL_ERROR``: any other exception (a client bug), logged with its traceback.
- argparse's ``ARGUMENT_PARSER_ERROR`` for a usage error.
"""

import argparse
import base64
import io
import json
import logging
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

import httpx
from apng import APNG, PNG

from glitchygames.clock import wall_clock_epoch_seconds
from glitchygames.exit_codes import ExitCode
from glitchygames.tools.ascii_renderer import ASCIIRenderer

LOG = logging.getLogger('glitchygames.api.client')

DEFAULT_SERVER_URL = 'http://localhost:8000'
DEFAULT_OUTPUT_FORMATS = ['toml', 'png']

MAX_FILE_NUMBERING_ATTEMPTS = 1000


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI client.

    Returns:
        Configured argument parser

    """
    parser = argparse.ArgumentParser(
        prog='glitchygames-client',
        description='CLI client for GlitchyGames Sprite Generation API',
    )

    parser.add_argument(
        'prompt',
        nargs='?',  # Optional when using --extract-frames
        help='Text description of the sprite to generate',
    )

    parser.add_argument(
        '--extract-frames',
        metavar='APNG_PATH',
        help='Extract frames from an APNG file instead of generating a sprite',
    )

    parser.add_argument(
        '--server-url',
        default=DEFAULT_SERVER_URL,
        help=f'Server URL (default: {DEFAULT_SERVER_URL})',
    )

    parser.add_argument(
        '--output-format',
        '-f',
        action='append',
        choices=['toml', 'png'],
        dest='output_formats',
        help='Output format (can be specified multiple times). Default: toml and png',
    )

    parser.add_argument(
        '--output-path',
        '-o',
        help="Directory to save output files. Created if it doesn't exist.",
    )

    parser.add_argument(
        '--width',
        type=int,
        help='Sprite width in pixels (1-64)',
    )

    parser.add_argument(
        '--height',
        type=int,
        help='Sprite height in pixels (1-64)',
    )

    parser.add_argument(
        '--frame-count',
        type=int,
        help='Number of frames per animation (1-32)',
    )

    parser.add_argument(
        '--film-strip-count',
        type=int,
        help='Number of film strips/animations to create (1-8)',
    )

    parser.add_argument(
        '--animation-duration',
        type=float,
        help='Duration of animation in seconds',
    )

    parser.add_argument(
        '--png-scale',
        type=int,
        default=1,
        help='Scale factor for PNG output (1-10, default: 1)',
    )

    parser.add_argument(
        '--extract-scale',
        type=int,
        default=8,
        help='Scale factor for extracted PNG frames using nearest-neighbor (default: 8)',
    )

    parser.add_argument(
        '--animation-language-model',
        metavar='MODEL',
        help=(
            'Override the AI model for generation '
            "(aisuite format, e.g., 'anthropic:claude-sonnet-4-5')"
        ),
    )

    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose output',
    )

    parser.add_argument(
        '--quiet',
        '-q',
        action='store_true',
        help='Suppress output except errors',
    )

    return parser


def _response_object(*, response: httpx.Response) -> dict[str, Any]:
    """Return a successful response's JSON body, which the API always sends as an object.

    A body that is not JSON raises ValueError (from ``response.json()``). Both that and the
    TypeError below are a malformed response (``ExitCode.UNUSABLE_INPUT`` through
    ``_exit_code_for_request_error``).

    Args:
        response: The server's answer (a 2xx status).

    Returns:
        The decoded JSON object.

    Raises:
        TypeError: If the body is JSON but not an object (a list, a string).

    """
    body = response.json()
    if not isinstance(body, dict):
        message = f'the server response is a JSON {type(body).__name__}, not an object'
        raise TypeError(message)
    return cast('dict[str, Any]', body)


def extract_apng_frames(
    server_url: str,
    apng_path: str,
) -> dict[str, Any]:
    """Extract frames and metadata from an APNG file.

    Args:
        server_url: Base URL of the API server
        apng_path: Path to the APNG file

    Returns:
        API response with frames and metadata

    """
    url = f'{server_url.rstrip("/")}/sprites/extract-frames'

    # Read and encode the APNG file
    apng_bytes = Path(apng_path).read_bytes()
    apng_base64 = base64.b64encode(apng_bytes).decode('utf-8')

    payload = {
        'apng_base64': apng_base64,
    }

    LOG.debug('Sending extract request to %s', url)

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return _response_object(response=response)


def generate_sprite(  # ruff: ignore[too-many-arguments]
    server_url: str,
    prompt: str,
    output_formats: list[str],
    *,
    output_path: str | None = None,
    width: int | None = None,
    height: int | None = None,
    frame_count: int | None = None,
    film_strip_count: int | None = None,
    animation_duration: float | None = None,
    png_scale: int = 1,
    model: str | None = None,
) -> dict[str, Any]:
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
    url = f'{server_url.rstrip("/")}/sprites/generate'

    # Default frame_count to 1
    effective_frame_count = frame_count or 1

    payload: dict[str, str | list[str] | int | float] = {
        'prompt': prompt,
        'output_format': output_formats,
        'png_scale': png_scale,
        'frame_count': effective_frame_count,
    }

    if output_path:
        payload['output_path'] = output_path
    if width:
        payload['width'] = width
    if height:
        payload['height'] = height
    if film_strip_count:
        payload['film_strip_count'] = film_strip_count
    if animation_duration:
        payload['animation_duration'] = animation_duration
    if model:
        payload['model'] = model

    LOG.debug('Sending request to %s', url)
    LOG.debug(f'Payload: {json.dumps(payload, indent=2)}')

    with httpx.Client(timeout=300.0) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return _response_object(response=response)


def display_sprite_ascii(toml_content: str) -> None:
    """Display the sprite as colorized ASCII art in the terminal.

    Args:
        toml_content: TOML content of the sprite

    """
    try:
        preview_lines = _sprite_ascii_preview_lines(toml_content=toml_content)
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        LOG.warning('Could not render ASCII preview: %s', e)
        return
    for line in preview_lines:
        print(line)  # ruff: ignore[print]
    print()  # ruff: ignore[print]  # Empty line after output


def _sprite_ascii_preview_lines(*, toml_content: str) -> list[str]:
    """Render a sprite as colorized ASCII art, one printed line per entry.

    Args:
        toml_content: TOML content of the sprite

    Returns:
        The preview's lines: each animation's frames, or the static sprite.

    """
    sprite_data = tomllib.loads(toml_content)
    renderer = ASCIIRenderer()
    colors = renderer.extract_colors_from_toml(sprite_data)
    lines: list[str] = []

    # Check if it's an animated sprite
    if sprite_data.get('animation'):
        animations = sprite_data['animation']
        for anim_index, animation in enumerate(animations):
            anim_name = animation.get('namespace', f'animation-{anim_index}')
            frames = animation.get('frame', [])

            lines.append(f'\n=== Animation: {anim_name} ({len(frames)} frames) ===')

            for frame_index, frame in enumerate(frames):
                pixels = frame.get('pixels', '')
                if pixels:
                    lines.extend((
                        f'\n--- Frame {frame_index} ---',
                        renderer.colorize_pixels(pixels, colors),
                    ))
    else:
        # Static sprite
        pixels = renderer.extract_pixels_from_toml(sprite_data)
        if pixels:
            lines.extend(('\n=== Sprite Preview ===', renderer.colorize_pixels(pixels, colors)))
    return lines


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
        # Create PNG from bytes (apng library lacks type stubs)
        png: PNG = PNG.from_bytes(frame_bytes)
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
        new_path = parent / f'{stem}_{counter:03d}{suffix}'
        if not new_path.exists():
            return new_path
        counter += 1

    # Fallback: use timestamp if we somehow hit 999 files
    timestamp = int(wall_clock_epoch_seconds())
    return parent / f'{stem}_{timestamp}{suffix}'


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
        new_dir = parent / f'{name}-{counter:03d}'
        if not new_dir.exists():
            return new_dir
        counter += 1

    # Fallback: use timestamp if we somehow hit 999 directories
    timestamp = int(wall_clock_epoch_seconds())
    return parent / f'{name}-{timestamp}'


def _save_extracted_frames(  # ruff: ignore[too-many-arguments]
    frame_entries: list[tuple[str, str, str, str]],
    extracted_dir: Path,
    *,
    frame_count: int,
    frame_delay_ms: int,
    extract_scale: int,
    model_used: str | None,
) -> list[str]:
    """Save individual extracted frames as PNGs with metadata.

    Args:
        frame_entries: List of (frame_name, animation_index_str, frame_index_str, base64_data)
        extracted_dir: Directory to save frames into
        frame_count: Total number of frames (for metadata)
        frame_delay_ms: Frame delay in ms (for metadata)
        extract_scale: Scale factor for nearest-neighbor upscale
        model_used: AI model name for metadata (or None)

    Returns:
        List of saved file paths

    """
    from PIL import Image, PngImagePlugin

    saved_paths: list[str] = []
    for frame_name, animation_index_str, frame_index_str, frame_base64 in frame_entries:
        frame_path = extracted_dir / f'{frame_name}.png'
        frame_image = Image.open(io.BytesIO(base64.b64decode(frame_base64)))

        # Upscale using nearest-neighbor to keep pixels crisp
        if extract_scale > 1:
            frame_image = frame_image.resize(
                (frame_image.width * extract_scale, frame_image.height * extract_scale),
                Image.Resampling.NEAREST,
            )

        # Create PNG metadata
        png_metadata = PngImagePlugin.PngInfo()
        png_metadata.add_text('FrameName', frame_name)
        png_metadata.add_text('AnimationIndex', animation_index_str)
        png_metadata.add_text('FrameIndex', frame_index_str)
        png_metadata.add_text('FrameCount', str(frame_count))
        png_metadata.add_text('DelayMs', str(frame_delay_ms))
        png_metadata.add_text('ExtractScale', str(extract_scale))
        if model_used:
            png_metadata.add_text('AIModel', model_used)

        # Save with metadata (uncompressed)
        frame_image.save(str(frame_path), format='PNG', compress_level=0, pnginfo=png_metadata)

        saved_paths.append(str(frame_path))

    return saved_paths


def save_files_locally(  # ruff: ignore[too-many-arguments]
    response: dict[str, Any],
    output_path: str,
    output_formats: list[str],
    *,
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
    saved_files: list[str] = []
    base_output_dir = Path(output_path)
    base_output_dir.mkdir(parents=True, exist_ok=True)

    sprite_name: str = response.get('sprite_name', 'sprite')
    # Sanitize sprite name for directory/filename
    safe_name: str = ''.join(c if c.isalnum() or c in '-_' else '_' for c in sprite_name)
    if not safe_name:
        safe_name = 'sprite'

    # Create a directory for this sprite
    sprite_dir = find_available_directory(base_output_dir / safe_name)
    sprite_dir.mkdir(parents=True, exist_ok=True)
    LOG.info('Created sprite directory: %s', sprite_dir)

    # Save TOML if requested and available
    if 'toml' in output_formats and response.get('toml_content'):
        toml_path = sprite_dir / f'{safe_name}.toml'
        toml_path.write_text(response['toml_content'], encoding='utf-8')
        saved_files.append(str(toml_path))
        LOG.info('Saved TOML: %s', toml_path)

    # Save APNG and extracted frames if animation frames are available
    if response.get('all_frames_png_base64'):
        frames: list[str] = response['all_frames_png_base64']
        rendered_frames: list[dict[str, Any]] = response.get('rendered_frames', [])
        frame_count = len(frames)

        # Calculate frame delay for APNG
        # Use animation_duration if provided, otherwise default to 100ms per frame
        if animation_duration and frame_count > 0:
            frame_delay_ms = int((animation_duration * 1000) / frame_count)
        else:
            frame_delay_ms = 100  # Default: 10 FPS

        # Create and save APNG
        apng_path = sprite_dir / f'{safe_name}.apng'
        apng_path.write_bytes(create_apng_from_frames(frames, frame_delay_ms=frame_delay_ms))
        saved_files.append(str(apng_path))
        LOG.info('Saved APNG: %s (%s frames, %sms/frame)', apng_path, frame_count, frame_delay_ms)

        # Extract and save individual frames with metadata
        extracted_dir = sprite_dir / 'extracted'
        extracted_dir.mkdir(exist_ok=True)

        if rendered_frames:
            # Use rendered_frames for proper animation-#-frame-#.png naming
            frame_entries: list[tuple[str, str, str, str]] = [
                (
                    (
                        f'animation-{info.get("animation_index", 0)}'
                        f'-frame-{info.get("frame_index", 0)}'
                    ),
                    str(info.get('animation_index', 0)),
                    str(info.get('frame_index', 0)),
                    str(info.get('png_base64', '')),
                )
                for info in rendered_frames
            ]
        else:
            # Fallback to old naming if rendered_frames not available
            frame_entries = [
                (f'animation-0-frame-{i}', '0', str(i), frame_base64)
                for i, frame_base64 in enumerate(frames)
            ]

        saved_files.extend(
            _save_extracted_frames(
                frame_entries=frame_entries,
                extracted_dir=extracted_dir,
                frame_count=frame_count,
                frame_delay_ms=frame_delay_ms,
                extract_scale=extract_scale,
                model_used=model_used,
            ),
        )

        LOG.info('Saved %s frames to: %s (scale: %sx)', frame_count, extracted_dir, extract_scale)

    # Save single PNG if requested, available, and no animation frames
    elif 'png' in output_formats and response.get('png_base64'):
        png_path = sprite_dir / f'{safe_name}.png'
        png_bytes = base64.b64decode(response['png_base64'])
        png_path.write_bytes(png_bytes)
        saved_files.append(str(png_path))
        LOG.info('Saved PNG: %s', png_path)

    return saved_files


# What sending a request and reading its response can raise (_exit_code_for_request_error):
# httpx's errors, its InvalidURL (not an HTTPError), an input file that cannot be read,
# ValueError from decoding the response's JSON, and TypeError for JSON that is not an object
# (raised by _response_object)
REQUEST_ERRORS = (httpx.HTTPError, httpx.InvalidURL, OSError, ValueError, TypeError)

# What handling a successful response can raise (_exit_code_for_response_handling_error):
# writing the output (OSError), and a malformed response (ValueError such as binascii.Error from
# bad base64, KeyError for a missing field, TypeError for a field of the wrong type)
RESPONSE_HANDLING_ERRORS = (OSError, ValueError, KeyError, TypeError)

# The HTTP status of a server that is overloaded or down for maintenance: unavailable, not a
# rejection of the request
HTTP_SERVICE_UNAVAILABLE = 503


def _print_traceback_if_verbose(*, parsed_args: argparse.Namespace) -> None:
    """Print the exception being handled when --verbose is given (call from an except block)."""
    if parsed_args.verbose:
        import traceback

        traceback.print_exc()


def _exit_code_for_server_error(
    *, error: Exception, server_url: str, rejected_exit_code: ExitCode
) -> ExitCode | None:
    """Log and return the exit code of an error in reaching the server or in its answer.

    Args:
        error: One of ``REQUEST_ERRORS``.
        server_url: The --server-url given.
        rejected_exit_code: The code for a server that refused this kind of request.

    Returns:
        ``ExitCode.OPTIONS_REFUSED`` for a server URL that is not usable;
        ``ExitCode.SERVICE_UNAVAILABLE`` when the server cannot be reached, stops answering or
        answers 503; ``rejected_exit_code`` for any other error status; None for any other
        error (not about the server's reachability or status).

    """
    if isinstance(error, (httpx.InvalidURL, httpx.UnsupportedProtocol)):
        LOG.error(f'Cannot use the server URL {server_url!r}: {error}')
        return ExitCode.OPTIONS_REFUSED
    if isinstance(error, httpx.ConnectError):
        LOG.error(f'Could not connect to server at {server_url}')
        LOG.error('Is the server running? Start it with: glitchygames-server')
        return ExitCode.SERVICE_UNAVAILABLE
    if isinstance(error, httpx.TransportError):
        LOG.error(f'The server at {server_url} did not answer: {error!r}')
        return ExitCode.SERVICE_UNAVAILABLE
    if isinstance(error, httpx.HTTPStatusError):
        LOG.error(f'HTTP error: {error.response.status_code} - {error.response.text}')
        if error.response.status_code == HTTP_SERVICE_UNAVAILABLE:
            return ExitCode.SERVICE_UNAVAILABLE
        return rejected_exit_code
    return None


def _exit_code_for_request_error(
    *, error: Exception, parsed_args: argparse.Namespace, rejected_exit_code: ExitCode
) -> ExitCode:
    """Log why a request failed and return its exit code (call from an except block).

    Args:
        error: One of ``REQUEST_ERRORS``.
        parsed_args: Parsed command line arguments (``server_url``, ``verbose``).
        rejected_exit_code: The code for a server that refused this kind of request
            (``GENERATION_REJECTED`` or ``EXTRACTION_REJECTED``).

    Returns:
        The server's code (``_exit_code_for_server_error``), else ``ExitCode.MISSING_INPUT``
        for an input file that does not exist, else ``ExitCode.UNUSABLE_INPUT`` (an unreadable
        input file, or a response that cannot be decoded: bad JSON, JSON that is not an object,
        a redirect loop, an undecodable body).

    """
    server_exit_code = _exit_code_for_server_error(
        error=error, server_url=parsed_args.server_url, rejected_exit_code=rejected_exit_code
    )
    if server_exit_code is not None:
        return server_exit_code
    if isinstance(error, FileNotFoundError):
        LOG.error('Input file not found: %s', error.filename or error)
        return ExitCode.MISSING_INPUT
    LOG.error('Error: %s', error)
    _print_traceback_if_verbose(parsed_args=parsed_args)
    return ExitCode.UNUSABLE_INPUT


def _exit_code_for_response_handling_error(
    *, error: Exception, parsed_args: argparse.Namespace
) -> ExitCode:
    """Log why handling a response failed and return its exit code (call from an except block).

    A KeyError or TypeError here is read as a malformed server response (a field missing or of
    the wrong type), not a client bug: the response's shape is the server's to guarantee.

    Args:
        error: One of ``RESPONSE_HANDLING_ERRORS``.
        parsed_args: Parsed command line arguments (``verbose``).

    Returns:
        ``ExitCode.CANNOT_WRITE_OUTPUT`` for a file or directory that cannot be written
        (including a FileNotFoundError while writing), otherwise ``ExitCode.UNUSABLE_INPUT``.

    """
    if isinstance(error, OSError):
        LOG.error('Cannot write the output: %s', error)
        _print_traceback_if_verbose(parsed_args=parsed_args)
        return ExitCode.CANNOT_WRITE_OUTPUT
    LOG.error('The server response is malformed: %r', error)
    _print_traceback_if_verbose(parsed_args=parsed_args)
    return ExitCode.UNUSABLE_INPUT


def _log_extraction_metadata(response: dict[str, Any]) -> None:
    """Log metadata from an APNG extraction response.

    Args:
        response: The extraction response dictionary

    """
    LOG.info(f'Extracted {response.get("frame_count")} frames')
    if response.get('width') and response.get('height'):
        LOG.info(f'  Canvas size: {response.get("width")}x{response.get("height")} pixels')
    if response.get('total_duration_ms'):
        LOG.info(f'  Total duration: {response.get("total_duration_ms")}ms')
    if response.get('loop_count') is not None:
        loops: int | None = response.get('loop_count')
        LOG.info(f'  Loop count: {"infinite" if loops == 0 else loops}')


def _save_apng_extracted_frames(response: dict[str, Any], output_path: str, apng_path: str) -> None:
    """Save extracted APNG frames to the output directory.

    Args:
        response: The extraction response dictionary
        output_path: Directory path to save frames
        apng_path: Original APNG file path (used for naming)

    """
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    apng_name = Path(apng_path).stem
    saved_files: list[str] = []

    for frame_info in response.get('frames', []):
        frame_path = output_dir / f'{apng_name}_frame_{frame_info["index"]:03d}.png'
        frame_bytes = base64.b64decode(frame_info['png_base64'])
        frame_path.write_bytes(frame_bytes)
        saved_files.append(str(frame_path))
        LOG.debug('Saved frame: %s', frame_path)

    LOG.info(f'Saved {len(saved_files)} frames to {output_dir}')


def _process_extraction_response(
    response: dict[str, Any],
    parsed_args: argparse.Namespace,
    apng_path: str,
) -> ExitCode:
    """Process a successful APNG extraction response.

    Args:
        response: The extraction API response
        parsed_args: Parsed command line arguments
        apng_path: Path to the original APNG file

    Returns:
        ``ExitCode.SUCCESS``, or ``ExitCode.EXTRACTION_REJECTED`` when the server says the
        extraction failed.

    """
    if not response.get('success'):
        LOG.error(f'Extraction failed: {response.get("error", "Unknown error")}')
        return ExitCode.EXTRACTION_REJECTED

    _log_extraction_metadata(response)

    if parsed_args.output_path:
        _save_apng_extracted_frames(response, parsed_args.output_path, apng_path)

    # Output JSON to stdout if verbose or no output path
    if parsed_args.verbose or not parsed_args.output_path:
        import json

        # Remove base64 data from output for readability unless verbose
        output_data = response.copy()
        if not parsed_args.verbose:
            for frame in output_data.get('frames', []):
                frame['png_base64'] = f'<{len(frame.get("png_base64", ""))} chars>'
        print(json.dumps(output_data, indent=2))  # ruff: ignore[print]

    return ExitCode.SUCCESS


def _handle_extract_frames(parsed_args: argparse.Namespace) -> ExitCode:
    """Handle the --extract-frames command.

    Args:
        parsed_args: Parsed command line arguments

    Returns:
        The exit code (``ExitCode``; see the module docstring).

    """
    apng_path = parsed_args.extract_frames

    try:
        LOG.info('Extracting frames from: %s', apng_path)
        response = extract_apng_frames(
            server_url=parsed_args.server_url,
            apng_path=apng_path,
        )
    except REQUEST_ERRORS as error:
        return _exit_code_for_request_error(
            error=error,
            parsed_args=parsed_args,
            rejected_exit_code=ExitCode.EXTRACTION_REJECTED,
        )
    try:
        return _process_extraction_response(response, parsed_args, apng_path)
    except RESPONSE_HANDLING_ERRORS as error:
        return _exit_code_for_response_handling_error(error=error, parsed_args=parsed_args)


def _log_generation_results(response: dict[str, Any]) -> None:
    """Log metadata about a successfully generated sprite.

    Args:
        response: The generation API response

    """
    LOG.info(f'Generated sprite: {response.get("sprite_name")}')
    if response.get('is_animated'):
        LOG.info(f'  Animated: {response.get("frame_count")} frames')
    if response.get('width') and response.get('height'):
        LOG.info(f'  Size: {response.get("width")}x{response.get("height")} pixels')

    # Display colorized ASCII preview of the sprite
    if response.get('toml_content'):
        display_sprite_ascii(response['toml_content'])


def _handle_generate_sprite(parsed_args: argparse.Namespace, output_formats: list[str]) -> ExitCode:
    """Handle sprite generation and output.

    Args:
        parsed_args: Parsed command line arguments
        output_formats: List of requested output formats

    Returns:
        The exit code (``ExitCode``; see the module docstring): ``GENERATION_REJECTED`` when
        the server says the generation failed.

    """
    LOG.info(f'Generating sprite: {parsed_args.prompt}')
    if parsed_args.animation_language_model:
        LOG.info(f'Using model: {parsed_args.animation_language_model}')
    try:
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
    except REQUEST_ERRORS as error:
        return _exit_code_for_request_error(
            error=error,
            parsed_args=parsed_args,
            rejected_exit_code=ExitCode.GENERATION_REJECTED,
        )

    if not response.get('success'):
        LOG.error(f'Generation failed: {response.get("error", "Unknown error")}')
        return ExitCode.GENERATION_REJECTED

    try:
        _output_generated_sprite(
            response=response, parsed_args=parsed_args, output_formats=output_formats
        )
    except RESPONSE_HANDLING_ERRORS as error:
        return _exit_code_for_response_handling_error(error=error, parsed_args=parsed_args)
    return ExitCode.SUCCESS


def _output_generated_sprite(
    *, response: dict[str, Any], parsed_args: argparse.Namespace, output_formats: list[str]
) -> None:
    """Log a generated sprite, save its files (with --output-path) or print its TOML.

    Args:
        response: The successful generation response.
        parsed_args: Parsed command line arguments.
        output_formats: The requested output formats.

    """
    _log_generation_results(response)

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
            LOG.info('Saved files:')
            for filepath in saved_files:
                LOG.info('  %s', filepath)

    # Output TOML to stdout if no output path specified
    if not parsed_args.output_path and 'toml' in output_formats and response.get('toml_content'):
        if not parsed_args.quiet:
            print('\n--- TOML Content ---')  # ruff: ignore[print]
        print(response['toml_content'])  # ruff: ignore[print]


def main(args: list[str] | None = None) -> int:
    """Run the CLI client.

    Args:
        args: Command line arguments (defaults to sys.argv[1:])

    Returns:
        The exit code (``ExitCode``; see the module docstring). A usage error exits through
        argparse instead (SystemExit with ``ExitCode.ARGUMENT_PARSER_ERROR``).

    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # Set up logging
    if parsed_args.verbose:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    elif parsed_args.quiet:
        logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(message)s')

    # Validate that prompt is provided for generation
    if not parsed_args.extract_frames and not parsed_args.prompt:
        parser.error('prompt is required unless using --extract-frames')

    try:
        if parsed_args.extract_frames:
            exit_code = _handle_extract_frames(parsed_args)
        else:
            # Use default output formats if none specified
            output_formats = parsed_args.output_formats or DEFAULT_OUTPUT_FORMATS
            exit_code = _handle_generate_sprite(parsed_args, output_formats)
    except Exception:
        # The handlers map every error they expect, so anything else is a client bug
        LOG.exception('Unexpected error in the sprite client')
        exit_code = ExitCode.INTERNAL_ERROR
    LOG.info(f'Exiting with {ExitCode(exit_code).describe()}')
    return ExitCode(exit_code)


def run() -> None:
    """Entry point for the CLI client."""
    sys.exit(main())


if __name__ == '__main__':
    run()
