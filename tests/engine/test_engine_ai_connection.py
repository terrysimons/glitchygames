"""A real engine, a real scene and a real WebSocket: what AI does to a run, and what it can't.

The fake service is the one ``tests/test_ai_link.py`` uses, on a real local port, so everything but
the models is real. The install points at a real control script, never the machine's own service.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, ClassVar, Self, override

import pygame
import pytest
from websockets.sync.server import serve

from glitchygames import ai_link
from glitchygames.ai_console import AiConsole
from glitchygames.ai_host import AiHostSources
from glitchygames.ai_link import INSTALL_ROOT_ENVIRONMENT_VARIABLE, AiLink, LinkState
from glitchygames.engine import ExitCode, GameEngine
from glitchygames.host import HostSources
from glitchygames.recording import post_input_event
from glitchygames.replay.tools.golden_traces import command_line
from glitchygames.scenes import Scene, SceneManager
from glitchygames.testing.keys import qwerty_scancode
from tests.test_ai_link import KEY_PRESS, FakeService, install

# These runs can't be --headless, which turns AI off, so on the dummy driver SCALED asks for a
# renderer it doesn't have (BUGS.md #178 item 32). Expected here, and harmless to what's tested
pytestmark = pytest.mark.filterwarnings('ignore:no fast renderer available')

# The discard port: nothing answers there
NOTHING_LISTENING_URL = 'ws://127.0.0.1:9/v1/session'
ARGUMENTS = ['--windowed', '--resolution', '320x240', '--log-level', 'warning']
# Paced, as uncapped frames would run out before the link had a moment to connect. A run that
# gets its proposal ends long before this: it only bounds a broken link, at about 10 s
MAXIMUM_FRAMES = 1200
# Why a run that ends on the AI's key presents a different number of frames each time
PROPOSAL_ARRIVES_IN_REAL_TIME = (
    "the run quits on the frame the AI's key arrives, sent over a real socket from the link's "
    'thread: how many frames that takes depends on how fast the driver presents them'
)


class ProposalWatchingScene(Scene):
    """Quits once it's received the AI's key press, or after too many frames."""

    NAME = 'Proposal Watching Scene'
    TARGET_FPS = 120.0
    keys_received: ClassVar[list[int]] = []
    maximum_frames: ClassVar[int] = MAXIMUM_FRAMES

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Count frames, and end a run that's gone on too long."""
        super().dt_tick(dt)
        self.frames_run = getattr(self, 'frames_run', 0) + 1
        if self.frames_run >= type(self).maximum_frames:
            self.scene_manager.quit()

    @override
    def on_key_down_event(self: Self, event: Any) -> None:
        """Note the key, and quit on the one the AI proposes."""
        type(self).keys_received.append(event.key)
        if event.key == pygame.K_F13:
            self.scene_manager.quit()

    @override
    def on_key_up_event(self: Self, event: Any) -> None:
        """Nothing here reads a release."""


@pytest.fixture
def scene():
    """Start each run with nothing received.

    Returns:
        The scene class.

    """
    ProposalWatchingScene.keys_received = []
    ProposalWatchingScene.maximum_frames = MAXIMUM_FRAMES
    return ProposalWatchingScene


@pytest.fixture
def fake_service(monkeypatch):
    """Run the fake service, and have new links use it.

    Yields:
        The fake.

    """
    fake = FakeService()
    server = serve(fake.handle, '127.0.0.1', 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'ws://127.0.0.1:{server.socket.getsockname()[1]}/v1/session'
    links_connect_to(url=url, monkeypatch=monkeypatch)
    yield fake
    server.shutdown()
    thread.join(timeout=5)


def links_connect_to(*, url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Have every new link use this URL: never the real service's port."""
    real_init = ai_link.AiLink.__init__

    def init_with_url(self: ai_link.AiLink, **arguments: Any) -> None:
        real_init(self, **{**arguments, 'session_url': url})

    monkeypatch.setattr(ai_link.AiLink, '__init__', init_with_url)


@pytest.fixture
def installed(tmp_path: Path, monkeypatch) -> Path:
    """Point the engine at a real, stand-in install.

    Returns:
        The file its control script records its calls in.

    """
    calls = install(root=tmp_path)
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))
    return calls


@pytest.mark.usefixtures('installed')
def test_ai_is_on_by_default_and_gets_the_ai_doors(scene):
    """With the service installed, a plain run has a link and the AI's subclass of the doors."""
    with command_line(ARGUMENTS):
        engine = GameEngine(game=scene)

    assert isinstance(engine.host.sources, AiHostSources)
    assert engine.ai_link is not None
    assert engine.ai_link.state is LinkState.NOT_STARTED


@pytest.mark.usefixtures('installed')
def test_no_ai_flag_gets_the_plain_doors(scene):
    """--no-ai never touches the service: the doors are exactly the host's own."""
    with command_line([*ARGUMENTS, '--no-ai']):
        engine = GameEngine(game=scene)

    assert type(engine.host.sources) is HostSources
    assert engine.ai_link is None


@pytest.mark.usefixtures('installed')
def test_headless_gets_the_plain_doors(scene):
    """Scripted sessions, golden traces and tools run headless, so AI can't enter a golden."""
    with command_line([*ARGUMENTS, '--headless']):
        engine = GameEngine(game=scene)

    assert type(engine.host.sources) is HostSources
    assert engine.ai_link is None


def test_a_machine_without_the_service_gets_the_plain_doors(scene):
    """The usual case: no install, no link, no cost. The harness points the install nowhere."""
    with command_line(ARGUMENTS):
        engine = GameEngine(game=scene)

    assert type(engine.host.sources) is HostSources
    assert engine.ai_link is None


@pytest.mark.frames_vary(reason=PROPOSAL_ARRIVES_IN_REAL_TIME)
def test_a_proposal_reaches_the_scene_and_the_session_ends_with_the_run(
    scene, fake_service, installed
):
    """The whole path: the models start, the game connects, a key arrives, the session closes."""
    fake_service.to_send = [KEY_PRESS]
    with command_line(ARGUMENTS):
        engine = GameEngine(game=scene)

    engine.start()

    assert pygame.K_F13 in scene.keys_received
    assert installed.read_text(encoding='utf-8').strip() == 'start'
    assert engine.ai_link.state is LinkState.STOPPED
    assert fake_service.sessions_closed.wait(timeout=5)


def test_a_service_that_never_answers_leaves_the_game_running(scene, installed, monkeypatch):
    """Nothing listening is only a state: the run plays out, and ends as it would have."""
    links_connect_to(url=NOTHING_LISTENING_URL, monkeypatch=monkeypatch)
    scene.maximum_frames = 30
    with command_line(ARGUMENTS):
        engine = GameEngine(game=scene)

    engine.start()

    assert installed.exists()
    assert scene.keys_received == []
    assert engine.ai_link.state is LinkState.STOPPED


@pytest.mark.frames_vary(reason=PROPOSAL_ARRIVES_IN_REAL_TIME)
def test_a_run_with_ai_replays_exactly_with_no_service(scene, fake_service, tmp_path, monkeypatch):
    """The core promise: AI input is recorded, so a replay needs no AI, model or service."""
    root = tmp_path / 'install'
    root.mkdir()
    install(root=root)
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(root))
    fake_service.to_send = [KEY_PRESS]
    recording = tmp_path / 'run.jsonl.gz'
    with command_line([*ARGUMENTS, '--record-trace', str(recording)]):
        GameEngine(game=scene).start()
    assert pygame.K_F13 in scene.keys_received

    # No service from here on: the install goes too, so nothing could answer
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path / 'gone'))
    scene.keys_received.clear()
    with (
        command_line([*ARGUMENTS, '--replay-trace', str(recording), '--headless']),
        pytest.raises(SystemExit) as ended,
    ):
        GameEngine(game=scene).start()

    assert ended.value.code == ExitCode.SUCCESS
    assert pygame.K_F13 in scene.keys_received


class TypingScene(ProposalWatchingScene):
    """Opens the console at frame 5, types while a real key is held, closes it, then quits."""

    NAME = 'Typing Scene'
    KEYS: ClassVar[dict[int, list[tuple[int, int, str]]]] = {
        3: [(pygame.KEYDOWN, pygame.K_w, 'w')],
        5: [(pygame.KEYDOWN, pygame.K_BACKQUOTE, '`')],
        6: [(pygame.KEYUP, pygame.K_BACKQUOTE, '')],
        7: [(pygame.KEYDOWN, pygame.K_q, 'q')],
        8: [(pygame.KEYUP, pygame.K_q, ''), (pygame.KEYUP, pygame.K_w, '')],
        9: [(pygame.KEYDOWN, pygame.K_BACKQUOTE, '`')],
        10: [(pygame.KEYUP, pygame.K_BACKQUOTE, '')],
        12: [(pygame.KEYDOWN, pygame.K_F13, '')],
    }
    releases_received: ClassVar[list[int]] = []
    console_frames: ClassVar[int] = 0

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Post this frame's keys, as a player would press them."""
        super().dt_tick(dt)
        for event_type, key, unicode in self.KEYS.get(self.frames_run, []):
            post_input_event(
                pygame.event.Event(
                    event_type,
                    key=key,
                    scancode=qwerty_scancode(key=key),
                    mod=0,
                    unicode=unicode,
                )
            )

    @override
    def on_key_up_event(self: Self, event: Any) -> None:
        """Note the release."""
        type(self).releases_received.append(event.key)


def test_typing_in_the_console_reaches_neither_the_game_nor_the_recording(tmp_path, monkeypatch):
    """The whole path on a real engine: the game sees one clean press and release of its own key.

    The recording then replays exactly, with no AI, no console and no service.
    """
    root = tmp_path / 'install'
    root.mkdir()
    install(root=root)
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(root))
    links_connect_to(url=NOTHING_LISTENING_URL, monkeypatch=monkeypatch)
    recording = tmp_path / 'typed.jsonl.gz'
    TypingScene.keys_received = []
    TypingScene.releases_received = []
    TypingScene.maximum_frames = MAXIMUM_FRAMES
    with command_line([*ARGUMENTS, '--record-trace', str(recording)]):
        GameEngine(game=TypingScene).start()

    assert TypingScene.keys_received == [pygame.K_w, pygame.K_F13]
    assert TypingScene.releases_received == [pygame.K_w]

    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path / 'gone'))
    TypingScene.keys_received = []
    TypingScene.releases_received = []
    with (
        command_line([*ARGUMENTS, '--replay-trace', str(recording), '--headless']),
        pytest.raises(SystemExit) as ended,
    ):
        GameEngine(game=TypingScene).start()

    assert ended.value.code == ExitCode.SUCCESS
    assert TypingScene.keys_received == [pygame.K_w, pygame.K_F13]
    assert TypingScene.releases_received == [pygame.K_w]


def test_the_debug_overlay_shows_the_consoles_status(scene):
    """The AI panel's lines come from the console; without one there are none."""
    with command_line(ARGUMENTS):
        engine = GameEngine(game=scene)
    manager = SceneManager()
    manager.game_engine = engine
    assert manager._ai_status() == ()

    engine.ai_console = AiConsole(link=AiLink(install_root=Path()), install_root=Path())
    assert manager._ai_status()[0].startswith('Link: ')

    manager.game_engine = None
    assert manager._ai_status() == ()
