"""Statistics from AI behaviour test runs, one configuration or several side by side.

Reads each configuration's ``results.jsonl`` (one per game) and ``server.json``, and reports, as
Markdown: passes by game, category and question with 95% Wilson intervals; why answers failed;
how much context answers used, and how close they came to the limit; the opening's size; tool
use, errors and answer sizes; rounds, finish reasons, time and memory; and, between two
configurations, the questions that got better or worse.

Usage:
    uv run python -m scripts.ai_behaviour.report DIRECTORY [DIRECTORY ...]
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

WILSON_Z = 1.96
# An answer whose generation ran into the end of the context: llama-server stops it with
# finish reason "length", and whatever it managed before then is incomplete
CUT_OFF = 'cut off: the context filled'
# How each failure reads in a result's ``why``, checked in this order (a size refusal also says
# "request failed", so it comes first)
FAILURE_SIGNS = (
    ('exceeds the available context', 'overflow: refused'),
    (CUT_OFF, 'overflow: cut off'),
    ('still calling tools', 'out of rounds'),
    ('request failed', 'refused'),
)
# A comparison of exactly two configurations also lists the questions that changed
PAIRED_CONFIGURATIONS = 2
NEAR_LIMIT_FRACTION = 0.75
SMALLEST_CONTEXT = 8192


def wilson(*, passed: int, total: int) -> tuple[float, float]:
    """The 95% Wilson interval for a pass rate: honest at small counts and at 0 or 100%.

    Returns:
        Its low and high ends, as percentages.

    """
    if total == 0:
        return 0.0, 0.0
    rate = passed / total
    denominator = 1 + WILSON_Z**2 / total
    middle = (rate + WILSON_Z**2 / (2 * total)) / denominator
    spread = (
        WILSON_Z * math.sqrt(rate * (1 - rate) / total + WILSON_Z**2 / (4 * total**2)) / denominator
    )
    return round(100 * (middle - spread), 1), round(100 * (middle + spread), 1)


def percentile(values: list[float], fraction: float) -> float:
    """A percentile, by nearest rank.

    Returns:
        The value, or 0 for no values.

    """
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)]


def failure_kind(result: dict[str, Any]) -> str:
    """Name why an answer failed.

    Returns:
        ``passed``, ``overflow``, ``out of rounds``, ``refused``, ``empty`` or ``wrong``.

    """
    if result['passed']:
        return 'passed'
    for sign, kind in FAILURE_SIGNS:
        if sign in result['why']:
            return kind
    return 'wrong' if result['answer'].strip() else 'empty'


def was_cut_off(result: dict[str, Any]) -> bool:
    """Whether any round's generation ran into the end of the context.

    Returns:
        True when a round finished for ``length``.

    """
    return any(
        detail.get('finish_reason') == 'length' for detail in result.get('round_details', [])
    )


def scored_again(result: dict[str, Any]) -> dict[str, Any]:
    """Fail an answer that was cut off, whatever its check said: it never finished.

    Results from before the runner failed these itself are corrected here.

    Returns:
        The result, corrected.

    """
    if was_cut_off(result) and not result['why'].startswith(CUT_OFF):
        return {**result, 'passed': False, 'why': CUT_OFF}
    return result


def load(*, directory: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read every game's results under a configuration's directory, and its server facts.

    Returns:
        The results, each with its game, and the server facts by game.

    """
    results: list[dict[str, Any]] = []
    servers: dict[str, Any] = {}
    for results_path in sorted(directory.glob('*/results.jsonl')):
        game = results_path.parent.name
        results.extend(
            scored_again({'game': game, **json.loads(line)})
            for line in results_path.read_text(encoding='utf-8').splitlines()
        )
        server_path = results_path.parent / 'server.json'
        if server_path.exists():
            servers[game] = json.loads(server_path.read_text(encoding='utf-8'))
    return results, servers


def rate_cell(results: list[dict[str, Any]]) -> str:
    """A pass count, rate and interval, for one table cell.

    Returns:
        Text like ``31/50 62% (48-74)``.

    """
    passed, total = sum(result['passed'] for result in results), len(results)
    low, high = wilson(passed=passed, total=total)
    rate = round(100 * passed / total) if total else 0
    return f'{passed}/{total} {rate}% ({low:.0f}-{high:.0f})'


def grouped(results: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    """Results by a field, or by each category when the field is ``categories``.

    Returns:
        The groups.

    """
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for result in results:
        for value in result[key] if key == 'categories' else [result[key]]:
            groups[value].append(result)
    return dict(sorted(groups.items()))


def table(*, title: str, header: list[str], rows: list[list[str]]) -> str:
    """Write a Markdown table under a heading.

    Returns:
        Markdown.

    """
    lines = [f'## {title}', '', '| ' + ' | '.join(header) + ' |', '|' + '---|' * len(header)]
    lines += ['| ' + ' | '.join(row) + ' |' for row in rows]
    return '\n'.join(lines) + '\n'


def report(*, runs: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]]) -> str:
    """Write the whole report for one or more configurations.

    Returns:
        Markdown.

    """
    names = list(runs)
    sections = ['# AI behaviour test statistics', '']
    for key, title in (('game', 'Passes by game'), ('categories', 'Passes by category')):
        groups = sorted({
            group for results, _servers in runs.values() for group in grouped(results, key)
        })
        rows = [
            [group, *(rate_cell(grouped(runs[name][0], key).get(group, [])) for name in names)]
            for group in groups
        ]
        rows.append(['**all**', *(rate_cell(runs[name][0]) for name in names)])
        sections.append(table(title=title, header=[key, *names], rows=rows))
    kinds = (
        'passed',
        'wrong',
        'overflow: refused',
        'overflow: cut off',
        'out of rounds',
        'refused',
        'empty',
    )
    outcomes = table(
        title='Outcomes',
        header=['outcome', *names],
        rows=[
            [
                kind,
                *(
                    str(sum(failure_kind(result) == kind for result in runs[name][0]))
                    for name in names
                ),
            ]
            for kind in kinds
        ],
    )
    sections.extend([
        outcomes,
        context_section(runs=runs),
        tool_section(runs=runs),
        cost_section(runs=runs),
    ])
    if len(names) == PAIRED_CONFIGURATIONS:
        sections.append(change_section(runs=runs))
    return '\n'.join(sections)


def context_section(*, runs: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]]) -> str:
    """How much context answers used, the opening's size, and how close they came to the limit.

    Returns:
        Markdown.

    """
    rows: list[list[str]] = []
    for name, (results, _servers) in runs.items():
        limit = int(name.split('-')[-1]) if name.split('-')[-1].isdigit() else SMALLEST_CONTEXT
        used = [result['context_used'] for result in results if result['context_used']]
        openings = [
            details[0]['cache_tokens'] + details[0]['prompt_tokens']
            for result in results
            if (details := result.get('round_details'))
        ]
        needed = [result['overflow_tokens'] for result in results if result.get('overflow_tokens')]
        spread = ' / '.join(
            f'{percentile(used, fraction):.0f}' for fraction in (0.5, 0.9, 0.95, 1.0)
        )
        opening_range = f'{min(openings, default=0)}-{max(openings, default=0)}'
        rows.append([
            name,
            spread,
            f'{sum(value >= NEAR_LIMIT_FRACTION * limit for value in used)}',
            f'{sum(value > SMALLEST_CONTEXT for value in used)}',
            f'{percentile(openings, 0.5):.0f} ({opening_range})',
            ', '.join(str(value) for value in sorted(needed)) or '-',
        ])
    return table(
        title='Context',
        header=[
            'configuration',
            'used: p50 / p90 / p95 / max',
            'within 75% of the limit',
            'needed more than 8K',
            'opening: median (range)',
            'tokens refused requests needed',
        ],
        rows=rows,
    )


def tool_section(*, runs: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]]) -> str:
    """Tool calls, errors and answer sizes per tool.

    Returns:
        Markdown.

    """
    rows: list[list[str]] = []
    tools = sorted({
        tool['name']
        for results, _servers in runs.values()
        for result in results
        for tool in result.get('tool_results', [])
    })
    for tool in tools:
        cells = [tool]
        for results, _servers in runs.values():
            sizes = [
                entry['characters']
                for result in results
                for entry in result.get('tool_results', [])
                if entry['name'] == tool
            ]
            errors = sum(
                entry['error']
                for result in results
                for entry in result.get('tool_results', [])
                if entry['name'] == tool
            )
            sizes_text = f'size p50 {percentile(sizes, 0.5):.0f} max {max(sizes, default=0)}'
            cells.append(f'{len(sizes)} calls, {errors} errors, {sizes_text}')
        rows.append(cells)
    return table(title='Tools', header=['tool', *runs], rows=rows)


def cost_section(*, runs: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]]) -> str:
    """Rounds, finish reasons, time and memory.

    Returns:
        Markdown.

    """
    rows: list[list[str]] = []
    for name, (results, servers) in runs.items():
        rounds = [result['rounds'] for result in results]
        seconds = [result['seconds'] for result in results]
        round_seconds = [
            detail['seconds'] for result in results for detail in result.get('round_details', [])
        ]
        generated = [
            detail['generated_tokens']
            for result in results
            for detail in result.get('round_details', [])
        ]
        finishes = collections.Counter(
            str(detail['finish_reason'])
            for result in results
            for detail in result.get('round_details', [])
        )
        memory = [
            server['footprint_mebibytes']
            for server in servers.values()
            if server.get('footprint_mebibytes')
        ]
        repeated = sum(result.get('repeated_calls', 0) for result in results)
        rows.append([
            name,
            f'{statistics.median(rounds)} (max {max(rounds)}), {repeated} repeated calls',
            f'{percentile(seconds, 0.5):.1f} / {percentile(seconds, 0.9):.1f} / {max(seconds):.1f}',
            f'{percentile(round_seconds, 0.5):.1f}',
            f'{percentile(generated, 0.5):.0f} / {max(generated, default=0)}',
            ', '.join(f'{reason} {count}' for reason, count in finishes.most_common()),
            f'{max(memory, default=0):.0f}',
        ])
    return table(
        title='Cost',
        header=[
            'configuration',
            'rounds: median',
            'seconds: p50 / p90 / max',
            'seconds per round',
            'generated per round: p50 / max',
            'finish reasons',
            'memory after (MiB, max)',
        ],
        rows=rows,
    )


def change_section(*, runs: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]]) -> str:
    """The questions whose passes changed between two configurations, largest first.

    Returns:
        Markdown.

    """
    first, second = list(runs)
    counts = {name: collections.Counter[str]() for name in runs}
    totals = {name: collections.Counter[str]() for name in runs}
    for name, (results, _servers) in runs.items():
        for result in results:
            counts[name][result['question']] += result['passed']
            totals[name][result['question']] += 1
    questions = sorted(set(totals[first]) | set(totals[second]))
    changed = sorted(
        (counts[second][question] - counts[first][question], question) for question in questions
    )
    rows = [
        [
            question,
            f'{counts[first][question]}/{totals[first][question]}',
            f'{counts[second][question]}/{totals[second][question]}',
            f'{delta:+d}',
        ]
        for delta, question in changed
        if delta
    ]
    return table(
        title=f'Questions that changed, {first} to {second}',
        header=['question', first, second, 'change'],
        rows=rows,
    )


def main(arguments: list[str] | None = None) -> int:
    """Report on the given configurations' directories.

    Returns:
        The exit code.

    """
    parser = argparse.ArgumentParser(description='Statistics from AI behaviour test runs.')
    parser.add_argument('directories', type=Path, nargs='+')
    options = parser.parse_args(arguments)
    runs = {directory.name: load(directory=directory) for directory in options.directories}
    sys.stdout.write(report(runs=runs))
    return 0


if __name__ == '__main__':
    sys.exit(main())
