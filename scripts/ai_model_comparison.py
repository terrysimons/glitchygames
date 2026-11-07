"""Ask every Bonsai size the same questions about saved game states, and compare the answers.

Stage 5, Part 2 (plans/lucid-circuit-5-load-harness.md). For each size and context it starts its
own llama-server through the installed ``run-llama-server.sh``, on a spare port, and stops it
afterwards. Only a temporary copy of the settings changes, and only the port and context, so the
agent selection and the installed service are left alone. It refuses to run while the service is
running, as that would skew both speed and memory.

The questions are ``scripts/ai_comparison/questions.json``, about states saved from real games. Each
turn is sent as the console sends it: the same system prompt, the state in the same form, and
``reasoning_effort`` low.

Writes to ``--output``: ``results.jsonl`` (every answer, as it comes), ``summary.md`` (one row per
size and context), ``answers.html`` (the answers side by side) and each server's log. Speed and
memory are this Mac's: they say how the sizes compare here, not how fast a smaller Mac would be.

Usage:
    uv run python -m scripts.ai_model_comparison --output test-results/ai-comparison
    uv run python -m scripts.ai_model_comparison --output out --configurations 4b:32768 --repeats 1
"""

from __future__ import annotations

import argparse
import contextlib
import html
import json
import os
import re
import shutil
import statistics
import sys
import tempfile
from collections.abc import Callable, Generator, Sequence
from pathlib import Path
from typing import Any, cast

import httpx2
from pydantic import BaseModel, ConfigDict

from glitchygames import clock
from glitchygames.ai.local_service import pieces_of_stream_line
from glitchygames.ai_console import REASONING_EFFORT, SYSTEM_PROMPT
from glitchygames.ai_link import install_root
from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command, start_command, stop_command

DATA_DIRECTORY = Path(__file__).with_name('ai_comparison')
# The service holds 23231-23238
COMPARISON_PORT = 23239
FULL_CONTEXT = 262144
SMALLER_CONTEXT = 32768
# Every size at its full context, and the smaller sizes again with a smaller one, as much of what
# they reserve is probably context
DEFAULT_CONFIGURATIONS = (
    f'2b:{FULL_CONTEXT}',
    f'4b:{FULL_CONTEXT}',
    f'9b:{FULL_CONTEXT}',
    f'27b:{FULL_CONTEXT}',
    f'2b:{SMALLER_CONTEXT}',
    f'4b:{SMALLER_CONTEXT}',
    f'9b:{SMALLER_CONTEXT}',
)
DEFAULT_REPEATS = 3
FACT_KINDS = ('fact', 'absent', 'deduction', 'follow_up')
STRUCTURED_KIND = 'structured'
# Questions needing counting across sprites, arithmetic or exact longer JSON, reported on their own
# too: the plain ones are easy enough that every size may nearly tie on them
HARD_PREFIX = 'hard-'
SERVER_LOAD_TIMEOUT_SECONDS = 600.0
HEALTH_TIMEOUT_SECONDS = 5.0
REQUEST_TIMEOUT_SECONDS = 300.0
# A runaway answer must not stall the comparison, and an answer this slow has failed anyway. There's
# no token limit: the service and console have none, and one would end hard questions mid-reasoning
ANSWER_TIME_LIMIT_SECONDS = 180.0
FOOTPRINT_TIMEOUT_SECONDS = 60.0
STATUS_TIMEOUT_SECONDS = 30.0
MEBIBYTE = 1024 * 1024
HTTP_OK = 200
NOT_KNOWN = re.compile(
    r"\b(do not|don't|does not|doesn't|cannot|can't|could not|couldn't) "
    r'(know|say|show|state|include|list|contain|mention|provide|tell|determine|see)\b'
    r'|\bunknown\b|\bnot (available|stated|shown|given|listed|provided|specified|included|known)\b'
    r"|\bisn't (stated|shown|given|listed|provided|included)\b",
    re.IGNORECASE,
)


class Question(BaseModel):
    """One question, and how to tell whether its answer is right."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str
    state: str
    kind: str
    # All but the last are asked first, so the last is a follow-up
    turns: tuple[str, ...]
    required: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    does_not_know: bool = False
    expected_json: dict[str, Any] | None = None
    # A right answer: the tests hold each question's scoring to it
    example_answer: str


class Configuration(BaseModel):
    """One size at one context."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    size: str
    context: int

    @property
    def name(self) -> str:
        """Name it for reports and file names."""
        return f'{self.size}-{self.context}'


class Answer(BaseModel):
    """What the model said, and how long it took."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    text: str
    pieces: int
    seconds: float
    first_piece_seconds: float | None
    first_answer_seconds: float | None
    # Stopped at ANSWER_TIME_LIMIT_SECONDS rather than finishing
    stopped: bool


class QuestionResult(BaseModel):
    """One question asked once."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    configuration: str
    question: str
    kind: str
    repeat: int
    passed: bool
    why: str
    answer: Answer


class ServerFacts(BaseModel):
    """What one server cost to start and hold."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    configuration: str
    load_seconds: float
    footprint_mebibytes: float | None


class AskedOf(BaseModel):
    """Everything needed to ask a running server something."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    base_url: str
    api_key: str
    alias: str


def say(message: str) -> None:
    """Print a progress line at once: a whole run takes a while."""
    sys.stdout.write(message + '\n')
    sys.stdout.flush()


def parse_configuration(text: str) -> Configuration:
    """Read ``SIZE:CONTEXT``.

    Returns:
        The configuration.

    """
    size, _, context = text.partition(':')
    return Configuration(size=size, context=int(context))


def load_questions(*, data_directory: Path = DATA_DIRECTORY) -> list[Question]:
    """Read the questions.

    Returns:
        Them, in the file's order.

    """
    raw = json.loads((data_directory / 'questions.json').read_text(encoding='utf-8'))
    return [Question.model_validate(item) for item in raw]


def load_state(*, name: str, data_directory: Path = DATA_DIRECTORY) -> str:
    """Read a saved state as the console would send it.

    Returns:
        The state, as JSON text with no extra spacing, like ``json.dumps(describe_scene(...))``.

    """
    return json.dumps(json.loads((data_directory / f'{name}.json').read_text(encoding='utf-8')))


def score(*, question: Question, answer: str) -> tuple[bool, str]:
    """Judge an answer against what its question requires.

    Returns:
        Whether it's right, and if not, why.

    """
    text = answer.strip()
    if not text:
        return False, 'no answer'
    if question.expected_json is not None:
        return _score_json(expected=question.expected_json, text=text)
    if question.does_not_know and not NOT_KNOWN.search(text):
        return False, 'should have said it does not know'
    for pattern in question.required:
        if not re.search(pattern, text, re.IGNORECASE):
            return False, f'missing {pattern}'
    for pattern in question.forbidden:
        if re.search(pattern, text, re.IGNORECASE):
            return False, f'holds {pattern}'
    return True, ''


def _score_json(*, expected: dict[str, Any], text: str) -> tuple[bool, str]:
    """Judge a structured answer: only JSON, with the expected values.

    Returns:
        Whether it's right, and if not, why.

    """
    try:
        parsed = json.loads(text)
    except ValueError:
        return False, 'not JSON'
    if not isinstance(parsed, dict):
        return False, 'JSON, but not an object'
    answered = cast('dict[str, Any]', parsed)
    for key, value in expected.items():
        if answered.get(key) != value:
            return False, f'{key} should be {value!r}, not {answered.get(key)!r}'
    return True, ''


def ask(
    *,
    target: AskedOf,
    messages: list[dict[str, str]],
    time_limit_seconds: float = ANSWER_TIME_LIMIT_SECONDS,
) -> Answer:
    """Ask once, streaming as the console does, timing the first piece and the first of the answer.

    Prompt caching is off: in a game the state changes between questions, so caching would flatter
    the time to the first piece.

    Returns:
        The answer.

    Raises:
        ValueError: If the server refused.

    """
    body = {
        'model': target.alias,
        'messages': messages,
        'stream': True,
        'cache_prompt': False,
        'chat_template_kwargs': {'reasoning_effort': REASONING_EFFORT},
    }
    started = clock.raw_counter_seconds()
    text = ''
    pieces = 0
    first_piece: float | None = None
    first_answer: float | None = None
    stopped = False
    with httpx2.stream(
        'POST',
        f'{target.base_url}/v1/chat/completions',
        json=body,
        headers={'Authorization': f'Bearer {target.api_key}'},
        timeout=REQUEST_TIMEOUT_SECONDS,
    ) as response:
        if response.status_code != HTTP_OK:
            message = f'The server answered {response.status_code}: {response.read().decode()}'
            raise ValueError(message)
        for line in response.iter_lines():
            elapsed = clock.raw_counter_seconds() - started
            if elapsed > time_limit_seconds:
                stopped = True
                break
            for piece in pieces_of_stream_line(line=line):
                pieces += 1
                first_piece = elapsed if first_piece is None else first_piece
                if piece.is_answer:
                    first_answer = elapsed if first_answer is None else first_answer
                    text += piece.text
    return Answer(
        text=text,
        pieces=pieces,
        seconds=round(clock.raw_counter_seconds() - started, 3),
        first_piece_seconds=None if first_piece is None else round(first_piece, 3),
        first_answer_seconds=None if first_answer is None else round(first_answer, 3),
        stopped=stopped,
    )


def ask_question(*, target: AskedOf, question: Question, state: str) -> Answer:
    """Ask a question's turns in order, each after the answer before it.

    Returns:
        The last turn's answer, which is the one scored.

    """
    messages = [{'role': 'system', 'content': f'{SYSTEM_PROMPT}\n\nThe game right now: {state}'}]
    answer: Answer | None = None
    for turn in question.turns:
        messages.append({'role': 'user', 'content': turn})
        answer = ask(target=target, messages=messages)
        messages.append({'role': 'assistant', 'content': answer.text})
    assert answer is not None  # Every question has a turn: the tests hold the file to it
    return answer


def agent_label(*, size: str) -> str:
    """Name a size's launchd agent, whose settings the install holds.

    Returns:
        The label.

    """
    return f'ai.glitchygames.bonsai-2-{size}.llama-cpp'


def write_settings(*, root: Path, configuration: Configuration, port: int, directory: Path) -> None:
    """Copy a size's installed settings, changing only the port and context."""
    label = agent_label(size=configuration.size)
    shutil.copy(root / 'config' / f'{label}.env', directory / f'{label}.env')
    (directory / f'{label}.env.runtime').write_text(
        f'AI_PORT={port}\nAI_CONTEXT_SIZE={configuration.context}\n', encoding='utf-8'
    )


def memory_footprint_mebibytes(*, process_id: int) -> float | None:
    """Read a process's physical footprint, which counts GPU memory where RSS can't.

    Returns:
        Its footprint, or None if macOS's footprint tool didn't report one.

    """
    result = run_command(
        command=['/usr/bin/footprint', '-p', str(process_id), '--format', 'bytes'],
        environment=os.environ,
        timeout_seconds=FOOTPRINT_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )
    match = re.search(r'Footprint:\s*(\d+)\s*B', result.stdout)
    return round(int(match.group(1)) / MEBIBYTE, 1) if match else None


@contextlib.contextmanager
def running_server(
    *, root: Path, configuration: Configuration, port: int, log_path: Path
) -> Generator[tuple[AskedOf, float, Callable[[], float | None]]]:
    """Start a size's llama-server through the installed script, and stop it afterwards.

    Yields:
        How to ask it, how long it took to load, and how to read its memory.

    Raises:
        RuntimeError: If it exits or doesn't load in time.

    """
    label = agent_label(size=configuration.size)
    base_url = f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory() as directory, log_path.open('w', encoding='utf-8') as log:
        write_settings(root=root, configuration=configuration, port=port, directory=Path(directory))
        started = clock.raw_counter_seconds()
        process = start_command(
            command=['/bin/sh', str(root / 'bin' / 'run-llama-server.sh'), directory, label],
            environment=os.environ,
            output=log,
        )
        try:
            while clock.raw_counter_seconds() - started < SERVER_LOAD_TIMEOUT_SECONDS:
                if process.poll() is not None:
                    message = f'{label} exited with {process.returncode}: see {log_path}'
                    raise RuntimeError(message)
                with contextlib.suppress(httpx2.HTTPError):
                    health = httpx2.get(f'{base_url}/health', timeout=HEALTH_TIMEOUT_SECONDS)
                    if health.status_code == HTTP_OK:
                        break
                clock.raw_sleep(0.25)
            else:
                message = f'{label} did not load in {SERVER_LOAD_TIMEOUT_SECONDS} s'
                raise RuntimeError(message)
            load_seconds = round(clock.raw_counter_seconds() - started, 1)
            api_key = (root / 'config' / 'worker-api-key').read_text(encoding='utf-8').strip()
            target = AskedOf(
                base_url=base_url, api_key=api_key, alias=f'bonsai-2-{configuration.size}'
            )
            yield target, load_seconds, lambda: memory_footprint_mebibytes(process_id=process.pid)
        finally:
            stop_command(process=process)


def asked_result(
    *, target: AskedOf, configuration: Configuration, question: Question, repeat: int, state: str
) -> QuestionResult:
    """Ask and score one question. A failed request counts against the size, and the run goes on.

    Returns:
        The result.

    """
    try:
        answer = ask_question(target=target, question=question, state=state)
    except (httpx2.HTTPError, ValueError) as error:
        answer = Answer(
            text='',
            pieces=0,
            seconds=0.0,
            first_piece_seconds=None,
            first_answer_seconds=None,
            stopped=False,
        )
        passed, why = False, f'request failed: {error}'
    else:
        passed, why = score(question=question, answer=answer.text)
        if answer.stopped:
            passed, why = False, 'hit the time limit'
    return QuestionResult(
        configuration=configuration.name,
        question=question.name,
        kind=question.kind,
        repeat=repeat,
        passed=passed,
        why=why,
        answer=answer,
    )


def percentage(results: Sequence[QuestionResult]) -> float | None:
    """Work out the share that passed.

    Returns:
        A percentage, or None when there were none.

    """
    if not results:
        return None
    return round(100 * sum(result.passed for result in results) / len(results), 1)


def median_of(values: Sequence[float | None]) -> float | None:
    """Take a median, leaving out what was never measured.

    Returns:
        The median, or None when nothing was.

    """
    measured = [value for value in values if value is not None]
    return round(statistics.median(measured), 2) if measured else None


def summary_rows(
    *, results: Sequence[QuestionResult], servers: Sequence[ServerFacts]
) -> list[dict[str, float | str | None]]:
    """Reduce the results to a row per size and context.

    Returns:
        The rows, in the order the servers ran.

    """
    rows: list[dict[str, float | str | None]] = []
    for server in servers:
        own = [result for result in results if result.configuration == server.configuration]
        # From the first piece on: the time before it is the prompt being read, not generation
        pieces_per_second = [
            result.answer.pieces / (result.answer.seconds - result.answer.first_piece_seconds)
            for result in own
            if result.answer.first_piece_seconds is not None
            and result.answer.seconds > result.answer.first_piece_seconds
        ]
        rows.append({
            'configuration': server.configuration,
            'facts_percent': percentage([result for result in own if result.kind in FACT_KINDS]),
            'structured_percent': percentage([
                result for result in own if result.kind == STRUCTURED_KIND
            ]),
            'hard_percent': percentage([
                result for result in own if result.question.startswith(HARD_PREFIX)
            ]),
            'median_first_answer_seconds': median_of([
                result.answer.first_answer_seconds for result in own
            ]),
            'median_total_seconds': median_of([result.answer.seconds for result in own]),
            'median_pieces_per_second': median_of(pieces_per_second),
            'load_seconds': server.load_seconds,
            'footprint_mebibytes': server.footprint_mebibytes,
        })
    return rows


def summary_markdown(*, rows: Sequence[dict[str, float | str | None]]) -> str:
    """Write the rows as a table.

    Returns:
        Markdown.

    """
    heading = (
        '| Size and context | Facts % | JSON % | Hard % | First answer s | Total s | Tokens/s '
        '| Load s | Memory MiB |'
    )
    lines = [heading, '|---|---|---|---|---|---|---|---|---|']
    lines += [
        f'| {row["configuration"]} | {row["facts_percent"]} | {row["structured_percent"]} '
        f'| {row["hard_percent"]} | {row["median_first_answer_seconds"]} '
        f'| {row["median_total_seconds"]} | {row["median_pieces_per_second"]} '
        f'| {row["load_seconds"]} | {row["footprint_mebibytes"]} |'
        for row in rows
    ]
    return '\n'.join(lines) + '\n'


def answers_page(*, questions: Sequence[Question], results: Sequence[QuestionResult]) -> str:
    """Write every answer side by side, as a score can't say whether an answer is useful.

    Returns:
        A self-contained HTML page.

    """
    configurations = list(dict.fromkeys(result.configuration for result in results))
    heading = ''.join(f'<th>{html.escape(name)}</th>' for name in configurations)
    rows: list[str] = []
    for question in questions:
        cells: list[str] = []
        for configuration in configurations:
            own = [
                result
                for result in results
                if result.configuration == configuration and result.question == question.name
            ]
            passed = sum(result.passed for result in own)
            answers = ''.join(
                f'<p class="{"pass" if result.passed else "fail"}">'
                f'{html.escape(result.answer.text) or "(no answer)"}'
                f'{"" if result.passed else f"<small>{html.escape(result.why)}</small>"}</p>'
                for result in own
            )
            cells.append(f'<td><b>{passed}/{len(own)}</b>{answers}</td>')
        asked = '<br>'.join(html.escape(turn) for turn in question.turns)
        rows.append(
            f'<tr><th scope="row">{asked}<small>{html.escape(question.kind)}, '
            f'{html.escape(question.state)}</small></th>{"".join(cells)}</tr>'
        )
    return (
        '<!doctype html><html><head><meta charset="utf-8"><title>Bonsai Answers</title><style>'
        ':root{color-scheme:light dark;--pass:#1a7f37;--fail:#c62828}'
        'body{font:14px system-ui;margin:16px}table{border-collapse:collapse}'
        'th,td{border:1px solid #8888;padding:6px;vertical-align:top;min-width:180px}'
        'th{text-align:left}'
        'p{margin:4px 0;padding-left:6px}small{display:block;opacity:.7}'
        '.pass{border-left:3px solid var(--pass)}.fail{border-left:3px solid var(--fail)}'
        f'</style></head><body><table><thead><tr><th>Question</th>{heading}</tr></thead><tbody>'
        f'{"".join(rows)}</tbody></table></body></html>\n'
    )


def compare(
    *,
    root: Path,
    configurations: Sequence[Configuration],
    questions: Sequence[Question],
    repeats: int,
    output: Path,
) -> list[dict[str, float | str | None]]:
    """Ask every configuration every question, writing the reports.

    Returns:
        The summary's rows.

    """
    output.mkdir(parents=True, exist_ok=True)
    results: list[QuestionResult] = []
    servers: list[ServerFacts] = []
    states = {question.state: load_state(name=question.state) for question in questions}
    with (output / 'results.jsonl').open('w', encoding='utf-8') as results_file:
        for configuration in configurations:
            log_path = output / f'server-{configuration.name}.log'
            say(f'{configuration.name}: loading')
            with running_server(
                root=root, configuration=configuration, port=COMPARISON_PORT, log_path=log_path
            ) as (target, load_seconds, read_footprint):
                for repeat in range(repeats):
                    for question in questions:
                        result = asked_result(
                            target=target,
                            configuration=configuration,
                            question=question,
                            repeat=repeat,
                            state=states[question.state],
                        )
                        results.append(result)
                        results_file.write(result.model_dump_json() + '\n')
                        results_file.flush()
                servers.append(
                    ServerFacts(
                        configuration=configuration.name,
                        load_seconds=load_seconds,
                        footprint_mebibytes=read_footprint(),
                    )
                )
            say(f'{configuration.name}: done')
    rows = summary_rows(results=results, servers=servers)
    (output / 'summary.md').write_text(summary_markdown(rows=rows), encoding='utf-8')
    (output / 'answers.html').write_text(
        answers_page(questions=questions, results=results), encoding='utf-8'
    )
    return rows


def service_is_running(*, root: Path) -> bool:
    """Ask the installed script whether any of the service is up.

    Returns:
        Whether it is.

    """
    result = run_command(
        command=['/bin/sh', str(root / 'bin' / 'ai-service.sh'), 'status'],
        environment=os.environ,
        timeout_seconds=STATUS_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )
    return 'running=' in result.stdout


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the comparison.

    Returns:
        The exit code.

    """
    parser = argparse.ArgumentParser(description='Compare the Bonsai sizes on saved game states.')
    parser.add_argument('--output', type=Path, required=True, help='Where the reports go')
    parser.add_argument(
        '--configurations',
        default=','.join(DEFAULT_CONFIGURATIONS),
        help='Comma-separated SIZE:CONTEXT (default: %(default)s)',
    )
    parser.add_argument('--repeats', type=int, default=DEFAULT_REPEATS, help='Times each is asked')
    parser.add_argument('--only', default='', help='Only questions with this in their name')
    options = parser.parse_args(arguments)
    root = install_root()
    if service_is_running(root=root):
        say('The AI service is running: stop it first (ai-service.sh stop).')
        return ExitCode.OPTIONS_REFUSED
    rows = compare(
        root=root,
        configurations=[parse_configuration(text) for text in options.configurations.split(',')],
        questions=[question for question in load_questions() if options.only in question.name],
        repeats=options.repeats,
        output=options.output,
    )
    say(summary_markdown(rows=rows))
    return ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(main())
