"""Every catalog instrument across its range, for listening (the instrument demos).

Moved from ``scripts/make_instrument_demos.py`` (plans/2026-11-14-sound-cache-on-first-use.md,
decision 5). Each pitched instrument climbs its range (lowest note to highest, in major and minor
thirds and fourths, then the top note held); each unpitched one plays four hits.
``glitchygames listening-instruments`` writes them to ``instruments/<family>/<name>.wav`` in the
listening folder, with ``index.txt`` listing every instrument, its family and its range
(glitchygames/audio/listening/files.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from glitchygames.audio import instruments
from glitchygames.audio.instrument import build_spec
from glitchygames.audio.pitch import Note, Tuning
from glitchygames.audio.render import render_sound
from glitchygames.audio.spec import PlaybackDefaults

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

SAMPLE_RATE = 44100
STEP_SECONDS = 0.3
TOP_NOTE_SECONDS = 0.9
CLIMB_STEPS = (4, 3, 5)  # semitones: a major third, a minor third, a fourth, repeating
HITS = (0.25, 0.25, 0.5, 1.0)


def demo_notes(entry: instruments.CatalogEntry) -> list[tuple[Note, float]]:
    """The demo melody: a climb from the lowest note to the highest, or four hits.

    Returns:
        (note, seconds) pairs.
    """
    playing_range = entry.playing_range
    if playing_range is None:
        return [(Note('A4'), seconds) for seconds in HITS]
    lowest, highest = playing_range
    notes: list[tuple[Note, float]] = []
    midi_number = lowest.midi_number
    step = 0
    while midi_number < highest.midi_number:
        notes.append((Note.from_midi_number(midi_number), STEP_SECONDS))
        midi_number += CLIMB_STEPS[step % len(CLIMB_STEPS)]
        step += 1
    notes.append((Note.from_midi_number(highest.midi_number), TOP_NOTE_SECONDS))
    return notes


def instrument_demo(entry: instruments.CatalogEntry) -> npt.NDArray[np.float64]:
    """Render one catalog instrument's demo (``demo_notes``).

    Returns:
        Its samples.
    """
    spec = build_spec(
        instruments.get(entry.name),
        name=entry.name,
        pitch=None,
        notes=demo_notes(entry),
        chord=None,
        length=None,
        transpose=0.0,
        tuning=Tuning(),
        sample_rate=SAMPLE_RATE,
        playback_defaults=PlaybackDefaults(),
    )
    return render_sound(spec).samples


def index_line(entry: instruments.CatalogEntry) -> str:
    """Return an instrument's line in ``index.txt``: family, name, range, title.

    Returns:
        The line.
    """
    playing_range = f'{entry.lowest}-{entry.highest}' if entry.pitched else 'unpitched'
    return f'{entry.family.value:22} {entry.name:36} {playing_range:10} {entry.title}'
