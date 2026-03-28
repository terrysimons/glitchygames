"""AI Sprite Generation - Improved prompts and formatting for sprite generation.

This module provides clean, concise prompts and helper functions for AI-based
sprite generation in the TOML format used by GlitchyGames.
"""

import logging
import re
from typing import Any, cast

from glitchygames.color import MAX_COLOR_CHANNEL_VALUE

LOG = logging.getLogger('game.ai.sprite_generator')

MIN_VALID_PIXEL_LINE_LENGTH = 16
MAX_SPRITE_DIMENSION = 64


class SpriteGenerationPrompt:
    """Encapsulates sprite generation prompt templates and logic."""

    # Concise format specification for AI
    FORMAT_SPEC = """\
You generate sprites in TOML format. \
Return ONLY raw TOML, no markdown, no code blocks, no explanations.

STATIC SPRITE (single frame):
[sprite]
name = "SpriteName"
pixels = \"\"\"
ABC
DEF
GHI
\"\"\"

[colors."A"]
red = 255
green = 0
blue = 0

[colors."B"]
red = 0
green = 255
blue = 0

ANIMATED SPRITE (multiple frames):
[sprite]
name = "AnimatedSprite"

[[animation]]
namespace = "idle"
frame_interval = 0.5  # Default timing for all frames
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
ABC
DEF
\"\"\"

[[animation.frame]]
namespace = "idle"
frame_index = 1
frame_interval = 1.0  # Override: hold this frame longer
pixels = \"\"\"
XYZ
123
\"\"\"

[colors."A"]
red = 255
green = 0
blue = 0

ANIMATED WITH VARIED TIMING:
[[animation]]
namespace = "blink"
frame_interval = 0.1  # Fast default

[[animation.frame]]
namespace = "blink"
frame_index = 0
frame_interval = 2.0  # Eyes open (hold 2 sec)
pixels = \"\"\"OO\"\"\"

[[animation.frame]]
namespace = "blink"
frame_index = 1
frame_interval = 0.1  # Eyes closed (quick blink)
pixels = \"\"\"--\"\"\"

CRITICAL RULES:
1. Use triple-quoted strings for pixels (\"\"\" not \")
2. Only define colors actually used in pixels
3. Static: [sprite] WITH pixels, NO [[animation]]
4. Animated: [sprite] WITHOUT pixels, WITH [[animation]]
5. Each color: separate red/green/blue fields (0-255)
6. Animated frames: include namespace AND frame_index
7. Character set: Use ASCII printable chars
8. Add per-frame timing when frames should hold different durations

PER-PIXEL ALPHA (optional):
[colors."A"]
red = 255
green = 0
blue = 0
alpha = 127    # 0=transparent, 255=opaque, omit for opaque

[colors."█"]
red = 255
green = 0
blue = 255     # Magenta transparency key (no alpha field)

ANIMATION TIMING:
- Set frame_interval at [[animation]] level for default timing
- Override frame_interval in [[animation.frame]] for specific frames
- Use varied timing for: blinking (long open, quick close), anticipation, impact frames
- Default 0.5 seconds per frame if not specified

ANIMATION FEATURES:
- loop: true (repeat) or false (play once)
- Multiple animations: use different namespace values
- Each animation can have different timing patterns
"""

    SYSTEM_MESSAGE = (
        'You are a sprite generation assistant for a pixel art editor. '
        'You create sprites in TOML format for game developers. '
        'Generate both static (single-frame) and animated (multi-frame) sprites.'
    )

    ASSISTANT_CONFIRMATION = (
        'I understand the TOML sprite format. I will generate sprites with:\n'
        '- Correct TOML structure (static or animated)\n'
        '- Triple-quoted pixel strings\n'
        '- Only colors used in pixels\n'
        '- Separate red/green/blue fields\n'
        '- Per-pixel alpha when needed\n'
        '- Per-frame timing overrides for varied animation\n'
        '- Raw TOML output only (no markdown)'
    )


def format_training_example(example: dict[str, Any], *, include_raw: bool = True) -> str:
    """Format a training example as clean TOML for AI context.

    Args:
        example: Training example dict with sprite data
        include_raw: If True, include raw_content if available (more accurate)

    Returns:
        Formatted TOML string for AI context

    """
    try:
        # Extract key information
        name = example.get('name', 'unknown')
        sprite_type = example.get('sprite_type', 'unknown')
        has_alpha = example.get('has_alpha', False)

        # Build description
        desc_parts = [f'name="{name}"', f'type={sprite_type}']
        if has_alpha:
            desc_parts.append('alpha=yes')

        description = f'# {", ".join(desc_parts)}\n'

        # Get raw content if available and requested
        if include_raw and 'raw_content' in example:
            return description + example['raw_content']

        # Fallback to sprite data reconstruction
        if 'pixels' in example and 'colors' in example:
            return description + _reconstruct_static_sprite(example)
        if 'animations' in example:
            return description + _reconstruct_animated_sprite(example)

        return description + '# (Format unavailable)'

    except (KeyError, ValueError, TypeError, AttributeError) as e:
        LOG.warning('Error formatting training example: %s', e)
        return f'# Example: {example.get("name", "unknown")} (formatting error)'


def _reconstruct_static_sprite(example: dict[str, Any]) -> str:
    """Reconstruct static sprite TOML from example data.

    Returns:
        str: The resulting string.

    """
    lines = ['[sprite]']
    lines.append(f'name = "{example.get("name", "unknown")}"')

    # Handle pixels
    pixels = example.get('pixels', '')
    if '\n' in pixels:
        lines.append(f'pixels = """\n{pixels}\n"""')
    else:
        lines.append(f'pixels = "{pixels}"')
    lines.append('')

    # Add colors
    colors: dict[str, Any] = example.get('colors', {})
    for char, color_data in sorted(colors.items()):
        lines.append(f'[colors."{char}"]')
        if isinstance(color_data, dict):
            color_dict = cast('dict[str, int]', color_data)
            lines.extend((
                f'red = {color_dict.get("red", 0)}',
                f'green = {color_dict.get("green", 0)}',
                f'blue = {color_dict.get("blue", 0)}',
            ))
            if 'alpha' in color_dict and color_dict['alpha'] != MAX_COLOR_CHANNEL_VALUE:
                lines.append(f'alpha = {color_dict["alpha"]}')
        lines.append('')

    return '\n'.join(lines)


def _reconstruct_animated_sprite(example: dict[str, Any]) -> str:
    """Reconstruct animated sprite TOML from example data.

    Returns:
        str: The resulting string.

    """
    lines = ['[sprite]']
    lines.extend((
        f'name = "{example.get("name", "unknown")}"',
        '',
    ))

    # Add animations
    animations: list[Any] = example.get('animations', [])
    for anim in animations:
        if not isinstance(anim, dict):
            continue

        anim_dict = cast('dict[str, Any]', anim)
        lines.extend([
            '[[animation]]',
            f'namespace = "{anim_dict.get("namespace", "default")}"',
            f'frame_interval = {anim_dict.get("frame_interval", 0.5)}',
            f'loop = {str(anim_dict.get("loop", True)).lower()}',
            '',
        ])

        # Add frames
        frames: list[Any] = anim_dict.get('frame', [])
        for frame in frames:
            if not isinstance(frame, dict):
                continue

            frame_dict = cast('dict[str, Any]', frame)
            lines.extend((
                '[[animation.frame]]',
                f'namespace = "{anim_dict.get("namespace", "default")}"',
                f'frame_index = {frame_dict.get("frame_index", 0)}',
            ))

            # Handle pixels
            pixels: str = frame_dict.get('pixels', '')
            if '\n' in pixels:
                lines.append(f'pixels = """\n{pixels}\n"""')
            else:
                lines.append(f'pixels = "{pixels}"')

            if 'frame_interval' in frame_dict:
                lines.append(f'frame_interval = {frame_dict["frame_interval"]}')
            lines.append('')

    # Add colors
    colors: dict[str, Any] = example.get('colors', {})
    for char, color_data in sorted(colors.items()):
        lines.append(f'[colors."{char}"]')
        if isinstance(color_data, dict):
            anim_color_dict = cast('dict[str, int]', color_data)
            lines.extend((
                f'red = {anim_color_dict.get("red", 0)}',
                f'green = {anim_color_dict.get("green", 0)}',
                f'blue = {anim_color_dict.get("blue", 0)}',
            ))
            if 'alpha' in anim_color_dict and anim_color_dict['alpha'] != MAX_COLOR_CHANNEL_VALUE:
                lines.append(f'alpha = {anim_color_dict["alpha"]}')
        lines.append('')

    return '\n'.join(lines)


def build_sprite_generation_messages(
    user_request: str,
    training_examples: list[dict[str, Any]] | None = None,
    *,
    max_examples: int = 3,
    include_size_hint: bool = True,
    include_animation_hint: bool = True,
) -> list[dict[str, str]]:
    """Build optimized AI message conversation for sprite generation.

    Args:
        user_request: User's sprite generation request
        training_examples: List of example sprites for context (optional)
        max_examples: Maximum number of examples to include
        include_size_hint: If True, detect and emphasize size hints
        include_animation_hint: If True, detect and emphasize animation hints

    Returns:
        List of message dicts for AI API

    """
    # Build context from examples
    example_context = ''
    if training_examples:
        # Limit examples to avoid token bloat
        examples = training_examples[:max_examples]
        formatted_examples = '\n\n---\n\n'.join([format_training_example(ex) for ex in examples])
        example_context = f'\n\nExample sprites:\n\n{formatted_examples}'

    # Build enhanced user request with hints
    enhanced_request = user_request

    # Add size hint if detected
    if include_size_hint:
        size_hint = get_sprite_size_hint(user_request)
        if size_hint:
            width, height = size_hint
            enhanced_request += (
                f'\n\nIMPORTANT: Generate sprite at exactly {width}x{height} pixels.'
            )

    # Add animation hint if detected
    if include_animation_hint and detect_animation_request(user_request):
        enhanced_request += (
            '\n\nIMPORTANT: This should be an ANIMATED sprite with multiple frames. '
            'Use [[animation]] and [[animation.frame]] sections.'
        )

    return [
        {'role': 'system', 'content': SpriteGenerationPrompt.SYSTEM_MESSAGE},
        {'role': 'user', 'content': f'{SpriteGenerationPrompt.FORMAT_SPEC}{example_context}'},
        {'role': 'assistant', 'content': SpriteGenerationPrompt.ASSISTANT_CONFIRMATION},
        {'role': 'user', 'content': enhanced_request},
    ]


def _check_truncated_pixel_data(content: str) -> tuple[bool, str]:
    """Check if pixel data appears truncated (unclosed pixel blocks).

    Args:
        content: AI response content

    Returns:
        Tuple of (is_valid, error_message)

    """
    if 'pixels = """' not in content:
        return True, ''

    # Check for unclosed pixel blocks
    unclosed = re.findall(r'pixels = """([^"]+)$', content, re.DOTALL)
    if not unclosed:
        return True, ''

    # Check if last line is incomplete (much shorter than expected)
    last_block = unclosed[0]
    lines = last_block.strip().split('\n')
    if lines and len(lines) > 1:
        # Compare last line length to previous line
        last_line = lines[-1].strip()
        prev_line = lines[-2].strip() if len(lines) > 1 else ''

        # If last line is much shorter than previous (< 25%), likely truncated
        if prev_line and len(last_line) < len(prev_line) * 0.25:
            return False, 'Response appears truncated (incomplete pixel data)'

        # Or if last line is very short (< 16 chars) for pixel data
        if len(last_line) < MIN_VALID_PIXEL_LINE_LENGTH:
            return False, 'Response appears truncated (incomplete pixel data)'

    return True, ''


def _check_mixed_format(content: str) -> tuple[bool, str]:
    """Check for invalid mixed static and animated format.

    Args:
        content: AI response content

    Returns:
        Tuple of (is_valid, error_message)

    """
    # Mixed format: [sprite] section with pixels AND [[animation]] sections
    # Note: animated sprites can have pixels in [[animation.frame]] sections, that's valid
    if '[sprite]' not in content or '[[animation]]' not in content:
        return True, ''

    # Check if pixels appears in [sprite] section (invalid for animated)
    lines = content.split('\n')
    in_sprite_section = False
    for line in lines:
        stripped = line.strip()
        if stripped == '[sprite]':
            in_sprite_section = True
        elif stripped.startswith('[') and not stripped.startswith('[colors'):
            in_sprite_section = False
        elif in_sprite_section and stripped.startswith('pixels'):
            return False, 'Mixed static and animated format (invalid)'

    return True, ''


def validate_ai_response(content: str) -> tuple[bool, str]:
    """Validate AI response for common errors.

    Args:
        content: AI response content

    Returns:
        Tuple of (is_valid, error_message)

    """
    if not content or not content.strip():
        return False, 'Empty response'

    content_lower = content.lower().strip()

    # Run all validation checks in sequence, returning the first failure
    error = _check_error_message(content_lower)
    if not error:
        error = _check_markdown_blocks(content, content_lower)
    if not error:
        _, error = _check_truncated_pixel_data(content)
    if not error:
        error = _check_required_sections(content_lower)
    if not error:
        _, error = _check_mixed_format(content)
    if not error and re.search(r'(red|green|blue)\s*=\s*\d+\s*,', content):
        error = 'Color values contain commas (should be separate fields)'

    if error:
        return False, error
    return True, ''


def _check_error_message(content_lower: str) -> str:
    """Check if content looks like an error message instead of TOML.

    Args:
        content_lower: Lowercased AI response content

    Returns:
        Error message string, or empty string if valid

    """
    error_indicators = [
        'i apologize',
        "i'm sorry",
        'i cannot',
        "i can't",
        'unable to',
        'error:',
        'failed to',
    ]

    has_error_phrase = any(phrase in content_lower for phrase in error_indicators)
    has_toml_structure = any(
        marker in content_lower for marker in ['[sprite]', '[colors', '[[animation]]']
    )

    if has_error_phrase and not has_toml_structure:
        return 'AI returned error message instead of sprite'
    return ''


def _check_markdown_blocks(content: str, content_lower: str) -> str:
    """Check for markdown code blocks that should have been cleaned.

    Args:
        content: AI response content
        content_lower: Lowercased AI response content

    Returns:
        Error message string, or empty string if valid

    """
    if content.startswith('```') or '```toml' in content_lower:
        return 'Response contains markdown code blocks (should be cleaned first)'
    return ''


def _check_required_sections(content_lower: str) -> str:
    """Check for required TOML sections.

    Args:
        content_lower: Lowercased AI response content

    Returns:
        Error message string, or empty string if valid

    """
    if '[sprite]' not in content_lower:
        return 'Missing [sprite] section'
    if '[colors' not in content_lower:
        return 'Missing [colors] section'
    return ''


def clean_ai_response(content: str | None) -> str | None:
    """Clean markdown and formatting from AI response.

    Args:
        content: Raw AI response

    Returns:
        Cleaned TOML content

    """
    if not content:
        return content

    cleaned = content.strip()

    # Remove markdown code blocks
    if cleaned.startswith('```'):
        lines = cleaned.split('\n')
        # Remove first line if it's a code fence
        if lines[0].startswith('```'):
            lines = lines[1:]
        # Remove last line if it's a code fence
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        cleaned = '\n'.join(lines)

    # Remove inline code fences
    cleaned = cleaned.replace('```toml', '').replace('```', '')

    # Remove any leading/trailing explanatory text
    # Find first [sprite] or [colors section
    lines = cleaned.split('\n')
    first_section = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('['):
            first_section = i
            break

    if first_section > 0:
        cleaned = '\n'.join(lines[first_section:])

    return cleaned.strip()


def get_sprite_size_hint(request: str) -> tuple[int, int] | None:
    """Extract sprite size hint from user request.

    Args:
        request: User's sprite generation request

    Returns:
        Tuple of (width, height) if found, None otherwise

    """
    # Look for patterns like "16x16", "32x32", "8x8"
    size_pattern = r'(\d{1,3})\s*[x×]\s*(\d{1,3})'  # noqa: RUF001
    match = re.search(size_pattern, request, re.IGNORECASE)

    if match:
        width = int(match.group(1))
        height = int(match.group(2))

        # Validate reasonable sizes (1-64 pixels)
        if 1 <= width <= MAX_SPRITE_DIMENSION and 1 <= height <= MAX_SPRITE_DIMENSION:
            return (width, height)

    return None


def detect_animation_request(request: str) -> bool:
    """Detect if user is requesting an animated sprite.

    Args:
        request: User's sprite generation request

    Returns:
        True if animation keywords detected

    """
    request_lower = request.lower()

    animation_keywords = [
        'animat',
        'frame',
        'walk',
        'run',
        'jump',
        'idle',
        '2-frame',
        'multi-frame',
        'loop',
        'cycle',
        'sequence',
        'moving',
        'spinning',
        'rotating',
        'bouncing',
    ]

    return any(keyword in request_lower for keyword in animation_keywords)


def detect_refinement_request(request: str) -> bool:
    """Detect if user is requesting a refinement of a previous sprite.

    Args:
        request: User's sprite generation request

    Returns:
        True if refinement keywords detected

    """
    request_lower = request.lower()

    refinement_keywords = [
        'make it',
        'change',
        'modify',
        'update',
        'adjust',
        'more',
        'less',
        'bigger',
        'smaller',
        'larger',
        'wider',
        'taller',
        'brighter',
        'darker',
        'lighter',
        'add',
        'remove',
        'replace',
        'different',
        'another',
        'new color',
        # Possessive pronouns indicating existing sprite
        'make his',
        'make her',
        'make their',
        'make its',
        'give him',
        'give her',
        'give it',
        'give them',
        'turn it',
        'turn the',
        'turn his',
        'turn her',
        # Direct references to "the sprite" or specific parts
        'make the',
        'change the',
        'update the',
    ]

    return any(keyword in request_lower for keyword in refinement_keywords)


def build_refinement_messages(
    user_request: str,
    last_sprite_content: str,
    conversation_history: list[dict[str, str]] | None = None,
    *,
    include_size_hint: bool = True,
    include_animation_hint: bool = True,
) -> list[dict[str, str]]:
    """Build message conversation for sprite refinement.

    Args:
        user_request: User's refinement request (e.g., "make it bigger")
        last_sprite_content: The last successfully generated sprite TOML
        conversation_history: Previous conversation messages (optional)
        include_size_hint: If True, detect and emphasize size hints
        include_animation_hint: If True, detect and emphasize animation hints

    Returns:
        List of message dicts for AI API

    """
    # Start with base system message and format spec
    messages = [
        {'role': 'system', 'content': SpriteGenerationPrompt.SYSTEM_MESSAGE},
        {'role': 'user', 'content': SpriteGenerationPrompt.FORMAT_SPEC},
        {'role': 'assistant', 'content': SpriteGenerationPrompt.ASSISTANT_CONFIRMATION},
    ]

    # Add conversation history if available
    if conversation_history:
        messages.extend(conversation_history)

    # Build enhanced user request with hints
    enhanced_request = user_request

    # Add size hint if detected
    if include_size_hint:
        size_hint = get_sprite_size_hint(user_request)
        if size_hint:
            width, height = size_hint
            enhanced_request += (
                f'\n\nIMPORTANT: Generate sprite at exactly {width}x{height} pixels.'
            )

    # Add animation hint if detected
    if include_animation_hint and detect_animation_request(user_request):
        enhanced_request += (
            '\n\nIMPORTANT: This should be an ANIMATED sprite with multiple frames. '
            'Use [[animation]] and [[animation.frame]] sections.'
        )

    # Add the previous sprite as context with explicit preservation instructions
    refinement_context = (
        f'Here is the current sprite:\n\n'
        f'```toml\n{last_sprite_content}\n```\n\n'
        f"User's request: {enhanced_request}\n\n"
        f'CRITICAL INSTRUCTIONS:\n'
        f'1. Return the EXACT same sprite structure with ONLY the changes requested\n'
        f'2. Preserve ALL animation namespaces (film strip labels) that exist\n'
        f'3. Preserve the EXACT number of frames in each animation'
        f' UNLESS the user explicitly asks to add/remove frames\n'
        f'4. Preserve ALL [[animation]] and'
        f' [[animation.frame]] sections\n'
        f'5. Only modify what the user specifically requested'
        f" (e.g., if they say 'make it red', only change colors)\n"
        f'6. If the user asks to add frames, add them.'
        f' If they ask to remove frames, remove them.'
        f' Otherwise, keep the same count.\n\n'
        f'Return ONLY the complete updated sprite in TOML format.'
    )

    messages.append({'role': 'user', 'content': refinement_context})

    return messages
