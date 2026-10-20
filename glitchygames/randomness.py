"""The engine's random numbers: named streams seeded from one master seed per run.

``GameEngine`` sets the master seed at startup with ``seed_engine_random()``: from
``--random-seed <int>`` when given, otherwise from ``secrets.randbits(SEED_BITS)``. The seed is
kept (``engine_random_seed()``, ``GameEngine.random_seed``) and written to the header of a
``--record-trace`` recording.

Every subsystem draws from its own stream: ``random_stream(name)`` (a ``random.Random``) or
``numpy_stream(name)`` (a ``numpy.random.Generator``). A stream is created on first use and
cached by name; its seed is ``stream_seed(kind=..., master_seed=..., name=...)``, a BLAKE2b
hash of the stream kind, the master seed and the name, so it is the same in every process
(Python's ``hash()`` is salted per process and is never used). Because each stream has its own
seed, adding a draw in one subsystem never shifts another subsystem's numbers.

``reset_streams(seed=...)`` sets a new master seed and drops every cached stream (tests,
replay); code must therefore look a stream up when it draws (or when the thing that draws is
created), not keep one from import time. ``engine_random()`` is ``random_stream('engine')``.

``capture_stream_states()``/``restore_stream_states(states=...)`` save and restore every stream
exactly (in-game playback, plans/2026-10-19-gameplay-replay-playback.md): the master seed and
each created stream's state, JSON-safe, so a scene rebuilt from its start
(glitchygames/scene_start.py) draws the numbers it drew when it began. A restore drops
the streams the capture did not hold; they are created from the seed on first use, exactly as
they would have been at capture time. Like ``reset_streams``, a restore replaces the stream
objects, so code that kept a stream draws from a stale one.

Streams in use: ``'shake'`` (glitchygames/effects/shake.py), ``'ball.serve'``
(glitchygames/game_objects/ball.py), ``'paddleslap.spawn'`` and ``'paddleslap.colors'``
(glitchygames/examples/paddleslap.py), ``'audio.controller_noise'``
(glitchygames/audio/controller_audio.py), and the numpy streams ``'audio.live'`` and
``'audio.synth'`` (glitchygames/audio/live.py, synth.py). ``glitchygames/audio/recipes.py``
seeds its noise with the constant ``RECIPE_NOISE_SEED`` so a recipe sounds the same every time;
that is deterministic and needs no stream.

Never use ``secrets``, ``random.SystemRandom``, the ``random`` module's global functions,
``random.Random()`` without a seed or ``np.random.default_rng()`` without a seed in the
package: ``tests/test_randomness.py`` scans for them. This module is the one exception (it
draws the master seed when none is given).
"""

from __future__ import annotations

import dataclasses
import hashlib
import random
import secrets
from typing import Any

import numpy as np

# Bits drawn from secrets when no seed is given
SEED_BITS = 64
# Digest size of the stream seed hash: a 128-bit stream seed
STREAM_SEED_DIGEST_BYTES = 16
# Stream kinds, part of the hashed bytes so a random and a numpy stream of one name differ
RANDOM_STREAM_KIND = 'random'
NUMPY_STREAM_KIND = 'numpy'
# The stream engine_random() returns
ENGINE_STREAM_NAME = 'engine'
# capture_stream_states() fields
SEED_STATE_FIELD = 'seed'
RANDOM_STATES_FIELD = 'random'
NUMPY_STATES_FIELD = 'numpy'
# The placeholder seed a restored stream is constructed with; setstate() replaces its state
RESTORED_STREAM_PLACEHOLDER_SEED = 0


@dataclasses.dataclass
class EngineRandomState:
    """The master seed (None until first seeded) and the streams created from it."""

    seed: int | None = None
    random_streams: dict[str, random.Random] = dataclasses.field(default_factory=dict)
    numpy_streams: dict[str, np.random.Generator] = dataclasses.field(default_factory=dict)


_STATE = EngineRandomState()


def stream_seed(*, kind: str, master_seed: int, name: str) -> int:
    """Derive a stream's seed from the master seed and the stream's name.

    The hashed bytes are ``<kind> NUL <master seed in decimal> NUL <name in UTF-8>``.

    Args:
        kind: ``RANDOM_STREAM_KIND`` or ``NUMPY_STREAM_KIND``.
        master_seed: The run's master seed.
        name: The stream's name.

    Returns:
        A 128-bit non-negative integer, the same in every process.

    """
    canonical_bytes = b'\x00'.join((
        kind.encode('utf-8'),
        str(master_seed).encode('ascii'),
        name.encode('utf-8'),
    ))
    digest = hashlib.blake2b(canonical_bytes, digest_size=STREAM_SEED_DIGEST_BYTES).digest()
    return int.from_bytes(digest, byteorder='big')


def reset_streams(*, seed: int) -> None:
    """Set a new master seed and drop every stream created from the old one.

    Args:
        seed: The new master seed.

    """
    _STATE.seed = seed
    _STATE.random_streams.clear()
    _STATE.numpy_streams.clear()


def seed_engine_random(*, seed: int | None = None) -> int:
    """Set the run's master seed (``reset_streams``), drawing one if none is given.

    Args:
        seed: The seed, or None to draw one from ``secrets.randbits(SEED_BITS)``.

    Returns:
        The seed used.

    """
    chosen_seed = secrets.randbits(SEED_BITS) if seed is None else seed
    reset_streams(seed=chosen_seed)
    return chosen_seed


def engine_random_seed() -> int:
    """Return the master seed, drawing one from secrets if nothing has seeded yet.

    Returns:
        The seed.

    """
    seed = _STATE.seed
    if seed is None:
        seed = seed_engine_random()
    return seed


def random_stream(name: str) -> random.Random:
    """Return the named ``random.Random`` stream, creating it on first use.

    Args:
        name: The stream's name (by convention ``<subsystem>`` or ``<game>.<purpose>``).

    Returns:
        The stream; the same object until the next ``reset_streams``.

    """
    generator = _STATE.random_streams.get(name)
    if generator is None:
        generator = random.Random(
            stream_seed(kind=RANDOM_STREAM_KIND, master_seed=engine_random_seed(), name=name)
        )
        _STATE.random_streams[name] = generator
    return generator


def numpy_stream(name: str) -> np.random.Generator:
    """Return the named ``numpy.random.Generator`` stream, creating it on first use.

    Args:
        name: The stream's name.

    Returns:
        The stream; the same object until the next ``reset_streams``.

    """
    generator = _STATE.numpy_streams.get(name)
    if generator is None:
        generator = np.random.default_rng(
            stream_seed(kind=NUMPY_STREAM_KIND, master_seed=engine_random_seed(), name=name)
        )
        _STATE.numpy_streams[name] = generator
    return generator


def engine_random() -> random.Random:
    """Return the engine's general-purpose stream, ``random_stream('engine')``.

    Returns:
        The stream.

    """
    return random_stream(ENGINE_STREAM_NAME)


def capture_stream_states() -> dict[str, Any]:
    """Return the master seed and every created stream's state, JSON-safe.

    ``{"seed": <master seed or None>, "random": {name: [version, [internal state ints],
    gauss_next]}, "numpy": {name: <bit generator state dict>}}``: ``random.Random.getstate()``
    with its tuples as lists, and numpy's ``bit_generator.state`` (PCG64's: plain dicts of ints
    and strings).

    Returns:
        The states, for ``restore_stream_states``.

    """
    random_states: dict[str, Any] = {}
    for name, generator in _STATE.random_streams.items():
        version, internal_state, gauss_next = generator.getstate()
        random_states[name] = [version, list(internal_state), gauss_next]
    return {
        SEED_STATE_FIELD: _STATE.seed,
        RANDOM_STATES_FIELD: random_states,
        NUMPY_STATES_FIELD: {
            # default_rng's PCG64 state is a dict of Python ints and strings, JSON-safe as is
            name: generator.bit_generator.state
            for name, generator in _STATE.numpy_streams.items()
        },
    }


def restore_stream_states(*, states: dict[str, Any]) -> None:
    """Restore the master seed and streams ``capture_stream_states`` returned.

    Streams the capture does not hold are dropped, so they are created from the seed on first
    use, as they would have been at capture time.

    Args:
        states: What ``capture_stream_states()`` returned (or its JSON read back).

    """
    _STATE.seed = states[SEED_STATE_FIELD]
    _STATE.random_streams.clear()
    _STATE.numpy_streams.clear()
    for name, (version, internal_state, gauss_next) in states[RANDOM_STATES_FIELD].items():
        generator = random.Random(RESTORED_STREAM_PLACEHOLDER_SEED)
        generator.setstate((version, tuple(internal_state), gauss_next))
        _STATE.random_streams[name] = generator
    for name, bit_generator_state in states[NUMPY_STATES_FIELD].items():
        numpy_generator = np.random.default_rng(RESTORED_STREAM_PLACEHOLDER_SEED)
        numpy_generator.bit_generator.state = bit_generator_state
        _STATE.numpy_streams[name] = numpy_generator
