"""The WebSocket a game connects to, and what happens when the last one leaves."""

import asyncio
import json
import time

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from glitchygames_ai_service.app import (
    CLOSE_BAD_HELLO,
    CLOSE_PROTOCOL_MISMATCH,
    PROTOCOL_VERSION,
    create_app,
)
from glitchygames_ai_service.sessions import SessionTracker
from tests.conftest import AUTHORIZED

HELLO = {'type': 'hello', 'protocol_version': PROTOCOL_VERSION}


def wait_for_file(*, path, seconds=5.0):
    deadline = time.monotonic() + seconds
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    return path.exists()


def test_a_session_is_welcomed_with_the_models(client, worker):
    with client.websocket_connect('/v1/session', headers=AUTHORIZED) as session:
        session.send_json(HELLO)
        welcome = session.receive_json()

    assert welcome['type'] == 'welcome'
    assert welcome['protocol_version'] == PROTOCOL_VERSION
    assert {model['id'] for model in welcome['models']} >= {'bonsai-2-27b'}


def test_a_session_answers_a_ping(client, worker):
    with client.websocket_connect('/v1/session', headers=AUTHORIZED) as session:
        session.send_json(HELLO)
        session.receive_json()
        session.send_json({'type': 'ping', 'sequence': 7})

        assert session.receive_json() == {'type': 'pong', 'sequence': 7}


@pytest.mark.parametrize(
    ('text', 'code'),
    [
        ('not json', 'invalid_json'),
        ('[1]', 'unknown_message'),
        ('{"type": "x"}', 'unknown_message'),
    ],
)
def test_a_bad_message_is_answered_and_the_session_goes_on(client, worker, text, code):
    with client.websocket_connect('/v1/session', headers=AUTHORIZED) as session:
        session.send_json(HELLO)
        session.receive_json()
        session.send_text(text)

        assert session.receive_json() == {'type': 'error', 'code': code}
        session.send_json({'type': 'ping', 'sequence': 1})
        assert session.receive_json()['type'] == 'pong'


def test_an_oversized_message_is_refused(settings, worker):
    small = settings.model_copy(update={'maximum_message_bytes': 64})
    with (
        TestClient(create_app(settings=small)) as client,
        client.websocket_connect('/v1/session', headers=AUTHORIZED) as session,
    ):
        session.send_json(HELLO)
        session.receive_json()
        session.send_text('x' * 65)

        assert session.receive_json() == {'type': 'error', 'code': 'message_too_large'}


def test_a_missing_token_is_refused(client):
    with pytest.raises(WebSocketDisconnect), client.websocket_connect('/v1/session') as session:
        session.receive_json()


def test_a_wrong_token_is_refused(client):
    headers = {'Authorization': 'Bearer wrong'}
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect('/v1/session', headers=headers) as session,
    ):
        session.receive_json()


def test_a_website_is_refused_even_with_the_token(client):
    headers = {**AUTHORIZED, 'Origin': 'https://example.com'}
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect('/v1/session', headers=headers) as session,
    ):
        session.receive_json()


def test_an_allowed_origin_is_let_in(client, worker):
    headers = {**AUTHORIZED, 'Origin': 'http://127.0.0.1:23231'}
    with client.websocket_connect('/v1/session', headers=headers) as session:
        session.send_json(HELLO)

        assert session.receive_json()['type'] == 'welcome'


def test_another_protocol_version_is_refused_clearly(client):
    with client.websocket_connect('/v1/session', headers=AUTHORIZED) as session:
        session.send_json({'type': 'hello', 'protocol_version': PROTOCOL_VERSION + 1})

        assert session.receive_json() == {
            'type': 'refused',
            'reason': 'protocol_version',
            'protocol_version': PROTOCOL_VERSION,
        }
        with pytest.raises(WebSocketDisconnect) as closed:
            session.receive_json()
    assert closed.value.code == CLOSE_PROTOCOL_MISMATCH
    assert client.app.state.sessions.count == 0


@pytest.mark.parametrize('first', ['not json', '[1]', json.dumps({'type': 'ping'})])
def test_anything_but_a_hello_first_is_refused(client, first):
    with client.websocket_connect('/v1/session', headers=AUTHORIZED) as session:
        session.send_text(first)
        with pytest.raises(WebSocketDisconnect) as closed:
            session.receive_json()

    assert closed.value.code == CLOSE_BAD_HELLO
    assert client.app.state.sessions.count == 0


def test_leaving_before_a_hello_counts_nothing(client):
    with client.websocket_connect('/v1/session', headers=AUTHORIZED):
        pass

    assert client.app.state.sessions.count == 0


def test_sessions_are_counted(client, worker):
    with client.websocket_connect('/v1/session', headers=AUTHORIZED) as session:
        session.send_json(HELLO)
        session.receive_json()

        assert client.get('/v1/status', headers=AUTHORIZED).json()['sessions'] == 1


def test_the_last_session_closing_stops_the_models(client, worker, control_log):
    with client.websocket_connect('/v1/session', headers=AUTHORIZED) as session:
        session.send_json(HELLO)
        session.receive_json()

    assert wait_for_file(path=control_log)
    assert control_log.read_text(encoding='utf-8').strip() == 'stop'


def test_one_game_leaving_keeps_the_models_for_another(client, worker, control_log):
    with client.websocket_connect('/v1/session', headers=AUTHORIZED) as staying:
        staying.send_json(HELLO)
        staying.receive_json()
        with client.websocket_connect('/v1/session', headers=AUTHORIZED) as leaving:
            leaving.send_json(HELLO)
            leaving.receive_json()
        time.sleep(0.2)

        assert not control_log.exists()
        assert client.get('/v1/status', headers=AUTHORIZED).json()['sessions'] == 1


def test_a_game_returning_in_the_grace_period_keeps_the_models(settings, worker, control_log):
    patient = settings.model_copy(update={'shutdown_grace_seconds': 0.5})
    with TestClient(create_app(settings=patient)) as client:
        with client.websocket_connect('/v1/session', headers=AUTHORIZED) as first:
            first.send_json(HELLO)
            first.receive_json()
        with client.websocket_connect('/v1/session', headers=AUTHORIZED) as second:
            second.send_json(HELLO)
            second.receive_json()
            time.sleep(0.8)

            assert not control_log.exists()


def test_the_tracker_runs_the_shutdown_once_after_the_grace_period():
    calls = []

    async def shut_down():
        calls.append('stop')

    async def scenario():
        tracker = SessionTracker(grace_seconds=0.01, on_last_session_gone=shut_down)
        tracker.opened()
        tracker.opened()
        tracker.closed()
        await asyncio.sleep(0.03)
        assert calls == []
        tracker.closed()
        await asyncio.sleep(0.03)

    asyncio.run(scenario())

    assert calls == ['stop']
