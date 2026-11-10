"""Check llama-server models by asking questions with known answers, and report what they cost.

Standard library only: this runs under whatever Python runs Ansible. With a plain model entry it
talks to the agent already on that port. With `server` in the config it starts its own llama-server
on that port for each model, one at a time, and stops it afterwards, which is how every size gets
checked without changing which agent is selected.

Exits 1 if any check fails. Prints one JSON object per model.
"""

import argparse
import base64
import json
import math
import re
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zlib
from itertools import starmap
from pathlib import Path

REQUEST_TIMEOUT_SECONDS = 900
SERVER_LOAD_TIMEOUT_SECONDS = 600
SERVER_STOP_TIMEOUT_SECONDS = 30
TEST_IMAGE_SIZE = 256
TEST_IMAGE_COLOR = (0, 0, 255)
OUTPUT_LIMIT = 16384
NORM_TOLERANCE = 0.01
LOG_LINES_OF_INTEREST = re.compile(
    r'offloaded \d+/\d+ layers|graph splits|buffer size|recommendedMaxWorkingSetSize|using device',
)


def solid_color_png_base64(*, size: int, color: tuple[int, int, int]) -> str:
    """Return a one-color PNG, base64 encoded.

    Returns:
        The encoded image.
    """

    def chunk(*, kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack('>I', len(data))
            + kind
            + data
            + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    row = b'\x00' + bytes(color) * size
    png = (
        b'\x89PNG\r\n\x1a\n'
        + chunk(kind=b'IHDR', data=struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
        + chunk(kind=b'IDAT', data=zlib.compress(row * size))
        + chunk(kind=b'IEND', data=b'')
    )
    return base64.b64encode(png).decode('ascii')


def post(*, url: str, api_key: str, body: dict[str, object]) -> dict[str, object]:
    """POST JSON and return the JSON answer.

    Returns:
        The decoded response.
    """
    request = urllib.request.Request(  # ruff: ignore[suspicious-url-open-usage] - always http://127.0.0.1
        url,
        data=json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:  # ruff: ignore[suspicious-url-open-usage]
        return json.load(response)


def ask(*, base_url: str, api_key: str, content: object) -> dict[str, object]:
    """Ask a chat question and report the answer and its speed.

    Returns:
        The answer, finish reason, seconds taken and llama-server's timings.
    """
    started = time.monotonic()
    response = post(
        url=f'{base_url}/v1/chat/completions',
        api_key=api_key,
        body={
            'messages': [{'role': 'user', 'content': content}],
            'max_tokens': OUTPUT_LIMIT,
            'chat_template_kwargs': {'reasoning_effort': 'medium'},
        },
    )
    choice = response['choices'][0]
    timings = response.get('timings', {})
    return {
        'answer': (choice['message'].get('content') or '').strip(),
        'finish_reason': choice.get('finish_reason'),
        'seconds': round(time.monotonic() - started, 1),
        'decode_tokens_per_second': round(timings.get('predicted_per_second', 0.0), 1),
        'prompt_tokens_per_second': round(timings.get('prompt_per_second', 0.0), 1),
        'tokens_generated': timings.get('predicted_n'),
    }


def check_reasoning(*, base_url: str, api_key: str) -> dict[str, object]:
    """Ask a text question and an image question with known answers.

    Returns:
        Each question's result, and whether it passed.
    """
    text = ask(
        base_url=base_url,
        api_key=api_key,
        content='What is 17 + 25? Reply with only the number.',
    )
    text['passed'] = re.search(r'\b42\b', text['answer']) is not None
    image_data = solid_color_png_base64(size=TEST_IMAGE_SIZE, color=TEST_IMAGE_COLOR)
    image = ask(
        base_url=base_url,
        api_key=api_key,
        content=[
            {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{image_data}'}},
            {'type': 'text', 'text': 'What color is this image? Reply with only one word.'},
        ],
    )
    image['passed'] = 'blue' in image['answer'].lower()
    return {'text': text, 'image': image, 'passed': text['passed'] and image['passed']}


def cosine(*, first: list[float], second: list[float]) -> float:
    """Return two vectors' cosine similarity.

    Returns:
        The similarity.
    """
    dot = sum(a * b for a, b in zip(first, second, strict=True))
    return dot / (math.hypot(*first) * math.hypot(*second))


def check_embedding(*, base_url: str, api_key: str, dimensions: int) -> dict[str, object]:
    """Check vectors' shape and that related words sit closer than unrelated ones.

    Returns:
        What was measured, and whether it passed.
    """
    response = post(
        url=f'{base_url}/v1/embeddings',
        api_key=api_key,
        body={'input': ['a small cat', 'a little kitten', 'a tax spreadsheet']},
    )
    vectors = [item['embedding'] for item in response['data']]
    norms = list(starmap(math.hypot, vectors))
    related = cosine(first=vectors[0], second=vectors[1])
    unrelated = cosine(first=vectors[0], second=vectors[2])
    return {
        'dimensions': len(vectors[0]),
        'norms': [round(norm, 4) for norm in norms],
        'related_similarity': round(related, 4),
        'unrelated_similarity': round(unrelated, 4),
        'passed': (
            all(len(vector) == dimensions for vector in vectors)
            and all(math.isfinite(value) for vector in vectors for value in vector)
            and all(abs(norm - 1.0) < NORM_TOLERANCE for norm in norms)
            and related > unrelated
        ),
    }


def memory_footprint_mib(*, process_id: int) -> float | None:
    """Read a process's physical footprint, which counts GPU memory where RSS can't.

    Returns:
        Its footprint in MiB, or None if macOS's footprint tool didn't report one.
    """
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        ['/usr/bin/footprint', '-p', str(process_id), '--format', 'bytes'],
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r'Footprint:\s*(\d+)\s*B', result.stdout)
    return round(int(match.group(1)) / (1024 * 1024), 1) if match else None


def wait_until_healthy(*, base_url: str, process: subprocess.Popen[bytes]) -> None:
    """Wait for a started server to finish loading.

    Raises:
        RuntimeError: If it exits or takes too long.
    """
    deadline = time.monotonic() + SERVER_LOAD_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            message = f'llama-server exited with {process.returncode} while loading'
            raise RuntimeError(message)
        try:
            with urllib.request.urlopen(f'{base_url}/health', timeout=5):  # ruff: ignore[suspicious-url-open-usage]
                return
        except urllib.error.URLError, TimeoutError:
            time.sleep(1)
    message = f'llama-server did not load in {SERVER_LOAD_TIMEOUT_SECONDS} s'
    raise RuntimeError(message)


def check_model(*, model: dict[str, object], api_key: str) -> dict[str, object]:
    """Run the checks for a model that's already being served.

    Returns:
        The result.
    """
    base_url = f'http://127.0.0.1:{model["port"]}'
    if model['role'] == 'reasoning':
        return check_reasoning(base_url=base_url, api_key=api_key)
    return check_embedding(base_url=base_url, api_key=api_key, dimensions=model['dimensions'])


def check_with_own_server(
    *, model: dict[str, object], server: list[str], api_key: str
) -> dict[str, object]:
    """Start a server for one model, check it, and stop it.

    Returns:
        The result, with what the server's log says about where the model ran.
    """
    base_url = f'http://127.0.0.1:{model["port"]}'
    with tempfile.TemporaryFile() as log:
        started = time.monotonic()
        process = subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true]
            [*server, *model['arguments']], stdout=log, stderr=subprocess.STDOUT
        )
        try:
            wait_until_healthy(base_url=base_url, process=process)
            load_seconds = round(time.monotonic() - started, 1)
            result = check_model(model=model, api_key=api_key)
            result['load_seconds'] = load_seconds
            result['footprint_mib'] = memory_footprint_mib(process_id=process.pid)
        finally:
            process.terminate()
            try:
                process.wait(timeout=SERVER_STOP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        log.seek(0)
        lines = log.read().decode(errors='replace').splitlines()
    result['log'] = sorted({line.strip() for line in lines if LOG_LINES_OF_INTEREST.search(line)})
    return result


def main() -> int:
    """Run every model's checks.

    Returns:
        0 if they all passed, else 1.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    arguments = parser.parse_args()
    config = json.loads(arguments.config.read_text(encoding='utf-8'))
    api_key = Path(config['api_key_file']).read_text(encoding='utf-8').strip()
    all_passed = True
    for model in config['models']:
        try:
            if 'server' in config:
                result = check_with_own_server(
                    model=model, server=config['server'], api_key=api_key
                )
            else:
                result = check_model(model=model, api_key=api_key)
        except (OSError, RuntimeError, KeyError, ValueError) as error:
            result = {'passed': False, 'error': f'{type(error).__name__}: {error}'}
        all_passed = all_passed and result['passed']
        sys.stdout.write(json.dumps({'model': model['alias'], **result}) + '\n')
        sys.stdout.flush()
    return 0 if all_passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
