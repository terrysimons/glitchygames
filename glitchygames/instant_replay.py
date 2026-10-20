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
   its start is completed and before its ``setup()``), so that from then on code-posted events
   are tracked (it owns the internal-post tracker, glitchygames/recording.py: the count of
   posts pending as the scene's first logic frame begins, and every event's origin, are exact
   in plain live play, not only while recording or replaying; posts made before that setup are
   not tracked, as for a recording started later) and save stores first opened are seen
   before the game can write to them (including those its ``setup()`` opens). Resuming the
   scene from the pause screen sets it up again and keeps the journal.
3. Recording begins (``begin``) at the top of the scene's first logic frame
   (glitchygames/scene_start.py, rule 7), with the polled input that frame's logic reads (the
   previous frame's snapshot). ``SceneManager.instant_replay_journal`` is None until then.
4. Each pump's batch (``add_event_batch``, from ``GameEngine._pump_events``) is recorded with
   each event's origin, classified as a recorder classifies it (``event_batch_records``) from
   the tracker's posts as they were before the doors' pump (so a recorder or a replay
   underneath, which consumes them, is classified identically); the events a playback scope
   held and redelivered before the pump go to the frame's ``redelivered_events``. Then posts
   the pump did not return are forgotten, as a recorder forgets them. Before ``begin`` the
   batches are only used to forget posts.
5. After each frame (``add_frame``, from ``SceneManager._run_frame``, after the doors ended
   the frame) the frame is recorded as ``recorded_frame`` builds it: the active scene's
   sprites, ``dt``, the batches, ``input_changes`` against the journal's previous snapshot,
   ``control_events``, ``saves_opened``, ``redelivered_events``, and on the first frame the
   scene's ``scene_start``. Frames are kept encoded as trace lines (glitchygames/tracing.py:
   a keyframe when a different scene object ends the frame, else a delta), which keeps an
   idle frame small.
6. A paused stretch: while the scene is behind the pause screen (the active scene's
   ``debug_subject`` is the journal's scene: ``PauseScene`` presents the paused scene), the
   journal goes on recording every frame, as the pause screen's own (its class and sprites);
   the scene's game time does not advance in them, so they add nothing to ``game_seconds``.
   The input that paused and resumed the scene is in the batches, so a playback pauses and
   resumes where the live scene did.
7. The journal ends (``close``: tracking and save observation stop, the frames are dropped)
   when a frame ends with any other scene active (a switch away, a transition, game over),
   when another opted-in scene is first set up, when the run ends (``terminate``), when its
   ``game_seconds`` pass the scene's ``MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS`` (rule 9), and
   when a playback scope begins (the live frame clock moves on by the scope's last frame and
   the scope's held events come back in the next frame, which a playback from the scene's
   start cannot reproduce; so after an instant replay or a demo the scene keeps no journal).
8. ``as_recording`` returns the recording: a header (``source: "instant_replay"``, the game
   and scene classes, ``recorded_at`` set so that it plus the frame clock is the wall clock
   the scene saw, and the run's ``random_seed``), a lead-in frame (frame 0: no scene, no
   sprites; the polled input before the scene's first logic frame and the save stores its
   setup first opened, which a playback learns but does not serve; glitchygames/replay/
   driver.py, rule 18), then the journal's frames from ``start_frame``
   (``JOURNAL_START_FRAME``), the first holding the scene start. Play it with
   ``start_playback(..., options=PlaybackOptions(start_frame=recording.start_frame, ...))``.
9. Memory: each kept frame is its trace line as compact UTF-8 JSON (a recording file's line,
   before gzip). Input (batches and changes) is recorded only when there is some; each
   frame's sprite sample dominates (``memory_bytes``; ``JOURNAL_BYTES_PER_MINUTE_LIMIT`` bounds
   a minute of a scene with one sprite moving every frame). The journal holds the whole scene,
   never a window of it: an instant replay rebuilds the scene from its start and
   fast-forwards (spec 5.4). Past the scene's fast-forward budget
   (``Scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS`` of game time) no instant replay can be
   played, and game time never goes back, so the scene manager ends the journal then: it
   never holds much more than the budget's frames.

Limits: devices are not journaled (the opened-device descriptors and enumeration answers
belong to the doors' recorder, which takes them): a scene that opens or enumerates devices in
its journaled frames may diverge when played back. A replay of the session builds the same
journal frames (its header's ``recorded_at`` may differ).

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
from glitchygames.recording import (
    event_batch_records,
    event_to_record,
    pending_internal_posts,
    recorded_frame,
    start_tracking_internal_posts,
    stop_tracking_internal_posts,
)
from glitchygames.sources import (
    active_sources,
    frame_clock_seconds,
    observe_save_store_openings,
    stop_observing_save_store_openings,
)
from glitchygames.state.sandbox import save_namespace_snapshot
from glitchygames.tracing import StableSpriteIds, decode_frame, encode_frame

if TYPE_CHECKING:
    from collections.abc import Iterable

    import pygame

    from glitchygames.input.state import InputSnapshot
    from glitchygames.scene_start import SceneStart
    from glitchygames.scenes import Scene
    from glitchygames.sources import RedeliveredEvent
    from glitchygames.state.manager import SaveManager
    from glitchygames.supervision import ControlEvent

# The header's ``source`` field for a journal's recording (a file recording's is
# glitchygames.recording.RECORDING_SOURCE)
INSTANT_REPLAY_SOURCE: Final = 'instant_replay'
# The recording frame a journal's playback starts at: frame 0 is the lead-in (rule 8)
JOURNAL_START_FRAME: Final = 1
# A minute at 60 FPS of a scene with one sprite moving every frame stays below this many
# bytes of kept frames (rule 9; the memory test's bound: 487_718 bytes measured, about 135
# per frame; PaddleSlap's golden script, 11 sprites, keeps 1_547_920 bytes in 3600 frames)
JOURNAL_BYTES_PER_MINUTE_LIMIT: Final = 500_000

# How kept frames are measured: compact JSON, as a recording's file holds them
_COMPACT_SEPARATORS = (',', ':')


class JournalRecording(BaseModel):
    """A journal as a recording a playback scope plays (read-only; rule 8).

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
        """Start tracking posts and watching save stores open, as the scene is first set up.

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
        # Save namespaces a playback seeds from the scene's start; others are snapshotted
        # into the frame that first opens them (setup's go to the lead-in frame)
        self._known_save_namespaces: set[str] = set() if start is None else set(start.saves)
        self._start: SceneStart | None = None
        self._is_closed = False
        self._sprite_ids = StableSpriteIds()
        # The lead-in frame's fields (rule 8)
        self._input_before_start: InputSnapshot = IDLE_INPUT
        self._lead_in_saves_opened: dict[str, Any] = {}
        self._game_seconds_at_start = 0.0
        # Kept frames, each a trace line as compact UTF-8 JSON (rule 9), and the last full
        # frame they are encoded against
        self._kept_frames: list[bytes] = []
        self._previous_frame_record: dict[str, Any] | None = None
        self._previous_scene: Scene | None = None
        self._recorded_snapshot: InputSnapshot = IDLE_INPUT
        # The current frame's fields, gathered until add_frame
        self._event_batches: list[list[dict[str, Any]]] = []
        self._redelivered_events: list[dict[str, Any]] = []
        self._saves_opened: dict[str, Any] = {}
        start_tracking_internal_posts()
        observe_save_store_openings(observer=self)

    @property
    def is_recording(self: Self) -> bool:
        """True from the scene's first logic frame until the journal is closed (rule 3)."""
        return self._start is not None and not self._is_closed

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

    def within_budget(self: Self, *, maximum_seconds: float) -> bool:
        """Report whether playing the journal from its start fast-forwards at most this much.

        Args:
            maximum_seconds: The scene time a playback may re-simulate
                (``Scene.MAX_INSTANT_REPLAY_FAST_FORWARD_SECONDS``).

        Returns:
            True when ``game_seconds`` is at most ``maximum_seconds``.

        """
        return self.game_seconds <= maximum_seconds

    def memory_bytes(self: Self) -> int:
        """Return the size of the kept frames: their compact JSON, as kept (rule 9).

        Returns:
            Bytes (without the Python object overhead of one bytes object per frame).

        """
        return sum(len(line) for line in self._kept_frames)

    def begin(self: Self, *, start: SceneStart, input_before_start: InputSnapshot) -> None:
        """Begin recording at the top of the scene's first logic frame (rule 3).

        Args:
            start: The scene's start, with its first logic frame.
            input_before_start: The polled input that frame's logic reads.

        """
        if self._start is not None or self._is_closed:
            return
        self._start = start
        self._input_before_start = input_before_start
        self._recorded_snapshot = input_before_start
        self._lead_in_saves_opened, self._saves_opened = self._saves_opened, {}
        self._game_seconds_at_start = self.scene.game_time
        # The wall clock the scene saw, less the frame clock: a playback's wall clock is this
        # stamp plus its frame clock (glitchygames/replay/driver.py, rule 9)
        self._header['recorded_at'] = (
            wall_clock_time() - timedelta(seconds=frame_clock_seconds())
        ).isoformat()

    def on_save_store_opened(self: Self, *, namespace: str, store: SaveManager) -> None:
        """Snapshot a save store opened for the first time since the scene's start (rule 2).

        Args:
            namespace: The store's namespace.
            store: The store, not yet written to by whoever opened it.

        """
        if self._is_closed or namespace in self._known_save_namespaces:
            return
        self._known_save_namespaces.add(namespace)
        self._saves_opened[namespace] = save_namespace_snapshot(saves=store)

    def add_event_batch(
        self: Self,
        *,
        raw_events: Iterable[pygame.event.Event],
        posts_before_pump: list[tuple[int, dict[str, Any]]],
        redelivered_events: list[RedeliveredEvent],
    ) -> None:
        """Record one pump's batch, then forget the posts it did not return (rule 4).

        Args:
            raw_events: The doors' batch, as they returned it.
            posts_before_pump: A copy of the tracker's posts as they were before the doors'
                pump (consumed here).
            redelivered_events: The events a playback scope held, delivered before the batch,
                each with its origin.

        """
        if self.is_recording:
            self._redelivered_events.extend(
                event_to_record(event=event, origin=origin) for event, origin in redelivered_events
            )
            self._event_batches.append(
                event_batch_records(raw_events=raw_events, pending=posts_before_pump)
            )
        # Matched or not returned, the posts made before this pump are done with (a recorder
        # or a replay underneath has already consumed them)
        pending_internal_posts().clear()

    def add_frame(
        self: Self,
        *,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
        input_snapshot: InputSnapshot,
    ) -> None:
        """Record the frame just finished (rule 5); nothing before the first logic frame.

        Args:
            dt: The frame's raw delta time.
            scene: The active scene at the end of the frame (the journal's, or the pause
                screen presenting it).
            control_events: The control events recorded in the frame, in order.
            input_snapshot: The frame's polled input.

        """
        if not self.is_recording or self._start is None:
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
            saves_opened=self._saves_opened,
            scene_start=self._start.to_json() if not self._kept_frames else None,
            redelivered_events=self._redelivered_events,
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
        self._previous_frame_record = frame_record
        self._previous_scene = scene
        self._event_batches = []
        self._redelivered_events = []
        self._saves_opened = {}

    def as_recording(self: Self) -> JournalRecording:
        """Return the journal as a recording a playback scope plays (rule 8).

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
        """End the journal: stop tracking posts and watching saves, drop the frames (rule 7)."""
        if self._is_closed:
            return
        self._is_closed = True
        stop_tracking_internal_posts()
        stop_observing_save_store_openings(observer=self)
        self._kept_frames = []
        self._previous_frame_record = None
        self._previous_scene = None
