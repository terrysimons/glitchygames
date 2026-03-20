#!/usr/bin/env python3
"""Unicode character map utilities for sprite generation."""

import logging
import unicodedata
from collections.abc import Generator

# Set up logging
LOG = logging.getLogger('glitchygames.tools.charmap')

# Constants
MAX_CHARS_TO_DISPLAY = 100

# Emoji ranges (approximate)
EMOJI_RANGES = [
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F300, 0x1F5FF),  # Misc. Symbols and Pictographs
    (0x1F680, 0x1F6FF),  # Transport and Map Symbols
    (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
    (0x1FA70, 0x1FAFF),  # Symbols and Pictographs Extended-A
    (0x2600, 0x26FF),  # Misc Symbols
    (0x2700, 0x27BF),  # Dingbats
    (0x1F1E6, 0x1F1FF),  # Regional Indicator Symbols (Flags)
]


def is_defined_non_whitespace_printable(ch: str) -> bool:
    """Check if character is defined, non-whitespace, and printable.

    Returns:
        bool: True if is defined non whitespace printable, False otherwise.

    """
    if not ch.isprintable():
        return False
    if ch.isspace():
        return False
    try:
        unicodedata.name(ch)
    except ValueError:
        return False
    return True


def is_emoji(ch: str) -> bool:
    """Check if character is an emoji.

    Returns:
        bool: True if is emoji, False otherwise.

    """
    cp = ord(ch)
    return any(start <= cp <= end for start, end in EMOJI_RANGES)


def unicode_generator_with_priority() -> Generator[str]:
    """Generate Unicode characters with priority ordering.

    Yields:
        str: The next Unicode character in priority order.

    """
    # Regional indicator letters (🇦-🇿)
    # ordered_letters = [
    #     "\U0001F1E6", "\U0001F1E7", "\U0001F1E8", "\U0001F1E9", "\U0001F1EA",
    #     "\U0001F1EB", "\U0001F1EC", "\U0001F1ED", "\U0001F1EE", "\U0001F1EF",
    #     "\U0001F1F0", "\U0001F1F1", "\U0001F1F2", "\U0001F1F3", "\U0001F1F4",
    #     "\U0001F1F5", "\U0001F1F6", "\U0001F1F7", "\U0001F1F8", "\U0001F1F9",
    #     "\U0001F1FA", "\U0001F1FB", "\U0001F1FC", "\U0001F1FD", "\U0001F1FE",
    #     "\U0001F1FF"
    # ]

    # Numeric dingbats:
    # numeric_dingbats = [
    #     "❶","❷","❸","❹","❺","❻","❼","❽","❾","❿",
    #     "➀","➁","➂","➃","➄","➅","➆","➇","➈","➉",
    #     "➊","➋","➌","➍","➎","➏","➐","➑","➒","➓"
    # ]

    handled_chars: set[str] = set()

    # # 1. Print regional indicator letters first
    # for ch in ordered_letters:
    #     if is_defined_non_whitespace_printable(ch):
    #         yield ch
    #         handled_chars.add(ch)

    # 2. Print all other emojis
    for codepoint in range(0x110000):
        ch = chr(codepoint)
        if ch in handled_chars:
            continue
        if is_emoji(ch) and is_defined_non_whitespace_printable(ch):
            yield ch
            handled_chars.add(ch)

    # 3. Print ASCII printable chars before 'A' (0x20-0x40)
    # 'A' = 0x41
    # for codepoint in range(0x20, 0x41):
    #     ch = chr(codepoint)
    #     if ch not in handled_chars and is_defined_non_whitespace_printable(ch):
    #         yield ch
    #         handled_chars.add(ch)

    # # 4. Print numeric dingbats now
    # for ch in numeric_dingbats:
    #     if ch not in handled_chars and is_defined_non_whitespace_printable(ch):
    #         yield ch
    #         handled_chars.add(ch)

    # # 5. Print ASCII uppercase 'A'-Z' (0x41-0x5A)
    # for codepoint in range(0x41, 0x5B):
    #     ch = chr(codepoint)
    #     if ch not in handled_chars and is_defined_non_whitespace_printable(ch):
    #         yield ch
    #         handled_chars.add(ch)

    # # 6. Print remaining ASCII printable chars after 'Z' (0x5B-0x7E)
    # for codepoint in range(0x5B, 0x7F):
    #     ch = chr(codepoint)
    #     if ch not in handled_chars and is_defined_non_whitespace_printable(ch):
    #         yield ch
    #         handled_chars.add(ch)

    # # 7. Print all other defined, printable, non-whitespace Unicode chars
    # for codepoint in range(0x110000):
    #     ch = chr(codepoint)
    #     if ch in handled_chars:
    #         continue
    #     # If it's emoji or in ASCII range, skip those again
    #     cp = ord(ch)
    #     if is_emoji(ch) or (0x20 <= cp < 0x7F):
    #         continue
    #     if is_defined_non_whitespace_printable(ch):
    #         yield ch


# Example usage:
if __name__ == '__main__':
    # Configure logging for this module
    logging.basicConfig(level=logging.INFO)

    chars = list(unicode_generator_with_priority())

    # Log the characters as a single message to avoid excessive logging
    sample_chars = chars[:MAX_CHARS_TO_DISPLAY]
    truncation = '...' if len(chars) > MAX_CHARS_TO_DISPLAY else ''
    LOG.info(f'Generated {len(chars)} Unicode characters: {" ".join(sample_chars)}{truncation}')
