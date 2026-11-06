"""A game's link to the AI service, against a real local WebSocket server and a real script."""

from __future__ import annotations

import json
import stat
import threading
from pathlib import Path
from typing import Any

import pygame
import pytest
from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve

from glitchygames import ai_link, clock
from glitchygames.ai_host import AiHostSources, input_event_from
from glitchygames.ai_link import (
    EXIT_NOT_ENOUGH_MEMORY,
    INSTALL_ROOT_ENVIRONMENT_VARIABLE,
    MAXIMUM_INBOX_MESSAGES,
    PROTOCOL_VERSION,
    AiLink,
    LinkState,
    create_link,
)
from glitchygames.host import HostSources

SERVICE_KEY = 'service-token'
WAIT_SECONDS = 10.0
KEY_PRESS = {
    'type': 'input_event',
    'event_type': pygame.KEYDOWN,
    'key': pygame.K_F13,
    'scancode': 104,
}


def install(*, root: Path, exit_code: int = 0) -> Path:
    """Lay out an install: a real control script that records its calls, and the key.

    Returns:
        The file the script records its calls in.

    """
    calls = root / 'control-calls'
    script = root / 'bin' / 'ai-service.sh'
    script.parent.mkdir(parents=True)
    script.write_text(f'#!/bin/sh\necho "$1" >> "{calls}"\nexit {exit_code}\n', encoding='utf-8')
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    key = root / 'config' / 'service-api-key'
    key.parent.mkdir(parents=True)
    key.write_text(f'{SERVICE_KEY}\n', encoding='utf-8')
    return calls


def wait_until(condition: Any) -> bool:
    """Wait for a condition the link's thread will make true, on a real clock.

    Returns:
        Whether it became true in time.

    """
    deadline = clock.raw_counter_seconds() + WAIT_SECONDS
    while clock.raw_counter_seconds() < deadline:
        if condition():
            return True
        clock.raw_sleep(0.01)
    return False


class FakeService:
    """A real WebSocket server, recording what it hears and answering as it's told."""

    def __init__(self) -> None:
        """Start out welcoming."""
        self.first_reply: dict[str, object] | str = {
            'type': 'welcome',
            'protocol_version': PROTOCOL_VERSION,
            'models': [],
        }
        self.to_send: list[dict[str, object] | str] = []
        self.heard: list[dict[str, object]] = []
        self.authorizations: list[str | None] = []
        self.sessions_opened = 0
        self.sessions_closed = threading.Event()
        self.drop_after_welcome = False

    def handle(self, connection: Any) -> None:
        """Serve one session."""
        self.sessions_opened += 1
        self.authorizations.append(connection.request.headers.get('Authorization'))
        try:
            self._converse(connection)
        except ConnectionClosed:
            self.sessions_closed.set()

    def _converse(self, connection: Any) -> None:
        """Answer the hello as told, send what's queued, then answer pings."""
        self.heard.append(json.loads(connection.recv()))
        connection.send(json.dumps(self.first_reply))
        if self.drop_after_welcome:
            self.drop_after_welcome = False
            return
        for message in self.to_send:
            connection.send(message if isinstance(message, str) else json.dumps(message))
        while True:
            heard = json.loads(connection.recv())
            self.heard.append(heard)
            connection.send(json.dumps({'type': 'pong', 'sequence': heard['sequence']}))


@pytest.fixture
def service():
    """Run the fake service on a real local port.

    Yields:
        The fake and its session URL.

    """
    fake = FakeService()
    server = serve(fake.handle, '127.0.0.1', 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield fake, f'ws://127.0.0.1:{server.socket.getsockname()[1]}/v1/session'
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture
def started_link(tmp_path):
    """Build links that are always stopped afterwards.

    Yields:
        A function making a started link.

    """
    links = []

    def make(*, session_url: str, exit_code: int = 0) -> AiLink:
        install(root=tmp_path, exit_code=exit_code)
        link = AiLink(install_root=tmp_path, session_url=session_url)
        links.append(link)
        link.start()
        return link

    yield make
    for link in links:
        link.stop()


def test_a_link_says_hello_with_its_token_and_connects(service, started_link):
    """The service hears the protocol version and token, and welcomes it."""
    fake, url = service

    link = started_link(session_url=url)

    assert wait_until(lambda: link.state is LinkState.CONNECTED)
    assert fake.heard[0] == {'type': 'hello', 'protocol_version': PROTOCOL_VERSION}
    assert fake.authorizations == [f'Bearer {SERVICE_KEY}']


def test_the_control_script_starts_the_service_as_the_link_starts(service, started_link, tmp_path):
    """Models load when the game does: the start asks the script."""
    _fake, url = service

    link = started_link(session_url=url)

    assert wait_until(lambda: link.state is LinkState.CONNECTED)
    assert (tmp_path / 'control-calls').read_text(encoding='utf-8').strip() == 'start'


def test_start_returns_before_the_service_does(tmp_path):
    """The frame loop never waits: a script that takes a while doesn't hold up start()."""
    release = tmp_path / 'release'
    script = tmp_path / 'bin' / 'ai-service.sh'
    install(root=tmp_path)
    script.write_text(
        f'#!/bin/sh\nwhile [ ! -e "{release}" ]; do sleep 0.01; done\nexit 1\n', encoding='utf-8'
    )
    link = AiLink(install_root=tmp_path, session_url='ws://127.0.0.1:9/v1/session')

    link.start()

    assert link.state is LinkState.STARTING
    release.touch()
    assert wait_until(lambda: link.state is LinkState.UNAVAILABLE)
    link.stop()


def test_a_round_trip_completes(service, started_link, mocker):
    """A ping goes out, and its pong is counted, while the game carries on."""
    fake, url = service
    mocker.patch.object(ai_link, 'PING_INTERVAL_SECONDS', 0.01)

    link = started_link(session_url=url)

    assert wait_until(lambda: link.round_trips >= 2)
    assert fake.heard[1]['type'] == 'ping'


def test_too_little_memory_means_no_ai_and_no_retry(started_link, tmp_path):
    """Not enough memory ends the attempt: nothing retries during play."""
    link = started_link(session_url='ws://127.0.0.1:9/v1/session', exit_code=EXIT_NOT_ENOUGH_MEMORY)

    assert wait_until(lambda: link.state is LinkState.NOT_ENOUGH_MEMORY)
    assert (tmp_path / 'control-calls').read_text(encoding='utf-8').strip() == 'start'


def test_a_service_that_will_not_start_is_reported(started_link):
    """Any other failure means no AI this run too."""
    link = started_link(session_url='ws://127.0.0.1:9/v1/session', exit_code=1)

    assert wait_until(lambda: link.state is LinkState.UNAVAILABLE)


def test_a_missing_key_does_not_escape_the_thread(tmp_path):
    """AI failing must never disturb the game: the error stays on the link."""
    install(root=tmp_path)
    (tmp_path / 'config' / 'service-api-key').unlink()
    link = AiLink(install_root=tmp_path, session_url='ws://127.0.0.1:9/v1/session')

    link.start()

    assert wait_until(lambda: link.state is LinkState.UNAVAILABLE)
    link.stop()


def test_a_refusal_stops_the_link_for_good(service, started_link):
    """A service on another protocol version refuses, and isn't asked again."""
    fake, url = service
    fake.first_reply = {'type': 'refused', 'reason': 'protocol_version', 'protocol_version': 99}

    link = started_link(session_url=url)

    assert wait_until(lambda: link.state is LinkState.REFUSED)
    clock.raw_sleep(0.1)
    assert fake.sessions_opened == 1


def test_a_lost_connection_is_retried(service, started_link, mocker):
    """A crashed service comes back under launchd, so the link reconnects."""
    fake, url = service
    fake.drop_after_welcome = True
    mocker.patch.object(ai_link, 'RECONNECT_DELAY_SECONDS', 0.01)

    link = started_link(session_url=url)

    assert wait_until(lambda: fake.sessions_opened >= 2)
    assert wait_until(lambda: link.state is LinkState.CONNECTED)


def test_a_service_that_is_down_is_retried_without_error(started_link, mocker):
    """Nothing listening is only a state, on the link's thread."""
    mocker.patch.object(ai_link, 'RECONNECT_DELAY_SECONDS', 0.01)

    link = started_link(session_url='ws://127.0.0.1:9/v1/session')

    assert wait_until(lambda: link.state is LinkState.RECONNECTING)


def test_waiting_to_reconnect_uses_the_engines_sleep_or_the_one_given(tmp_path):
    """The wait is injected, so a test or a caller can replace it."""
    install(root=tmp_path)
    waits = []
    link = AiLink(
        install_root=tmp_path, session_url='ws://127.0.0.1:9/v1/session', sleep=waits.append
    )

    link.start()

    assert wait_until(lambda: len(waits) >= 2)
    assert waits[0] == ai_link.RECONNECT_DELAY_SECONDS
    link.stop()


def test_stop_closes_the_session_so_the_service_can_count_it(service, started_link):
    """Closing is what tells the service one game has gone."""
    fake, url = service
    link = started_link(session_url=url)
    assert wait_until(lambda: link.state is LinkState.CONNECTED)

    link.stop()

    assert link.state is LinkState.STOPPED
    assert fake.sessions_closed.wait(timeout=WAIT_SECONDS)


def test_stop_before_start_is_harmless(tmp_path):
    """A run that never reached the game still tears down."""
    link = AiLink(install_root=tmp_path)

    link.stop()

    assert link.state is LinkState.STOPPED


def test_stop_during_a_retry_ends_the_thread(mocker, tmp_path):
    """Stopping while waiting to reconnect doesn't start another attempt."""
    install(root=tmp_path)
    link = AiLink(
        install_root=tmp_path,
        session_url='ws://127.0.0.1:9/v1/session',
        sleep=lambda _seconds: link.stop(),
    )
    connect = mocker.spy(ai_link.clock, 'raw_sleep')

    link._run()  # Run directly: the stop then comes from the same thread, deterministically

    assert link.state is LinkState.STOPPED
    connect.assert_not_called()


def test_messages_for_the_game_reach_the_inbox_in_order(service, started_link):
    """What isn't the session's own goes to the game, oldest first."""
    fake, url = service
    fake.to_send = [{'type': 'first'}, {'type': 'second'}]

    link = started_link(session_url=url)
    assert wait_until(lambda: len(link._inbox) == 2)

    assert [message['type'] for message in link.take_messages()] == ['first', 'second']
    assert link.take_messages() == []


@pytest.mark.parametrize('bad_message', ['not json', '[1, 2]', '{"no": "type"}'])
def test_a_bad_message_is_dropped_and_the_link_goes_on(service, started_link, bad_message):
    """Nothing the service sends can end the link or reach the game."""
    fake, url = service
    fake.to_send = [bad_message, {'type': 'after'}]

    link = started_link(session_url=url)

    assert wait_until(lambda: len(link._inbox) == 1)
    assert link.take_messages() == [{'type': 'after'}]
    assert link.state is LinkState.CONNECTED


def test_the_inbox_keeps_only_the_newest(tmp_path):
    """AI that falls behind drops old proposals, rather than building a backlog."""
    link = AiLink(install_root=tmp_path)

    for number in range(MAXIMUM_INBOX_MESSAGES + 5):
        link._receive(text=json.dumps({'type': 'x', 'number': number}))

    messages = link.take_messages()
    assert len(messages) == MAXIMUM_INBOX_MESSAGES
    assert messages[0]['number'] == 5


@pytest.mark.parametrize(
    'options',
    [{'ai': False}, {'ai': True, 'headless': True}, {}],
    ids=['no-ai', 'headless', 'option-missing'],
)
def test_a_run_that_should_have_no_ai_gets_no_link(options, tmp_path, monkeypatch):
    """Even with the service installed: --no-ai and every tool's headless run leave it alone."""
    install(root=tmp_path)
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))

    assert create_link(options=options) is None


def test_a_browser_gets_no_link(tmp_path, monkeypatch):
    """A browser can't start the service."""
    install(root=tmp_path)
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))
    monkeypatch.setattr(ai_link.sys, 'platform', 'emscripten')

    assert create_link(options={'ai': True}) is None


def test_a_machine_without_the_service_gets_no_link():
    """The usual case for a player without it. The harness points the install nowhere."""
    assert create_link(options={'ai': True}) is None


def test_an_install_without_a_key_gets_no_link(tmp_path, monkeypatch):
    """A damaged install is no AI, not a crash."""
    install(root=tmp_path)
    (tmp_path / 'config' / 'service-api-key').unlink()
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))

    assert create_link(options={'ai': True}) is None


def test_an_installed_service_gets_a_link_not_yet_started(tmp_path, monkeypatch):
    """Nothing starts until the game loads."""
    calls = install(root=tmp_path)
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))

    link = create_link(options={'ai': True})

    assert link is not None
    assert link.state is LinkState.NOT_STARTED
    assert not calls.exists()


def test_a_run_without_ai_never_imports_websockets_or_the_ai_layer():
    """No AI means no cost: the imports are what the design promises."""
    lines = Path(ai_link.__file__).read_text(encoding='utf-8').splitlines()
    top_level = [line for line in lines if line.startswith(('import ', 'from '))]

    assert not [line for line in top_level if 'websockets' in line or 'ai_host' in line]


class FakeInnerSources:
    """The few door members the AI's subclass reaches through."""

    random_seed = 1

    def __init__(self, *, events: list[pygame.event.Event]) -> None:
        """Hold the batch to answer with."""
        self.events = events

    def pump_events(self) -> list[pygame.event.Event]:
        """Return the batch."""
        return self.events


def test_the_ai_doors_are_host_doors(tmp_path):
    """They're a subclass: the frozen host is used, never edited."""
    assert issubclass(AiHostSources, HostSources)
    link = AiLink(install_root=tmp_path)
    doors = AiHostSources(inner=FakeInnerSources(events=[]), link=link)
    assert doors.link is link
    assert doors.overlay is None


def test_a_proposal_joins_the_batch_after_the_players_events(tmp_path):
    """Proposals follow what really happened, and each arrives once."""
    player = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, scancode=4, mod=0, unicode='a')
    link = AiLink(install_root=tmp_path)
    doors = AiHostSources(inner=FakeInnerSources(events=[player]), link=link)
    link._receive(text=json.dumps(KEY_PRESS))

    batch = doors.pump_events()

    assert batch[0] is player
    assert batch[1].key == pygame.K_F13
    assert len(doors.pump_events()) == 1


def test_a_quiet_frame_returns_the_host_batch_untouched(tmp_path):
    """With nothing proposed, the batch is the host's own."""
    player = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, scancode=4, mod=0, unicode='a')
    doors = AiHostSources(
        inner=FakeInnerSources(events=[player]), link=AiLink(install_root=tmp_path)
    )

    assert doors.pump_events() == [player]


def test_an_input_proposal_becomes_a_complete_key_event():
    """It has what a game's handlers read."""
    event = input_event_from(message=KEY_PRESS)

    assert event is not None
    assert event.type == pygame.KEYDOWN
    assert (event.key, event.scancode, event.mod, event.unicode) == (pygame.K_F13, 104, 0, '')


@pytest.mark.parametrize(
    'message',
    [
        {'type': 'something_else'},
        {'type': 'input_event'},
        {**KEY_PRESS, 'event_type': pygame.QUIT},
        {**KEY_PRESS, 'event_type': pygame.USEREVENT},
        {**KEY_PRESS, 'key': 'a'},
        {**KEY_PRESS, 'key': True},
        {**KEY_PRESS, 'scancode': None},
    ],
    ids=['other-kind', 'empty', 'quit', 'user-event', 'text-key', 'bool-key', 'no-scancode'],
)
def test_anything_but_a_valid_key_proposal_is_refused(message):
    """A service, or anything on its port, can't quit the game or forge other events."""
    assert input_event_from(message=message) is None


def test_refused_proposals_never_reach_the_batch(tmp_path):
    """The check is applied on the way in."""
    link = AiLink(install_root=tmp_path)
    doors = AiHostSources(inner=FakeInnerSources(events=[]), link=link)
    link._receive(text=json.dumps({**KEY_PRESS, 'event_type': pygame.QUIT}))

    assert doors.pump_events() == []
