"""Sprite generation endpoints for the GlitchyGames API."""

import base64
import io
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from glitchygames.api.models import (
    OUTPUT_FORMAT_PNG,
    OUTPUT_FORMAT_TOML,
    ApngExtractRequest,
    ApngExtractResponse,
    ApngFrameInfo,
    RenderedFrameInfo,
    SpriteGenerationRequest,
    SpriteGenerationResponse,
    SpriteRefinementRequest,
)
from glitchygames.services import (
    AIProviderError,
    RendererService,
    ServiceConfig,
    SpriteGenerationService,
)

LOG = logging.getLogger('glitchygames.api.sprites')

PNG_IHDR_MINIMUM_BYTES = 24

router = APIRouter(prefix='/sprites', tags=['sprites'])


def _get_services() -> tuple[SpriteGenerationService, RendererService]:
    """Get service instances.

    Returns:
        Tuple of (SpriteGenerationService, RendererService)

    """
    config = ServiceConfig.from_env()
    return SpriteGenerationService(config), RendererService(config)


def _save_sprite_files(
    output_path: str,
    sprite_name: str,
    toml_content: str | None,
    png_bytes: bytes | None,
    rendered_frames: list[RenderedFrameInfo] | None,
    output_format: list[str],
) -> list[str]:
    """Save sprite files to the specified directory.

    Args:
        output_path: Directory to save files to (created if doesn't exist)
        sprite_name: Name of the sprite (used for filenames)
        toml_content: TOML content to save (if any)
        png_bytes: PNG bytes to save (if any)
        rendered_frames: List of RenderedFrameInfo with animation/frame indices
        output_format: List of requested output formats

    Returns:
        List of saved file paths

    """
    saved_files = []

    # Create directory if it doesn't exist
    save_dir = Path(output_path)
    save_dir.mkdir(parents=True, exist_ok=True)
    LOG.info(f'Saving sprite files to: {save_dir}')

    # Sanitize sprite name for filename
    safe_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in sprite_name)
    if not safe_name:
        safe_name = 'sprite'

    # Save TOML if requested
    if OUTPUT_FORMAT_TOML in output_format and toml_content:
        toml_path = save_dir / f'{safe_name}.toml'
        toml_path.write_text(toml_content, encoding='utf-8')
        saved_files.append(str(toml_path))
        LOG.info(f'Saved TOML: {toml_path}')

    # Save PNG if requested
    if OUTPUT_FORMAT_PNG in output_format and png_bytes:
        png_path = save_dir / f'{safe_name}.png'
        png_path.write_bytes(png_bytes)
        saved_files.append(str(png_path))
        LOG.info(f'Saved PNG: {png_path}')

    # Save animation frames if provided (using animation-#-frame-#.png naming)
    if rendered_frames:
        for frame_info in rendered_frames:
            frame_bytes = base64.b64decode(frame_info.png_base64)
            frame_path = save_dir / (
                f'animation-{frame_info.animation_index}-frame-{frame_info.frame_index}.png'
            )
            frame_path.write_bytes(frame_bytes)
            saved_files.append(str(frame_path))
            LOG.info(f'Saved frame: {frame_path}')

    return saved_files


@router.post('/generate')
async def generate_sprite(request: SpriteGenerationRequest) -> SpriteGenerationResponse:
    """Generate a new sprite from a text prompt.

    This endpoint uses AI to generate a sprite based on the provided text
    description. The sprite can be returned as TOML, PNG, or both.

    Args:
        request: Sprite generation request with prompt and options

    Returns:
        Generated sprite data in the requested format

    Raises:
        HTTPException: If AI provider is unavailable (503) or other errors (500)

    """
    generation_service, renderer_service = _get_services()

    try:
        # Generate the sprite
        LOG.info(f'Generating sprite from prompt: {request.prompt[:50]}...')
        if request.model:
            LOG.info(f'Using model override: {request.model}')
        result = generation_service.generate_sprite(
            prompt=request.prompt,
            width=request.width,
            height=request.height,
            frame_count=request.frame_count,
            film_strip_count=request.film_strip_count,
            animation_duration=request.animation_duration,
            model=request.model,
        )

        if not result.success:
            LOG.warning(f'Generation failed: {result.error}')
            return SpriteGenerationResponse(
                success=False,
                error=result.error,
            )

        # Prepare response based on output format
        response = SpriteGenerationResponse(
            success=True,
            sprite_name=result.sprite_name,
            is_animated=result.is_animated,
            frame_count=result.frame_count,
        )

        # Include TOML if requested
        if OUTPUT_FORMAT_TOML in request.output_format:
            response.toml_content = result.toml_content

        # Render PNG if requested
        png_bytes = None
        if OUTPUT_FORMAT_PNG in request.output_format and result.toml_content:
            # Auto-render all frames if frame_count > 1
            render_all_frames = result.frame_count > 1
            render_result = renderer_service.render_from_toml(
                result.toml_content,
                scale=request.png_scale,
                render_all_frames=render_all_frames,
            )
            if render_result.success:
                response.png_base64 = render_result.png_base64
                response.width = render_result.width
                response.height = render_result.height
                png_bytes = render_result.png_bytes
                if render_all_frames and render_result.all_frames_png_base64:
                    response.all_frames_png_base64 = render_result.all_frames_png_base64
                    # Convert rendered_frames to API model
                    response.rendered_frames = [
                        RenderedFrameInfo(
                            animation_index=rf.animation_index,
                            frame_index=rf.frame_index,
                            png_base64=rf.png_base64,
                        )
                        for rf in render_result.rendered_frames
                    ]
            else:
                LOG.warning(f'PNG rendering failed: {render_result.error}')
                # Only fail if PNG was the only requested format
                if request.output_format == [OUTPUT_FORMAT_PNG]:
                    return SpriteGenerationResponse(
                        success=False,
                        error=f'PNG rendering failed: {render_result.error}',
                    )

        # Save files if output_path is specified
        if request.output_path and result.sprite_name:
            saved_files = _save_sprite_files(
                output_path=request.output_path,
                sprite_name=result.sprite_name,
                toml_content=response.toml_content,
                png_bytes=png_bytes,
                rendered_frames=response.rendered_frames,
                output_format=request.output_format,
            )
            response.saved_files = saved_files

        return response

    except AIProviderError as e:
        LOG.exception('AI provider error')
        raise HTTPException(
            status_code=503,
            detail=f'AI provider unavailable: {e}',
        ) from e
    except Exception as e:
        LOG.exception('Unexpected error')
        raise HTTPException(
            status_code=500,
            detail=f'Internal server error: {e}',
        ) from e


@router.post('/refine')
async def refine_sprite(request: SpriteRefinementRequest) -> SpriteGenerationResponse:
    """Refine an existing sprite based on a text prompt.

    This endpoint uses AI to modify an existing sprite based on the provided
    instructions. The original sprite is provided as TOML content.

    Args:
        request: Sprite refinement request with prompt, current TOML, and options

    Returns:
        Refined sprite data in the requested format

    Raises:
        HTTPException: If AI provider is unavailable (503) or other errors (500)

    """
    generation_service, renderer_service = _get_services()

    try:
        # Refine the sprite
        LOG.info(f'Refining sprite with prompt: {request.prompt[:50]}...')
        result = generation_service.refine_sprite(
            prompt=request.prompt,
            current_toml=request.current_toml,
        )

        if not result.success:
            LOG.warning(f'Refinement failed: {result.error}')
            return SpriteGenerationResponse(
                success=False,
                error=result.error,
            )

        # Prepare response based on output format
        response = SpriteGenerationResponse(
            success=True,
            sprite_name=result.sprite_name,
            is_animated=result.is_animated,
            frame_count=result.frame_count,
        )

        # Include TOML if requested
        if OUTPUT_FORMAT_TOML in request.output_format:
            response.toml_content = result.toml_content

        # Render PNG if requested
        png_bytes = None
        if OUTPUT_FORMAT_PNG in request.output_format and result.toml_content:
            # Auto-render all frames if frame_count > 1
            render_all_frames = result.frame_count > 1
            render_result = renderer_service.render_from_toml(
                result.toml_content,
                scale=request.png_scale,
                render_all_frames=render_all_frames,
            )
            if render_result.success:
                response.png_base64 = render_result.png_base64
                response.width = render_result.width
                response.height = render_result.height
                png_bytes = render_result.png_bytes
                if render_all_frames and render_result.all_frames_png_base64:
                    response.all_frames_png_base64 = render_result.all_frames_png_base64
                    # Convert rendered_frames to API model
                    response.rendered_frames = [
                        RenderedFrameInfo(
                            animation_index=rf.animation_index,
                            frame_index=rf.frame_index,
                            png_base64=rf.png_base64,
                        )
                        for rf in render_result.rendered_frames
                    ]
            else:
                LOG.warning(f'PNG rendering failed: {render_result.error}')
                # Only fail if PNG was the only requested format
                if request.output_format == [OUTPUT_FORMAT_PNG]:
                    return SpriteGenerationResponse(
                        success=False,
                        error=f'PNG rendering failed: {render_result.error}',
                    )

        # Save files if output_path is specified
        if request.output_path and result.sprite_name:
            saved_files = _save_sprite_files(
                output_path=request.output_path,
                sprite_name=result.sprite_name,
                toml_content=response.toml_content,
                png_bytes=png_bytes,
                rendered_frames=response.rendered_frames,
                output_format=request.output_format,
            )
            response.saved_files = saved_files

        return response

    except AIProviderError as e:
        LOG.exception('AI provider error')
        raise HTTPException(
            status_code=503,
            detail=f'AI provider unavailable: {e}',
        ) from e
    except Exception as e:
        LOG.exception('Unexpected error')
        raise HTTPException(
            status_code=500,
            detail=f'Internal server error: {e}',
        ) from e


def _extract_single_frame(
    png: object, control: object, index: int
) -> tuple[ApngFrameInfo, int]:
    """Extract a single frame and its metadata from an APNG frame pair.

    Args:
        png: The PNG frame object
        control: The APNG control chunk (may be None)
        index: Frame index

    Returns:
        Tuple of (ApngFrameInfo, delay_ms)

    """
    # Get PNG bytes for this frame (uncompressed)
    frame_buffer = io.BytesIO()
    png.save(frame_buffer)
    frame_bytes = frame_buffer.getvalue()
    frame_base64 = base64.b64encode(frame_bytes).decode('utf-8')

    # Calculate frame delay in milliseconds
    # APNG stores delay as delay_num/delay_den seconds
    if control is not None:
        delay_num = control.delay if hasattr(control, 'delay') else 100
        delay_den = control.delay_den if hasattr(control, 'delay_den') else 1000
        if delay_den == 0:
            delay_den = 1000
        delay_ms = int((delay_num / delay_den) * 1000)

        # Get frame dimensions and offsets
        frame_width = control.width if hasattr(control, 'width') else 0
        frame_height = control.height if hasattr(control, 'height') else 0
        x_offset = control.x_offset if hasattr(control, 'x_offset') else 0
        y_offset = control.y_offset if hasattr(control, 'y_offset') else 0
    else:
        # Default values if no control chunk
        delay_ms = 100
        frame_width = 0
        frame_height = 0
        x_offset = 0
        y_offset = 0

    # Try to get dimensions from PNG if not in control chunk
    if frame_width == 0 or frame_height == 0:
        frame_width, frame_height = _extract_png_dimensions(frame_bytes, frame_width, frame_height)

    frame_info = ApngFrameInfo(
        index=index,
        png_base64=frame_base64,
        delay_ms=delay_ms,
        width=frame_width,
        height=frame_height,
        x_offset=x_offset,
        y_offset=y_offset,
    )
    return frame_info, delay_ms


def _extract_png_dimensions(
    frame_bytes: bytes, default_width: int, default_height: int
) -> tuple[int, int]:
    """Extract width and height from PNG IHDR chunk bytes.

    Args:
        frame_bytes: Raw PNG file bytes
        default_width: Default width if extraction fails
        default_height: Default height if extraction fails

    Returns:
        Tuple of (width, height)

    """
    try:
        import struct

        # PNG dimensions are in the IHDR chunk at bytes 16-24
        if len(frame_bytes) >= PNG_IHDR_MINIMUM_BYTES:
            width = struct.unpack('>I', frame_bytes[16:20])[0]
            height = struct.unpack('>I', frame_bytes[20:24])[0]
            return width, height
    except (struct.error, IndexError, ValueError) as dimension_error:
        LOG.debug('Could not extract PNG dimensions: %s', dimension_error)
    return default_width, default_height


@router.post('/extract-frames')
async def extract_apng_frames(request: ApngExtractRequest) -> ApngExtractResponse:
    """Extract individual frames and metadata from an APNG file.

    This endpoint decodes an APNG (Animated PNG) file and returns each frame
    as a separate PNG along with timing and metadata information.

    Args:
        request: APNG extraction request with base64-encoded APNG data

    Returns:
        Extracted frames and metadata

    Raises:
        HTTPException: If APNG parsing fails (400) or other errors (500)

    """
    try:
        from apng import APNG

        # Decode the base64 APNG data
        try:
            apng_bytes = base64.b64decode(request.apng_base64)
        except (ValueError, TypeError) as e:
            LOG.warning(f'Failed to decode base64: {e}')
            return ApngExtractResponse(
                success=False,
                error=f'Invalid base64 data: {e}',
            )

        # Parse the APNG
        try:
            apng = APNG.from_bytes(apng_bytes)
        except (ValueError, OSError) as e:
            LOG.warning(f'Failed to parse APNG: {e}')
            return ApngExtractResponse(
                success=False,
                error=f'Invalid APNG file: {e}',
            )

        # Extract frames and metadata
        frames_info = []
        total_duration_ms = 0
        canvas_width = None
        canvas_height = None

        for index, (png, control) in enumerate(apng.frames):
            frame_info, delay_ms = _extract_single_frame(png, control, index)

            # Track canvas size (first frame usually defines it)
            if canvas_width is None:
                canvas_width = frame_info.width
                canvas_height = frame_info.height

            total_duration_ms += delay_ms
            frames_info.append(frame_info)

        # Get loop count from APNG
        loop_count = apng.num_plays if hasattr(apng, 'num_plays') else 0

        LOG.info(
            f'Extracted {len(frames_info)} frames from APNG '
            f'({canvas_width}x{canvas_height}, {total_duration_ms}ms total)'
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

    except Exception as e:
        LOG.exception('Unexpected error extracting APNG frames')
        raise HTTPException(
            status_code=500,
            detail=f'Internal server error: {e}',
        ) from e
