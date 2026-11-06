"""The REST API, against a real local fake model server."""

import json

import httpx2
import pytest
from starlette.testclient import TestClient

from glitchygames_ai_service.__main__ import main
from glitchygames_ai_service.app import create_app
from glitchygames_ai_service.settings import (
    CONFIG_ENVIRONMENT_VARIABLE,
    ModelEntry,
    ModelRole,
    load_settings,
)
from tests.conftest import AUTHORIZED, DIMENSIONS, WORKER_KEY, free_port

PROTECTED = [
    ('GET', '/v1/models'),
    ('GET', '/v1/status'),
    ('POST', '/v1/embeddings'),
    ('POST', '/v1/chat/completions'),
]


def chat(client, **fields):
    body = {'messages': [{'role': 'user', 'content': 'hi'}], **fields}
    return client.post('/v1/chat/completions', headers=AUTHORIZED, json=body)


@pytest.mark.parametrize(('method', 'path'), PROTECTED)
def test_every_protected_route_refuses_a_missing_token(client, method, path):
    response = client.request(method, path, json={})

    assert response.status_code == 401
    assert response.json()['error']['code'] == 'unauthorized'


@pytest.mark.parametrize(('method', 'path'), PROTECTED)
def test_every_protected_route_refuses_a_wrong_token(client, method, path):
    response = client.request(method, path, json={}, headers={'Authorization': 'Bearer wrong'})

    assert response.status_code == 401


def test_health_live_needs_no_token_or_model(client):
    assert client.get('/health/live').json() == {'status': 'live'}


def test_ready_when_a_reasoning_and_an_embedding_model_answer(client, worker):
    response = client.get('/health/ready')

    assert response.status_code == 200
    assert response.json()['ready'] is True


def test_not_ready_while_models_load(client, worker):
    worker.health_status = 503

    response = client.get('/health/ready')

    assert response.status_code == 503
    assert response.json()['ready'] is False
    assert {model['state'] for model in response.json()['models']} == {'loading', 'stopped'}


def test_a_stopped_model_is_never_reported_as_ready(client, worker):
    models = {
        model['id']: model for model in client.get('/v1/models', headers=AUTHORIZED).json()['data']
    }

    assert models['bonsai-2-27b']['state'] == 'ready'
    assert models['bonsai-2-2b']['state'] == 'stopped'
    assert models['qwen3-embedding-0.6b']['dimensions'] == DIMENSIONS


def test_an_unexpected_health_status_counts_as_stopped(client, worker):
    worker.health_status = 500

    models = client.get('/v1/models', headers=AUTHORIZED).json()['data']

    assert {model['state'] for model in models} == {'stopped'}


def test_status_reports_sessions_and_models(client, worker):
    body = client.get('/v1/status', headers=AUTHORIZED).json()

    assert body['sessions'] == 0
    assert body['protocol_version'] == 1
    assert len(body['models']) == 3


def test_chat_goes_to_the_running_size_with_the_worker_token(client, worker):
    response = chat(client, model='reasoning')

    assert response.status_code == 200
    assert response.json()['choices'][0]['message']['content'] == '42'
    assert worker.requests[-1]['model'] == 'bonsai-2-27b'
    assert worker.authorization[-1] == f'Bearer {WORKER_KEY}'


def test_the_client_token_never_reaches_a_model_server(client, worker):
    chat(client)

    assert AUTHORIZED['Authorization'] not in worker.authorization


def test_vision_means_the_reasoning_model(client, worker):
    assert chat(client, model='vision').status_code == 200
    assert worker.requests[-1]['model'] == 'bonsai-2-27b'


def test_a_size_that_is_not_running_is_refused_not_replaced(client, worker):
    response = chat(client, model='bonsai-2-2b')

    assert response.status_code == 503
    assert response.json()['error']['code'] == 'model_unavailable'
    assert worker.requests == []


def test_an_unknown_model_is_refused(client, worker):
    response = chat(client, model='gpt-5')

    assert response.status_code == 503
    assert worker.requests == []


def test_an_embedding_model_cannot_answer_chat(client, worker):
    assert chat(client, model='qwen3-embedding-0.6b').status_code == 503


def test_system_messages_merge_into_one_leading_message(client, worker):
    response = client.post(
        '/v1/chat/completions',
        headers=AUTHORIZED,
        json={
            'messages': [
                {'role': 'user', 'content': 'hi'},
                {'role': 'system', 'content': 'one'},
                {'role': 'system', 'content': 'two'},
            ]
        },
    )

    assert response.status_code == 200
    messages = worker.requests[-1]['messages']
    assert messages[0] == {'role': 'system', 'content': 'one\n\ntwo'}
    assert [message['role'] for message in messages] == ['system', 'user']


def test_image_parts_pass_through(client, worker):
    parts = [{'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AA=='}}]

    client.post(
        '/v1/chat/completions',
        headers=AUTHORIZED,
        json={'messages': [{'role': 'user', 'content': parts}]},
    )

    assert worker.requests[-1]['messages'][0]['content'] == parts


def test_reasoning_effort_reaches_the_template(client, worker):
    chat(client, reasoning_effort='medium')

    assert worker.requests[-1]['chat_template_kwargs'] == {'reasoning_effort': 'medium'}


def test_the_effort_the_template_rejects_is_refused_here(client, worker):
    assert chat(client, reasoning_effort='high').status_code == 422
    assert worker.requests == []


def test_optional_settings_pass_through_only_when_given(client, worker):
    chat(client, temperature=0.5, response_format={'type': 'json_object'})

    assert worker.requests[-1]['temperature'] == 0.5
    assert worker.requests[-1]['response_format'] == {'type': 'json_object'}
    assert 'top_p' not in worker.requests[-1]


@pytest.mark.parametrize(
    'fields', [{'frequency_penalty': 1.0}, {'tools': []}, {'max_tokens': 0}, {'messages': []}]
)
def test_unsupported_or_invalid_fields_are_refused(client, worker, fields):
    assert chat(client, **fields).status_code == 422
    assert worker.requests == []


def test_streaming_passes_events_through_and_frees_its_slot(client, worker):
    with client.stream(
        'POST',
        '/v1/chat/completions',
        headers=AUTHORIZED,
        json={'stream': True, 'messages': [{'role': 'user', 'content': 'hi'}]},
    ) as response:
        text = ''.join(response.iter_text())

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/event-stream')
    assert '[DONE]' in text
    assert client.app.state.slots.in_use == 0
    assert worker.stream_closed.wait(timeout=5)


def test_embeddings_go_to_the_embedding_model(client, worker):
    response = client.post('/v1/embeddings', headers=AUTHORIZED, json={'input': 'a small cat'})

    assert response.status_code == 200
    assert len(response.json()['data'][0]['embedding']) == DIMENSIONS
    assert worker.requests[-1]['model'] == 'qwen3-embedding-0.6b'


def test_the_models_own_dimensions_are_accepted(client, worker):
    response = client.post(
        '/v1/embeddings', headers=AUTHORIZED, json={'input': 'a', 'dimensions': DIMENSIONS}
    )

    assert response.status_code == 200


def test_other_dimensions_are_refused_until_validated(client, worker):
    response = client.post(
        '/v1/embeddings', headers=AUTHORIZED, json={'input': 'a', 'dimensions': 4}
    )

    assert response.status_code == 422
    assert response.json()['error']['code'] == 'unsupported_dimensions'
    assert worker.requests == []


def test_a_reasoning_model_cannot_embed(client, worker):
    response = client.post(
        '/v1/embeddings', headers=AUTHORIZED, json={'input': 'a', 'model': 'bonsai-2-27b'}
    )

    assert response.status_code == 503
    assert client.app.state.slots.in_use == 0


def test_full_slots_refuse_rather_than_queue(client, worker):
    client.app.state.slots.in_use = client.app.state.slots.limit

    response = chat(client)

    assert response.status_code == 503
    assert response.json()['error']['code'] == 'too_many_requests'
    assert worker.requests == []
    client.app.state.slots.in_use = 0


def test_a_refused_chat_gives_its_slot_back(client, worker):
    chat(client, model='bonsai-2-2b')

    assert client.app.state.slots.in_use == 0


@pytest.fixture
def client_of_a_failing_worker(settings, mocker, worker):
    with TestClient(create_app(settings=settings)) as test_client:
        workers = test_client.app.state.workers
        real_send = workers.client.send

        async def fail_after_the_health_check(request, **options):
            if request.url.path == '/health':
                return await real_send(request, **options)
            message = 'the worker went away'
            raise httpx2.ConnectError(message)

        mocker.patch.object(workers.client, 'send', side_effect=fail_after_the_health_check)
        yield test_client


@pytest.mark.parametrize('stream', [False, True])
def test_a_model_server_failing_mid_request_is_reported_cleanly(client_of_a_failing_worker, stream):
    response = chat(client_of_a_failing_worker, stream=stream)

    assert response.status_code == 503
    assert response.json()['error']['code'] == 'model_failed'
    assert client_of_a_failing_worker.app.state.slots.in_use == 0


def test_an_embedding_failure_is_reported_cleanly(client_of_a_failing_worker):
    response = client_of_a_failing_worker.post(
        '/v1/embeddings', headers=AUTHORIZED, json={'input': 'a'}
    )

    assert response.status_code == 503
    assert response.json()['error']['code'] == 'model_failed'
    assert client_of_a_failing_worker.app.state.slots.in_use == 0


def test_the_docs_use_only_local_files(client):
    page = client.get('/docs')

    assert page.status_code == 200
    assert 'src="/docs/scalar.js"' in page.text
    assert '"withDefaultFonts": false' in page.text
    assert 'https://' not in page.text
    assert 'cdn.' not in page.text


def test_the_docs_script_is_the_local_file(client):
    response = client.get('/docs/scalar.js')

    assert response.text == 'window.scalar = true;'
    assert 'javascript' in response.headers['content-type']


def test_the_contract_documents_every_route_with_a_stable_id(client):
    paths = client.get('/openapi.json').json()['paths']
    operation_ids = {
        operation['operationId'] for path in paths.values() for operation in path.values()
    }

    assert operation_ids == {
        'createChatCompletion',
        'createEmbeddings',
        'getStatus',
        'healthLive',
        'healthReady',
        'listModels',
    }


def test_the_contract_documents_the_errors(client):
    paths = client.get('/openapi.json').json()['paths']

    assert set(paths['/v1/models']['get']['responses']) >= {'200', '401', '503'}
    assert '503' in paths['/health/ready']['get']['responses']


def test_settings_load_from_the_file_the_environment_names(tmp_path, settings, monkeypatch):
    path = tmp_path / 'service.json'
    path.write_text(settings.model_dump_json(), encoding='utf-8')
    monkeypatch.setenv(CONFIG_ENVIRONMENT_VARIABLE, str(path))

    assert load_settings() == settings


def test_settings_refuse_an_unknown_key(tmp_path, settings, monkeypatch):
    path = tmp_path / 'service.json'
    path.write_text(
        json.dumps({**json.loads(settings.model_dump_json()), 'surprise': 1}), encoding='utf-8'
    )
    monkeypatch.setenv(CONFIG_ENVIRONMENT_VARIABLE, str(path))

    with pytest.raises(ValueError, match='surprise'):
        load_settings()


def test_the_service_listens_on_loopback_by_default(settings):
    assert settings.host == '127.0.0.1'
    entry = ModelEntry(alias='x', role=ModelRole.REASONING, port=free_port())
    assert entry.dimensions is None


def test_main_serves_what_the_settings_say(tmp_path, settings, monkeypatch, mocker):
    path = tmp_path / 'service.json'
    path.write_text(settings.model_dump_json(), encoding='utf-8')
    monkeypatch.setenv(CONFIG_ENVIRONMENT_VARIABLE, str(path))
    run = mocker.patch('uvicorn.run')

    main()

    assert run.call_args.kwargs['host'] == '127.0.0.1'
    assert run.call_args.kwargs['port'] == settings.port
    assert run.call_args.kwargs['ws_max_size'] == settings.maximum_message_bytes
