"""The frame-phase probe's summaries and surface audit (scripts/frame_phase_probe.py)."""

from __future__ import annotations

from typing import Any

import pygame
import pytest
from scripts import frame_phase_probe
from scripts.frame_phase_probe import (
    HITCH_FACTOR,
    PHASE_NAMES,
    audit_surfaces,
    distribution,
    summarize,
    summarize_ticks,
    surface_format,
)

FRAME_SECONDS = 1 / 60


def frame_row(*, start: float, phases: dict[str, float] | None = None) -> dict[str, Any]:
    """Return a row as the probe records one (``FrameProbe._begin_frame`` and ``_end_frame``).

    Returns:
        The row.

    """
    return {
        'start': start,
        'scene': 'TitleScene',
        'game_time': start,
        'phases': phases or {'render_scene': 0.0004},
        'gc_pauses': [],
        'sprites_blitted': 5,
        'rect_count': 5,
        'rect_area': 66616,
        'duration': 0.0006,
    }


def tick(*, seconds: float, ran_frame: bool) -> dict[str, Any]:
    """Return a tick as the probe records one (its pacer wrapper).

    Returns:
        The tick.

    """
    return {
        'tick_seconds': seconds,
        'period_seconds': FRAME_SECONDS,
        'accumulated_before': 0.0,
        'accumulated_after': 0.0,
        'ticks_since_frame_before': 1,
        'ticks_since_frame_after': 0 if ran_frame else 1,
        'measured_tick_seconds': FRAME_SECONDS / 2,
        'ran_frame': ran_frame,
    }


class TestWrappedNames:
    """The engine names the probe wraps or reads by string still exist.

    The probe patches private SceneManager and TickPacer members by name, so a rename in the
    engine would otherwise break it only when someone next measures a browser.
    """

    def test_every_scene_manager_method_the_probe_wraps_exists(self):
        from glitchygames.scenes import scene as scene_module

        names = [frame_phase_probe.FRAME_METHOD, *frame_phase_probe.MANAGER_PHASES.values()]
        missing = [
            name for name in names if not callable(getattr(scene_module.SceneManager, name, None))
        ]
        assert missing == []

    def test_every_drawing_and_display_function_the_probe_wraps_exists(self):
        from glitchygames.scenes import scene as scene_module

        owners_and_names = [
            (pygame.sprite.LayeredDirty, 'clear'),
            (pygame.sprite.LayeredDirty, frame_phase_probe.DRAW_METHOD),
            (scene_module, 'make_opaque'),
            (pygame.display, 'update'),
            (pygame.display, 'flip'),
        ]
        missing = [
            name for owner, name in owners_and_names if not callable(getattr(owner, name, None))
        ]
        assert missing == []

    def test_the_pacer_method_and_both_counts_the_probe_reads_exist(self):
        from glitchygames import host

        pacer = host.TickPacer()
        assert callable(getattr(pacer, frame_phase_probe.PACER_METHOD, None))
        assert isinstance(getattr(pacer, frame_phase_probe.PACER_ACCUMULATOR), float)
        assert isinstance(getattr(pacer, frame_phase_probe.PACER_TICK_COUNT), int)


class TestDistribution:
    """``distribution``: count, median, nearest-rank percentiles and maximum."""

    def test_no_values_is_all_zero(self):
        assert distribution(values=[]) == {
            'count': 0,
            'median': 0.0,
            'p95': 0.0,
            'p99': 0.0,
            'max': 0.0,
        }

    def test_percentiles_are_nearest_rank(self):
        """Of 1 to 100, the 95th percentile is 95 and the 99th is 99 (nearest rank)."""
        result = distribution(values=[float(value) for value in range(100, 0, -1)])

        assert result == {'count': 100, 'median': 50.5, 'p95': 95.0, 'p99': 99.0, 'max': 100.0}

    def test_every_statistic_lies_within_the_values(self):
        values = [0.3, 0.1, 0.9, 0.4]
        result = distribution(values=values)

        assert min(values) <= result['median'] <= result['p95'] <= result['p99'] <= result['max']
        assert result['max'] == max(values)


class TestSummarize:
    """``summarize``: the frames' phases, intervals and hitches."""

    def test_even_frames_have_no_hitches(self):
        rows = [frame_row(start=index * FRAME_SECONDS) for index in range(60)]

        summary = summarize(rows=rows)

        assert summary['frames'] == 60
        assert summary['hitches'] == []
        assert summary['interval_seconds']['median'] == pytest.approx(FRAME_SECONDS)

    def test_a_late_frame_is_a_hitch_named_by_the_frame_before_it(self):
        starts = [index * FRAME_SECONDS for index in range(10)]
        # The gap after the sixth frame is two frames long
        starts[6:] = [start + FRAME_SECONDS for start in starts[6:]]
        rows = [frame_row(start=start) for start in starts]
        rows[5]['phases'] = {'sprites_draw': 0.002, 'display_update': 0.001}

        hitches = summarize(rows=rows)['hitches']

        assert len(hitches) == 1
        assert hitches[0]['game_time'] == rows[5]['game_time']
        assert hitches[0]['interval'] == pytest.approx(2 * FRAME_SECONDS)
        assert hitches[0]['slowest_phase'] == 'sprites_draw'

    def test_a_gap_at_the_hitch_factor_is_not_a_hitch(self):
        """Only intervals over HITCH_FACTOR times the median count."""
        starts = [index * FRAME_SECONDS for index in range(10)]
        starts[6:] = [start + (HITCH_FACTOR - 1) * FRAME_SECONDS * 0.99 for start in starts[6:]]

        assert summarize(rows=[frame_row(start=start) for start in starts])['hitches'] == []

    def test_every_phase_is_summarized_even_where_it_never_ran(self):
        summary = summarize(rows=[frame_row(start=0.0), frame_row(start=FRAME_SECONDS)])

        assert tuple(summary['phase_seconds']) == PHASE_NAMES
        assert summary['phase_seconds']['display_flip']['max'] == 0.0


class TestSummarizeTicks:
    """``summarize_ticks``: the outer ticks and how many each frame waited."""

    def test_sixty_fps_on_one_hundred_twenty_hertz_waits_two_ticks_a_frame(self):
        ticks = [
            tick(seconds=index * FRAME_SECONDS / 2, ran_frame=index % 2 == 0) for index in range(20)
        ]

        pacing = summarize_ticks(ticks=ticks)

        assert pacing['ticks'] == 20
        assert pacing['ticks_per_frame'] == {'2': 9}
        assert pacing['skipped_tick_gaps'] == []

    def test_uneven_waits_are_counted_by_length(self):
        """The judder measured in Chrome at 120 Hz: a frame after one tick, then after three."""
        ran = [True, False, True, True, False, False, True, False, True]
        ticks = [
            tick(seconds=index * FRAME_SECONDS / 2, ran_frame=runs)
            for index, runs in enumerate(ran)
        ]

        assert summarize_ticks(ticks=ticks)['ticks_per_frame'] == {'1': 1, '2': 2, '3': 1}

    def test_a_late_tick_is_a_skipped_tick_gap(self):
        seconds = [index * FRAME_SECONDS / 2 for index in range(10)]
        seconds[7:] = [value + FRAME_SECONDS for value in seconds[7:]]
        ticks = [tick(seconds=value, ran_frame=True) for value in seconds]

        gaps = summarize_ticks(ticks=ticks)['skipped_tick_gaps']

        assert [gap['tick_seconds'] for gap in gaps] == [seconds[7]]

    def test_no_ticks_summarize_to_nothing(self):
        assert summarize_ticks(ticks=[]) == {
            'ticks': 0,
            'interval_seconds': distribution(values=[]),
            'ticks_per_frame': {},
            'skipped_tick_gaps': [],
        }


class TestSurfaceAudit:
    """``audit_surfaces`` and ``surface_format``: what decides each sprite's blit cost."""

    def test_a_per_pixel_alpha_image_in_the_display_format_matches_it(self):
        display = pygame.Surface((80, 48), depth=32)
        image = pygame.Surface((10, 10), pygame.SRCALPHA, depth=32)
        sprite = pygame.sprite.DirtySprite()
        sprite.image = image
        sprite.dirty = 2

        audit = audit_surfaces(display=display, sprites=[sprite])

        (audited,) = audit['sprites']
        assert audited['format']['per_pixel_alpha'] is True
        assert audited['dirty'] == 2
        assert audited['matches_display'] is (
            image.get_bitsize() == display.get_bitsize()
            and image.get_masks()[:3] == display.get_masks()[:3]
        )

    def test_an_image_of_another_depth_does_not_match(self):
        display = pygame.Surface((80, 48), depth=32)
        sprite = pygame.sprite.DirtySprite()
        sprite.image = pygame.Surface((10, 10), depth=16)

        (audited,) = audit_surfaces(display=display, sprites=[sprite])['sprites']

        assert audited['matches_display'] is False

    def test_without_a_display_nothing_matches_and_spriteless_images_are_skipped(self):
        imaged = pygame.sprite.DirtySprite()
        imaged.image = pygame.Surface((4, 4))
        imageless = pygame.sprite.DirtySprite()

        audit = audit_surfaces(display=None, sprites=[imaged, imageless])

        assert audit['display'] is None
        assert [entry['matches_display'] for entry in audit['sprites']] == [False]

    def test_surface_format_reports_a_colorkey(self):
        surface = pygame.Surface((4, 4), depth=32)
        surface.set_colorkey((255, 0, 255))

        assert surface_format(surface=surface)['colorkey'][:3] == [255, 0, 255]


def test_the_report_marker_is_one_console_line_prefix():
    """measure_browser_frames finds the report by this prefix on a console line."""
    assert frame_phase_probe.REPORT_MARKER.endswith(' ')
    assert '\n' not in frame_phase_probe.REPORT_MARKER
