"""Run the AI behaviour tests: each question, through tools, on 2B at 8K by default.

For every question it starts from that question's snapshot, lets the model call tools until it
answers (at most ``MAXIMUM_TOOL_ROUNDS`` rounds), then judges the answer with the question's check.
It keeps every answer, call and drawing, how long each took, and the context used, which is the
prompt plus what was generated, at its largest over the rounds. Speed doesn't matter here: these
test what the AI does.

Usage:
    uv run python -m scripts.ai_behaviour.run --game paddleslap --output test-results/ai-behaviour
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx2

from glitchygames import clock
from glitchygames.ai_link import install_root
from scripts.ai_behaviour.capture import FIXTURES_DIRECTORY, PACKAGE_DIRECTORY
from scripts.ai_behaviour.questions import QUESTIONS, Answered, BehaviourQuestion
from scripts.ai_behaviour.report import CUT_OFF
from scripts.ai_behaviour.tools import SnapshotTools, tool_definitions, tool_result_text
from scripts.ai_model_comparison import (
    COMPARISON_PORT,
    REQUEST_TIMEOUT_SECONDS,
    AskedOf,
    parse_configuration,
    running_server,
    say,
    service_is_running,
)

if TYPE_CHECKING:
    from glitchygames.ai_introspection import JsonValue

# 8 left 16 of 150 answers still exploring, mostly not looping (2026-11-07), so 16, with a nudge
# to answer this many rounds before the end
MAXIMUM_TOOL_ROUNDS = 16
NUDGE_ROUNDS_LEFT = 2
DEFAULT_CONFIGURATION = '2b:8192'
DEFAULT_REPEATS = 3
REASONING_EFFORT = 'low'
HTTP_OK = 200
SYSTEM_PROMPT = """You help a developer with the game {game}, running now.

The game's mechanics:
{mechanics}

How to answer, in this order:
1. If the mechanics above answer it, answer from them.
2. Otherwise read the game: get_scene, list_sprites, get_sprite, get_object, and history for the \
past.
3. Only if neither says how something works, read its code with read_source. Never make up rules.
Use calculate for arithmetic, and draw when asked to show something. If the game doesn't record \
something, work it out from history and say how. If a question assumes something untrue, say so; \
if you can't tell, say so.
Asked to change the game: say whether it offers a way, then always write Python for it in a \
```python block. It runs only in a copy of the game.
Answer briefly, in plain text."""


def mechanics_for(*, game: str) -> str:
    """Read a game's stand-in mechanics.

    Returns:
        The text.

    """
    return (PACKAGE_DIRECTORY / 'mechanics' / f'{game}.md').read_text(encoding='utf-8')


def load_snapshot(*, game: str, moment: str) -> dict[str, Any]:
    """Read a captured snapshot.

    Returns:
        The snapshot.

    """
    return json.loads((FIXTURES_DIRECTORY / game / f'{moment}.json').read_text(encoding='utf-8'))


def chat(
    *, target: AskedOf, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
) -> dict[str, Any]:
    """Send one round to the model, with the tools.

    Returns:
        The response's JSON.

    Raises:
        ValueError: If the server refused, which a full context does.

    """
    response = httpx2.post(
        f'{target.base_url}/v1/chat/completions',
        json={
            'model': target.alias,
            'messages': messages,
            'tools': tools,
            'chat_template_kwargs': {'reasoning_effort': REASONING_EFFORT},
        },
        headers={'Authorization': f'Bearer {target.api_key}'},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code != HTTP_OK:
        message = f'The server answered {response.status_code}: {response.text[:300]}'
        raise ValueError(message)
    return response.json()


def ask(*, target: AskedOf, question: BehaviourQuestion) -> dict[str, Any]:
    """Let the model answer one question through tools, and judge it.

    Returns:
        The result: answer, calls, drawings, rounds, seconds, context used, and the verdict.

    """
    started = clock.raw_counter_seconds()
    conversation = Conversation(question=question)
    failure = conversation.run(target=target)
    tools = conversation.tools
    answered = Answered(
        text=conversation.text,
        calls=tools.calls,
        drawings=tools.drawings,
        snapshot=conversation.snapshot,
    )
    if not failure and any(
        detail['finish_reason'] == 'length' for detail in conversation.round_details
    ):
        # Generation ran into the end of the context: whatever came before is incomplete
        failure = CUT_OFF
    passed, why = (False, failure) if failure else question.check(answered)
    return {
        'question': question.name,
        'categories': list(question.categories),
        'passed': passed,
        'why': why,
        'answer': conversation.text,
        'calls': tools.calls,
        'drawings': tools.drawings,
        'rounds': conversation.rounds,
        'seconds': round(clock.raw_counter_seconds() - started, 2),
        'context_used': conversation.context_used,
        # How many tokens a refused request needed, when the context was too small for it
        'overflow_tokens': overflow_tokens(failure=failure),
        'round_details': conversation.round_details,
        'tool_results': conversation.tool_results,
        'repeated_calls': tools.repeated_calls,
    }


class Conversation:
    """One question's rounds with the model: its messages, the stand-in tools, and the costs."""

    def __init__(self, *, question: BehaviourQuestion) -> None:
        """Open with the system prompt, the game's mechanics and the question."""
        self.snapshot = load_snapshot(game=question.game, moment=question.moment)
        self.tools = SnapshotTools(snapshot=self.snapshot)
        self.offered = tool_definitions(game=question.game)
        self.messages: list[dict[str, Any]] = [
            {
                'role': 'system',
                'content': SYSTEM_PROMPT.format(
                    game=question.game, mechanics=mechanics_for(game=question.game)
                ),
            },
            {'role': 'user', 'content': question.text},
        ]
        self.text = ''
        self.rounds = 0
        self.context_used = 0
        # Kept for the statistics only: what each round cost, and each tool answer's size
        self.round_details: list[dict[str, Any]] = []
        self.tool_results: list[dict[str, Any]] = []

    def run(self, *, target: AskedOf) -> str:
        """Go round until the model answers, runs out of rounds, or a request fails.

        Returns:
            Why it failed, or an empty string when it answered.

        """
        try:
            for round_number in range(1, MAXIMUM_TOOL_ROUNDS + 1):
                if self.play_round(target=target, round_number=round_number):
                    return ''
        except (httpx2.HTTPError, ValueError) as error:
            return f'request failed: {error}'
        return f'still calling tools after {MAXIMUM_TOOL_ROUNDS} rounds'

    def play_round(self, *, target: AskedOf, round_number: int) -> bool:
        """Send one round, record its cost, and answer any tool calls it made.

        Returns:
            True when the model answered rather than calling tools.

        """
        self.rounds = round_number
        rounds_left = MAXIMUM_TOOL_ROUNDS - round_number + 1
        if rounds_left == NUDGE_ROUNDS_LEFT:
            self.messages.append({
                'role': 'user',
                'content': f'({rounds_left} tool rounds left: answer now with what you have.)',
            })
        round_started = clock.raw_counter_seconds()
        body = chat(target=target, messages=self.messages, tools=self.offered)
        choice = body['choices'][0]
        message = choice['message']
        calls: list[dict[str, Any]] = message.get('tool_calls') or []
        timings = body.get('timings', {})
        self.round_details.append({
            'round': round_number,
            'seconds': round(clock.raw_counter_seconds() - round_started, 3),
            'cache_tokens': timings.get('cache_n', 0),
            'prompt_tokens': timings.get('prompt_n', 0),
            'generated_tokens': timings.get('predicted_n', 0),
            'finish_reason': choice.get('finish_reason'),
            'tool_calls': [call['function']['name'] for call in calls],
        })
        # prompt_n counts only what wasn't reused from the cache, which cache_n counts
        self.context_used = max(
            self.context_used,
            timings.get('cache_n', 0) + timings.get('prompt_n', 0) + timings.get('predicted_n', 0),
        )
        if not calls:
            self.text = message.get('content') or ''
            return True
        self.messages.append(message)
        for call in calls:
            self.answer_call(call=call)
        return False

    def answer_call(self, *, call: dict[str, Any]) -> None:
        """Run one tool call and add its answer to the messages."""
        try:
            decoded: JsonValue = json.loads(call['function'].get('arguments') or '{}')
        except ValueError:
            decoded = {}
        # A model may send arguments that aren't an object: those are treated as none
        arguments: dict[str, Any] = decoded if isinstance(decoded, dict) else {}
        result = self.tools.call(name=call['function']['name'], arguments=arguments)
        result_text = tool_result_text(result)
        self.tool_results.append({
            'name': call['function']['name'],
            'characters': len(result_text),
            'error': isinstance(result, dict) and 'error' in result,
        })
        self.messages.append({
            'role': 'tool',
            'tool_call_id': call.get('id', ''),
            'content': result_text,
        })


def overflow_tokens(*, failure: str) -> int | None:
    """Read how many tokens a request needed from llama-server's refusal, if it was one.

    Returns:
        The tokens, or None when the failure was something else.

    """
    match = re.search(r'request \((\d+) tokens\) exceeds', failure)
    return int(match.group(1)) if match else None


def summary(*, results: list[dict[str, Any]]) -> str:
    """Write a row per question: passes, tool calls, rounds, time and context.

    Returns:
        Markdown.

    """
    header = (
        'Question',
        'Passed',
        'Tool calls (median)',
        'Seconds (median)',
        'Context used (max)',
        'Why it failed',
    )
    lines = ['| ' + ' | '.join(header) + ' |', '|' + '---|' * len(header)]
    for name in dict.fromkeys(result['question'] for result in results):
        own = [result for result in results if result['question'] == name]
        reasons = sorted({result['why'] for result in own if not result['passed']})
        lines.append(
            f'| {name} | {sum(result["passed"] for result in own)}/{len(own)} '
            f'| {statistics.median(len(result["calls"]) for result in own)} '
            f'| {statistics.median(result["seconds"] for result in own)} '
            f'| {max(result["context_used"] for result in own)} | {"; ".join(reasons)[:160]} |'
        )
    return '\n'.join(lines) + '\n'


def main(arguments: list[str] | None = None) -> int:
    """Run a game's questions.

    Returns:
        The exit code: 0 when every question was asked, whatever the answers.

    """
    parser = argparse.ArgumentParser(description='Run the AI behaviour tests.')
    parser.add_argument('--game', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--configuration', default=DEFAULT_CONFIGURATION)
    parser.add_argument('--repeats', type=int, default=DEFAULT_REPEATS)
    parser.add_argument('--only', default='', help='Only questions with this in their name')
    options = parser.parse_args(arguments)
    root = install_root()
    if service_is_running(root=root):
        say('The AI service is running: stop it first (ai-service.sh stop).')
        return 64
    questions = [
        question
        for question in QUESTIONS
        if question.game == options.game and options.only in question.name
    ]
    options.output.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    configuration = parse_configuration(options.configuration)
    with (
        running_server(
            root=root,
            configuration=configuration,
            port=COMPARISON_PORT,
            log_path=options.output / f'server-{configuration.name}.log',
        ) as (target, load_seconds, read_footprint),
        (options.output / 'results.jsonl').open('w', encoding='utf-8') as results_file,
    ):
        for repeat in range(options.repeats):
            for question in questions:
                result = {'repeat': repeat, **ask(target=target, question=question)}
                results.append(result)
                results_file.write(json.dumps(result) + '\n')
                results_file.flush()
                say(f'{question.name} #{repeat}: {"pass" if result["passed"] else "FAIL"}')
        # The server's cost after the whole session
        (options.output / 'server.json').write_text(
            json.dumps({
                'configuration': configuration.name,
                'load_seconds': load_seconds,
                'footprint_mebibytes': read_footprint(),
            }),
            encoding='utf-8',
        )
    text = summary(results=results)
    (options.output / 'summary.md').write_text(text, encoding='utf-8')
    say(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
