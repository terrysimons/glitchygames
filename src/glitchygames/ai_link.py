"""A game's live link to the local AI service: one WebSocket, on its own thread.

The service is its own project (``services/ai-service``, plans/lucid-circuit.md) and shares no code
with the engine: this speaks its wire protocol and knows nothing else about it. A game runs the same
with the service absent, stopped or crashing.

The rules:

1. The frame loop never waits. ``start`` returns at once, and ``take_messages`` only looks at a
   deque, costing one truth test on a frame with nothing waiting. Everything that can block
   (starting the service, connecting, reading the socket) happens on the link's thread.
2. Nothing runs unless it's wanted. ``reason_lucid_circuit_is_off`` is the run's gate, for this
   link and whatever else of a game uses Lucid Circuit (Bitmappy's AI): off in a replay, when its
   flag is off (``--no-lucid-circuit``, a browser: ``glitchygames/feature_flags.py``), when the
   options hold no answer for the flag, and with ``--headless``. ``create_link`` returns None for
   such a run, and on a machine without the service: the run then builds plain ``HostSources``
   and never imports ``websockets``. A replay's engine has no host, and makes no link. Each says
   why (``log_lucid_circuit_off``). Where the service is stays each user's own check, and so does
   whether there is a run to ask.
3. Starting the service is one attempt. Not enough free memory means no AI for this run: nothing is
   retried during play. A lost connection is retried slowly, as launchd restarts a crashed service.
4. A service speaking another protocol version refuses the session, and the link stops. The game and
   the service can be different versions, as they share no code.
5. The inbox is bounded, and drops its oldest message when full: AI that falls behind must not build
   an unbounded backlog, and the newest proposal is the one worth having.
6. The service stops the models when the last session closes, a crashed game's included. Nothing
   here has to, and ``stop`` only closes this game's session.

Where the service is: ``service_locations()``, which every module and script follows
(plans/lucid-circuit-linux.md, 6.1). A Mac has one folder; Linux has two roots, the programs
(``/opt/glitchygames/ai``, the .deb's) and the user's data (``$XDG_DATA_HOME/glitchygames/ai``).
``GLITCHYGAMES_AI_INSTALL_ROOT`` sets both; ``GLITCHYGAMES_AI_PROGRAM_ROOT`` and
``GLITCHYGAMES_AI_USER_ROOT`` each set one and win over it (empty counts as unset). The test
harness sets the first to nowhere and removes the other two, so nothing a shell exports reaches the
real service (tests/test_ai_service_isolation_guard.py). On Linux the game pins itself to its own
core once the link reports the service started (``src/glitchygames/cpu_placement.py``, reading the
placement setup.sh wrote).
"""

from __future__ import annotations

import collections
import json
import logging
import os
import sys
import threading
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, ConfigDict

from glitchygames import clock, process
from glitchygames.feature_flags import LUCID_CIRCUIT, flag_state, option_name
from glitchygames.state.paths import platform_data_home

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from websockets.sync.connection import Connection

LOG = logging.getLogger('game.ai_link')

# Sets both roots. The test harness points it nowhere, so no test can reach the real service on a
# machine that has it
INSTALL_ROOT_ENVIRONMENT_VARIABLE = 'GLITCHYGAMES_AI_INSTALL_ROOT'
# Each sets one root, and wins over INSTALL_ROOT_ENVIRONMENT_VARIABLE (plans/lucid-circuit-linux.md
# 6.1: the programs and the user's data are in different places on Linux)
PROGRAM_ROOT_ENVIRONMENT_VARIABLE = 'GLITCHYGAMES_AI_PROGRAM_ROOT'
USER_ROOT_ENVIRONMENT_VARIABLE = 'GLITCHYGAMES_AI_USER_ROOT'
# Where the Linux package puts the programs; the user's data is under platform_data_home()
LINUX_PROGRAM_ROOT = Path('/opt/glitchygames/ai')
# What the control script gets of the game's environment beyond HOME and PATH, each only when set
# and not empty (an empty variable counts as unset, here and in the scripts):
# the variables that choose the service's folders, so the script resolves the same user folder as
# service_locations, and the two that lead systemctl --user to the user manager's bus, without
# which it can't start a unit (plans/lucid-circuit-linux.md, 6.2)
CONTROL_SCRIPT_ENVIRONMENT_VARIABLES = (
    'XDG_DATA_HOME',
    USER_ROOT_ENVIRONMENT_VARIABLE,
    PROGRAM_ROOT_ENVIRONMENT_VARIABLE,
    INSTALL_ROOT_ENVIRONMENT_VARIABLE,
    'XDG_RUNTIME_DIR',
    'DBUS_SESSION_BUS_ADDRESS',
)
DEFAULT_SESSION_URL = 'ws://127.0.0.1:23231/v1/session'

# Bumped with the service's own PROTOCOL_VERSION when the messages change incompatibly
PROTOCOL_VERSION = 1
START_TIMEOUT_SECONDS = 60.0
CONNECT_TIMEOUT_SECONDS = 5.0
# How long one read of the socket waits, so a stop is noticed this soon
RECEIVE_POLL_SECONDS = 0.25
PING_INTERVAL_SECONDS = 5.0
RECONNECT_DELAY_SECONDS = 2.0
STOP_JOIN_SECONDS = 1.0
MAXIMUM_INBOX_MESSAGES = 64
# bin/ai-service.sh's exit code when no model fits in the memory free right now. The only copy:
# glitchygames.ai.local_service reads it from here
EXIT_NOT_ENOUGH_MEMORY = 3
# Why a run playing a recording has no AI
REPLAY_OFF_REASON = 'never used in a replay'


class ServiceLocations(BaseModel):
    """Where the service's programs are, and where its keys, settings and history are.

    On a Mac both are one folder; on Linux the programs are in ``/opt`` and the user's data is in
    the user's own data folder. Every module that touches the service reads both from here.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    program_root: Path
    user_root: Path

    @classmethod
    def in_one_folder(cls, *, root: Path) -> ServiceLocations:
        """Return locations with both roots the same, as on a Mac and in tests.

        Args:
            root: The one folder.

        Returns:
            The locations.

        """
        return cls(program_root=root, user_root=root)

    @property
    def control_script(self) -> Path:
        """The script that starts, stops and reports on the service."""
        return self.program_root / 'bin' / 'ai-service.sh'

    @property
    def key_file(self) -> Path:
        """The key a game presents to the service."""
        return self.user_root / 'config' / 'service-api-key'

    @property
    def cpu_placement_file(self) -> Path:
        """The cores the game, its mirror and the AI run on, as setup.sh wrote them (Linux)."""
        return self.user_root / 'config' / 'cpu-placement.json'

    @property
    def history_directory(self) -> Path:
        """Where the AI console keeps each game's history."""
        return self.user_root / 'history'


def _environment_value(*, name: str) -> str | None:
    """Return an environment variable's value, with an empty one counting as unset.

    The scripts test each with ``[ -n ... ]`` (platform_functions.sh.j2), so the engine must too:
    ``Path('')`` would be the current folder.

    Args:
        name: The variable.

    Returns:
        Its value, or None when it is unset or empty.

    """
    return os.environ.get(name) or None


def service_locations() -> ServiceLocations | None:
    """Return where the service is installed on this machine.

    Returns:
        The locations the environment variables choose (an empty one counts as unset), else this
        platform's: one folder on macOS, split programs and user data on Linux. None on any other
        platform.

    """
    one_folder = _environment_value(name=INSTALL_ROOT_ENVIRONMENT_VARIABLE)
    program_override = _environment_value(name=PROGRAM_ROOT_ENVIRONMENT_VARIABLE)
    user_override = _environment_value(name=USER_ROOT_ENVIRONMENT_VARIABLE)
    if sys.platform == 'darwin':
        program_default = user_default = platform_data_home() / 'GlitchyGames' / 'AI'
    elif sys.platform.startswith('linux'):
        program_default = LINUX_PROGRAM_ROOT
        user_default = platform_data_home() / 'glitchygames' / 'ai'
    else:
        program_default = user_default = None
    if one_folder is not None:
        program_default = user_default = Path(one_folder)
    program_root = Path(program_override) if program_override is not None else program_default
    user_root = Path(user_override) if user_override is not None else user_default
    if program_root is None or user_root is None:
        return None
    return ServiceLocations(program_root=program_root, user_root=user_root)


def control_script_environment() -> dict[str, str]:
    """Build the environment every caller runs the control script with.

    Returns:
        HOME, a fixed PATH, and each of CONTROL_SCRIPT_ENVIRONMENT_VARIABLES that is set here and
        not empty.

    """
    environment = {'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'}
    for name in CONTROL_SCRIPT_ENVIRONMENT_VARIABLES:
        value = _environment_value(name=name)
        if value is not None:
            environment[name] = value
    return environment


class LinkState(StrEnum):
    """Where a link is. Only ``CONNECTED`` means AI can answer."""

    NOT_STARTED = 'not_started'
    STARTING = 'starting'
    CONNECTED = 'connected'
    RECONNECTING = 'reconnecting'
    NOT_ENOUGH_MEMORY = 'not_enough_memory'
    UNAVAILABLE = 'unavailable'
    REFUSED = 'refused'
    STOPPED = 'stopped'


class AiLink:
    """One game's session with the local AI service."""

    def __init__(
        self,
        *,
        locations: ServiceLocations,
        session_url: str = DEFAULT_SESSION_URL,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        """Prepare the link. Nothing starts until ``start``.

        Args:
            locations: Where the service's programs and the user's data are.
            session_url: Where its WebSocket listens.
            sleep: The wait between connection attempts. None is ``clock.raw_sleep``, looked up at
                each wait, so a patch on ``glitchygames.clock`` reaches it.

        """
        self.locations = locations
        self.session_url = session_url
        self.sleep = sleep
        self.state = LinkState.NOT_STARTED
        self.round_trips = 0
        # What the service reported as this session opened
        self.models: list[dict[str, Any]] = []
        self._inbox: collections.deque[dict[str, Any]] = collections.deque(
            maxlen=MAXIMUM_INBOX_MESSAGES
        )
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the link's thread and return at once."""
        self.state = LinkState.STARTING
        self._thread = threading.Thread(target=self._run, name='ai-link', daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Ask the thread to end, waiting only a moment: a teardown must not hang on the socket."""
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=STOP_JOIN_SECONDS)
        self.state = LinkState.STOPPED

    def take_messages(self) -> list[dict[str, Any]]:
        """Take what the service has sent. Called every frame, so nearly always just one test.

        Returns:
            The messages, oldest first.

        """
        if not self._inbox:
            return []
        messages: list[dict[str, Any]] = []
        while self._inbox:
            messages.append(self._inbox.popleft())
        return messages

    def _run(self) -> None:
        """Start the service, then hold a session until stopped. Never lets an error escape.

        A daemon thread's exception would only print: AI failing must not disturb the game at all.
        """
        try:
            if self._start_service():
                self._hold_session()
        except Exception:
            LOG.exception('The AI link stopped')
            self.state = LinkState.UNAVAILABLE

    def _start_service(self) -> bool:
        """Run ``ai-service.sh start``, which picks sizes from the machine's state right now.

        Returns:
            Whether the service started.

        """
        result = process.run_command(
            command=[str(self.locations.control_script), 'start'],
            environment=control_script_environment(),
            timeout_seconds=START_TIMEOUT_SECONDS,
            capture_output=process.OutputCapture.TOGETHER,
        )
        if result.returncode == EXIT_NOT_ENOUGH_MEMORY:
            LOG.warning('No AI this run: not enough free memory for a local model')
            self.state = LinkState.NOT_ENOUGH_MEMORY
            return False
        if result.returncode != 0:
            LOG.warning('No AI this run: the service would not start (%s)', result.returncode)
            self.state = LinkState.UNAVAILABLE
            return False
        return True

    def _hold_session(self) -> None:
        """Connect, and reconnect after a lost connection, until stopped or refused."""
        # Imported here, on this thread: a run with no AI never loads it
        from websockets.exceptions import WebSocketException
        from websockets.sync.client import connect

        key = self.locations.key_file.read_text(encoding='utf-8').strip()
        while not self._stopping.is_set():
            try:
                with connect(
                    self.session_url,
                    additional_headers={'Authorization': f'Bearer {key}'},
                    open_timeout=CONNECT_TIMEOUT_SECONDS,
                    # Our own pings carry the round trip; the library's would only duplicate them
                    ping_interval=None,
                ) as session:
                    self._serve(session=session)
                    if self.state is LinkState.REFUSED:
                        return
            except (OSError, TimeoutError, WebSocketException) as error:
                LOG.debug('The AI service is not reachable: %s', error)
            if self._stopping.is_set():
                return
            self.state = LinkState.RECONNECTING
            (clock.raw_sleep if self.sleep is None else self.sleep)(RECONNECT_DELAY_SECONDS)

    def _serve(self, *, session: Connection) -> None:
        """Say hello, then read messages and send pings until stopped or refused.

        Args:
            session: The open WebSocket.

        """
        session.send(json.dumps({'type': 'hello', 'protocol_version': PROTOCOL_VERSION}))
        next_ping = clock.raw_counter_seconds() + PING_INTERVAL_SECONDS
        sequence = 0
        while not self._stopping.is_set():
            if clock.raw_counter_seconds() >= next_ping:
                sequence += 1
                session.send(json.dumps({'type': 'ping', 'sequence': sequence}))
                next_ping = clock.raw_counter_seconds() + PING_INTERVAL_SECONDS
            try:
                text = session.recv(timeout=RECEIVE_POLL_SECONDS)
            except TimeoutError:
                continue
            self._receive(text=text)
            if self.state is LinkState.REFUSED:
                return

    def _receive(self, *, text: str | bytes) -> None:
        """Handle one message: the session's own, or one for the game.

        Args:
            text: The message as it arrived.

        """
        try:
            decoded: object = json.loads(text)
        except ValueError:
            LOG.warning('The AI service sent something other than JSON')
            return
        if not isinstance(decoded, dict):
            LOG.warning('The AI service sent something other than a message')
            return
        message = cast('dict[str, Any]', decoded)
        kind = message.get('type')
        if kind == 'welcome':
            self.state = LinkState.CONNECTED
            self.models = message.get('models', [])
            LOG.info('Connected to the local AI service')
        elif kind == 'pong':
            self.round_trips += 1
        elif kind == 'refused':
            LOG.warning('No AI this run: the service refused this game: %s', message.get('reason'))
            self.state = LinkState.REFUSED
        elif kind is not None:
            self._inbox.append(message)


def lucid_circuit_off_message(*, reason: str) -> str:
    """Return how a run says Lucid Circuit is off, in the same words for every reason (rule 2).

    Args:
        reason: The reason.

    Returns:
        The message.

    """
    return f'Lucid Circuit is off: {reason}'


def log_lucid_circuit_off(*, reason: str, level: int = logging.INFO) -> None:
    """Log why a run may not use Lucid Circuit, or that this machine's service can't be (rule 2).

    Args:
        reason: The reason.
        level: The logging level.

    """
    LOG.log(level, '%s', lucid_circuit_off_message(reason=reason))


def reason_lucid_circuit_is_off(*, options: Mapping[str, Any], in_replay: bool) -> str | None:
    """Say why a run may not use Lucid Circuit, wherever the service is (rule 2).

    A replay's reason comes first: what a replayed game says then never depends on how the replay
    was started, or on the machine.

    Args:
        options: The run's options.
        in_replay: Whether the run is playing a recording.

    Returns:
        The reason (the flag's own, when the flag is off), or None for a run that may.

    """
    if in_replay:
        return REPLAY_OFF_REASON
    lucid_circuit = flag_state(name=LUCID_CIRCUIT)
    if not lucid_circuit.on:
        return lucid_circuit.reason
    if not options.get(option_name(flag_name=LUCID_CIRCUIT)):
        return 'the options given do not turn it on'
    if options.get('headless'):
        return 'never used with --headless'
    return None


def create_link(*, options: Mapping[str, Any]) -> AiLink | None:
    """Create the link a run should have, if any (rule 2).

    The engine context's flag decides, as for every other reader of it, so one run never has two
    answers: the engine's options hold the same one (``take_flag_options`` set both), and no
    recording changes either. Options must turn it on as well: an old caller's, which hold no
    answer, get no link, and an explicit False vetoes one though the context's flag is on.
    Neither can turn on what the other did not.

    Args:
        options: The run's options, taken by its engine.

    Returns:
        The link, not started, or None for a run with no AI.

    """
    # A replay's engine makes no link: it never asks (GameEngine.__init__)
    reason = reason_lucid_circuit_is_off(options=options, in_replay=False)
    if reason is not None:
        log_lucid_circuit_off(reason=reason)
        return None
    locations = service_locations()
    if locations is None:
        log_lucid_circuit_off(reason=f'no AI service on the platform {sys.platform}')
        return None
    if not locations.control_script.is_file():
        log_lucid_circuit_off(reason=f'the AI service is not installed at {locations.program_root}')
        return None
    if not locations.key_file.is_file():
        log_lucid_circuit_off(
            reason=f'the AI service at {locations.user_root} has no key', level=logging.WARNING
        )
        return None
    return AiLink(locations=locations)
