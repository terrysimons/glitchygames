"""glitchygames/testing/text_metrics.py: what this machine's fonts measure, to compare platforms.

The report is a measurement, so no test compares a width with a number: a width that differs on
another platform is what the report is for (PR #328). The tests check what the report holds and
that its numbers agree with each other.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames.fonts import font_manager
from glitchygames.process import OutputCapture, run_command
from glitchygames.testing import text_metrics

if TYPE_CHECKING:
    from pathlib import Path

# A character neither font has a glyph for
MISSING_CHARACTER = '中'

# Starting Python, pygame and the engine, then measuring: about a second here
CHILD_TIMEOUT_SECONDS = 120


@pytest.fixture(scope='module')
def report() -> text_metrics.TextMetricsReport:
    """Return this machine's report (measured once: every test reads the same one).

    Returns:
        The report.

    """
    return text_metrics.measure_text_metrics()


class TestTheReport:
    """What a report holds, and that its numbers agree with each other."""

    def test_the_report_is_kept_in_test_results_for_ci(self, report, pytestconfig):
        # CI stores test-results/ from every machine (Windows' too), even when tests fail
        report_path = (
            pytestconfig.rootpath / 'test-results' / 'text-metrics' / f'{sys.platform}.json'
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report.model_dump_json(indent=2), encoding='utf-8')
        kept = report_path.read_text(encoding='utf-8')
        assert text_metrics.TextMetricsReport.model_validate_json(kept) == report

    def test_the_report_measures_every_hud_text_in_both_fonts(self, report):
        assert [(fonts.font, fonts.point_size) for fonts in report.fonts] == [
            ('default', text_metrics.HUD_POINT_SIZE),
            (font_manager.DEFAULT_FONT_NAME, text_metrics.HUD_POINT_SIZE),
        ]
        for fonts in report.fonts:
            assert tuple(measurement.text for measurement in fonts.texts) == text_metrics.HUD_TEXTS

    def test_the_texts_include_both_games_first_frames_and_the_widths_that_differed(self):
        for text in ('Score: 0', 'Score: 10', 'Score: 100', 'Lives: 3', 'Floor: Boiler Room'):
            assert text in text_metrics.HUD_TEXTS

    def test_each_text_has_one_glyph_per_character_and_their_advances_sum(self, report):
        for fonts in report.fonts:
            for measurement in fonts.texts:
                glyphs = [glyph for glyph in measurement.glyphs if glyph is not None]
                assert [glyph.character for glyph in glyphs] == list(measurement.text)
                assert measurement.advance_sum == sum(glyph.advance for glyph in glyphs)

    def test_the_sizes_are_what_pygame_measures_for_the_same_font(self, report):
        font = pygame.font.Font(None, text_metrics.HUD_POINT_SIZE)
        default_font = report.fonts[0]
        for measurement in default_font.texts:
            assert measurement.size == font.size(measurement.text)
            assert measurement.rendered_size_aliased == (
                font.render(measurement.text, antialias=False, color=(255, 255, 255)).get_size()
            )

    def test_the_report_names_the_versions_it_can_read_and_says_which_it_cannot(self, report):
        pygame.font.init()
        assert report.sdl_ttf_version == pygame.font.get_sdl_ttf_version(linked=True)
        assert report.pygame_version == pygame.version.ver
        assert report.sdl_ttf_built_in_libraries == text_metrics.SDL_TTF_BUILT_IN_LIBRARIES
        assert 'unknown' in report.sdl_ttf_built_in_libraries

    def test_a_character_a_font_has_no_glyph_for_has_no_metrics(self, mocker):
        # Font.metrics gives None for a character the font cannot map (pygame's documentation),
        # but both fonts draw a fallback box for any character, so a stand-in font keeps that
        # contract (pygame's Font is a C type: its methods cannot be patched)
        real_font = pygame.font.Font

        class FontWithoutGlyphs:
            def __init__(self, path: Path | None, point_size: int) -> None:
                self._font = real_font(path, point_size)

            def size(self, text: str) -> tuple[int, int]:
                return self._font.size(text)

            def render(
                self, text: str, *, antialias: bool, color: tuple[int, int, int]
            ) -> pygame.Surface:
                return self._font.render(text, antialias=antialias, color=color)

            def metrics(self, text: str) -> list[None]:
                return [None for _character in text]

        mocker.patch.object(pygame.font, 'Font', FontWithoutGlyphs)
        report = text_metrics.measure_text_metrics(texts=(MISSING_CHARACTER,))
        for fonts in report.fonts:
            (measurement,) = fonts.texts
            assert measurement.glyphs == [None]
            assert measurement.advance_sum == 0

    def test_main_prints_the_report_as_json(self, capsys):
        text_metrics.main()
        printed = text_metrics.TextMetricsReport.model_validate_json(capsys.readouterr().out)
        assert tuple(measurement.text for measurement in printed.fonts[0].texts) == (
            text_metrics.HUD_TEXTS
        )

    def test_python_dash_m_prints_the_report_as_json(self):
        # A child process, not runpy in this one: CI tests the installed copy, whose every
        # glitchygames module pytest marks for assertion rewriting (the distribution declares a
        # pytest11 plugin), and runpy cannot run a module through that loader (it has no
        # get_code). The documented command hides pygame's banner, as here.
        result = run_command(
            command=[sys.executable, '-m', text_metrics.__name__],
            environment={**os.environ, 'PYGAME_HIDE_SUPPORT_PROMPT': '1'},
            timeout_seconds=CHILD_TIMEOUT_SECONDS,
            capture_output=OutputCapture.APART,
        )
        assert result.returncode == 0, result.stderr
        printed = text_metrics.TextMetricsReport.model_validate_json(result.stdout)
        assert tuple(measurement.text for measurement in printed.fonts[0].texts) == (
            text_metrics.HUD_TEXTS
        )
