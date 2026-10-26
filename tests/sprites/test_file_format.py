"""The sprite file-format check belongs to the engine: Bitmappy imports it, not the reverse."""

from __future__ import annotations

import pytest

from glitchygames.sprites import animated
from glitchygames.sprites.file_format import detect_file_format


@pytest.mark.parametrize('filename', ['ball.toml', 'BALL.TOML', 'ball'])
def test_toml_and_bare_names_are_toml(filename):
    """A .toml name (any case) and a name with no extension are TOML."""
    assert detect_file_format(filename) == 'toml'


def test_another_format_is_refused_by_name():
    """Any other extension is refused, naming it."""
    with pytest.raises(ValueError, match=r'Unsupported file format: \.yaml'):
        detect_file_format('ball.yaml')


def test_the_engine_reaches_no_bitmappy_module():
    """The animated sprite uses the engine's check itself, with no fallback copy."""
    assert animated.detect_file_format is detect_file_format
