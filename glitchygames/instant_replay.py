"""The instant-replay journal: a scene's own recording, kept in memory from its start.

A scene class that sets ``Scene.INSTANT_REPLAY_SECONDS`` offers instant replay
(plans/2026-10-19-gameplay-replay.md, section 5.4). While such a scene runs, the scene manager
keeps an ``InstantReplayJournal`` of it: every frame since the scene's first logic frame,
recorded exactly as ``--record-trace`` records them (glitchygames/recording.py, whose
record-building functions it shares), so a playback scope can rebuild the scene from its start
and play the journal back with no divergence (glitchygames/replay/playback.py). The rules:

1. Opting in: a scene class whose ``INSTANT_REPLAY_SECONDS`` is not None and whose start is
   captured (glitchygames/scene_start.py, rule 1: such a class captures its start in plain
   live play too). A scene stand-in, a class that opts out of start capture, and a scene a
   playback scope builds (its doors are scoped) keep no journal.
2. The journal is made as the scene is first set up (``SceneManager._setup_new_scene``, after
   its start is completed and before its ``setup()``). From then on it sees save stores first
   opened before the game can write to them (including those its ``setup()`` opens) and the
   answers the devices door gives (``glitchygames.sources.observe_device_answers``); the
   answers given and devices opened from the scene's ``__init__`` until then come from its
   start capture (``SceneStartCapture.device_answers`` / ``opened_devices``). Code-posted
   events are tracked for the whole run (``GameEngine`` owns the internal-post tracker), so
   every event's origin and the count of posts pending as a frame begins are exact in plain
   live play. Resuming the scene from the pause screen sets it up again and keeps the journal.
3. Recording begins (``begin``) at the top of the scene's first logic frame
   (glitchygames/scene_start.py, rule 7), with the polled input that frame's logic reads (the
   previous frame's snapshot). ``SceneManager.instant_replay_journal`` is None until then.
4. Each pump's batch (``add_event_batch``, from ``GameEngine._pump_events``) is recorded with
   each event's origin, classified as a recorder classifies it (``event_batch_records``): from
   a replay's merge when the doors are a replay's (``ReplaySources.last_batch_origins``, as a
   ``--rebaseline`` recorder takes them; a watched replay's held frames drain the real queue
   between pumps), else from the tracker's posts as they were before the doors' pump. The
   events a playback scope held and redelivered before the pump go to the frame's
   ``redelivered_events``.
5. After each frame (``add_frame``, from ``SceneManager._run_frame``, after the doors ended
   the frame) the frame is recorded as ``recorded_frame`` builds it: the active scene's
   sprites, ``dt``, the batches, ``input_changes`` against the journal's previous snapshot,
   ``control_events``, ``devices_opened``, ``device_enumeration``, ``saves_opened``,
   ``redelivered_events``, on the first frame the scene's ``scene_start``, and the journal's
   own ``resume_bridge`` and ``playback_answers`` (rules 7 and 8). Frames are kept encoded as
   trace lines (glitchygames/tracing.py: a keyframe when a different scene object ends the
   frame, else a delta), which keeps an idle frame small.
6. A paused stretch: while the scene is behind the pause screen (the active scene's
   ``debug_subject`` is the journal's scene: ``PauseScene`` presents the paused scene), the
   journal goes on recording every frame, as the pause screen's own (its class and sprites);
   the scene's game time does not advance in them, so they add nothing to ``game_seconds``
   (they do to ``recorded_seconds``: a playback runs them again). The input that paused and
   resumed the scene is in the batches, so a playback pauses and resumes where the live scene
   did.
7. A playback scope (a demo, an instant replay) suspends the journal (``suspend``) as it
   begins: its frames are not the scene's, and nothing the scope's doors see is kept. On the
   first frame after the scope that presents the scene again, the journal resumes
   (``resume``) at the top of the frame, before any of its work, and writes into that frame a
   ``resume_bridge`` (``ResumeBridge``, glitchygames/scene_start.py): the frame clock (moved on
   by the scope's last frame), the FPS event timer and the count of code-posted events pending
   then (posted as the scope's last frame ended), and the polled input the frame's logic reads.
   The frame's ``redelivered_events`` hold what the scope held. A playback of the journal sets
   that state at the top of the frame (and, as the scope's end did, stops the SCREEN shake and
   sustained rumble; the random streams, restored in place at the scope's end, need nothing)
   and serves the frame as it serves its start frame
   (glitchygames/replay/driver.py, rule 18), so the gap leaves no trace; it adds no game time.
8. Playback requests: every answer the scene's code gets from ``start_playback`` /
   ``start_playback_from_recording`` (glitchygames/replay/playback.py) is recorded in the
   frame it was asked in (``playback_answers``; asked in ``setup()``, before the first logic
   frame, in the first frame's). Inside a playback scope those functions return the next
   answer the frame being played recorded and request nothing (scopes do not nest; a recording
   without one, such as a demo, is refused as before). So a scene that shows an instant replay
   after every goal plays back across its earlier replays.
9. The journal ends (``close``: save and device observation stop, the frames are dropped)
   when a frame ends with any other scene presented (a switch away, a transition, game over,
   a scope that returns elsewhere), when another opted-in scene is first set up, when the run
   ends (``terminate``) and when its ``recorded_seconds`` pass the scene's
   ``MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS`` (rule 11).
10. ``as_recording`` returns the recording: a header (``source: "instant_replay"``, the game
    and scene classes, ``recorded_at`` set so that it plus the frame clock is the wall clock
    the scene saw, the run's ``random_seed``, and ``devices`` and ``device_enumeration``: the
    devices opened and the answers given from the scene's ``__init__`` until its first logic
    frame, which the rebuilt scene's ``__init__`` and ``setup()`` are served), a lead-in frame
    (frame 0: no scene, no sprites; the polled input before the scene's first logic frame and
    the save stores its setup first opened, which a playback learns but does not serve;
    glitchygames/replay/driver.py, rule 18), then the journal's frames from ``start_frame``
    (``JOURNAL_START_FRAME``), the first holding the scene start. Play it with
    ``start_playback(..., options=PlaybackOptions(start_frame=recording.start_frame, ...))``,
    as ``SceneManager.instant_replay`` does (glitchygames/replay/playback.py, rule 7).
11. Memory: each kept frame is its trace line as compact UTF-8 JSON (a recording file's line,
    before gzip). Input (batches and changes) is recorded only when there is some; each
    frame's sprite sample dominates (``memory_bytes``; ``JOURNAL_BYTES_PER_MINUTE_LIMIT``
    bounds a minute of a scene with one sprite moving every frame). The journal holds the
    whole scene, never a window of it: an instant replay rebuilds the scene from its start and
    re-simulates every kept frame (spec 5.4). The frame time it holds (``recorded_seconds``,
    paused frames included) is that cost; past the scene's fast-forward budget
    (``Scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS``) no instant replay can be played, and
    the cost never goes back, so the scene manager ends the journal then: it never holds much
    more than the budget's frames (longer scenes need state snapshots, out of scope).

Limits: devices opened before the scene's ``__init__`` are not stand-ins in a playback (as for
any playback; ``joystick_for_instance`` knows only devices opened in it). A replay of the
session builds the same journal frames (its header's ``recorded_at`` may differ).

This module is a leaf like glitchygames/scene_start.py: it imports no scene, engine or replay
module, so glitchygames.scenes imports it without pulling in the replay package.
"""

from __future__ import annotations

import copy
import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field

from glitchygames.clock import wall_clock_time
from glitchygames.input.state import IDLE_INPUT, snapshot_changes
from glitchygames.logical_names import logical_name
from glitchygames.recording import (
    DEVICE_ENUMERATION_FIELD,
    DEVICES_HEADER_FIELD,
    event_batch_records,
    event_to_record,
    recorded_frame,
)
from glitchygames.sources import (
    active_sources,
    frame_clock_seconds,
    has_scoped_sources,
    observe_device_answers,
    observe_save_store_openings,
    stop_observing_device_answers,
    stop_observing_save_store_openings,
)
from glitchygames.state.sandbox import save_namespace_snapshot
from glitchygames.tracing import StableSpriteIds, decode_frame, encode_frame

if TYPE_CHECKING:
    from collections.abc import Iterable

    import pygame

    from glitchygames.input.devices import DeviceDescriptor, EnumerationAnswer
    from glitchygames.input.state import InputSnapshot
    from glitchygames.scene_start import ResumeBridge, SceneStart
    from glitchygames.scenes import Scene
    from glitchygames.sources import RedeliveredEvent
    from glitchygames.state.manager import SaveManager
    from glitchygames.supervision import ControlEvent

# The header's ``source`` field for a journal's recording (a file recording's is
# glitchygames.recording.RECORDING_SOURCE)
INSTANT_REPLAY_SOURCE: Final = 'instant_replay'
# The recording frame a journal's playback starts at: frame 0 is the lead-in (rule 10)
JOURNAL_START_FRAME: Final = 1
# A minute at 60 FPS of a scene with one sprite moving every frame stays below this many
# bytes of kept frames (rule 11; the memory test's bound: 487_718 bytes measured, about 135
# per frame; PaddleSlap's golden script, 11 sprites, keeps 1_547_920 bytes in 3600 frames).
# Bytes of compact JSON: each kept frame is one Python bytes object, whose own overhead (33
# bytes on CPython) is not counted
JOURNAL_BYTES_PER_MINUTE_LIMIT: Final = 500_000

# How kept frames are measured: compact JSON, as a recording's file holds them
_COMPACT_SEPARATORS = (',', ':')


class JournalRecording(BaseModel):
    """A journal as a recording a playback scope plays (read-only; rule 10).

    Attributes:
        header: The recording's header fields.
        frames: The decoded frames: the lead-in, then the journal's.
        start_frame: The frame to start playing at (``JOURNAL_START_FRAME``): it holds the
            scene's start.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    header: dict[str, Any]
    frames: list[dict[str, Any]]
    start_frame: int = Field(ge=0)


class InstantReplayJournal:
    """One opted-in scene's frames since its first logic frame (see the module docstring).

    Attributes:
        scene: The scene journaled.

    """

    def __init__(self: Self, *, scene: Scene, game: object | None) -> None:
        """Start watching save stores open and device answers, as the scene is first set up.

        Args:
            scene: The opted-in scene, its start completed, before its ``setup()`` (rule 2).
            game: The running game (``GameEngine.game``), named in the header; None without
                an engine.

        """
        self.scene = scene
        start = scene.scene_start
        self._header: dict[str, Any] = {
            'source': INSTANT_REPLAY_SOURCE,
            'frame_seconds': None,
            'scene_class': type(scene).__name__,
            'random_seed': active_sources().random_seed,
        }
        if game is not None:
            self._header['game_class'] = type(game).__name__
            self._header['game_module'] = type(game).__module__
            # The game's logical name, which replays compare (glitchygames/logical_names.py)
            self._header['game'] = logical_name(scene_class=type(game))
        # Save namespaces a playback seeds from the scene's start; others are snapshotted
        # into the frame that first opens them (setup's go to the lead-in frame)
        self._known_save_namespaces: set[str] = set() if start is None else set(start.saves)
        self._start: SceneStart | None = None
        self._is_closed = False
        self._is_suspended = False
        self._sprite_ids = StableSpriteIds()
        # The lead-in frame's fields (rule 10)
        self._input_before_start: InputSnapshot = IDLE_INPUT
        self._lead_in_saves_opened: dict[str, Any] = {}
        self._game_seconds_at_start = 0.0
        self._recorded_seconds = 0.0
        # Kept frames, each a trace line as compact UTF-8 JSON (rule 11), and the last full
        # frame they are encoded against
        self._kept_frames: list[bytes] = []
        self._previous_frame_record: dict[str, Any] | None = None
        self._previous_scene: Scene | None = None
        self._recorded_snapshot: InputSnapshot = IDLE_INPUT
        # The current frame's fields, gathered until add_frame (before begin, the devices and
        # answers go to the header and the playback answers to the first frame)
        self._event_batches: list[list[dict[str, Any]]] = []
        self._redelivered_events: list[dict[str, Any]] = []
        self._saves_opened: dict[str, Any] = {}
        self._devices_opened: list[dict[str, Any]] = []
        self._device_enumeration: list[dict[str, Any]] = []
        self._resume_bridge: dict[str, Any] | None = None
        self._playback_answers: list[bool] = []
        capture = scene.scene_start_capture
        if capture is not None:
            self._devices_opened = [descriptor.to_json() for descriptor in capture.opened_devices]
            self._device_enumeration = [answer.to_json() for answer in capture.device_answers]
        observe_save_store_openings(observer=self)
        observe_device_answers(observer=self)

    @property
    def is_recording(self: Self) -> bool:
        """True from the scene's first logic frame until the journal is closed (rule 3)."""
        return self._start is not None and not self._is_closed

    @property
    def is_suspended(self: Self) -> bool:
        """True from a playback scope's start until the scene resumes after it (rule 7)."""
        return self._is_suspended

    @property
    def frame_count(self: Self) -> int:
        """How many frames the journal holds."""
        return len(self._kept_frames)

    @property
    def game_seconds(self: Self) -> float:
        """The scene's game time since its first logic frame (paused frames add nothing)."""
        if self._start is None:
            return 0.0
        return self.scene.game_time - self._game_seconds_at_start

    @property
    def recorded_seconds(self: Self) -> float:
        """The frame time of every kept frame, paused ones included (what a playback re-runs)."""
        return self._recorded_seconds

    def within_budget(self: Self, *, maximum_seconds: float) -> bool:
        """Report whether playing the journal from its start re-simulates at most this much.

        Args:
            maximum_seconds: The frame time a playback may re-simulate
                (``Scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS``).

        Returns:
            True when ``recorded_seconds`` is at most ``maximum_seconds``.

        """
        return self._recorded_seconds <= maximum_seconds

    def memory_bytes(self: Self) -> int:
        """Return the size of the kept frames: their compact JSON, as kept (rule 11).

        Returns:
            Bytes (without the Python object overhead of one bytes object per frame).

        """
        return sum(len(line) for line in self._kept_frames)

    def _is_watching(self: Self) -> bool:
        """Report whether what the doors see now belongs to the scene.

        Returns:
            True while the journal is open, not suspended, and no playback scope serves.

        """
        return not self._is_closed and not self._is_suspended and not has_scoped_sources()

    def begin(self: Self, *, start: SceneStart, input_before_start: InputSnapshot) -> None:
        """Begin recording at the top of the scene's first logic frame (rule 3).

        Args:
            start: The scene's start, with its first logic frame.
            input_before_start: The polled input that frame's logic reads.

        """
        if self._start is not None or self._is_closed:
            return
        self._start = start
        self._is_suspended = False
        self._input_before_start = input_before_start
        self._recorded_snapshot = input_before_start
        self._lead_in_saves_opened, self._saves_opened = self._saves_opened, {}
        # Served to the rebuilt scene's __init__ and setup(), before its first logic frame
        self._header[DEVICES_HEADER_FIELD], self._devices_opened = self._devices_opened, []
        self._header[DEVICE_ENUMERATION_FIELD], self._device_enumeration = (
            self._device_enumeration,
            [],
        )
        self._game_seconds_at_start = self.scene.game_time
        # The wall clock the scene saw, less the frame clock: a playback's wall clock is this
        # stamp plus its frame clock (glitchygames/replay/driver.py, rule 9)
        self._header['recorded_at'] = (
            wall_clock_time() - timedelta(seconds=frame_clock_seconds())
        ).isoformat()

    def suspend(self: Self) -> None:
        """Stop keeping what the doors see while a playback scope plays (rule 7).

        A journal not begun yet is not suspended: it begins at its scene's first logic frame,
        after the scope, as usual.
        """
        if self.is_recording:
            self._is_suspended = True

    def resume(self: Self, *, bridge: ResumeBridge, input_before: InputSnapshot) -> None:
        """Go on recording at the top of the first frame after the scope (rule 7).

        Args:
            bridge: What the scene resumes with, written into this frame.
            input_before: The polled input this frame's logic reads (the bridge's).

        """
        if not self._is_suspended or self._is_closed:
            return
        self._is_suspended = False
        self._resume_bridge = bridge.model_dump()
        self._recorded_snapshot = input_before

    def on_save_store_opened(self: Self, *, namespace: str, store: SaveManager) -> None:
        """Snapshot a save store opened for the first time since the scene's start (rule 2).

        Args:
            namespace: The store's namespace.
            store: The store, not yet written to by whoever opened it.

        """
        if not self._is_watching() or namespace in self._known_save_namespaces:
            return
        self._known_save_namespaces.add(namespace)
        self._saves_opened[namespace] = save_namespace_snapshot(saves=store)

    def on_device_answer(
        self: Self, *, answer: EnumerationAnswer, opened: DeviceDescriptor | None
    ) -> None:
        """Keep an answer the devices door gave, and the device it opened (rule 2).

        Args:
            answer: The answer given.
            opened: The descriptor of the device an open opened, else None.

        """
        if not self._is_watching():
            return
        self._device_enumeration.append(answer.to_json())
        if opened is not None:
            self._devices_opened.append(opened.to_json())

    def add_playback_answer(self: Self, *, granted: bool) -> None:
        """Keep what a playback request of the scene's code got, in this frame (rule 8).

        Args:
            granted: The answer ``start_playback`` returned.

        """
        if self._is_watching():
            self._playback_answers.append(granted)

    def add_event_batch(
        self: Self,
        *,
        raw_events: Iterable[pygame.event.Event],
        posts_before_pump: list[tuple[int, dict[str, Any]]],
        origins: list[str] | None,
        redelivered_events: list[RedeliveredEvent],
    ) -> None:
        """Record one pump's batch (rule 4).

        Args:
            raw_events: The doors' batch, as they returned it.
            posts_before_pump: A copy of the tracker's posts as they were before the doors'
                pump (consumed here), which classify the batch when ``origins`` is None.
            origins: Each event's origin when a replay's merge knows them, else None.
            redelivered_events: The events a playback scope held, delivered before the batch,
                each with its origin.

        """
        if not self.is_recording or not self._is_watching():
            return
        self._redelivered_events.extend(
            event_to_record(event=event, origin=origin) for event, origin in redelivered_events
        )
        self._event_batches.append(
            event_batch_records(raw_events=raw_events, pending=posts_before_pump, origins=origins)
        )

    def add_frame(
        self: Self,
        *,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
        input_snapshot: InputSnapshot,
    ) -> None:
        """Record the frame just finished (rule 5); nothing before begin or while suspended.

        Args:
            dt: The frame's raw delta time.
            scene: The active scene at the end of the frame (the journal's, or the pause
                screen presenting it).
            control_events: The control events recorded in the frame, in order.
            input_snapshot: The frame's polled input.

        """
        if self._start is None or not self.is_recording or not self._is_watching():
            return
        input_changes = snapshot_changes(previous=self._recorded_snapshot, current=input_snapshot)
        self._recorded_snapshot = input_snapshot
        frame_record = recorded_frame(
            frame_number=JOURNAL_START_FRAME + len(self._kept_frames),
            scene=scene,
            sprite_ids=self._sprite_ids,
            dt=dt,
            event_batches=self._event_batches,
            input_changes=input_changes,
            control_events=[control_event.to_json() for control_event in control_events],
            devices_opened=self._devices_opened,
            saves_opened=self._saves_opened,
            device_enumeration=self._device_enumeration,
            scene_start=self._start.to_json() if not self._kept_frames else None,
            redelivered_events=self._redelivered_events,
            resume_bridge=self._resume_bridge,
            playback_answers=self._playback_answers,
        )
        # A different scene object (the pause screen, the scene again) starts a keyframe, as a
        # recorder's does
        is_new_scene_object = scene is not self._previous_scene
        line_record = encode_frame(
            frame_record=frame_record,
            previous_frame_record=None if is_new_scene_object else self._previous_frame_record,
        )
        # As a recording's file holds it: compact, text written as is
        self._kept_frames.append(
            json.dumps(line_record, separators=_COMPACT_SEPARATORS, ensure_ascii=False).encode(
                'utf-8'
            )
        )
        self._recorded_seconds += dt
        self._previous_frame_record = frame_record
        self._previous_scene = scene
        self._event_batches = []
        self._redelivered_events = []
        self._saves_opened = {}
        self._devices_opened = []
        self._device_enumeration = []
        self._resume_bridge = None
        self._playback_answers = []

    def as_recording(self: Self) -> JournalRecording:
        """Return the journal as a recording a playback scope plays (rule 10).

        Returns:
            The header, the lead-in frame and the decoded frames (copies: changing them never
            changes the journal), and the frame to start at.

        """
        lead_in_frame = recorded_frame(
            frame_number=0,
            scene=None,
            sprite_ids=StableSpriteIds(),
            dt=0.0,
            event_batches=[],
            input_changes=snapshot_changes(previous=IDLE_INPUT, current=self._input_before_start),
            saves_opened=self._lead_in_saves_opened,
        )
        frames = [copy.deepcopy(lead_in_frame)]
        previous_frame_record: dict[str, Any] | None = None
        for line in self._kept_frames:
            previous_frame_record = decode_frame(
                line_record=json.loads(line), previous_frame_record=previous_frame_record
            )
            frames.append(previous_frame_record)
        return JournalRecording(
            header=copy.deepcopy(self._header), frames=frames, start_frame=JOURNAL_START_FRAME
        )

    def close(self: Self) -> None:
        """End the journal: stop watching saves and devices, drop the frames (rule 9)."""
        if self._is_closed:
            return
        self._is_closed = True
        stop_observing_save_store_openings(observer=self)
        stop_observing_device_answers(observer=self)
        self._kept_frames = []
        self._previous_frame_record = None
        self._previous_scene = None
