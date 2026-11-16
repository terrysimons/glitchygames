"""A game's declared sounds, compiled at start: in slices during the CRT power-on, then the rest.

plans/2026-11-14-sound-migration.md, decision 6. A game declares every sound it plays
(``Scene.SOUNDS`` on the class it hands ``GameEngine``: effects, instruments or paths to a sound
file's entry; never a short name, which resolves through a scene and none is active yet). The
engine makes a ``StartupSounds`` over the context's audio engine before the power-on and gives
``compile_for`` to it as idle work, so each frame's spare time compiles sounds; ``finish``
compiles whatever is left before the game is built, which is everything where the power-on is
skipped. The game's own requests then find each sound compiled (and, under ``--sound-cache
disk``, a later launch reads them back instead).

Rules:

1. Each declared sound is requested once, in order, through ``audio.sound`` (the one compile
   path: cached, accounted as a setup compile since no scene has run a frame).
2. A slice compiles until its time is used, and always at least one sound, so every slice makes
   progress; a sound that takes longer than a frame delays that one frame.
3. Time is the engine's raw counter (``clock.raw_counter_seconds``, looked up when called), or
   the counter given.
4. No thread: the work runs in the power-on's own frames, so engine contexts and the GIL need no
   care, and the browser's awaited ticks take the same slices.
"""

from __future__ import annotations

import math
from collections import deque
from typing import TYPE_CHECKING

from glitchygames import clock

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glitchygames.audio.effects import Effect
    from glitchygames.audio.engine import AudioEngine
    from glitchygames.audio.instrument import Instrument


class StartupSounds:
    """The declared sounds still to compile (rules in the module docstring)."""

    def __init__(
        self,
        *,
        audio: AudioEngine,
        sources: Sequence[str | Instrument | Effect],
        counter: Callable[[], float] | None = None,
    ) -> None:
        """Hold the sounds to compile.

        Args:
            audio: The context's audio engine.
            sources: The declared sounds (effects, instruments or ``path#name`` strings).
            counter: Reads seconds (rule 3); None is the engine's raw counter.
        """
        self._audio = audio
        self._pending: deque[str | Instrument | Effect] = deque(sources)
        self._counter = counter

    @property
    def remaining(self) -> int:
        """The declared sounds not yet compiled."""
        return len(self._pending)

    def compile_for(self, seconds: float) -> None:
        """Compile declared sounds until ``seconds`` are used, and always at least one (rule 2).

        Args:
            seconds: The time this slice may use; anything not a positive number is none.
        """
        budget = seconds if seconds > 0.0 and not math.isnan(seconds) else 0.0
        started = self._now()
        while self._pending:
            self._audio.sound(self._pending.popleft())
            if self._now() - started >= budget:
                return

    def finish(self) -> None:
        """Compile every declared sound still pending."""
        while self._pending:
            self._audio.sound(self._pending.popleft())

    def _now(self) -> float:
        return clock.raw_counter_seconds() if self._counter is None else self._counter()
