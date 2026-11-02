"""The audio engine: one-call sounds, plays and their voices for one engine context (impl spec 8).

``SceneManager.audio`` is the current engine context's ``AudioEngine``, made on first use. It is
the value of a ``ContextSlot`` (``AUDIO_ENGINE_SLOT``), so each context has its own library,
voices and short-name index; ``existing_audio_engine()`` reads it without making one.

- ``sound(...)`` takes what a sound is (the source, pitch, notes, chord, length, transpose and
  parameters) and returns the compiled ``Sound``; getting never plays. Short names are looked up
  in the active scene's ``SOUND_DIRECTORY``, relative to the scene's package directory
  (``replay.tools.identity.game_identity``; the scene module's own directory when that finds
  none), and paths are relative to that directory too (ruling R21). During a scene's
  ``setup()`` the scene being set up is the one asked.
- ``play(...)`` is ``sound(identity...).play(playback...)``; ``beep(...)`` is
  ``sound(Instrument(wave=...), pitch=..., length=...).play(...)``.
- Plays belong to the scene that started them (the scene in setup, else the active scene), or,
  with no scene, to the engine's ``SYSTEM_OWNER`` (the CRT power-on's sounds, Task 11), which no
  scene clean-up stops.

Once per frame the scene manager calls ``begin_frame`` (the frame number for the compile log),
``begin_logic_frame`` (before the active scene's ``dt_tick``: compiles stop counting as setup,
and a setup whose compiles took more than 50 ms is logged once at INFO, naming its slowest
sounds), ``update`` (where ``LiveAudio.update`` runs, with the same arguments: impl spec 4.2)
and ``take_frame_account`` (the frame's audio work for the doors' ``end_frame``, impl spec
11.0); ``begin_scene_setup`` before each scene's ``setup()``.

``update`` takes ``LiveAudio.update``'s arguments, with one rule of its own (ruling R33): the
voices of the active scene, of a running or pending transition and of the system owner play;
those of ``paused_owners`` (a playback scope's) pause and gain no played time, and so do the
previous scene's, but only while the active scene shows it as paused (``active_scene.debug_subject
is previous_scene``: a pause screen's subject is the game it paused). Any other owner's voices,
a scene switched away from directly included, fade out over 50 ms unless they were played with
``persist=True`` (feature spec 7.4). Then each voice gains the frame's served ``dt``. (Live
voices keep pausing behind any previous scene until M2 replaces them.)

``silenced(channel)`` follows ``FrameSilencer``'s stops (impl spec 7.3), and ``close()`` fades
every voice over 50 ms and waits at most 100 ms for the fades (impl spec 10.3).
"""

from __future__ import annotations

import collections
import dataclasses
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast, override

import pygame

from glitchygames import clock
from glitchygames.audio.accounting import AudioAccountant, AudioFrameAccount
from glitchygames.audio.buses import BusTree
from glitchygames.audio.instrument import Instrument
from glitchygames.audio.library import (
    DEFAULT_MEMORY_LIMIT_BYTES,
    CacheMode,
    CacheStatistics,
    Sound,
    SoundLibrary,
)
from glitchygames.audio.pitch import Tuning
from glitchygames.audio.voices import (
    DEFAULT_STOP_FADE_SECONDS,
    ChannelPartition,
    ChannelState,
    VoiceTable,
    reserve_channels,
)
from glitchygames.audio.waves import current_wave_registry
from glitchygames.engine_context import ContextSlot, current_context

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping, Sequence

    from glitchygames.audio.accounting import CompileRecord
    from glitchygames.audio.pitch import PitchLike
    from glitchygames.audio.voices import SoundHandle
    from glitchygames.audio.waves import WaveRegistry
    from glitchygames.scenes import Scene

log: logging.Logger = logging.getLogger('game.audio.engine')

# Impl spec 7.1 and 10.2: the library's channels (--sound-channels) and the unreserved ones left
# for Sound.play() callers (pygame's default count)
DEFAULT_LIBRARY_CHANNELS: Final[int] = 32
LEGACY_CHANNELS: Final[int] = 8
# The live pool a scene manager without a game engine reserves (--live-voice-pool's default)
DEFAULT_LIVE_POOL: Final[int] = 4
BYTES_PER_MEGABYTE: Final[int] = 1024 * 1024
DEFAULT_CACHE_MEMORY_MEGABYTES: Final[int] = DEFAULT_MEMORY_LIMIT_BYTES // BYTES_PER_MEGABYTE
# Feature spec 7.4: a scene's voices fade over 50 ms when it is cleaned up
SCENE_CLEANUP_FADE_SECONDS: Final[float] = DEFAULT_STOP_FADE_SECONDS
# Impl spec 10.3: shutdown fades everything over 50 ms and waits at most 100 ms
SHUTDOWN_FADE_SECONDS: Final[float] = DEFAULT_STOP_FADE_SECONDS
SHUTDOWN_WAIT_SECONDS: Final[float] = 0.1
SHUTDOWN_POLL_SECONDS: Final[float] = 0.005
# Impl spec 6.5: a setup whose compiles take longer than this logs one INFO line
SLOW_SETUP_MILLISECONDS: Final[float] = 50.0
# The window compiles_last_second counts over, in served frame time
COMPILE_RATE_WINDOW_SECONDS: Final[float] = 1.0
NO_MIXER_DEVICE: Final[str] = 'no mixer'
SCHEDULED_PLAY_MESSAGE: Final[str] = 'at_frame scheduling arrives in M2'
POSITIONED_PLAY_MESSAGE: Final[str] = 'positional audio arrives in M4'


class _SystemOwner:
    """The owner of the engine's own voices (one instance: ``SYSTEM_OWNER``)."""

    @override
    def __repr__(self) -> str:
        """Name the owner.

        Returns:
            ``<the audio engine's system owner>``.
        """
        return "<the audio engine's system owner>"


# Voices owned by the engine itself (the CRT power-on's, impl spec 7.3 and 10.1): never a scene's,
# so no scene clean-up stops them
SYSTEM_OWNER: Final[object] = _SystemOwner()


@dataclasses.dataclass(frozen=True, slots=True)
class AudioDiagnostics:
    """What the audio engine has done, for the game (feature spec W8 and 11.1).

    Attributes:
        voices_playing: Library voices playing, paused or waiting for their channel.
        voices_limit: The library's channels.
        compiles: Compiles and decodes so far.
        compile_milliseconds: Their total time.
        setup_compiles: Those run before a scene's first logic frame.
        setup_compile_milliseconds: Their total time.
        gameplay_compiles: Those run inside gameplay frames.
        gameplay_compile_milliseconds: Their total time.
        compiles_in_gameplay: The last 32 gameplay compiles (name, milliseconds and frame).
        stolen_voices: Voices stolen for a new play.
        delayed_plays: Plays that waited a frame for their stolen channel.
        dropped_plays: Plays with no channel and nothing to steal.
        device: The mixer's format and driver, or ``no mixer``.
        cache: The cache's counters.
    """

    voices_playing: int
    voices_limit: int
    compiles: int
    compile_milliseconds: float
    setup_compiles: int
    setup_compile_milliseconds: float
    gameplay_compiles: int
    gameplay_compile_milliseconds: float
    compiles_in_gameplay: tuple[CompileRecord, ...]
    stolen_voices: int
    delayed_plays: int
    dropped_plays: int
    device: str
    cache: CacheStatistics


@dataclasses.dataclass(frozen=True, slots=True)
class AudioDiagnosticsSnapshot:
    """The audio engine as the debug overlay's Audio panel draws it (impl spec 10.5; ruling R3).

    Attributes:
        cache_mode: The cache mode.
        device: The mixer's format and driver, or ``no mixer``.
        voices_live: Live channels sounding on the device.
        voices_library: Library voices playing, paused or waiting.
        voices_legacy: Legacy channels sounding on the device.
        compiles_last_second: Compiles and decodes over the last second of served frame time.
        cache_hit_rate: Hits over requests, or None before any request.
        frame_work_by_kind: The last frame's audio work in seconds, by kind.
        frame_processing_seconds: The last frame's processing time, or None when not given.
        channels: Every channel's group and state.
        bus_levels: Each bus's effective gain.
        muted_buses: The buses muted themselves.
        compile_log: The last eight compiles and decodes.
    """

    cache_mode: CacheMode
    device: str
    voices_live: int
    voices_library: int
    voices_legacy: int
    compiles_last_second: int
    cache_hit_rate: float | None
    frame_work_by_kind: Mapping[str, float]
    frame_processing_seconds: float | None
    channels: tuple[ChannelState, ...]
    bus_levels: Mapping[str, float]
    muted_buses: frozenset[str]
    compile_log: tuple[CompileRecord, ...]


def _no_scene() -> object | None:
    """The default scene source: no scene (every play is the system owner's).

    Returns:
        None.
    """
    return None


def _device_description() -> str:
    """The running mixer's format and driver.

    Returns:
        ``44100 Hz, 16-bit signed, 2 channels, driver dummy``, or ``no mixer``.
    """
    settings = pygame.mixer.get_init()
    if settings is None:
        return NO_MIXER_DEVICE
    rate, sample_format, channel_count = settings
    signedness = 'signed' if sample_format < 0 else 'unsigned'
    return (
        f'{rate} Hz, {abs(sample_format)}-bit {signedness}, {channel_count} channels, '
        f'driver {pygame.mixer.get_driver()}'
    )


def _module_directory(module_name: str) -> Path | None:
    """The directory of a loaded module's file.

    Returns:
        The directory, or None when the module is not loaded or has no file.
    """
    module = sys.modules.get(module_name)
    module_file = None if module is None else getattr(module, '__file__', None)
    return None if module_file is None else Path(module_file).parent


def default_channel_partition() -> ChannelPartition:
    """Partition the mixer as a game engine would by default (4 live, 32 library, 8 legacy).

    For a scene manager without a game engine (tests, tools): ``reserve_channels`` only grows
    the channel table, so an engine's earlier partition loses no channel.

    Returns:
        The partition.
    """
    return reserve_channels(
        live_pool=DEFAULT_LIVE_POOL,
        library_channels=DEFAULT_LIBRARY_CHANNELS,
        legacy_channels=LEGACY_CHANNELS,
    )


class AudioEngine:
    """Sounds, plays, voices and buses for one engine context (impl spec 8).

    Attributes:
        waves: The context's wave registry.
        buses: The bus tree.
        tuning: The tuning pitches resolve with (part of what a sound is).
        sounds: The sound library (``warm``, ``names``, ``statistics``).
        accountant: The audio work accounting (impl spec 11.0).
        cache_mode: The cache mode.
    """

    def __init__(
        self,
        *,
        partition: ChannelPartition,
        cache: CacheMode = CacheMode.RAM,
        memory_limit_bytes: int = DEFAULT_MEMORY_LIMIT_BYTES,
        scene_source: Callable[[], object | None] = _no_scene,
        frame_number: int | None = None,
    ) -> None:
        """Make an engine over a channel partition.

        Args:
            partition: The mixer's channel partition (``reserve_channels``).
            cache: The cache mode (``disk`` arrives in M3: ValueError).
            memory_limit_bytes: The bytes compiled sounds may hold under ``ram``.
            scene_source: Gives the scene plays belong to and short names resolve in (the scene
                in setup, else the active scene), or None.
            frame_number: The frame being run, for the compile log.
        """
        self.waves: WaveRegistry = current_wave_registry()
        self.buses = BusTree()
        self.tuning = Tuning()
        self.cache_mode = cache
        self.accountant = AudioAccountant()
        self.accountant.frame_number = frame_number
        self._partition = partition
        self._scene_source = scene_source
        self._voices = VoiceTable(
            partition=partition, buses=self.buses, compile_for_play=self._compile_for_play
        )
        self.sounds = SoundLibrary(
            cache=cache,
            accountant=self.accountant,
            waves=self.waves,
            tuning_source=self._current_tuning,
            memory_limit_bytes=memory_limit_bytes,
            is_playing=self._voices.is_playing_sound,
        )
        # Scene classes' (package directory, sound directory), looked up once each
        self._scene_paths: dict[type, tuple[Path | None, Path | None]] = {}
        # Scenes that played, until their voices are cleaned up (compared by identity)
        self._owners: list[object] = []
        # (served seconds, compiles) per frame over the last second (compiles_last_second)
        self._compile_window: collections.deque[tuple[float, int]] = collections.deque()
        self._compile_window_seconds = 0.0
        self._compiles_counted = 0
        self._last_frame_account = AudioFrameAccount(audio_seconds=0.0, audio_work=())
        self._last_processing_seconds: float | None = None
        self._closed = False

    # --- Sounds and plays (impl spec 8) ---

    def sound(  # ruff: ignore[too-many-arguments] - impl spec 8
        self,
        source: str | Instrument,
        *,
        pitch: PitchLike | None = None,
        notes: str | Sequence[tuple[PitchLike, float]] | None = None,
        chord: Sequence[PitchLike] | None = None,
        length: float | None = None,
        transpose: float = 0.0,
        parameters: Mapping[str, float] | None = None,
    ) -> Sound:
        """Get a sound; the first request for what it is compiles it. Getting never plays.

        Args:
            source: A short name (looked up in the scene's ``SOUND_DIRECTORY``), a path
                (relative to the scene's package directory) or an ``Instrument``.
            pitch: A pitch (``pitch``, ``notes`` and ``chord`` are mutually exclusive).
            notes: A melody.
            chord: Pitches played together.
            length: Seconds per note or chord before release.
            transpose: Semitones to shift notes or a chord.
            parameters: Live parameters (M2).

        Returns:
            The sound; its ``play()`` plays it through this engine.
        """
        package_root, sound_directory = self._paths_for(self._scene_source())
        sound = self.sounds.sound(
            source,
            scene_sound_directory=sound_directory,
            package_root=package_root,
            pitch=pitch,
            notes=notes,
            chord=chord,
            length=length,
            transpose=transpose,
            parameters=parameters,
        )
        sound.attach_player(self._play_sound)
        return sound

    def play(  # ruff: ignore[too-many-arguments] - impl spec 8
        self,
        source: str | Instrument,
        *,
        pitch: PitchLike | None = None,
        notes: str | Sequence[tuple[PitchLike, float]] | None = None,
        chord: Sequence[PitchLike] | None = None,
        length: float | None = None,
        transpose: float = 0.0,
        parameters: Mapping[str, float] | None = None,
        volume: float | None = None,
        pan: float | None = None,
        bus: str | None = None,
        priority: int | None = None,
        loop: bool | None = None,
        at_frame: int | None = None,
        persist: bool = False,
        position: tuple[float, float] | None = None,
    ) -> SoundHandle:
        """Get a sound and play it: ``sound(identity...).play(playback...)``.

        Args:
            source: As ``sound``.
            pitch: As ``sound``.
            notes: As ``sound``.
            chord: As ``sound``.
            length: As ``sound``.
            transpose: As ``sound``.
            parameters: As ``sound``.
            volume: As ``Sound.play``.
            pan: As ``Sound.play``.
            bus: As ``Sound.play``.
            priority: As ``Sound.play``.
            loop: As ``Sound.play``.
            at_frame: As ``Sound.play``.
            persist: As ``Sound.play``.
            position: As ``Sound.play``.

        Returns:
            The handle.
        """
        return self.sound(
            source,
            pitch=pitch,
            notes=notes,
            chord=chord,
            length=length,
            transpose=transpose,
            parameters=parameters,
        ).play(
            volume=volume,
            pan=pan,
            bus=bus,
            priority=priority,
            loop=loop,
            at_frame=at_frame,
            persist=persist,
            position=position,
        )

    def beep(
        self,
        *,
        pitch: PitchLike = 'A4',
        wave: str = 'square',
        length: float = 0.1,
        volume: float = 0.5,
        bus: str = 'effects',
    ) -> SoundHandle:
        """Play a basic waveform with a pluck envelope (feature spec W1); cached like any sound.

        Args:
            pitch: The pitch (a float is hertz).
            wave: The wave's name.
            length: Seconds before the release.
            volume: 0-1.
            bus: The bus.

        Returns:
            The handle.
        """
        return self.play(Instrument(wave=wave), pitch=pitch, length=length, volume=volume, bus=bus)

    def stop_all(self, *, fade: float = DEFAULT_STOP_FADE_SECONDS, bus: str | None = None) -> None:
        """Fade out every voice, or every voice on a bus and the buses under it.

        Persisted voices stop too.

        Args:
            fade: The fade in seconds (at least 5 ms).
            bus: A bus name, or None for every voice.
        """
        bus_names = None if bus is None else self._subtree(bus)
        self._voices.stop_buses(bus_names, fade_seconds=fade)

    def diagnostics(self) -> AudioDiagnostics:
        """What the engine has done so far (feature spec W8).

        Returns:
            The counters.
        """
        accountant = self.accountant
        counters = self._voices.counters
        return AudioDiagnostics(
            voices_playing=self._voices.voice_count,
            voices_limit=len(self._partition.library),
            compiles=accountant.compile_count,
            compile_milliseconds=(
                accountant.setup_compile_milliseconds + accountant.gameplay_compile_milliseconds
            ),
            setup_compiles=accountant.setup_compile_count,
            setup_compile_milliseconds=accountant.setup_compile_milliseconds,
            gameplay_compiles=accountant.gameplay_compile_count,
            gameplay_compile_milliseconds=accountant.gameplay_compile_milliseconds,
            compiles_in_gameplay=accountant.gameplay_compiles,
            stolen_voices=counters.steals,
            delayed_plays=counters.delayed_plays,
            dropped_plays=counters.dropped_plays,
            device=_device_description(),
            cache=self.sounds.statistics(),
        )

    def snapshot(self) -> AudioDiagnosticsSnapshot:
        """The engine as the debug overlay's Audio panel draws it (ruling R3).

        Returns:
            The snapshot.
        """
        channels = self._voices.snapshot()
        statistics = self.sounds.statistics()
        requests = statistics.hits + statistics.misses
        work_by_kind: dict[str, float] = {}
        for kind, _name, microseconds in self._last_frame_account.audio_work:
            work_by_kind[kind] = work_by_kind.get(kind, 0.0) + microseconds / 1_000_000
        return AudioDiagnosticsSnapshot(
            cache_mode=self.cache_mode,
            device=_device_description(),
            voices_live=sum(
                1 for channel in channels if channel.group == 'live' and channel.state != 'idle'
            ),
            voices_library=self._voices.voice_count,
            voices_legacy=sum(
                1 for channel in channels if channel.group == 'legacy' and channel.state != 'idle'
            ),
            compiles_last_second=sum(count for _seconds, count in self._compile_window),
            cache_hit_rate=None if requests == 0 else statistics.hits / requests,
            frame_work_by_kind=work_by_kind,
            frame_processing_seconds=self._last_processing_seconds,
            channels=channels,
            bus_levels={name: self.buses[name].effective_gain() for name in self.buses.names()},
            muted_buses=frozenset(name for name in self.buses.names() if self.buses[name].mute),
            compile_log=self.accountant.compile_log,
        )

    # --- The scene manager's calls, once per frame (impl spec 4.2 and 11.0) ---

    def begin_frame(self, *, frame_number: int) -> None:
        """Note the frame being run, for the compile log.

        Args:
            frame_number: The scene manager's frame number.
        """
        self.accountant.frame_number = frame_number

    def begin_scene_setup(self) -> None:
        """A scene's ``setup()`` begins: its compiles count as setup until its first logic frame."""
        self.accountant.setup_mode = True

    def begin_logic_frame(self) -> None:
        """A scene's logic frame begins: compiles now belong to their frame (impl spec 6.5).

        The first logic frame after a setup ends it: if the setup's compiles took more than
        50 ms, one INFO line names its slowest sounds.
        """
        if not self.accountant.setup_mode:
            return
        self.accountant.setup_mode = False
        total_milliseconds, slowest = self.accountant.take_setup_compiles()
        if total_milliseconds > SLOW_SETUP_MILLISECONDS:
            log.info(
                'Setup compiled sounds for %.1f ms (more than %.0f ms); the slowest: %s',
                total_milliseconds,
                SLOW_SETUP_MILLISECONDS,
                ', '.join(f'{record.name} {record.milliseconds:.1f} ms' for record in slowest),
            )

    def update(
        self,
        *,
        dt: float,
        active_scene: object | None,
        previous_scene: object | None,
        active_transitions: Sequence[object | None],
        paused_owners: Sequence[object] = (),
    ) -> None:
        """Apply the owner rules, then move every voice by the frame's served time.

        The arguments are ``LiveAudio.update``'s (see the module docstring).

        Args:
            dt: The frame's served time (a replay's recorded dt).
            active_scene: The active scene.
            previous_scene: The previous scene; held only while the active scene's
                ``debug_subject`` is it (a pause screen over it).
            active_transitions: The running and the pending transition (either may be None).
            paused_owners: Other owners whose voices pause (a playback scope's).
        """
        playing_owners = [
            SYSTEM_OWNER,
            *(owner for owner in (active_scene, *active_transitions) if owner is not None),
        ]
        # The previous scene is held only behind a pause screen showing it (ruling R33); a scene
        # switched away from directly is cleaned up
        shown_as_paused = getattr(active_scene, 'debug_subject', None) is previous_scene
        held_candidates = (previous_scene, *paused_owners) if shown_as_paused else paused_owners
        held_owners = [
            owner
            for owner in held_candidates
            if owner is not None and not _contains(playing_owners, owner)
        ]
        for owner in list(self._owners):
            if _contains(playing_owners, owner) or _contains(held_owners, owner):
                continue
            self._voices.stop_owner(owner, fade_seconds=SCENE_CLEANUP_FADE_SECONDS)
            self._owners = [kept for kept in self._owners if kept is not owner]
        self._voices.advance(dt=dt, paused_owners=held_owners)
        self._count_compiles(dt=dt)

    def take_frame_account(self, *, processing_seconds: float | None = None) -> AudioFrameAccount:
        """Return the frame's audio work and start the next frame's (impl spec 11.0).

        Args:
            processing_seconds: The frame's processing time, shown beside its audio work.

        Returns:
            The account.
        """
        self._last_frame_account = self.accountant.take_frame()
        self._last_processing_seconds = processing_seconds
        return self._last_frame_account

    def silenced(self, channel_index: int | None) -> None:
        """A channel (None: every channel) was stopped outside the engine: end its voices.

        Args:
            channel_index: The mixer channel ``FrameSilencer`` stopped, or None after
                ``pygame.mixer.stop()``.
        """
        indices = self._partition.library if channel_index is None else (channel_index,)
        for index in indices:
            self._voices.silenced(index)

    def close(self, *, wait_seconds: float = SHUTDOWN_WAIT_SECONDS) -> None:
        """Fade every voice over 50 ms, then wait for the fades at most ``wait_seconds``.

        Later plays are silent. Without a mixer, or on a mixer restarted with fewer channels
        than the partition's (its channels are gone), the voices simply end. Again: nothing.

        Args:
            wait_seconds: The longest wait (impl spec 10.3: 100 ms); 0 does not wait.
        """
        if self._closed:
            return
        self._closed = True
        if not self._partition_fits_the_mixer():
            # No channel to fade: the voices end in the table
            self.silenced(None)
            self._voices.close(fade_seconds=SHUTDOWN_FADE_SECONDS)
            return
        self._voices.close(fade_seconds=SHUTDOWN_FADE_SECONDS)
        deadline = clock.raw_counter_seconds() + wait_seconds
        while self._a_library_channel_sounds() and clock.raw_counter_seconds() < deadline:
            clock.raw_sleep(SHUTDOWN_POLL_SECONDS)

    # --- Inside ---

    def _current_tuning(self) -> Tuning:
        """The tuning, read at each request.

        Returns:
            ``tuning``.
        """
        return self.tuning

    def _compile_for_play(self, sound: Sound) -> Sound:
        """The library's ``compile_for_play`` (the voice table calls it on every play).

        Returns:
            The sound to play.
        """
        return self.sounds.compile_for_play(sound)

    def _play_sound(  # ruff: ignore[too-many-arguments] - impl spec 8's playback arguments
        self,
        sound: Sound,
        *,
        volume: float | None,
        pan: float | None,
        bus: str | None,
        priority: int | None,
        loop: bool | None,
        at_frame: int | None,
        persist: bool,
        position: tuple[float, float] | None,
    ) -> SoundHandle:
        """Play a sound for the current owner; None arguments take the sound's defaults.

        Returns:
            The handle.

        Raises:
            NotImplementedError: For ``at_frame`` (M2) or ``position`` (M4).
        """
        if at_frame is not None:
            raise NotImplementedError(SCHEDULED_PLAY_MESSAGE)
        if position is not None:
            raise NotImplementedError(POSITIONED_PLAY_MESSAGE)
        defaults = sound.playback_defaults
        owner = self._scene_source()
        if owner is None:
            owner = SYSTEM_OWNER
        elif not _contains(self._owners, owner):
            self._owners.append(owner)
        return self._voices.play(
            sound,
            volume=defaults.volume if volume is None else volume,
            pan=defaults.pan if pan is None else pan,
            bus=defaults.bus if bus is None else bus,
            priority=defaults.priority if priority is None else priority,
            loop=defaults.loop if loop is None else loop,
            persist=persist,
            owner=owner,
        )

    def _paths_for(self, scene: object | None) -> tuple[Path | None, Path | None]:
        """A scene's package directory and sound directory (ruling R21), looked up once a class.

        Returns:
            The package directory and the sound directory; either may be None.
        """
        if scene is None:
            return None, None
        scene_class = type(scene)
        known = self._scene_paths.get(scene_class)
        if known is not None:
            return known
        # Imported here: the replay tools import the scenes, which import this package
        from glitchygames.replay.tools.identity import game_identity

        # game_identity reads only the class's module, so any scene-like class will do
        package_root = game_identity(game=cast('type[Scene]', scene_class)).package_directory
        if package_root is None:
            package_root = _module_directory(scene_class.__module__)
        sound_directory_name: str | None = getattr(scene_class, 'SOUND_DIRECTORY', None)
        sound_directory = None
        if sound_directory_name is not None:
            directory = Path(sound_directory_name)
            if directory.is_absolute():
                sound_directory = directory
            elif package_root is not None:
                sound_directory = package_root / directory
        paths = (package_root, sound_directory)
        self._scene_paths[scene_class] = paths
        return paths

    def _subtree(self, bus: str) -> frozenset[str]:
        """A bus and every bus under it.

        Returns:
            Their names.
        """
        self.buses[bus]  # raises KeyError naming the buses for an unknown bus
        names = {bus}
        changed = True
        while changed:
            changed = False
            for name in self.buses.names():
                parent = self.buses[name].parent
                if name not in names and parent is not None and parent in names:
                    names.add(name)
                    changed = True
        return frozenset(names)

    def _count_compiles(self, *, dt: float) -> None:
        """Add this frame's compiles to the last second's window, dropping what left it."""
        compiled = self.accountant.compile_count
        self._compile_window.append((dt, compiled - self._compiles_counted))
        self._compiles_counted = compiled
        self._compile_window_seconds += dt
        while self._compile_window_seconds > COMPILE_RATE_WINDOW_SECONDS:
            seconds, _count = self._compile_window.popleft()
            self._compile_window_seconds -= seconds

    def _partition_fits_the_mixer(self) -> bool:
        """Whether a mixer runs with every library channel of the partition.

        Returns:
            False without a mixer, or when the mixer has fewer channels (restarted since).
        """
        if pygame.mixer.get_init() is None:
            return False
        return all(index < pygame.mixer.get_num_channels() for index in self._partition.library)

    def _a_library_channel_sounds(self) -> bool:
        """Whether the device still plays (or fades) a library channel.

        Returns:
            True while one is busy.
        """
        return any(pygame.mixer.Channel(index).get_busy() for index in self._partition.library)


def _contains(owners: Collection[object], owner: object) -> bool:
    """Whether ``owner`` is among ``owners``, by identity (scenes are compared as objects).

    Returns:
        True when it is.
    """
    return any(candidate is owner for candidate in owners)


@dataclasses.dataclass(slots=True)
class _AudioEngineHolder:
    """A context's audio engine, or None until something asks for audio."""

    engine: AudioEngine | None = None


# Each engine context's audio engine (glitchygames.engine_context; impl spec 8, Access point)
AUDIO_ENGINE_SLOT: ContextSlot[_AudioEngineHolder] = ContextSlot(
    name='glitchygames.audio.engine.audio_engine', factory=_AudioEngineHolder
)


def existing_audio_engine() -> AudioEngine | None:
    """The current context's audio engine, without making one.

    Returns:
        The engine, or None when nothing asked for audio yet.
    """
    return current_context().value(slot=AUDIO_ENGINE_SLOT).engine


def install_audio_engine(*, engine: AudioEngine) -> AudioEngine:
    """Make ``engine`` the current context's audio engine (``SceneManager.audio`` makes it).

    Args:
        engine: The engine.

    Returns:
        The engine.
    """
    current_context().value(slot=AUDIO_ENGINE_SLOT).engine = engine
    return engine


def discard_audio_engine(*, wait_seconds: float = SHUTDOWN_WAIT_SECONDS) -> None:
    """Close the current context's audio engine and forget it (shutdown; a new engine's start).

    Args:
        wait_seconds: The longest wait for the fades (``AudioEngine.close``).
    """
    holder = current_context().value(slot=AUDIO_ENGINE_SLOT)
    engine, holder.engine = holder.engine, None
    if engine is not None:
        engine.close(wait_seconds=wait_seconds)
