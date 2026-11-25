"""A game's link to the AI service, against a real local WebSocket server and a real script."""

from __future__ import annotations

import errno
import json
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    ServiceLocations,
    create_link,
    service_locations,
)
from glitchygames.feature_flags import flag_state, take_flag_options
from glitchygames.host import HostSources
from tests.ai_service_stand_in import SERVICE_KEY, install

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

# Every install here runs its control script, on Windows too (tests/ai_service_stand_in.py)
pytestmark = pytest.mark.usefixtures('stand_in_ai_control_scripts')

WAIT_SECONDS = 10.0
KEY_PRESS = {
    'type': 'input_event',
    'event_type': pygame.KEYDOWN,
    'key': pygame.K_F13,
    'scancode': 104,
}


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
        link = AiLink(
            locations=ServiceLocations.in_one_folder(root=tmp_path), session_url=session_url
        )
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


# What ai-service.sh needs from the game's environment on Linux: the folders that choose the
# user's data (the engine's rule, which the script follows) and the way to systemd's user manager
FORWARDED_TO_THE_CONTROL_SCRIPT = {
    'XDG_DATA_HOME': '/home/player/data',
    ai_link.USER_ROOT_ENVIRONMENT_VARIABLE: '/home/player/ai',
    ai_link.PROGRAM_ROOT_ENVIRONMENT_VARIABLE: '/opt/elsewhere',
    INSTALL_ROOT_ENVIRONMENT_VARIABLE: '/srv/one-folder',
    'XDG_RUNTIME_DIR': '/run/user/1000',
    'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1000/bus',
}


def recorded_environment(*, record: Path) -> dict[str, str]:
    """Read the environment a stand-in control script recorded.

    Returns:
        Each variable's value, by name.

    """
    lines = record.read_text(encoding='utf-8').splitlines()
    return dict(line.split('=', 1) for line in lines if '=' in line)


@pytest.mark.parametrize('variables', ['set', 'empty', 'unset'])
def test_the_control_script_gets_the_folders_and_the_user_bus_and_nothing_else(
    variables, tmp_path, monkeypatch
):
    """The script finds the user's folder as the engine does, and can reach systemctl --user.

    Without XDG_RUNTIME_DIR or DBUS_SESSION_BUS_ADDRESS, systemctl --user can't find the user's
    bus (systemd 257: "$DBUS_SESSION_BUS_ADDRESS and $XDG_RUNTIME_DIR not defined"). Anything
    else in the game's environment stays behind, and a variable that isn't set isn't invented.
    An empty one counts as unset, as it does for the engine and the scripts, so it isn't passed on.
    """
    variables_set = variables == 'set'
    record = tmp_path / 'environment'
    install(root=tmp_path, environment_record=record)
    for name, value in FORWARDED_TO_THE_CONTROL_SCRIPT.items():
        if variables == 'set':
            monkeypatch.setenv(name, value)
        elif variables == 'empty':
            monkeypatch.setenv(name, '')
        else:
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('GLITCHYGAMES_UNRELATED_SETTING', 'stays with the game')
    link = AiLink(
        locations=ServiceLocations.in_one_folder(root=tmp_path),
        session_url='ws://127.0.0.1:9/v1/session',
    )
    try:
        link.start()
        assert wait_until(lambda: link.state is LinkState.RECONNECTING)
    finally:
        link.stop()

    environment = recorded_environment(record=record)
    for name, value in FORWARDED_TO_THE_CONTROL_SCRIPT.items():
        assert environment.get(name) == (value if variables_set else None), name
    assert environment['HOME'] == str(Path.home())
    assert 'GLITCHYGAMES_UNRELATED_SETTING' not in environment


def test_start_returns_before_the_service_does(tmp_path):
    """The frame loop never waits: a script that takes a while doesn't hold up start()."""
    release = tmp_path / 'release'
    install(root=tmp_path, exit_code=1, waits_for=release)
    link = AiLink(
        locations=ServiceLocations.in_one_folder(root=tmp_path),
        session_url='ws://127.0.0.1:9/v1/session',
    )

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
    link = AiLink(
        locations=ServiceLocations.in_one_folder(root=tmp_path),
        session_url='ws://127.0.0.1:9/v1/session',
    )

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


def refuse_every_connection_at_once(mocker: MockerFixture) -> Any:
    """Make every connection attempt refused at once, as a closed port refuses it on a Mac.

    websockets' sync connect lets socket.create_connection's ConnectionRefusedError through
    (websockets 17.4, checked against 127.0.0.1:9). A real refused connect is no measure of
    anything: on Windows one to a closed loopback port takes seconds, as the stack retries the
    SYN after the reset (CI job 4022 ran out of its 10 s waiting for two).

    Returns:
        The patched connect, whose calls are the attempts.
    """
    return mocker.patch(
        'websockets.sync.client.connect',
        side_effect=ConnectionRefusedError(errno.ECONNREFUSED, 'Connection refused'),
    )


def test_stop_ends_the_wait_to_reconnect(tmp_path, mocker):
    """A game quitting with nothing listening is not held up, and leaves no thread behind."""
    install(root=tmp_path)
    refuse_every_connection_at_once(mocker)
    # Far longer than stop's own wait for the thread
    mocker.patch.object(ai_link, 'RECONNECT_DELAY_SECONDS', 30.0)
    link = AiLink(
        locations=ServiceLocations.in_one_folder(root=tmp_path),
        session_url='ws://127.0.0.1:9/v1/session',
    )
    link.start()
    assert wait_until(lambda: link.state is LinkState.RECONNECTING)

    link.stop()

    assert link._thread is not None
    link._thread.join(timeout=WAIT_SECONDS)
    assert not link._thread.is_alive()


def test_waiting_to_reconnect_uses_the_sleep_given(tmp_path, mocker):
    """The wait is injected, so a test or a caller can replace it."""
    install(root=tmp_path)
    attempts = refuse_every_connection_at_once(mocker)
    waits = []

    def stop_after_the_second_wait(seconds: float) -> None:
        waits.append(seconds)
        if len(waits) == 2:
            link.stop()

    link = AiLink(
        locations=ServiceLocations.in_one_folder(root=tmp_path),
        session_url='ws://127.0.0.1:9/v1/session',
        sleep=stop_after_the_second_wait,
    )
    # Were the wait given ignored, the link would wait on its own and never stop: this error ends
    # the run instead (the link reports it as UNAVAILABLE)
    mocker.patch.object(
        link._stopping, 'wait', side_effect=AssertionError('waited on its own, not the given')
    )

    link._run()  # Run directly: the stop then comes from the same thread, deterministically

    assert waits == [ai_link.RECONNECT_DELAY_SECONDS] * 2
    assert attempts.call_count == 2
    assert link.state is LinkState.STOPPED


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
    link = AiLink(locations=ServiceLocations.in_one_folder(root=tmp_path))

    link.stop()

    assert link.state is LinkState.STOPPED


def test_stop_during_a_retry_ends_the_thread(tmp_path):
    """Stopping while waiting to reconnect doesn't start another attempt."""
    install(root=tmp_path)
    waits = []

    def stop_while_waiting(seconds: float) -> None:
        waits.append(seconds)
        link.stop()

    link = AiLink(
        locations=ServiceLocations.in_one_folder(root=tmp_path),
        session_url='ws://127.0.0.1:9/v1/session',
        sleep=stop_while_waiting,
    )

    link._run()  # Run directly: the stop then comes from the same thread, deterministically

    assert link.state is LinkState.STOPPED
    assert len(waits) == 1


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
    link = AiLink(locations=ServiceLocations.in_one_folder(root=tmp_path))

    for number in range(MAXIMUM_INBOX_MESSAGES + 5):
        link._receive(text=json.dumps({'type': 'x', 'number': number}))

    messages = link.take_messages()
    assert len(messages) == MAXIMUM_INBOX_MESSAGES
    assert messages[0]['number'] == 5


def asked(*, lucid_circuit: bool | None) -> dict[str, Any]:
    """The options of a run whose engine asked this of Lucid Circuit (None: nothing typed).

    Returns:
        The options, as the engine takes them, with the context's answer set.

    """
    options: dict[str, Any] = {'lucid_circuit': lucid_circuit}
    take_flag_options(options=options)
    return options


@pytest.mark.parametrize(
    ('lucid_circuit', 'headless', 'linked'),
    [
        (None, False, True),
        (True, False, True),
        (False, False, False),
        (None, True, False),
        (True, True, False),
        (False, True, False),
    ],
)
def test_a_run_gets_a_link_when_lucid_circuit_is_on_and_it_is_not_headless(
    lucid_circuit, headless, linked, tmp_path, monkeypatch
):
    """With the service installed: --no-lucid-circuit and every tool's headless run get none."""
    install(root=tmp_path)
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))
    options = {**asked(lucid_circuit=lucid_circuit), 'headless': headless}

    assert (create_link(options=options) is not None) is linked


@pytest.mark.parametrize('options', [{}, {'ai': True}, {'lucid_circuit': None}])
def test_options_without_an_answer_get_no_link(options, tmp_path, monkeypatch):
    """Ruling C: an old caller's options fail closed, though the flag's default is on."""
    install(root=tmp_path)
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))

    assert flag_state(name='lucid-circuit').on
    assert create_link(options=options) is None


@pytest.mark.parametrize('context_says', [True, False])
def test_options_and_context_must_both_turn_it_on(context_says, tmp_path, monkeypatch):
    """Neither can turn on what the other turned off."""
    install(root=tmp_path)
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))
    asked(lucid_circuit=context_says)

    assert create_link(options={'lucid_circuit': not context_says}) is None


@pytest.mark.parametrize(
    'run',
    [
        (False, {'lucid_circuit': False}, 'turned off by --no-lucid-circuit'),
        (True, {'lucid_circuit': True, 'headless': True}, 'never used with --headless'),
        (True, {}, 'the options given do not turn it on'),
        (True, {'lucid_circuit': False}, 'the options given do not turn it on'),
    ],
    ids=['off', 'headless', 'no-answer', 'vetoed'],
)
def test_a_run_with_lucid_circuit_off_says_why(run, tmp_path, monkeypatch, caplog):
    """The flag's own reason, or the gate's, with the service installed.

    Each run is what the context was asked, the options given and the reason.
    """
    lucid_circuit, options, reason = run
    install(root=tmp_path)
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))
    asked(lucid_circuit=lucid_circuit)

    with caplog.at_level(logging.INFO, logger=ai_link.LOG.name):
        create_link(options=options)

    assert caplog.messages == [f'Lucid Circuit is off: {reason}']


def test_a_machine_without_the_service_says_so(caplog):
    """The same words begin it."""
    with caplog.at_level(logging.INFO, logger=ai_link.LOG.name):
        create_link(options=asked(lucid_circuit=True))

    (record,) = caplog.records
    locations = service_locations()
    assert locations is not None
    assert record.levelno == logging.INFO
    assert record.getMessage() == (
        f'Lucid Circuit is off: the AI service is not installed at {locations.program_root}'
    )


def test_a_platform_without_the_service_says_so(mocker, no_location_variables, caplog):
    """Windows, by the platform's name."""
    mocker.patch.object(ai_link.sys, 'platform', 'win32')

    with caplog.at_level(logging.INFO, logger=ai_link.LOG.name):
        create_link(options=asked(lucid_circuit=True))

    assert caplog.messages == ['Lucid Circuit is off: no AI service on the platform win32']


def test_an_install_without_a_key_says_so(tmp_path, monkeypatch, caplog):
    """A damaged install is a warning."""
    install(root=tmp_path)
    (tmp_path / 'config' / 'service-api-key').unlink()
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))

    with caplog.at_level(logging.INFO, logger=ai_link.LOG.name):
        create_link(options=asked(lucid_circuit=True))

    (record,) = caplog.records
    assert record.levelno == logging.WARNING
    assert record.getMessage() == f'Lucid Circuit is off: the AI service at {tmp_path} has no key'


def test_a_browser_gets_no_link(tmp_path, monkeypatch, caplog):
    """The flag's availability decides, with its reason, even where a service is found."""
    install(root=tmp_path)
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))
    options = asked(lucid_circuit=True)
    monkeypatch.setattr(ai_link.sys, 'platform', 'emscripten')

    with caplog.at_level(logging.INFO, logger=ai_link.LOG.name):
        link = create_link(options=options)

    assert link is None
    (message,) = caplog.messages
    assert message.startswith('Lucid Circuit is off: unavailable in the browser')


def test_a_machine_without_the_service_gets_no_link():
    """The usual case for a player without it. The harness points the install nowhere."""
    assert create_link(options={'lucid_circuit': True}) is None


def test_an_install_without_a_key_gets_no_link(tmp_path, monkeypatch):
    """A damaged install is no AI, not a crash."""
    install(root=tmp_path)
    (tmp_path / 'config' / 'service-api-key').unlink()
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))

    assert create_link(options={'lucid_circuit': True}) is None


def test_an_installed_service_gets_a_link_not_yet_started(tmp_path, monkeypatch):
    """Nothing starts until the game loads."""
    calls = install(root=tmp_path)
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))

    link = create_link(options={'lucid_circuit': True})

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
    link = AiLink(locations=ServiceLocations.in_one_folder(root=tmp_path))
    doors = AiHostSources(inner=FakeInnerSources(events=[]), link=link)
    assert doors.link is link
    assert doors.overlay is None


def test_a_proposal_joins_the_batch_after_the_players_events(tmp_path):
    """Proposals follow what really happened, and each arrives once."""
    player = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, scancode=4, mod=0, unicode='a')
    link = AiLink(locations=ServiceLocations.in_one_folder(root=tmp_path))
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
        inner=FakeInnerSources(events=[player]),
        link=AiLink(locations=ServiceLocations.in_one_folder(root=tmp_path)),
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
    link = AiLink(locations=ServiceLocations.in_one_folder(root=tmp_path))
    doors = AiHostSources(inner=FakeInnerSources(events=[]), link=link)
    link._receive(text=json.dumps({**KEY_PRESS, 'event_type': pygame.QUIT}))

    assert doors.pump_events() == []


LINUX_DATA_HOME = Path('/home/player/.local/share')


@pytest.fixture
def no_location_variables(monkeypatch):
    """Leave the platform to choose: the harness points the install variable nowhere."""
    for name in (
        INSTALL_ROOT_ENVIRONMENT_VARIABLE,
        ai_link.PROGRAM_ROOT_ENVIRONMENT_VARIABLE,
        ai_link.USER_ROOT_ENVIRONMENT_VARIABLE,
    ):
        monkeypatch.delenv(name, raising=False)


def test_service_locations_on_macos_are_one_folder(no_location_variables, mocker):
    """The Ansible role and the .pkg install into one folder."""
    mocker.patch.object(ai_link.sys, 'platform', 'darwin')

    locations = service_locations()

    expected = Path.home() / 'Library' / 'Application Support' / 'GlitchyGames' / 'AI'
    assert locations == ServiceLocations(program_root=expected, user_root=expected)


def test_service_locations_on_linux_split_programs_and_user_data(
    no_location_variables, monkeypatch, mocker
):
    """The programs are in /opt; the keys, settings and history are the user's own."""
    mocker.patch.object(ai_link.sys, 'platform', 'linux')
    monkeypatch.setenv('XDG_DATA_HOME', str(LINUX_DATA_HOME))

    with_xdg = service_locations()

    monkeypatch.delenv('XDG_DATA_HOME')
    without_xdg = service_locations()
    assert with_xdg == ServiceLocations(
        program_root=Path('/opt/glitchygames/ai'), user_root=LINUX_DATA_HOME / 'glitchygames' / 'ai'
    )
    assert without_xdg == ServiceLocations(
        program_root=Path('/opt/glitchygames/ai'),
        user_root=Path.home() / '.local' / 'share' / 'glitchygames' / 'ai',
    )


def test_the_placement_file_lives_in_the_user_config(tmp_path):
    """setup.sh writes the CPU placement beside the key, in the user's own config."""
    locations = ServiceLocations(program_root=tmp_path / 'programs', user_root=tmp_path / 'user')

    assert locations.cpu_placement_file == tmp_path / 'user' / 'config' / 'cpu-placement.json'
    assert ServiceLocations.in_one_folder(root=tmp_path).cpu_placement_file == (
        tmp_path / 'config' / 'cpu-placement.json'
    )


def test_the_install_root_variable_still_sets_both_roots(tmp_path, monkeypatch, mocker):
    """On any platform, a test's one folder."""
    mocker.patch.object(ai_link.sys, 'platform', 'win32')
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))

    assert service_locations() == ServiceLocations.in_one_folder(root=tmp_path)


def test_the_program_and_user_variables_each_set_one_and_win(tmp_path, monkeypatch):
    """Each variable moves its own root, over the one-folder variable."""
    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path / 'one'))
    monkeypatch.setenv(ai_link.PROGRAM_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path / 'programs'))

    only_programs = service_locations()

    monkeypatch.setenv(ai_link.USER_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path / 'user'))
    both = service_locations()
    assert only_programs == ServiceLocations(
        program_root=tmp_path / 'programs', user_root=tmp_path / 'one'
    )
    assert both == ServiceLocations(program_root=tmp_path / 'programs', user_root=tmp_path / 'user')


def test_one_variable_alone_completes_a_platform_without_defaults(
    no_location_variables, tmp_path, monkeypatch, mocker
):
    """Both roots named means the platform needs no default."""
    mocker.patch.object(ai_link.sys, 'platform', 'win32')
    monkeypatch.setenv(ai_link.PROGRAM_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path / 'programs'))
    assert service_locations() is None

    monkeypatch.setenv(ai_link.USER_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path / 'user'))

    assert service_locations() == ServiceLocations(
        program_root=tmp_path / 'programs', user_root=tmp_path / 'user'
    )


@pytest.mark.parametrize('platform', ['darwin', 'linux'])
def test_an_empty_location_variable_counts_as_unset(
    platform, no_location_variables, tmp_path, monkeypatch, mocker
):
    """An empty variable is no folder at all, not Path('') (the current folder), as in the scripts.

    platform_functions.sh.j2 tests each with ``[ -n ... ]``, so the engine must too, or the two
    would look for the service in different places.
    """
    mocker.patch.object(ai_link.sys, 'platform', platform)
    monkeypatch.setenv('XDG_DATA_HOME', str(LINUX_DATA_HOME))
    platform_default = service_locations()
    for name in (
        INSTALL_ROOT_ENVIRONMENT_VARIABLE,
        ai_link.PROGRAM_ROOT_ENVIRONMENT_VARIABLE,
        ai_link.USER_ROOT_ENVIRONMENT_VARIABLE,
    ):
        monkeypatch.setenv(name, '')

    all_empty = service_locations()

    monkeypatch.setenv(INSTALL_ROOT_ENVIRONMENT_VARIABLE, str(tmp_path))
    only_one_folder = service_locations()
    assert platform_default is not None
    assert all_empty == platform_default
    assert only_one_folder == ServiceLocations.in_one_folder(root=tmp_path)


@pytest.mark.parametrize('platform', ['win32', 'emscripten'])
def test_another_platform_has_no_locations_and_no_link(platform, no_location_variables, mocker):
    """Neither has the service."""
    mocker.patch.object(ai_link.sys, 'platform', platform)

    assert service_locations() is None
    assert create_link(options={'lucid_circuit': True}) is None


def test_create_link_needs_the_control_script_and_the_key_in_their_own_roots(tmp_path, monkeypatch):
    """The script is under the program root only, the key under the user root only."""
    programs = tmp_path / 'programs'
    user = tmp_path / 'user'
    monkeypatch.setenv(ai_link.PROGRAM_ROOT_ENVIRONMENT_VARIABLE, str(programs))
    monkeypatch.setenv(ai_link.USER_ROOT_ENVIRONMENT_VARIABLE, str(user))
    install(root=programs)
    (user / 'config').mkdir(parents=True)
    assert create_link(options={'lucid_circuit': True}) is None  # no key in the user root

    (user / 'config' / 'service-api-key').write_text(SERVICE_KEY, encoding='utf-8')
    link = create_link(options={'lucid_circuit': True})
    assert link is not None
    assert link.locations == ServiceLocations(program_root=programs, user_root=user)

    (programs / 'bin' / 'ai-service.sh').unlink()
    assert create_link(options={'lucid_circuit': True}) is None  # no script in the program root
    (programs / 'bin' / 'ai-service.sh').touch()
    (user / 'config' / 'service-api-key').unlink()
    (programs / 'config' / 'service-api-key').write_text(SERVICE_KEY, encoding='utf-8')
    # A key in the program root does not count
    assert create_link(options={'lucid_circuit': True}) is None
