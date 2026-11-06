"""A game's live link to the local AI service: one WebSocket, on its own thread.

The service is its own project (``services/ai-service``, plans/lucid-circuit.md) and shares no code
with the engine: this speaks its wire protocol and knows nothing else about it. A game runs the same
with the service absent, stopped or crashing.

The rules:

1. The frame loop never waits. ``start`` returns at once, and ``take_messages`` only looks at a
   deque, costing one truth test on a frame with nothing waiting. Everything that can block
   (starting the service, connecting, reading the socket) happens on the link's thread.
2. Nothing runs unless it's wanted: ``create_link`` returns None for ``--no-ai``, ``--headless``
   (scripted sessions, golden traces, tools), a browser, and a machine without the service, so those
   runs build plain ``HostSources`` and never import ``websockets``. A replay never asks.
3. Starting the service is one attempt. Not enough free memory means no AI for this run: nothing is
   retried during play. A lost connection is retried slowly, as launchd restarts a crashed service.
4. A service speaking another protocol version refuses the session, and the link stops. The game and
   the service can be different versions, as they share no code.
5. The inbox is bounded, and drops its oldest message when full: AI that falls behind must not build
   an unbounded backlog, and the newest proposal is the one worth having.
6. The service stops the models when the last session closes, a crashed game's included. Nothing
   here has to, and ``stop`` only closes this game's session.
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

from glitchygames import clock, process

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from websockets.sync.connection import Connection

LOG = logging.getLogger('game.ai_link')

# Where the Ansible role and the .pkg install it, for the user running the game
DEFAULT_INSTALL_ROOT = Path.home() / 'Library' / 'Application Support' / 'GlitchyGames' / 'AI'
# Overrides DEFAULT_INSTALL_ROOT. The test harness points it nowhere, so no test can reach the real
# service on a machine that has it
INSTALL_ROOT_ENVIRONMENT_VARIABLE = 'GLITCHYGAMES_AI_INSTALL_ROOT'
DEFAULT_SESSION_URL = 'ws://127.0.0.1:11449/v1/session'

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
# bin/ai-service.sh's exit code when no model fits in the memory free right now
EXIT_NOT_ENOUGH_MEMORY = 3


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
        install_root: Path,
        session_url: str = DEFAULT_SESSION_URL,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        """Prepare the link. Nothing starts until ``start``.

        Args:
            install_root: Where the service is installed.
            session_url: Where its WebSocket listens.
            sleep: The wait between connection attempts. None is ``clock.raw_sleep``, looked up at
                each wait, so a patch on ``glitchygames.clock`` reaches it.

        """
        self.control_script = install_root / 'bin' / 'ai-service.sh'
        self.key_file = install_root / 'config' / 'service-api-key'
        self.session_url = session_url
        self.sleep = sleep
        self.state = LinkState.NOT_STARTED
        self.round_trips = 0
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
            command=[str(self.control_script), 'start'],
            environment={'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'},
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

        key = self.key_file.read_text(encoding='utf-8').strip()
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
            LOG.info('Connected to the local AI service')
        elif kind == 'pong':
            self.round_trips += 1
        elif kind == 'refused':
            LOG.warning('No AI this run: the service refused this game: %s', message.get('reason'))
            self.state = LinkState.REFUSED
        elif kind is not None:
            self._inbox.append(message)


def install_root() -> Path:
    """Return where the service is installed on this machine.

    Returns:
        The environment variable's choice, else ``DEFAULT_INSTALL_ROOT``.

    """
    return Path(os.environ.get(INSTALL_ROOT_ENVIRONMENT_VARIABLE, DEFAULT_INSTALL_ROOT))


def create_link(*, options: Mapping[str, Any]) -> AiLink | None:
    """Create the link a run should have, if any (rule 2).

    Args:
        options: The run's options.

    Returns:
        The link, not started, or None for a run with no AI.

    """
    if not options.get('ai') or options.get('headless') or sys.platform == 'emscripten':
        return None
    root = install_root()
    if not (root / 'bin' / 'ai-service.sh').is_file():
        LOG.debug('The local AI service is not installed at %s', root)
        return None
    if not (root / 'config' / 'service-api-key').is_file():
        LOG.warning('The local AI service at %s has no key', root)
        return None
    return AiLink(install_root=root)
