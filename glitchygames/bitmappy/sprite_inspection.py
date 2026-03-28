"""Sprite inspection and AI training data loading for the Bitmappy editor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from glitchygames.color import MAX_COLOR_CHANNEL_VALUE, MAX_PER_PIXEL_ALPHA, RGBA_COMPONENT_COUNT
from glitchygames.sprites import SpriteFactory
from glitchygames.sprites.animated import AnimatedSprite

from .alpha import convert_sprite_to_alpha_format, parse_toml_sprite_data
from .constants import LOG, ai_training_state
from .pixel_ops import render_frame_to_ascii, render_frames_side_by_side
from .utils import SPRITE_CONFIG_DIR

if TYPE_CHECKING:
    from pathlib import Path

    from glitchygames.sprites import BitmappySprite
    from glitchygames.tools.ascii_renderer import ASCIIRenderer


def _sprite_has_per_pixel_alpha(sprite: AnimatedSprite | object) -> bool:
    """Check if an animated sprite has any non-opaque alpha pixels.

    Args:
        sprite: An AnimatedSprite object with _animations attribute.

    Returns:
        True if any pixel has alpha != 255.

    """
    if not hasattr(sprite, '_animations'):
        return False

    for frames in sprite._animations.values():  # type: ignore[union-attr] # ty: ignore[unresolved-attribute]
        for frame in frames:  # type: ignore[reportUnknownVariableType]
            for pixel in frame.get_pixel_data():  # type: ignore[reportUnknownMemberType]
                if len(pixel) == RGBA_COMPONENT_COUNT and pixel[3] != MAX_COLOR_CHANNEL_VALUE:  # type: ignore[reportUnknownArgumentType]
                    return True
    return False


def _pixels_have_alpha(pixels: list[tuple[int, ...]]) -> bool:
    """Check if any pixels in a list have non-opaque alpha.

    Args:
        pixels: List of pixel tuples (RGB or RGBA).

    Returns:
        True if any pixel has alpha != 255.

    """
    for pixel in pixels:
        if len(pixel) == RGBA_COMPONENT_COUNT and pixel[3] != MAX_COLOR_CHANNEL_VALUE:
            return True
    return False


def _render_static_sprite_ascii(
    sprite: AnimatedSprite | BitmappySprite,
    renderer: ASCIIRenderer,
) -> None:
    """Render ASCII output for a single-frame (static) sprite.

    Args:
        sprite: An AnimatedSprite with _animations.
        renderer: The ASCII renderer to use.

    """
    try:
        first_anim = next(iter(sprite._animations.values()))  # type: ignore[union-attr] # ty: ignore[unresolved-attribute]
        first_frame = first_anim[0] if first_anim else None
        if first_frame:
            ascii_output = render_frame_to_ascii(first_frame, renderer)
            if ascii_output:
                LOG.info(ascii_output)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as e:
        LOG.debug(f'Failed to render ASCII for single-frame sprite: {e}')


def _render_animated_sprite_ascii(
    sprite: AnimatedSprite | BitmappySprite,
    renderer: ASCIIRenderer,
) -> None:
    """Render ASCII output for all animation frames side-by-side.

    Args:
        sprite: An AnimatedSprite with _animations.
        renderer: The ASCII renderer to use.

    """
    try:
        for anim_name, frames in sprite._animations.items():  # type: ignore[union-attr] # ty: ignore[unresolved-attribute]
            if frames:
                LOG.info('  Animation: "%s" (%d frames)', anim_name, len(frames))  # type: ignore[arg-type]
                ascii_output = render_frames_side_by_side(frames, renderer)  # type: ignore[arg-type]
                if ascii_output:
                    LOG.info(ascii_output)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as e:
        LOG.debug(f'Failed to render frames side-by-side: {e}')


def _get_sprite_color_count(sprite: AnimatedSprite | BitmappySprite) -> int:
    """Get the number of colors in a sprite's color map.

    Args:
        sprite: A sprite object.

    Returns:
        Number of colors.

    """
    if hasattr(sprite, 'color_map'):
        return len(sprite.color_map)  # type: ignore[union-attr] # ty: ignore[invalid-argument-type]
    if hasattr(sprite, '_color_map'):
        return len(sprite._color_map)  # type: ignore[reportPrivateUsage] # ty: ignore[invalid-argument-type]
    return 0


def _get_sprite_alpha_type(sprite: AnimatedSprite | BitmappySprite) -> str:
    """Determine the alpha type of a sprite (indexed or per-pixel).

    Args:
        sprite: A sprite object.

    Returns:
        Either "indexed" or "per-pixel".

    """
    if not hasattr(sprite, 'color_map'):
        return 'indexed'

    for color_value in sprite.color_map.values():  # type: ignore[union-attr] # ty: ignore[unresolved-attribute]
        if isinstance(color_value, (list, tuple)) and len(color_value) >= RGBA_COMPONENT_COUNT:  # type: ignore[arg-type]
            alpha = color_value[3]  # type: ignore[index]
            if isinstance(alpha, (int, float)) and 0 <= alpha <= MAX_PER_PIXEL_ALPHA:
                return 'per-pixel'
    return 'indexed'


def _calculate_animation_duration(
    sprite: AnimatedSprite | BitmappySprite,
    sprite_type: str,
) -> tuple[float, bool]:
    """Calculate total animation duration and loop status.

    Args:
        sprite: A sprite object.
        sprite_type: Either "static" or "animated".

    Returns:
        Tuple of (total_duration, is_looped).

    """
    total_duration = 0.0
    is_looped = False
    if sprite_type != 'animated' or not hasattr(sprite, '_animations'):
        return total_duration, is_looped

    for frames in sprite._animations.values():  # type: ignore[union-attr] # ty: ignore[unresolved-attribute]
        if hasattr(sprite, 'is_looping') and sprite.is_looping:  # type: ignore[union-attr]
            is_looped = True
        for frame in frames:  # type: ignore[union-attr]
            total_duration += frame.duration if hasattr(frame, 'duration') else 0.5  # type: ignore[union-attr]

    return total_duration, is_looped  # type: ignore[return-value]


def _format_duration_string(sprite_type: str, total_duration: float, *, is_looped: bool) -> str:
    """Format a human-readable duration string.

    Args:
        sprite_type: Either "static" or "animated".
        total_duration: Total duration in seconds.
        is_looped: Whether the animation loops.

    Returns:
        Formatted duration string.

    """
    if sprite_type == 'static':
        return '∞'
    if is_looped:
        return f'{total_duration:.1f}s (∞)'
    if total_duration > 0:
        return f'{total_duration:.1f}s (1 time)'
    return '∞'


def _log_colorized_sprite_output(
    config_file: Path,
    config_data: dict[str, Any],
    sprite: AnimatedSprite | BitmappySprite,
    renderer: ASCIIRenderer,
) -> None:
    """Generate and log colorized ASCII output for a loaded sprite.

    Args:
        config_file: Path to the config file.
        config_data: Parsed TOML config data.
        sprite: The loaded sprite object.
        renderer: The ASCII renderer to use.

    """
    sprite_name = getattr(sprite, 'name', 'Unknown')

    if isinstance(sprite, AnimatedSprite):
        has_alpha = _sprite_has_per_pixel_alpha(sprite)
        is_static = sprite.is_static_sprite()
        frame_count = sprite.get_total_frame_count()
        animation_count = len(sprite._animations) if hasattr(sprite, '_animations') else 0  # type: ignore[reportPrivateUsage]

        if is_static:
            LOG.info(
                f'Loaded "{sprite_name}" (filename: {config_file.name}, type:'
                f' single-frame, per-pixel alpha: {has_alpha})',
            )
            _render_static_sprite_ascii(sprite, renderer)
        else:
            LOG.info(
                f'Loaded "{sprite_name}" (filename: {config_file.name}, type:'
                f' animated, animations: {animation_count}, per-pixel alpha:'
                f' {has_alpha})',
            )
            _render_animated_sprite_ascii(sprite, renderer)
    else:
        frame_count = 1
        has_alpha = _pixels_have_alpha(sprite.pixels) if hasattr(sprite, 'pixels') else False
        LOG.info(
            f'Loaded "{sprite_name}" (filename: {config_file.name}, type:'
            f' single-frame, per-pixel alpha: {has_alpha})',
        )

    sprite_type = 'animated' if isinstance(sprite, AnimatedSprite) else 'static'
    color_count = _get_sprite_color_count(sprite)
    alpha_type = _get_sprite_alpha_type(sprite)
    total_duration, is_looped = _calculate_animation_duration(sprite, sprite_type)
    duration_str = _format_duration_string(sprite_type, total_duration, is_looped=is_looped)

    colorized_output = renderer.render_sprite(config_data)
    LOG.debug(
        f'Generated colorized output for {config_file.name}: {len(colorized_output)} characters',
    )
    LOG.debug(f'\n🎨 Colorized ASCII Output for {config_file.name}:')
    LOG.debug(
        f'   Type: {sprite_type}, Frames: {frame_count}, Colors: {color_count},'
        f' Alpha: {alpha_type}, Duration: {duration_str}',
    )
    LOG.debug(colorized_output)
    LOG.debug(f'Successfully printed colorized output for {config_file.name}')


def _process_config_file(config_file: Path, training_data: list[dict[str, Any]]) -> None:
    """Process a single sprite config file and add it to training data.

    Args:
        config_file: Path to the config file.
        training_data: List to append training data to.

    """
    LOG.debug(f'Processing config file: {config_file}')
    try:
        if ai_training_state['format'] != 'toml':
            LOG.warning(f"Unsupported format '{ai_training_state['format']}' for {config_file}")
            return

        config_data, sprite_data = parse_toml_sprite_data(config_file)
        converted_sprite_data = convert_sprite_to_alpha_format(sprite_data)
        training_data.append(converted_sprite_data)

        try:
            from glitchygames.tools.ascii_renderer import ASCIIRenderer

            renderer = ASCIIRenderer()
            sprite = SpriteFactory.load_sprite(filename=str(config_file))
            _log_colorized_sprite_output(config_file, config_data, sprite, renderer)
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            LOG.warning(f'Could not create colorized output for {config_file.name}: {e}')
            import traceback

            LOG.warning(f'Traceback: {traceback.format_exc()}')

    except (FileNotFoundError, PermissionError, ValueError, KeyError) as e:
        LOG.warning(f'Error loading sprite config {config_file}: {e}')


def load_ai_training_data() -> None:
    """Load AI training data from sprite config files.

    Raises:
        TypeError: If ai_training_state['data'] is not a list.

    """
    training_data = ai_training_state['data']
    if not isinstance(training_data, list):
        msg = "ai_training_state['data'] must be a list"
        raise TypeError(msg)

    LOG.info(f'Loading AI training data from: {SPRITE_CONFIG_DIR}')
    LOG.debug(f'Sprite config directory exists: {SPRITE_CONFIG_DIR.exists()}')

    if not SPRITE_CONFIG_DIR.exists():
        LOG.warning(f'Sprite config directory not found: {SPRITE_CONFIG_DIR}')
        LOG.info(f'Total AI training data loaded: {len(training_data)} sprites')
        return

    toml_files = list(SPRITE_CONFIG_DIR.glob('*.toml'))

    if toml_files:
        config_files = toml_files
        ai_training_state['format'] = 'toml'
        LOG.info(f'Found {len(config_files)} TOML sprite config files')
    else:
        config_files = []
        LOG.warning('No sprite config files found')

    for config_file in config_files:
        _process_config_file(config_file, training_data)

    LOG.info(f'Total AI training data loaded: {len(training_data)} sprites')
