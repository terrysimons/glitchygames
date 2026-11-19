"""Turn llama.cpp's raw output into the summary lines benchmark_llama_cpp.sh prints.

Runs on the Raspberry Pi with its system Python and nothing else installed, beside the shell
script that calls it:

    python3 summarize_llama_cpp_results.py bench RESULT_JSON MODEL_NAME
    python3 summarize_llama_cpp_results.py answer LABEL EXPECTED < chat_completion.json
    python3 summarize_llama_cpp_results.py embeddings < embeddings.json
    python3 summarize_llama_cpp_results.py image
    python3 summarize_llama_cpp_results.py power POWER_CSV
    python3 summarize_llama_cpp_results.py placement [CPU_ROOT]

Each prints one or more lines, and a reply it can't read becomes a line saying so, never a crash,
so one bad configuration doesn't end the run.
"""

from __future__ import annotations

import base64
import csv
import json
import math
import struct
import sys
import zlib
from pathlib import Path

EMBEDDING_PHRASES = ('a red apple', 'a green apple', 'a diesel locomotive')
IMAGE_SIDE = 64
# The game's core and the mirror's, before the AI's (plans/lucid-circuit-linux.md 6.2)
GAME_AND_MIRROR_CORES = 2

# vcgencmd get_throttled's bits (https://www.raspberrypi.com/documentation/computers/os.html#get_throttled)
THROTTLED_BITS = {
    0: 'under-voltage now',
    1: 'clock capped now',
    2: 'throttled now',
    3: 'soft temperature limit now',
    16: 'under-voltage has occurred',
    17: 'clock capping has occurred',
    18: 'throttling has occurred',
    19: 'soft temperature limit has occurred',
}


def summarize_bench(*, result_path: Path, model_name: str) -> list[str]:
    """Describe each llama-bench run in a result file.

    Args:
        result_path: llama-bench's ``-o json`` output.
        model_name: The model's file name, for the line.

    Returns:
        One line per run, or one saying the file couldn't be read.

    """
    try:
        runs = json.loads(result_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        return [f'  {model_name}: llama-bench failed ({error}); see its .log']
    lines: list[str] = []
    for run in runs:
        test = f'pp{run["n_prompt"]}' if run['n_gen'] == 0 else f'tg{run["n_gen"]}'
        # How many tokens llama-bench put in the KV cache before timing (-d): reading a full
        # cache is part of every token's cost, so a test at depth 0 says nothing about it
        depth = run.get('n_depth', 0)
        if depth:
            test = f'{test} @ d{depth}'
        lines.append(
            f'  {model_name}  {test}: {run["avg_ts"]:.2f} ± {run["stddev_ts"]:.2f} tok/s  '
            f'(KV cache {run.get("type_k")}/{run.get("type_v")}, threads {run.get("n_threads")}, '
            f'backends {run.get("backends")}, gpu layers {run.get("n_gpu_layers")})'
        )
    return lines


def summarize_answer(*, label: str, expected: str, reply_text: str) -> str:
    """Judge one chat completion and describe its speed.

    Args:
        label: The question's short name.
        expected: Text the answer must contain to count as right, compared without case.
        reply_text: The server's JSON reply.

    Returns:
        One line.

    """
    try:
        reply = json.loads(reply_text)
        message = reply['choices'][0]['message']
    except (ValueError, KeyError, IndexError, TypeError) as error:
        return f'  {label}: no answer ({error}): {reply_text[:200]!r}'
    answer = (message.get('content') or '').strip()
    reasoning = message.get('reasoning_content') or ''
    timings = reply.get('timings', {})
    verdict = 'right' if expected.lower() in answer.lower() else 'WRONG'
    return (
        f'  {label}: {verdict}: {answer[:120]!r}  (reasoning {len(reasoning)} chars, '
        f'{timings.get("predicted_n")} tokens at {timings.get("predicted_per_second", 0):.1f} '
        f'tok/s, prompt {timings.get("prompt_per_second", 0):.1f} tok/s)'
    )


def cosine(first: list[float], second: list[float]) -> float:
    """Return the cosine similarity of two vectors.

    Returns:
        A value from -1 to 1.

    """
    dot = sum(a * b for a, b in zip(first, second, strict=True))
    return dot / math.sqrt(sum(a * a for a in first) * sum(b * b for b in second))


def summarize_embeddings(*, reply_text: str) -> str:
    """Check that two similar phrases score closer than an unrelated one.

    Args:
        reply_text: The server's JSON reply for ``EMBEDDING_PHRASES``, in that order.

    Returns:
        One line.

    """
    try:
        vectors = [item['embedding'] for item in json.loads(reply_text)['data']]
    except (ValueError, KeyError, TypeError) as error:
        return f'  no embeddings ({error}): {reply_text[:200]!r}'
    near = cosine(vectors[0], vectors[1])
    far = cosine(vectors[0], vectors[2])
    verdict = 'right' if near > far else 'WRONG'
    return (
        f'  {len(vectors[0])} dimensions; apple~apple {near:.3f}, '
        f'apple~locomotive {far:.3f}: {verdict}'
    )


def png_chunk(*, kind: bytes, data: bytes) -> bytes:
    """Return one PNG chunk: length, type, data and CRC.

    Returns:
        The chunk's bytes.

    """
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', checksum)


def two_colour_image() -> str:
    """Make a small PNG, left half red and right half blue, so nothing is downloaded.

    Returns:
        The PNG, base64-encoded.

    """
    half = IMAGE_SIDE // 2
    row = b'\x00' + b'\xff\x00\x00' * half + b'\x00\x00\xff' * (IMAGE_SIDE - half)
    header = struct.pack('>IIBBBBB', IMAGE_SIDE, IMAGE_SIDE, 8, 2, 0, 0, 0)
    png = (
        b'\x89PNG\r\n\x1a\n'
        + png_chunk(kind=b'IHDR', data=header)
        + png_chunk(kind=b'IDAT', data=zlib.compress(row * IMAGE_SIDE))
        + png_chunk(kind=b'IEND', data=b'')
    )
    return base64.b64encode(png).decode('ascii')


def describe_throttled(*, flags: int) -> str:
    """Name every set bit of vcgencmd get_throttled's value.

    Args:
        flags: The value, as an integer.

    Returns:
        The names joined, or "none".

    """
    names = [name for bit, name in THROTTLED_BITS.items() if flags & (1 << bit)]
    return ', '.join(names) if names else 'none'


def summarize_power(*, samples_path: Path) -> list[str]:
    """Sum up the power samples benchmark_llama_cpp.sh took, step by step.

    Args:
        samples_path: Its power.csv, one row a second.

    Returns:
        A line per step (lowest clock, hottest, lowest supply and core voltage), then every
        throttle flag seen in the whole run, or one line saying the file couldn't be read.

    """
    try:
        with samples_path.open(encoding='utf-8', newline='') as samples_file:
            rows = list(csv.DictReader(samples_file))
    except OSError as error:
        return [f'  no power samples ({error})']
    lines: list[str] = []
    flags_seen = 0
    phases: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        phases.setdefault(row['phase'], []).append(row)
    for phase, phase_rows in phases.items():
        try:
            clocks = [int(row['clock_mhz']) for row in phase_rows]
            temperatures = [float(row['temperature_c']) for row in phase_rows]
            supplies = [float(row['supply_volts']) for row in phase_rows]
            cores = [float(row['core_volts']) for row in phase_rows]
            for row in phase_rows:
                flags_seen |= int(row['throttled'], 16)
        except (KeyError, ValueError) as error:
            lines.append(f'  {phase}: unreadable samples ({error})')
            continue
        lines.append(
            f'  {phase}: {len(phase_rows)} s; clock {min(clocks)}-{max(clocks)} MHz; '
            f'up to {max(temperatures):.1f} C; supply down to {min(supplies):.3f} V; '
            f'core {min(cores):.4f}-{max(cores):.4f} V'
        )
    lines.append(f'  throttle flags seen: {describe_throttled(flags=flags_seen)}')
    return lines


def online_cores(*, cpu_root: Path) -> list[int]:
    """Read which cores are online, from a list such as ``0-3`` or ``0,2-5``.

    Args:
        cpu_root: ``/sys/devices/system/cpu``, or a stand-in.

    Returns:
        The core numbers, ascending.

    """
    cores: list[int] = []
    for part in (cpu_root / 'online').read_text(encoding='utf-8').strip().split(','):
        first, _, last = part.partition('-')
        cores.extend(range(int(first), int(last or first) + 1))
    return sorted(cores)


def cpu_placement(*, cpu_root: Path) -> dict[str, list[int]]:
    """Place the game, the mirror and the AI the way the service does.

    plans/lucid-circuit-linux.md 6.2: cores ranked by ``cpu_capacity``, highest first, ties by
    number (by number alone unless every core reports one); the game takes the first, the mirror
    the second, the AI the rest; with two cores the AI shares the mirror's; with one, nothing is
    placed. The service's ``setup.sh`` is where this rule lives once it is built.

    Args:
        cpu_root: ``/sys/devices/system/cpu``, or a stand-in.

    Returns:
        ``game``, ``mirror`` and ``ai`` core lists, or an empty mapping for a single core.

    """
    cores = online_cores(cpu_root=cpu_root)
    capacity_files = {core: cpu_root / f'cpu{core}' / 'cpu_capacity' for core in cores}
    if all(path.is_file() for path in capacity_files.values()):
        capacities = {
            core: int(path.read_text(encoding='utf-8')) for core, path in capacity_files.items()
        }
        ranked = sorted(cores, key=lambda core: (-capacities[core], core))
    else:
        ranked = cores
    if len(ranked) < GAME_AND_MIRROR_CORES:
        return {}
    # With only two cores the AI shares the mirror's, never the game's
    ai = (
        [ranked[1]]
        if len(ranked) == GAME_AND_MIRROR_CORES
        else sorted(ranked[GAME_AND_MIRROR_CORES:])
    )
    return {'game': [ranked[0]], 'mirror': [ranked[1]], 'ai': ai}


def main(arguments: list[str]) -> int:
    """Print the summary the first argument asks for.

    Args:
        arguments: The command line, less the program name.

    Returns:
        0, or 64 for a command line it doesn't know.

    """
    match arguments:
        case ['bench', result_path, model_name]:
            lines = summarize_bench(result_path=Path(result_path), model_name=model_name)
            sys.stdout.write('\n'.join(lines) + '\n')
        case ['answer', label, expected]:
            sys.stdout.write(
                summarize_answer(label=label, expected=expected, reply_text=sys.stdin.read()) + '\n'
            )
        case ['embeddings']:
            sys.stdout.write(summarize_embeddings(reply_text=sys.stdin.read()) + '\n')
        case ['image']:
            sys.stdout.write(two_colour_image() + '\n')
        case ['power', samples_path]:
            sys.stdout.write('\n'.join(summarize_power(samples_path=Path(samples_path))) + '\n')
        case ['placement', *rest] if len(rest) <= 1:
            # One line per part, such as "ai 2,3", for the shell to read; nothing for one core
            placement = cpu_placement(cpu_root=Path(rest[0] if rest else '/sys/devices/system/cpu'))
            for part, cores in placement.items():
                sys.stdout.write(f'{part} {",".join(str(core) for core in cores)}\n')
        case _:
            sys.stderr.write(f'{__doc__}\n')
            return 64
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
