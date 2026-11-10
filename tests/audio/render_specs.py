"""Spec builders for the renderer's tests: each names only what its test cares about."""

import dataclasses

from glitchygames.audio.instrument import Instrument, Noise, Source, build_spec
from glitchygames.audio.pitch import Hz, Tuning
from glitchygames.audio.spec import EnvelopeSpec, PlaybackDefaults

SAMPLE_RATE = 44100
# Full level for the whole note, no ramps: the note's edges are exactly where the spec says
HELD_ENVELOPE = EnvelopeSpec(attack=0.0, decay=0.0, sustain=1.0, release=0.0, curve='linear')


def spec_for(  # ruff: ignore[too-many-arguments] - a test helper over build_spec's keywords
    instrument,
    *,
    name='render-test',
    pitch=None,
    notes=None,
    chord=None,
    length=None,
    transpose=0.0,
):
    """Build a spec at 44100 Hz in the default tuning.

    Returns:
        The spec.
    """
    return build_spec(
        instrument,
        name=name,
        pitch=pitch,
        notes=notes,
        chord=chord,
        length=length,
        transpose=transpose,
        tuning=Tuning(),
        sample_rate=SAMPLE_RATE,
        playback_defaults=PlaybackDefaults(),
    )


def with_source_levels(spec, level):
    """The spec with every source at ``level``.

    ``Source`` keeps a layer's level within 0-1, but a sound's layers can still sum past full
    scale; setting the level on the spec models that loudness in one layer.

    Returns:
        The changed spec.
    """
    sources = tuple(dataclasses.replace(source, level=level) for source in spec.sources)
    return dataclasses.replace(spec, sources=sources)


def single_note_spec(  # ruff: ignore[too-many-arguments] - a test helper; each keyword is a knob
    *,
    wave,
    hz,
    length=0.25,
    sustain=1.0,
    envelope=None,
    hard_edges=False,
    level=None,
    drive=0.0,
    filter=None,  # ruff: ignore[builtin-argument-shadowing] - Instrument's keyword
    normalize=False,
    name='render-test',
):
    """One note of one wave.

    Without an envelope the note is held at ``sustain`` from its first frame to its last.

    Returns:
        The spec.
    """
    instrument = Instrument(
        wave=wave,
        envelope=envelope or dataclasses.replace(HELD_ENVELOPE, sustain=sustain),
        hard_edges=hard_edges,
        drive=drive,
        filter=filter,
        normalize=normalize,
    )
    spec = spec_for(instrument, name=name, pitch=Hz(hz), length=length)
    return spec if level is None else with_source_levels(spec, level)


def notes_spec(text, *, hard_edges=False, wave='square', envelope=None):
    """A melody on one wave.

    The default envelope decays to silence within each note, so every onset follows silence.

    Returns:
        The spec.
    """
    instrument = Instrument(
        wave=wave,
        envelope=envelope or EnvelopeSpec(attack=0.0, decay=0.02, sustain=0.0, release=0.0),
        hard_edges=hard_edges,
    )
    return spec_for(instrument, notes=text)


def layered_spec(*, hz, length=1.0):
    """One sine source per frequency, each at its own fixed pitch.

    Returns:
        The spec.
    """
    sources = {
        f'layer_{index}': Source('sine', level=1.0 / len(hz), pitch=Hz(frequency))
        for index, frequency in enumerate(hz)
    }
    instrument = Instrument(sources=sources, envelope=HELD_ENVELOPE)
    return spec_for(instrument, pitch=Hz(hz[0]), length=length)


def noise_spec(  # ruff: ignore[too-many-arguments] - a test helper; each keyword is a knob
    *,
    kind,
    bits=15,
    taps=(14, 13),
    rate_hz=None,
    seed=None,
    length=0.25,
    pitch=None,
    name='noise-test',
):
    """One noise layer held for ``length`` seconds.

    ``rate_hz`` is set on the spec: the public ``Noise(rate=...)`` is a pitch, so it stops at
    Nyquist, but the clock may run up to one step per sample.

    Returns:
        The spec.
    """
    instrument = Instrument(
        noise=Noise(kind, bits=bits, taps=taps, seed=seed),
        envelope=HELD_ENVELOPE,
        hard_edges=True,
    )
    spec = spec_for(
        instrument, name=name, pitch=None if pitch is None else Hz(pitch), length=length
    )
    if rate_hz is None:
        return spec
    (source,) = spec.sources
    noise = dataclasses.replace(source.noise, rate_hz=rate_hz)
    return dataclasses.replace(spec, sources=(dataclasses.replace(source, noise=noise),))
