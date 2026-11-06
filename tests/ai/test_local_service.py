"""The client for the local AI service, against a real local HTTP server and a real script."""

import json
import stat
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from glitchygames.ai import local_service
from glitchygames.ai.local_service import (
    EXIT_NOT_ENOUGH_MEMORY,
    LocalAIClient,
    LocalAIServiceError,
    LocalAIServiceNotInstalledError,
    create_chat_client,
)

if TYPE_CHECKING:
    from pathlib import Path

SERVICE_KEY = 'service-token'
ANSWER = {'choices': [{'message': {'content': '42', 'reasoning_content': 'adding'}}], 'timings': {}}
MESSAGES = [{'role': 'user', 'content': 'What is 17 + 25?'}]


class FakeService:
    """How the fake service behaves, and what it was asked."""

    def __init__(self) -> None:
        """Start out healthy, answering 42."""
        self.ready_status = HTTPStatus.OK
        self.chat_status = HTTPStatus.OK
        self.chat_body: dict[str, object] = ANSWER
        self.requests: list[dict[str, object]] = []
        self.authorizations: list[str | None] = []
        self.ready_checks = 0
        # How many readiness checks answer 503 before it turns ready
        self.not_ready_for = 0


@pytest.fixture
def service():
    """Run the fake service on a real local port.

    Yields:
        The fake's state and its base URL.

    """
    fake = FakeService()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            fake.ready_checks += 1
            status = fake.ready_status
            if fake.ready_checks <= fake.not_ready_for:
                status = HTTPStatus.SERVICE_UNAVAILABLE
            self._answer(status=status, body={'ready': status == HTTPStatus.OK})

        def do_POST(self) -> None:
            length = int(self.headers['Content-Length'])
            fake.requests.append(json.loads(self.rfile.read(length)))
            fake.authorizations.append(self.headers.get('Authorization'))
            self._answer(status=fake.chat_status, body=fake.chat_body)

        def _answer(self, *, status: int, body: dict[str, object]) -> None:
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_arguments: object) -> None:
            """Keep the test output quiet."""

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield fake, f'http://127.0.0.1:{server.server_address[1]}'
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


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


def client_for(*, root: Path, base_url: str) -> LocalAIClient:
    """Build a client that doesn't really wait between checks.

    Returns:
        The client.

    """
    return LocalAIClient(install_root=root, base_url=base_url, sleep=lambda _seconds: None)


def test_a_chat_request_reads_as_every_caller_expects(service, tmp_path):
    """The answer has the shape callers read, and the service gets the request and token."""
    fake, base_url = service
    install(root=tmp_path)

    client = client_for(root=tmp_path, base_url=base_url)
    response = client.chat.completions.create(model='reasoning', messages=MESSAGES, max_tokens=64)

    assert response.choices[0].message.content == '42'
    assert fake.requests == [{'model': 'reasoning', 'messages': MESSAGES, 'max_tokens': 64}]
    assert fake.authorizations == [f'Bearer {SERVICE_KEY}']


def test_no_output_limit_leaves_the_services_own(service, tmp_path):
    """Without max_tokens, none is sent, so the service's own limit applies."""
    fake, base_url = service
    install(root=tmp_path)

    client_for(root=tmp_path, base_url=base_url).create(model='reasoning', messages=MESSAGES)

    assert 'max_tokens' not in fake.requests[0]


def test_a_running_service_is_left_alone(service, tmp_path):
    """A service already answering is not started again."""
    _fake, base_url = service
    calls = install(root=tmp_path)

    client_for(root=tmp_path, base_url=base_url).create(model='reasoning', messages=MESSAGES)

    assert not calls.exists()


def test_a_stopped_service_is_started_and_waited_for(service, tmp_path):
    """The control script starts it, and the request waits until the models answer."""
    fake, base_url = service
    calls = install(root=tmp_path)
    fake.not_ready_for = 3

    response = client_for(root=tmp_path, base_url=base_url).create(
        model='reasoning', messages=MESSAGES
    )

    assert calls.read_text(encoding='utf-8').strip() == 'start'
    assert response.choices[0].message.content == '42'


def test_a_service_nothing_answers_for_is_started(tmp_path):
    """Nothing listening means start it, and a failed start is reported."""
    calls = install(root=tmp_path, exit_code=1)

    with pytest.raises(LocalAIServiceError, match='would not start'):
        # Port 9 refuses: nothing listens there
        client_for(root=tmp_path, base_url='http://127.0.0.1:9').create(
            model='reasoning', messages=MESSAGES
        )

    assert calls.read_text(encoding='utf-8').strip() == 'start'


def test_too_little_memory_says_so_and_can_be_retried(service, tmp_path):
    """The script's memory exit becomes a clear error with a retryable status."""
    fake, base_url = service
    install(root=tmp_path, exit_code=EXIT_NOT_ENOUGH_MEMORY)
    fake.ready_status = HTTPStatus.SERVICE_UNAVAILABLE

    with pytest.raises(LocalAIServiceError, match='not enough free memory') as error:
        client_for(root=tmp_path, base_url=base_url).create(model='reasoning', messages=MESSAGES)

    assert error.value.status_code == HTTPStatus.SERVICE_UNAVAILABLE


def test_a_service_that_never_gets_ready_stops_waiting(service, tmp_path, mocker):
    """Waiting for the models is bounded."""
    fake, base_url = service
    install(root=tmp_path)
    fake.ready_status = HTTPStatus.SERVICE_UNAVAILABLE
    readings = iter([0.0, 1.0, local_service.READY_TIMEOUT_SECONDS + 1.0])
    mocker.patch('glitchygames.clock.raw_counter_seconds', side_effect=lambda: next(readings))

    with pytest.raises(LocalAIServiceError, match='was not ready'):
        client_for(root=tmp_path, base_url=base_url).create(model='reasoning', messages=MESSAGES)


def test_waiting_uses_the_engines_sleep_by_default(service, tmp_path, mocker):
    """Without an injected sleep, waiting goes through the engine's clock."""
    fake, base_url = service
    install(root=tmp_path)
    fake.not_ready_for = 2
    sleep = mocker.patch('glitchygames.clock.raw_sleep')

    LocalAIClient(install_root=tmp_path, base_url=base_url).create(
        model='reasoning', messages=MESSAGES
    )

    sleep.assert_called_with(local_service.READY_POLL_SECONDS)


def test_a_refusal_carries_its_status_for_the_callers_retries(service, tmp_path):
    """The service's status reaches the error, as Bitmappy's retries read it."""
    fake, base_url = service
    install(root=tmp_path)
    fake.chat_status = HTTPStatus.UNPROCESSABLE_ENTITY
    fake.chat_body = {'error': {'code': 'x', 'message': 'no'}}

    with pytest.raises(LocalAIServiceError, match='answered 422') as error:
        client_for(root=tmp_path, base_url=base_url).create(model='reasoning', messages=MESSAGES)

    assert error.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_a_dropped_connection_is_reported(service, tmp_path, mocker):
    """A transport failure becomes the client error, with no status."""
    _fake, base_url = service
    install(root=tmp_path)
    failure = local_service.httpx2.ReadError('the connection dropped')
    mocker.patch.object(local_service.httpx2, 'post', side_effect=failure)

    with pytest.raises(LocalAIServiceError, match='ReadError') as error:
        client_for(root=tmp_path, base_url=base_url).create(model='reasoning', messages=MESSAGES)

    assert error.value.status_code is None


def test_an_uninstalled_service_is_refused_at_once_and_not_retried(tmp_path):
    """Without the service there is nothing to retry, so the error is a ValueError."""
    with pytest.raises(LocalAIServiceNotInstalledError, match='not installed') as error:
        client_for(root=tmp_path, base_url='http://127.0.0.1:9')

    # Bitmappy's retries give up at once on a ValueError
    assert isinstance(error.value, ValueError)


def test_a_missing_key_is_reported_as_not_installed(service, tmp_path):
    """A damaged install is reported, not sent unauthenticated."""
    _fake, base_url = service
    install(root=tmp_path)
    (tmp_path / 'config' / 'service-api-key').unlink()

    with pytest.raises(LocalAIServiceNotInstalledError, match='no key'):
        client_for(root=tmp_path, base_url=base_url).create(model='reasoning', messages=MESSAGES)


def test_the_factory_makes_a_local_client_with_the_timeout(tmp_path, monkeypatch):
    """Only the local service answers for now, with the timeout asked for."""
    install(root=tmp_path)
    monkeypatch.setattr(
        LocalAIClient.__init__,
        '__kwdefaults__',
        {
            **LocalAIClient.__init__.__kwdefaults__,
            'install_root': tmp_path,
        },
    )

    client = create_chat_client(timeout_seconds=12.0)

    assert isinstance(client, LocalAIClient)
    assert client.timeout_seconds == 12.0
