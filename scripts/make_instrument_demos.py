"""Render every catalog instrument across its range to WAV files, for listening.

Run from the repository root: ``uv run python -m scripts.make_instrument_demos [OUTPUT_DIRECTORY]
[--only TEXT]``. Each pitched instrument climbs its range (lowest note to highest, in major
thirds and fourths, then the top note held); each unpitched one plays four hits. Files go to
``OUTPUT_DIRECTORY/<family>/<name>.wav`` (default ``build/instruments``, git-ignored), with an
``index.txt`` listing every instrument, its family and its range (written by unfiltered runs).
"""

from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

import numpy as np

from glitchygames.audio import instruments
from glitchygames.audio.instrument import build_spec
from glitchygames.audio.pitch import Note, Tuning
from glitchygames.audio.render import render_sound
from glitchygames.audio.spec import PlaybackDefaults

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


def write_wav(path: Path, samples: np.ndarray) -> None:
    """Write mono float samples as 16-bit PCM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.round(samples * 32767), -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(SAMPLE_RATE)
        file.writeframes(pcm.tobytes())


def main() -> None:
    """Render the demos."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('output', nargs='?', type=Path, default=Path('build') / 'instruments')
    parser.add_argument('--only', default='', help='only instruments whose name contains TEXT')
    arguments = parser.parse_args()
    lines = []
    for entry in instruments.entries():
        if arguments.only not in entry.name:
            continue
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
        samples = render_sound(spec).samples
        write_wav(arguments.output / entry.family.value / f'{entry.name}.wav', samples)
        playing_range = f'{entry.lowest}-{entry.highest}' if entry.pitched else 'unpitched'
        lines.append(f'{entry.family.value:22} {entry.name:36} {playing_range:10} {entry.title}')
    if not arguments.only:  # a filtered run keeps the full index
        (arguments.output / 'index.txt').write_text('\n'.join(lines) + '\n')
    sys.stdout.write(f'{len(lines)} instruments written to {arguments.output}\n')


if __name__ == '__main__':
    main()
