"""The client for the local AI service, the one place the engine's AI requests go.

The service is its own project (``services/ai-service``, plans/lucid-circuit.md) and shares no code
with the engine: this speaks its REST API and knows nothing else about it. A caller uses
``create_chat_client()`` and the ``ChatClient`` Protocol, the OpenAI-style call they've always made,
so another backend (a hosted one, later) would be a second implementation of that Protocol and one
choice in the factory, with no caller changing.

This module isn't imported until an AI request is made, so a game that makes none (or a browser
build, which has no AI: it can't start the service) never loads it.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import httpx2
from pydantic import BaseModel, ConfigDict

from glitchygames import clock, process
from glitchygames.ai_link import install_root as default_install_root

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

LOG = logging.getLogger('glitchygames.ai.local_service')

DEFAULT_BASE_URL = 'http://127.0.0.1:11449'
# The role, not a size: the service answers with whichever size this machine could run
REASONING_MODEL = 'reasoning'
DEFAULT_TIMEOUT_SECONDS = 600.0

HEALTH_TIMEOUT_SECONDS = 2.0
START_TIMEOUT_SECONDS = 60.0
READY_TIMEOUT_SECONDS = 120.0
READY_POLL_SECONDS = 0.25
# bin/ai-service.sh's exit code when no model fits in the memory free right now
EXIT_NOT_ENOUGH_MEMORY = 3


class LocalAIServiceError(Exception):
    """The service couldn't answer.

    Attributes:
        status_code: The service's HTTP status, when it gave one. Bitmappy's retries read this.

    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        """Describe the failure.

        Args:
            message: What went wrong, for a person.
            status_code: The service's HTTP status, if any.

        """
        super().__init__(message)
        self.status_code = status_code


class LocalAIServiceNotInstalledError(LocalAIServiceError, ValueError):
    """The service isn't on this machine, so trying again can't help (hence ValueError)."""


class ChatMessage(BaseModel):
    """A choice's message. Fields the service adds beyond these are ignored."""

    model_config = ConfigDict(frozen=True, extra='ignore')

    content: str | None = None


class ChatChoice(BaseModel):
    """One choice of a chat completion."""

    model_config = ConfigDict(frozen=True, extra='ignore')

    message: ChatMessage


class ChatCompletion(BaseModel):
    """A chat completion."""

    model_config = ConfigDict(frozen=True, extra='ignore')

    choices: tuple[ChatChoice, ...]


class ChatResponse(Protocol):
    """What a caller reads from a completion: ``choices[0].message.content``."""

    @property
    def choices(self) -> Sequence[Any]:
        """The completion's choices."""
        ...


class ChatCompletions(Protocol):
    """The chat completions endpoint."""

    def create(
        self, *, model: str, messages: list[dict[str, Any]], max_tokens: int | None = None
    ) -> ChatResponse:
        """Request a chat completion."""
        ...


class ChatEndpoints(Protocol):
    """The client's chat namespace."""

    @property
    def completions(self) -> ChatCompletions:
        """The chat completions endpoint."""
        ...


class ChatClient(Protocol):
    """What every AI caller uses, whatever answers it."""

    @property
    def chat(self) -> ChatEndpoints:
        """The client's chat namespace."""
        ...


class LocalAIClient:
    """Sends chat requests to the local AI service, starting it first if it isn't up.

    The ``chat.completions`` attributes give it the shape of ``ChatClient``.
    """

    def __init__(
        self,
        *,
        install_root: Path | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        """Prepare the client. Nothing is contacted or started until a request.

        Args:
            install_root: Where the service is installed. None is this machine's
                (``glitchygames.ai_link.install_root``).
            base_url: Where it listens.
            timeout_seconds: The longest one chat request may take.
            sleep: The wait between readiness checks. None is ``clock.raw_sleep``, looked up at
                each wait, so a patch on ``glitchygames.clock`` reaches it.

        Raises:
            LocalAIServiceNotInstalledError: If the service isn't installed.

        """
        self.install_root = default_install_root() if install_root is None else install_root
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.sleep = sleep
        self.control_script = self.install_root / 'bin' / 'ai-service.sh'
        self.key_file = self.install_root / 'config' / 'service-api-key'
        if not self.control_script.is_file():
            message = (
                f'The local AI service is not installed (no {self.control_script}). '
                'Install it with ansible/macos_ai_service.yml or its package.'
            )
            raise LocalAIServiceNotInstalledError(message)
        # client.chat.completions.create(...), the shape every caller uses
        self.chat = self
        self.completions = self

    def create(
        self, *, model: str, messages: list[dict[str, Any]], max_tokens: int | None = None
    ) -> ChatCompletion:
        """Request a chat completion.

        Args:
            model: The model: a role (``REASONING_MODEL``), or an exact size's alias.
            messages: The conversation.
            max_tokens: The output limit, or None for the service's.

        Returns:
            The completion.

        Raises:
            LocalAIServiceError: If the service can't be started, or doesn't answer.

        """
        self._ensure_ready()
        body: dict[str, Any] = {'model': model, 'messages': messages}
        if max_tokens is not None:
            body['max_tokens'] = max_tokens
        try:
            response = httpx2.post(
                f'{self.base_url}/v1/chat/completions',
                json=body,
                headers={'Authorization': f'Bearer {self._service_key()}'},
                timeout=self.timeout_seconds,
            )
        except httpx2.HTTPError as error:
            message = f'The local AI service failed: {type(error).__name__}: {error}'
            raise LocalAIServiceError(message) from error
        if response.status_code != HTTPStatus.OK:
            message = f'The local AI service answered {response.status_code}: {response.text}'
            raise LocalAIServiceError(message, status_code=response.status_code)
        return ChatCompletion.model_validate(response.json())

    def _service_key(self) -> str:
        """Read the token clients send.

        Returns:
            The token.

        Raises:
            LocalAIServiceNotInstalledError: If it's missing.

        """
        try:
            return self.key_file.read_text(encoding='utf-8').strip()
        except OSError as error:
            message = f'The local AI service has no key at {self.key_file}'
            raise LocalAIServiceNotInstalledError(message) from error

    def _is_ready(self) -> bool:
        """Ask whether the models are answering.

        Returns:
            Whether they are. A service that isn't up, or is still loading, isn't ready.

        """
        try:
            response = httpx2.get(f'{self.base_url}/health/ready', timeout=HEALTH_TIMEOUT_SECONDS)
        except httpx2.HTTPError:
            return False
        return response.status_code == HTTPStatus.OK

    def _ensure_ready(self) -> None:
        """Start the service if it isn't up, and wait until the models answer.

        Raises:
            LocalAIServiceError: If there isn't the memory, it won't start, or it never gets ready.

        """
        if self._is_ready():
            return
        LOG.info('Starting the local AI service')
        result = process.run_command(
            command=[str(self.control_script), 'start'],
            environment={'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'},
            timeout_seconds=START_TIMEOUT_SECONDS,
            capture_output=process.OutputCapture.TOGETHER,
        )
        if result.returncode == EXIT_NOT_ENOUGH_MEMORY:
            message = 'There is not enough free memory to run a local AI model right now'
            raise LocalAIServiceError(message, status_code=HTTPStatus.SERVICE_UNAVAILABLE)
        if result.returncode != 0:
            message = f'The local AI service would not start ({result.returncode}): {result.stdout}'
            raise LocalAIServiceError(message)
        deadline = clock.raw_counter_seconds() + READY_TIMEOUT_SECONDS
        while clock.raw_counter_seconds() < deadline:
            if self._is_ready():
                return
            (clock.raw_sleep if self.sleep is None else self.sleep)(READY_POLL_SECONDS)
        message = f'The local AI service was not ready after {READY_TIMEOUT_SECONDS} s'
        raise LocalAIServiceError(message)


def create_chat_client(*, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> ChatClient:
    """Create the client AI requests go through.

    Args:
        timeout_seconds: The longest one chat request may take.

    Returns:
        The client. Only the local service answers for now.

    """
    return LocalAIClient(timeout_seconds=timeout_seconds)
