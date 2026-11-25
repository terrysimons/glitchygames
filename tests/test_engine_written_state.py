"""What running an engine changes is reset after each test (tests/engine_written_state.py)."""

from __future__ import annotations

import os

import pygame
import pytest

from tests import engine_written_state
from tests.engine_written_state import (
    CLICKTHROUGH_VARIABLE,
    EVENT_TYPES,
    EngineWrittenState,
    blocked_types,
    engine_written_state_for_run,
    reset_engine_written_state,
)

# As tests/test_leaked_state_guard.py runs its inner tests: in this process, with the harness
INNER_OPTIONS = ('-p', 'tests.harness', '-p', 'no:randomly', '-p', 'no:cacheprovider')
# Each state: what a test leaves, and what the test after it asserts (names from INNER_HEADER)
PLANTED = {
    'blocked controller events': (
        'pygame.event.set_blocked(CONTROLLER_TYPES)',
        'all(posted_is_received(event_type) for event_type in CONTROLLER_TYPES)',
    ),
    'a blocked custom event': (
        'pygame.event.set_blocked(pygame.USEREVENT + 1)',
        'posted_is_received(pygame.USEREVENT + 1)',
    ),
    'an allowed system event': (
        'pygame.event.set_allowed(pygame.SYSWMEVENT)',
        'pygame.event.get_blocked(pygame.SYSWMEVENT)',
    ),
    'mixer channels': (
        'pygame.mixer.set_num_channels(44)',
        'pygame.mixer.get_num_channels() == RUN_STATE.channel_count',
    ),
    'the caption': (
        "pygame.display.set_caption('planted', 'planted')",
        'pygame.display.get_caption() == RUN_STATE.caption',
    ),
    'the click-through variable': (
        "os.environ[CLICKTHROUGH_VARIABLE] = 'planted'",
        'os.environ.get(CLICKTHROUGH_VARIABLE) == CLICKTHROUGH_FOR_RUN',
    ),
}
INNER_HEADER = """\
import os

import pygame

from tests.engine_written_state import (
    CLICKTHROUGH_FOR_RUN,
    CLICKTHROUGH_VARIABLE,
    engine_written_state_for_run,
)

RUN_STATE = engine_written_state_for_run()
CONTROLLER_TYPES = [
    value for name, value in vars(pygame).items() if name.startswith('CONTROLLER')
    and isinstance(value, int) and pygame.event.event_name(value).startswith('Controller')
]


def posted_is_received(event_type):
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(event_type))
    return bool(pygame.event.get(event_type))

"""
INNER_TESTS = """

def test_leaves_it():
    {leaves}


def test_after_it():
    assert {clean}
"""
# A variable the run's shell could have exported
RUN_VALUE = '0'


@pytest.mark.parametrize('state', PLANTED)
def test_what_an_engine_writes_is_reset_for_the_next_test(state, pytester):
    """The test that left it passes, and the next finds it as the run started."""
    leaves, clean = PLANTED[state]
    pytester.makepyfile(test_inner=INNER_HEADER + INNER_TESTS.format(leaves=leaves, clean=clean))

    result = pytester.runpytest_inprocess(*INNER_OPTIONS)

    result.assert_outcomes(passed=2)


def test_every_item_is_reset_even_one_no_fixture_reaches(pytester):
    """A golden replay's item runs an engine, and gets no autouse fixture."""
    pytester.makeconftest("""
import pygame
import pytest


class BlocksEvents(pytest.Item):
    def runtest(self):
        pygame.event.set_blocked(pygame.CONTROLLERBUTTONDOWN)


class ItemFile(pytest.File):
    def collect(self):
        yield BlocksEvents.from_parent(self, name='blocks_events')


def pytest_collect_file(file_path, parent):
    if file_path.suffix == '.item':
        return ItemFile.from_parent(parent, path=file_path)
    return None
""")
    (pytester.path / 'custom.item').write_text('', encoding='utf-8')

    result = pytester.runpytest_inprocess(*INNER_OPTIONS)

    result.assert_outcomes(passed=1)
    assert blocked_types() == engine_written_state_for_run().blocked_types


def test_a_variable_the_run_was_given_is_put_back(mocker, monkeypatch):
    """An exported click-through choice outlives a test that removed it."""
    monkeypatch.delenv(CLICKTHROUGH_VARIABLE, raising=False)
    mocker.patch.object(engine_written_state, 'CLICKTHROUGH_FOR_RUN', RUN_VALUE)

    reset_engine_written_state(run_state=engine_written_state_for_run())

    assert os.environ.pop(CLICKTHROUGH_VARIABLE) == RUN_VALUE


def test_a_type_the_run_started_with_blocked_is_blocked_again():
    """A driver that starts with more types blocked than the dummy one keeps them so."""
    run_state = engine_written_state_for_run()
    with_key_presses = run_state.blocked_types | {pygame.KEYDOWN}

    reset_engine_written_state(
        run_state=run_state.model_copy(update={'blocked_types': with_key_presses})
    )

    assert blocked_types() == with_key_presses
    reset_engine_written_state(run_state=run_state)
    assert blocked_types() == run_state.blocked_types


def test_what_the_run_never_had_is_left():
    """A run whose mixer could not start, or with no window caption, has none to go back to."""
    caption = pygame.display.get_caption()
    channel_count = pygame.mixer.get_num_channels()

    reset_engine_written_state(
        run_state=EngineWrittenState(
            blocked_types=engine_written_state_for_run().blocked_types,
            caption=(),
            channel_count=None,
        )
    )

    assert pygame.display.get_caption() == caption
    assert pygame.mixer.get_num_channels() == channel_count


def test_a_stopped_display_and_mixer_are_left_stopped(mocker):
    """What a test quit starts fresh at the next test's setup; reading it now would raise."""
    mocker.patch.object(pygame.display, 'get_init', return_value=False)
    mocker.patch.object(pygame.mixer, 'get_init', return_value=None)
    set_caption = mocker.patch.object(pygame.display, 'set_caption')
    set_channels = mocker.patch.object(pygame.mixer, 'set_num_channels')
    get_blocked = mocker.patch.object(pygame.event, 'get_blocked')

    reset_engine_written_state(
        run_state=EngineWrittenState(
            blocked_types=frozenset(), caption=('another', 'another'), channel_count=3
        )
    )

    for never_called in (set_caption, set_channels, get_blocked):
        never_called.assert_not_called()


def test_a_run_whose_mixer_could_not_start_has_no_channel_count(mocker):
    """The state is still read."""
    mocker.patch.object(pygame.mixer, 'get_init', return_value=None)

    assert engine_written_state_for_run.__wrapped__().channel_count is None


def test_every_named_event_type_is_watched():
    """The controller types among them, and the highest pygame names."""
    assert {pygame.CONTROLLERBUTTONDOWN, pygame.KEYDOWN, pygame.USEREVENT} <= set(EVENT_TYPES)
