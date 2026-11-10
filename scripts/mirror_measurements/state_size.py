"""Each frame's whole state, as the AI's tools read it, with no sprite cap.

Read as scripts/ai_behaviour/capture.py reads a snapshot (properties on, plumbing off): the scene
(depth 0), its ``describe_for_ai()`` facts, and every sprite one level deep by stable id. The size
is compact JSON in bytes, every ``--every``-th frame. Each recording's largest frame is written
beside its result (``NAME.largest.json``), to see what makes it large.

Usage:
    uv run python -m scripts.mirror_measurements.state_size --output DIR [--every 10]
        [--only NAME ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from scripts.mirror_measurements.common import (
    RECORDING_NAMES,
    percentiles,
    recording_named,
    replay_with_hook,
    run_measurement,
)

if TYPE_CHECKING:
    from glitchygames.scenes import Scene

MODULE = 'scripts.mirror_measurements.state_size'
DEFAULT_EVERY = 10


def measure(*, name: str, every: int, output: Path) -> dict[str, Any]:
    """Replay one recording, sizing its state every ``every`` frames.

    Returns:
        The run's result.

    """
    from glitchygames.ai_introspection import ReadOptions, read_object
    from glitchygames.tracing import StableSpriteIds

    options = ReadOptions(include_properties=True)
    sprite_ids = StableSpriteIds()
    sizes: list[dict[str, Any]] = []
    largest: dict[str, Any] = {'bytes': 0, 'text': ''}

    def on_frame(frame: int, scene: Scene | None, _processing: float | None) -> None:
        if scene is None:
            return
        subject = scene.debug_subject
        # Ids are given on first sight, so every frame's sprites are seen, as the recorder does
        for sprite in subject.all_sprites:
            sprite_ids.id_for(sprite)
        if frame % every:
            return
        sprites = {
            str(read['id']): read
            for read in (
                read_object(value=sprite, depth=1, sprite_ids=sprite_ids, options=options)
                for sprite in subject.all_sprites
            )
        }
        state = {
            'scene': read_object(value=subject, depth=0, sprite_ids=sprite_ids, options=options),
            'facts': subject.describe_for_ai(),
            'sprites': sprites,
        }
        text = json.dumps(state, separators=(',', ':'), default=str)
        entry = {
            'frame': frame,
            'scene': type(subject).__qualname__,
            'sprites': len(sprites),
            'bytes': len(text),
            'sprite_bytes': len(json.dumps(sprites, separators=(',', ':'), default=str)),
        }
        sizes.append(entry)
        if entry['bytes'] > largest['bytes']:
            largest.update(entry, text=text)

    replay_with_hook(recording=recording_named(name), on_frame=on_frame)
    (output / f'{name}.largest.json').write_text(largest.pop('text'), encoding='utf-8')
    return {
        'name': name,
        'measured_frames': len(sizes),
        'bytes': percentiles([entry['bytes'] for entry in sizes]).model_dump(),
        'sprites': percentiles([entry['sprites'] for entry in sizes]).model_dump(),
        'bytes_per_sprite': percentiles([
            entry['sprite_bytes'] / entry['sprites'] for entry in sizes if entry['sprites']
        ]).model_dump(),
        'largest': largest,
        'by_frame': sizes,
    }


def summary_line(result: dict[str, Any]) -> str:
    """One recording's line.

    Returns:
        The line.

    """
    size = result['bytes']
    return (
        f'{result["name"]}: {result["measured_frames"]} frames, sprites max '
        f'{result["sprites"]["max"]:.0f}, state p50 {size["p50"] / 1e3:.1f} KB, max '
        f'{size["max"] / 1e3:.1f} KB, {result["bytes_per_sprite"]["p50"]:.0f} B per sprite\n'
    )


def main(arguments: list[str] | None = None) -> int:
    """Size every recording's state, each its own process, or (``--child``) one.

    Returns:
        0, or the first failed run's exit code.

    """
    parser = argparse.ArgumentParser(
        description="Each frame's whole state, as the AI's tools read it, with no sprite cap"
    )
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--every', type=int, default=DEFAULT_EVERY)
    parser.add_argument('--only', nargs='+', choices=RECORDING_NAMES, default=RECORDING_NAMES)
    parser.add_argument('--child', choices=RECORDING_NAMES, help=argparse.SUPPRESS)
    options = parser.parse_args(arguments)
    options.output.mkdir(parents=True, exist_ok=True)
    if options.child is not None:
        result = measure(name=options.child, every=options.every, output=options.output)
        (options.output / f'{options.child}.json').write_text(
            json.dumps(result, indent=1), encoding='utf-8'
        )
        return 0
    for name in options.only:
        exit_code = run_measurement(
            module=MODULE,
            arguments=[
                '--output',
                str(options.output),
                '--every',
                str(options.every),
                '--child',
                name,
            ],
        )
        if exit_code:
            return exit_code
        result = json.loads((options.output / f'{name}.json').read_text(encoding='utf-8'))
        sys.stdout.write(summary_line(result))
        sys.stdout.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
