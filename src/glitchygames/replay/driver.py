"""Exact replay of a ``--record-trace`` recording through the real engine (``--replay-trace``).

``ReplaySources`` are the doors (glitchygames/sources.py) a replay installs: everything the
recorded run took in is served from the recording, so the real engine and game code run the
session again, and every frame's sprites are compared with the recorded frame. The rules
(plans/2026-10-19-gameplay-replay.md, sections 3.1-3.3):

1. Startup, in one place (``GameEngine.__init__``): once the options are parsed,
   ``start_replay`` reads the recording, refuses a recording of another game
   (``ReplayRefusedError``; the engine logs it and exits with ``ExitCode.UNUSABLE_INPUT``, as
   for an unreadable file or a malformed one (``decoded_replay_sources``), or
   ``ExitCode.MISSING_INPUT`` for a missing one;
   glitchygames/exit_codes.py), warns once about a different engine version, applies the
   recorded options (all but ``REPLAY_LOCAL_OPTIONS``) and seeds the random streams with the
   recorded seed. Games read the display's size, so the window opens at the header's
   ``screen_size`` (the size the recorded display had, which a window manager may have made
   other than the recorded ``--resolution``): ``apply_recorded_screen_size`` sets the
   ``resolution`` option to it, and the engine's normal display set-up opens it (headless or
   watched). A window that still opens at another size is refused (``display_size_refusal``:
   the engine logs ``Cannot replay PATH: it was recorded on a 800x600 display, but the window
   opened at 800x480 ...`` and exits with ``ExitCode.UNUSABLE_INPUT``); a ``screen_size`` that is
   not two positive integers is a malformed header (``UNUSABLE_INPUT``). A header without one
   (not written by the engine's recorder, which always writes it, format 2 included) keeps the
   recorded ``--resolution``, with a warning. A size that changes during the recorded run is
   not recorded, so a game that reads the live size every frame can still diverge. The engine
   installs the sources before the first frame; while installed they own the internal-post
   tracker (glitchygames/recording.py).
2. Pump: the real queue is drained (through the live doors' pump) and each event classified
   with the internal-post tracker. From the first drain on, real input, device and window
   events are blocked at SDL (``REAL_INPUT_EVENT_TYPES``, glitchygames/replay/input_blocking.py),
   so they never enter the queue (each drain blocks them again, as an event manager made mid-run
   allows its types); the blocked state each type had before comes back when the
   replay ends (``finish_run``, normally or after an error) or is uninstalled. QUIT, the
   window's close event and the custom range are never blocked, nor, in a watched replay, are
   KEYDOWN and KEYUP (``WATCHED_REAL_KEY_EVENT_TYPES``: the viewer's keys, rule 14). Blocking
   also refuses posts of those types: game code that fakes input by posting, say, KEYDOWN loses
   the post, which shows as a missing internal event divergence (the engine's own posts are
   QUIT and custom types). So game code posting KEYDOWN or KEYUP replays differently watched
   and headless: watched, the keys are not blocked, the post arrives and matches its recorded
   internal record; headless (and so ``--audit``), it is refused and diverges. A recording of
   such a game can match watched and diverge headless. What external events still arrive
   (queued before the first drain, the close event, app lifecycle and system notifications)
   never reach the game: a watched replay's real key presses and releases go to its controls
   (rule 14), the rest are dropped, except the window's QUIT, kept last so closing the window
   ends the replay. A control tick of a held frame (rule 14) drains the queue the same way; the
   internal events it finds wait for the next pump. Pump N serves the recording's batch N in
   its recorded order: each external record is rebuilt (recorded references mapped to live
   objects: a window to None, as live events of the display module's window carry it; a
   joystick to its opened stand-in, an event whose joystick has none being dropped with one
   warning per instance id), and each internal record is the live internal event the replayed
   code posted again (equal records). A recorded internal event nobody posted, a posted one the
   recording does not have, or a frame pumped more or fewer times than recorded is a
   divergence of the frame. Internal events are matched by encoded record
   (``event_to_record``), so one carrying a window or joystick reference would compare the
   recorded and live ids; none of the engine's posts carry one today.
3. Frame indexes: the sources count their own ``end_frame`` calls; every recorded frame they
   serve is picked by that count, never by the scene manager's frame number.
4. Frame time: the current frame's recorded ``dt``; past the end, the measurement. The FPS
   events and performance statistics (``performance_frame_seconds``) use it too under
   ``--replay-fps recorded`` (the default), so the FPS events are compared exactly; under
   ``--replay-fps real`` they use this machine's measured frame time, and FPS events are not
   compared (logic still receives the recorded ``dt``).
5. Input: the frame's snapshot, rebuilt by applying each frame's ``input_changes`` in order
   (a version-2 recording has none: polled input reads as idle, with one warning). Held keys
   answer by the key codes the recording machine held them as, whatever this machine's
   keyboard layout (glitchygames/input/state.py).
6. Devices: a ``ReplayDeviceRegistry`` from the header, learning each frame's opened devices
   and enumeration answers when the frame begins (before any open in it is answered).
7. Saves: a ``MemorySaveManager`` per namespace, seeded from the header's ``saves`` or the
   frame's ``saves_opened`` (an unknown namespace gets an empty store); real saves are never
   touched.
8. End of frame: a divergence found by the frame's pumps comes first; then the frame's
   control events that are not applied again (markers the replayed code records by itself)
   are compared with the recorded ones, in order; then the scene's sprites are sampled as the
   recorder samples them and compared with the recorded frame (scene class, then each sprite:
   present, ``rect``, ``visible``). The first difference stops a headless replay, as does
   the last recorded frame; a watched replay pauses there instead (rule 14). Under
   ``ReplayOptions.stop_on_divergence`` False (``--rebaseline``, rule 17) a difference stops
   nothing: the result keeps the first one, counts the frames that differ
   (``ReplayResult.differing_frame_count``) and names every sprite that differs in them
   (``ReplayResult.affected_sprite_ids``), and the replay runs on to the last recorded frame.
   The report's history ends at the first divergent frame either way. A frame that pumped fewer
   times than recorded never serves its remaining batches (they are not carried into a later
   pump); their external events are counted (``ReplayResult.undelivered_input_count``).
9. Clocks: the wall clock is the recording's ``recorded_at`` plus the frame clock; elapsed
   seconds are the frame clock, live and replayed alike (glitchygames/clock.py).
10. ``recorded_frame_fields`` hands a recording made over the replay (``--rebaseline``, rule 17)
    the frame's recorded saves and device fields, and ``last_batch_origins`` each event's origin
    in the batch the last pump returned.
11. ``GameEngine._shutdown`` calls ``finish_run`` and reports the result (``ReplayResult.report``:
    printed to stdout under ``--headless``, logged otherwise); ``GameEngine.start`` then ends the
    run with ``ReplayResult.exit_code(policy=options.exit_policy)``.
    The report of a sprite divergence lists the sprite in the last ``REPORT_HISTORY_FRAMES``
    frames before it, recorded and replayed (kept by ``end_frame``).
12. Digests (``--replay-digest PATH``, for ``--audit``: glitchygames/replay/audit.py): each
    compared frame's ``frame_digest`` (of the frame as sampled for rule 8) is kept, and
    ``finish_run`` writes them with the divergence summary to the digest file. The engine
    refuses a digest file it cannot write before the run (``ExitCode.CANNOT_WRITE_OUTPUT``);
    one that cannot be written at the end is logged on one line (``digest_write_failed``), and
    the run exits ``ExitCode.CANNOT_WRITE_OUTPUT`` once the replay is reported.
13. Pacing: the scene manager never paces a replay (``paced_frame_seconds`` is 0.0). A
    headless replay (``--headless``) is not paced at all, as its frame times come from the
    recording. A watched replay is paced by its viewer (glitchygames/replay/viewer.py, whose
    docstring is the contract): an outer tick 60 times a second of real time
    (``glitchygames.clock.measured_seconds``, never replayed: it only decides when frames run,
    never what they do) runs the inner recorded frames its accumulator pays for (real time
    times the speed, consumed by each frame's recorded duration, bounded per tick in frames and
    real time, never owing more than one tick's worth).
14. Watching (not ``--headless``): ``ReplayControls`` (glitchygames/replay/controls.py) take
    the viewer's real key presses and releases; none reaches the game. ``hold_frame`` drives
    the viewer: with no outer tick open it sleeps until the next one, drains the real queue
    and acts on the keys read since the last tick (once per press; a key already down when
    the replay starts acts only after its release); it then answers False for each inner frame
    the open tick runs and True when the tick closes, refreshing the status line (showing the
    real speed while the viewer cannot keep up); the scene manager then presents that frame.
    Inner frames are not presented (``presents_frames`` is False). The start screen
    (``ReplayOptions.wait_for_start``) holds the loop after frame 0, so the first frame's
    picture is behind the message (frame 0's sounds play before Space, and a one-frame
    recording reaches its end at the start screen). The loop is also
    held while paused (until a step) and once the recording is used up. At a divergence or the
    end the replay pauses with the debug overlay on (``ReplayControls.debug_overlay``, the
    scene manager's, handed over by the engine) and a banner (``ReplayControls.banner``)
    instead of stopping; Esc stops it (a run that already ended keeps its end reason, else
    ``'quit'``). The status bar is drawn by ``draw_overlay``. A headless replay never holds and
    has no controls' keys: its KEYDOWN and KEYUP stay blocked.
15. Step back (``,``), Home and D restart the replay (glitchygames/replay/rebuild.py, whose
    docstring is the contract): a control tick that takes the controls' restart request
    (``ReplayControls.take_restart_request``) stops the replay with ``ReplayResult.restart_frame``
    set and the end reason ``'restart'``, and the engine relaunches it once torn down. A replay
    given ``ReplayOptions.pause_at_frame`` N (watched only: a headless replay ignores it, as
    nobody could unpause it) rebuilds: without its start screen, frames run unpresented and
    unpaced in silence (``Rebuild.silence_frame`` after each; ``hold_frame`` never holds, except
    every ``REBUILD_PROGRESS_INTERVAL_SECONDS`` of real time to present the progress line and read
    the viewer's keys), until frame ``max(N, FIRST_PAUSED_FRAME)`` is the next to run; there it
    pauses. A divergence or the end of the recording on the way pauses it there instead (rule
    14). ``ReplayOptions.viewer_state`` restores the viewer's speed, debug panel and the
    divergence frame an earlier run found.
16. Bookmarks (watched): B bookmarks the frame the status line shows
    (``ReplayControls.bookmarks``, frame N meaning paused with frame N next). S
    (``ReplaySources.bookmarks``, saved by the control tick) writes a copy of the recording
    (``write_bookmarked_copy``) to ``bookmarked_copy_path``, with a
    ``{'kind': 'breakpoint', 'label': 'bookmark'}`` control event appended to frame N - 1 (the
    frame whose picture was shown) for each bookmark N (one already there is not added again;
    other control events are kept). The same bookmarks as the last save are not written again
    (unless that copy was deleted since). The copy's header names its source
    (``bookmarked_copy_of``); only a file with that field is updated in place (written aside and
    moved in), so an original is never written, even one named like a copy, nor a copy of
    another recording; a copy an earlier session saved from the same source keeps its
    bookmarks (they are added to the viewer's). The copy replays as its source does: a cut-off
    source gives ``source_truncated`` (the copy ends as truncated) and a version-2 source
    ``input_capture_format_version`` (polled input reads as idle, markers are not compared).
    With no bookmarks nothing is written and the viewer is told so. A breakpoint is re-applied
    on its frame (glitchygames/supervision.py) and is not compared, so the copy replays exactly
    as the original; a watched replay pauses when it applies one
    (``ReplayControls.pause_at_breakpoint``, a control event handler the engine registers),
    except while rebuilding, so a saved copy reopens and stops at each bookmark. A recording's
    bookmark breakpoints are the viewer's bookmarks from the start, so S keeps them. A restart
    (rule 15) with bookmarks saves the copy first and replays the copy
    (``GameEngine._restart_replay``, which warns naming the bookmarks if the copy cannot be
    saved), so bookmarks survive step back.
17. Rebaseline (``--replay-trace OLD --rebaseline NEW --headless``; glitchygames/replay/
    rebaseline.py, whose docstring is the contract): ``start_replay`` gives the replay
    ``stop_on_divergence=False`` and ``ReplayExitPolicy.SUCCESS_AFTER_WRITING``, and the engine
    records the run over it into NEW (``RecordingSources`` with ``replayed`` set: origins and
    the saves and device fields come from this replay, never from the live trackers). It also
    gives it ``captures_scene_starts=True``, so the scenes the replayed code builds capture their
    starts and NEW holds them (``scene_start``, frame 0's included), as a ``--record-trace``
    recording does; a recording's ``scene_start`` fields are never compared (the replayed code
    captures its own). A rebaseline is also how a recording made before logical names
    (glitchygames/logical_names.py: no ``game`` in its header, no ``scene`` in its scene starts)
    of a game that has moved since is converted: under ``--rebaseline`` such a recording's game
    is matched by its class's qualified name alone, its module may differ, and so are its scene
    starts' scenes (``modules_not_compared``, the one rule ``check_recorded_game`` and
    ``find_scene_class`` share; several loaded classes of that name are still refused); NEW
    holds the current logical names. A plain replay of such a recording is refused
    (``ExitCode.UNUSABLE_INPUT``) with a message naming
    ``--replay-trace OLD --rebaseline NEW --headless``. There is no table of former locations.
    A recording whose classes moved to another logical module is converted the same way (the
    logical modules are not compared, the qualified names are); a plain replay refuses it,
    naming the rebaseline.
18. Playback (Part 3's in-game playback scope, glitchygames/replay/playback.py, whose docstring
    is the contract): ``playback_replay_sources`` builds the sources a scope serves a
    recording's frames from, starting at ``ReplayOptions.start_frame`` N (the frame holding the
    rebuilt scene's ``scene_start``). They behave as a headless replay's that nobody watches:
    no viewer, controls, start screen or overlay; they never hold, pause or pace (the scope
    uses the installed doors' pacing and presenting) and stop at the recording's end or first
    divergence; no game check, recorded options or seed are applied, and no report is printed
    and no exit code given (the scope keeps the result). The frames before N are not served:
    what they took in is learned when the sources are made (opened devices, saves first
    opened, the polled input they changed; not enumeration answers, which those frames
    consumed), and the sprite ids continue the recording's (``StableSpriteIds``'s
    ``recorded_ids``: the ids those frames gave, but those frame N holds, which are the
    replayed scene's own, sampled already between its setup and its first logic frame), so
    frame N is compared as recorded. Saves start from the scene start's
    save view, over the header's. The internal events of frame N's first batch that were posted
    before the scene began (``ReplayOptions.earlier_internal_event_count``, from its start's
    first logic frame; glitchygames/scene_start.py, rule 7) are served from the recording, as
    external ones are, and not compared; so are the events frame N's ``redelivered_events``
    holds (a playback scope's held events, delivered before its first pump: they belong to the
    frame, but no door pumped them), first in its first batch
    (``ReplayOptions.serves_redelivered_events``). Frame indexes stay the recording's (rule 3,
    offset by N):
    divergences name recording frames, and ``ReplayResult.frames_replayed`` counts up to the
    last compared recording frame.
    A later frame holding a ``resume_bridge`` (an instant-replay journal's: its scene resumed
    there after a playback scope; glitchygames/instant_replay.py, rule 7) begins as the start
    frame does: the bridge is kept for the frame (``frame_bridge``: the playback scope sets the
    frame clock, the FPS event timer and the polled input from it at the top of the frame), the
    polled input before it is the bridge's, the first ``earlier_internal_event_count`` internal
    events of its first batch are served from the recording, uncompared, and its
    ``redelivered_events`` come first in its first pump: the external ones served, the internal
    ones (the scene's own posts from before the scope, which the playback ran) matched with the
    live posts. A frame's ``playback_answers`` are kept for the frame
    (``recorded_playback_answers``): the playback scope answers the replayed code's playback
    requests with them (glitchygames/replay/playback.py, ``answered_playback_request``).
19. Seed (``--random-seed``; the user's decisions, 2026-10-26): a replay runs under its
    recording's seed (``random_seed``), unless given another (``ReplayOptions.random_seed``,
    which ``start_replay`` reads before the recorded options are applied). Given the recorded
    one, nothing changes. Given another, the replay is reseeded (``ReplaySources.is_reseeded``):
    the recording's inputs are played out under it (the engine's streams are seeded with it,
    here and in the engine), a difference never stops it (as in rule 17), and the run's
    ``random_seed`` option names it. A reseeded rebaseline writes NEW under that seed (NEW's
    header and options name it); a plain reseeded replay writes nothing and exits ``SUCCESS``
    whatever it found (``ReplayExitPolicy.SUCCESS_WITHOUT_COMPARING``), its report the
    rebaseline's summary of what differed. ``--audit`` is a check, so the engine refuses one
    under another seed.
20. Onion skin (``--compare-trace OLD``; glitchygames/replay/tools/compare.py, whose docstring
    is the contract): a watched replay's ``onion_skin`` draws OLD's frame of the same number
    over the presented copy of the frame shown (``draw_overlay``, before the status bar; not
    while rebuilding, though ``hold_frame`` begins it as a rebuild starts, so OLD's child
    rebuilds alongside), and a headless child's ``frame_sink`` takes each replayed game frame
    (glitchygames/game_frames.py) as it is presented: the engine makes such a replay draw its
    overlay (``draws_overlay``), and its ``draw_overlay`` hands the presented frame over instead
    of drawing (a scene switched to after the frame was presented never shows in it); ``False``
    back stops the replay at the frame's end (``frame_sink_closed``: nobody reads). Neither
    changes what is replayed or compared.
"""

from __future__ import annotations

import collections
import dataclasses
import enum
import importlib.metadata
import itertools
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol, Self, cast

import pygame
from pydantic import BaseModel, ConfigDict, Field

from glitchygames.clock import measured_seconds
from glitchygames.events import FPSEVENT
from glitchygames.exit_codes import ExitCode
from glitchygames.game_frames import game_frame_clock
from glitchygames.input.devices import (
    DeviceDescriptor,
    EnumerationAnswer,
    ReplayDeviceRegistry,
    ReplayJoystick,
)
from glitchygames.input.state import IDLE_INPUT, apply_snapshot_changes
from glitchygames.live_sources import LiveSources
from glitchygames.logical_names import logical_name
from glitchygames.output_files import write_aside_then_replace
from glitchygames.randomness import seed_engine_random
from glitchygames.recording import (
    CONTROL_EVENTS_FIELD,
    DEVICE_ENUMERATION_FIELD,
    DEVICES_HEADER_FIELD,
    DEVICES_OPENED_FIELD,
    DT_FIELD,
    EVENT_BATCHES_FIELD,
    EVENT_NAME_FIELD,
    EVENT_ORIGIN_FIELD,
    EVENT_TYPE_FIELD,
    EXTERNAL_ORIGIN,
    INPUT_CHANGES_FIELD,
    INTERNAL_ORIGIN,
    PLAYBACK_ANSWERS_FIELD,
    RECORDED_AT_HEADER_FIELD,
    REDELIVERED_EVENTS_FIELD,
    RESUME_BRIDGE_FIELD,
    SAVES_HEADER_FIELD,
    SAVES_OPENED_FIELD,
    WINDOW_REFERENCE,
    RecordedReference,
    RecordingSources,
    UnrepresentableValue,
    event_from_record,
    event_to_record,
    forget_pending_posts,
    is_input_post,
    pending_internal_posts,
    recorded_start_time,
    start_tracking_internal_posts,
    stop_tracking_internal_posts,
    take_matching_post,
    value_from_json,
)
from glitchygames.recording_history import (
    CONTENT_HASH_FIELD,
    MEASUREMENT_FRAME_FIELDS,
    PROCESSING_SECONDS_FIELD,
    frame_content_hash,
    latest_measurement_run,
)
from glitchygames.replay.audit import frame_digest, write_digest_file
from glitchygames.replay.controls import (
    BREAKPOINT_LABEL_FIELD,
    FIRST_PAUSED_FRAME,
    ReplayControls,
    Reseeding,
)
from glitchygames.replay.input_blocking import REAL_INPUT_EVENT_TYPES, EventTypeBlock
from glitchygames.replay.processing import (
    ProcessingComparison,
    ProcessingSummary,
    machine_description,
)
from glitchygames.replay.rebuild import Rebuild, ViewerState
from glitchygames.replay.viewer import ReplayViewer
from glitchygames.scene_start import ResumeBridge
from glitchygames.sources import frame_clock_seconds
from glitchygames.state.sandbox import MemorySaveManager
from glitchygames.supervision import (
    BREAKPOINT_KIND,
    KIND_FIELD,
    REAPPLIED_CONTROL_EVENT_KINDS,
    ControlEvent,
)
from glitchygames.tracing import (
    BOOKMARKED_COPY_OF_HEADER_FIELD,
    FRAMES_FIELD,
    RECT_FIELD,
    SCENE_FIELD,
    SPRITE_ID_FIELD,
    SPRITES_FIELD,
    TRACE_FORMAT_VERSION,
    StableSpriteIds,
    TraceFormatError,
    TraceReadResult,
    is_bookmarked_copy,
    read_trace_result,
    sample_scene_frame,
    write_trace,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from glitchygames.input.state import InputSnapshot
    from glitchygames.scene_start import SceneStart
    from glitchygames.scenes import Scene
    from glitchygames.sources import EngineSources
    from glitchygames.state.manager import SaveManager

LOG = logging.getLogger('game.replay')
LOG.addHandler(logging.NullHandler())

# Options the recording never overrides: how this run is watched, logged, paced and recorded,
# not what the game does
REPLAY_LOCAL_OPTIONS: frozenset[str] = frozenset({
    'replay_trace',
    'record_trace',
    'audit',
    'replay_digest',
    'headless',
    'rebaseline',
    'replay_pause_at_frame',
    'replay_restart_handoff',
    'replay_viewer_state',
    'replay_fps',
    # --compare-trace's options and its child's frame stream (glitchygames/replay/tools/
    # compare.py): how this run is watched
    'compare_trace',
    'compare_alpha',
    'replay_frame_stream',
    'compare_processing',
    'max_processing_slowdown',
    'profile',
    'log_level',
    'windowed',
    'video_driver',
    'debug_overlay',
    'log_timer_jitter',
    'timer_backend',
    'sleep_granularity_ns',
    'windows_timer_1ms',
    'perf_trim_percent',
    'fps_histogram',
    # --debug-events: whether unhandled events are logged, not what the game does
    'debug_events',
})

# How many frames before a sprite divergence its report lists (with the divergent frame itself)
REPORT_HISTORY_FRAMES = 20

# --replay-fps values: FPS events (and the performance statistics) from the recorded frame times
# (exact, compared) or from this machine's measured frame times (not compared)
RECORDED_REPLAY_FPS: Final = 'recorded'
REAL_REPLAY_FPS: Final = 'real'
REPLAY_FPS_CHOICES = (RECORDED_REPLAY_FPS, REAL_REPLAY_FPS)
REAL_REPLAY_FPS_NOTICE = (
    '--replay-fps real: FPS events follow this machine and are not compared; sprites that draw '
    'the FPS value may diverge'
)

# Divergence kinds
SPRITE_DIVERGENCE = 'sprite'
SCENE_DIVERGENCE = 'scene'
EVENT_DIVERGENCE = 'event'
LENGTH_DIVERGENCE = 'length'

# ReplayResult.end_reason values
RUNNING_END_REASON = 'running'
END_OF_RECORDING_END_REASON = 'end_of_recording'
DIVERGED_END_REASON = 'diverged'
TRUNCATED_END_REASON = 'truncated'
QUIT_END_REASON = 'quit'
RESTART_END_REASON = 'restart'

# Divergence subjects and fields that are not a sprite id or a sprite field
SCENE_SUBJECT = 'scene'
SCENE_CLASS_FIELD = 'class'
PRESENT_FIELD = 'present'
VISIBLE_FIELD = 'visible'
RECORDING_SUBJECT = 'recording'
FRAME_COUNT_FIELD = 'frames'
PUMP_COUNT_FIELD = 'pump count'
MISSING_INTERNAL_EVENT_FIELD = 'missing internal event'
UNEXPECTED_INTERNAL_EVENT_FIELD = 'unexpected internal event'
CONTROL_EVENT_FIELD = 'control event'

# The first format version whose frames record control events (older ones have no markers to
# compare)
CONTROL_EVENTS_FORMAT_VERSION = 3

# Header fields the replay reads
GAME_CLASS_HEADER_FIELD = 'game_class'
GAME_MODULE_HEADER_FIELD = 'game_module'
# The game class's logical name (glitchygames/logical_names.py), which replays compare
GAME_HEADER_FIELD = 'game'
# The module name of a file run as a script (python paddleslap.py)
SCRIPT_MODULE_NAME = '__main__'
RANDOM_SEED_HEADER_FIELD = 'random_seed'
ENGINE_VERSION_HEADER_FIELD = 'engine_version'
OPTIONS_HEADER_FIELD = 'options'
# The (width, height) of the display the recorded run had (GameEngine.trace_recording_header);
# the replay opens its window at it (rule 1)
SCREEN_SIZE_HEADER_FIELD = 'screen_size'

# The viewer's keys: left unblocked at SDL during a watched replay and handed to its controls
# (rule 14), never to the game
WATCHED_REAL_KEY_EVENT_TYPES: frozenset[int] = frozenset({pygame.KEYDOWN, pygame.KEYUP})

# A watched replay's banner once the recording is used up (rule 14)
END_OF_RECORDING_BANNER = 'End of recording'
TRUNCATED_RECORDING_BANNER = 'End of recording (the file is truncated)'

# The frame fields a recording made over a replay copies from it (recorded_frame_fields)
REBASELINE_FRAME_FIELDS = (SAVES_OPENED_FIELD, DEVICES_OPENED_FIELD, DEVICE_ENUMERATION_FIELD)

# Bookmarks (rule 16): the control event each bookmark adds to the saved copy, and the copy's name
# (x.jsonl.gz -> x.bookmarked.jsonl.gz)
BOOKMARK_LABEL = 'bookmark'
BOOKMARK_CONTROL_EVENT = ControlEvent(
    kind=BREAKPOINT_KIND, data={BREAKPOINT_LABEL_FIELD: BOOKMARK_LABEL}
)
# Header fields a bookmarked copy carries, so it replays as its source does: the source file's
# name (only a file with it is updated in place), whether the source was cut off (the copy then
# ends as truncated), and the source's format version when it is older than the copy's (a
# version-2 source: polled input reads as idle and control events are not compared). The first,
# BOOKMARKED_COPY_OF_HEADER_FIELD, is glitchygames/tracing.py's (is_bookmarked_copy reads it)
SOURCE_TRUNCATED_HEADER_FIELD = 'source_truncated'
INPUT_CAPTURE_FORMAT_HEADER_FIELD = 'input_capture_format_version'
RECORDING_FILE_SUFFIX = '.jsonl.gz'
BOOKMARKED_COPY_MARK = '.bookmarked'
NO_BOOKMARKS_MESSAGE = 'no bookmarks to save'
NO_RECORDING_FILE_MESSAGE = 'no recording file to copy the bookmarks into'
ALREADY_SAVED_MESSAGE = 'bookmarks already saved to {name}'

VERSION_TWO_INPUT_WARNING = (
    'The recording is format version %d, recorded before input-state capture; polled input '
    'will read as idle'
)


class FrameSink(Protocol):
    """Takes each replayed frame as presented (``ReplaySources.frame_sink``; rule 20)."""

    def write_frame(self, *, frame_index: int, surface: pygame.Surface) -> bool:
        """Take the frame just replayed; return False to stop the replay (nobody takes more)."""
        ...


class FrameOverlay(Protocol):
    """Draws over a presented frame: a watched replay's (``ReplaySources.onion_skin``; rule 20).

    Live play's too (``HostSources.overlay``; rule 9 of glitchygames/replay/tools/compare.py).
    """

    def begin(self) -> None:
        """Get ready to draw (start what it needs), drawing nothing yet; idempotent."""
        ...

    def draw(self, *, surface: pygame.Surface, frame_index: int) -> None:
        """Draw over the presented copy of frame ``frame_index``."""
        ...


class ReplayRefusedError(RuntimeError):
    """The recording cannot be replayed by this game (a recording of another game)."""


class ReplayExitPolicy(enum.Enum):
    """What a replay's run exits with once it is over (``ReplayResult.exit_code``)."""

    # ReplayResult.exit_code: SUCCESS when matched, REPLAY_DIVERGED, UNUSABLE_INPUT when truncated
    RESULT = 'result'
    # ExitCode.SUCCESS whatever the result (--rebaseline: the new recording is the outcome),
    # but ExitCode.REBASELINE_INPUT_LOST when the run lost recorded input
    SUCCESS_AFTER_WRITING = 'success'
    # ExitCode.SUCCESS whatever the result: a replay under another seed than recorded
    # (--random-seed N; rule 19), which plays the recording's inputs out and compares nothing
    SUCCESS_WITHOUT_COMPARING = 'success-without-comparing'


class ReplayOptions(BaseModel):
    """How a replay is run: everything ``ReplaySources`` is configured with but the recording.

    Read-only; ``start_replay`` builds it from the run's local options (``REPLAY_LOCAL_OPTIONS``,
    never the recording's). Later replay tasks add their fields here (a playback start frame).

    Attributes:
        headless: True under ``--headless``: frames are not paced (rule 13) and the engine prints
            the report to stdout (rule 11).
        exit_policy: What the run exits with once it is over (``ReplayResult.exit_code``).
        fps_source: ``RECORDED_REPLAY_FPS`` or ``REAL_REPLAY_FPS`` (``--replay-fps``; rule 4).
        digest_path: Where ``finish_run`` writes the frame digests (``--replay-digest``; rule
            12), or None.
        use_fastevents: Drain the real queue with pygame.fastevent when pygame has it
            (``GameEngine.USE_FASTEVENTS``), as the live doors would.
        wait_for_start: True to hold a watched replay at its start screen before frame 0 until
            the viewer presses Space (rule 14); ``start_replay`` sets it for every watched
            replay. A headless replay never waits, whatever this says.
        pause_at_frame: The frame a restarted watched replay rebuilds up to and pauses at
            (``--replay-pause-at-frame``; rule 15), or None. A headless replay ignores it.
        restart_handoff_path: Where a restarted replay hands its own restart to the
            supervising process (``--replay-restart-handoff``; glitchygames/replay/rebuild.py),
            or None in the first replay process.
        viewer_state: The viewer's state a restarted replay starts with
            (``--replay-viewer-state``: speed, debug panel, divergence frame), or None.
        recording_path: The recording's file, which a saved bookmarked copy is copied from
            (rule 16; ``start_replay`` sets it), or None (nothing can be saved).
        stop_on_divergence: True (the default) to end the comparison at the first difference
            (rule 8); False to note every differing frame and run on to the end
            (``--rebaseline``, rule 17).
        captures_scene_starts: True when scenes the replayed code builds capture their starts
            (``EngineSources.captures_scene_starts``; glitchygames/scene_start.py): a
            rebaseline's new recording holds them (rule 17). False (the default) for a replay
            that records nothing.
        start_frame: The recording frame served first (rule 18: an in-game playback of a
            scene that began on a later frame). 0 (the default) for every other replay.
        earlier_internal_event_count: How many internal records of the start frame's first
            batch were posted before the replayed scene began (glitchygames/scene_start.py,
            rule 7): served from the recording, not compared (rule 18). 0 for every other
            replay.
        serves_redelivered_events: True to deliver the start frame's recorded
            ``redelivered_events`` before its first pump (a playback, rule 18); False for every
            other replay, which redelivers them itself as the recorded run did.
        compare_processing: True to compare each frame's processing time with the recorded
            one (``--compare-processing``; glitchygames/replay/processing.py).
        max_processing_slowdown_percent: The slowdown a replay that matched may show before it
            exits ``PROCESSING_SLOWER`` (``--max-processing-slowdown``), or None for no check.
        random_seed: The master seed the replay runs the recording's inputs under in place of
            the recorded one (``--random-seed N``; rule 19), or None (the default) for the
            recorded seed. A seed other than the recorded one makes the replay reseeded
            (``ReplaySources.is_reseeded``).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    headless: bool = False
    exit_policy: ReplayExitPolicy = ReplayExitPolicy.RESULT
    fps_source: Literal['recorded', 'real'] = RECORDED_REPLAY_FPS
    digest_path: Path | None = None
    use_fastevents: bool = False
    wait_for_start: bool = False
    pause_at_frame: int | None = Field(default=None, ge=0)
    restart_handoff_path: Path | None = None
    viewer_state: ViewerState | None = None
    recording_path: Path | None = None
    stop_on_divergence: bool = True
    captures_scene_starts: bool = False
    start_frame: int = Field(default=0, ge=0)
    earlier_internal_event_count: int = Field(default=0, ge=0)
    serves_redelivered_events: bool = False
    compare_processing: bool = False
    max_processing_slowdown_percent: float | None = Field(default=None, ge=0)
    random_seed: int | None = None


# The options of a replay given none (a test's, a tool's): watched without the start screen,
# recorded FPS, no digests
DEFAULT_REPLAY_OPTIONS = ReplayOptions()


class RecordedFrames:
    """The recording's complete frames, read by index (``ReplaySources.recording``).

    Attributes:
        is_truncated: True when the file was cut off (a killed recorder).

    """

    def __init__(self: Self, *, frames: Sequence[dict[str, Any]], is_truncated: bool) -> None:
        """Keep the decoded frames.

        Args:
            frames: Every complete recorded frame, decoded (glitchygames/tracing.py).
            is_truncated: True when the file was cut off after the last of them.

        """
        self._frames = frames
        self.is_truncated = is_truncated

    @property
    def frame_count(self: Self) -> int:
        """How many complete frames the recording holds."""
        return len(self._frames)

    @property
    def frames(self: Self) -> Sequence[dict[str, Any]]:
        """Every complete frame, decoded (a rebaseline summarises the earlier runs from them)."""
        return self._frames

    def frame(self: Self, *, frame_index: int) -> dict[str, Any] | None:
        """Return a recorded frame, or None past the end of the recording.

        Args:
            frame_index: The recording's frame index (not negative).

        Returns:
            The decoded frame, or None.

        """
        if frame_index < len(self._frames):
            return self._frames[frame_index]
        return None

    def recorded_dt(self: Self, *, frame_index: int) -> float:
        """Return a frame's recorded ``dt``: the duration of the frame before it (rule 4).

        Args:
            frame_index: The recording's frame index.

        Returns:
            Seconds.

        """
        return float(self._frames[frame_index][DT_FIELD])

    def recorded_frame_fields(self: Self, *, frame_index: int) -> dict[str, Any]:
        """Return the recorded frame's save and device fields (rule 10; a rebaseline copies them).

        Args:
            frame_index: The recording's frame index.

        Returns:
            Whichever of ``saves_opened``, ``devices_opened`` and ``device_enumeration`` the
            frame has; none past the end of the recording (a frame the recording does not have
            took nothing in from it).

        """
        frame = self.frame(frame_index=frame_index)
        if frame is None:
            return {}
        return {
            field_name: frame[field_name]
            for field_name in REBASELINE_FRAME_FIELDS
            if field_name in frame
        }

    def recorded_frame_histories(self: Self, *, frame_index: int) -> dict[str, Any]:
        """Return the recorded frame's histories (a rebaseline stacks its own in front).

        Args:
            frame_index: The recording's frame index.

        Returns:
            Whichever of ``content_hash`` and ``processing_seconds`` the frame has; none past the
            end of the recording.

        """
        frame = self.frame(frame_index=frame_index)
        if frame is None:
            return {}
        return {name: frame[name] for name in MEASUREMENT_FRAME_FIELDS if name in frame}


class BookmarkedCopy:
    """Saves the viewer's bookmarks into a copy of the recording (``ReplaySources.bookmarks``).

    Rule 16: S asks for a save (the control tick calls ``save``), and
    ``GameEngine._restart_replay`` saves before a restart with bookmarks.
    """

    def __init__(
        self: Self,
        *,
        controls: ReplayControls,
        recording_path: Path | None,
        is_bookmarked_copy: bool,
    ) -> None:
        """Keep what a save needs.

        Args:
            controls: The watched replay's controls (their ``bookmarks``, and where the outcome
                is shown); their bookmarks start as the recording's own.
            recording_path: The file the recording was read from
                (``ReplayOptions.recording_path``), or None.
            is_bookmarked_copy: True when the recording is a bookmarked copy: its bookmarks
                are already saved in it.

        """
        self._controls = controls
        self._recording_path = recording_path
        # The bookmarks last saved and where (a save of the same ones writes nothing)
        self._saved_bookmarks: list[int] | None = None
        self._saved_path: Path | None = None
        if is_bookmarked_copy and recording_path is not None:
            self._saved_bookmarks = list(controls.bookmarks)
            self._saved_path = recording_path

    def save(self: Self) -> Path | None:
        """Save a copy of the recording with the bookmarks as breakpoints.

        The viewer is told the outcome (``ReplayControls.show_message``), and it is logged.

        The same bookmarks as the last save (or as a bookmarked copy being replayed holds) are
        not written again, unless that copy has been deleted since.

        Returns:
            The copy's path (already saved, or just written), or None when there is no copy:
            no bookmarks, no recording file (sources made from frames in memory), or the copy
            could not be written.

        """
        bookmarks = list(self._controls.bookmarks)
        if not bookmarks:
            self._controls.show_message(text=NO_BOOKMARKS_MESSAGE)
            return None
        if self._recording_path is None:
            self._controls.show_message(text=NO_RECORDING_FILE_MESSAGE)
            return None
        if (
            self._saved_path is not None
            and bookmarks == self._saved_bookmarks
            # A copy deleted since it was saved is written again
            and self._saved_path.exists()
        ):
            self._controls.show_message(
                text=ALREADY_SAVED_MESSAGE.format(name=self._saved_path.name)
            )
            return self._saved_path
        destination = bookmarked_copy_path(recording_path=self._recording_path)
        try:
            write_bookmarked_copy(
                recording_path=self._recording_path, bookmarks=bookmarks, destination=destination
            )
        # A TraceFormatError (the file changed since it was read) is a ValueError
        except (OSError, ValueError) as error:
            LOG.exception('Could not save bookmarks %s to %s', bookmarks, destination)
            self._controls.show_message(text=f'could not save bookmarks: {error}')
            return None
        LOG.info('Saved bookmarks %s to %s', bookmarks, destination)
        self._controls.show_message(text=f'bookmarks saved to {destination.name}')
        self._saved_bookmarks = bookmarks
        self._saved_path = destination
        return destination


@dataclasses.dataclass(frozen=True)
class Divergence:
    """The first difference between the replay and the recording.

    Attributes:
        frame_number: The recording's frame index.
        kind: ``SCENE_DIVERGENCE``, ``SPRITE_DIVERGENCE``, ``EVENT_DIVERGENCE`` or
            ``LENGTH_DIVERGENCE``.
        subject: What differed: a sprite id, ``'scene'``, ``'recording'``, an event's name or
            a control event's kind.
        field: Which of its fields: ``'rect'``, ``'visible'``, ``'present'``, ``'class'``,
            ``'frames'``, ``'pump count'``, ``'missing internal event'``,
            ``'unexpected internal event'``, ``'control event'``.
        expected: The recorded value (None when the replay has something the recording has not).
        actual: The replayed value (None when the replay is missing something recorded).

    """

    frame_number: int
    kind: str
    subject: str
    field: str
    expected: object
    actual: object

    def describe(self: Self) -> str:
        """Describe the divergence on one line.

        Returns:
            For example ``frame 6120: sprite Ball#2 rect expected [412, 300, 16, 16], got
            [412, 301, 16, 16]``, or for a different active scene ``frame 40: scene expected
            ArrivalScene, got PauseScene``.

        """
        return f'frame {self.frame_number}: {self.describe_difference()}'

    def describe_difference(self: Self) -> str:
        """Describe what differed, without the frame.

        Returns:
            For example ``sprite Ball#2 rect expected [412, 300, 16, 16], got [412, 301, 16,
            16]``, or ``scene expected ArrivalScene, got PauseScene``.

        """
        if self.kind == SCENE_DIVERGENCE:
            return f'scene expected {self.expected}, got {self.actual}'
        return (
            f'{self.kind} {self.subject} {self.field} expected {self.expected}, got {self.actual}'
        )


def _new_frame_history() -> collections.deque[tuple[int, list[dict[str, Any]]]]:
    """Return an empty history of the last compared frames (``REPORT_HISTORY_FRAMES`` + 1).

    Returns:
        A deque of (recording frame index, sampled sprites) that keeps the newest entries.

    """
    return collections.deque(maxlen=REPORT_HISTORY_FRAMES + 1)


def _describe_history_sprite(*, sprites: list[dict[str, Any]], sprite_id: str) -> str:
    """Describe one sprite of a frame for the divergence report.

    Returns:
        ``[x, y, width, height] visible`` (or ``hidden``), or ``absent`` when the frame does
        not have the sprite.

    """
    for sprite in sprites:
        if sprite[SPRITE_ID_FIELD] == sprite_id:
            visibility = 'visible' if sprite[VISIBLE_FIELD] else 'hidden'
            return f'{sprite[RECT_FIELD]} {visibility}'
    return 'absent'


@dataclasses.dataclass
class ReplayResult:
    """How a replay went so far.

    Attributes:
        frames_replayed: How many recorded frames were run and compared.
        divergence: The first difference, or None.
        end_reason: ``'running'``, ``'end_of_recording'``, ``'diverged'``, ``'truncated'``
            (the last complete frame of a cut-off file was replayed), ``'quit'`` (the
            window was closed, or Esc was pressed in a watched replay, before the end) or
            ``'restart'`` (the viewer stepped back before the end: rule 15).
        restart_frame: The frame the replay restarts at (rule 15), or None. Set by a step back
            even after the replay ended (a divergence keeps its end reason).
        recorded_history: The last compared frames as recorded: (recording frame index, its
            sprites), up to ``REPORT_HISTORY_FRAMES`` + 1. ``ReplaySources.end_frame`` adds each
            compared frame up to and including the first divergent one, then stops, so once the
            replay diverged the history ends there (even when the replay runs on past it).
        replayed_history: The same frames as the replay sampled them.
        differing_frame_count: How many compared frames differed from the recording (at most 1
            unless ``ReplayOptions.stop_on_divergence`` is False).
        affected_sprite_ids: Every sprite that differed in those frames, in the order first
            found (``differing_sprite_ids``).
        frames_recorded: How many complete frames the recording holds.
        undelivered_input_count: Recorded external events the run never received: those in
            batches of a compared frame that the frame did not pump (it pumped fewer times than
            recorded). Events of frames never replayed are not counted here (see
            ``frames_recorded``).
        first_undelivered_input_frame: The frame of the first of them, or None.
        processing_comparison: Collects each frame's processing time beside the recorded one
            while comparing them (``--compare-processing``), else None.
        processing: How this replay's processing time compared with the recording's
            (glitchygames/replay/processing.py), settled by ``finish_run``; None when not
            compared.
        max_processing_slowdown_percent: The slowdown a matched replay may show
            (``--max-processing-slowdown``), or None for no check.
        shown_game_frames: With an onion skin, the game frame each frame run showed
            (glitchygames/game_frames.py), by frame index (None: no game frame yet); a step
            back's restart starts OLD's child at one (rule 8 of
            glitchygames/replay/tools/compare.py). Empty without one.

    """

    frames_replayed: int = 0
    divergence: Divergence | None = None
    end_reason: str = RUNNING_END_REASON
    restart_frame: int | None = None
    shown_game_frames: dict[int, int | None] = dataclasses.field(default_factory=dict, repr=False)
    recorded_history: collections.deque[tuple[int, list[dict[str, Any]]]] = dataclasses.field(
        default_factory=_new_frame_history, repr=False
    )
    replayed_history: collections.deque[tuple[int, list[dict[str, Any]]]] = dataclasses.field(
        default_factory=_new_frame_history, repr=False
    )
    differing_frame_count: int = 0
    affected_sprite_ids: list[str] = dataclasses.field(default_factory=list[str])
    frames_recorded: int = 0
    undelivered_input_count: int = 0
    first_undelivered_input_frame: int | None = None
    processing_comparison: ProcessingComparison | None = dataclasses.field(default=None, repr=False)
    processing: ProcessingSummary | None = None
    max_processing_slowdown_percent: float | None = None

    @property
    def has_lost_input(self: Self) -> bool:
        """True when the run never received some recorded input (a rebaseline's rule 2).

        That is undelivered events, or frames it never replayed (a run that ended before the
        recording did).
        """
        return self.undelivered_input_count > 0 or self.frames_replayed < self.frames_recorded

    def note_undelivered_inputs(self: Self, *, frame_index: int, count: int) -> None:
        """Count recorded external events a frame never received (its unpumped batches).

        Args:
            frame_index: The recording's frame index.
            count: How many (nothing is noted for 0).

        """
        if count == 0:
            return
        self.undelivered_input_count += count
        if self.first_undelivered_input_frame is None:
            self.first_undelivered_input_frame = frame_index

    def note_differing_frame(self: Self, *, sprite_ids: Sequence[str]) -> None:
        """Count one more differing frame and add the sprites that differ in it.

        Args:
            sprite_ids: The frame's differing sprites (``differing_sprite_ids``), any order.

        """
        self.differing_frame_count += 1
        known_sprite_ids = set(self.affected_sprite_ids)
        for sprite_id in sprite_ids:
            if sprite_id not in known_sprite_ids:
                known_sprite_ids.add(sprite_id)
                self.affected_sprite_ids.append(sprite_id)

    def exit_code(self: Self, *, policy: ReplayExitPolicy) -> ExitCode:
        """Return the exit code the replay's run ends with (glitchygames/exit_codes.py).

        Args:
            policy: The replay's exit policy (``ReplayOptions.exit_policy``).

        Returns:
            Under ``ReplayExitPolicy.SUCCESS_AFTER_WRITING``: ``REBASELINE_INPUT_LOST`` when the
            run lost recorded input (``has_lost_input``), else ``SUCCESS``. Under
            ``ReplayExitPolicy.SUCCESS_WITHOUT_COMPARING``: ``SUCCESS``. Under
            ``ReplayExitPolicy.RESULT``: ``SUCCESS`` when the replay matched to the end of the
            recording or was quit or restarted before it; ``UNUSABLE_INPUT`` when it matched up
            to the cut-off of a truncated recording; ``REPLAY_DIVERGED`` when it diverged, or is
            still running (``finish_run`` turns a run that ended early into a length divergence).
            A replay that would exit ``SUCCESS`` under a processing check
            (``max_processing_slowdown_percent``) exits ``PROCESSING_SLOWER`` when it took
            longer than allowed, and ``UNUSABLE_INPUT`` when the recording holds no processing
            times to check (glitchygames/replay/processing.py).

        """
        if policy == ReplayExitPolicy.SUCCESS_AFTER_WRITING:
            return ExitCode.REBASELINE_INPUT_LOST if self.has_lost_input else ExitCode.SUCCESS
        if policy == ReplayExitPolicy.SUCCESS_WITHOUT_COMPARING:
            return ExitCode.SUCCESS
        if self.divergence is not None:
            return ExitCode.REPLAY_DIVERGED
        if self.end_reason in {END_OF_RECORDING_END_REASON, QUIT_END_REASON, RESTART_END_REASON}:
            return self._processing_check_exit_code()
        if self.end_reason == TRUNCATED_END_REASON:
            return ExitCode.UNUSABLE_INPUT
        return ExitCode.REPLAY_DIVERGED

    def _processing_check_exit_code(self: Self) -> ExitCode:
        """Return a matched replay's exit code under its processing check, if it has one.

        Returns:
            ``SUCCESS``; ``PROCESSING_SLOWER`` when it took more than the allowed slowdown
            longer; ``UNUSABLE_INPUT`` when nothing could be compared.

        """
        if self.max_processing_slowdown_percent is None or self.processing is None:
            return ExitCode.SUCCESS
        if self.processing.frames_compared == 0:
            return ExitCode.UNUSABLE_INPUT
        if self.processing.exceeds(max_slowdown_percent=self.max_processing_slowdown_percent):
            return ExitCode.PROCESSING_SLOWER
        return ExitCode.SUCCESS

    def report(self: Self) -> str:
        """Describe how the replay went, for stdout (``--headless``) or the log.

        Returns:
            One line, e.g. ``Replay matched 9800 frames (end of recording)`` or ``Replay ended
            early at frame 4312: the recording is truncated``; for a sprite divergence, its line
            (``Replay diverged at frame 6120: sprite Ball#2 rect expected [412, 300, 16, 16],
            got [412, 301, 16, 16]``) followed by ``Ball#2, last 20 frames (expected | got):``
            and one ``  6100: [400, 290, 16, 16] visible | [400, 290, 16, 16] visible`` line per
            frame up to the divergent one.

        """
        divergence = self.divergence
        if divergence is not None:
            lines = [f'Replay diverged at {divergence.describe()}']
            if divergence.kind == SPRITE_DIVERGENCE:
                sprite_id = divergence.subject
                lines.append(f'{sprite_id}, last {REPORT_HISTORY_FRAMES} frames (expected | got):')
                for (frame_index, recorded_sprites), (_, replayed_sprites) in zip(
                    self.recorded_history, self.replayed_history, strict=True
                ):
                    expected = _describe_history_sprite(
                        sprites=recorded_sprites, sprite_id=sprite_id
                    )
                    got = _describe_history_sprite(sprites=replayed_sprites, sprite_id=sprite_id)
                    lines.append(f'  {frame_index}: {expected} | {got}')
            return '\n'.join(lines)
        if self.end_reason == END_OF_RECORDING_END_REASON:
            return f'Replay matched {self.frames_replayed} frames (end of recording)'
        if self.end_reason == QUIT_END_REASON:
            return f'Replay matched {self.frames_replayed} frames (quit before the end)'
        if self.end_reason == RESTART_END_REASON:
            return (
                f'Replay matched {self.frames_replayed} frames (restarting at frame '
                f'{self.restart_frame})'
            )
        if self.end_reason == TRUNCATED_END_REASON:
            return f'Replay ended early at frame {self.frames_replayed}: the recording is truncated'
        return f'Replay still running after {self.frames_replayed} frames'


def _recorded_start(*, header: dict[str, Any]) -> datetime:
    """Return the header's ``recorded_at`` as an aware datetime (UTC when it has no offset).

    Raises:
        TraceFormatError: If the header has no readable ``recorded_at``.

    """
    recorded_at = header.get(RECORDED_AT_HEADER_FIELD)
    try:
        start = recorded_start_time(header=header)
    except ValueError as error:
        message = f'The recording header recorded_at {recorded_at!r} is not ISO 8601'
        raise TraceFormatError(message) from error
    if start is None:
        message = f'The recording header has no recorded_at start time (found {recorded_at!r})'
        raise TraceFormatError(message)
    return start


def _recorded_machine(*, header: dict[str, Any]) -> str | None:
    """Return the machine the header's latest run names (``measurement_runs[0]``), or None.

    Returns:
        The machine's description, or None (older recordings name none).

    """
    run = latest_measurement_run(header=header)
    return None if run is None else run.machine


def _recorded_paced(*, header: dict[str, Any]) -> bool | None:
    """Return whether the header's latest run paced its frames, or None when it does not say.

    Returns:
        True or False, or None.

    """
    run = latest_measurement_run(header=header)
    return None if run is None else run.processing_paced


def recorded_screen_size(*, header: Mapping[str, Any]) -> tuple[int, int] | None:
    """Return the header's ``screen_size`` as (width, height), or None when it holds none.

    The engine's recorder always writes it; a header without one was made some other way (by
    hand, by a test).

    Raises:
        TraceFormatError: If the header's ``screen_size`` is not two positive integers.

    """
    screen_size: object = header.get(SCREEN_SIZE_HEADER_FIELD)
    if screen_size is None:
        return None
    match screen_size:
        case [int() as width, int() as height] if (
            not isinstance(width, bool)
            and not isinstance(height, bool)
            and width > 0
            and height > 0
        ):
            return (width, height)
        case _:
            message = (
                f'The recording header screen_size is not a positive [width, height] '
                f'(found {screen_size!r})'
            )
            raise TraceFormatError(message)


def recorded_random_seed(*, header: Mapping[str, Any]) -> int:
    """Return the header's ``random_seed``.

    Raises:
        TraceFormatError: If the header has no integer seed.

    """
    random_seed = header.get(RANDOM_SEED_HEADER_FIELD)
    if isinstance(random_seed, bool) or not isinstance(random_seed, int):
        message = f'The recording header has no integer random_seed (found {random_seed!r})'
        raise TraceFormatError(message)
    return random_seed


def replay_seed_and_options(
    *, recorded_seed: int, options: ReplayOptions
) -> tuple[int, ReplayOptions, bool]:
    """Return the seed a replay runs under, how it runs and whether it is reseeded (rule 19).

    Under another seed than recorded it plays the recording's inputs out without stopping at
    a difference; unless it rebaselines (rule 17: NEW is its outcome), it exits ``SUCCESS``
    whatever it found.

    Args:
        recorded_seed: The recording's seed.
        options: The replay's options as given (``random_seed``: the seed given, or None).

    Returns:
        The seed (the given one, else the recorded one); the options: as given under the
        recorded seed, else with ``stop_on_divergence`` False and, but for a rebaseline's,
        ``ReplayExitPolicy.SUCCESS_WITHOUT_COMPARING``; and whether the seed is another than
        recorded.

    """
    if options.random_seed is None or options.random_seed == recorded_seed:
        return recorded_seed, options, False
    reseeded = options.model_copy(
        update={
            'stop_on_divergence': False,
            'exit_policy': (
                options.exit_policy
                if options.exit_policy == ReplayExitPolicy.SUCCESS_AFTER_WRITING
                else ReplayExitPolicy.SUCCESS_WITHOUT_COMPARING
            ),
        }
    )
    return options.random_seed, reseeded, True


def _sprite_differences(
    *, frame_index: int, recorded: dict[str, Any], replayed: dict[str, Any]
) -> Iterator[Divergence]:
    """Yield the sprite differences between two sampled frames, at most one per sprite.

    Recorded sprites are checked in recorded (draw) order: a missing one, else its rect, else
    its visibility; then each replayed sprite the recording does not have.

    Yields:
        Each sprite's first difference.

    """
    replayed_by_id = {sprite[SPRITE_ID_FIELD]: sprite for sprite in replayed[SPRITES_FIELD]}
    recorded_ids: set[str] = set()
    for recorded_sprite in recorded[SPRITES_FIELD]:
        sprite_id = recorded_sprite[SPRITE_ID_FIELD]
        recorded_ids.add(sprite_id)
        replayed_sprite = replayed_by_id.get(sprite_id)
        if replayed_sprite is None:
            yield Divergence(
                frame_number=frame_index,
                kind=SPRITE_DIVERGENCE,
                subject=sprite_id,
                field=PRESENT_FIELD,
                expected=True,
                actual=False,
            )
            continue
        for field_name in (RECT_FIELD, VISIBLE_FIELD):
            if recorded_sprite[field_name] != replayed_sprite[field_name]:
                yield Divergence(
                    frame_number=frame_index,
                    kind=SPRITE_DIVERGENCE,
                    subject=sprite_id,
                    field=field_name,
                    expected=recorded_sprite[field_name],
                    actual=replayed_sprite[field_name],
                )
                break
    for replayed_sprite in replayed[SPRITES_FIELD]:
        sprite_id = replayed_sprite[SPRITE_ID_FIELD]
        if sprite_id not in recorded_ids:
            yield Divergence(
                frame_number=frame_index,
                kind=SPRITE_DIVERGENCE,
                subject=sprite_id,
                field=PRESENT_FIELD,
                expected=False,
                actual=True,
            )


def differing_sprite_ids(*, recorded: dict[str, Any], replayed: dict[str, Any]) -> list[str]:
    """Name every sprite that differs between a recorded frame and its replay (rule 8).

    Args:
        recorded: The recorded frame (decoded: every sprite listed).
        replayed: The replayed frame, sampled by ``sample_scene_frame``.

    Returns:
        The sprite ids: recorded sprites that are missing or changed (rect or visibility), in
        recorded order, then replayed sprites the recording does not have.

    """
    return [
        divergence.subject
        for divergence in _sprite_differences(frame_index=0, recorded=recorded, replayed=replayed)
    ]


def _take_live_match(
    *,
    unmatched: list[tuple[pygame.event.Event, dict[str, Any]]],
    record: dict[str, Any],
    is_compared: bool,
) -> pygame.event.Event | None:
    """Remove and return the first live internal event that stands for a recorded internal one.

    Args:
        unmatched: The live internal events not matched yet, each with its record (changed in
            place).
        record: The recorded internal event.
        is_compared: True to match equal records only; False (a type that is not compared) to
            match the first live event of the recorded type.

    Returns:
        The live event, or None when none matches.

    """
    recorded_type = record.get(EVENT_TYPE_FIELD)
    for index, (live_event, live_record) in enumerate(unmatched):
        matches = (live_record == record) if is_compared else (live_event.type == recorded_type)
        if matches:
            del unmatched[index]
            return live_event
    return None


def first_frame_difference(
    *, frame_index: int, recorded: dict[str, Any], replayed: dict[str, Any]
) -> Divergence | None:
    """Compare a replayed frame with the recorded one (scene class, then sprites).

    Args:
        frame_index: The recording's frame index.
        recorded: The recorded frame (decoded: every sprite listed).
        replayed: The replayed frame, sampled by ``sample_scene_frame``.

    Returns:
        The first difference, or None when the frames match.

    """
    if recorded[SCENE_FIELD] != replayed[SCENE_FIELD]:
        return Divergence(
            frame_number=frame_index,
            kind=SCENE_DIVERGENCE,
            subject=SCENE_SUBJECT,
            field=SCENE_CLASS_FIELD,
            expected=recorded[SCENE_FIELD],
            actual=replayed[SCENE_FIELD],
        )
    return next(
        _sprite_differences(frame_index=frame_index, recorded=recorded, replayed=replayed), None
    )


class ReplaySources:
    """The replay's doors (implements glitchygames.sources.EngineSources; module docstring).

    Attributes:
        header: The recording's header fields (without ``format_version`` and ``frames``).
        recording: The recorded frames.
        options: How the replay is run (``ReplayOptions``).
        result: How the replay went so far.
        random_seed: The replay's master seed: the recorded one, or one given in its place
            (``ReplayOptions.random_seed``; rule 19).
        recorded_seed: The recording's own master seed (its header's ``random_seed``).
        is_reseeded: True when the replay runs under another seed than recorded (rule 19): it
            never stops at a difference, and its options say so (``stop_on_divergence``
            False; ``ReplayExitPolicy.SUCCESS_WITHOUT_COMPARING`` unless it rebaselines).
        controls: The watched replay's controls (rule 14; unused by a headless replay).
        viewer: The watched replay's outer loop (rule 14, glitchygames/replay/viewer.py).
        bookmarks: Saves the viewer's bookmarks into a copy of the recording (rule 16).
        draws_overlay: True for a watched replay, which draws its status bar
            (``draw_overlay``).
        presents_frames: False for a watched replay, whose viewer presents the latest frame
            once per outer tick.
        captures_scene_starts: Whether scenes built now capture their starts
            (``ReplayOptions.captures_scene_starts``: a rebaseline's).
        start_input: The polled input before the start frame (``IDLE_INPUT`` before frame 0),
            which the start frame's logic reads (``dt_tick`` runs before the frame's pump); a
            playback scope makes it the current input as it begins (rule 18).
        frame_bridge: The current frame's resume bridge, when the recorded scene resumed in it
            after a playback scope (an instant-replay journal's frame; rule 18), else None.
        recorded_playback_answers: The answers the current frame's playback requests got, not
            yet given again (an instant-replay journal's ``playback_answers``; rule 18).
        digest_write_failed: True once ``finish_run`` could not write the digest file (rule
            12; the engine then exits ``ExitCode.CANNOT_WRITE_OUTPUT``).
        frame_sink: Takes each replayed frame as presented (rule 20: a headless child's frame
            stream), or None.
        frame_sink_closed: True once the frame sink took no more (the replay stops at the
            frame's end).
        onion_skin: Draws over each presented frame of a watched replay (rule 20:
            ``--compare-trace``), or None.

    """

    # Set for each frame as it begins (_begin_frame)
    frame_bridge: ResumeBridge | None
    recorded_playback_answers: collections.deque[bool]
    # Set by finish_run when the digest file cannot be written
    digest_write_failed: bool = False
    # Set by the engine for --replay-frame-stream and --compare-trace (rule 20)
    frame_sink: FrameSink | None = None
    frame_sink_closed: bool = False
    onion_skin: FrameOverlay | None = None

    def __init__(
        self: Self,
        *,
        header: dict[str, Any],
        frames: Sequence[dict[str, Any]],
        format_version: int,
        is_truncated: bool = False,
        options: ReplayOptions = DEFAULT_REPLAY_OPTIONS,
    ) -> None:
        """Prepare to serve the recording from its first frame.

        Args:
            header: The header fields.
            frames: Every complete recorded frame, decoded (glitchygames/tracing.py).
            format_version: The file's format version (2 or 3).
            is_truncated: True when the file was cut off (a killed recorder): the replay then
                ends with ``'truncated'`` after the last complete frame.
            options: How the replay is run.

        """
        self.header = header
        # The recorded seed is read (and checked) whatever the replay runs under
        self.recorded_seed = recorded_random_seed(header=header)
        self.random_seed, self.options, self.is_reseeded = replay_seed_and_options(
            recorded_seed=self.recorded_seed, options=options
        )
        self._recorded_at = _recorded_start(header=header)
        # A bookmarked copy of a cut-off recording ends as its source did (rule 16)
        self.recording = RecordedFrames(
            frames=frames,
            is_truncated=is_truncated or header.get(SOURCE_TRUNCATED_HEADER_FIELD) is True,
        )
        self.result = ReplayResult(
            frames_recorded=self.recording.frame_count,
            max_processing_slowdown_percent=options.max_processing_slowdown_percent,
            # Each frame's processing time beside the recorded one (replay/processing.py)
            processing_comparison=(
                ProcessingComparison(
                    recorded_machine=_recorded_machine(header=header),
                    replay_machine=machine_description(),
                    recorded_paced=_recorded_paced(header=header),
                )
                if options.compare_processing
                else None
            ),
        )
        # A bookmarked copy of a version-2 recording replays as version 2 (rule 16)
        input_capture_format_version = header.get(INPUT_CAPTURE_FORMAT_HEADER_FIELD)
        if isinstance(input_capture_format_version, int):
            format_version = min(format_version, input_capture_format_version)
        self.draws_overlay = not options.headless
        self.captures_scene_starts = options.captures_scene_starts
        # Watched, inner frames are not presented: the viewer's outer tick presents the latest
        self.presents_frames = options.headless
        self.controls = ReplayControls(
            total_frames=self.recording.frame_count,
            awaiting_start=options.wait_for_start and not options.headless,
            # Watched, a reseeded replay's status says it is not compared (rule 19)
            reseeding=(
                Reseeding(random_seed=self.random_seed, recorded_seed=self.recorded_seed)
                if self.is_reseeded
                else None
            ),
        )
        self.viewer = ReplayViewer(controls=self.controls)
        # A bookmarked copy's bookmarks are the viewer's from the start, so S keeps them
        self.controls.bookmarks = recorded_bookmarks(frames=frames)
        self.bookmarks = BookmarkedCopy(
            controls=self.controls,
            recording_path=options.recording_path,
            is_bookmarked_copy=BOOKMARKED_COPY_OF_HEADER_FIELD in header,
        )
        # A restarted watched replay rebuilds up to its pause frame (rule 15)
        self._rebuild: Rebuild | None = None
        if options.pause_at_frame is not None and not options.headless:
            self._rebuild = Rebuild(target_frame=max(options.pause_at_frame, FIRST_PAUSED_FRAME))
            self.controls.rebuild_target_frame = self._rebuild.target_frame
        if options.viewer_state is not None:
            # What the viewer had set before the restart (the engine carries the panel over to
            # the scene manager's debug overlay with the controls')
            self.controls.speed = options.viewer_state.speed
            self.controls.debug_overlay.panel = options.viewer_state.debug_panel
            self.controls.divergence_frame = options.viewer_state.divergence_frame
        self._compares_control_events = format_version >= CONTROL_EVENTS_FORMAT_VERSION
        # Frames ended so far (end_frame calls), after the start frame: the index of the frame
        # being served (rule 3; a playback starts at a later frame, rule 18)
        self._frame_index = options.start_frame
        # Pumps so far in the current frame: the index of the batch the next pump serves
        self._pump_index = 0
        # The start frame's earlier internal events still to serve from the recording (rule 18)
        self._earlier_internal_events_to_serve = options.earlier_internal_event_count
        self._stop_requested = False
        self._window_was_closed = False
        self._last_batch_origins: list[str] = []
        # Internal events a held frame drained from the real queue, for the next pump (rule 14)
        self._held_internal_events: list[pygame.event.Event] = []
        # The first difference the current frame's pumps found (reported at end_frame)
        self._frame_divergence: Divergence | None = None
        # One frame_digest per compared frame, kept only when digest_path is set (rule 12)
        self._frame_digests: list[str] = []
        # Joystick instance ids without a stand-in already warned about, and unrepresentable
        # types already logged
        self._warned_joystick_instances: set[int] = set()
        self._logged_unrepresentable_types: set[str] = set()
        # Only its event pump is used: the one place the real queue is read (rule 2)
        self._live_queue = LiveSources(
            random_seed=self.random_seed, use_fastevents=options.use_fastevents
        )
        # Real input blocked at SDL from the first drain of the queue until the replay ends or
        # is uninstalled (rule 2); the snapshot is taken once, so a drain after the end does not
        # block again. A watched replay leaves the viewer's keys unblocked (rule 14)
        blocked_event_types = (
            REAL_INPUT_EVENT_TYPES
            if options.headless
            else tuple(
                event_type
                for event_type in REAL_INPUT_EVENT_TYPES
                if event_type not in WATCHED_REAL_KEY_EVENT_TYPES
            )
        )
        self._real_input_block = EventTypeBlock(event_types=blocked_event_types)
        self._has_blocked_real_input = False
        # A playback from a later frame continues the recording's sprite ids (rule 18)
        self._sprite_ids = StableSpriteIds(
            recorded_ids=_ids_given_before_start(frames=frames, start_frame=options.start_frame)
        )
        self._snapshot: InputSnapshot = IDLE_INPUT
        self._devices = ReplayDeviceRegistry(
            descriptors=[
                DeviceDescriptor.from_json(record)
                for record in header.get(DEVICES_HEADER_FIELD, [])
            ],
            enumeration_answers=[
                EnumerationAnswer.from_json(record)
                for record in header.get(DEVICE_ENUMERATION_FIELD, [])
            ],
        )
        # Namespace -> the recorded snapshot a store opened for it starts from
        self._save_snapshots: dict[str, dict[str, Any]] = dict(header.get(SAVES_HEADER_FIELD, {}))
        self._opened_save_namespaces: dict[str, MemorySaveManager] = {}
        if format_version < TRACE_FORMAT_VERSION:
            LOG.warning(VERSION_TWO_INPUT_WARNING, format_version)
        self.start_input = self._learn_frames_before_start(frames=frames)
        # Sets frame_bridge and recorded_playback_answers too (declared on the class)
        self._begin_frame()

    @classmethod
    def from_path(
        cls,
        *,
        path: Path,
        options: ReplayOptions = DEFAULT_REPLAY_OPTIONS,
    ) -> ReplaySources:
        """Read a recording file into replay sources.

        A file cut off part way (a killed recorder) replays up to its last complete frame
        (``recording.is_truncated``; ``announce_replay`` says so once the run will replay it). A
        file that is not a readable recording raises TraceFormatError (from reading it, or from
        a header without the seed or start time), a missing one OSError.

        Args:
            path: The recording.
            options: How the replay is run.

        Returns:
            The sources.

        """
        read_result = read_trace_result(path=path)
        frames = read_result.trace[FRAMES_FIELD]
        is_truncated = is_cut_off(read_result=read_result)
        header = {name: value for name, value in read_result.trace.items() if name != FRAMES_FIELD}
        return decoded_replay_sources(
            header=header,
            frames=frames,
            format_version=read_result.format_version,
            is_truncated=is_truncated,
            options=options,
        )

    @property
    def opened_save_namespaces(self: Self) -> Mapping[str, SaveManager]:
        """Every memory store opened so far, by namespace (read-only)."""
        return MappingProxyType(self._opened_save_namespaces)

    @property
    def stop_requested(self: Self) -> bool:
        """True once the replay should end the run.

        A headless replay stops once it diverged or reached its last frame; any replay stops
        once the window was closed or (watched) Esc was pressed.
        """
        return self._stop_requested

    def on_installed(self: Self) -> None:
        """Own the internal-post tracker while installed (internal events pass through)."""
        start_tracking_internal_posts()

    def on_uninstalled(self: Self) -> None:
        """Give up the internal-post tracker and restore the blocked state of real input.

        A rebuild still running stops following the game's music calls (rule 15).
        """
        stop_tracking_internal_posts()
        self._real_input_block.restore()
        if self._rebuild is not None:
            self._rebuild.stop_following_music()

    def pump_events(
        self: Self, *, real_events: list[pygame.event.Event] | None = None
    ) -> list[pygame.event.Event]:
        """Serve the recording's batch for this pump, merged with live internal events (rule 2).

        The first drain of the real queue blocks real input at SDL (rule 2), and every later one
        blocks it again (event managers made mid-run allow their types); a pump given
        ``real_events`` does not own the queue, so it blocks nothing. A watched replay's real
        key presses go to its controls (rule 14).

        Args:
            real_events: The real batch to filter instead of draining the real queue (a Part 3
                playback scope passes the base pump's batch).

        Returns:
            The recorded batch in its order (external events from the recording, internal ones
            as the replayed code posted them again), then any live internal event the
            recording does not have, then the window's QUIT if it was closed.

        """
        is_first_drain = real_events is None and not self._has_blocked_real_input
        live_events = self._drain_real_queue() if real_events is None else real_events
        live_internal_events, window_closes = self._sort_live_events(
            live_events=live_events, is_first_drain=is_first_drain
        )
        # Posted but not returned: the queue was cleared or the type is blocked
        forget_pending_posts()
        # Posts a held frame found come first: they were queued before this drain (rule 14)
        live_internal_events = [*self._held_internal_events, *live_internal_events]
        self._held_internal_events = []
        bridge_events: list[pygame.event.Event] = []
        bridge_origins: list[str] = []
        if self.frame_bridge is not None and self._pump_index == 0:
            bridge_events, bridge_origins, live_internal_events = (
                self._resumed_frame_redelivered_events(live_internal_events=live_internal_events)
            )
        batch, origins = self._merged_batch(live_internal_events=live_internal_events)
        batch = [*bridge_events, *batch]
        origins = [*bridge_origins, *origins]
        if self.options.serves_redelivered_events and self._pump_index == 0:
            redelivered, redelivered_origins = self._start_frame_redelivered_events()
            batch = [*redelivered, *batch]
            origins = [*redelivered_origins, *origins]
        self._pump_index += 1
        if window_closes:
            self._window_was_closed = True
            batch.append(window_closes[-1])
            origins.append(EXTERNAL_ORIGIN)
        self._last_batch_origins = origins
        return batch

    def last_batch_origins(self: Self) -> list[str]:
        """Return each event's origin in the batch the last pump returned.

        For a recording made over the replay (``--rebaseline``, rule 17), which records these
        rather than classify the batch with the internal-post tracker (the pump above has
        already consumed its pending posts).

        Returns:
            ``'external'`` for served recorded events and a window close, ``'internal'`` for
            passed-through live events.

        """
        return list(self._last_batch_origins)

    def frame_seconds(self: Self, *, measured: float) -> float:
        """Return the current frame's recorded dt (rule 4).

        The scene manager asks before frame 0 and after each frame ends, so the first call
        returns frame 0's dt and each later call the next frame's.

        Args:
            measured: The measured start-to-start time.

        Returns:
            The recorded dt; ``measured`` past the end of the recording.

        """
        frame = self._current_frame()
        if frame is None:
            return measured
        return float(frame[DT_FIELD])

    def performance_frame_seconds(self: Self, *, measured: float, frame_seconds: float) -> float:
        """Return the frame time FPS events and the performance statistics use (rule 4).

        Args:
            measured: The measured start-to-start time.
            frame_seconds: The frame time ``frame_seconds()`` returned (the recorded dt).

        Returns:
            ``frame_seconds`` under ``--replay-fps recorded``, ``measured`` under ``real``.

        """
        if self.options.fps_source == REAL_REPLAY_FPS:
            return measured
        return frame_seconds

    def paced_frame_seconds(self: Self) -> float | None:
        """Return how the frame starting now is paced (rule 13).

        Returns:
            0.0: a headless replay is not paced, and a watched one paces itself in
            ``hold_frame`` (holding the loop until the frame is due), so the scene manager
            never waits for it.

        """
        return 0.0

    def hold_frame(self: Self) -> bool:
        """Drive the viewer's outer loop: say whether the next inner frame waits (rule 14).

        Opens the viewer's next outer tick when none is open (sleeping until it is due, then
        reading the viewer's keys and refreshing the status line), and runs inner frames from
        the viewer's accumulator (glitchygames/replay/viewer.py).

        While a restarted replay rebuilds (rule 15) no outer tick opens: frames run unheld,
        but for one hold every ``REBUILD_PROGRESS_INTERVAL_SECONDS`` of real time, which reads
        the viewer's keys (Esc and the window's close still end the replay) and presents the
        progress line.

        Returns:
            False when headless (a headless replay never holds), while rebuilding (but at its
            progress) or when the viewer runs one more inner frame in its open tick; True when
            the tick closes or the rebuild shows its progress (the loop presents the outer frame
            and asks again).

        """
        if self.options.headless:
            return False
        if self._rebuild is not None:
            # Before frame 0's game code: the game's own music pauses are followed from it
            self._rebuild.begin()
            # An onion skin's OLD rebuilds alongside (rule 20), not after this rebuild
            if self.onion_skin is not None:
                self.onion_skin.begin()
            now = measured_seconds()
            if not self._rebuild.progress_is_due(frame_index=self._frame_index, now=now):
                return False
            self._run_control_tick(now=now)
            return True
        # Nothing has run since the last tick closed: its state decides how the viewer waits
        now = self.viewer.begin_tick(is_inner_running=self._is_inner_running())
        if now is not None:
            self._run_control_tick(now=now)
            self.viewer.accrue(now=now, is_inner_running=self._is_inner_running())
        runs_inner_frame = self.viewer.should_run_inner_frame(
            inner_frame_seconds=self._inner_frame_seconds(),
            is_inner_over=self._is_inner_over(),
            is_first_inner_frame=self._frame_index == 0,
        )
        if not runs_inner_frame:
            # The tick closed: the status line describes the frame about to be presented
            self._refresh_status_line()
        return not runs_inner_frame

    def draw_overlay(self: Self, *, surface: pygame.Surface) -> None:
        """Draw the watched replay's status bar, banner and start screen (rule 14).

        What is drawn changes once per control tick (``hold_frame``); it is drawn on every
        presented frame.

        With ``--compare-trace`` (rule 20) OLD's frame is drawn first, over the frame the replay
        shows (the last one run), but never over a rebuild's progress screen. OLD's frame is
        the one of the game frame shown (glitchygames/game_frames.py): through a pause screen's
        frames, the game frame before them.

        Args:
            surface: The presented frame (never a screenshot or a traced frame).

        """
        if self.options.headless:
            # Only a frame sink makes a headless replay draw an overlay: it takes the frame
            self._hand_frame_to_sink(surface=surface)
            return
        shown_game_frame = game_frame_clock().shown_game_frame
        if (
            self.onion_skin is not None
            and self._rebuild is None
            and self._frame_index > self.options.start_frame
            and shown_game_frame is not None
        ):
            self.onion_skin.draw(surface=surface, frame_index=shown_game_frame)
        self.controls.draw(surface=surface)

    def input_snapshot(self: Self) -> InputSnapshot:
        """Return the current frame's recorded polled input (rule 5).

        Returns:
            The snapshot (the last recorded one past the end).

        """
        return self._snapshot

    def devices(self: Self) -> ReplayDeviceRegistry:
        """Return the registry of recorded devices (rule 6).

        Returns:
            The registry.

        """
        return self._devices

    def saves(self: Self, *, namespace: str) -> SaveManager:
        """Open (or return the already opened) memory store for ``namespace`` (rule 7).

        Args:
            namespace: The game's app name.

        Returns:
            A MemorySaveManager seeded from the recorded snapshot (empty when the recording has
            none for ``namespace``).

        """
        store = self._opened_save_namespaces.get(namespace)
        if store is None:
            store = MemorySaveManager(
                app_name=namespace, snapshot=self._save_snapshots.get(namespace, {})
            )
            self._opened_save_namespaces[namespace] = store
        return store

    def wall_clock_time(self: Self) -> datetime:
        """Return the recording's start time plus the frame clock (rule 9).

        Returns:
            Timezone-aware time.

        """
        return self._recorded_at + timedelta(seconds=frame_clock_seconds())

    def control_events_for_frame(self: Self, *, frame_number: int) -> list[ControlEvent]:
        """Return the current frame's recorded supervisor actions, to apply again.

        Args:
            frame_number: The scene manager's frame number (not used to pick the frame: rule 3).

        Returns:
            The recorded control events whose kind is applied again, in order (markers the
            replayed code records by itself are left out).

        """
        del frame_number
        frame = self._current_frame()
        # Frames run only while the recording has one: a headless replay stops after its last
        # frame, a watched one holds there (rules 8 and 14)
        assert frame is not None
        return [
            ControlEvent.from_json(record)
            for record in frame.get(CONTROL_EVENTS_FIELD, [])
            if record.get(KIND_FIELD) in REAPPLIED_CONTROL_EVENT_KINDS
        ]

    def end_frame(
        self: Self,
        *,
        frame_number: int,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
        processing_seconds: float | None = None,
    ) -> None:
        """Compare the frame with the recorded one, then move on to the next (rule 8).

        Args:
            frame_number: The scene manager's frame number (log messages only: rule 3).
            dt: The frame's raw dt.
            scene: The active scene at the end of the frame.
            control_events: The control events recorded in the frame.
            processing_seconds: This replay's processing time for the frame, compared with the
                recorded one under ``--compare-processing`` (None: not measured).

        """
        # dt is the recorded one by construction
        del dt
        frame = self._current_frame()
        # Frames run only while the recording has one: a headless replay stops after its last
        # frame, a watched one holds there (rules 8 and 14)
        assert frame is not None
        # Compared until the replay ended (a watched replay may run on after its end, rule 14)
        if self.result.end_reason == RUNNING_END_REASON:
            # Sampled exactly as the recorder samples a recorded frame
            replayed = sample_scene_frame(
                frame_number=self._frame_index, scene=scene, sprite_ids=self._sprite_ids
            )
            if self.options.digest_path is not None:
                self._frame_digests.append(frame_digest(frame_record=replayed))
            # For the divergence report (rule 11): the frames up to the first divergence
            if self.result.divergence is None:
                self.result.recorded_history.append((self._frame_index, frame[SPRITES_FIELD]))
                self.result.replayed_history.append((self._frame_index, replayed[SPRITES_FIELD]))
            divergence = self._frame_difference(
                frame=frame, replayed=replayed, control_events=control_events
            )
            self._note_unpumped_batches(frame=frame)
            self._compare_processing(frame=frame, processing_seconds=processing_seconds)
            self.result.frames_replayed = self._frame_index + 1
            if divergence is not None:
                self._note_divergence(
                    divergence=divergence, frame=frame, replayed=replayed, frame_number=frame_number
                )
            if divergence is not None and self.options.stop_on_divergence:
                self._end_replay(
                    end_reason=DIVERGED_END_REASON,
                    banner=f'Diverged at {divergence.describe()}',
                )
            elif self._frame_index == self.recording.frame_count - 1:
                self._end_replay(
                    end_reason=TRUNCATED_END_REASON
                    if self.recording.is_truncated
                    else END_OF_RECORDING_END_REASON,
                    banner=TRUNCATED_RECORDING_BANNER
                    if self.recording.is_truncated
                    else END_OF_RECORDING_BANNER,
                )
        self._note_the_shown_game_frame()
        # A frame sink nobody reads any more ends the replay as a quit does (rule 20)
        if self.frame_sink_closed or self._window_was_closed or self.controls.quit_requested:
            self._stop(end_reason=QUIT_END_REASON)
        self._frame_index += 1
        self._pump_index = 0
        self._frame_divergence = None
        self.controls.current_frame = self._frame_index
        if self._rebuild is not None:
            self._rebuild.silence_frame()
            if (
                self._frame_index >= self._rebuild.target_frame
                or self.controls.paused
                or self._stop_requested
            ):
                self._finish_rebuild(rebuild=self._rebuild)
        self._begin_frame()

    def _note_the_shown_game_frame(self: Self) -> None:
        """Note the game frame the frame just run showed, with an onion skin (rule 20).

        Only an onion skin's step back reads them (``ReplayResult.shown_game_frames``): a replay
        without one keeps none, so a long headless run holds nothing for it.
        """
        if self.onion_skin is not None:
            self.result.shown_game_frames[self._frame_index] = game_frame_clock().shown_game_frame

    def _hand_frame_to_sink(self: Self, *, surface: pygame.Surface) -> None:
        """Give the frame being presented to the frame sink, if a game frame (rule 20).

        Only game frames, numbered by the game-frame clock (glitchygames/game_frames.py): a
        pause screen's frame is never sent as one of OLD's. A sink that takes no more (nobody
        reads its frames) stops the replay at the frame's end (``frame_sink_closed``) rather
        than letting it run on unseen.

        Args:
            surface: The frame as presented (the display surface).

        """
        # Only a frame sink makes a headless replay draw (the engine's _connect_the_frame_stream)
        assert self.frame_sink is not None
        clock = game_frame_clock()
        if not clock.is_game_frame:
            return
        # A game frame always shows itself
        assert clock.shown_game_frame is not None
        if not self.frame_sink.write_frame(frame_index=clock.shown_game_frame, surface=surface):
            self.frame_sink_closed = True

    def finish_run(self: Self) -> None:
        """Settle the result when the run ends (``GameEngine._shutdown``).

        A run that ended while the replay was still running (the game quit or failed before
        the recording's last frame) diverged in length, unless an earlier frame already
        differed (a replay that does not stop at a divergence, rule 8): the first difference is
        kept. Either way the blocked state of real input is restored (rule 2), and the digest
        file written when asked for (rule 12).
        """
        self._real_input_block.restore()
        if self.result.processing_comparison is not None:
            self.result.processing = self.result.processing_comparison.summary()
        if self.result.end_reason == RUNNING_END_REASON:
            if self.result.divergence is None:
                self.result.divergence = Divergence(
                    frame_number=self.result.frames_replayed,
                    kind=LENGTH_DIVERGENCE,
                    subject=RECORDING_SUBJECT,
                    field=FRAME_COUNT_FIELD,
                    expected=self.recording.frame_count,
                    actual=self.result.frames_replayed,
                )
            self._stop(end_reason=DIVERGED_END_REASON)
        if self.options.digest_path is not None:
            divergence = self.result.divergence
            write_error: OSError | None = None
            try:
                write_digest_file(
                    path=self.options.digest_path,
                    digests=self._frame_digests,
                    divergence=None if divergence is None else divergence.describe(),
                )
            except OSError as error:
                write_error = error
            if write_error is not None:
                # Logged without a traceback: the message says what failed; the engine reports
                # the replay, then exits CANNOT_WRITE_OUTPUT (rule 12)
                LOG.error(
                    'Could not write the digest file %s: %s', self.options.digest_path, write_error
                )
                self.digest_write_failed = True

    def _compare_processing(
        self: Self, *, frame: dict[str, Any], processing_seconds: float | None
    ) -> None:
        """Add the frame's processing time beside the recorded one, when comparing them.

        Args:
            frame: The recorded frame.
            processing_seconds: This replay's processing time for it (None: not measured).

        """
        comparison = self.result.processing_comparison
        if comparison is None or processing_seconds is None:
            return
        history = frame.get(PROCESSING_SECONDS_FIELD)
        recorded_value: object = (
            cast('list[Any]', history)[0] if isinstance(history, list) and history else None
        )
        recorded_seconds: float | None = None
        if isinstance(recorded_value, (int, float)) and not isinstance(recorded_value, bool):
            recorded_seconds = float(recorded_value)
        comparison.add_frame(
            frame_index=self._frame_index,
            recorded_seconds=recorded_seconds,
            replayed_seconds=processing_seconds,
        )

    def _current_frame(self: Self) -> dict[str, Any] | None:
        return self.recording.frame(frame_index=self._frame_index)

    def _note_unpumped_batches(self: Self, *, frame: dict[str, Any]) -> None:
        """Count the external events of the frame's batches no pump served (rule 8).

        They are never carried into a later pump: that would invent an input sequence the
        recording does not have. A replay that stops at the divergence (the pump count) ends
        here anyway; one that runs on (``--rebaseline``) reports the count.

        Args:
            frame: The recorded frame, after its last pump.

        """
        unpumped_batches = frame.get(EVENT_BATCHES_FIELD, [])[self._pump_index :]
        self.result.note_undelivered_inputs(
            frame_index=self._frame_index,
            count=sum(
                1
                for batch in unpumped_batches
                for record in batch
                if record.get(EVENT_ORIGIN_FIELD) == EXTERNAL_ORIGIN
            ),
        )

    def _note_divergence(
        self: Self,
        *,
        divergence: Divergence,
        frame: dict[str, Any],
        replayed: dict[str, Any],
        frame_number: int,
    ) -> None:
        """Keep a differing frame in the result: the first divergence, the count, its sprites.

        Args:
            divergence: The frame's first difference.
            frame: The recorded frame.
            replayed: The replayed frame, sampled by ``sample_scene_frame``.
            frame_number: The scene manager's frame number (the log message only: rule 3).

        """
        self.result.note_differing_frame(
            sprite_ids=differing_sprite_ids(recorded=frame, replayed=replayed)
        )
        if self.result.divergence is not None:
            return
        LOG.debug(
            'Replay diverged at recorded frame %d (run frame %d)',
            divergence.frame_number,
            frame_number,
        )
        self.result.divergence = divergence
        self.controls.divergence_frame = divergence.frame_number

    def _frame_difference(
        self: Self,
        *,
        frame: dict[str, Any],
        replayed: dict[str, Any],
        control_events: list[ControlEvent],
    ) -> Divergence | None:
        """Return the frame's first difference: its pumps', its markers', then its sprites'.

        Args:
            frame: The recorded frame.
            replayed: The replayed frame, sampled by ``sample_scene_frame``.
            control_events: The control events recorded in the frame.

        Returns:
            The divergence, or None when the frame matches.

        """
        if self._frame_divergence is not None:
            return self._frame_divergence
        recorded_pump_count = len(frame.get(EVENT_BATCHES_FIELD, []))
        if self._pump_index < recorded_pump_count:
            # Fewer pumps than recorded (more are found by the extra pump itself)
            return Divergence(
                frame_number=self._frame_index,
                kind=LENGTH_DIVERGENCE,
                subject=RECORDING_SUBJECT,
                field=PUMP_COUNT_FIELD,
                expected=recorded_pump_count,
                actual=self._pump_index,
            )
        control_event_divergence = self._control_event_difference(
            frame=frame, control_events=control_events
        )
        if control_event_divergence is not None:
            return control_event_divergence
        return first_frame_difference(
            frame_index=self._frame_index, recorded=frame, replayed=replayed
        )

    def _control_event_difference(
        self: Self, *, frame: dict[str, Any], control_events: list[ControlEvent]
    ) -> Divergence | None:
        """Compare the markers the replayed code recorded with the frame's recorded ones (rule 8).

        Control events applied again (``REAPPLIED_CONTROL_EVENT_KINDS``) are left out on both
        sides: the replay records them itself from the recording.

        Returns:
            The first marker that differs (missing, extra or changed), or None.

        """
        if not self._compares_control_events:
            return None
        recorded_markers = [
            record
            for record in frame.get(CONTROL_EVENTS_FIELD, [])
            if record.get(KIND_FIELD) not in REAPPLIED_CONTROL_EVENT_KINDS
        ]
        # Through JSON, as the recording wrote them: an integer key becomes a string and a
        # tuple a list, so a marker is never compared with its recorded form falsely
        replayed_markers = [
            json.loads(json.dumps(control_event.to_json()))
            for control_event in control_events
            if control_event.kind not in REAPPLIED_CONTROL_EVENT_KINDS
        ]
        for expected, actual in itertools.zip_longest(recorded_markers, replayed_markers):
            if expected != actual:
                differing_marker = expected if expected is not None else actual
                return Divergence(
                    frame_number=self._frame_index,
                    kind=EVENT_DIVERGENCE,
                    subject=str(differing_marker[KIND_FIELD]),
                    field=CONTROL_EVENT_FIELD,
                    expected=expected,
                    actual=actual,
                )
        return None

    def _note_frame_divergence(
        self: Self, *, kind: str, subject: str, field: str, expected: object, actual: object
    ) -> None:
        """Keep the current frame's first difference found while pumping (end_frame reports it)."""
        if self._frame_divergence is None:
            self._frame_divergence = Divergence(
                frame_number=self._frame_index,
                kind=kind,
                subject=subject,
                field=field,
                expected=expected,
                actual=actual,
            )

    def _merged_batch(
        self: Self, *, live_internal_events: list[pygame.event.Event]
    ) -> tuple[list[pygame.event.Event], list[str]]:
        """Build this pump's batch in the recorded batch's order (rule 2).

        Under ``--replay-fps real`` FPS events are not compared (rule 4): a recorded one takes
        the next live FPS event in its place, if any, and a live one left over is delivered;
        neither is a divergence.

        Args:
            live_internal_events: The events the replayed code posted, in queue order.

        Returns:
            The batch and each event's origin. On a pump the frame did not record, the live
            internal events alone.

        """
        uncompared_event_types: frozenset[int] = (
            frozenset({FPSEVENT}) if self.options.fps_source == REAL_REPLAY_FPS else frozenset()
        )
        live_origins = [INTERNAL_ORIGIN] * len(live_internal_events)
        frame = self._current_frame()
        # Frames run only while the recording has one: a headless replay stops after its last
        # frame, a watched one holds there (rules 8 and 14)
        assert frame is not None
        batches = frame.get(EVENT_BATCHES_FIELD, [])
        if self._pump_index >= len(batches):
            self._note_frame_divergence(
                kind=LENGTH_DIVERGENCE,
                subject=RECORDING_SUBJECT,
                field=PUMP_COUNT_FIELD,
                expected=len(batches),
                actual=self._pump_index + 1,
            )
            return list(live_internal_events), live_origins
        # Each live internal event with its record, compared with the recorded internal records
        unmatched = [
            (event, event_to_record(event=event, origin=INTERNAL_ORIGIN))
            for event in live_internal_events
        ]
        batch: list[pygame.event.Event] = []
        origins: list[str] = []
        for record in batches[self._pump_index]:
            if self._serves_recorded_event(record=record, batch=batch, origins=origins):
                continue
            is_compared = record.get(EVENT_TYPE_FIELD) not in uncompared_event_types
            matched_event = _take_live_match(
                unmatched=unmatched, record=record, is_compared=is_compared
            )
            if matched_event is not None:
                batch.append(matched_event)
                origins.append(INTERNAL_ORIGIN)
            elif is_compared:
                self._note_frame_divergence(
                    kind=EVENT_DIVERGENCE,
                    subject=str(record.get(EVENT_NAME_FIELD)),
                    field=MISSING_INTERNAL_EVENT_FIELD,
                    expected=record,
                    actual=None,
                )
        # Posted again by the replayed code but not recorded: still delivered, and a divergence
        # (unless its type is not compared)
        for event, live_record in unmatched:
            batch.append(event)
            origins.append(INTERNAL_ORIGIN)
            if event.type in uncompared_event_types:
                continue
            self._note_frame_divergence(
                kind=EVENT_DIVERGENCE,
                subject=str(live_record[EVENT_NAME_FIELD]),
                field=UNEXPECTED_INTERNAL_EVENT_FIELD,
                expected=None,
                actual=live_record,
            )
        return batch, origins

    def _serves_recorded_event(
        self: Self,
        *,
        record: dict[str, Any],
        batch: list[pygame.event.Event],
        origins: list[str],
    ) -> bool:
        """Serve a recorded event from the recording itself, when it is not matched live.

        External records always are (rule 2). So are the start frame's first internal records
        posted by code the replay did not run (``ReplayOptions.earlier_internal_event_count``,
        rule 18): delivered as recorded and never compared.

        Args:
            record: The recorded event.
            batch: The batch being built (the event is added to it, unless its joystick has no
                stand-in).
            origins: Its origins (the record's is added with it).

        Returns:
            True when the record was served from the recording; False for an internal record
            the replayed code must post again.

        """
        origin = record.get(EVENT_ORIGIN_FIELD)
        if origin != EXTERNAL_ORIGIN:
            if self._earlier_internal_events_to_serve == 0:
                return False
            # Posted before the replayed scene began, by code the playback did not run
            self._earlier_internal_events_to_serve -= 1
        event = self._live_event_from_record(record=record)
        if event is not None:
            batch.append(event)
            origins.append(EXTERNAL_ORIGIN if origin == EXTERNAL_ORIGIN else INTERNAL_ORIGIN)
        return True

    def _start_frame_redelivered_events(self: Self) -> tuple[list[pygame.event.Event], list[str]]:
        """Return the start frame's recorded redelivered events, for its first pump (rule 18).

        Returns:
            The events (their references mapped to live objects) and their recorded origins;
            none on any other frame.

        """
        frame = self._current_frame()
        if frame is None or self._frame_index != self.options.start_frame:
            return [], []
        events: list[pygame.event.Event] = []
        origins: list[str] = []
        for record in frame.get(REDELIVERED_EVENTS_FIELD, []):
            event = self._live_event_from_record(record=record)
            if event is not None:
                events.append(event)
                origins.append(str(record.get(EVENT_ORIGIN_FIELD)))
        return events, origins

    def _resumed_frame_redelivered_events(
        self: Self, *, live_internal_events: list[pygame.event.Event]
    ) -> tuple[list[pygame.event.Event], list[str], list[pygame.event.Event]]:
        """Return a resumed frame's redelivered events, for its first pump (rule 18).

        The scope the scene waited behind held them and delivered them before this pump: the
        external ones (the player's releases, device and window events) are served from the
        recording; the internal ones were posted by the scene's own frames before the scope,
        which the playback ran, so they are the live posts again, matched as recorded.

        Args:
            live_internal_events: The events the replayed code posted, in queue order.

        Returns:
            The events, their origins, and the live internal events left for the batch.

        """
        frame = self._current_frame()
        # Frames run only while the recording has one: a headless replay stops after its last
        # frame, a watched one holds there (rules 8 and 14)
        assert frame is not None
        unmatched = [
            (event, event_to_record(event=event, origin=INTERNAL_ORIGIN))
            for event in live_internal_events
        ]
        events: list[pygame.event.Event] = []
        origins: list[str] = []
        for record in frame.get(REDELIVERED_EVENTS_FIELD, []):
            if record.get(EVENT_ORIGIN_FIELD) == EXTERNAL_ORIGIN:
                event = self._live_event_from_record(record=record)
                if event is not None:
                    events.append(event)
                    origins.append(EXTERNAL_ORIGIN)
                continue
            matched_event = _take_live_match(unmatched=unmatched, record=record, is_compared=True)
            if matched_event is None:
                self._note_frame_divergence(
                    kind=EVENT_DIVERGENCE,
                    subject=str(record.get(EVENT_NAME_FIELD)),
                    field=MISSING_INTERNAL_EVENT_FIELD,
                    expected=record,
                    actual=None,
                )
                continue
            events.append(matched_event)
            origins.append(INTERNAL_ORIGIN)
        return events, origins, [event for event, _record in unmatched]

    def _live_event_from_record(self: Self, *, record: dict[str, Any]) -> pygame.event.Event | None:
        """Rebuild a recorded external event with its references mapped to live objects.

        A window reference becomes None: the window is the display module's, and live play
        never calls ``pygame.Window.from_display_module()`` (deprecated, and calling it would
        make SDL's window events carry a Window from then on), so every live event of the
        current window carries ``window=None``. A joystick reference becomes the stand-in
        opened for its instance id.

        Returns:
            The event, or None when its joystick has no stand-in (dropped, with one warning
            per instance id).

        """
        recorded_event = event_from_record(record)
        attributes: dict[str, Any] = {}
        for name, value in recorded_event.dict.items():
            if isinstance(value, RecordedReference):
                if value.kind == WINDOW_REFERENCE:
                    attributes[name] = None
                    continue
                joystick = self._opened_joystick(instance_id=value.identifier)
                if joystick is None:
                    return None
                attributes[name] = joystick
                continue
            if (
                isinstance(value, UnrepresentableValue)
                and value.type_name not in self._logged_unrepresentable_types
            ):
                self._logged_unrepresentable_types.add(value.type_name)
                LOG.debug(
                    'Recorded events carry an unrepresentable %s; it is injected as recorded',
                    value.type_name,
                )
            attributes[name] = value
        return pygame.event.Event(recorded_event.type, attributes)

    def _opened_joystick(self: Self, *, instance_id: int) -> ReplayJoystick | None:
        """Return the stand-in opened for a recorded instance id, or None (warned once per id).

        Returns:
            The joystick stand-in, or None when no device was opened for ``instance_id``.

        """
        joystick = self._devices.joystick_for_instance(instance_id=instance_id)
        if joystick is None and instance_id not in self._warned_joystick_instances:
            self._warned_joystick_instances.add(instance_id)
            LOG.warning(
                'recorded joystick event for instance %d has no device; dropped', instance_id
            )
        return joystick

    def _begin_frame(self: Self) -> None:
        """Learn what the current frame took in, before any of its doors are asked.

        Its opened devices and enumeration answers, its newly opened save namespaces, and its
        polled input (applied to the previous frame's snapshot).
        """
        frame = self._current_frame()
        self.frame_bridge = None
        self.recorded_playback_answers = collections.deque()
        if frame is None:
            return
        self._devices.add_enumeration_answers(
            answers=[
                EnumerationAnswer.from_json(record)
                for record in frame.get(DEVICE_ENUMERATION_FIELD, [])
            ]
        )
        bridge_record = frame.get(RESUME_BRIDGE_FIELD)
        if bridge_record is not None and self._frame_index != self.options.start_frame:
            # A scene resuming after a playback scope (rule 18): the frame starts from the
            # recorded state, as the start frame does
            bridge = ResumeBridge.model_validate(bridge_record)
            self.frame_bridge = bridge
            self._earlier_internal_events_to_serve = bridge.earlier_internal_event_count
            self._snapshot = apply_snapshot_changes(
                previous=IDLE_INPUT, changes=bridge.input_before
            )
        self.recorded_playback_answers = collections.deque(frame.get(PLAYBACK_ANSWERS_FIELD, []))
        self._learn_frame_inputs(frame=frame)

    def _learn_frames_before_start(
        self: Self, *, frames: Sequence[dict[str, Any]]
    ) -> InputSnapshot:
        """Learn what the frames before the start frame took in; none is served (rule 18).

        Args:
            frames: Every recorded frame.

        Returns:
            The polled input before the start frame, which its logic reads.

        """
        for earlier_frame in frames[: self.options.start_frame]:
            self._learn_frame_inputs(frame=earlier_frame)
        return self._snapshot

    def _learn_frame_inputs(self: Self, *, frame: dict[str, Any]) -> None:
        """Learn a frame's opened devices, newly opened save namespaces and polled input.

        Everything ``_begin_frame`` learns but the enumeration answers, which are consumed by
        the frame's own enumeration calls (so a playback learns the frames before its start
        frame without them; rule 18).

        Args:
            frame: The recorded frame.

        """
        self._devices.add_descriptors(
            descriptors=[
                DeviceDescriptor.from_json(record) for record in frame.get(DEVICES_OPENED_FIELD, [])
            ]
        )
        for namespace, snapshot in frame.get(SAVES_OPENED_FIELD, {}).items():
            self._save_snapshots.setdefault(namespace, snapshot)
        self._snapshot = apply_snapshot_changes(
            previous=self._snapshot, changes=frame.get(INPUT_CHANGES_FIELD, {})
        )

    def _drain_real_queue(self: Self) -> list[pygame.event.Event]:
        """Take every event from SDL's queue, blocking real input at SDL from the first (rule 2).

        Returns:
            The real batch, in queue order.

        """
        live_events = self._live_queue.pump_events()
        # After the drain, so the replayed code's posts made before the first drain are kept
        if not self._has_blocked_real_input:
            self._has_blocked_real_input = True
            self._real_input_block.block()
        else:
            # An event manager made since the last drain (a scene's widgets) called
            # set_allowed; block again without a new snapshot
            self._real_input_block.reassert()
        return live_events

    def _sort_live_events(
        self: Self, *, live_events: list[pygame.event.Event], is_first_drain: bool
    ) -> tuple[list[pygame.event.Event], list[pygame.event.Event]]:
        """Split a real batch into internal events and window closes; nothing else reaches the game.

        Classified with the internal-post tracker (its matched posts are consumed). A watched
        replay keeps its real key presses and releases for the next control tick (rule 14),
        except the presses of the first drain: stale ones, queued before the replay.

        Args:
            live_events: The real batch.
            is_first_drain: True for the replay's first drain of the real queue.

        Returns:
            The internal events and the window's QUIT events, each in queue order.

        """
        pending = pending_internal_posts()
        live_internal_events: list[pygame.event.Event] = []
        window_closes: list[pygame.event.Event] = []
        for event in live_events:
            post = take_matching_post(event=event, pending=pending)
            if post is not None and is_input_post(post=post):
                # The replayed code's copy of an input post (post_input_event): the recording
                # holds it as external and serves it, so this one is dropped, never taken for
                # a window close or a viewer key
                continue
            if post is not None or event.type >= pygame.USEREVENT:
                live_internal_events.append(event)
            elif event.type == pygame.QUIT:
                window_closes.append(event)
            elif event.type in WATCHED_REAL_KEY_EVENT_TYPES and not self.options.headless:
                if is_first_drain:
                    # Stale, pressed before the replay: not acted on, but followed in order, so
                    # a key still down is held (its operating-system repeats are not new
                    # presses until it is released)
                    if event.type == pygame.KEYDOWN:
                        self.controls.note_key_already_down(key=event.key)
                    else:
                        self.controls.release_key(key=event.key)
                else:
                    self.viewer.queue_key_event(event_type=event.type, key=event.key)
            # Every other real external event is dropped: real input is blocked at SDL, so
            # these are events queued before the first drain, the window's close event (its
            # QUIT follows) and app lifecycle and system notifications
        return live_internal_events, window_closes

    def _run_control_tick(self: Self, *, now: float) -> None:
        """Read the real queue and act on the viewer's keys, at an outer tick's start (rule 14).

        Args:
            now: The measured time of the tick.

        """
        is_first_drain = not self._has_blocked_real_input
        live_internal_events, window_closes = self._sort_live_events(
            live_events=self._drain_real_queue(), is_first_drain=is_first_drain
        )
        self._held_internal_events.extend(live_internal_events)
        self.viewer.apply_key_events(now=now)
        if window_closes or self.controls.quit_requested:
            self._stop(end_reason=QUIT_END_REASON)
            return
        if self.controls.take_save_request():
            self.bookmarks.save()
        restart_frame = self.controls.take_restart_request()
        if restart_frame is not None:
            # The engine relaunches the replay at the frame once the run is torn down (rule 15)
            self.result.restart_frame = restart_frame
            self._stop(end_reason=RESTART_END_REASON)

    def _refresh_status_line(self: Self) -> None:
        """Give the controls the status line of the frame the closing outer tick presents."""
        divergence = self.result.divergence
        self.controls.update_status(
            status_line=self.controls.status_line(
                frame_number=self._frame_index,
                seconds=frame_clock_seconds(),
                divergence_frame=None if divergence is None else divergence.frame_number,
                effective_speed=self.viewer.real_speed_if_behind(),
            )
        )

    def _finish_rebuild(self: Self, *, rebuild: Rebuild) -> None:
        """End a restarted replay's rebuild: pause it where it is, its music resumed (rule 15).

        Args:
            rebuild: The rebuild in progress (``self._rebuild``).

        """
        rebuild.finish()
        self._rebuild = None
        self.controls.rebuild_target_frame = None
        self.controls.paused = True
        self.controls.step_requested = False

    def _is_inner_over(self: Self) -> bool:
        """Report whether no inner frame can run: the replay stopped or its recording is used up.

        Returns:
            True when over.

        """
        return self._stop_requested or self._current_frame() is None

    def _is_inner_running(self: Self) -> bool:
        """Report whether the inner game is running (not over, at the start screen or paused).

        Returns:
            True when the viewer's accumulator should fill.

        """
        return not (self._is_inner_over() or self.controls.awaiting_start or self.controls.paused)

    def _inner_frame_seconds(self: Self) -> float:
        """Return how long the inner frame starting now lasted when recorded (rule 4).

        Returns:
            The next frame's recorded ``dt`` (the duration of this one), or this frame's own
            for the last recorded frame; 0.0 past the end.

        """
        for frame_index in (self._frame_index + 1, self._frame_index):
            if self.recording.frame(frame_index=frame_index) is not None:
                return self.recording.recorded_dt(frame_index=frame_index)
        return 0.0

    def _end_replay(self: Self, *, end_reason: str, banner: str) -> None:
        """End the comparison: stop a headless replay, pause a watched one there (rule 14).

        Args:
            end_reason: The result's end reason.
            banner: The watched replay's banner line (a divergence or the end).

        """
        if self.options.headless:
            self._stop(end_reason=end_reason)
            return
        self.result.end_reason = end_reason
        self.controls.paused = True
        self.controls.banner = banner
        self.controls.debug_overlay.is_visible = True

    def _stop(self: Self, *, end_reason: str) -> None:
        """Stop the replay; a replay that already ended keeps its end reason."""
        if self.result.end_reason == RUNNING_END_REASON:
            self.result.end_reason = end_reason
        self._stop_requested = True


def replayed_batch_origins(*, doors: EngineSources) -> list[str] | None:
    """Return each event's origin in the doors' last batch, when a replay's merge knows them.

    A recorder over a replay (``--rebaseline``) takes them from the replay, and so does the
    instant-replay journal (glitchygames/instant_replay.py, rule 4): a watched replay's held
    frames drain the real queue between pumps, so the posts pending before a pump do not tell
    them. So does a playback scope over a replay of the session
    (glitchygames/replay/playback.py, rule 5): the replay's pump has consumed the posts, and a
    recorded external event of a type SDL never generates (a live supervisor's input post) is
    told from the replayed code's posts only by its recorded origin.

    Args:
        doors: The doors that pumped (the run's installed ones, or a recording around them).

    Returns:
        The origins, in the batch's order, or None when the doors are not a replay's.

    """
    while isinstance(doors, RecordingSources):
        doors = doors.inner
    if isinstance(doors, ReplaySources):
        return doors.last_batch_origins()
    return None


def _ids_given_before_start(*, frames: Sequence[dict[str, Any]], start_frame: int) -> set[str]:
    """Return the sprite ids the frames before ``start_frame`` gave to other sprites (rule 18).

    The ids the start frame holds are left out: those sprites are the replayed scene's (set up,
    and sampled, a frame or a transition's ride before its first logic frame), which the
    rebuilt scene makes again and which take those ids again.

    Returns:
        The ids.

    """
    if start_frame == 0:
        return set()
    start_ids = {sprite[SPRITE_ID_FIELD] for sprite in frames[start_frame].get(SPRITES_FIELD, [])}
    return {
        sprite[SPRITE_ID_FIELD]
        for frame in frames[:start_frame]
        for sprite in frame.get(SPRITES_FIELD, [])
    } - start_ids


def decoded_replay_sources(
    *,
    header: dict[str, Any],
    frames: Sequence[dict[str, Any]],
    format_version: int,
    is_truncated: bool = False,
    options: ReplayOptions = DEFAULT_REPLAY_OPTIONS,
) -> ReplaySources:
    """Make replay sources from a decoded recording, refusing a malformed one (rule 1).

    What the sources decode as they are made (the header's devices, enumeration answers and
    saves, the frames before the start frame and the start frame itself: their devices, saves,
    input changes and resume bridge) is checked here, so a malformed recording raises
    TraceFormatError, which the engine refuses with ``ExitCode.UNUSABLE_INPUT`` as it does an
    unreadable file (``ReplaySources.from_path``), and a playback refuses as it does any
    recording it cannot play (``playback_replay_sources``).

    Known limitation: the catch covers the whole ``ReplaySources.__init__``, so a genuine
    engine bug there that raises AttributeError, KeyError, TypeError or ValueError is reported
    as a malformed recording (``UNUSABLE_INPUT``, 65), not as ``INTERNAL_ERROR`` (70); the
    message keeps the original exception (``repr``), and it is chained as the cause.

    Args:
        header: The header fields.
        frames: Every complete recorded frame, decoded.
        format_version: The file's format version (2 or 3).
        is_truncated: True when the file was cut off.
        options: How the replay is run.

    Returns:
        The sources.

    Raises:
        TraceFormatError: If the header has no seed or start time, or what the sources decode
            is malformed.

    """
    try:
        return ReplaySources(
            header=header,
            frames=frames,
            format_version=format_version,
            is_truncated=is_truncated,
            options=options,
        )
    except TraceFormatError:
        # Already says what is wrong (a header without its seed or start time)
        raise
    # A pydantic ValidationError (a resume bridge) is a ValueError
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        where = '' if options.start_frame == 0 else f' before frame {options.start_frame}'
        message = f'The recording is malformed{where}: {error!r}'
        raise TraceFormatError(message) from error


def playback_replay_sources(
    *, header: dict[str, Any], frames: Sequence[dict[str, Any]], start: SceneStart, start_frame: int
) -> ReplaySources:
    """Return the sources an in-game playback scope serves a recording from (rule 18).

    Args:
        header: The recording's header fields (its ``random_seed`` and ``recorded_at`` are
            required).
        frames: Every recorded frame, decoded (glitchygames/tracing.py).
        start: The ``scene_start`` frame ``start_frame`` holds: the rebuilt scene's start,
            whose save view the saves start from (over the header's).
        start_frame: The recording frame served first.

    Returns:
        The sources, not installed (the scope pushes them; glitchygames/sources.py).

    Raises:
        TraceFormatError: If the header cannot be replayed, or the frames before
            ``start_frame`` are malformed (a sprite without an id or with an id that is not
            ``<Class>#<n>``, an unreadable device descriptor or input change).

    """
    header_saves: object = header.get(SAVES_HEADER_FIELD, {})
    if not isinstance(header_saves, dict):
        message = f'The recording header saves is not a mapping: {header_saves!r}'
        raise TraceFormatError(message)
    saves: dict[str, Any] = {**cast('dict[str, Any]', header_saves), **start.saves}
    first_logic_frame = start.first_logic_frame
    return decoded_replay_sources(
        header={**header, SAVES_HEADER_FIELD: saves},
        frames=frames,
        # Only recordings that hold scene starts can be played, and those are this format's
        format_version=TRACE_FORMAT_VERSION,
        # Nobody watches a playback's replay: it never holds or pauses and stops at its end
        # or first divergence (the scope ends then)
        options=ReplayOptions(
            headless=True,
            start_frame=start_frame,
            serves_redelivered_events=True,
            earlier_internal_event_count=(
                0 if first_logic_frame is None else first_logic_frame.earlier_internal_event_count
            ),
        ),
    )


def is_cut_off(*, read_result: TraceReadResult) -> bool:
    """Report whether a recording file was cut off part way (a killed recorder).

    Args:
        read_result: The file as read.

    Returns:
        True when its gzip stream did not end or its last line was cut off.

    """
    return not read_result.is_complete or read_result.dropped_partial_line is not None


def recorded_bookmarks(*, frames: Sequence[Mapping[str, Any]]) -> list[int]:
    """Return the bookmarks a recording's breakpoints hold (rule 16; none for most).

    Args:
        frames: The recorded frames.

    Returns:
        N for each frame N - 1 holding ``BOOKMARK_CONTROL_EVENT``, sorted.

    """
    bookmark_record = BOOKMARK_CONTROL_EVENT.to_json()
    return [
        frame_index + 1
        for frame_index, frame in enumerate(frames)
        if bookmark_record in frame.get(CONTROL_EVENTS_FIELD, [])
    ]


def bookmarked_copy_path(*, recording_path: Path) -> Path:
    """Name the bookmarked copy of a recording (rule 16), next to it.

    Args:
        recording_path: The recording.

    Returns:
        The recording itself when it is a bookmarked copy (``is_bookmarked_copy``: a
        restarted replay replays one, and saving again updates it); else
        ``x.bookmarked.jsonl.gz`` for ``x.jsonl.gz`` (``x.bookmarked.trace`` for another suffix
        such as ``x.trace``), even when the name already says ``bookmarked``.

    """
    if is_bookmarked_copy(path=recording_path):
        return recording_path
    name = recording_path.name
    suffix = (
        RECORDING_FILE_SUFFIX if name.endswith(RECORDING_FILE_SUFFIX) else recording_path.suffix
    )
    stem = name.removesuffix(suffix)
    return recording_path.with_name(f'{stem}{BOOKMARKED_COPY_MARK}{suffix}')


def write_bookmarked_copy(*, recording_path: Path, bookmarks: list[int], destination: Path) -> None:
    """Write a copy of a recording with a breakpoint for each bookmark (rule 16).

    The recording's header and complete frames are copied as read; for each bookmark N, frame
    N - 1 gets ``BOOKMARK_CONTROL_EVENT`` appended to its control events, unless it already has
    it, and its newest content hash (``content_hash[0]``, glitchygames/recording_history.py)
    is recomputed to describe the breakpoint. The header gains ``bookmarked_copy_of`` (the
    source's file name, kept from a copy), ``source_truncated`` when the source was cut off,
    and ``input_capture_format_version`` when the source is older than format version 3, so
    the copy replays as its source does. A
    copy an earlier session saved from the same source keeps its bookmarks: they are added to
    ``bookmarks`` (a copy of another recording is never written over). The copy is written
    aside, then moved into place (``glitchygames.output_files.write_aside_then_replace``), so
    ``destination`` is never left half written, even when it is ``recording_path``.

    Args:
        recording_path: The recording to copy (never written, unless it is a bookmarked copy
            and ``destination``).
        bookmarks: The bookmarked frames (``ReplayControls.bookmarks``), each 1 to the
            recording's frame count.
        destination: The copy's path (``bookmarked_copy_path``): a new file or a bookmarked
            copy.

    Raises:
        ValueError: If ``destination`` exists but is not a bookmarked copy of
            ``recording_path``, or a bookmark is outside the recording (nothing is written
            either way).

    """
    bookmarks = sorted({
        *bookmarks,
        *_earlier_copy_bookmarks(recording_path=recording_path, destination=destination),
    })
    read_result = read_trace_result(path=recording_path)
    trace = read_result.trace
    frames: list[dict[str, Any]] = trace[FRAMES_FIELD]
    bookmark_record = BOOKMARK_CONTROL_EVENT.to_json()
    for bookmark in bookmarks:
        if not 1 <= bookmark <= len(frames):
            message = (
                f'Bookmark {bookmark} is outside the recording {recording_path} '
                f'(frames 1 to {len(frames)} can be bookmarked)'
            )
            raise ValueError(message)
        frame = frames[bookmark - 1]
        control_events = list(frame.get(CONTROL_EVENTS_FIELD, []))
        if bookmark_record not in control_events:
            control_events.append(bookmark_record)
        frame[CONTROL_EVENTS_FIELD] = control_events
        # The breakpoint is the frame's content now (a rebaseline of the copy re-applies it), so
        # the newest run's hash describes it; older runs' hashes stay as they were
        recorded_hashes = frame.get(CONTENT_HASH_FIELD)
        if isinstance(recorded_hashes, list) and recorded_hashes:
            frame[CONTENT_HASH_FIELD] = [
                frame_content_hash(frame_record=frame),
                *cast('list[Any]', recorded_hashes)[1:],
            ]
    trace.setdefault(BOOKMARKED_COPY_OF_HEADER_FIELD, recording_path.name)
    if is_cut_off(read_result=read_result):
        trace[SOURCE_TRUNCATED_HEADER_FIELD] = True
    if read_result.format_version < TRACE_FORMAT_VERSION:
        trace.setdefault(INPUT_CAPTURE_FORMAT_HEADER_FIELD, read_result.format_version)
    write_aside_then_replace(
        destination=destination, write=lambda aside: write_trace(trace=trace, path=aside)
    )


def _earlier_copy_bookmarks(*, recording_path: Path, destination: Path) -> list[int]:
    """Return the bookmarks a copy an earlier session saved holds, to keep them (rule 16).

    Args:
        recording_path: The recording being copied.
        destination: The copy's path.

    Returns:
        The bookmarks of ``destination`` when it is a bookmarked copy of ``recording_path``
        saved earlier; none when it does not exist or is ``recording_path`` itself (a copy
        being replayed, whose frames already hold them).

    Raises:
        ValueError: If ``destination`` exists but is not a bookmarked copy, or is a copy of
            another recording.

    """
    if not destination.exists():
        return []
    if not is_bookmarked_copy(path=destination):
        message = f'{destination} is not a bookmarked copy; refusing to write over it'
        raise ValueError(message)
    if destination.resolve() == recording_path.resolve():
        return []
    copy = read_trace_result(path=destination).trace
    copy_of = copy.get(BOOKMARKED_COPY_OF_HEADER_FIELD)
    if copy_of != recording_path.name:
        message = (
            f'{destination} is a bookmarked copy of {copy_of}, not of {recording_path.name}; '
            'refusing to write over it'
        )
        raise ValueError(message)
    return recorded_bookmarks(frames=copy[FRAMES_FIELD])


def installed_engine_version() -> str | None:
    """Return the installed glitchygames version (a recording's ``engine_version``).

    Returns:
        The version, or None when the package metadata is not installed.

    """
    try:
        return importlib.metadata.version('glitchygames')
    except importlib.metadata.PackageNotFoundError:
        return None


# How to convert a recording made before logical names whose game has moved since (rule 17)
REBASELINE_REMEDY = '--replay-trace OLD --rebaseline NEW --headless'


def modules_not_compared(
    *, recorded_module: str | None, loaded_module: str, is_rebaseline: bool
) -> bool:
    """Return whether a record is matched by qualified name alone.

    The one rule for every record a game or scene is found by: an old-format record (a header
    without ``game``, a scene start without ``scene``; glitchygames/logical_names.py) gives its
    module, a newer one its logical module. Used by ``check_recorded_game`` and by
    ``find_scene_class`` (glitchygames/replay/playback.py). Their modules are compared, so a
    class of the same name in another game is refused, except where they cannot be: no module
    recorded, or a game file run as a script (``__main__``) on either side. Under
    ``--rebaseline`` (rule 17) they are never compared: a game or scene that moved since it was
    recorded has another module or logical module, and the rebaseline is how such a recording
    is converted (its new recording holds the current logical names). A plain replay keeps
    comparing them.

    Args:
        recorded_module: The module the record names, or None when it names none.
        loaded_module: The module of the loaded class it is compared with.
        is_rebaseline: True during a ``--rebaseline``.

    Returns:
        True when only the qualified names are compared.

    """
    return (
        is_rebaseline
        or recorded_module is None
        or SCRIPT_MODULE_NAME in {recorded_module, loaded_module}
    )


def check_recorded_game(
    *, header: Mapping[str, Any], game_class: type[Scene], is_rebaseline: bool = False
) -> None:
    """Refuse a recording of another game.

    A recording holding ``game`` (the game class's logical name, glitchygames/logical_names.py)
    must name the started game's logical name; the qualified names must be equal, and so must
    the logical modules unless ``modules_not_compared`` says otherwise (``__main__`` on either
    side: a game file run as a script, ``python paddleslap.py``, is the same game as its console
    script; or a ``--rebaseline``, the game having moved to another logical module). A plain
    replay of a recording whose game moved is refused with a message naming the rebaseline. A
    recording without ``game`` (made before logical names) must name the started game's class name,
    and its module too unless ``modules_not_compared`` says otherwise: under ``--rebaseline`` the
    module may differ (the game moved since; the new recording holds its logical name), while a
    plain replay of such a recording is refused with a message naming the rebaseline that converts
    it.

    Args:
        header: The recording's header fields.
        game_class: The game being started.
        is_rebaseline: True during a ``--rebaseline`` (rule 17).

    Raises:
        ReplayRefusedError: If the recording is of a different game, or was made before logical
            names by a game that has moved since and the run is not a rebaseline.

    """
    recorded_game = header.get(GAME_CLASS_HEADER_FIELD)
    recorded_logical_name = header.get(GAME_HEADER_FIELD)
    started_logical_name = logical_name(scene_class=game_class)
    if recorded_logical_name is not None:
        recorded_module, _, recorded_qualified_name = str(recorded_logical_name).partition(':')
        started_module, _, started_qualified_name = started_logical_name.partition(':')
        differs = recorded_qualified_name != started_qualified_name
        if (
            not differs
            and recorded_module != started_module
            and not modules_not_compared(
                recorded_module=recorded_module,
                loaded_module=started_module,
                is_rebaseline=is_rebaseline,
            )
        ):
            message = (
                f'The recording is of the game {recorded_logical_name}, and this game '
                f'({started_logical_name}) has the same name in another logical module: if it is '
                'this game, the game has since moved, and a replay cannot tell it from another '
                f'game of that name. Convert the recording with {REBASELINE_REMEDY}'
            )
            raise ReplayRefusedError(message)
        recorded_place = str(recorded_logical_name)
    else:
        recorded_module = header.get(GAME_MODULE_HEADER_FIELD)
        # The header's class name (game_class.__name__ when recorded): a game class is a
        # module's top-level class, so its qualified name
        differs = recorded_game != game_class.__name__
        modules_differ = recorded_module != game_class.__module__ and not modules_not_compared(
            recorded_module=recorded_module,
            loaded_module=game_class.__module__,
            is_rebaseline=is_rebaseline,
        )
        if not differs and modules_differ:
            message = (
                f'The recording was made before logical names, by the game {recorded_game} in '
                f'{recorded_module}, and this game ({started_logical_name}) is in '
                f'{game_class.__module__}: if it is this game, the game has since moved, and a '
                'replay cannot tell it from another game of that name. Convert the recording '
                f'with {REBASELINE_REMEDY}'
            )
            raise ReplayRefusedError(message)
        recorded_place = f'{recorded_game} ({recorded_module or "module not recorded"})'
    if differs:
        message = (
            f'The recording is of the game {recorded_place}, not {started_logical_name}; '
            'refusing to replay it'
        )
        raise ReplayRefusedError(message)


def apply_recorded_options(*, options: dict[str, Any], recorded: dict[str, Any]) -> None:
    """Put every recorded option except ``REPLAY_LOCAL_OPTIONS`` into ``options``.

    Args:
        options: The run's options (``GameEngine.OPTIONS``), changed in place.
        recorded: The header's ``options`` (JSON-safe; read back with ``value_from_json``).

    """
    for name, value in recorded.items():
        if name not in REPLAY_LOCAL_OPTIONS:
            options[name] = value_from_json(value)


def apply_recorded_screen_size(
    *, options: dict[str, Any], screen_size: tuple[int, int] | None
) -> None:
    """Open the replay's window at the size the recorded display had (rule 1).

    Games read the display's size, so the replay asks for the recorded ``screen_size``, not
    the recorded ``--resolution``: a window manager may have given the recorded window another
    size than it asked for. A header without one keeps the recorded ``--resolution``, with a
    warning.

    Args:
        options: The run's options, the recorded ones already in place; ``resolution`` is set.
        screen_size: The header's (width, height), or None when it holds none.

    """
    if screen_size is None:
        LOG.warning(
            'The recording does not hold the size of the display it was made on (no screen_size '
            'in its header); the replay opens its window at the recorded --resolution %s and '
            'diverges if the recorded window had another size',
            options.get('resolution'),
        )
        return
    width, height = screen_size
    options['resolution'] = f'{width}x{height}'


def display_size_refusal(*, header: Mapping[str, Any], display_size: tuple[int, int]) -> str | None:
    """Say why the replay is refused when its window did not open at the recorded size.

    Args:
        header: The recording's header fields (its ``screen_size``).
        display_size: The size the replay's display has, once opened.

    Returns:
        The refusal's message (one line, naming both sizes), or None when the sizes match or
        the recording holds no size.

    """
    recorded_size = recorded_screen_size(header=header)
    if recorded_size is None or display_size == recorded_size:
        return None
    recorded_width, recorded_height = recorded_size
    display_width, display_height = display_size
    return (
        f'it was recorded on a {recorded_width}x{recorded_height} display, but the window '
        f'opened at {display_width}x{display_height} (the window manager chose another size); '
        f'refusing to replay it'
    )


def start_replay(
    *,
    path: Path,
    game_class: type[Scene],
    options: dict[str, Any],
    use_fastevents: bool = False,
) -> ReplaySources:
    """Read a recording and prepare the run to replay it (rule 1); the caller installs it.

    A recording of another game raises ReplayRefusedError (``check_recorded_game``); an
    unreadable file raises TraceFormatError or OSError (``ReplaySources.from_path``). The engine
    exits with ``ExitCode.UNUSABLE_INPUT`` on each, or ``ExitCode.MISSING_INPUT`` for a missing
    file.

    Args:
        path: The recording.
        game_class: The game being started (its logical name (or, for a recording made before
            logical names, its class name and module) must match the recording's).
        options: The run's options, given the recorded ones in place; ``replay_fps`` (local, so
            never the recording's) picks the FPS source, ``RECORDED_REPLAY_FPS`` when unset, and
            ``replay_digest`` (local) the digest file (rule 12), none when unset, and
            ``headless`` (local) whether frames are paced (rule 13) and whether the replay is
            watched, starting at its start screen (rule 14) unless ``replay_pause_at_frame``
            (local) restarts it at a pause frame (rule 15; ignored, with a warning, when
            headless), ``replay_restart_handoff`` (local) where a supervised restart hands its
            own restart over (glitchygames/replay/rebuild.py), and ``replay_viewer_state``
            (local) the viewer state it starts with. ``rebaseline`` (local) makes the replay
            run on past divergences and exit ``SUCCESS`` once over (rule 17).
        use_fastevents: Drain the real queue with pygame.fastevent (``GameEngine.USE_FASTEVENTS``).

    Returns:
        The replay's sources, not yet installed.

    """
    # Local options (REPLAY_LOCAL_OPTIONS): the recorded ones applied below never replace them
    replay_digest = options.get('replay_digest')
    headless = bool(options.get('headless'))
    pause_at_frame = options.get('replay_pause_at_frame')
    if pause_at_frame is not None and headless:
        # A frame stream reads it itself (rule 20: where a restarted onion skin's child starts)
        if options.get('replay_frame_stream') is None:
            LOG.warning(
                '--replay-pause-at-frame is ignored with --headless: nobody could unpause the '
                'replay'
            )
        pause_at_frame = None
    restart_handoff = options.get('replay_restart_handoff')
    is_rebaseline = options.get('rebaseline') is not None
    replay_options = ReplayOptions(
        headless=headless,
        # A rebaseline writes the new recording whatever the result (rule 17)
        exit_policy=(
            ReplayExitPolicy.SUCCESS_AFTER_WRITING if is_rebaseline else ReplayExitPolicy.RESULT
        ),
        fps_source=options.get('replay_fps') or RECORDED_REPLAY_FPS,
        digest_path=None if replay_digest is None else Path(replay_digest),
        use_fastevents=use_fastevents,
        # Every watched replay starts at its start screen (rule 14), but a restart: the viewer
        # already started it (rule 15)
        wait_for_start=not headless and pause_at_frame is None,
        pause_at_frame=pause_at_frame,
        restart_handoff_path=None if restart_handoff is None else Path(restart_handoff),
        viewer_state=options.get('replay_viewer_state'),
        recording_path=path,
        # A rebaseline summarizes every frame that changed, so it never stops at the first
        stop_on_divergence=not is_rebaseline,
        # The rebaseline's new recording holds the scene starts, frame 0's included (rule 17)
        captures_scene_starts=is_rebaseline,
        # --max-processing-slowdown implies --compare-processing (replay/processing.py)
        compare_processing=bool(options.get('compare_processing'))
        or options.get('max_processing_slowdown') is not None,
        max_processing_slowdown_percent=options.get('max_processing_slowdown'),
        # Read before the recorded options are applied (random_seed is not local): a given seed
        # replaces the recorded one (rule 19)
        random_seed=options.get('random_seed'),
    )
    sources = ReplaySources.from_path(path=path, options=replay_options)
    check_recorded_game(header=sources.header, game_class=game_class, is_rebaseline=is_rebaseline)
    recorded_version = sources.header.get(ENGINE_VERSION_HEADER_FIELD)
    installed_version = installed_engine_version()
    if recorded_version != installed_version:
        LOG.warning(
            'The recording was made with engine version %s; this is %s. The replay may diverge',
            recorded_version,
            installed_version,
        )
    apply_recorded_options(options=options, recorded=sources.header.get(OPTIONS_HEADER_FIELD, {}))
    if sources.is_reseeded:
        # The run's options name the seed it runs under (rule 19), as a rebaseline's NEW does
        options['random_seed'] = sources.random_seed
    apply_recorded_screen_size(
        options=options, screen_size=recorded_screen_size(header=sources.header)
    )
    seed_engine_random(seed=sources.random_seed)
    if replay_options.fps_source == REAL_REPLAY_FPS:
        LOG.warning(REAL_REPLAY_FPS_NOTICE)
    return sources


def announce_replay(*, path: Path, sources: ReplaySources) -> None:
    """Log that the run replays the recording (and where a truncated one stops).

    Called by the engine once it is sure to replay (``--audit`` replays in child processes
    instead, and refuses a truncated recording), so nothing announces a replay that will not
    happen.

    Args:
        path: The recording.
        sources: Its replay sources.

    """
    if sources.recording.is_truncated:
        LOG.warning(
            '%s is cut off after %d complete frames; replaying up to there',
            path,
            sources.recording.frame_count,
        )
    LOG.info(
        'Replaying %s (%d frames, random seed %d)',
        path,
        sources.recording.frame_count,
        sources.random_seed,
    )
