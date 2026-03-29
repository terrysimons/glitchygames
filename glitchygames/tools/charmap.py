#!/usr/bin/env python3
"""Unicode character map utilities for sprite generation."""

from __future__ import annotations

import logging
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
    handled_chars: set[str] = set()

    # Print all emojis
    for codepoint in range(0x110000):
        ch = chr(codepoint)
        if ch in handled_chars:
            continue
        if is_emoji(ch) and is_defined_non_whitespace_printable(ch):
            yield ch
            handled_chars.add(ch)


# Example usage:
if __name__ == '__main__':
    # Configure logging for this module
    logging.basicConfig(level=logging.INFO)

    chars = list(unicode_generator_with_priority())

    # Log the characters as a single message to avoid excessive logging
    sample_chars = chars[:MAX_CHARS_TO_DISPLAY]
    truncation = '...' if len(chars) > MAX_CHARS_TO_DISPLAY else ''
    LOG.info(f'Generated {len(chars)} Unicode characters: {" ".join(sample_chars)}{truncation}')
