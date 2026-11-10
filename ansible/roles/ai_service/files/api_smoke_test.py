"""Use the running API as a game would: REST with known answers, then a WebSocket session.

Exits 1 if anything is wrong, naming it. Runs under the sidecar's own Python.
"""

import argparse
import asyncio
import json
import re
import time
from pathlib import Path

import httpx2
import websockets

LOAD_TIMEOUT_SECONDS = 120.0
REQUEST_TIMEOUT_SECONDS = 900.0


def wait_until_ready(*, base_url: str) -> None:
    """Wait for the API and both models to answer.

    Raises:
        RuntimeError: If they don't in time.

    """
    deadline = time.monotonic() + LOAD_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            if httpx2.get(f'{base_url}/health/ready', timeout=5.0).status_code == httpx2.codes.OK:
                return
        except httpx2.TransportError:
            pass
        time.sleep(0.5)
    message = f'The API was not ready in {LOAD_TIMEOUT_SECONDS} s'
    raise RuntimeError(message)


def check_rest(*, base_url: str, headers: dict[str, str]) -> list[str]:
    """Exercise the REST API.

    Returns:
        What failed, if anything.

    """
    problems = []
    client = httpx2.Client(base_url=base_url, timeout=REQUEST_TIMEOUT_SECONDS)
    if client.get('/v1/models').status_code != httpx2.codes.UNAUTHORIZED:
        problems.append('/v1/models answered without a token')
    models = client.get('/v1/models', headers=headers).json()['data']
    print('models:', {model['id']: model['state'] for model in models})

    answer = client.post(
        '/v1/chat/completions',
        headers=headers,
        json={
            'model': 'reasoning',
            'messages': [{'role': 'user', 'content': 'What is 17 + 25? Reply with only the number.'}],
            'reasoning_effort': 'medium',
        },
    ).json()['choices'][0]['message']['content']
    print('chat:', answer.strip())
    if not re.search(r'\b42\b', answer):
        problems.append(f'chat answered {answer!r}')

    streamed = ''
    with client.stream(
        'POST',
        '/v1/chat/completions',
        headers=headers,
        json={
            'stream': True,
            'messages': [{'role': 'user', 'content': 'What is 17 + 25? Reply with only the number.'}],
        },
    ) as response:
        for line in response.iter_lines():
            if line.startswith('data: {'):
                delta = json.loads(line[6:])['choices'][0]['delta']
                streamed += delta.get('content') or ''
    print('stream:', streamed.strip())
    if not re.search(r'\b42\b', streamed):
        problems.append(f'streaming answered {streamed!r}')

    vector = client.post(
        '/v1/embeddings', headers=headers, json={'model': 'embedding', 'input': 'a small cat'}
    ).json()['data'][0]['embedding']
    print('embedding dimensions:', len(vector))
    if not vector:
        problems.append('the embedding was empty')

    if 'scalar.js' not in client.get('/docs').text:
        problems.append('/docs names no local script')
    if len(client.get('/docs/scalar.js').content) == 0:
        problems.append('/docs/scalar.js is empty')
    if 'createChatCompletion' not in client.get('/openapi.json').text:
        problems.append('/openapi.json is missing an operation')
    return problems


async def check_session(*, url: str, headers: dict[str, str]) -> list[str]:
    """Open a session, as a game does, and refuse a website.

    Returns:
        What failed, if anything.

    """
    problems = []
    async with websockets.connect(url, additional_headers=headers) as session:
        await session.send(json.dumps({'type': 'hello', 'protocol_version': 1}))
        welcome = json.loads(await session.recv())
        print('session:', welcome['type'], 'protocol', welcome['protocol_version'])
        if welcome['type'] != 'welcome':
            problems.append(f'hello answered {welcome}')
        await session.send(json.dumps({'type': 'ping', 'sequence': 1}))
        if json.loads(await session.recv()) != {'type': 'pong', 'sequence': 1}:
            problems.append('ping went unanswered')
    try:
        async with websockets.connect(
            url, additional_headers=headers, origin='https://example.com'
        ):
            problems.append('a website was let in')
    except websockets.InvalidStatus:
        print('session from a website: refused')
    return problems


def main() -> int:
    """Run every check.

    Returns:
        0 if they all passed, else 1.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--key-file', type=Path, required=True)
    arguments = parser.parse_args()
    base_url = f'http://127.0.0.1:{arguments.port}'
    key = arguments.key_file.read_text(encoding='utf-8').strip()
    headers = {'Authorization': f'Bearer {key}'}

    wait_until_ready(base_url=base_url)
    problems = check_rest(base_url=base_url, headers=headers)
    problems += asyncio.run(
        check_session(url=f'ws://127.0.0.1:{arguments.port}/v1/session', headers=headers)
    )
    for problem in problems:
        print('PROBLEM:', problem)
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
