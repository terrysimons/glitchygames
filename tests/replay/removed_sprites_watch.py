"""Watch one replay for sprites removed from every group yet still in memory.

Run as a child, ``python -m tests.replay.removed_sprites_watch CONSOLE_SCRIPT RECORDING``: a replay
needs a process of its own. It prints a JSON report as its last line. The sprites it watches are
those the replay samples, so every sprite the engine compares is covered, with no opt-in.
"""

from __future__ import annotations

import collections
import contextlib
import gc
import json
import sys
import weakref
from typing import Any

from glitchygames import tracing
from glitchygames.replay.tools.children import game_entry_point

# How many sprite samples pass between checks: each runs the garbage collector
SPRITE_SAMPLES_BETWEEN_CHECKS = 1000
HOLDERS_SHOWN_PER_CHECK = 3


class RemovedSpriteWatch:
    """Remembers sprites weakly, and reports those removed yet still held."""

    def __init__(self) -> None:
        """Start with nothing seen."""
        self.watchers: list[weakref.ref[Any]] = []
        self.seen_object_ids: set[int] = set()
        self.checks = 0
        self.most_held: collections.Counter[str] = collections.Counter()
        self.holders: collections.Counter[str] = collections.Counter()

    def see(self, sprite: object) -> None:
        """Remember a sprite the first time it's sampled.

        An object at a freed sprite's address goes unwatched, which can only miss one, and the
        addresses of living sprites never repeat.
        """
        if id(sprite) not in self.seen_object_ids:
            self.seen_object_ids.add(id(sprite))
            self.watchers.append(weakref.ref(sprite))

    def check(self) -> None:
        """Collect garbage, then count what was removed from every group and still lives."""
        self.checks += 1
        gc.collect()
        living = [watcher() for watcher in self.watchers]
        held = [sprite for sprite in living if sprite is not None and not sprite.alive()]
        counts = collections.Counter(type(sprite).__name__ for sprite in held)
        for name, count in counts.items():
            self.most_held[name] = max(self.most_held[name], count)
        for sprite in held[:HOLDERS_SHOWN_PER_CHECK]:
            for referrer in gc.get_referrers(sprite):
                if referrer is not living and referrer is not held:
                    holder = f'{type(referrer).__module__}.{type(referrer).__qualname__}'
                    self.holders[f'{type(sprite).__name__} held by {holder}'] += 1

    def report(self) -> dict[str, Any]:
        """Say what was found.

        Returns:
            JSON-ready counts.

        """
        return {
            'sprites_seen': len(self.watchers),
            'checks': self.checks,
            'most_held': dict(self.most_held),
            'holders': dict(self.holders),
        }


def main() -> None:
    """Replay a recording under the watch, and print the report."""
    console_script, recording = sys.argv[1:3]
    watch = RemovedSpriteWatch()
    real_id_for = tracing.StableSpriteIds.id_for
    samples = [0]

    def watching_id_for(self: tracing.StableSpriteIds, sprite: object) -> str:
        watch.see(sprite)
        samples[0] += 1
        if samples[0] % SPRITE_SAMPLES_BETWEEN_CHECKS == 0:
            watch.check()
        return real_id_for(self, sprite)

    tracing.StableSpriteIds.id_for = watching_id_for  # ty: ignore[invalid-assignment]
    sys.argv = [console_script, '--replay-trace', recording, '--headless', '--log-level', 'error']
    with contextlib.suppress(SystemExit):
        game_entry_point(console_script=console_script).load()()
    sys.stdout.write(json.dumps(watch.report()) + '\n')


if __name__ == '__main__':
    main()
