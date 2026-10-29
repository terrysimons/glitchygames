"""The CRT power-on sequence before every game (glitchygames/crt_power_on.py)."""

from __future__ import annotations

import asyncio
import itertools
import os

import pygame
import pytest

from glitchygames import crt_power_on
from glitchygames.backgrounds import (
    BackgroundPattern,
    active_default_background_pattern,
    background_pattern_surface,
    paint_default_background,
    set_active_default_background_pattern,
)
from glitchygames.crt_power_on import (
    CRT_POWER_ON_VARIABLE,
    DOT_STAGE_START,
    FRAME_SECONDS,
    LINE_STAGE_START,
    OPEN_STAGE_START,
    SEQUENCE_SECONDS,
    WARM_UP_STAGE_START,
    CrtPowerOnMode,
    PowerOnOutcome,
    draw_power_on,
    play_power_on,
    play_power_on_async,
    resolve_mode,
    should_play,
)


@pytest.mark.parametrize(
    ('mode', 'video_driver', 'options', 'plays'),
    [
        # Someone is watching a live run
        (CrtPowerOnMode.AUTO, 'cocoa', {}, True),
        # Nobody sees SDL's dummy driver: --headless, and every test
        (CrtPowerOnMode.AUTO, 'dummy', {}, False),
        # Before frame 0 of a replay, an audit, a rebaseline or a recording: never
        (CrtPowerOnMode.AUTO, 'cocoa', {'replay_trace': 'run.jsonl.gz'}, False),
        (CrtPowerOnMode.AUTO, 'cocoa', {'record_trace': 'run.jsonl.gz'}, False),
        (CrtPowerOnMode.AUTO, 'cocoa', {'audit': True}, False),
        (CrtPowerOnMode.AUTO, 'cocoa', {'rebaseline': 'new.jsonl.gz'}, False),
        # Options left at their defaults (None, False) are not set
        (CrtPowerOnMode.AUTO, 'cocoa', {'replay_trace': None, 'audit': False}, True),
        (CrtPowerOnMode.OFF, 'cocoa', {}, False),
        # The sequence's own tests force it on the dummy driver
        (CrtPowerOnMode.ON, 'dummy', {}, True),
    ],
)
def test_when_the_sequence_plays(mode, video_driver, options, plays):
    """Auto plays only where someone watches and nothing is recorded or replayed."""
    assert should_play(mode=mode, video_driver=video_driver, options=options) is plays


SIZE = (160, 120)


@pytest.fixture(params=list(BackgroundPattern), ids=lambda pattern: pattern.value)
def configured_background(request) -> BackgroundPattern:
    """Run a test once per background the run can be configured with (--default-background).

    The harness puts the default pattern back after the test (tests/harness.py).

    Returns:
        The pattern in effect.

    """
    set_active_default_background_pattern(pattern=request.param)
    return request.param


def never_wait(_seconds: float) -> None:
    """Stand in for the raw sleep (glitchygames/clock.py): the frames run back to back."""


def settled_picture(*, size: tuple[int, int] = SIZE) -> pygame.Surface:
    """Return the background the sequence settles on (the engine's default pattern)."""
    return background_pattern_surface(pattern=active_default_background_pattern(), size=size)


def drawn(*, progress: float, size: tuple[int, int] = SIZE) -> pygame.Surface:
    """Return a surface showing the sequence at ``progress``."""
    surface = pygame.Surface(size)
    surface.fill((90, 10, 200))  # anything the drawing must cover
    draw_power_on(surface=surface, picture=settled_picture(size=size), progress=progress)
    return surface


def is_bright(color: pygame.Color) -> bool:
    """Whether a pixel is near white (the beam)."""
    return min(color.r, color.g, color.b) > 200


def is_black(color: pygame.Color) -> bool:
    """Whether a pixel is black (the tube showing nothing there)."""
    return max(color.r, color.g, color.b) == 0


def test_it_starts_black():
    """The tube is off: every pixel black."""
    surface = drawn(progress=0.0)

    assert pygame.transform.average_color(surface)[:3] == (0, 0, 0)


def test_the_beam_first_shows_as_a_dot_in_the_centre():
    """Before the beam deflects it lights one spot in the middle."""
    middle_of_dot = (DOT_STAGE_START + LINE_STAGE_START) / 2
    surface = drawn(progress=middle_of_dot)

    assert is_bright(surface.get_at((SIZE[0] // 2, SIZE[1] // 2)))
    assert is_black(surface.get_at((0, 0)))
    assert is_black(surface.get_at((SIZE[0] // 4, SIZE[1] // 2)))


def test_the_dot_stretches_into_a_line_across_the_screen():
    """The horizontal sweep comes first: a thin bright line, nothing above it."""
    end_of_line = OPEN_STAGE_START - 0.001
    surface = drawn(progress=end_of_line)
    centre_row = SIZE[1] // 2

    assert is_bright(surface.get_at((SIZE[0] // 6, centre_row)))
    assert is_bright(surface.get_at((SIZE[0] * 5 // 6, centre_row)))
    assert is_black(surface.get_at((SIZE[0] // 2, centre_row - SIZE[1] // 10)))


@pytest.mark.usefixtures('configured_background')
def test_the_picture_opens_from_the_line():
    """Half way through opening: a band of picture in the middle, black above and below."""
    middle_of_open = (OPEN_STAGE_START + WARM_UP_STAGE_START) / 2
    surface = drawn(progress=middle_of_open)

    assert not is_black(surface.get_at((SIZE[0] // 4, SIZE[1] // 2)))
    assert is_black(surface.get_at((SIZE[0] // 4, 0)))
    assert is_black(surface.get_at((SIZE[0] // 4, SIZE[1] - 1)))


@pytest.mark.usefixtures('configured_background')
def test_the_warm_up_flickers_around_the_picture():
    """The whole picture shows, but not yet at its settled brightness."""
    settled = pygame.transform.average_color(drawn(progress=1.0))
    warming_up = [
        pygame.transform.average_color(drawn(progress=progress))
        for progress in (0.52, 0.56, 0.62, 0.70, 0.80)
    ]

    assert all(color[:3] != (0, 0, 0) for color in warming_up)
    assert any(color[:3] != settled[:3] for color in warming_up)


@pytest.mark.usefixtures('configured_background')
def test_it_settles_on_exactly_the_default_background():
    """The hand-over frame is the picture the engine painted before this sequence existed."""
    expected = pygame.Surface(SIZE)
    paint_default_background(surface=expected)

    assert pygame.image.tobytes(drawn(progress=1.0), 'RGB') == pygame.image.tobytes(expected, 'RGB')


@pytest.mark.parametrize('size', [(1, 1), (7, 5), (2, 300)])
@pytest.mark.parametrize('progress', [0.0, 0.1, 0.2, 0.35, 0.45, 0.6, 0.85, 0.95, 1.0])
@pytest.mark.usefixtures('configured_background')
def test_every_moment_draws_at_any_size(size, progress):
    """Tiny or odd windows draw without error (no zero-sized scaling)."""
    drawn(progress=progress, size=size)


def test_drawing_never_changes_the_picture():
    """The picture is the shared, cached pattern surface: it is only read."""
    picture = settled_picture()
    before = pygame.image.tobytes(picture, 'RGB')

    for progress in (0.1, 0.25, 0.4, 0.6, 1.0):
        draw_power_on(surface=pygame.Surface(SIZE), picture=picture, progress=progress)

    assert pygame.image.tobytes(picture, 'RGB') == before


class ScriptedEvents:
    """The doors' event pump, answering with scripted batches, then empty ones."""

    def __init__(self, *, batches: list[list[pygame.event.Event]]) -> None:
        """Start with the batches to answer, in order."""
        self.batches = list(batches)
        self.pumps = 0

    def pump_events(self) -> list[pygame.event.Event]:
        """Return the next scripted batch (an empty one once the script is used up)."""
        self.pumps += 1
        return self.batches.pop(0) if self.batches else []


def measured_clock(mocker, *, step: float) -> None:
    """Make the measured clock read 0, then ``step`` more at each later reading."""
    mocker.patch(
        'glitchygames.clock.measured_seconds', side_effect=itertools.count(start=0.0, step=step)
    )


def shows_the_default_background(surface: pygame.Surface) -> bool:
    """Whether the surface shows exactly the settled picture."""
    expected = pygame.Surface(surface.get_size())
    paint_default_background(surface=expected)
    return pygame.image.tobytes(surface, 'RGB') == pygame.image.tobytes(expected, 'RGB')


def test_it_plays_to_the_end_one_frame_per_tick(mocker):
    """Each frame draws the moment the clock says and waits a frame; it ends settled."""
    screen = pygame.display.get_surface()
    measured_clock(mocker, step=FRAME_SECONDS)
    flips = mocker.spy(pygame.display, 'flip')
    pauses: list[float] = []

    outcome = play_power_on(screen=screen, sources=ScriptedEvents(batches=[]), sleep=pauses.append)

    assert outcome is PowerOnOutcome.FINISHED
    # One frame per FRAME_SECONDS of the sequence, then the settled picture
    assert flips.call_count == pytest.approx(SEQUENCE_SECONDS / FRAME_SECONDS + 1, abs=2)
    assert set(pauses) == {FRAME_SECONDS}
    assert shows_the_default_background(screen)


def test_a_key_or_button_skips_to_the_settled_picture(mocker):
    """A key press ends it at once, on the settled picture; the press is dropped."""
    screen = pygame.display.get_surface()
    measured_clock(mocker, step=FRAME_SECONDS)
    events = ScriptedEvents(
        batches=[[], [], [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)]]
    )

    outcome = play_power_on(screen=screen, sources=events, sleep=never_wait)

    assert outcome is PowerOnOutcome.SKIPPED
    assert events.pumps == 3
    assert shows_the_default_background(screen)


@pytest.mark.parametrize(
    'event_type',
    [
        pygame.MOUSEBUTTONDOWN,
        pygame.JOYBUTTONDOWN,
        pygame.CONTROLLERBUTTONDOWN,
    ],
)
def test_every_kind_of_button_skips(mocker, event_type):
    """A mouse, joystick or controller button skips it too."""
    measured_clock(mocker, step=FRAME_SECONDS)
    events = ScriptedEvents(batches=[[pygame.event.Event(event_type)]])

    outcome = play_power_on(screen=pygame.display.get_surface(), sources=events, sleep=never_wait)

    assert outcome is PowerOnOutcome.SKIPPED


def test_closing_the_window_ends_it_as_a_quit(mocker):
    """A QUIT wins over a skip in the same batch: the engine hands it back to the game."""
    measured_clock(mocker, step=FRAME_SECONDS)
    events = ScriptedEvents(
        batches=[
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a), pygame.event.Event(pygame.QUIT)]
        ]
    )

    outcome = play_power_on(screen=pygame.display.get_surface(), sources=events, sleep=never_wait)

    assert outcome is PowerOnOutcome.QUIT


def test_the_async_player_awaits_one_tick_per_frame(mocker):
    """In a browser (start_async) each frame waits for the next animation frame instead."""
    screen = pygame.display.get_surface()
    measured_clock(mocker, step=FRAME_SECONDS)
    ticks: list[int] = []

    async def wait_for_tick() -> float:
        await asyncio.sleep(0)
        ticks.append(len(ticks))
        return len(ticks) * FRAME_SECONDS

    outcome = asyncio.run(
        play_power_on_async(
            screen=screen, sources=ScriptedEvents(batches=[]), wait_for_tick=wait_for_tick
        )
    )

    assert outcome is PowerOnOutcome.FINISHED
    assert len(ticks) == pytest.approx(SEQUENCE_SECONDS / FRAME_SECONDS, abs=2)
    assert shows_the_default_background(screen)


@pytest.mark.parametrize(
    ('option', 'environment', 'mode'),
    [
        # Nothing chosen: auto
        (None, {}, CrtPowerOnMode.AUTO),
        # The environment chooses when the option does not (the tests turn it off this way)
        (None, {CRT_POWER_ON_VARIABLE: 'off'}, CrtPowerOnMode.OFF),
        # An explicit option always wins
        ('on', {CRT_POWER_ON_VARIABLE: 'off'}, CrtPowerOnMode.ON),
        ('auto', {CRT_POWER_ON_VARIABLE: 'off'}, CrtPowerOnMode.AUTO),
    ],
)
def test_the_mode_comes_from_the_option_then_the_environment(option, environment, mode):
    """The option, else the environment variable, else auto."""
    assert resolve_mode(option=option, environment=environment) is mode


def test_a_bad_environment_value_falls_back_to_auto_with_a_warning(caplog):
    """A typo in the variable must not stop every game from starting."""
    mode = resolve_mode(option=None, environment={CRT_POWER_ON_VARIABLE: 'sometimes'})

    assert mode is CrtPowerOnMode.AUTO
    assert f'{CRT_POWER_ON_VARIABLE}=sometimes' in caplog.text


def test_the_tests_never_play_it_unless_asked():
    """tests/sdl_defaults.py turns it off for the run, the native child run included."""
    assert resolve_mode(option=None, environment=os.environ) is CrtPowerOnMode.OFF


def test_brightness_one_leaves_the_picture_unchanged():
    """Neither darkened nor brightened."""
    picture = settled_picture()
    surface = picture.copy()

    crt_power_on._set_brightness(surface=surface, brightness=1.0)

    assert pygame.image.tobytes(surface, 'RGB') == pygame.image.tobytes(picture, 'RGB')
