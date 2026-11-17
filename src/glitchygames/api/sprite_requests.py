"""The sprite requests: what the sprite routes and ``glitchygames-client`` both do.

plans/2026-11-16-console-sprite-generation.md, part 1: one code path, so the server and the
client never drift. The routes (``api/routes/sprites.py``) call these and map their errors to
HTTP statuses; the client (``api/client.py``) calls them in its own process, with no server,
and maps the same errors to exit codes.

Rules:

1. Generation and refinement go through ``SpriteGenerationService``, which talks to the local AI
   service; its ``AIProviderError`` is passed on (the route's 503, the client's
   ``SERVICE_UNAVAILABLE``).
2. A response is unsuccessful, never an exception, when the service failed, or when PNG was the
   only format asked for and rendering it failed.
3. Files are saved only on request (``output_path``) and only under ``ALLOWED_OUTPUT_ROOT``; an
   absolute path or one that leaves the root raises ``SpriteRequestRefusedError`` (the route's
   400).
4. Frames come from an APNG (``extract_frames_response``) or a ``.toml`` sprite
   (``extract_toml_frames_response``) in one response shape, so they are saved the same way. Bad
   input is an unsuccessful response, never an exception. A ``.toml`` sprite is read by the
   sprite loader alone (through the renderer), and each frame's delay is the duration the loader
   gave it (its ``frame_interval``, else its animation's, else the loader's default).
"""

from __future__ import annotations

import base64
import io
import logging
import struct
from pathlib import Path
from typing import TYPE_CHECKING

from glitchygames.api.models import (
    OUTPUT_FORMAT_PNG,
    OUTPUT_FORMAT_TOML,
    ApngExtractResponse,
    ApngFrameInfo,
    RenderedFrameInfo,
    SpriteGenerationRequest,
    SpriteGenerationResponse,
    SpriteRefinementRequest,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    import apng as apng_types

    from glitchygames.services import RendererService, SpriteGenerationService
    from glitchygames.services.sprite_generation_service import GenerationResult

LOG = logging.getLogger('glitchygames.api.sprite_requests')

PNG_IHDR_MINIMUM_BYTES = 24
# The eight bytes every PNG (and so every APNG) starts with (PNG specification, section 5.2)
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
MILLISECONDS_PER_SECOND = 1000

# Base directory under which all sprite files will be saved.
# All requested output paths are resolved relative to this directory.
ALLOWED_OUTPUT_ROOT = (Path.cwd() / 'sprite_outputs').resolve()


class SpriteRequestRefusedError(ValueError):
    """A request asked for something refused before any work: an output path off the root."""


def generate_response(
    request: SpriteGenerationRequest,
    *,
    generation_service: SpriteGenerationService,
    renderer_service: RendererService,
) -> SpriteGenerationResponse:
    """Generate a sprite from a description and build its response (rules 1 to 3).

    Args:
        request: What to generate, in which formats, and where to save it (if anywhere).
        generation_service: The sprite service (talks to the local AI service).
        renderer_service: The renderer, for PNG output.

    Returns:
        The response.
    """
    LOG.info('Generating sprite from prompt: %s...', request.prompt[:50])
    if request.model:
        LOG.info('Using model override: %s', request.model)
    result = generation_service.generate_sprite(
        prompt=request.prompt,
        width=request.width,
        height=request.height,
        frame_count=request.frame_count,
        film_strip_count=request.film_strip_count,
        animation_duration=request.animation_duration,
        model=request.model,
    )
    return _response_for_result(
        result=result,
        request=request,
        renderer_service=renderer_service,
        failure_label='Generation',
    )


def refine_response(
    request: SpriteRefinementRequest,
    *,
    generation_service: SpriteGenerationService,
    renderer_service: RendererService,
) -> SpriteGenerationResponse:
    """Refine an existing sprite from instructions and build its response (rules 1 to 3).

    Args:
        request: The instructions, the current sprite's TOML, formats and output path.
        generation_service: The sprite service (talks to the local AI service).
        renderer_service: The renderer, for PNG output.

    Returns:
        The response.
    """
    LOG.info('Refining sprite with prompt: %s...', request.prompt[:50])
    result = generation_service.refine_sprite(
        prompt=request.prompt, current_toml=request.current_toml
    )
    return _response_for_result(
        result=result,
        request=request,
        renderer_service=renderer_service,
        failure_label='Refinement',
    )


def save_sprite_files(  # ruff: ignore[too-many-arguments]
    output_path: str,
    sprite_name: str,
    *,
    toml_content: str | None,
    png_bytes: bytes | None,
    rendered_frames: list[RenderedFrameInfo] | None,
    output_format: Sequence[str],
) -> list[str]:
    """Save sprite files under ``ALLOWED_OUTPUT_ROOT`` (rule 3).

    Args:
        output_path: Directory to save files to, relative to the root (created if missing).
        sprite_name: Name of the sprite (used for filenames).
        toml_content: TOML content to save (if any).
        png_bytes: PNG bytes to save (if any).
        rendered_frames: The rendered frames with their animation and frame indices.
        output_format: The requested output formats.

    Returns:
        The saved files' paths.

    Raises:
        SpriteRequestRefusedError: If the output path is absolute or resolves outside the root.
    """
    saved_files: list[str] = []
    requested_path = Path(output_path)
    if requested_path.is_absolute():
        message = 'Absolute output paths are not allowed.'
        raise SpriteRequestRefusedError(message)
    save_dir = (ALLOWED_OUTPUT_ROOT / requested_path).resolve()
    if save_dir != ALLOWED_OUTPUT_ROOT and ALLOWED_OUTPUT_ROOT not in save_dir.parents:
        message = 'Invalid output path.'
        raise SpriteRequestRefusedError(message)

    save_dir.mkdir(parents=True, exist_ok=True)
    LOG.info('Saving sprite files to: %s', save_dir)

    # Sanitize sprite name for filename
    safe_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in sprite_name)
    if not safe_name:
        safe_name = 'sprite'

    if OUTPUT_FORMAT_TOML in output_format and toml_content:
        toml_path = save_dir / f'{safe_name}.toml'
        toml_path.write_text(toml_content, encoding='utf-8')
        saved_files.append(str(toml_path))
        LOG.info('Saved TOML: %s', toml_path)

    if OUTPUT_FORMAT_PNG in output_format and png_bytes:
        png_path = save_dir / f'{safe_name}.png'
        png_path.write_bytes(png_bytes)
        saved_files.append(str(png_path))
        LOG.info('Saved PNG: %s', png_path)

    # Animation frames (animation-#-frame-#.png naming)
    if rendered_frames:
        for frame_info in rendered_frames:
            frame_bytes = base64.b64decode(frame_info.png_base64)
            frame_path = save_dir / (
                f'animation-{frame_info.animation_index}-frame-{frame_info.frame_index}.png'
            )
            frame_path.write_bytes(frame_bytes)
            saved_files.append(str(frame_path))
            LOG.info('Saved frame: %s', frame_path)

    return saved_files


def _render_png_to_response(
    renderer_service: RendererService,
    response: SpriteGenerationResponse,
    toml_content: str,
    *,
    png_scale: int,
    frame_count: int,
) -> bytes | None:
    """Render PNG frames and populate the response object.

    Args:
        renderer_service: The renderer service instance.
        response: The response object to populate.
        toml_content: TOML content to render.
        png_scale: Scale factor for PNG output.
        frame_count: Number of frames (>1 triggers multi-frame rendering).

    Returns:
        Raw PNG bytes for the first frame, or None if rendering failed.
    """
    render_all_frames = frame_count > 1
    render_result = renderer_service.render_from_toml(
        toml_content, scale=png_scale, render_all_frames=render_all_frames
    )
    if not render_result.success:
        LOG.warning('PNG rendering failed: %s', render_result.error)
        return None

    response.png_base64 = render_result.png_base64
    response.width = render_result.width
    response.height = render_result.height

    if render_all_frames and render_result.all_frames_png_base64:
        response.all_frames_png_base64 = render_result.all_frames_png_base64
        response.rendered_frames = [
            RenderedFrameInfo(
                animation_index=rendered.animation_index,
                frame_index=rendered.frame_index,
                png_base64=rendered.png_base64,
            )
            for rendered in render_result.rendered_frames
        ]

    return render_result.png_bytes


def _response_for_result(
    *,
    result: GenerationResult,
    request: SpriteGenerationRequest | SpriteRefinementRequest,
    renderer_service: RendererService,
    failure_label: str,
) -> SpriteGenerationResponse:
    """Build a generation or refinement response: TOML, PNG and saved files as requested.

    Args:
        result: The generation service's result.
        request: The request, for its output format, PNG scale and output path.
        renderer_service: The renderer service instance.
        failure_label: What failed, for the log ('Generation' or 'Refinement').

    Returns:
        The response; unsuccessful when the service failed, or when PNG was the only requested
        format and rendering it failed (rule 2).
    """
    if not result.success:
        LOG.warning('%s failed: %s', failure_label, result.error)
        return SpriteGenerationResponse(success=False, error=result.error)

    response = SpriteGenerationResponse(
        success=True,
        sprite_name=result.sprite_name,
        is_animated=result.is_animated,
        frame_count=result.frame_count,
    )

    if OUTPUT_FORMAT_TOML in request.output_format:
        response.toml_content = result.toml_content

    png_bytes = None
    if OUTPUT_FORMAT_PNG in request.output_format and result.toml_content:
        png_bytes = _render_png_to_response(
            renderer_service,
            response,
            result.toml_content,
            png_scale=request.png_scale,
            frame_count=result.frame_count,
        )
        # Only fail if PNG was the only requested format and rendering failed
        if png_bytes is None and request.output_format == [OUTPUT_FORMAT_PNG]:
            return SpriteGenerationResponse(success=False, error='PNG rendering failed')

    if request.output_path and result.sprite_name:
        response.saved_files = save_sprite_files(
            output_path=request.output_path,
            sprite_name=result.sprite_name,
            toml_content=response.toml_content,
            png_bytes=png_bytes,
            rendered_frames=response.rendered_frames,
            output_format=request.output_format,
        )
    return response


# --- Frames (rule 4) ---


def extract_single_frame(
    png: apng_types.PNG,
    control: apng_types.FrameControl | None,
    index: int,
) -> tuple[ApngFrameInfo, int]:
    """Extract a single frame and its metadata from an APNG frame pair.

    Args:
        png: The PNG frame object.
        control: The APNG control chunk (may be None).
        index: Frame index.

    Returns:
        Tuple of (ApngFrameInfo, delay_ms).
    """
    frame_buffer = io.BytesIO()
    png.save(frame_buffer)
    frame_bytes = frame_buffer.getvalue()
    frame_base64 = base64.b64encode(frame_bytes).decode('utf-8')

    # APNG stores delay as delay_num/delay_den seconds
    if control is not None:
        delay_num: int = control.delay
        delay_den: int = control.delay_den
        if delay_den == 0:
            delay_den = 1000
        delay_ms: int = int((delay_num / delay_den) * 1000)
        frame_width: int = control.width or 0
        frame_height: int = control.height or 0
        x_offset: int = control.x_offset
        y_offset: int = control.y_offset
    else:
        delay_ms = 100
        frame_width = 0
        frame_height = 0
        x_offset = 0
        y_offset = 0

    if frame_width == 0 or frame_height == 0:
        frame_width, frame_height = extract_png_dimensions(frame_bytes, frame_width, frame_height)

    frame_info = ApngFrameInfo(
        index=index,
        png_base64=frame_base64,
        delay_ms=delay_ms,
        width=frame_width,
        height=frame_height,
        x_offset=x_offset,
        y_offset=y_offset,
        animation_index=0,
        animation_frame_index=index,
    )
    return frame_info, delay_ms


def extract_png_dimensions(
    frame_bytes: bytes, default_width: int, default_height: int
) -> tuple[int, int]:
    """Extract width and height from PNG IHDR chunk bytes.

    Args:
        frame_bytes: Raw PNG file bytes.
        default_width: Default width if extraction fails.
        default_height: Default height if extraction fails.

    Returns:
        Tuple of (width, height).
    """
    # PNG dimensions are in the IHDR chunk at bytes 16-24; with at least 24 bytes each
    # slice holds exactly the 4 bytes '>I' unpacks, so unpacking cannot fail
    if len(frame_bytes) >= PNG_IHDR_MINIMUM_BYTES:
        width = struct.unpack('>I', frame_bytes[16:20])[0]
        height = struct.unpack('>I', frame_bytes[20:24])[0]
        return width, height
    return default_width, default_height


def extract_frames_response(*, apng_base64: str) -> ApngExtractResponse:
    """Decode an APNG and extract its frames and metadata (rule 4).

    Args:
        apng_base64: The base64-encoded APNG data.

    Returns:
        The extracted frames and metadata, or an unsuccessful response for bad base64 or APNG
        data.
    """
    from apng import APNG

    try:
        apng_bytes = base64.b64decode(apng_base64)
    except (ValueError, TypeError) as e:
        LOG.warning('Failed to decode base64: %s', e)
        return ApngExtractResponse(success=False, error=f'Invalid base64 data: {e}')

    # The apng package does not check the PNG signature: it parses arbitrary bytes as an APNG
    # with no frames, which used to come back as a success (BUGS.md #137)
    if not apng_bytes.startswith(PNG_SIGNATURE):
        LOG.warning('Refused APNG data without the PNG signature')
        return ApngExtractResponse(
            success=False,
            error='Invalid APNG file: the data does not start with the PNG signature',
        )

    # The apng package reads chunk headers with struct, so data cut off inside one raises
    # struct.error (not a ValueError subclass)
    try:
        apng: APNG = APNG.from_bytes(apng_bytes)
    except (ValueError, OSError, struct.error) as e:
        LOG.warning('Failed to parse APNG: %s', e)
        return ApngExtractResponse(success=False, error=f'Invalid APNG file: {e}')

    # A PNG signature followed by no image data parses as an APNG with no frames (BUGS.md #137)
    if not apng.frames:
        LOG.warning('Refused APNG data with no frames')
        return ApngExtractResponse(success=False, error='Invalid APNG file: it has no frames')

    frames_info: list[ApngFrameInfo] = []
    total_duration_ms: int = 0
    canvas_width: int | None = None
    canvas_height: int | None = None
    for index, (png, control) in enumerate(apng.frames):
        frame_info, delay_ms = extract_single_frame(png, control, index)
        if canvas_width is None:
            canvas_width = frame_info.width
            canvas_height = frame_info.height
        total_duration_ms += delay_ms
        frames_info.append(frame_info)

    loop_count = apng.num_plays if hasattr(apng, 'num_plays') else 0
    LOG.info(
        'Extracted %s frames from APNG (%sx%s, %sms total)',
        len(frames_info),
        canvas_width,
        canvas_height,
        total_duration_ms,
    )
    return ApngExtractResponse(
        success=True,
        frame_count=len(frames_info),
        width=canvas_width,
        height=canvas_height,
        loop_count=loop_count,
        total_duration_ms=total_duration_ms,
        frames=frames_info,
    )


def extract_toml_frames_response(
    *, toml_content: str, renderer_service: RendererService
) -> ApngExtractResponse:
    """Render every frame of a ``.toml`` sprite, in an APNG's response shape (rule 4).

    The sprite loader is the only reader of the file: the renderer loads it and reports each
    frame with the duration the loader gave it, so nothing here parses the TOML a second way.

    Args:
        toml_content: The sprite file's text.
        renderer_service: The renderer.

    Returns:
        Each frame with its animation, its place in it and its delay; or an unsuccessful
        response for text that is not a sprite (including a ``frame_interval`` that is not a
        number).
    """
    render_result = renderer_service.render_from_toml(toml_content, render_all_frames=True)
    if not render_result.success or not render_result.rendered_frames:
        LOG.warning('Refused a .toml that does not render: %s', render_result.error)
        return ApngExtractResponse(
            success=False, error=f'Invalid sprite file: {render_result.error or "no frames"}'
        )
    width, height = render_result.width, render_result.height
    frames: list[ApngFrameInfo] = []
    for index, rendered in enumerate(render_result.rendered_frames):
        delay_ms = _delay_ms(duration_seconds=rendered.duration_seconds)
        if delay_ms is None:
            message = (
                f'Invalid sprite file: frame {rendered.frame_index} of animation '
                f'{rendered.animation_index} has a frame_interval that is not a number '
                f'({rendered.duration_seconds!r})'
            )
            LOG.warning('Refused a .toml sprite: %s', message)
            return ApngExtractResponse(success=False, error=message)
        frames.append(
            ApngFrameInfo(
                index=index,
                png_base64=rendered.png_base64,
                delay_ms=delay_ms,
                width=width,
                height=height,
                animation_index=rendered.animation_index,
                animation_frame_index=rendered.frame_index,
            )
        )
    return ApngExtractResponse(
        success=True,
        frame_count=len(frames),
        width=width,
        height=height,
        loop_count=0,
        total_duration_ms=sum(frame.delay_ms for frame in frames),
        frames=frames,
    )


def _delay_ms(*, duration_seconds: object) -> int | None:
    """A frame's duration in whole milliseconds, or None when it is not a number.

    The loader keeps a sprite file's ``frame_interval`` as written, so text there arrives as
    text.

    Returns:
        The delay, or None.
    """
    if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, int | float):
        return None
    return round(duration_seconds * MILLISECONDS_PER_SECOND)
