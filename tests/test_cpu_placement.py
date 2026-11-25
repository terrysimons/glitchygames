"""The game pins itself to its core: the placement the service's setup writes, read and obeyed.

plans/lucid-circuit-linux.md section 6.2: the game on the fastest core, the mirror on the next,
every AI unit on the rest. ``setup.sh`` writes the placement; a live Linux run with AI moves every
one of its threads onto the game's cores, and a core the machine lacks is a warning, never a crash.
The threads are a fake ``/proc/self/task`` under ``tmp_path`` and the affinity call a recording
double, so no test moves the test process itself.
"""

from __future__ import annotations

import errno
import json
import logging
from typing import TYPE_CHECKING, Any, Self, override

import pygame
import pytest

from glitchygames import cpu_placement
from glitchygames.ai_link import (
    INSTALL_ROOT_ENVIRONMENT_VARIABLE,
    AiLink,
    LinkState,
    ServiceLocations,
)
from glitchygames.cpu_placement import CpuPlacement, pin_this_process, read_cpu_placement
from glitchygames.engine import GameEngine
from glitchygames.engine_context import EngineContext
from glitchygames.render_target import set_render_target
from glitchygames.replay.tools.golden_traces import command_line
from glitchygames.scenes import Scene
from tests.ai_service_stand_in import install

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture

# These runs can't be --headless, which turns AI off, so on the dummy driver SCALED asks for a
# renderer it doesn't have (BUGS.md #178 item 32). Expected here, and harmless to what's tested
pytestmark = [
    pytest.mark.filterwarnings('ignore:no fast renderer available'),
    # Every install here runs its control script, on Windows too (tests/ai_service_stand_in.py)
    pytest.mark.usefixtures('stand_in_ai_control_scripts'),
]

ARGUMENTS = ['--windowed', '--resolution', '320x240', '--log-level', 'warning']
# A Pi 5's placement, as setup.sh writes it
PI_5_PLACEMENT = {'game': [0], 'mirror': [1], 'ai': [2, 3]}
GAME_CORES = frozenset({0})
THREAD_IDS = (4242, 4243, 4250)
# A Pi 5's cores, all allowed to this process
PI_5_CORES = frozenset({0, 1, 2, 3})


def four_cores() -> set[int]:
    """Stand in for ``os.sched_getaffinity(0)`` on a Pi 5 with no cgroup limit.

    Returns:
        The cores this process may run on.

    """
    return set(PI_5_CORES)


class OneFrameScene(Scene):
    """Ends its run on its first frame."""

    NAME = 'One Frame Scene'

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Quit at once."""
        super().dt_tick(dt)
        self.scene_manager.quit()


def fake_task_directory(*, root: Path, thread_ids: tuple[int, ...] = THREAD_IDS) -> Path:
    """Lay out a ``/proc/self/task`` stand-in: one folder per thread id.

    Returns:
        The folder.

    """
    task_directory = root / 'task'
    for thread_id in thread_ids:
        (task_directory / str(thread_id)).mkdir(parents=True)
    return task_directory


def write_placement(*, root: Path, placement: dict[str, Any]) -> Path:
    """Write a placement file where setup.sh writes it, under the user root.

    Returns:
        The file.

    """
    path = ServiceLocations.in_one_folder(root=root).cpu_placement_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(placement), encoding='utf-8')
    return path


def test_a_live_run_with_ai_pins_every_thread_to_the_game_cores(tmp_path, mocker):
    """Each thread listed (SDL's audio thread among them) gets the game's cores."""
    set_affinity = mocker.Mock()

    pinned = pin_this_process(
        cores=GAME_CORES,
        task_directory=fake_task_directory(root=tmp_path),
        set_affinity=set_affinity,
        read_allowed_cores=four_cores,
    )

    assert pinned
    assert set_affinity.call_args_list == [mocker.call(thread_id, {0}) for thread_id in THREAD_IDS]


def test_a_core_the_machine_lacks_is_a_warning_not_a_crash(tmp_path, mocker, caplog):
    """EINVAL (a core gone offline since the check) stops at the first thread: none moved."""
    set_affinity = mocker.Mock(side_effect=OSError(errno.EINVAL, 'Invalid argument'))
    caplog.set_level(logging.WARNING, logger=cpu_placement.__name__)

    pinned = pin_this_process(
        cores=frozenset({2, 3}),
        task_directory=fake_task_directory(root=tmp_path),
        set_affinity=set_affinity,
        read_allowed_cores=four_cores,
    )

    assert not pinned
    assert set_affinity.call_count == 1
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert '[2, 3]' in warnings[0].getMessage()


def test_a_core_the_process_may_not_use_is_a_warning_and_nothing_moves(tmp_path, mocker, caplog):
    """{0, 7} on a four-core machine: the kernel would pin to 0 alone, silently, so it is refused.

    The same holds for a core outside a cgroup's AllowedCPUs: the check is against the cores this
    process may run on, not the cores the machine has.
    """
    set_affinity = mocker.Mock()
    caplog.set_level(logging.WARNING, logger=cpu_placement.__name__)

    pinned = pin_this_process(
        cores=frozenset({0, 7}),
        task_directory=fake_task_directory(root=tmp_path),
        set_affinity=set_affinity,
        read_allowed_cores=four_cores,
    )

    assert not pinned
    set_affinity.assert_not_called()
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert '[7]' in warnings[0].getMessage()


def test_the_allowed_cores_unreadable_is_a_warning_and_nothing_moves(tmp_path, mocker, caplog):
    """If the process's own cores can't be read, nothing is pinned, and the game goes on."""
    set_affinity = mocker.Mock()
    caplog.set_level(logging.WARNING, logger=cpu_placement.__name__)

    pinned = pin_this_process(
        cores=GAME_CORES,
        task_directory=fake_task_directory(root=tmp_path),
        set_affinity=set_affinity,
        read_allowed_cores=mocker.Mock(side_effect=OSError(errno.EPERM, 'Operation not permitted')),
    )

    assert not pinned
    set_affinity.assert_not_called()
    assert len(caplog.records) == 1


def test_a_later_refusal_leaves_the_earlier_threads_pinned(tmp_path, mocker, caplog):
    """No rollback: a thread refused after others were moved stops there, the others stay moved."""
    refused_thread = THREAD_IDS[1]
    pinned_threads: list[int] = []

    def set_affinity(thread_id: int, cores: set[int]) -> None:
        if thread_id == refused_thread:
            raise PermissionError(errno.EPERM, 'Operation not permitted')
        pinned_threads.append(thread_id)

    caplog.set_level(logging.WARNING, logger=cpu_placement.__name__)

    pinned = pin_this_process(
        cores=GAME_CORES,
        task_directory=fake_task_directory(root=tmp_path),
        set_affinity=set_affinity,
        read_allowed_cores=four_cores,
    )

    assert not pinned
    assert pinned_threads == [THREAD_IDS[0]]
    assert len(caplog.records) == 1


def test_a_thread_that_ends_while_pinning_is_skipped(tmp_path, mocker, caplog):
    """A thread gone between the listing and its turn (ESRCH) is no failure: the rest are pinned."""
    ended_thread = THREAD_IDS[1]

    def set_affinity(thread_id: int, cores: set[int]) -> None:
        if thread_id == ended_thread:
            raise ProcessLookupError(errno.ESRCH, 'No such process')
        pinned_threads.append((thread_id, cores))

    pinned_threads: list[tuple[int, set[int]]] = []
    caplog.set_level(logging.WARNING, logger=cpu_placement.__name__)

    pinned = pin_this_process(
        cores=GAME_CORES,
        task_directory=fake_task_directory(root=tmp_path),
        set_affinity=set_affinity,
        read_allowed_cores=four_cores,
    )

    assert pinned
    assert pinned_threads == [(THREAD_IDS[0], {0}), (THREAD_IDS[2], {0})]
    assert not caplog.records


def test_only_thread_ids_are_pinned(tmp_path, mocker):
    """An entry that isn't a thread id is not a thread: it is passed over, not a crash."""
    task_directory = fake_task_directory(root=tmp_path, thread_ids=(7,))
    (task_directory / 'not-a-thread').mkdir()
    set_affinity = mocker.Mock()

    assert pin_this_process(
        cores=GAME_CORES,
        task_directory=task_directory,
        set_affinity=set_affinity,
        read_allowed_cores=four_cores,
    )
    set_affinity.assert_called_once_with(7, {0})


def test_no_thread_list_is_a_warning_not_a_crash(tmp_path, mocker, caplog):
    """No ``/proc`` (a container without it) means nothing is pinned, and the game goes on."""
    set_affinity = mocker.Mock()
    caplog.set_level(logging.WARNING, logger=cpu_placement.__name__)

    pinned = pin_this_process(
        cores=GAME_CORES,
        task_directory=tmp_path / 'no-proc',
        set_affinity=set_affinity,
        read_allowed_cores=four_cores,
    )

    assert not pinned
    set_affinity.assert_not_called()
    assert len(caplog.records) == 1


def test_the_affinity_call_is_the_systems_on_linux_and_none_elsewhere(tmp_path, mocker, caplog):
    """Given neither call, Linux uses the system's; another platform pins nothing, and says so.

    Linux's are ``os.sched_setaffinity`` and ``os.sched_getaffinity(0)``. Both exist only on
    Linux, so their doubles are created where they are missing.
    """
    system_call = mocker.patch('glitchygames.cpu_placement.os.sched_setaffinity', create=True)
    allowed_cores_call = mocker.patch(
        'glitchygames.cpu_placement.os.sched_getaffinity', create=True, return_value=set(PI_5_CORES)
    )
    task_directory = fake_task_directory(root=tmp_path, thread_ids=(7,))
    caplog.set_level(logging.WARNING, logger=cpu_placement.__name__)

    mocker.patch.object(cpu_placement, 'sys', mocker.Mock(platform='linux'))
    on_linux = pin_this_process(cores=GAME_CORES, task_directory=task_directory)
    mocker.patch.object(cpu_placement, 'sys', mocker.Mock(platform='darwin'))
    on_a_mac = pin_this_process(cores=GAME_CORES, task_directory=task_directory)

    assert (on_linux, on_a_mac) == (True, False)
    system_call.assert_called_once_with(7, {0})
    allowed_cores_call.assert_called_once_with(0)
    assert len(caplog.records) == 1


@pytest.mark.parametrize(
    'placement',
    [
        {'game': [], 'mirror': [1], 'ai': [2, 3]},
        {'game': [-1], 'mirror': [1], 'ai': [2, 3]},
        {**PI_5_PLACEMENT, 'spare': [4]},
        {'game': ['0'], 'mirror': [1], 'ai': [2, 3]},
        b'\xff\xfe{"game": [0], "mirror": [1], "ai": [2, 3]}',
        b'{"game": [0]',
    ],
    ids=['empty-game', 'negative-core', 'unknown-key', 'core-as-text', 'not-utf-8', 'not-json'],
)
def test_a_malformed_placement_is_ignored_with_a_warning(placement, tmp_path, caplog):
    """A placement that fails validation is no placement: a warning, and the game unpinned.

    A file of bytes is written as they are: not UTF-8, or not JSON at all.
    """
    if isinstance(placement, bytes):
        path = ServiceLocations.in_one_folder(root=tmp_path).cpu_placement_file
        path.parent.mkdir(parents=True)
        path.write_bytes(placement)
    else:
        path = write_placement(root=tmp_path, placement=placement)
    caplog.set_level(logging.WARNING, logger=cpu_placement.__name__)

    assert read_cpu_placement(path=path) is None
    assert len(caplog.records) == 1


def test_a_placement_reads_as_the_cores_setup_wrote(tmp_path):
    """The Pi 5's file gives the game core 0, the mirror core 1 and the AI cores 2 and 3."""
    path = write_placement(root=tmp_path, placement=PI_5_PLACEMENT)

    assert read_cpu_placement(path=path) == CpuPlacement(
        game=frozenset({0}), mirror=frozenset({1}), ai=frozenset({2, 3})
    )


def test_a_missing_placement_is_quietly_none(tmp_path, caplog):
    """A one-core machine gets no file (nothing is pinned there): that is no warning."""
    caplog.set_level(logging.WARNING, logger=cpu_placement.__name__)

    assert read_cpu_placement(path=tmp_path / 'cpu-placement.json') is None
    assert not caplog.records


def test_an_unreadable_placement_is_a_warning_not_a_crash(tmp_path, caplog):
    """A placement that can't be read (here a folder in its place) is no placement."""
    path = tmp_path / 'cpu-placement.json'
    path.mkdir()
    caplog.set_level(logging.WARNING, logger=cpu_placement.__name__)

    assert read_cpu_placement(path=path) is None
    assert len(caplog.records) == 1


@pytest.fixture
def installed_with_placement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the engine at a real stand-in install whose setup wrote the Pi 5's placement.

    Returns:
        The install's folder.

    """
    install(root=tmp_path)
    write_placement(root=tmp_path, placement=PI_5_PLACEMENT)
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))
    return tmp_path


@pytest.fixture
def pinning(mocker: MockerFixture) -> Any:
    """Record the engine's pinning instead of moving the test process, on a pretend Linux.

    Returns:
        The double standing in for ``pin_this_process``.

    """
    mocker.patch.object(cpu_placement, 'sys', mocker.Mock(platform='linux'))
    return mocker.patch.object(cpu_placement, 'pin_this_process', return_value=True)


def started_service(*, engine: GameEngine, state: LinkState) -> None:
    """Have the engine's link report a state, then run the frame's first step, as the loop does.

    The link's thread sets the state; the main thread reads it as each frame pumps its events.
    """
    assert engine.ai_link is not None
    engine.ai_link.state = state
    engine.host.sources.pump_events()


@pytest.mark.usefixtures('installed_with_placement')
def test_a_live_linux_run_with_ai_pins_itself_once_the_service_has_started(pinning):
    """Not as the link is made: on the first frame the link reports CONNECTED, and only once.

    Before the start the service may yet refuse (not enough memory) or fail, and a game pinned for
    an AI that never runs would keep one core of four for nothing (design section 6.2).
    """
    with command_line(ARGUMENTS):
        engine = GameEngine(game=OneFrameScene)
    assert engine.ai_link is not None
    pinning.assert_not_called()

    started_service(engine=engine, state=LinkState.STARTING)
    pinning.assert_not_called()
    started_service(engine=engine, state=LinkState.CONNECTED)
    started_service(engine=engine, state=LinkState.RECONNECTING)
    started_service(engine=engine, state=LinkState.CONNECTED)

    pinning.assert_called_once_with(cores=GAME_CORES)


@pytest.mark.usefixtures('installed_with_placement')
@pytest.mark.parametrize(
    'state',
    [LinkState.NOT_ENOUGH_MEMORY, LinkState.UNAVAILABLE, LinkState.REFUSED, LinkState.STOPPED],
)
def test_a_start_that_fails_or_is_refused_never_pins(pinning, state):
    """A run whose AI never started leaves every thread where the system put it."""
    with command_line(ARGUMENTS):
        engine = GameEngine(game=OneFrameScene)

    for _ in range(3):
        started_service(engine=engine, state=state)

    pinning.assert_not_called()


@pytest.mark.usefixtures('installed_with_placement')
@pytest.mark.parametrize(
    'state', [state for state in LinkState if state is not LinkState.CONNECTED]
)
def test_only_a_connected_link_pins(pinning, state, installed_with_placement):
    """pin_the_game_to_its_cores itself refuses every state but CONNECTED."""
    link = AiLink(locations=ServiceLocations.in_one_folder(root=installed_with_placement))
    link.state = state
    assert cpu_placement.pin_the_game_to_its_cores(link=link) is False

    link.state = LinkState.CONNECTED
    assert cpu_placement.pin_the_game_to_its_cores(link=link) is True
    pinning.assert_called_once_with(cores=GAME_CORES)


@pytest.mark.parametrize(
    'run',
    [
        (['--no-lucid-circuit'], 'linux', True),
        (['--headless'], 'linux', True),
        ([], 'darwin', True),
        ([], 'linux', False),
    ],
    ids=['no-lucid-circuit', 'headless', 'mac', 'no-placement'],
)
def test_no_pinning_without_ai_on_a_mac_or_without_a_placement(
    run, installed_with_placement, pinning, mocker
):
    """Through the engine: each of these leaves every thread where the system put it.

    Each run is its extra arguments, its platform, and whether setup wrote a placement. A run
    with a link has its service report a start, so the Mac and the missing placement are what
    refuse, not a service that never started.
    """
    arguments, platform, with_placement = run
    mocker.patch.object(cpu_placement, 'sys', mocker.Mock(platform=platform))
    if not with_placement:
        ServiceLocations.in_one_folder(root=installed_with_placement).cpu_placement_file.unlink()
    system_call = mocker.patch('glitchygames.cpu_placement.os.sched_setaffinity', create=True)

    with command_line([*ARGUMENTS, *arguments]):
        engine = GameEngine(game=OneFrameScene)
    if engine.ai_link is not None:
        started_service(engine=engine, state=LinkState.CONNECTED)

    assert (engine.ai_link is not None) is (platform == 'darwin' or not with_placement)
    pinning.assert_not_called()
    system_call.assert_not_called()


def test_no_link_never_pins(pinning):
    """A run without AI has no link to report a start, so nothing pins it."""
    assert cpu_placement.pin_the_game_to_its_cores(link=None) is False
    pinning.assert_not_called()


@pytest.mark.draws_frames
@pytest.mark.usefixtures('installed_with_placement')
def test_a_replay_never_pins(pinning, tmp_path):
    """A replay has no link: watching one leaves the process where it was."""
    recording = tmp_path / 'one-frame.jsonl.gz'
    with command_line([*ARGUMENTS, '--headless', '--record-trace', str(recording)]):
        GameEngine(game=OneFrameScene).start()

    with command_line([*ARGUMENTS, '--replay-trace', str(recording)]):
        engine = GameEngine(game=OneFrameScene)

    assert engine.ai_link is None
    pinning.assert_not_called()


@pytest.mark.usefixtures('installed_with_placement')
def test_an_inner_game_never_pins_the_process_it_shares(pinning):
    """An inner context (the Arcade) shares the process with other games: it never pins it."""
    with EngineContext(name='inner').active():
        set_render_target(surface=pygame.Surface((320, 240)))
        with command_line(ARGUMENTS):
            engine = GameEngine(game=OneFrameScene)
        started_service(engine=engine, state=LinkState.CONNECTED)

    assert engine.ai_link is not None
    pinning.assert_not_called()
