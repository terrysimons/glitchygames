"""Tests for terminal_utils module - terminal capability detection and color mapping."""

import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools.terminal_utils import (
    ANSI_256_GRAYSCALE_RAMP_THRESHOLD,
    ANSI_COLOR_CHANNEL_MIDPOINT,
    ColorMapper,
    TerminalCapability,
    TerminalDetector,
)


class TestTerminalCapability:
    """Test TerminalCapability constants."""

    def test_monochrome_constant(self):
        """Test MONOCHROME capability constant exists and has expected value."""
        assert TerminalCapability.MONOCHROME == 'mono'

    def test_color_8_constant(self):
        """Test COLOR_8 capability constant exists and has expected value."""
        assert TerminalCapability.COLOR_8 == '8_color'

    def test_color_256_constant(self):
        """Test COLOR_256 capability constant exists and has expected value."""
        assert TerminalCapability.COLOR_256 == '256_color'

    def test_true_color_constant(self):
        """Test TRUE_COLOR capability constant exists and has expected value."""
        assert TerminalCapability.TRUE_COLOR == 'true_color'


class TestTerminalDetector:
    """Test TerminalDetector class."""

    def test_detect_capability_truecolor_via_colorterm(self, mocker):
        """Test detection of true color support via COLORTERM=truecolor."""
        mocker.patch.dict('os.environ', {'TERM': '', 'COLORTERM': 'truecolor'})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.TRUE_COLOR

    def test_detect_capability_24bit_via_colorterm(self, mocker):
        """Test detection of true color support via COLORTERM=24bit."""
        mocker.patch.dict('os.environ', {'TERM': '', 'COLORTERM': '24bit'})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.TRUE_COLOR

    def test_detect_capability_direct_via_term(self, mocker):
        """Test detection of true color support via TERM=direct."""
        mocker.patch.dict('os.environ', {'TERM': 'direct', 'COLORTERM': ''})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.TRUE_COLOR

    def test_detect_capability_truecolor_via_term(self, mocker):
        """Test detection of true color support via TERM=truecolor."""
        mocker.patch.dict('os.environ', {'TERM': 'truecolor', 'COLORTERM': ''})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.TRUE_COLOR

    def test_detect_capability_256color_via_colorterm(self, mocker):
        """Test detection of 256-color support via COLORTERM containing '256'."""
        mocker.patch.dict('os.environ', {'TERM': '', 'COLORTERM': '256color'})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.COLOR_256

    def test_detect_capability_256color_via_term(self, mocker):
        """Test detection of 256-color support via TERM containing '256color'."""
        mocker.patch.dict('os.environ', {'TERM': 'xterm-256color', 'COLORTERM': ''})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.COLOR_256

    def test_detect_capability_xterm(self, mocker):
        """Test detection of 256-color for xterm terminal."""
        mocker.patch.dict('os.environ', {'TERM': 'xterm', 'COLORTERM': ''})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.COLOR_256

    def test_detect_capability_screen(self, mocker):
        """Test detection of 256-color for screen terminal."""
        mocker.patch.dict('os.environ', {'TERM': 'screen', 'COLORTERM': ''})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.COLOR_256

    def test_detect_capability_tmux(self, mocker):
        """Test detection of 256-color for tmux terminal."""
        mocker.patch.dict('os.environ', {'TERM': 'tmux', 'COLORTERM': ''})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.COLOR_256

    def test_detect_capability_rxvt(self, mocker):
        """Test detection of 256-color for rxvt terminal."""
        mocker.patch.dict('os.environ', {'TERM': 'rxvt', 'COLORTERM': ''})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.COLOR_256

    def test_detect_capability_linux(self, mocker):
        """Test detection of 8-color for linux terminal."""
        mocker.patch.dict('os.environ', {'TERM': 'linux', 'COLORTERM': ''})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.COLOR_8

    def test_detect_capability_vt100(self, mocker):
        """Test detection of 8-color for vt100 terminal."""
        mocker.patch.dict('os.environ', {'TERM': 'vt100', 'COLORTERM': ''})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.COLOR_8

    def test_detect_capability_vt220(self, mocker):
        """Test detection of 8-color for vt220 terminal."""
        mocker.patch.dict('os.environ', {'TERM': 'vt220', 'COLORTERM': ''})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.COLOR_8

    def test_detect_capability_unknown_defaults_to_8_color(self, mocker):
        """Test that unknown terminal types default to 8-color."""
        mocker.patch.dict('os.environ', {'TERM': 'unknown-terminal', 'COLORTERM': ''})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.COLOR_8

    def test_detect_capability_empty_defaults_to_8_color(self, mocker):
        """Test that empty TERM and COLORTERM default to 8-color."""
        mocker.patch.dict('os.environ', {'TERM': '', 'COLORTERM': ''})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.COLOR_8

    def test_detect_capability_caching(self, mocker):
        """Test that detect_capability caches the result after first call."""
        mocker.patch.dict('os.environ', {'TERM': 'xterm', 'COLORTERM': ''})
        detector = TerminalDetector()

        first_result = detector.detect_capability()
        assert first_result == TerminalCapability.COLOR_256

        # Change env after first call - should still return cached value
        mocker.patch.dict('os.environ', {'TERM': 'truecolor', 'COLORTERM': ''})
        second_result = detector.detect_capability()
        assert second_result == first_result

    def test_detect_capability_case_insensitive(self, mocker):
        """Test that TERM/COLORTERM values are lowercased for comparison."""
        mocker.patch.dict('os.environ', {'TERM': '', 'COLORTERM': 'TRUECOLOR'})
        detector = TerminalDetector()
        assert detector.detect_capability() == TerminalCapability.TRUE_COLOR

    def test_has_color_support_non_tty(self, mocker):
        """Test that non-TTY stdout results in no color support."""
        mocker.patch.object(sys.stdout, 'isatty', return_value=False)
        detector = TerminalDetector()
        assert detector.has_color_support() is False

    def test_has_color_support_tty_no_no_color(self, mocker):
        """Test that TTY stdout without NO_COLOR gives color support."""
        mocker.patch.object(sys.stdout, 'isatty', return_value=True)
        mocker.patch.dict('os.environ', {'TERM': 'xterm', 'COLORTERM': ''}, clear=False)
        # Ensure NO_COLOR is not set
        environ_copy = dict(__import__('os').environ)
        environ_copy.pop('NO_COLOR', None)
        mocker.patch.dict('os.environ', environ_copy, clear=True)
        mocker.patch.dict('os.environ', {'TERM': 'xterm', 'COLORTERM': ''})

        detector = TerminalDetector()
        assert detector.has_color_support() is True

    def test_has_color_support_no_color_env_set(self, mocker):
        """Test that NO_COLOR environment variable disables color support."""
        mocker.patch.object(sys.stdout, 'isatty', return_value=True)
        mocker.patch.dict('os.environ', {'NO_COLOR': '1', 'TERM': 'xterm', 'COLORTERM': ''})
        detector = TerminalDetector()
        assert detector.has_color_support() is False

    def test_has_color_support_caching(self, mocker):
        """Test that has_color_support caches the result after first call."""
        mocker.patch.object(sys.stdout, 'isatty', return_value=False)
        detector = TerminalDetector()

        first_result = detector.has_color_support()
        assert first_result is False

        # Even if we change stdout to a TTY, cached value should persist
        mocker.patch.object(sys.stdout, 'isatty', return_value=True)
        second_result = detector.has_color_support()
        assert second_result is False


class TestColorMapperRGBTo8Color:
    """Test ColorMapper._rgb_to_8_color with all 8 ANSI color combinations."""

    @pytest.fixture
    def mapper(self):
        """Create a ColorMapper instance for testing.

        Returns:
            ColorMapper: A fresh ColorMapper instance.

        """
        return ColorMapper()

    def test_black(self, mapper):
        """Test black color mapping (all channels below midpoint)."""
        result = mapper._rgb_to_8_color(0, 0, 0)
        assert result == '\033[30m'

    def test_red(self, mapper):
        """Test red color mapping (only red above midpoint)."""
        result = mapper._rgb_to_8_color(200, 0, 0)
        assert result == '\033[31m'

    def test_green(self, mapper):
        """Test green color mapping (only green above midpoint)."""
        result = mapper._rgb_to_8_color(0, 200, 0)
        assert result == '\033[32m'

    def test_yellow(self, mapper):
        """Test yellow color mapping (red and green above midpoint)."""
        result = mapper._rgb_to_8_color(200, 200, 0)
        assert result == '\033[33m'

    def test_blue(self, mapper):
        """Test blue color mapping (only blue above midpoint)."""
        result = mapper._rgb_to_8_color(0, 0, 200)
        assert result == '\033[34m'

    def test_magenta(self, mapper):
        """Test magenta color mapping (red and blue above midpoint)."""
        result = mapper._rgb_to_8_color(200, 0, 200)
        assert result == '\033[35m'

    def test_cyan(self, mapper):
        """Test cyan color mapping (green and blue above midpoint)."""
        result = mapper._rgb_to_8_color(0, 200, 200)
        assert result == '\033[36m'

    def test_white(self, mapper):
        """Test white color mapping (all channels above midpoint)."""
        result = mapper._rgb_to_8_color(255, 255, 255)
        assert result == '\033[37m'

    def test_midpoint_boundary_below(self, mapper):
        """Test colors just below the midpoint threshold are treated as off."""
        result = mapper._rgb_to_8_color(127, 127, 127)
        assert result == '\033[30m'  # All below midpoint = black

    def test_midpoint_boundary_at(self, mapper):
        """Test colors at exactly the midpoint threshold are treated as on."""
        result = mapper._rgb_to_8_color(128, 128, 128)
        assert result == '\033[37m'  # All at midpoint = white


class TestColorMapperRGBTo256Color:
    """Test ColorMapper._rgb_to_256_color method."""

    @pytest.fixture
    def mapper(self):
        """Create a ColorMapper instance for testing.

        Returns:
            ColorMapper: A fresh ColorMapper instance.

        """
        return ColorMapper()

    def test_grayscale_below_threshold(self, mapper):
        """Test grayscale ramp for very dark values below threshold."""
        result = mapper._rgb_to_256_color(5, 5, 5)
        assert result.startswith('\033[38;5;')
        # Extract color index
        color_index = int(result.split(';')[-1].rstrip('m'))
        assert 232 <= color_index <= 255  # Grayscale range

    def test_grayscale_above_threshold(self, mapper):
        """Test extended grayscale for values at/above threshold."""
        result = mapper._rgb_to_256_color(100, 100, 100)
        assert result.startswith('\033[38;5;')
        color_index = int(result.split(';')[-1].rstrip('m'))
        assert 232 <= color_index <= 255  # Grayscale range

    def test_color_cube_pure_red(self, mapper):
        """Test color cube mapping for pure red."""
        result = mapper._rgb_to_256_color(255, 0, 0)
        assert result.startswith('\033[38;5;')
        color_index = int(result.split(';')[-1].rstrip('m'))
        # Red in color cube: 16 + (5 * 36) + (0 * 6) + 0 = 196
        assert color_index == 196

    def test_color_cube_pure_green(self, mapper):
        """Test color cube mapping for pure green."""
        result = mapper._rgb_to_256_color(0, 255, 0)
        color_index = int(result.split(';')[-1].rstrip('m'))
        # Green in color cube: 16 + (0 * 36) + (5 * 6) + 0 = 46
        assert color_index == 46

    def test_color_cube_pure_blue(self, mapper):
        """Test color cube mapping for pure blue."""
        result = mapper._rgb_to_256_color(0, 0, 255)
        color_index = int(result.split(';')[-1].rstrip('m'))
        # Blue in color cube: 16 + (0 * 36) + (0 * 6) + 5 = 21
        assert color_index == 21

    def test_color_cube_mixed(self, mapper):
        """Test color cube mapping for a mixed color."""
        result = mapper._rgb_to_256_color(128, 128, 0)
        assert result.startswith('\033[38;5;')
        color_index = int(result.split(';')[-1].rstrip('m'))
        assert 16 <= color_index <= 231  # Within color cube range

    def test_grayscale_black(self, mapper):
        """Test grayscale mapping for pure black (r=g=b=0)."""
        result = mapper._rgb_to_256_color(0, 0, 0)
        assert result.startswith('\033[38;5;')
        color_index = int(result.split(';')[-1].rstrip('m'))
        assert color_index == 232  # Darkest grayscale


class TestColorMapperRGBToTrueColor:
    """Test ColorMapper._rgb_to_true_color method."""

    @pytest.fixture
    def mapper(self):
        """Create a ColorMapper instance for testing.

        Returns:
            ColorMapper: A fresh ColorMapper instance.

        """
        return ColorMapper()

    def test_true_color_red(self, mapper):
        """Test true color escape code for pure red."""
        result = mapper._rgb_to_true_color(255, 0, 0)
        assert result == '\033[38;2;255;0;0m'

    def test_true_color_green(self, mapper):
        """Test true color escape code for pure green."""
        result = mapper._rgb_to_true_color(0, 255, 0)
        assert result == '\033[38;2;0;255;0m'

    def test_true_color_blue(self, mapper):
        """Test true color escape code for pure blue."""
        result = mapper._rgb_to_true_color(0, 0, 255)
        assert result == '\033[38;2;0;0;255m'

    def test_true_color_arbitrary(self, mapper):
        """Test true color escape code for arbitrary RGB values."""
        result = mapper._rgb_to_true_color(123, 45, 67)
        assert result == '\033[38;2;123;45;67m'


class TestColorMapperGetColorCode:
    """Test ColorMapper.get_color_code with various capabilities."""

    def test_get_color_code_no_color_support(self, mocker):
        """Test that get_color_code returns empty string without color support."""
        mocker.patch.object(sys.stdout, 'isatty', return_value=False)
        mapper = ColorMapper()
        result = mapper.get_color_code(255, 0, 0)
        assert not result

    def test_get_color_code_true_color(self, mocker):
        """Test get_color_code with true color capability."""
        mocker.patch.object(sys.stdout, 'isatty', return_value=True)
        mocker.patch.dict('os.environ', {'TERM': '', 'COLORTERM': 'truecolor'})
        # Ensure NO_COLOR is not set
        environ_copy = dict(__import__('os').environ)
        environ_copy.pop('NO_COLOR', None)
        mocker.patch.dict('os.environ', environ_copy, clear=True)
        mocker.patch.dict('os.environ', {'TERM': '', 'COLORTERM': 'truecolor'})

        mapper = ColorMapper()
        result = mapper.get_color_code(100, 150, 200)
        assert result == '\033[38;2;100;150;200m'

    def test_get_color_code_256_color(self, mocker):
        """Test get_color_code with 256-color capability."""
        mocker.patch.object(sys.stdout, 'isatty', return_value=True)
        environ_copy = dict(__import__('os').environ)
        environ_copy.pop('NO_COLOR', None)
        mocker.patch.dict('os.environ', environ_copy, clear=True)
        mocker.patch.dict('os.environ', {'TERM': 'xterm-256color', 'COLORTERM': ''})

        mapper = ColorMapper()
        result = mapper.get_color_code(255, 0, 0)
        assert result.startswith('\033[38;5;')

    def test_get_color_code_8_color(self, mocker):
        """Test get_color_code with 8-color capability."""
        mocker.patch.object(sys.stdout, 'isatty', return_value=True)
        environ_copy = dict(__import__('os').environ)
        environ_copy.pop('NO_COLOR', None)
        mocker.patch.dict('os.environ', environ_copy, clear=True)
        mocker.patch.dict('os.environ', {'TERM': 'linux', 'COLORTERM': ''})

        mapper = ColorMapper()
        result = mapper.get_color_code(255, 0, 0)
        assert result == '\033[31m'

    def test_get_color_code_caching(self, mocker):
        """Test that get_color_code caches results for repeated calls."""
        mocker.patch.object(sys.stdout, 'isatty', return_value=True)
        environ_copy = dict(__import__('os').environ)
        environ_copy.pop('NO_COLOR', None)
        mocker.patch.dict('os.environ', environ_copy, clear=True)
        mocker.patch.dict('os.environ', {'TERM': '', 'COLORTERM': 'truecolor'})

        mapper = ColorMapper()
        first_result = mapper.get_color_code(100, 200, 50)
        second_result = mapper.get_color_code(100, 200, 50)
        assert first_result == second_result
        assert (100, 200, 50) in mapper._color_cache

    def test_get_color_code_monochrome_via_mock(self, mocker):
        """Test get_color_code returns empty when capability is MONOCHROME."""
        mapper = ColorMapper()
        mocker.patch.object(mapper.detector, 'has_color_support', return_value=True)
        mapper._capability = TerminalCapability.MONOCHROME
        result = mapper.get_color_code(255, 0, 0)
        assert not result


class TestColorMapperGetResetCode:
    """Test ColorMapper.get_reset_code method."""

    def test_get_reset_code_with_color_support(self, mocker):
        """Test reset code returns escape sequence when colors are supported."""
        mapper = ColorMapper()
        mocker.patch.object(mapper.detector, 'has_color_support', return_value=True)
        assert mapper.get_reset_code() == '\033[0m'

    def test_get_reset_code_without_color_support(self, mocker):
        """Test reset code returns empty string without color support."""
        mapper = ColorMapper()
        mocker.patch.object(mapper.detector, 'has_color_support', return_value=False)
        assert not mapper.get_reset_code()


class TestColorMapperClearCache:
    """Test ColorMapper.clear_cache method."""

    def test_clear_cache_empties_color_cache(self):
        """Test that clear_cache empties the internal color cache."""
        mapper = ColorMapper()
        mapper._color_cache[255, 0, 0] = '\033[31m'
        mapper._capability = TerminalCapability.COLOR_8

        mapper.clear_cache()

        assert mapper._color_cache == {}
        assert mapper._capability is None


class TestModuleConstants:
    """Test module-level constants."""

    def test_ansi_color_channel_midpoint(self):
        """Test ANSI_COLOR_CHANNEL_MIDPOINT constant value."""
        assert ANSI_COLOR_CHANNEL_MIDPOINT == 128

    def test_ansi_256_grayscale_ramp_threshold(self):
        """Test ANSI_256_GRAYSCALE_RAMP_THRESHOLD constant value."""
        assert ANSI_256_GRAYSCALE_RAMP_THRESHOLD == 8
