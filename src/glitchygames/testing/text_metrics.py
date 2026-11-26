"""What this machine's fonts measure: a triage tool for comparing text widths across platforms.

PR #328's recordings replayed on macOS and Linux but not on Windows, where Brave Adventurer's and
Clockwork Keep's HUD text (pygame's default font, freesansbold, at 28 points) rendered one pixel
narrower: ``Score: 10`` 88 pixels wide on macOS and 87 on Windows, ``Score: 0`` 77 and 76. The
font file is the same in every wheel, so the difference is in how each platform's SDL_ttf lays
the text out. This module measures that, the same way on every machine, so two platforms'
reports can be compared line by line.

For each font (pygame's default and the engine's bundled Vera) and each text in ``HUD_TEXTS`` it
records ``Font.size()``, the rendered surface's size with and without antialiasing, every
glyph's ``Font.metrics()`` (min x, max x, min y, max y, advance) and the sum of the advances.
SDL_ttf makes a line's width from the advances, and from the glyphs' ink where that reaches
further (``Score: 100`` on macOS: the advances sum to 99, the width is 100), so both are kept.

It also records the versions it can read: pygame's, SDL's and SDL_ttf's. pygame does not expose
the FreeType and HarfBuzz that SDL_ttf was built with (Windows' SDL2_ttf.dll carries its own
copies inside it), so the report says so rather than guess. ``pygame.freetype``'s FreeType is
pygame's own copy, used by ``pygame.freetype`` only, and is labeled that way.

Two ways to read it:

- ``PYGAME_HIDE_SUPPORT_PROMPT=1 uv run python -m glitchygames.testing.text_metrics`` prints the
  report as JSON. Without the variable pygame's banner comes first: running the module imports
  the ``glitchygames`` package, and pygame with it, before this module could hide it.
- tests/testing/test_text_metrics.py writes the same JSON to
  ``test-results/text-metrics/<sys.platform>.json``, which CI keeps: CircleCI's Windows job
  stores its ``test-results/`` as an artifact on each machine of its split, even when tests
  fail, so the report is in the artifacts of whichever machine ran that test file. (Not in the
  JUnit record: ``record_property`` warns under the xunit2 report, an error in CI's serial run,
  and tests/test_suite_collection.py refuses it.)
"""

from __future__ import annotations

import platform
import sys

import pygame
import pygame.freetype
from pydantic import BaseModel, ConfigDict

from glitchygames.fonts import font_manager

# The point size both games' HUDs use
HUD_POINT_SIZE = 28

# The texts measured: both games' HUD texts as their first frames show them, the numbers around
# them, Clockwork Keep's floor names (clockwork_keep/levels.py; the engine never imports a game)
# and single glyphs, whose advances add up to each line's
HUD_TEXTS: tuple[str, ...] = (
    *tuple(f'Score: {score}' for score in range(11)),
    'Score: 100',
    'Score: 1250',
    *tuple(f'Lives: {lives}' for lives in range(6)),
    'Floor: Boiler Room',
    'Floor: Gear Works',
    'Floor: Clock Face',
    'S',
    'c',
    ':',
    ' ',
)

# Said in every report, since no pygame call can read them
SDL_TTF_BUILT_IN_LIBRARIES = (
    'unknown: pygame does not expose the FreeType or HarfBuzz versions SDL_ttf was built with'
)


class GlyphMetrics(BaseModel):
    """One glyph's ``Font.metrics()``, in pixels.

    Attributes:
        character: The glyph's character.
        min_x: The ink's left edge, from the pen position.
        max_x: The ink's right edge, from the pen position.
        min_y: The ink's bottom, from the baseline.
        max_y: The ink's top, from the baseline.
        advance: How far the pen moves after the glyph.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    character: str
    min_x: int
    max_x: int
    min_y: int
    max_y: int
    advance: int


class TextMeasurement(BaseModel):
    """What one font measures for one text.

    Attributes:
        text: The text.
        size: ``Font.size(text)``.
        rendered_size_antialiased: The size of ``Font.render(text, True, ...)``.
        rendered_size_aliased: The size of ``Font.render(text, False, ...)``.
        glyphs: Each character's metrics (None: the font has no glyph for it).
        advance_sum: The sum of the glyphs' advances.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    text: str
    size: tuple[int, int]
    rendered_size_antialiased: tuple[int, int]
    rendered_size_aliased: tuple[int, int]
    glyphs: list[GlyphMetrics | None]
    advance_sum: int


class FontMeasurements(BaseModel):
    """One font's measurements of every text.

    Attributes:
        font: Which font: ``default`` (pygame's freesansbold) or ``Vera`` (bundled).
        point_size: The size it was opened at.
        texts: One measurement per text, in ``HUD_TEXTS`` order.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    font: str
    point_size: int
    texts: list[TextMeasurement]


class TextMetricsReport(BaseModel):
    """Everything this machine measures, and the versions behind it.

    Attributes:
        platform: ``platform.platform()``.
        machine: ``platform.machine()``.
        python_version: The running Python's version.
        pygame_version: pygame's version.
        sdl_version: The SDL pygame is linked with.
        sdl_ttf_version: The SDL_ttf pygame is linked with.
        sdl_ttf_built_in_libraries: Always ``SDL_TTF_BUILT_IN_LIBRARIES``.
        pygame_freetype_version: The FreeType of ``pygame.freetype``, not SDL_ttf's.
        fonts: Each font's measurements.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    platform: str
    machine: str
    python_version: str
    pygame_version: str
    sdl_version: tuple[int, int, int]
    sdl_ttf_version: tuple[int, int, int]
    sdl_ttf_built_in_libraries: str
    pygame_freetype_version: tuple[int, int, int]
    fonts: list[FontMeasurements]


def _glyph_metrics(*, character: str, metrics: tuple[int, ...] | None) -> GlyphMetrics | None:
    if metrics is None:
        return None
    min_x, max_x, min_y, max_y, advance = metrics
    return GlyphMetrics(
        character=character, min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y, advance=advance
    )


def _measure_text(*, font: pygame.font.Font, text: str) -> TextMeasurement:
    color = (255, 255, 255)
    glyphs = [
        _glyph_metrics(character=character, metrics=metrics)
        for character, metrics in zip(text, font.metrics(text), strict=True)
    ]
    return TextMeasurement(
        text=text,
        size=font.size(text),
        rendered_size_antialiased=font.render(text, antialias=True, color=color).get_size(),
        rendered_size_aliased=font.render(text, antialias=False, color=color).get_size(),
        glyphs=glyphs,
        advance_sum=sum(glyph.advance for glyph in glyphs if glyph is not None),
    )


def _version(version: tuple[int, ...]) -> tuple[int, int, int]:
    major, minor, patch = version
    return (major, minor, patch)


def measure_text_metrics(
    *, texts: tuple[str, ...] = HUD_TEXTS, point_size: int = HUD_POINT_SIZE
) -> TextMetricsReport:
    """Measure each text in pygame's default font and the bundled Vera.

    Args:
        texts: The texts to measure.
        point_size: The size to open both fonts at.

    Returns:
        The report.

    """
    pygame.font.init()
    vera_path = font_manager.BUNDLED_FONT_DIRECTORY / font_manager.BUNDLED_FONT_FILE_NAMES['vera']
    fonts = {
        'default': pygame.font.Font(None, point_size),
        font_manager.DEFAULT_FONT_NAME: pygame.font.Font(vera_path, point_size),
    }
    return TextMetricsReport(
        platform=platform.platform(),
        machine=platform.machine(),
        python_version=sys.version.split()[0],
        pygame_version=pygame.version.ver,
        sdl_version=_version(pygame.version.SDL),
        sdl_ttf_version=_version(pygame.font.get_sdl_ttf_version(linked=True)),
        sdl_ttf_built_in_libraries=SDL_TTF_BUILT_IN_LIBRARIES,
        pygame_freetype_version=_version(pygame.freetype.get_version(linked=True)),
        fonts=[
            FontMeasurements(
                font=name,
                point_size=point_size,
                texts=[_measure_text(font=font, text=text) for text in texts],
            )
            for name, font in fonts.items()
        ],
    )


def main() -> None:
    """Print this machine's report as JSON."""
    sys.stdout.write(measure_text_metrics().model_dump_json(indent=2) + '\n')


if __name__ == '__main__':
    main()
