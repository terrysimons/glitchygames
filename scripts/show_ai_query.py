#!/usr/bin/env python3
# ruff: noqa: RUF001
"""Script to demonstrate how Bitmappy constructs AI queries for sprite generation.

This script shows the complete message structure that would be sent to the AI,
including system prompts, training examples, and user requests.
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

CONTENT_PREVIEW_LENGTH = 200
MINIMUM_ARGUMENT_COUNT = 2


def print_separator(title: str, char: str = '=', width: int = 80) -> None:
    """Print a formatted separator with title."""
    print(f'\n{char * width}')  # noqa: T201
    print(f'{title:^{width}}')  # noqa: T201
    print(f'{char * width}')  # noqa: T201


def print_message(message: dict[str, str], index: int) -> None:
    """Print a formatted message."""
    role: str = message['role']
    content: str = message['content']
    print(f'\n--- Message {index} ({role.upper()}) ---')  # noqa: T201
    print(f'Role: {role}')  # noqa: T201
    print(f'Content Length: {len(content)} characters')  # noqa: T201
    print(f'Content Preview: {content[:CONTENT_PREVIEW_LENGTH]}...')  # noqa: T201
    if len(content) > CONTENT_PREVIEW_LENGTH:
        remaining = len(content) - CONTENT_PREVIEW_LENGTH
        print(f'[... {remaining} more characters ...]')  # noqa: T201


def construct_ai_query(
    user_prompt: str, *, show_full_content: bool = False
) -> list[dict[str, str]]:
    """Construct the AI query that Bitmappy would send.

    Returns:
        List of message dicts representing the full AI conversation.
    """
    print_separator('BITMAPPY AI QUERY CONSTRUCTION')

    # AI Configuration (extracted from bitmappy.py)
    ai_model: str = 'ollama:mistral-nemo:12b'
    ai_max_input_tokens: int = 8192
    ai_training_format: str = 'toml'

    # Sprite glyphs (first 512 characters)
    sprite_glyphs = [
        '.',
        '#',
        '0',
        '1',
        '2',
        '3',
        '4',
        '5',
        '6',
        '7',
        '8',
        '9',
        'a',
        'b',
        'c',
        'd',
        'e',
        'f',
        'g',
        'h',
        'i',
        'j',
        'k',
        'l',
        'm',
        'n',
        'o',
        'p',
        'q',
        'r',
        's',
        't',
        'u',
        'v',
        'w',
        'x',
        'y',
        'z',
        'A',
        'B',
        'C',
        'D',
        'E',
        'F',
        'G',
        'H',
        'I',
        'J',
        'K',
        'L',
        'M',
        'N',
        'O',
        'P',
        'Q',
        'R',
        'S',
        'T',
        'U',
        'V',
        'W',
        'X',
        'Y',
        'Z',
        '█',
        '▓',
        '▒',
        '░',
        '▄',
        '▀',
        '▌',
        '▐',
        '■',
        '□',
        '▲',
        '△',
        '▼',
        '▽',
        '◄',
        '►',
        '◀',
        '▶',
        '●',
        '○',
        '◆',
        '◇',
        '★',
        '☆',
        '♦',
        '♠',
        '♣',
        '♥',
        '♪',
        '♫',
        '♬',
        '♭',
        '♮',
        '♯',
        '♩',
        '♪',
        '♫',
        '♬',
        '♭',
        '♮',
        '♯',
        '♩',
        '♪',
        '♫',
        '♬',
        '♭',
        '♮',
        '♯',
        'α',
        'β',
        'γ',
        'δ',
        'ε',
        'ζ',
        'η',
        'θ',
        'ι',
        'κ',
        'λ',
        'μ',
        'ν',
        'ξ',
        'ο',
        'π',
        'ρ',
        'σ',
        'τ',
        'υ',
        'φ',
        'χ',
        'ψ',
        'ω',
        'Α',
        'Β',
        'Γ',
        'Δ',
        'Ε',
        'Ζ',
        'Η',
        'Θ',
        'Ι',
        'Κ',
        'Λ',
        'Μ',
        'Ν',
        'Ξ',
        'Ο',
        'Π',
        'Ρ',
        'Σ',
        'Τ',
        'Υ',
        'Φ',
        'Χ',
        'Ψ',
        'Ω',
        '∞',
        '±',
        '×',
        '÷',
        '≤',
        '≥',
        '≠',
        '≈',
        '≡',
        '∝',
        '∑',
        '∏',
        '∫',
        '∂',
        '∇',
        '∆',
        '√',
        '∛',
        '∜',
        '∝',
        '∞',
        '∅',
        '∈',
        '∉',
        '⊂',
        '⊃',
        '⊆',
        '⊇',
        '∪',
        '∩',
        '←',
        '→',
        '↑',
        '↓',
        '↔',
        '↕',
        '↖',
        '↗',
        '↘',
        '↙',
        '↚',
        '↛',
        '↜',
        '↝',
        '↞',
        '↟',
        '↠',
        '↡',
        '↢',
        '↣',
        '↤',
        '↥',
        '↦',
        '↧',
        '↨',
        '↩',
        '↪',
        '↫',
        '↬',
        '↭',
        '↮',
        '↯',
        '↰',
        '↱',
        '↲',
        '↳',
        '↴',
        '↵',
        '↶',
        '↷',
        '↸',
        '↹',
        '↺',
        '↻',
        '↼',
        '↽',
        '↾',
        '↿',
        '⇀',
        '⇁',
        '⇂',
        '⇃',
        '⇄',
        '⇅',
        '⇆',
        '⇇',
        '⇈',
        '⇉',
        '⇊',
        '⇋',
        '⇌',
        '⇍',
        '⇎',
        '⇏',
        '⇐',
        '⇒',
        '⇔',
        '⇕',
        '⇖',
        '⇗',
        '⇘',
        '⇙',
        '⇚',
        '⇛',
        '⇜',
        '⇝',
        '⇞',
        '⇟',
        '⇠',
        '⇡',
        '⇢',
        '⇣',
        '⇤',
        '⇥',
        '⇦',
        '⇧',
        '⇨',
        '⇩',
        '⇪',
        '⇫',
        '⇬',
        '⇭',
        '⇮',
        '⇯',
        '⇰',
        '⇱',
        '⇲',
        '⇳',
        '⇴',
        '⇵',
        '⇶',
        '⇷',
        '⇸',
        '⇹',
        '⇺',
        '⇻',
        '⇼',
        '⇽',
        '⇾',
        '⇿',
        '∀',
        '∁',
        '∂',
        '∃',
        '∄',
        '∅',
        '∆',
        '∇',
        '∈',
        '∉',
        '∋',
        '∌',
        '∍',
        '∎',
        '∏',
        '∐',
        '∑',
        '−',
        '∓',
        '∔',
        '∕',
        '∖',
        '∗',
        '∘',
        '∙',
        '√',
        '∛',
        '∜',
        '∝',
        '∞',
        '∟',
        '∠',
        '∡',
        '∢',
        '∣',
        '∤',
        '∥',
        '∦',
        '∧',
        '∨',
        '∩',
        '∪',
        '∫',
        '∬',
        '∭',
        '∮',
        '∯',
        '∰',
        '∱',
        '∲',
        '∳',
        '∴',
        '∵',
        '∶',
        '∷',
        '∸',
        '∹',
        '∺',
        '∻',
        '∼',
        '∽',
        '∾',
        '∿',
        '≀',
        '≁',
        '≂',
        '≃',
        '≄',
        '≅',
        '≆',
        '≇',
        '≈',
        '≉',
        '≊',
        '≋',
        '≌',
        '≍',
        '≎',
        '≏',
        '≐',
        '≑',
        '≒',
        '≓',
        '≔',
        '≕',
        '≖',
        '≗',
        '≘',
        '≙',
        '≚',
        '≛',
        '≜',
        '≝',
        '≞',
        '≟',
        '≠',
        '≡',
        '≢',
        '≣',
        '≤',
        '≥',
        '≦',
        '≧',
        '≨',
        '≩',
        '≪',
        '≫',
        '≬',
        '≭',
        '≮',
        '≯',
        '≰',
        '≱',
        '≲',
        '≳',
        '≴',
        '≵',
        '≶',
        '≷',
        '≸',
        '≹',
        '≺',
        '≻',
        '≼',
        '≽',
        '≾',
        '≿',
        '⊀',
        '⊁',
        '⊂',
        '⊃',
        '⊄',
        '⊅',
        '⊆',
        '⊇',
        '⊈',
        '⊉',
        '⊊',
        '⊋',
        '⊌',
        '⊍',
        '⊎',
        '⊏',
        '⊐',
        '⊑',
        '⊒',
        '⊓',
        '⊔',
        '⊕',
        '⊖',
        '⊗',
        '⊘',
        '⊙',
        '⊚',
        '⊛',
        '⊜',
        '⊝',
        '⊞',
        '⊟',
        '⊠',
        '⊡',
        '⊢',
        '⊣',
        '⊤',
        '⊥',
        '⊦',
        '⊧',
        '⊨',
        '⊩',
        '⊪',
        '⊫',
        '⊬',
        '⊭',
        '⊮',
        '⊯',
        '⊰',
        '⊱',
        '⊲',
        '⊳',
        '⊴',
        '⊵',
        '⊶',
        '⊷',
        '⊸',
        '⊹',
        '⊺',
        '⊻',
        '⊼',
        '⊽',
        '⊾',
        '⊿',
        '⋀',
        '⋁',
        '⋂',
        '⋃',
        '⋄',
        '⋅',
        '⋆',
        '⋇',
        '⋈',
        '⋉',
        '⋊',
        '⋋',
        '⋌',
        '⋍',
        '⋎',
        '⋏',
        '⋐',
        '⋑',
        '⋒',
        '⋓',
        '⋔',
        '⋕',
        '⋖',
        '⋗',
        '⋘',
        '⋙',
        '⋚',
        '⋛',
        '⋜',
        '⋝',
        '⋞',
        '⋟',
        '⋠',
        '⋡',
        '⋢',
        '⋣',
        '⋤',
        '⋥',
        '⋦',
        '⋧',
        '⋨',
        '⋩',
        '⋪',
        '⋫',
        '⋬',
        '⋭',
        '⋮',
        '⋯',
        '⋰',
        '⋱',
        '⋲',
        '⋳',
        '⋴',
        '⋵',
        '⋶',
        '⋷',
        '⋸',
        '⋹',
        '⋺',
        '⋻',
        '⋼',
        '⋽',
        '⋾',
        '⋿',
    ]

    # Complete TOML format template (extracted from bitmappy.py)
    complete_toml_format = """
COMPLETE TOML FORMAT REQUIREMENTS:

STATIC SPRITES (single-frame):
    [sprite] section with name and pixels
    [colors] section with colors.0 through colors.7
    Each color has red, green, blue values (0-255)

ANIMATED SPRITES (multi-frame):
    [sprite] section with name only (NO pixels item)
    [colors] section with 'colors."X"' section keys, where X is the character used in the pixels
    [[animation]] section with namespace, frame_interval, loop
    [[animation.frame]] sections with namespace, frame_index, pixels
    PER-FRAME TIMING: When asked to generate per-frame frame_intervals, add a frame_interval
    parameter to each frame where the frame's draw interval is different from the global
    animation namespace frame_interval

CRITICAL RULES:
    - ONLY include color definitions for colors that are actually used in the pixels
    - ALWAYS include namespace in each [[animation.frame]] section
    - ALWAYS include frame_index in each [[animation.frame]] section
    - ALWAYS include frame_interval and loop in [[animation]] section
    - NEVER mix static and animated content in the same file!
    - Static sprites: [sprite] with pixels + [colors] sections ONLY
    - Animated sprites: [sprite] with NO pixels item + [colors] + [[animation]] sections
      ONLY
    - IMPORTANT: Animated sprites must NOT have a pixels item in the [sprite] section!
    - CRITICAL: Use triple-quoted block strings for multi-line pixel data, never use single quotes
    - EFFICIENCY: Only define colors that appear in the pixel data (e.g., if pixels only use
      "0", only define [colors."0"])

COLOR FORMAT REQUIREMENTS:
    - Each color definition MUST use separate red, green, blue fields
    - NEVER use comma-separated values like "red = 255, 0, 0"
    - ALWAYS use the format:
      [colors."X"]
      red = 255
      green = 0
      blue = 0
    - Each color value must be a single integer from 0-255
    - Example of CORRECT color format:
      [colors."#"]
      red = 255
      green = 0
      blue = 0
    - Example of INCORRECT color format (DO NOT USE):
      [colors."#"]
      red = 255, 0, 0
"""

    print(f'AI Model: {ai_model}')  # noqa: T201
    print(f'Max input tokens: {ai_max_input_tokens}')  # noqa: T201
    print(f'Training format: {ai_training_format}')  # noqa: T201

    # Mock training examples (since we can't load them without pygame)
    print('\nUsing mock training examples for demonstration...')  # noqa: T201
    relevant_examples = [
        {
            'name': 'example_static_sprite',
            'sprite_type': 'static',
            'pixels': '.#.\n#.#\n.#.',
            'colors': {
                '.': {'red': 0, 'green': 0, 'blue': 0},
                '#': {'red': 255, 'green': 255, 'blue': 255},
            },
        },
        {
            'name': 'example_animated_sprite',
            'sprite_type': 'animated',
            'animations': [{'namespace': 'walk', 'frame_interval': 0.1, 'loop': True}],
        },
    ]
    print(f'Selected {len(relevant_examples)} mock examples')  # noqa: T201

    # Determine format instruction
    format_instruction = (
        'I understand. I will provide ONLY raw TOML content without any '
        'markdown formatting, code blocks, or explanations. The TOML format '
        'will include:\n'
        '    - [sprite] section containing name and pixels '
        '(using triple-quoted block strings)\n'
        '    - [colors."X"] sections ONLY for colors that are actually used '
        'in the pixel data\n'
        '    - RGB values from 0-255 for each color\n'
        '    - Pixels using the SPRITE_GLYPHS character set\n'
        '    - For animated sprites: [[animation]] and [[animation.frame]] sections\n'
        '    - When "frame", "animation", "animated", "2-frame", or "multi-frame" '
        'is mentioned, I will create an ANIMATED sprite with multiple frames\n'
        '    - IMPORTANT: Use triple-quoted block strings for multi-line pixel data\n'
        '    - EFFICIENCY: Only define colors that appear in the pixels '
        '(e.g., if pixels="0", only define [colors."0"])'
    )

    glyph_count = len(sprite_glyphs[:512])
    glyph_list = sprite_glyphs[:512]
    examples_text = '\n'.join([str(data) for data in relevant_examples])

    # Construct the complete message array (extracted from bitmappy.py)
    messages: list[dict[str, str]] = [
        {
            'role': 'system',
            'content': (
                'You are a helpful assistant in a bitmap editor that can create '
                'game content for game developers. You can create both static '
                'single-frame sprites and animated multi-frame sprites.\n\n'
                f'Available character set for sprite pixels: {glyph_count} '
                f'colors: {glyph_list}'
            ),
        },
        {
            'role': 'user',
            'content': (
                'Here is the context for your sprite generation:\n\n'
                f'{examples_text}\n\n'
                f'Available character set: {glyph_count} colors: {glyph_list}\n\n'
                'IMPORTANT: The examples above include both the selected frame and '
                'the selected strip from the current sprite. Use this context to '
                'understand what the user is asking for and determine the appropriate '
                'response based on their request.'
            ),
        },
        {
            'role': 'assistant',
            'content': (
                'Thank you for providing those sprite examples. I understand '
                'that each sprite consists of:\n\n'
                '1. A name\n'
                '2. A pixel layout using characters from: '
                f'{glyph_count} colors: {glyph_list}\n'
                '3. A color palette mapping characters to RGB values\n'
                '4. For animated sprites: multiple frames with timing information\n\n'
                f"I'll use the {ai_training_format.upper()} format when suggesting "
                'new sprites.'
            ),
        },
        {
            'role': 'user',
            'content': (
                'Great! When I ask you to create a sprite, please provide ONLY the '
                f'{ai_training_format.upper()} content without any markdown formatting, '
                f'code blocks, or explanations. Just the raw {ai_training_format.upper()} '
                'file content.\n\n'
                f'{complete_toml_format}\n\n'
                f'IMPORTANT: Return ONLY the {ai_training_format.upper()} content, '
                'no markdown code blocks, no explanations, no ```toml or ``` markers.'
            ),
        },
        {
            'role': 'assistant',
            'content': format_instruction,
        },
        {
            'role': 'user',
            'content': user_prompt.strip(),
        },
    ]

    # Print message summary
    print_separator('MESSAGE STRUCTURE')
    print(f'Total messages: {len(messages)}')  # noqa: T201

    total_chars = sum(len(msg['content']) for msg in messages)
    print(f'Total characters: {total_chars:,}')  # noqa: T201

    # Estimate token count (rough approximation: 1 token ~ 4 characters)
    estimated_tokens = total_chars // 4
    print(f'Estimated tokens: {estimated_tokens:,}')  # noqa: T201
    print(f'Max input tokens: {ai_max_input_tokens:,}')  # noqa: T201
    token_usage_percent = estimated_tokens / ai_max_input_tokens * 100
    print(f'Token usage: {token_usage_percent:.1f}%')  # noqa: T201

    # Print each message
    print_separator('DETAILED MESSAGE BREAKDOWN')
    for i, message in enumerate(messages):
        print_message(message, i + 1)

        if show_full_content:
            print('\nFull content:')  # noqa: T201
            print('-' * 40)  # noqa: T201
            print(message['content'])  # noqa: T201
            print('-' * 40)  # noqa: T201

    # Show API call parameters
    print_separator('API CALL PARAMETERS')

    print('Parameters that would be sent to AI:')  # noqa: T201
    print(f'  model: {ai_model}')  # noqa: T201
    print(f'  messages: {len(messages)} messages')  # noqa: T201
    print(f'  max_tokens: {ai_max_input_tokens}')  # noqa: T201

    return messages


def main() -> None:
    """Main function."""
    if len(sys.argv) < MINIMUM_ARGUMENT_COUNT:
        print(  # noqa: T201
            'Usage: python show_ai_query.py <user_prompt> [--full-content]'
        )
        print('\nExamples:')  # noqa: T201
        print("  python show_ai_query.py 'a red hat'")  # noqa: T201
        print(  # noqa: T201
            "  python show_ai_query.py 'animated walking character' --full-content"
        )
        sys.exit(1)

    user_prompt: str = sys.argv[1]
    show_full_content: bool = '--full-content' in sys.argv

    print(f"User prompt: '{user_prompt}'")  # noqa: T201
    print(f'Show full content: {show_full_content}')  # noqa: T201

    try:
        messages: list[dict[str, str]] = construct_ai_query(
            user_prompt, show_full_content=show_full_content
        )

        print_separator('SUMMARY')
        print(  # noqa: T201
            f'Successfully constructed AI query with {len(messages)} messages'
        )
        print('Ready to send to ollama:mistral-nemo:12b')  # noqa: T201

    except Exception as exception:  # noqa: BLE001
        print(f'Error: {exception}')  # noqa: T201
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
