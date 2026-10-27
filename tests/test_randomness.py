"""Tests for the engine's random number streams (glitchygames/randomness.py).

One master seed per run; every subsystem draws from its own named stream, seeded from
(master seed, name) through a stable hash, so a seed reproduces a run and a draw in one
subsystem never shifts another's sequence. The guard scan that keeps unseeded randomness out of
the engine and the members is tests/test_unseeded_randomness_guard.py.
"""

from __future__ import annotations

import json
import random

import numpy as np

from glitchygames import randomness
from glitchygames.engine_context import EngineContext
from glitchygames.randomness import (
    NUMPY_STREAM_KIND,
    RANDOM_STREAM_KIND,
    SEED_BITS,
    capture_stream_states,
    engine_random,
    engine_random_seed,
    numpy_stream,
    random_stream,
    reset_streams,
    restore_stream_states,
    seed_engine_random,
    stream_seed,
)

DRAW_COUNT = 20
TEST_SEED = 123
# stream_seed(kind='random', master_seed=123, name='engine'): the blake2b-128 digest of
# b'random\x00123\x00engine' as a big-endian integer. Pinned: Python's hash() is salted per
# process, so a value that matched in every run proves the hash is stable.
PINNED_ENGINE_STREAM_SEED = 182259697978296911412075486029851279510
PINNED_ENGINE_STREAM_FIRST_VALUE = 0.9962194675483362
# The numpy stream seed of master seed 123 and the name 'audio.synth'
PINNED_SYNTH_NUMPY_STREAM_SEED = 138955109165650377915384574469052649923


def _draws(name: str) -> list[float]:
    return [random_stream(name).random() for _ in range(DRAW_COUNT)]


class TestStreams:
    """Named streams: reproducible, independent, lazily created and cached."""

    def test_same_seed_gives_the_same_sequence_per_stream(self):
        """Two resets with seed 123 give every stream the same sequence again."""
        reset_streams(seed=TEST_SEED)
        first_run = (_draws('shake'), _draws('ball.serve'))
        reset_streams(seed=TEST_SEED)

        assert (_draws('shake'), _draws('ball.serve')) == first_run

    def test_different_names_give_different_sequences(self):
        """Two streams of one master seed do not repeat each other."""
        reset_streams(seed=TEST_SEED)

        assert _draws('shake') != _draws('ball.serve')

    def test_drawing_from_one_stream_does_not_shift_another(self):
        """Extra draws from stream A leave stream B's next value unchanged."""
        reset_streams(seed=TEST_SEED)
        undisturbed_value = random_stream('ball.serve').random()
        reset_streams(seed=TEST_SEED)
        for _ in range(DRAW_COUNT):
            random_stream('shake').random()

        assert random_stream('ball.serve').random() == undisturbed_value

    def test_different_seeds_give_different_sequences(self):
        """Master seeds 123 and 124 give a stream different sequences."""
        reset_streams(seed=TEST_SEED)
        first_run = _draws('shake')
        reset_streams(seed=TEST_SEED + 1)

        assert _draws('shake') != first_run

    def test_streams_are_cached_by_name_until_reset(self):
        """The same name returns the same generator; a reset starts new ones."""
        reset_streams(seed=TEST_SEED)
        generator = random_stream('shake')
        numpy_generator = numpy_stream('audio.live')

        assert random_stream('shake') is generator
        assert numpy_stream('audio.live') is numpy_generator
        reset_streams(seed=TEST_SEED)
        assert random_stream('shake') is not generator
        assert numpy_stream('audio.live') is not numpy_generator

    def test_numpy_stream_is_reproducible_and_independent(self):
        """Streams from numpy_stream follow the same rules as random streams."""
        reset_streams(seed=TEST_SEED)
        first_run = numpy_stream('audio.synth').uniform(-1.0, 1.0, DRAW_COUNT)
        other_stream = numpy_stream('audio.live').uniform(-1.0, 1.0, DRAW_COUNT)
        reset_streams(seed=TEST_SEED)

        assert np.array_equal(numpy_stream('audio.synth').uniform(-1.0, 1.0, DRAW_COUNT), first_run)
        assert not np.array_equal(first_run, other_stream)

    def test_engine_random_is_the_engine_stream(self):
        """engine_random() is random_stream('engine')."""
        reset_streams(seed=TEST_SEED)

        assert engine_random() is random_stream('engine')


class TestStableHash:
    """Stream seeds come from a stable hash of (kind, master seed, name), never hash()."""

    def test_known_seed_and_name_give_a_pinned_stream_seed(self):
        """stream_seed is the same in every process (Python's hash() would not be)."""
        assert (
            stream_seed(kind='random', master_seed=TEST_SEED, name='engine')
            == PINNED_ENGINE_STREAM_SEED
        )
        assert (
            stream_seed(kind='numpy', master_seed=TEST_SEED, name='audio.synth')
            == PINNED_SYNTH_NUMPY_STREAM_SEED
        )

    def test_known_seed_and_name_give_a_pinned_first_value(self):
        """The engine stream of seed 123 always starts with the same value."""
        reset_streams(seed=TEST_SEED)

        assert random_stream('engine').random() == PINNED_ENGINE_STREAM_FIRST_VALUE

    def test_random_and_numpy_streams_of_one_name_have_different_seeds(self):
        """The kind is part of the hashed bytes."""
        assert stream_seed(kind='random', master_seed=1, name='x') != stream_seed(
            kind='numpy', master_seed=1, name='x'
        )

    def test_negative_master_seed_is_accepted(self):
        """--random-seed accepts any int, including negative ones."""
        reset_streams(seed=-5)

        assert engine_random_seed() == -5
        assert (
            random_stream('engine').random()
            == random.Random(stream_seed(kind='random', master_seed=-5, name='engine')).random()
        )


class TestMasterSeed:
    """The master seed: given, or drawn once from secrets."""

    def test_seed_engine_random_with_a_seed_resets_the_streams(self):
        """seed_engine_random(seed=n) is reset_streams(seed=n) and returns n."""
        assert seed_engine_random(seed=TEST_SEED) == TEST_SEED
        first_run = _draws('shake')
        reset_streams(seed=TEST_SEED)

        assert _draws('shake') == first_run

    def test_no_seed_draws_one_from_secrets(self, mocker):
        """Without a seed, the seed is secrets.randbits(SEED_BITS) and is remembered."""
        randbits = mocker.patch.object(randomness.secrets, 'randbits', return_value=987654321)

        assert seed_engine_random() == 987654321
        randbits.assert_called_once_with(SEED_BITS)
        assert engine_random_seed() == 987654321

    def test_a_stream_seeds_the_master_seed_on_first_use(self, mocker):
        """A draw before the engine seeded gets a secrets-seeded stream, not an error."""
        mocker.patch.object(randomness.secrets, 'randbits', return_value=42)

        generator = random_stream('shake')

        assert generator is random_stream('shake')
        assert engine_random_seed() == 42


class TestStreamStates:
    """capture_stream_states/restore_stream_states save and restore every stream exactly."""

    def test_restore_reproduces_the_next_draws(self):
        """After a restore, every stream (and a stream not yet created) draws as it would have."""
        reset_streams(seed=TEST_SEED)
        random_stream('shake').random()
        numpy_stream('audio.live').random()
        states = capture_stream_states()
        expected = (
            random_stream('shake').random(),
            numpy_stream('audio.live').random(),
            random_stream('new').random(),
        )
        reset_streams(seed=999)
        restore_stream_states(states=states)

        assert engine_random_seed() == TEST_SEED
        assert (
            random_stream('shake').random(),
            numpy_stream('audio.live').random(),
            random_stream('new').random(),
        ) == expected

    def test_restore_drops_streams_created_after_the_capture(self):
        """A stream created after the capture is recreated from the seed, as at capture time."""
        reset_streams(seed=TEST_SEED)
        states = capture_stream_states()
        first_draws = _draws('late')
        restore_stream_states(states=states)

        assert _draws('late') == first_draws

    def test_a_held_stream_object_is_restored_in_place(self):
        """Code holding a stream (a running shake's random source) sees the restored state."""
        reset_streams(seed=TEST_SEED)
        held_random = random_stream('shake')
        held_numpy = numpy_stream('audio.live')
        states = capture_stream_states()
        expected = (held_random.random(), held_numpy.random())
        held_random.random()
        held_numpy.random()
        restore_stream_states(states=states)

        assert random_stream('shake') is held_random
        assert numpy_stream('audio.live') is held_numpy
        assert (held_random.random(), held_numpy.random()) == expected

    def test_a_held_stream_the_capture_lacks_is_reseeded_in_place(self):
        """A stream made after the capture starts over from its seed, in the same object."""
        reset_streams(seed=TEST_SEED)
        states = capture_stream_states()
        held_random = random_stream('late')
        held_numpy = numpy_stream('late.numpy')
        expected = (held_random.random(), held_numpy.random())
        restore_stream_states(states=states)

        assert random_stream('late') is held_random
        assert numpy_stream('late.numpy') is held_numpy
        assert (held_random.random(), held_numpy.random()) == expected

    def test_a_capture_taken_before_any_seeding_drops_later_streams(self, mocker):
        """Restoring a seedless capture drops later streams; they are made anew on first use.

        Nothing has seeded the run yet (the fresh_random_streams fixture), so the capture holds
        no master seed. Streams made after it cannot be reseeded, so the restore drops them from
        the registry: the next lookup makes a new stream from the master seed drawn then.
        """
        states = capture_stream_states()
        reset_streams(seed=TEST_SEED)
        held_random = random_stream('late')
        held_numpy = numpy_stream('late.numpy')
        restore_stream_states(states=states)
        mocker.patch('glitchygames.randomness.secrets.randbits', return_value=TEST_SEED + 1)

        late_random = random_stream('late')
        late_numpy = numpy_stream('late.numpy')

        assert late_random is not held_random
        assert late_numpy is not held_numpy
        assert engine_random_seed() == TEST_SEED + 1
        reset_streams(seed=TEST_SEED + 1)
        assert late_random.random() == random_stream('late').random()
        assert late_numpy.random() == numpy_stream('late.numpy').random()

    def test_states_are_json_safe(self):
        """The capture reads back from JSON exactly (lists, not tuples)."""
        reset_streams(seed=TEST_SEED)
        random_stream('shake').random()
        numpy_stream('audio.live').random()
        states = capture_stream_states()

        assert json.loads(json.dumps(states)) == states

    def test_restored_states_survive_a_json_round_trip(self):
        """States read back from JSON (a recording's) restore the same draws."""
        reset_streams(seed=TEST_SEED)
        random_stream('shake').random()
        numpy_stream('audio.live').random()
        states = json.loads(json.dumps(capture_stream_states()))
        expected = (random_stream('shake').random(), numpy_stream('audio.live').random())
        restore_stream_states(states=states)

        assert (random_stream('shake').random(), numpy_stream('audio.live').random()) == expected


# Master seeds of the two contexts below, and the streams they draw from
FIRST_CONTEXT_SEED = 5
SECOND_CONTEXT_SEED = 6
CONTEXT_DRAWS_STREAM = 'tests.context_draws'
CONTEXT_NOISE_STREAM = 'tests.context_noise'
CONTEXT_DRAW_COUNT = 3
# The range of the numpy draws below: integers(low=..., high=...)
CONTEXT_NOISE_LOW = 0
CONTEXT_NOISE_HIGH = 1000


def reference_random(*, master_seed: int) -> random.Random:
    """Return the draws stream as a fresh process with this master seed would make it.

    Args:
        master_seed: The master seed.

    Returns:
        A new random.Random.

    """
    return random.Random(
        stream_seed(kind=RANDOM_STREAM_KIND, master_seed=master_seed, name=CONTEXT_DRAWS_STREAM)
    )


def test_each_engine_context_has_its_own_master_seed_and_streams():
    """A seed and its streams in one context are never another's (audit C4)."""
    second = EngineContext(name='second')
    reset_streams(seed=FIRST_CONTEXT_SEED)
    default_stream = random_stream(name=CONTEXT_DRAWS_STREAM)

    with second.active():
        reset_streams(seed=SECOND_CONTEXT_SEED)
        second_stream = random_stream(name=CONTEXT_DRAWS_STREAM)
        assert second_stream is not default_stream
        assert engine_random_seed() == SECOND_CONTEXT_SEED

    assert engine_random_seed() == FIRST_CONTEXT_SEED
    assert random_stream(name=CONTEXT_DRAWS_STREAM) is default_stream


def test_interleaved_draws_in_two_contexts_equal_each_context_drawing_alone():
    """Drawing in turn in two contexts gives each the numbers it would draw on its own."""
    second = EngineContext(name='second')
    reset_streams(seed=FIRST_CONTEXT_SEED)
    with second.active():
        reset_streams(seed=SECOND_CONTEXT_SEED)

    default_draws: list[float] = []
    second_draws: list[float] = []
    default_noise: list[int] = []
    second_noise: list[int] = []
    for _ in range(CONTEXT_DRAW_COUNT):
        default_draws.append(random_stream(name=CONTEXT_DRAWS_STREAM).random())
        default_noise.append(
            int(
                numpy_stream(name=CONTEXT_NOISE_STREAM).integers(
                    low=CONTEXT_NOISE_LOW, high=CONTEXT_NOISE_HIGH
                )
            )
        )
        with second.active():
            second_draws.append(random_stream(name=CONTEXT_DRAWS_STREAM).random())
            second_noise.append(
                int(
                    numpy_stream(name=CONTEXT_NOISE_STREAM).integers(
                        low=CONTEXT_NOISE_LOW, high=CONTEXT_NOISE_HIGH
                    )
                )
            )

    default_reference = reference_random(master_seed=FIRST_CONTEXT_SEED)
    second_reference = reference_random(master_seed=SECOND_CONTEXT_SEED)
    assert default_draws == [default_reference.random() for _ in range(CONTEXT_DRAW_COUNT)]
    assert second_draws == [second_reference.random() for _ in range(CONTEXT_DRAW_COUNT)]
    for master_seed, noise in (
        (FIRST_CONTEXT_SEED, default_noise),
        (SECOND_CONTEXT_SEED, second_noise),
    ):
        noise_reference = np.random.default_rng(
            stream_seed(kind=NUMPY_STREAM_KIND, master_seed=master_seed, name=CONTEXT_NOISE_STREAM)
        )
        assert noise == [
            int(noise_reference.integers(low=CONTEXT_NOISE_LOW, high=CONTEXT_NOISE_HIGH))
            for _ in range(CONTEXT_DRAW_COUNT)
        ]


def test_restoring_stream_states_in_one_context_never_touches_another_contexts_streams():
    """Review Focus 5: a restore works in place, on the current context's streams only."""
    second = EngineContext(name='second')
    reset_streams(seed=FIRST_CONTEXT_SEED)
    default_stream = random_stream(name=CONTEXT_DRAWS_STREAM)
    default_stream.random()
    default_state_before = default_stream.getstate()
    captured = capture_stream_states()

    with second.active():
        restore_stream_states(states=captured)
        second_stream = random_stream(name=CONTEXT_DRAWS_STREAM)
        assert second_stream is not default_stream
        assert second_stream.getstate() == default_state_before
        second_stream.random()
        restore_stream_states(states=captured)
        assert random_stream(name=CONTEXT_DRAWS_STREAM) is second_stream
        assert engine_random_seed() == FIRST_CONTEXT_SEED

    assert random_stream(name=CONTEXT_DRAWS_STREAM) is default_stream
    assert default_stream.getstate() == default_state_before
