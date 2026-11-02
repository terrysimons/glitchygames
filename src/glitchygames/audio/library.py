"""The sound library: one-call ``sound()``, the cache modes and compile accounting.

The first request for a sound compiles it, equal requests return the same ``Sound``, and getting a
sound never plays it (feature spec 3.1, impl spec 6.2 and 6.4). With cache ``none`` a ``Sound``
holds only what identifies it, and every play compiles it anew (``compile_for_play``), which
forces mid-frame rendering for benchmarks. The pieces of work are timed by the library's
``AudioAccountant`` (impl spec 11.0).
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
import sysconfig
import wave
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

import numpy as np
import numpy.typing as npt
import pygame

from glitchygames import clock
from glitchygames.audio.assets import (
    INSTRUMENT_SEPARATOR,
    RECORDED_SOUND_SUFFIXES,
    SOUND_FILE_SUFFIX,
    ShortNameIndex,
    SoundEntry,
    SoundFile,
    is_path_reference,
    load_sound_file,
    require_recorded_file,
)
from glitchygames.audio.exceptions import AudioUnavailableError, SoundAssetError, SoundRenderError
from glitchygames.audio.instrument import Instrument, build_spec
from glitchygames.audio.render import render_sound
from glitchygames.audio.spec import (
    AUDIO_RENDER_VERSION,
    PlaybackDefaults,
    SoundSpec,
    identity_key,
)
from glitchygames.audio.synth import (
    PCM16_SCALE,
    SIGNED_16_BIT_FORMAT,
    FloatArray,
    mixer_sample_rate,
    to_pcm16,
)

if TYPE_CHECKING:
    from glitchygames.audio.accounting import AudioAccountant
    from glitchygames.audio.pitch import PitchLike, Tuning
    from glitchygames.audio.recipes import SoundRecipe
    from glitchygames.audio.waves import WaveRegistry

log: logging.Logger = logging.getLogger('game.audio.library')

Int16Array = npt.NDArray[np.int16]
DEFAULT_MEMORY_LIMIT_BYTES: Final[int] = 256 * 1024 * 1024
GENERATED_NAME_PREFIX: Final[str] = 'instrument'
GENERATED_NAME_DIGITS: Final[int] = 8
IDENTITY_KEY_HEX_DIGITS: Final[int] = 32  # 128 bits, as spec.identity_key
STEREO_CHANNELS: Final[int] = 2
WAVE_SAMPLE_WIDTH_BYTES: Final[int] = 2  # 16-bit PCM
DISK_CACHE_MESSAGE: Final[str] = 'the disk cache arrives in M3'


class CacheMode(enum.StrEnum):
    """How compiled audio is kept (feature spec 9.3)."""

    NONE = 'none'
    RAM = 'ram'
    DISK = 'disk'


@dataclass(frozen=True, slots=True)
class CacheStatistics:
    """What the cache has done so far.

    Attributes:
        hits: Requests answered by a sound that was already compiled.
        misses: Requests that needed a compile (a new sound, or one evicted from memory).
        compiles: Compiles and decodes run, including every play under cache ``none``.
        bytes_held: The int16 bytes of the compiled sounds held in memory.
    """

    hits: int
    misses: int
    compiles: int
    bytes_held: int


@dataclass(frozen=True, slots=True)
class SoundRequest:
    """One set of ``sound()`` arguments, for ``SoundLibrary.warm``.

    Attributes:
        source: A short name, a path, or an ``Instrument``.
        scene_sound_directory: The scene's sound directory, or None.
        package_root: The game package's directory, or None.
        pitch: A pitch, or None.
        notes: A melody, or None.
        chord: Pitches played together, or None.
        length: Seconds, or None.
        transpose: Semitones.
        parameters: Live parameters (M2), or None.
    """

    source: str | Instrument
    scene_sound_directory: Path | None
    package_root: Path | None = None
    pitch: PitchLike | None = None
    notes: str | Sequence[tuple[PitchLike, float]] | None = None
    chord: Sequence[PitchLike] | None = None
    length: float | None = None
    transpose: float = 0.0
    parameters: Mapping[str, float] | None = None


class Sound:
    """A sound the library compiled (or, under cache ``none``, will compile at each play).

    Exactly one of ``spec`` (a version 1 sound or an instrument), ``legacy_recipe`` (version 0) and
    ``recorded_file`` says how it is compiled. ``length`` and ``peak`` are 0.0 until the sound is
    compiled (``is_compiled``); a sound the memory limit dropped is compiled again, in place, by
    its next request.

    Attributes:
        name: The short name, the path stem, or a generated ``instrument-<digest>`` name.
        length: Seconds, including the release tail.
        peak: The loudest sample's magnitude before clipping.
        is_live: Whether this is a live (M2) sound.
        identity_key: The cache key.
        sample_rate: The rate of the samples (the mixer's, at request time).
        playback_defaults: The sound file's playback defaults.
        spec: The spec of a version 1 sound, or None.
        legacy_recipe: The version 0 recipe, or None.
        recorded_file: The WAV/OGG path of a recorded sound, or None.
        samples_float: Mono float64 samples, or None until compiled.
        samples_int16: The same as signed 16-bit PCM, or None until compiled.
    """

    def __init__(  # ruff: ignore[too-many-arguments] - one construction site
        self,
        *,
        name: str,
        identity_key: str,
        sample_rate: int,
        playback_defaults: PlaybackDefaults,
        spec: SoundSpec | None = None,
        legacy_recipe: SoundRecipe | None = None,
        recorded_file: Path | None = None,
    ) -> None:
        """Make an uncompiled sound.

        Args:
            name: The sound's name.
            identity_key: The cache key.
            sample_rate: The rate to compile at.
            playback_defaults: The default playback settings.
            spec: The spec of a version 1 sound.
            legacy_recipe: The version 0 recipe.
            recorded_file: A recorded sound's file.
        """
        self.name = name
        self.identity_key = identity_key
        self.sample_rate = sample_rate
        self.playback_defaults = playback_defaults
        self.spec = spec
        self.legacy_recipe = legacy_recipe
        self.recorded_file = recorded_file
        self.is_live = spec.live if spec is not None else False
        self.length = 0.0
        self.peak = 0.0
        self.samples_float: FloatArray | None = None
        self.samples_int16: Int16Array | None = None
        self._mixer_sound: pygame.mixer.Sound | None = None
        self._mixer_settings: tuple[int, int, int] | None = None

    @property
    def is_compiled(self) -> bool:
        """Whether the sound holds its samples."""
        return self.samples_int16 is not None

    def fresh_copy(self) -> Sound:
        """Make an uncompiled sound that compiles the same way (cache ``none``, each play).

        Returns:
            The new sound.
        """
        return Sound(
            name=self.name,
            identity_key=self.identity_key,
            sample_rate=self.sample_rate,
            playback_defaults=self.playback_defaults,
            spec=self.spec,
            legacy_recipe=self.legacy_recipe,
            recorded_file=self.recorded_file,
        )

    def install(
        self,
        *,
        samples_float: FloatArray,
        samples_int16: Int16Array,
        peak: float,
        sample_rate: int,
        mixer_sound: pygame.mixer.Sound | None = None,
    ) -> None:
        """Hold the compiled samples.

        Args:
            samples_float: Mono float64 samples.
            samples_int16: The same as signed 16-bit PCM.
            peak: The loudest magnitude before clipping.
            sample_rate: The rate of the samples.
            mixer_sound: A pygame sound already made from them (a recorded file's), or None.
        """
        self.samples_float = samples_float
        self.samples_int16 = samples_int16
        self.peak = peak
        self.sample_rate = sample_rate
        self.length = len(samples_int16) / sample_rate
        self._mixer_sound = mixer_sound
        self._mixer_settings = pygame.mixer.get_init() if mixer_sound is not None else None

    def release(self) -> None:
        """Drop the samples and the pygame sound (the memory limit's eviction)."""
        self.samples_float = None
        self.samples_int16 = None
        self._mixer_sound = None
        self._mixer_settings = None
        self.length = 0.0
        self.peak = 0.0

    def mixer_sound(self) -> pygame.mixer.Sound | None:
        """The pygame sound for the running mixer, built on first use.

        A sound compiled before the mixer started gets its pygame sound here once there is a
        mixer. If the mixer's rate differs from the sound's, the samples are resampled (linearly)
        so the sound keeps its pitch and length; a two-channel mixer gets the mono samples on both
        channels.

        Returns:
            The sound, or None without a mixer or before the sound is compiled.

        Raises:
            AudioUnavailableError: If the mixer is not signed 16-bit.
        """
        settings = pygame.mixer.get_init()
        if settings is None or self.samples_int16 is None:
            return None
        if self._mixer_sound is not None and self._mixer_settings == settings:
            return self._mixer_sound
        rate, sample_format, channel_count = settings
        if sample_format != SIGNED_16_BIT_FORMAT:
            message = f'mixer format {sample_format} is not signed 16-bit'
            raise AudioUnavailableError(message)
        samples = self.samples_int16
        if rate != self.sample_rate:
            samples = _resample(samples, from_rate=self.sample_rate, to_rate=rate)
        frames = (
            samples
            if channel_count == 1
            else np.repeat(samples[:, np.newaxis], channel_count, axis=1)
        )
        # pygame.sndarray.make_sound has incomplete type stubs for its ndarray parameter
        self._mixer_sound = pygame.sndarray.make_sound(np.ascontiguousarray(frames))  # pyright: ignore[reportUnknownMemberType]
        self._mixer_settings = settings
        return self._mixer_sound


def _resample(samples: Int16Array, *, from_rate: int, to_rate: int) -> Int16Array:
    """Resample by linear interpolation (enough to keep a held sound's pitch on a new mixer).

    Returns:
        The samples at the new rate.
    """
    new_length = round(len(samples) * to_rate / from_rate)
    positions = np.arange(new_length) * (from_rate / to_rate)
    resampled = np.interp(positions, np.arange(len(samples)), samples.astype(np.float64))
    return np.round(resampled).astype(np.int16)


def _freeze(value: object) -> object:
    """Make an identity argument hashable, so it can key the request memo.

    Returns:
        The value with lists, tuples and mappings turned into tuples.
    """
    if isinstance(value, Mapping):
        mapping = {str(key): item for key, item in cast('Mapping[object, object]', value).items()}
        return tuple((key, _freeze(mapping[key])) for key in sorted(mapping))
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in cast('Sequence[object]', value))
    return value


def _names_identity(request: SoundRequest) -> bool:
    """Whether a request gives a pitch, notes, chord, length or transpose.

    Returns:
        True if it gives any.
    """
    given = (request.pitch, request.notes, request.chord, request.length)
    return any(argument is not None for argument in given) or bool(request.transpose)


def _digest(payload: Mapping[str, Any]) -> str:
    """The identity key of a payload that is not a ``SoundSpec`` (a recipe or a recorded file).

    Returns:
        32 hex digits.
    """
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()[:IDENTITY_KEY_HEX_DIGITS]


class SoundLibrary:
    """Resolves, compiles and caches sounds (the engine's ``audio.sound`` lives here).

    Attributes:
        playing_predicate: Says whether a sound is playing, so eviction spares it; the mixer
            (Task 8) sets it. The default says nothing is playing.
    """

    def __init__(
        self,
        *,
        cache: CacheMode,
        accountant: AudioAccountant,
        waves: WaveRegistry,
        tuning_source: Callable[[], Tuning],
        memory_limit_bytes: int = DEFAULT_MEMORY_LIMIT_BYTES,
    ) -> None:
        """Make a library.

        Args:
            cache: The cache mode.
            accountant: Where compile and decode times go.
            waves: The registry the wave tables of loaded sound files are registered in; it must
                be the current context's (``build_spec`` looks waves up there).
            tuning_source: Gives the tuning at each request.
            memory_limit_bytes: The int16 bytes held before the least recently played sounds go.

        Raises:
            ValueError: For cache ``disk``, which arrives in M3.
        """
        if cache is CacheMode.DISK:
            raise ValueError(DISK_CACHE_MESSAGE)
        self._cache = cache
        self._accountant = accountant
        self._waves = waves
        self._tuning_source = tuning_source
        self._memory_limit_bytes = memory_limit_bytes
        self.playing_predicate: Callable[[Sound], bool] = lambda _sound: False
        self._recipes: dict[str, SoundRecipe] = {}
        self._indexes: dict[tuple[Path, Path | None], ShortNameIndex] = {}
        # request -> identity key, so a repeated request is a dictionary hit (impl spec 6.2).
        # A sound file edited after its first request is not re-read: hot reload is M4.
        self._memo: dict[tuple[object, ...], str] = {}
        self._sounds: dict[str, Sound] = {}
        # Compiled sounds, least recently played first
        self._play_order: OrderedDict[str, Sound] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._compiles = 0
        self._bytes_held = 0

    def add_recipes(self, recipes: Iterable[SoundRecipe]) -> None:
        """Add version 0 recipes by name; they are looked up before the sound directory.

        Args:
            recipes: The recipes.
        """
        for recipe in recipes:
            self._recipes[recipe.name] = recipe

    def names(self) -> tuple[str, ...]:
        """The names of the added recipes and of every sound requested so far.

        Returns:
            The names, sorted.
        """
        known = set(self._recipes)
        known.update(sound.name for sound in self._sounds.values())
        return tuple(sorted(known))

    def statistics(self) -> CacheStatistics:
        """What the cache has done so far.

        Returns:
            The counters.
        """
        return CacheStatistics(
            hits=self._hits,
            misses=self._misses,
            compiles=self._compiles,
            bytes_held=self._bytes_held,
        )

    def sound(  # ruff: ignore[too-many-arguments] - impl spec 8
        self,
        source: str | Instrument,
        *,
        scene_sound_directory: Path | None,
        package_root: Path | None = None,
        pitch: PitchLike | None = None,
        notes: str | Sequence[tuple[PitchLike, float]] | None = None,
        chord: Sequence[PitchLike] | None = None,
        length: float | None = None,
        transpose: float = 0.0,
        parameters: Mapping[str, float] | None = None,
    ) -> Sound:
        """Get a sound; the first request for an identity compiles it. Getting never plays.

        Arguments given here replace the sound file entry's own: a ``pitch``, ``notes`` or
        ``chord`` replaces all three of the entry's, ``length`` replaces its length, and
        ``transpose`` is added to its transpose. A recorded or version 0 sound takes none of them.

        Args:
            source: A short name, a path (``'sounds/pickups.toml#coin'``, ``'sounds/slap.wav'``;
                relative to ``package_root``), or an ``Instrument``.
            scene_sound_directory: Where short names are looked up, or None.
            package_root: The game package's directory (paths and file references stay inside it).
            pitch: A pitch.
            notes: A melody.
            chord: Pitches played together.
            length: Seconds per note or chord before release.
            transpose: Semitones to shift notes or a chord.
            parameters: Live parameters; they identify the request but a baked sound ignores them
                (live sounds arrive in M2).

        Returns:
            The sound. Under cache ``none`` it holds no samples until ``compile_for_play``.
        """
        request = SoundRequest(
            source=source,
            scene_sound_directory=scene_sound_directory,
            package_root=package_root,
            pitch=pitch,
            notes=notes,
            chord=chord,
            length=length,
            transpose=transpose,
            parameters=parameters,
        )
        sound, known = self._lookup(request)
        self._ensure_compiled(sound, known=known)
        return sound

    def compile_for_play(self, sound: Sound) -> Sound:
        """The sound to play: the same one under ``ram``, a fresh compile under ``none``.

        Under ``ram`` a sound the memory limit dropped is compiled again, in place, and counted.
        Playing makes a ``ram`` sound the most recently played.

        Args:
            sound: A sound from ``sound()``.

        Returns:
            The compiled sound.
        """
        if self._cache is CacheMode.NONE:
            fresh = sound.fresh_copy()
            self._compile(fresh)
            return fresh
        if not sound.is_compiled:
            self._misses += 1
            self._compile(sound)
            self._hold(sound)
        else:
            self._play_order.move_to_end(sound.identity_key)
        return sound

    def warm(self, requests: Sequence[SoundRequest], *, budget_ms: float | None = None) -> float:
        """Compile as many of the requests as fit in a time budget (for a loading scene).

        At least one request compiles per call. It uses the same compile path as ``sound()``.

        Args:
            requests: The ``sound()`` argument sets to have compiled.
            budget_ms: The milliseconds to spend this call, or None for no limit.

        Returns:
            Progress from 0 to 1: the share of requests that are compiled.
        """
        if not requests:
            return 1.0
        started = clock.raw_counter_ns()
        compiled_this_call = 0
        done = 0
        for request in requests:
            sound, known = self._lookup(request)
            if self._cache is CacheMode.RAM and not sound.is_compiled:
                elapsed_ms = (clock.raw_counter_ns() - started) / 1_000_000
                if budget_ms is not None and compiled_this_call > 0 and elapsed_ms >= budget_ms:
                    continue
                compiled_this_call += 1
            self._ensure_compiled(sound, known=known)
            done += 1
        return done / len(requests)

    def _ensure_compiled(self, sound: Sound, *, known: bool) -> None:
        """Count the request and, under ``ram``, compile the sound unless it is already."""
        if self._cache is CacheMode.NONE:
            if known:
                self._hits += 1
            else:
                self._misses += 1
            return
        if sound.is_compiled:
            self._hits += 1
            return
        self._misses += 1
        self._compile(sound)
        self._hold(sound)

    def _hold(self, sound: Sound) -> None:
        """Keep a compiled sound in memory; over the limit, drop the least recently played."""
        assert sound.samples_int16 is not None
        self._play_order[sound.identity_key] = sound
        self._play_order.move_to_end(sound.identity_key)
        self._bytes_held += sound.samples_int16.nbytes
        if self._bytes_held <= self._memory_limit_bytes:
            return
        for candidate in list(self._play_order.values()):
            # The sound just asked for stays, and so does anything that is playing
            if candidate is sound or self.playing_predicate(candidate):
                continue
            assert candidate.samples_int16 is not None
            self._bytes_held -= candidate.samples_int16.nbytes
            del self._play_order[candidate.identity_key]
            candidate.release()
            if self._bytes_held <= self._memory_limit_bytes:
                break

    def _compile(self, sound: Sound) -> None:
        """Compile a sound into itself, timed and counted."""
        kind = 'decode' if sound.recorded_file is not None else 'compile'
        with self._accountant.measure(kind, sound.name):
            if sound.recorded_file is not None:
                _decode_recorded_file(sound)
            elif sound.spec is not None:
                rendered = render_sound(sound.spec)
                sound.install(
                    samples_float=rendered.samples,
                    samples_int16=to_pcm16(rendered.samples),
                    peak=rendered.peak,
                    sample_rate=sound.sample_rate,
                )
            else:
                assert sound.legacy_recipe is not None
                # Version 0 recipes compile through today's renderer, unchanged (impl spec 10.4)
                samples = sound.legacy_recipe.render(sample_rate=sound.sample_rate)
                sound.install(
                    samples_float=samples,
                    samples_int16=to_pcm16(samples),
                    peak=float(np.max(np.abs(samples))) if len(samples) else 0.0,
                    sample_rate=sound.sample_rate,
                )
        self._compiles += 1

    def _lookup(self, request: SoundRequest) -> tuple[Sound, bool]:
        """Find the sound for a request, making (not compiling) it if it is new.

        Returns:
            The sound, and whether it was known already.
        """
        sample_rate = mixer_sample_rate()
        tuning = self._tuning_source()
        source = request.source
        source_key: object = (
            ('instrument', source)
            if isinstance(source, Instrument)
            else ('name', source, request.scene_sound_directory, request.package_root)
        )
        memo_key = (
            source_key,
            _freeze(request.pitch),
            _freeze(request.notes),
            _freeze(request.chord),
            request.length,
            request.transpose,
            _freeze(request.parameters),
            sample_rate,
            tuning,
        )
        remembered = self._memo.get(memo_key)
        if remembered is not None:
            return self._sounds[remembered], True
        sound = self._build(request, sample_rate=sample_rate, tuning=tuning)
        existing = self._sounds.get(sound.identity_key)
        if existing is not None:
            self._memo[memo_key] = existing.identity_key
            return existing, True
        self._sounds[sound.identity_key] = sound
        self._memo[memo_key] = sound.identity_key
        return sound, False

    def _build(self, request: SoundRequest, *, sample_rate: int, tuning: Tuning) -> Sound:
        """Resolve a request to an uncompiled sound.

        Returns:
            The sound.

        Raises:
            ValueError: When a recorded or version 0 sound is given a pitch, notes, chord, length
                or transpose.
        """
        if isinstance(request.source, Instrument):
            return self._instrument_sound(
                request.source,
                name=None,
                request=request,
                defaults=PlaybackDefaults(),
                sample_rate=sample_rate,
                tuning=tuning,
            )
        entry = self._resolve_entry(request)
        if (entry.legacy_recipe is not None or entry.file is not None) and _names_identity(request):
            message = (
                f'{entry.name!r} is a recorded or version 0 sound: it takes no pitch, notes, '
                f'chord, length or transpose'
            )
            raise ValueError(message)
        if entry.legacy_recipe is not None:
            return Sound(
                name=entry.name,
                identity_key=_digest({
                    'legacy_recipe': entry.legacy_recipe.to_dict(),
                    'name': entry.name,
                    'sample_rate': sample_rate,
                    'render_version': AUDIO_RENDER_VERSION,
                    'numpy_version': np.__version__,
                    'platform': sysconfig.get_platform(),
                }),
                sample_rate=sample_rate,
                playback_defaults=entry.playback_defaults,
                legacy_recipe=entry.legacy_recipe,
            )
        if entry.file is not None:
            path = require_recorded_file(entry)
            status = path.stat()
            return Sound(
                name=entry.name,
                identity_key=_digest({
                    'recorded_file': str(path.resolve()),
                    'modification_time_ns': status.st_mtime_ns,
                    'size': status.st_size,
                    'sample_rate': sample_rate,
                }),
                sample_rate=sample_rate,
                playback_defaults=entry.playback_defaults,
                recorded_file=path,
            )
        assert entry.instrument is not None
        return self._instrument_sound(
            entry.instrument,
            name=entry.name,
            request=request,
            defaults=entry.playback_defaults,
            sample_rate=sample_rate,
            tuning=tuning,
            entry=entry,
        )

    def _instrument_sound(  # ruff: ignore[too-many-arguments] - one construction site
        self,
        instrument: Instrument,
        *,
        name: str | None,
        request: SoundRequest,
        defaults: PlaybackDefaults,
        sample_rate: int,
        tuning: Tuning,
        entry: SoundEntry | None = None,
    ) -> Sound:
        """Build the sound of an instrument (given directly, or named by a sound file entry).

        Returns:
            The uncompiled sound.

        Raises:
            SoundRenderError: For a live instrument, which has no baked audio in M1.
        """
        pitch, notes, chord = request.pitch, request.notes, request.chord
        length, transpose = request.length, request.transpose
        if entry is not None:
            if pitch is None and notes is None and chord is None:
                pitch, notes, chord = entry.pitch, entry.notes, entry.chord
            if length is None:
                length = entry.length
            transpose += entry.transpose

        def spec_named(spec_name: str) -> SoundSpec:
            return build_spec(
                instrument,
                name=spec_name,
                pitch=pitch,
                notes=notes,
                chord=chord,
                length=length,
                transpose=transpose,
                tuning=tuning,
                sample_rate=sample_rate,
                playback_defaults=defaults,
            )

        if name is None:
            # The seed derives from the name, so the generated name must be the same in every
            # process: a digest of the spec built under a fixed name, never a hash() or an id()
            digest = identity_key(spec_named(GENERATED_NAME_PREFIX))
            name = f'{GENERATED_NAME_PREFIX}-{digest[:GENERATED_NAME_DIGITS]}'
        spec = spec_named(name)
        if spec.live:
            message = f'{name!r} is a live sound; live sounds arrive in M2'
            raise SoundRenderError(message)
        return Sound(
            name=name,
            identity_key=identity_key(spec),
            sample_rate=sample_rate,
            playback_defaults=defaults,
            spec=spec,
        )

    def _resolve_entry(self, request: SoundRequest) -> SoundEntry:
        """Find the sound file entry a string names.

        Returns:
            The entry (a recorded file gets one made for it).

        Raises:
            KeyError: For a short name with no sound directory. (Other failures come from the
                helpers: ``SoundAssetError`` for a name in both ``add_recipes`` and the
                directory or a bad path, ``KeyError`` for an unknown name.)
        """
        source = request.source
        assert isinstance(source, str)
        directory = request.scene_sound_directory
        package_root = request.package_root
        if is_path_reference(source):
            return self._path_entry(source, package_root=package_root)
        if source in self._recipes:
            self._refuse_name_in_both(source, directory=directory, package_root=package_root)
            return SoundEntry(name=source, legacy_recipe=self._recipes[source])
        if directory is None:
            message = f'no sound named {source!r}: the scene has no sound directory'
            raise KeyError(message)
        index = self._index_for(directory, package_root=package_root)
        location = index.resolve(source)
        if location.is_recorded_file:
            return SoundEntry(
                name=location.path.stem, file=location.path, source_path=location.path
            )
        return self._entry_in(index.load(location), location.table_name)

    def _refuse_name_in_both(
        self, name: str, *, directory: Path | None, package_root: Path | None
    ) -> None:
        """Refuse a recipe name the sound directory also defines (Ruling R2).

        Raises:
            SoundAssetError: Naming add_recipes and the directory's file.
        """
        if directory is None:
            return
        try:
            location = self._index_for(directory, package_root=package_root).resolve(name)
        except KeyError:
            return
        message = (
            f'the sound name {name!r} is defined in add_recipes and in {location.path}; rename one'
        )
        raise SoundAssetError(message)

    def _index_for(self, directory: Path, *, package_root: Path | None) -> ShortNameIndex:
        key = (directory, package_root)
        if key not in self._indexes:
            self._indexes[key] = ShortNameIndex(directory, package_root=package_root)
        return self._indexes[key]

    def _path_entry(self, source: str, *, package_root: Path | None) -> SoundEntry:
        """The entry a path reference names.

        Returns:
            The entry.

        Raises:
            SoundAssetError: For a TOML path without a sound name, a ``#`` on a recorded file, or
                a file that is neither a sound file nor a WAV/OGG.
        """
        file_part, _, table_name = source.partition(INSTRUMENT_SEPARATOR)
        path = Path(file_part)
        if package_root is not None and not path.is_absolute():
            path = package_root / path
        suffix = path.suffix.lower()
        if suffix == SOUND_FILE_SUFFIX:
            if not table_name:
                message = f'{source!r}: name a sound in the file, as {file_part}#<sound>'
                raise SoundAssetError(message)
            return self._entry_in(load_sound_file(path, package_root=package_root), table_name)
        if suffix in RECORDED_SOUND_SUFFIXES and not table_name:
            return SoundEntry(name=path.stem, file=path, source_path=path)
        message = (
            f'{source!r}: a sound path is a {SOUND_FILE_SUFFIX} sound file followed by '
            f'#<sound>, or a {" or ".join(RECORDED_SOUND_SUFFIXES)} file'
        )
        raise SoundAssetError(message)

    def _entry_in(self, sound_file: SoundFile, table_name: str | None) -> SoundEntry:
        """Register a loaded file's waves and take one of its sounds.

        Returns:
            The entry.

        Raises:
            KeyError: When the file defines no such sound. (Registering its waves can raise
                ``SoundAssetError``.)
        """
        self._register_waves(sound_file)
        assert table_name is not None
        if table_name not in sound_file.sounds:
            known = ', '.join(sound_file.sounds) or 'none'
            message = f'{sound_file.path} has no sound {table_name!r} (it defines: {known})'
            raise KeyError(message)
        return sound_file.sounds[table_name]

    def _register_waves(self, sound_file: SoundFile) -> None:
        """Register a file's ``[waves.*]`` before its instruments' specs are built.

        Registering an equal wave under a name again changes nothing.

        Raises:
            SoundAssetError: When a different wave is registered under the name already.
        """
        for wave_name, file_wave in sound_file.waves.items():
            if wave_name in self._waves:
                if self._waves[wave_name] == file_wave:
                    continue
                message = (
                    f'{sound_file.path}: waves.{wave_name}: a different wave is already '
                    f'registered under this name'
                )
                raise SoundAssetError(message)
            self._waves.register(wave_name, file_wave)


def _decode_recorded_file(sound: Sound) -> None:
    """Load a recorded sound: through the mixer when there is one, else decode a WAV.

    Raises:
        SoundAssetError: When the file cannot be loaded, or cannot be decoded without a mixer.
    """
    path = sound.recorded_file
    assert path is not None
    settings = pygame.mixer.get_init()
    if settings is not None:
        try:
            mixer_sound = pygame.mixer.Sound(str(path))
        except pygame.error as error:
            message = f'{path}: cannot be loaded: {error}'
            raise SoundAssetError(message) from error
        # pygame.sndarray.array has incomplete type stubs
        frames: Int16Array = pygame.sndarray.array(mixer_sound)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        samples = _as_mono(frames)
        sound.install(
            samples_float=samples / PCM16_SCALE,
            samples_int16=samples,
            peak=float(np.max(np.abs(samples))) / PCM16_SCALE if len(samples) else 0.0,
            sample_rate=int(settings[0]),
            mixer_sound=mixer_sound,
        )
        return
    if path.suffix.lower() != '.wav':
        message = (
            f'{path}: a mixer is needed to decode {path.suffix} files; '
            f'only .wav decodes without one'
        )
        raise SoundAssetError(message)
    try:
        with wave.open(str(path), 'rb') as wave_file:
            width = wave_file.getsampwidth()
            channels = wave_file.getnchannels()
            rate = wave_file.getframerate()
            raw = wave_file.readframes(wave_file.getnframes())
    except (wave.Error, EOFError) as error:
        message = f'{path}: cannot be decoded as a WAV file: {error}'
        raise SoundAssetError(message) from error
    if width != WAVE_SAMPLE_WIDTH_BYTES:
        message = f'{path}: only 16-bit WAV files decode without a mixer, got {width * 8}-bit'
        raise SoundAssetError(message)
    # WAV data is little-endian by definition
    interleaved = np.frombuffer(raw, dtype='<i2').reshape(-1, channels)
    samples = _as_mono(interleaved)
    sound.install(
        samples_float=samples / PCM16_SCALE,
        samples_int16=samples,
        peak=float(np.max(np.abs(samples))) / PCM16_SCALE if len(samples) else 0.0,
        sample_rate=rate,
    )


def _as_mono(frames: Int16Array) -> Int16Array:
    """Average a channel axis away.

    Returns:
        One int16 sample per frame.
    """
    if frames.ndim == 1:
        return frames
    if frames.shape[1] == 1:
        return np.ascontiguousarray(frames[:, 0])
    averaged: FloatArray = np.mean(frames, axis=1, dtype=np.float64)
    return np.round(averaged).astype(np.int16)
