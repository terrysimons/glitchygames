"""Tests for the debug overlay's Audio panel (sound engine impl spec 10.5), asserted on pixels."""

import types

import pygame
import pytest

from glitchygames.audio.accounting import CompileRecord
from glitchygames.audio.engine import AudioDiagnosticsSnapshot
from glitchygames.audio.library import CacheMode
from glitchygames.audio.voices import ChannelState
from glitchygames.camera import Camera2D
from glitchygames.debug.overlay import (
    GRAPH_WINDOW_SECONDS,
    DebugOverlay,
    DebugPanel,
    load_debug_font,
)
from glitchygames.debug.panels import (
    AUDIO_CACHE_COLOR,
    AUDIO_COMPILE_COLOR,
    AUDIO_DECODE_COLOR,
    AUDIO_FRAME_OUTLINE_COLOR,
    AUDIO_LABEL_WIDTH,
    AUDIO_LIVE_COLOR,
    AUDIO_PANEL_TOP,
    AUDIO_SECTION_GAP,
    GRAPH_HEIGHT,
    GRAPH_WIDTH,
    HUD_LINE_HEIGHT,
    HUD_MARGIN,
    TARGET_LINE_COLOR,
    DebugFrameInfo,
    draw_audio_header,
    draw_audio_panel,
    draw_performance_panel,
)

SURFACE_SIZE = (640, 480)
FRAME_SECONDS = 0.01  # 100 pixels per second: one pixel per frame on the 200 pixel graph
FULL_WINDOW_FRAMES = 200  # GRAPH_WINDOW_SECONDS / FRAME_SECONDS
PIXELS_PER_FRAME = 1
CHANNEL_STATE_COLOURS = {
    'idle': (60, 60, 60),
    'playing': (80, 200, 100),
    'fading': (230, 200, 60),
    'paused': (120, 120, 200),
}
# The left column below the header: where the strip, the meters and the log are drawn
LEFT_COLUMN = pygame.Rect(0, 0, SURFACE_SIZE[0] - GRAPH_WIDTH - 2 * HUD_MARGIN, SURFACE_SIZE[1])
COMPILE_LOG_TOP = 180  # under the header (to y=118), strip (to 158) and two bus meters
COMPILE_LOG_AREA = pygame.Rect(0, COMPILE_LOG_TOP, LEFT_COLUMN.width, SURFACE_SIZE[1])
HEADER_AREA = pygame.Rect(0, 0, LEFT_COLUMN.width, 120)


@pytest.fixture(autouse=True)
def initialized_pygame():
    """Initialise pygame (fonts) for tests that draw real text."""
    pygame.init()


@pytest.fixture
def display():
    """A real, black surface (no assumption about the window's pixel format).

    Returns:
        A pygame.Surface.
    """
    return pygame.Surface(SURFACE_SIZE)


@pytest.fixture
def font():
    """The overlay's own bundled font.

    Returns:
        The debug font.
    """
    return load_debug_font()


def snapshot_with(**overrides):
    """Build an AudioDiagnosticsSnapshot (defaults: cache ram, a quiet engine, 4 + 32 + 8 channels).

    Returns:
        The snapshot.
    """
    channels = tuple(
        ChannelState(index=index, group=group, state='idle')
        for index, group in enumerate(['live'] * 4 + ['library'] * 32 + ['legacy'] * 8)
    )
    arguments = {
        'cache_mode': CacheMode.RAM,
        'device': '44100 Hz, 16-bit signed, 2 channels, driver dummy',
        'voices_live': 0,
        'voices_library': 0,
        'voices_legacy': 0,
        'compiles_last_second': 0,
        'cache_hit_rate': None,
        'frame_work_by_kind': {},
        'frame_processing_seconds': None,
        'channels': channels,
        'bus_levels': {'master': 1.0, 'sfx': 0.5},
        'muted_buses': frozenset(),
        'compile_log': (),
    }
    arguments.update(overrides)
    return AudioDiagnosticsSnapshot(**arguments)


def frame_info_with(audio=None, *, target_fps=60.0):
    """Build a DebugFrameInfo carrying an audio snapshot.

    Returns:
        The frame info.
    """
    return DebugFrameInfo(
        target_fps=target_fps,
        audio=audio,
        rumble_levels=(0.0, 0.0),
        screen_shake_offset=(0.0, 0.0),
        mouse_position=None,
    )


def overlay_with_audio_history(*, work_by_frame):
    """Build an overlay whose history holds frames of FRAME_SECONDS with the given audio work.

    Args:
        work_by_frame: Per frame, oldest first, the audio work in seconds by kind.

    Returns:
        The overlay.
    """
    overlay = DebugOverlay(visible=True)
    for work in work_by_frame:
        overlay.record_frame(frame_seconds=FRAME_SECONDS, audio_work_by_kind=work)
    return overlay


def audio_graph_rect():
    """The audio-time graph's rect: the frame-time graph's place, in the bottom-right corner.

    Returns:
        The rect.
    """
    return pygame.Rect(
        SURFACE_SIZE[0] - HUD_MARGIN - GRAPH_WIDTH,
        SURFACE_SIZE[1] - HUD_MARGIN - GRAPH_HEIGHT - HUD_LINE_HEIGHT,
        GRAPH_WIDTH,
        GRAPH_HEIGHT,
    )


def audio_graph_column_rect(*, frame, frames=FULL_WINDOW_FRAMES):
    """The graph columns of one frame, when the newest of ``frames`` frames is at the right edge.

    Returns:
        The rect covering the frame's columns, the whole height of the graph.
    """
    graph_rect = audio_graph_rect()
    frames_after = frames - 1 - frame
    right_edge = graph_rect.right - frames_after * PIXELS_PER_FRAME
    return pygame.Rect(
        right_edge - PIXELS_PER_FRAME, graph_rect.top, PIXELS_PER_FRAME, GRAPH_HEIGHT
    )


def channel_strip_area(*, font, snapshot):
    """The channel strip's cells (not its labels): under the header, right of the labels.

    Returns:
        The rect.
    """
    scratch = pygame.Surface(SURFACE_SIZE)
    header_bottom = draw_audio_header(
        surface=scratch, font=font, frame_info=frame_info_with(snapshot), top=AUDIO_PANEL_TOP
    )
    return pygame.Rect(
        HUD_MARGIN + AUDIO_LABEL_WIDTH,
        header_bottom + AUDIO_SECTION_GAP,
        LEFT_COLUMN.width,
        3 * 12,
    )


def colour_count_in(surface, area, colour):
    """Count pixels of an exact RGB colour inside an area (alpha ignored).

    Returns:
        The number of matching pixels.
    """
    clipped = area.clip(surface.get_rect())
    return sum(
        1
        for x in range(clipped.left, clipped.right)
        for y in range(clipped.top, clipped.bottom)
        if tuple(surface.get_at((x, y)))[:3] == colour
    )


def colour_present_in(surface, area, colour):
    """Report whether an exact RGB colour is drawn inside an area.

    Returns:
        True when at least one pixel has the colour.
    """
    return colour_count_in(surface, area, colour) > 0


def quiet_history(*, frames=FULL_WINDOW_FRAMES):
    """Build an overlay history of ``frames`` frames with no audio work.

    Returns:
        The overlay.
    """
    return overlay_with_audio_history(work_by_frame=[{}] * frames)


class TestAudioTimeGraph:
    """One bar per frame, stacked by kind of audio work, over the frame-time graph's window."""

    def test_a_gameplay_compile_draws_a_compile_coloured_bar_in_its_frame_column(
        self, display, font
    ):
        """A compile at a known frame puts the compile colour in that frame's columns only."""
        work_by_frame = [{}] * FULL_WINDOW_FRAMES
        work_by_frame[10] = {'compile': 0.004}
        overlay = overlay_with_audio_history(work_by_frame=work_by_frame)
        draw_audio_panel(
            surface=display, overlay=overlay, font=font, frame_info=frame_info_with(snapshot_with())
        )
        assert colour_present_in(display, audio_graph_column_rect(frame=10), AUDIO_COMPILE_COLOR)
        assert not colour_present_in(
            display, audio_graph_column_rect(frame=50), AUDIO_COMPILE_COLOR
        )

    def test_the_bar_is_stacked_by_kind(self, display, font):
        """A frame with every kind of work shows all four colours in its columns."""
        work_by_frame = [{}] * FULL_WINDOW_FRAMES
        work_by_frame[100] = {
            'compile': 0.004,
            'decode': 0.004,
            'live_chunk': 0.004,
            'cache_read': 0.004,
        }
        overlay = overlay_with_audio_history(work_by_frame=work_by_frame)
        draw_audio_panel(
            surface=display, overlay=overlay, font=font, frame_info=frame_info_with(snapshot_with())
        )
        column = audio_graph_column_rect(frame=100)
        for colour in (
            AUDIO_COMPILE_COLOR,
            AUDIO_DECODE_COLOR,
            AUDIO_LIVE_COLOR,
            AUDIO_CACHE_COLOR,
        ):
            assert colour_present_in(display, column, colour)

    def test_an_unknown_kind_is_drawn_in_the_cache_colour(self, display, font):
        """The summed 'other' entry has no colour of its own: it is drawn like a cache read."""
        work_by_frame = [{}] * FULL_WINDOW_FRAMES
        work_by_frame[100] = {'other': 0.004}
        overlay = overlay_with_audio_history(work_by_frame=work_by_frame)
        draw_audio_panel(
            surface=display, overlay=overlay, font=font, frame_info=frame_info_with(snapshot_with())
        )
        assert colour_present_in(display, audio_graph_column_rect(frame=100), AUDIO_CACHE_COLOR)

    def test_a_tiny_amount_of_work_still_shows(self, display, font):
        """A microsecond of work is at least one pixel tall, so it is never invisible."""
        work_by_frame = [{}] * FULL_WINDOW_FRAMES
        work_by_frame[100] = {'live_chunk': 0.000001}
        overlay = overlay_with_audio_history(work_by_frame=work_by_frame)
        draw_audio_panel(
            surface=display, overlay=overlay, font=font, frame_info=frame_info_with(snapshot_with())
        )
        assert colour_present_in(display, audio_graph_column_rect(frame=100), AUDIO_LIVE_COLOR)

    def test_a_huge_amount_of_work_is_clipped_to_the_graph(self, display, font):
        """A bar taller than the graph stops at the graph's top edge."""
        work_by_frame = [{}] * FULL_WINDOW_FRAMES
        work_by_frame[100] = {'compile': 5.0}
        overlay = overlay_with_audio_history(work_by_frame=work_by_frame)
        draw_audio_panel(
            surface=display, overlay=overlay, font=font, frame_info=frame_info_with(snapshot_with())
        )
        graph_rect = audio_graph_rect()
        column = audio_graph_column_rect(frame=100)
        assert tuple(display.get_at((column.left, graph_rect.top)))[:3] == AUDIO_COMPILE_COLOR
        assert tuple(display.get_at((column.left, graph_rect.top - 1)))[:3] != AUDIO_COMPILE_COLOR

    def test_kinds_with_no_work_or_no_room_draw_nothing(self, display, font):
        """A zero entry, and a kind stacked past the top of a full bar, add no pixels."""
        work_by_frame = [{}] * FULL_WINDOW_FRAMES
        work_by_frame[100] = {'compile': 5.0, 'decode': 0.004, 'live_chunk': 0.0}
        overlay = overlay_with_audio_history(work_by_frame=work_by_frame)
        draw_audio_panel(
            surface=display, overlay=overlay, font=font, frame_info=frame_info_with(snapshot_with())
        )
        column = audio_graph_column_rect(frame=100)
        assert colour_present_in(display, column, AUDIO_COMPILE_COLOR)
        assert not colour_present_in(display, column, AUDIO_DECODE_COLOR)
        assert not colour_present_in(display, column, AUDIO_LIVE_COLOR)

    def test_the_graph_shares_the_frame_time_graphs_window(self, display, font):
        """With 1 second of history the bars fill the right half: the left half stays empty."""
        work_by_frame = [{'compile': 0.004}] * (FULL_WINDOW_FRAMES // 2)
        overlay = overlay_with_audio_history(work_by_frame=work_by_frame)
        draw_audio_panel(
            surface=display, overlay=overlay, font=font, frame_info=frame_info_with(snapshot_with())
        )
        graph_rect = audio_graph_rect()
        left_half = pygame.Rect(graph_rect.left, graph_rect.top, GRAPH_WIDTH // 2 - 2, GRAPH_HEIGHT)
        right_half = pygame.Rect(
            graph_rect.centerx + 2, graph_rect.top, GRAPH_WIDTH // 2 - 2, GRAPH_HEIGHT
        )
        assert not colour_present_in(display, left_half, AUDIO_COMPILE_COLOR)
        assert colour_present_in(display, right_half, AUDIO_COMPILE_COLOR)
        assert GRAPH_WINDOW_SECONDS == 2.0

    def test_the_frame_budget_is_a_line(self, display, font):
        """The target frame time is drawn as the Performance panel's target line colour."""
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=font,
            frame_info=frame_info_with(snapshot_with(), target_fps=60.0),
        )
        assert colour_present_in(display, audio_graph_rect(), TARGET_LINE_COLOR)

    def test_no_target_draws_no_budget_line(self, display, font):
        """An uncapped run has no frame budget, so no line."""
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=font,
            frame_info=frame_info_with(snapshot_with(), target_fps=0.0),
        )
        assert not colour_present_in(display, audio_graph_rect(), TARGET_LINE_COLOR)

    def test_a_low_target_grows_the_graph_ceiling(self, display, font):
        """Like the frame-time graph, a 10 FPS target (100 ms) still puts its line on the graph."""
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=font,
            frame_info=frame_info_with(snapshot_with(), target_fps=10.0),
        )
        assert colour_present_in(display, audio_graph_rect(), TARGET_LINE_COLOR)

    def test_each_frames_total_time_is_a_faint_outline_behind_its_bar(self, display, font):
        """A frame's whole duration is outlined above the (shorter) bar of its audio work."""
        work_by_frame = [{}] * FULL_WINDOW_FRAMES
        work_by_frame[100] = {'live_chunk': 0.001}
        overlay = overlay_with_audio_history(work_by_frame=work_by_frame)
        draw_audio_panel(
            surface=display,
            overlay=overlay,
            font=font,
            frame_info=frame_info_with(snapshot_with(), target_fps=0.0),
        )
        column = audio_graph_column_rect(frame=100)
        silent_column = audio_graph_column_rect(frame=50)
        assert colour_count_in(display, column, AUDIO_LIVE_COLOR) > 0
        # The quiet frame has no bar, yet its 10 ms frame is outlined: not the backing alone
        assert any(
            tuple(display.get_at((silent_column.left, y)))[:3] != (0, 0, 0)
            for y in range(silent_column.top, silent_column.bottom)
        )

    def test_a_graph_with_no_history_draws_without_bars(self, display, font):
        """Before any frame is recorded the graph is just its backing."""
        draw_audio_panel(
            surface=display,
            overlay=DebugOverlay(visible=True),
            font=font,
            frame_info=frame_info_with(snapshot_with(), target_fps=0.0),
        )
        assert not colour_present_in(display, audio_graph_rect(), AUDIO_COMPILE_COLOR)


class TestChannelStrip:
    """One cell per mixer channel, coloured by state."""

    @pytest.mark.parametrize(('state', 'colour'), CHANNEL_STATE_COLOURS.items())
    def test_each_channel_state_has_its_colour(self, display, font, state, colour):
        """Every channel in one state draws that state's colour, and no other state's."""
        channels = tuple(
            ChannelState(index=index, group=group, state=state)
            for index, group in enumerate(['live'] * 4 + ['library'] * 32 + ['legacy'] * 8)
        )
        snapshot = snapshot_with(channels=channels)
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=font,
            frame_info=frame_info_with(snapshot),
        )
        cells = channel_strip_area(font=font, snapshot=snapshot)
        assert colour_present_in(display, cells, colour)
        for other_state, other_colour in CHANNEL_STATE_COLOURS.items():
            if other_state != state:
                assert not colour_present_in(display, cells, other_colour)

    def test_a_single_playing_channel_is_one_cell(self, display, font):
        """One playing library channel among idle ones draws exactly one cell of playing colour."""
        channels = tuple(
            ChannelState(
                index=index,
                group=group,
                state='playing' if index == 10 else 'idle',
            )
            for index, group in enumerate(['live'] * 4 + ['library'] * 32 + ['legacy'] * 8)
        )
        snapshot = snapshot_with(channels=channels)
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=font,
            frame_info=frame_info_with(snapshot),
        )
        cells = channel_strip_area(font=font, snapshot=snapshot)
        playing_pixels = colour_count_in(display, cells, CHANNEL_STATE_COLOURS['playing'])
        idle_pixels = colour_count_in(display, cells, CHANNEL_STATE_COLOURS['idle'])
        assert playing_pixels > 0
        assert idle_pixels == playing_pixels * 43

    def test_groups_are_labelled(self, display, mocker):
        """The three groups name themselves: live, library and legacy."""
        rendered = []
        real_font = load_debug_font()
        spy = mocker.Mock(wraps=real_font)
        spy.render.side_effect = lambda text, *args, **kwargs: (
            rendered.append(text) or real_font.render(text, *args, **kwargs)
        )
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=spy,
            frame_info=frame_info_with(snapshot_with()),
        )
        assert {'live', 'library', 'legacy'} <= set(rendered)


class TestBusMeters:
    """One bar per bus, with a mute mark."""

    def test_a_bus_draws_a_bar_and_its_name(self, display, mocker):
        """Each bus is named and has a level bar."""
        rendered = []
        real_font = load_debug_font()
        spy = mocker.Mock(wraps=real_font)
        spy.render.side_effect = lambda text, *args, **kwargs: (
            rendered.append(text) or real_font.render(text, *args, **kwargs)
        )
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=spy,
            frame_info=frame_info_with(snapshot_with(bus_levels={'master': 1.0, 'sfx': 0.5})),
        )
        assert 'master' in rendered
        assert 'sfx' in rendered

    def test_a_louder_bus_has_a_longer_bar(self, display, font):
        """The bar's length follows the bus level; a muted bus is marked in its own colour."""
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=font,
            frame_info=frame_info_with(snapshot_with(bus_levels={'half': 0.5})),
        )
        half = colour_count_in(display, LEFT_COLUMN, panels_bus_colour())
        display.fill((0, 0, 0))
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=font,
            frame_info=frame_info_with(snapshot_with(bus_levels={'full': 1.0})),
        )
        assert half > 0
        assert colour_count_in(display, LEFT_COLUMN, panels_bus_colour()) == 2 * half

    def test_a_level_above_unity_is_clipped(self, display, font):
        """A bus boosted past 1.0 draws no wider than a full bar."""
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=font,
            frame_info=frame_info_with(snapshot_with(bus_levels={'full': 1.0})),
        )
        full = colour_count_in(display, LEFT_COLUMN, panels_bus_colour())
        display.fill((0, 0, 0))
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=font,
            frame_info=frame_info_with(snapshot_with(bus_levels={'full': 3.0})),
        )
        assert colour_count_in(display, LEFT_COLUMN, panels_bus_colour()) == full

    def test_a_muted_bus_is_marked(self, display, font):
        """A muted bus draws its bar in the muted colour instead of the level colour."""
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=font,
            frame_info=frame_info_with(
                snapshot_with(bus_levels={'sfx': 1.0}, muted_buses=frozenset({'sfx'}))
            ),
        )
        assert colour_present_in(display, LEFT_COLUMN, panels_bus_muted_colour())
        assert not colour_present_in(display, LEFT_COLUMN, panels_bus_colour())


def panels_bus_colour():
    """The bus meters' bar colour.

    Returns:
        An RGB tuple.
    """
    from glitchygames.debug import panels

    return panels.AUDIO_BUS_COLOR


def panels_bus_muted_colour():
    """The bus meters' muted bar colour.

    Returns:
        An RGB tuple.
    """
    from glitchygames.debug import panels

    return panels.AUDIO_BUS_MUTED_COLOR


class TestCompileLog:
    """The last compiles: frame, sound, milliseconds and setup or gameplay."""

    def test_gameplay_compiles_are_red_in_the_log(self, display, font):
        """A gameplay compile's entry is drawn in compile red."""
        log = (
            CompileRecord(frame_number=12, name='explosion', milliseconds=4.5, during_setup=False),
        )
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=font,
            frame_info=frame_info_with(snapshot_with(compile_log=log)),
        )
        assert colour_present_in(display, COMPILE_LOG_AREA, AUDIO_COMPILE_COLOR)

    def test_setup_compiles_are_not_red(self, display, font):
        """A setup compile is drawn in the ordinary text colour."""
        log = (CompileRecord(frame_number=None, name='coin', milliseconds=2.0, during_setup=True),)
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=font,
            frame_info=frame_info_with(snapshot_with(compile_log=log)),
        )
        assert not colour_present_in(display, COMPILE_LOG_AREA, AUDIO_COMPILE_COLOR)

    def test_each_entry_names_frame_sound_time_and_phase(self, display, mocker):
        """The log line reads frame, sound, milliseconds and setup or gameplay."""
        rendered = []
        real_font = load_debug_font()
        spy = mocker.Mock(wraps=real_font)
        spy.render.side_effect = lambda text, *args, **kwargs: (
            rendered.append(text) or real_font.render(text, *args, **kwargs)
        )
        log = (
            CompileRecord(frame_number=None, name='coin', milliseconds=2.0, during_setup=True),
            CompileRecord(frame_number=12, name='explosion', milliseconds=4.5, during_setup=False),
        )
        draw_audio_panel(
            surface=display,
            overlay=quiet_history(),
            font=spy,
            frame_info=frame_info_with(snapshot_with(compile_log=log)),
        )
        assert any('coin' in text and '2.0 ms' in text and 'setup' in text for text in rendered)
        assert any(
            '12' in text and 'explosion' in text and '4.5 ms' in text and 'gameplay' in text
            for text in rendered
        )


class TestHeader:
    """The cache mode in large type, the device, voices, compiles and the cache hit rate."""

    def test_cache_none_header_is_red(self, display, font):
        """`CACHE: NONE` is drawn in compile red."""
        draw_audio_header(
            surface=display,
            font=font,
            frame_info=frame_info_with(snapshot_with(cache_mode=CacheMode.NONE)),
            top=HUD_MARGIN,
        )
        assert colour_present_in(display, HEADER_AREA, AUDIO_COMPILE_COLOR)

    @pytest.mark.parametrize('cache_mode', [CacheMode.RAM, CacheMode.DISK])
    def test_other_cache_modes_are_not_red(self, display, font, cache_mode):
        """`RAM` and `DISK` are not alarming: no red in the header."""
        draw_audio_header(
            surface=display,
            font=font,
            frame_info=frame_info_with(snapshot_with(cache_mode=cache_mode)),
            top=HUD_MARGIN,
        )
        assert not colour_present_in(display, HEADER_AREA, AUDIO_COMPILE_COLOR)

    def test_the_cache_mode_is_in_large_type(self, display, mocker):
        """The cache mode line is drawn larger than the other header lines."""
        real_font = load_debug_font()
        draw_audio_header(
            surface=display,
            font=real_font,
            frame_info=frame_info_with(snapshot_with(cache_mode=CacheMode.NONE)),
            top=HUD_MARGIN,
        )
        red_rows = [
            y
            for y in range(HEADER_AREA.height)
            if colour_present_in(
                display, pygame.Rect(0, y, HEADER_AREA.width, 1), AUDIO_COMPILE_COLOR
            )
        ]
        assert max(red_rows) - min(red_rows) + 1 > real_font.get_height()

    def test_the_header_names_its_readings(self, display, mocker):
        """The header text carries the cache mode, device, voices, compiles and hit rate."""
        rendered = []
        real_font = load_debug_font()
        spy = mocker.Mock(wraps=real_font)
        spy.render.side_effect = lambda text, *args, **kwargs: (
            rendered.append(text) or real_font.render(text, *args, **kwargs)
        )
        snapshot = snapshot_with(
            cache_mode=CacheMode.DISK,
            voices_live=1,
            voices_library=2,
            voices_legacy=3,
            compiles_last_second=4,
            cache_hit_rate=0.875,
        )
        draw_audio_header(
            surface=display, font=spy, frame_info=frame_info_with(snapshot), top=HUD_MARGIN
        )
        assert 'CACHE: DISK' in rendered
        assert snapshot.device in rendered
        assert 'voices: live 1 / library 2 / legacy 3' in rendered
        assert 'compiles last second: 4' in rendered
        assert 'cache hit rate: 87.5%' in rendered

    def test_no_requests_shows_no_hit_rate(self, display, mocker):
        """Before any cache request the hit rate is n/a."""
        rendered = []
        real_font = load_debug_font()
        spy = mocker.Mock(wraps=real_font)
        spy.render.side_effect = lambda text, *args, **kwargs: (
            rendered.append(text) or real_font.render(text, *args, **kwargs)
        )
        draw_audio_header(
            surface=display,
            font=spy,
            frame_info=frame_info_with(snapshot_with(cache_hit_rate=None)),
            top=HUD_MARGIN,
        )
        assert 'cache hit rate: n/a' in rendered

    def test_the_header_returns_the_next_lines_top(self, display, font):
        """The returned y is below everything the header drew."""
        next_top = draw_audio_header(
            surface=display, font=font, frame_info=frame_info_with(snapshot_with()), top=HUD_MARGIN
        )
        assert next_top > HUD_MARGIN + HUD_LINE_HEIGHT
        below = pygame.Rect(0, next_top, SURFACE_SIZE[0], SURFACE_SIZE[1] - next_top)
        assert not any(
            tuple(display.get_at((x, y)))[:3] != (0, 0, 0)
            for x in range(300)
            for y in range(next_top, next_top + 4)
        )
        assert below.height > 0

    def test_no_engine_says_audio_not_started(self, display, mocker):
        """With no snapshot the header says the audio engine has not started."""
        rendered = []
        real_font = load_debug_font()
        spy = mocker.Mock(wraps=real_font)
        spy.render.side_effect = lambda text, *args, **kwargs: (
            rendered.append(text) or real_font.render(text, *args, **kwargs)
        )
        next_top = draw_audio_header(
            surface=display, font=spy, frame_info=frame_info_with(None), top=HUD_MARGIN
        )
        assert rendered == ['audio: not started']
        assert next_top == HUD_MARGIN + HUD_LINE_HEIGHT

    def test_no_engine_draws_only_the_not_started_line_in_the_panel(self, display, mocker):
        """The Audio panel without an engine draws the line and nothing else."""
        rendered = []
        real_font = load_debug_font()
        spy = mocker.Mock(wraps=real_font)
        spy.render.side_effect = lambda text, *args, **kwargs: (
            rendered.append(text) or real_font.render(text, *args, **kwargs)
        )
        draw_audio_panel(
            surface=display, overlay=quiet_history(), font=spy, frame_info=frame_info_with(None)
        )
        assert rendered == ['audio: not started']
        assert not colour_present_in(display, audio_graph_rect(), TARGET_LINE_COLOR)


class TestPanelSelection:
    """F4 order, the All panel and the Performance panel's voices line."""

    def test_f4_reaches_the_audio_panel_after_performance(self):
        """F4 from Performance shows Audio, and Audio wraps round to All."""
        overlay = DebugOverlay(visible=True)
        overlay.panel = DebugPanel.PERFORMANCE
        overlay.cycle_panel()
        assert overlay.panel is DebugPanel.AUDIO
        overlay.cycle_panel()
        assert overlay.panel is DebugPanel.ALL

    def test_the_panel_value_is_audio(self):
        """The mode line names the panel by its value."""
        assert DebugPanel.AUDIO.value == 'audio'

    def test_the_all_panel_draws_only_the_header(self, display):
        """Under All, the Audio panel is its header: no graph, strip, meters or log."""
        overlay = quiet_history()
        overlay.panel = DebugPanel.ALL
        log = (
            CompileRecord(frame_number=12, name='explosion', milliseconds=4.5, during_setup=False),
        )
        channels = tuple(
            ChannelState(index=index, group='library', state='playing') for index in range(8)
        )
        scene = types.SimpleNamespace(camera=Camera2D(*SURFACE_SIZE))
        overlay.draw(
            display,
            scene=scene,
            screen_offset=(0, 0),
            frame_info=frame_info_with(
                snapshot_with(cache_mode=CacheMode.NONE, compile_log=log, channels=channels),
                target_fps=60.0,
            ),
        )
        assert colour_present_in(display, HEADER_AREA, AUDIO_COMPILE_COLOR)
        assert not colour_present_in(display, COMPILE_LOG_AREA, AUDIO_COMPILE_COLOR)
        assert not colour_present_in(display, LEFT_COLUMN, CHANNEL_STATE_COLOURS['playing'])
        # The Performance panel's frame-time graph is in the graph's place, not the audio one
        assert not colour_present_in(display, audio_graph_rect(), AUDIO_FRAME_OUTLINE_COLOR)

    def test_the_audio_panel_selected_draws_everything(self, display):
        """Under Audio, the overlay draws the whole panel and the mode line names it."""
        overlay = quiet_history()
        overlay.panel = DebugPanel.AUDIO
        scene = types.SimpleNamespace(camera=Camera2D(*SURFACE_SIZE))
        overlay.draw(
            display,
            scene=scene,
            screen_offset=(0, 0),
            frame_info=frame_info_with(snapshot_with(), target_fps=60.0),
        )
        assert colour_present_in(display, audio_graph_rect(), TARGET_LINE_COLOR)
        assert colour_present_in(display, LEFT_COLUMN, CHANNEL_STATE_COLOURS['idle'])

    def test_the_performance_panel_keeps_its_voices_line(self, display, mocker):
        """The Performance panel's `voices: N` comes from the snapshot's live voice count."""
        rendered = []
        real_font = load_debug_font()
        spy = mocker.Mock(wraps=real_font)
        spy.render.side_effect = lambda text, *args, **kwargs: (
            rendered.append(text) or real_font.render(text, *args, **kwargs)
        )
        draw_performance_panel(
            surface=display,
            overlay=DebugOverlay(visible=True),
            font=spy,
            frame_info=frame_info_with(snapshot_with(voices_live=3)),
        )
        assert 'voices: 3' in rendered
        rendered.clear()
        draw_performance_panel(
            surface=display,
            overlay=DebugOverlay(visible=True),
            font=spy,
            frame_info=frame_info_with(None),
        )
        assert not any('voices' in text for text in rendered)


class TestOverlayAudioHistory:
    """The rolling per-frame audio work, beside the frame times."""

    def test_work_is_recorded_with_its_frame(self):
        """Each frame's work is kept with the frame time, oldest first."""
        overlay = DebugOverlay(visible=True)
        overlay.record_frame(frame_seconds=0.01, audio_work_by_kind={'compile': 0.002})
        overlay.record_frame(frame_seconds=0.01)
        assert overlay.graph_audio_work() == [{'compile': 0.002}, {}]

    def test_a_non_positive_frame_records_no_work(self):
        """A frame that is ignored for its duration leaves the two histories aligned."""
        overlay = DebugOverlay(visible=True)
        overlay.record_frame(frame_seconds=0.0, audio_work_by_kind={'compile': 0.002})
        overlay.record_frame(frame_seconds=0.01, audio_work_by_kind={'decode': 0.001})
        assert overlay.graph_frame_times() == [0.01]
        assert overlay.graph_audio_work() == [{'decode': 0.001}]

    def test_the_work_window_matches_the_frame_window(self):
        """Only the frames inside the graph window have their work returned."""
        overlay = DebugOverlay(visible=True)
        for index in range(300):
            overlay.record_frame(frame_seconds=0.01, audio_work_by_kind={'frame': float(index)})
        work = overlay.graph_audio_work()
        assert len(work) == len(overlay.graph_frame_times()) == FULL_WINDOW_FRAMES
        assert work[-1] == {'frame': 299.0}
