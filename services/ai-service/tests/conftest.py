"""A real local fake model server, and the service configured to use it."""

import json
import socket
import stat
import threading
import time
from typing import TYPE_CHECKING

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.testclient import TestClient

from glitchygames_ai_service.app import create_app
from glitchygames_ai_service.settings import ModelEntry, ModelRole, Settings

if TYPE_CHECKING:
    from pathlib import Path

SERVICE_KEY = 'service-token'
WORKER_KEY = 'worker-token'
AUTHORIZED = {'Authorization': f'Bearer {SERVICE_KEY}'}
DIMENSIONS = 8


class FakeWorker:
    """What the fake model server was asked, and how it should behave."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.authorization: list[str | None] = []
        self.health_status = 200
        self.stream_closed = threading.Event()


def fake_worker_app(*, worker: FakeWorker) -> FastAPI:
    application = FastAPI()

    @application.get('/health')
    async def health() -> JSONResponse:
        return JSONResponse({'status': 'ok'}, status_code=worker.health_status)

    @application.post('/v1/chat/completions')
    async def chat(request: Request) -> object:
        body = await request.json()
        worker.requests.append(body)
        worker.authorization.append(request.headers.get('authorization'))
        if not body.get('stream'):
            return {'choices': [{'message': {'content': '42'}}], 'model': body['model']}

        async def events():
            try:
                yield b'data: {"delta": "4"}\n\n'
                yield b'data: {"delta": "2"}\n\n'
                yield b'data: [DONE]\n\n'
            finally:
                worker.stream_closed.set()

        return StreamingResponse(events(), media_type='text/event-stream')

    @application.post('/v1/embeddings')
    async def embeddings(request: Request) -> dict:
        body = await request.json()
        worker.requests.append(body)
        return {'data': [{'embedding': [0.0] * DIMENSIONS}], 'model': body['model']}

    return application


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


@pytest.fixture(scope='session')
def running_worker():
    worker = FakeWorker()
    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            fake_worker_app(worker=worker), host='127.0.0.1', port=port, log_level='error'
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    yield worker, port
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def worker(running_worker):
    fake, _port = running_worker
    fake.requests.clear()
    fake.authorization.clear()
    fake.health_status = 200
    fake.stream_closed.clear()
    return fake


@pytest.fixture
def control_log(tmp_path) -> Path:
    return tmp_path / 'control.log'


@pytest.fixture
def settings(tmp_path, running_worker, control_log) -> Settings:
    _fake, port = running_worker
    (tmp_path / 'service-key').write_text(f'{SERVICE_KEY}\n', encoding='utf-8')
    (tmp_path / 'worker-key').write_text(f'{WORKER_KEY}\n', encoding='utf-8')
    (tmp_path / 'scalar.js').write_text('window.scalar = true;', encoding='utf-8')
    control = tmp_path / 'ai-service.sh'
    control.write_text(
        f'#!/bin/sh\necho "$1" >> {json.dumps(str(control_log))}\n', encoding='utf-8'
    )
    control.chmod(control.stat().st_mode | stat.S_IEXEC)
    return Settings(
        port=free_port(),
        models=(
            ModelEntry(alias='bonsai-2-27b', role=ModelRole.REASONING, port=port),
            # Nothing listens here: an installed size that isn't running
            ModelEntry(alias='bonsai-2-2b', role=ModelRole.REASONING, port=free_port()),
            ModelEntry(
                alias='qwen3-embedding-0.6b',
                role=ModelRole.EMBEDDING,
                port=port,
                dimensions=DIMENSIONS,
            ),
        ),
        service_key_file=tmp_path / 'service-key',
        worker_key_file=tmp_path / 'worker-key',
        control_script=control,
        scalar_file=tmp_path / 'scalar.js',
        allowed_origins=('http://127.0.0.1:23231',),
        shutdown_grace_seconds=0.05,
        maximum_concurrent_requests=2,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client
