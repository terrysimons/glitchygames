"""Mixes: several instrument parts compiled into one sound, optionally folded into an exact loop.

A game's score is several instruments playing together. Played as separate sounds, each takes a
mixer channel and its own buffer, and a loop restarted from game frames lands up to a frame late.
A ``Mix`` is one sound instead (``audio.sound(Mix(...))``): its parts are rendered and added at
their volumes, and the result is cached as every sound is (``SoundLibrary``: the process's
memory, then the disk layer, else compiled and written), so the first request builds it and every
later request, in this launch or a later one, gets the built copy.

With ``loop_seconds`` the mix is exactly that long, so ``play(loop=True)`` repeats it in time,
sample for sample: a melody's own render drops a trailing rest and adds its release tail, so the
frames past the loop's end (the tails) are added onto its start, as they would ring into the next
pass, and a rest at the end is kept as silence.

``Mix`` and ``MixPart`` are what a game writes; ``MixRecipe`` is the library's resolved form (each
part's ``SoundSpec`` at the mixer's rate and tuning), the one thing ``compile_sound`` renders.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Final

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from glitchygames.audio.instrument import (
    Instrument,
)
from glitchygames.audio.render import render_sound, rendered_frame_count
from glitchygames.audio.spec import (
    SoundSpec,
)

if TYPE_CHECKING:
    from glitchygames.audio.synth import FloatArray

# A volume's range, as every play's
SILENT: Final[float] = 0.0
FULL_VOLUME: Final[float] = 1.0


class MixPart(BaseModel):
    """One instrument playing one melody in a mix, at a volume."""

    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    instrument: Instrument
    notes: str
    volume: float = Field(default=FULL_VOLUME, ge=SILENT, le=FULL_VOLUME)


class Mix(BaseModel):
    """Parts started together and compiled into one sound; a loop if ``loop_seconds`` is given.

    Attributes:
        name: The sound's name (each part's seed derives from it).
        parts: The parts, at least one.
        loop_seconds: The loop's exact length, or None for a sound as long as its longest part.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str = Field(min_length=1)
    parts: tuple[MixPart, ...] = Field(min_length=1)
    loop_seconds: float | None = Field(default=None, gt=0.0)


class MixedPart(BaseModel):
    """A part as the library resolved it: its spec and its volume."""

    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    spec: SoundSpec
    volume: float


class MixRecipe(BaseModel):
    """A mix resolved at one rate: what a ``Sound`` holds and ``compile_sound`` renders."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    parts: tuple[MixedPart, ...]
    loop_seconds: float | None
    sample_rate: int

    @property
    def loop_frame_count(self) -> int | None:
        """The loop's frames at this rate, or None for a mix that does not loop."""
        if self.loop_seconds is None:
            return None
        return round(self.loop_seconds * self.sample_rate)

    def frame_count(self) -> int:
        """The frames the render gives, known without rendering (cache ``none``'s length).

        Returns:
            The loop's frames, or the longest part's.
        """
        loop_frames = self.loop_frame_count
        if loop_frames is not None:
            return loop_frames
        return max(rendered_frame_count(part.spec) for part in self.parts)

    def render(self) -> FloatArray:
        """Render every part, add them at their volumes, and fold a loop's overhang onto its start.

        Returns:
            Mono float64 samples, unclipped (the caller clips, and takes the peak from these).
        """
        rendered = [(render_sound(part.spec).samples, part.volume) for part in self.parts]
        mixed = np.zeros(max(len(samples) for samples, _volume in rendered))
        for samples, volume in rendered:
            mixed[: len(samples)] += volume * samples
        loop_frames = self.loop_frame_count
        if loop_frames is None:
            return mixed
        folded = np.zeros(loop_frames)
        for start in range(0, len(mixed), loop_frames):
            overhang = mixed[start : start + loop_frames]
            folded[: len(overhang)] += overhang
        return folded

    def at_rate(self, sample_rate: int) -> MixRecipe:
        """Return the same mix at another rate (an offline render's).

        Returns:
            The recipe, every part's spec rebuilt at the rate.
        """
        if sample_rate == self.sample_rate:
            return self
        return MixRecipe(
            parts=tuple(
                MixedPart(spec=replace(part.spec, sample_rate=sample_rate), volume=part.volume)
                for part in self.parts
            ),
            loop_seconds=self.loop_seconds,
            sample_rate=sample_rate,
        )
