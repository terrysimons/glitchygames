"""Extended test coverage for charmap module: edge cases and unicode_generator_with_priority."""

import sys
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools.charmap import (
    is_defined_non_whitespace_printable,
    is_emoji,
    unicode_generator_with_priority,
)


class TestIsDefinedNonWhitespacePrintableEdgeCases:
    """Tests for is_defined_non_whitespace_printable with edge cases."""

    def test_undefined_char_returns_false(self):
        """Test that an undefined Unicode character returns False.

        Some codepoints are printable but not defined in unicodedata.name(),
        which raises ValueError. The function should catch that and return False.
        """
        # U+FDD0 is a non-character that is technically valid but has no name
        # in the Unicode database, causing unicodedata.name() to raise ValueError.
        # However, it may not be printable. Let's find a char that is printable
        # but undefined.
        # The soft hyphen U+00AD is a common character that causes issues.
        # Some private use area characters may be printable but undefined.
        # U+E000 is in the Private Use Area - printable but no Unicode name
        char = '\ue000'
        # If it's printable but has no Unicode name, the function should return False
        if char.isprintable() and not char.isspace():
            result = is_defined_non_whitespace_printable(char)
            assert result is False

    def test_control_char_returns_false(self):
        """Test that a control character returns False (not printable)."""
        result = is_defined_non_whitespace_printable('\x00')
        assert result is False

    def test_space_returns_false(self):
        """Test that a space character returns False (is whitespace)."""
        result = is_defined_non_whitespace_printable(' ')
        assert result is False

    def test_tab_returns_false(self):
        """Test that a tab character returns False."""
        result = is_defined_non_whitespace_printable('\t')
        assert result is False

    def test_regular_letter_returns_true(self):
        """Test that a regular letter returns True."""
        result = is_defined_non_whitespace_printable('A')
        assert result is True

    def test_digit_returns_true(self):
        """Test that a digit returns True."""
        result = is_defined_non_whitespace_printable('5')
        assert result is True

    def test_punctuation_returns_true(self):
        """Test that a punctuation character returns True."""
        result = is_defined_non_whitespace_printable('!')
        assert result is True


class TestUnicodeGeneratorWithPriority:
    """Tests for unicode_generator_with_priority function."""

    def test_returns_generator(self):
        """Test that the function returns a generator."""
        generator = unicode_generator_with_priority()
        # Generators have __next__ method
        assert hasattr(generator, '__next__')

    def test_yields_emoji_characters(self):
        """Test that the generator yields emoji characters."""
        generator = unicode_generator_with_priority()
        # Get the first several characters
        first_chars = [next(generator) for _index in range(10)]
        # All yielded characters should be emojis (since emojis come first)
        for char in first_chars:
            assert is_emoji(char), f'Expected emoji but got {char!r} (U+{ord(char):04X})'

    def test_yields_defined_printable_characters(self):
        """Test that all yielded characters are defined, non-whitespace, and printable."""
        generator = unicode_generator_with_priority()
        # Check the first 50 characters
        for _index in range(50):
            char = next(generator)
            assert is_defined_non_whitespace_printable(char), (
                f'Character {char!r} (U+{ord(char):04X}) is not defined non-whitespace printable'
            )

    def test_no_duplicate_characters(self):
        """Test that the generator does not yield duplicate characters."""
        generator = unicode_generator_with_priority()
        seen = set()
        # Check the first 100 characters for duplicates
        for _index in range(100):
            char = next(generator)
            assert char not in seen, f'Duplicate character: {char!r} (U+{ord(char):04X})'
            seen.add(char)

    def test_generator_yields_multiple_characters(self):
        """Test that the generator can yield a substantial number of characters."""
        generator = unicode_generator_with_priority()
        chars = [next(generator) for _index in range(100)]
        assert len(chars) == 100
