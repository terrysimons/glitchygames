"""Tests for the color constants module (glitchygames/color/constants.py)."""

import pytest
from pygame import Color

from glitchygames.color import constants


class TestColorConversionHelpers:
    """The module-initialization helpers accept only pygame Colors."""

    def test_to_rgb_drops_the_alpha_channel(self):
        """_to_rgb returns the red, green and blue channels as a plain tuple."""
        assert constants._to_rgb(color=Color(1, 2, 3, 4)) == (1, 2, 3)

    def test_to_rgba_keeps_the_alpha_channel(self):
        """_to_rgba returns all four channels as a plain tuple."""
        assert constants._to_rgba(color=Color(1, 2, 3, 4)) == (1, 2, 3, 4)

    def test_to_rgb_rejects_a_tuple(self):
        """A non-Color (here a tuple, or the None a bad palette index answers) is a TypeError."""
        with pytest.raises(TypeError, match=r'Expected pygame\.Color, got tuple'):
            constants._to_rgb(color=(1, 2, 3))

    def test_to_rgba_rejects_none(self):
        """None (what get_color answers past the palette's end) is a TypeError."""
        with pytest.raises(TypeError, match=r'Expected pygame\.Color, got NoneType'):
            constants._to_rgba(color=None)

    def test_named_constants_are_plain_tuples(self):
        """The exported named colors are tuples, not pygame Colors."""
        assert type(constants.YELLOW) is tuple
        assert len(constants.YELLOW) == constants.RGB_COMPONENT_COUNT
