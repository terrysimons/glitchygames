"""Gameplay recording: ``--record-trace PATH`` writes a live session as a sprite trace.

A recording is a trace in the format of ``glitchygames/tracing.py`` (gzip JSON Lines, a
header line, then one keyframe or delta line per frame), so the tools that read golden
traces read recordings too. On top of the sprite fields it records what an exact replay
(``--replay-trace``, glitchygames/replay/driver.py) needs. ``GameEngine`` installs
``RecordingSources`` around the run's doors (glitchygames/sources.py), so everything the run
takes in is recorded where it passes through them.

- Header: ``source: "recording"``, ``frame_seconds: null`` (frame times vary; each frame
  carries its own), plus what ``GameEngine`` adds: game and scene class names, engine,
  pygame and Python versions, every command-line option, the screen size, the start time
  (``recorded_at``, ISO 8601; a replay's wall clock is this stamp plus its frame clock) and
  ``random_seed`` (see ``glitchygames/randomness.py``). And what the run took in before
  recording started (format version 3): ``saves``, a snapshot of every save store opened
  so far (see Saves below); ``devices``, the descriptors of devices opened so far (``kind``,
  ``device_index``, ``instance_id``, ``name``, ``guid`` and the axis, button, hat and ball
  counts; glitchygames/input/devices.py); and ``device_enumeration``, the enumeration and
  open answers given so far (``call``, ``device_index``, ``value``, ``error``), in order.
- Exactly one frame line per main-loop frame, numbered 0, 1, 2, ... in order: transition
  frames, paused frames, frames where nothing changed, and a final frame whose active scene
  is None (``scene: null``, no sprites) included.
- Each frame: ``dt``, the frame's raw delta time (``SceneManager.dt``). A transition's
  ``update`` receives it as is; scene logic (``Scene.dt_tick``) and the camera aim receive
  ``min(dt, MAX_FRAME_SECONDS)`` when the scene sets that cap, which a replay re-derives from
  the scene class's attribute. And ``event_batches``: one batch per time the engine read
  SDL's queue that frame (``GameEngine._pump_events``, the only place it does), in order, each
  holding the raw events exactly as pygame returned them, before any dispatch, discarding
  (transitions) or unhandled-event reporting. Every pump's batch is kept, including empty
  ones, so a replay can hand batch N to pump call N without guessing. What was delivered,
  discarded or unhandled is a deterministic function of the batch and the game state, which
  replay re-derives. Pumps after the final recorded frame (while the engine terminates and
  shuts down) belong to no frame and are not recorded.
- Format version 3 adds seven frame fields, each written only on frames where it is not
  empty: ``input_changes``, the frame's polled input (see Polled input below) as the fields
  that changed since the previous frame's snapshot (``glitchygames.input.state.
  snapshot_changes``; the first frame's against ``IDLE_INPUT``); ``control_events``, the
  supervisor actions recorded in the frame, in order (``ControlEvent.to_json``:
  ``{"kind": ..., **data}``; glitchygames/supervision.py); ``devices_opened``, descriptors of
  devices opened in the frame; ``saves_opened``, a snapshot of each save namespace first
  opened in the frame, taken before the game could write to it;
  ``device_enumeration``, the enumeration and open answers given in the frame (failures
  included, with their ``error``); and ``scene_start``, the start of the scene that began in
  the frame (``SceneStart.to_json``: ``scene_class``, ``arguments``,
  ``construction_random_states``, ``construction_frame_clock_seconds``,
  ``setup_random_states``, ``setup_frame_clock_seconds``, ``saves`` and
  ``first_logic_frame``; glitchygames/scene_start.py), written on the scene's first logic frame
  (the first frame whose ``dt_tick`` runs on it: frame 0 for the scene set up before the first
  frame, the frame after a ``next_scene`` switch, the first frame after a transition's ride;
  scene_start.py rule 7), once per scene: resuming it from the pause screen does not write it
  again, and a scene that never runs a logic frame (set up and switched away from within one
  frame, or still arriving when the recording stops) has no ``scene_start`` at all. Frame 0
  holds the first scene's start only when the run was started with ``--record-trace`` (or
  ``--rebaseline``): those runs capture scene starts from their start, while a recording
  started later in the run (``GameEngine.start_trace_recording``) holds the starts of scenes
  built after it began.
  ``scene_start`` needed no format version: readers pass frame fields they do not use through
  unchanged (glitchygames/tracing.py), and a replay never compares it (the replayed code
  captures its own); a recording without it replays as before and cannot be played in-game.
  And ``redelivered_events``: the events a playback scope held for the live game, delivered
  before the frame's first pump (see Playback scopes below), likewise version-free; a replay
  never serves it (it redelivers them itself), a playback starting on the frame does.
- A frame whose active scene is a different scene object from the previous frame's is a
  keyframe, even when both scenes have the same class (two floors of one game).

Event records
-------------

``{"type": <number>, "name": <pygame's event name>, "origin": "external" | "internal",
"attributes": {...}}``, with every attribute of the event.

Origin: ``internal`` means engine or game code posted the event; ``external`` means it came
from SDL (keyboard, mouse, controller, joystick, touch, window, device, drop, the OS asking
to quit). Replay re-injects only external events and takes internal ones from the live queue,
where the code that posted them posts them again. The rule:

- A type at or above ``pygame.USEREVENT`` (FPSEVENT, GAMEEVENT, MENUEVENT, any
  ``pygame.event.custom_type()``) is internal: SDL never generates those.
- An SDL-type event posted through ``post_event()`` (every post in the engine goes through
  it, such as the QUIT that ``quit_game()`` posts) is internal: while recording,
  ``post_event`` remembers each event it posted, and the next pump matches it (same type and
  attributes) to the batch.
- Anything else is external.

A recording made over a replay (``--rebaseline``, glitchygames/replay/rebaseline.py) takes each
event's origin from the replay's merge instead (``ReplayedRecording.last_batch_origins``): served
recorded events are external, the replayed code's posts internal, so nothing is classified again.

Limits: an SDL-type event a game posts with ``pygame.event.post`` directly (not
``post_event``) is recorded as external, so replay would deliver it twice; games should post
through ``post_event``. A posted event identical to an SDL event in the same batch is told
apart only by count (the first match is the internal one; the two are indistinguishable).
Posts the next pump does not return (the queue was cleared, or the type is blocked) are
forgotten at that pump. Events posted before recording started are classified by type alone.

Playback scopes
---------------

A recording wraps the run's installed doors, never a playback scope's (glitchygames/replay/
playback.py pushes ``PlaybackSources`` on top of them; glitchygames/sources.py). While a scope
plays a recording to a rebuilt scene, each recorded frame holds what the live session did:

- ``event_batches``: the batches the installed doors' pump returned, which the scope pumps once
  per pump of the frame: the player's real input (only the scope's exit check sees it), the
  window's QUIT, and the playback scene's own posts (internal). Replaying the session therefore
  replays the exit press and the scene's posts as they happened.
- ``input_changes``: the player's polled input (the scope reads the installed doors' snapshot
  every frame, then serves the recording's to the scene).
- ``dt``: the frame times the frames ran with, which are the played recording's.
- The sprites: the active scene's, which is the playback scene.
- ``control_events``: a ``playback`` marker (``{"kind": "playback", "source": <"demo" or
  "instant">, "frames": <frames to play>}``; glitchygames/supervision.py) on the frame the
  scope began. It is not applied again: replaying the session starts the scope again from the
  recorded input, and the marker is compared.
- No ``saves_opened``, ``devices_opened`` or ``device_enumeration`` from the playback scene:
  its saves are a sandbox and its devices the played recording's stand-ins, so nothing passes
  through the installed doors.
- No ``scene_start``: a scene that ends a frame while scoped doors are active (the playback
  scene, or a scene it switched to) is not one the live session began, so its start is never
  written (``RecordingSources._unrecorded_scene_start``).
- After the scope: the events it held for the live game (the live game's own posts and the
  player's releases, device and window events, in the order they were pumped) are delivered
  before the next pump (``sources.redeliver_events``). That frame records them in its
  ``redelivered_events`` field (event records with their origins); its ``event_batches`` do
  not hold them. A replay of the session does not serve the field: it holds and redelivers
  the events the same way from the scope frames' batches. A playback starting on that frame
  (a scene whose first logic frame follows the scope) serves them before its first pump
  (glitchygames/replay/driver.py, rule 18).

Polled input
------------

Input read by polling, outside the event queue (held keys, modifiers, the mouse, device axes,
buttons and hats on the joystick layer, and controller axes and buttons), is not in any batch.
Code reads it from the frame's ``InputSnapshot`` (``glitchygames.input.state.current_input()``),
never from pygame; the snapshot is taken once per frame through the doors, right after the
frame's pump, and recorded as the frame's ``input_changes``, so polled input replays exactly.

Saves
-----

The header's ``saves`` and a frame's ``saves_opened`` map each save namespace (a game's app
name) to ``glitchygames.state.sandbox.save_namespace_snapshot`` of its store: slot name -> the
envelope ``load_raw`` returned, or ``{"__unreadable__": {"kind": "corrupt" | "os_error",
"message": ...}}`` for a slot that could not be read, each with its ``"__file_extension__"``
and an optional ``"__listing__"`` (what ``list_slots`` reported). The format is described in
glitchygames/state/sandbox.py.

Attribute values
----------------

Stored JSON-safe by ``json_safe_value`` and read back by ``value_from_json``:

- ``None``, ``bool``, ``str`` (any Unicode, written as is), ``int`` (int subclasses such as
  enums are stored as their int value) and finite ``float`` values are stored as themselves.
  Other numbers (``numbers.Integral`` and ``numbers.Real``, such as numpy's ``int64`` and
  ``float32``) and numpy scalars whose ``item()`` is a bool, int or float (``numpy.bool_``)
  are stored as the plain JSON number or bool.
- A ``tuple`` (and a pygame ``Vector2``/``Vector3``) is a JSON array, and every JSON array
  reads back as a tuple: pygame puts tuples on events (``pos``, ``rel``, ``buttons``, a hat's
  ``value``) and games compare them with tuples, so replay must restore the type.
- Every other value is a JSON object with one ``__tag__`` key:
  ``{"__list__": [...]}``, ``{"__mapping__": {...}}`` (a dict with string keys),
  ``{"__pairs__": [[key, value], ...]}`` (a dict with other keys),
  ``{"__float__": "nan" | "inf" | "-inf"}``, ``{"__bytes__": "<hex>"}``.
- pygame objects are references: a ``pygame.Window`` is ``{"__ref__": "window", "id": n}``
  (``Window.id``) and a joystick is ``{"__ref__": "joystick", "instance_id": n}``; they read
  back as ``RecordedReference``. (Controller events carry ``instance_id`` integers, not
  objects.)
- A value nothing above covers (a sprite in a MENUEVENT payload, any other Python object)
  is ``{"__unrepresentable__": "<module.Class>"}`` and reads back as
  ``UnrepresentableValue``. The event is never dropped and recording never fails on a value.

The trace encoding reserves the frame fields ``kind``, ``changed``, ``added``, ``removed`` and
``order``; the recorder's own fields (``dt``, ``event_batches`` and the format-3 fields) avoid
them.
"""

from __future__ import annotations

import dataclasses
import logging
import math
import numbers
import weakref
from collections.abc import Sized
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Protocol, Self, TypedDict, Unpack, cast

import numpy as np
import pygame

from glitchygames.input.state import IDLE_INPUT, snapshot_changes
from glitchygames.scene_start import SceneStart, SceneStartCapture
from glitchygames.sources import has_scoped_sources, pending_redelivered_events
from glitchygames.state.sandbox import save_namespace_snapshot
from glitchygames.tracing import StableSpriteIds, TraceFormatError, TraceWriter, sample_scene_frame

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping
    from datetime import datetime
    from pathlib import Path
    from types import TracebackType

    from glitchygames.input.devices import DeviceRegistry
    from glitchygames.input.state import InputSnapshot
    from glitchygames.scenes import Scene
    from glitchygames.sources import EngineSources
    from glitchygames.state.manager import SaveManager
    from glitchygames.supervision import ControlEvent

LOG = logging.getLogger('game.recording')
LOG.addHandler(logging.NullHandler())

# The header's ``source`` field for traces recorded from play
RECORDING_SOURCE = 'recording'

# Frame fields a recording adds to each sprite frame
DT_FIELD = 'dt'
EVENT_BATCHES_FIELD = 'event_batches'
# Frame fields format version 3 adds (each written only on frames where it is not empty)
INPUT_CHANGES_FIELD = 'input_changes'
CONTROL_EVENTS_FIELD = 'control_events'
DEVICES_OPENED_FIELD = 'devices_opened'
SAVES_OPENED_FIELD = 'saves_opened'
# A scene's start (glitchygames/scene_start.py), on its first logic frame
SCENE_START_FIELD = 'scene_start'
# Events a playback scope held for the live game, delivered before the frame's first pump
# (glitchygames/sources.py redeliver_events)
REDELIVERED_EVENTS_FIELD = 'redelivered_events'
# Device enumeration answers (glitchygames/input/devices.py): a header field for answers given
# before recording started, and a frame field for answers given during that frame
DEVICE_ENUMERATION_FIELD = 'device_enumeration'
# The frame fields format version 3 adds, in RecordedFrameFields order (a version-2 frame has
# none of them)
RECORDING_FORMAT_THREE_FIELDS = (
    INPUT_CHANGES_FIELD,
    CONTROL_EVENTS_FIELD,
    DEVICES_OPENED_FIELD,
    SAVES_OPENED_FIELD,
    DEVICE_ENUMERATION_FIELD,
    SCENE_START_FIELD,
    REDELIVERED_EVENTS_FIELD,
)
# Header fields format version 3 adds
SAVES_HEADER_FIELD = 'saves'
DEVICES_HEADER_FIELD = 'devices'

# Event record fields and origins
EVENT_TYPE_FIELD = 'type'
EVENT_NAME_FIELD = 'name'
EVENT_ORIGIN_FIELD = 'origin'
EVENT_ATTRIBUTES_FIELD = 'attributes'
EXTERNAL_ORIGIN = 'external'
INTERNAL_ORIGIN = 'internal'

# Tags for attribute values JSON has no direct form for
LIST_TAG = '__list__'
MAPPING_TAG = '__mapping__'
PAIRS_TAG = '__pairs__'
FLOAT_TAG = '__float__'
BYTES_TAG = '__bytes__'
REFERENCE_TAG = '__ref__'
UNREPRESENTABLE_TAG = '__unrepresentable__'

# Reference kinds and the field holding each one's identifier
WINDOW_REFERENCE = 'window'
JOYSTICK_REFERENCE = 'joystick'
REFERENCE_IDENTIFIER_FIELDS = {WINDOW_REFERENCE: 'id', JOYSTICK_REFERENCE: 'instance_id'}

# Containers json_safe_value converts item by item
type JsonSafeContainer = (
    tuple[object, ...] | list[object] | dict[object, object] | pygame.Vector2 | pygame.Vector3
)

_NON_FINITE_FLOAT_NAMES = {'nan': math.nan, 'inf': math.inf, '-inf': -math.inf}
_KEY_VALUE_PAIR_LENGTH = 2


@dataclasses.dataclass(frozen=True)
class RecordedReference:
    """A pygame object an event referred to, read back from a recording.

    Attributes:
        kind: ``'window'`` or ``'joystick'``.
        identifier: The window's ``id`` or the joystick's instance id.

    """

    kind: str
    identifier: int


@dataclasses.dataclass(frozen=True)
class UnrepresentableValue:
    """An event attribute a recording could not store, read back from it.

    Attributes:
        type_name: The value's ``module.QualifiedClassName``.

    """

    type_name: str


@dataclasses.dataclass
class InternalEventPosts:
    """Events engine or game code posted (``post_event``) that no pump has returned yet.

    Attributes:
        owner_count: How many owners want posts tracked: each open ``GameplayRecorder``, and a
            replay's sources while installed (``start_tracking_internal_posts``).
        pending: (type, attributes) of each tracked post, in posting order.

    """

    owner_count: int = 0
    pending: list[tuple[int, dict[str, Any]]] = dataclasses.field(default_factory=list)

    @property
    def is_tracking(self) -> bool:
        """True while at least one owner holds the tracker."""
        return self.owner_count > 0


_INTERNAL_POSTS = InternalEventPosts()


def start_tracking_internal_posts() -> None:
    """Become one more owner of the internal-post tracker (tracking runs from the first owner).

    A ``GameplayRecorder`` owns it while open, and a replay's sources while installed, so
    closing a recorder never switches tracking off under a live replay.
    """
    _INTERNAL_POSTS.owner_count += 1


def stop_tracking_internal_posts() -> None:
    """Give up one ownership; at zero owners tracking stops and pending posts are forgotten."""
    _INTERNAL_POSTS.owner_count = max(0, _INTERNAL_POSTS.owner_count - 1)
    if _INTERNAL_POSTS.owner_count == 0:
        _INTERNAL_POSTS.pending.clear()


def reset_internal_post_tracking() -> None:
    """Forget every owner and every pending post (a new run, or a test)."""
    _INTERNAL_POSTS.owner_count = 0
    _INTERNAL_POSTS.pending.clear()


def pending_internal_posts() -> list[tuple[int, dict[str, Any]]]:
    """Return the tracker's posts no pump has returned yet: its own list, not a copy.

    ``event_origin`` removes each match from it, so a pump classifying its batch with it
    consumes the posts it matched.

    Returns:
        (type, attributes) of each pending post, in posting order.

    """
    return _INTERNAL_POSTS.pending


def post_event(event: pygame.event.Event) -> bool:
    """Post an event from engine or game code; a recording marks it ``origin: internal``.

    Use this instead of ``pygame.event.post`` so recordings can tell code-posted events from
    SDL's (see the module docstring for the rule).

    Args:
        event: The event to post.

    Returns:
        True if pygame queued the event (False if its type is blocked).

    """
    was_posted = bool(pygame.event.post(event))
    if was_posted and _INTERNAL_POSTS.is_tracking:
        _INTERNAL_POSTS.pending.append((event.type, dict(event.dict)))
    return was_posted


def _non_finite_float_name(value: float) -> str:
    if math.isnan(value):
        return 'nan'
    return 'inf' if value > 0 else '-inf'


def _json_safe_scalar(value: float | str | None) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return str(value)
    if isinstance(value, int):
        return int(value)
    if math.isfinite(value):
        return float(value)
    return {FLOAT_TAG: _non_finite_float_name(value)}


def _json_safe_number(value: numbers.Real | np.generic) -> Any:
    """Store a number that is not a Python bool, int or float (a numpy scalar) as one.

    ``numbers.Integral`` and ``numbers.Real`` cover numpy's integer and floating scalars;
    ``numpy.bool_`` is neither, so any other numpy scalar is unwrapped with ``item()``.

    Returns:
        A plain JSON value, or an ``__unrepresentable__`` tag when the scalar has no plain form.

    """
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        return _json_safe_scalar(float(value))
    plain_value = value.item()
    if isinstance(plain_value, (bool, int, float)):
        return _json_safe_scalar(plain_value)
    return _json_safe_object(value)


def _json_safe_container(value: JsonSafeContainer) -> Any:
    if isinstance(value, list):
        return {LIST_TAG: [json_safe_value(item) for item in value]}
    if isinstance(value, dict):
        if all(isinstance(key, str) for key in value):
            return {MAPPING_TAG: {str(key): json_safe_value(item) for key, item in value.items()}}
        return {
            PAIRS_TAG: [
                [json_safe_value(key), json_safe_value(item)] for key, item in value.items()
            ]
        }
    # A tuple or a vector
    return [json_safe_value(item) for item in cast('Iterable[object]', value)]


def _json_safe_object(value: object) -> dict[str, Any]:
    if isinstance(value, pygame.Window):
        return {REFERENCE_TAG: WINDOW_REFERENCE, 'id': value.id}
    if isinstance(value, pygame.joystick.JoystickType):
        return {REFERENCE_TAG: JOYSTICK_REFERENCE, 'instance_id': value.get_instance_id()}
    value_class = type(value)
    return {UNREPRESENTABLE_TAG: f'{value_class.__module__}.{value_class.__qualname__}'}


def json_safe_value(value: object) -> Any:
    """Convert an event attribute value to a JSON-safe form ``value_from_json`` reverses.

    Args:
        value: Any value pygame (or a game) put on an event.

    Returns:
        A value ``json.dumps(..., allow_nan=False)`` accepts. The module docstring lists the
        forms. A value it cannot store becomes an ``__unrepresentable__`` tag.

    """
    if value is None or isinstance(value, (bool, str, int, float)):
        return _json_safe_scalar(value)
    if isinstance(value, (tuple, list, dict, pygame.Vector2, pygame.Vector3)):
        return _json_safe_container(cast('JsonSafeContainer', value))
    if isinstance(value, (bytes, bytearray)):
        return {BYTES_TAG: bytes(value).hex()}
    if isinstance(value, (numbers.Real, np.generic)):
        return _json_safe_number(value)
    return _json_safe_object(value)


def _malformed(encoded: object) -> TraceFormatError:
    return TraceFormatError(f'Malformed recorded value {encoded!r}')


def _reference_from_json(encoded: dict[str, Any]) -> RecordedReference:
    kind = encoded[REFERENCE_TAG]
    identifier_field = REFERENCE_IDENTIFIER_FIELDS.get(kind)
    if identifier_field is None or set(encoded) != {REFERENCE_TAG, identifier_field}:
        raise _malformed(encoded)
    identifier = encoded[identifier_field]
    if isinstance(identifier, bool) or not isinstance(identifier, int):
        raise _malformed(encoded)
    return RecordedReference(kind=kind, identifier=identifier)


def _list_from_json(encoded: dict[str, Any], payload: object) -> list[object]:
    if not isinstance(payload, list):
        raise _malformed(encoded)
    return [value_from_json(item) for item in cast('list[object]', payload)]


def _mapping_from_json(encoded: dict[str, Any], payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise _malformed(encoded)
    return {
        str(key): value_from_json(item) for key, item in cast('dict[str, object]', payload).items()
    }


def _pairs_from_json(encoded: dict[str, Any], payload: object) -> dict[object, object]:
    if not isinstance(payload, list) or not all(
        isinstance(pair, list) and len(cast('list[object]', pair)) == _KEY_VALUE_PAIR_LENGTH
        for pair in cast('list[object]', payload)
    ):
        raise _malformed(encoded)
    return {
        value_from_json(key): value_from_json(item)
        for key, item in cast('list[list[object]]', payload)
    }


def _float_from_json(encoded: dict[str, Any], payload: object) -> float:
    if not isinstance(payload, str) or payload not in _NON_FINITE_FLOAT_NAMES:
        raise _malformed(encoded)
    return _NON_FINITE_FLOAT_NAMES[payload]


def _bytes_from_json(encoded: dict[str, Any], payload: object) -> bytes:
    if not isinstance(payload, str):
        raise _malformed(encoded)
    try:
        return bytes.fromhex(payload)
    except ValueError as error:
        raise _malformed(encoded) from error


def _unrepresentable_from_json(encoded: dict[str, Any], payload: object) -> UnrepresentableValue:
    if not isinstance(payload, str):
        raise _malformed(encoded)
    return UnrepresentableValue(type_name=payload)


# Single-key tag -> its decoder (each raises TraceFormatError on a payload of the wrong form)
_TAG_DECODERS: dict[str, Callable[[dict[str, Any], object], object]] = {
    LIST_TAG: _list_from_json,
    MAPPING_TAG: _mapping_from_json,
    PAIRS_TAG: _pairs_from_json,
    FLOAT_TAG: _float_from_json,
    BYTES_TAG: _bytes_from_json,
    UNREPRESENTABLE_TAG: _unrepresentable_from_json,
}


def _tagged_value_from_json(encoded: dict[str, Any]) -> object:
    if REFERENCE_TAG in encoded:
        return _reference_from_json(encoded)
    if len(encoded) != 1:
        raise _malformed(encoded)
    tag, payload = next(iter(encoded.items()))
    decoder = _TAG_DECODERS.get(tag)
    if decoder is None:
        raise _malformed(encoded)
    return decoder(encoded, payload)


def value_from_json(encoded: object) -> object:
    """Rebuild an event attribute value from its ``json_safe_value`` form.

    A JSON object that is not one of the tagged forms raises ``TraceFormatError``.

    Args:
        encoded: The value as read back from JSON.

    Returns:
        The original value; a ``RecordedReference`` for a pygame object, an
        ``UnrepresentableValue`` for a value the recording could not store.

    """
    if isinstance(encoded, list):
        return tuple(value_from_json(item) for item in cast('list[object]', encoded))
    if isinstance(encoded, dict):
        return _tagged_value_from_json(cast('dict[str, Any]', encoded))
    return encoded


def event_to_record(*, event: pygame.event.Event, origin: str) -> dict[str, Any]:
    """Describe a pygame event as a JSON-safe record, with every attribute.

    Args:
        event: The raw pygame event.
        origin: ``EXTERNAL_ORIGIN`` or ``INTERNAL_ORIGIN``.

    Returns:
        ``{"type": <number>, "name": <pygame's event name>, "origin": ..., "attributes":
        {...}}``.

    """
    return {
        EVENT_TYPE_FIELD: event.type,
        EVENT_NAME_FIELD: pygame.event.event_name(event.type),
        EVENT_ORIGIN_FIELD: origin,
        EVENT_ATTRIBUTES_FIELD: {
            str(name): json_safe_value(value) for name, value in event.dict.items()
        },
    }


def event_from_record(record: dict[str, Any]) -> pygame.event.Event:
    """Rebuild a pygame event from its record.

    Args:
        record: A record written by ``event_to_record`` (read back from JSON).

    Returns:
        An event with the recorded type and attribute values.

    Raises:
        TraceFormatError: If the record is malformed.

    """
    try:
        event_type = int(record[EVENT_TYPE_FIELD])
        attributes = {
            str(name): value_from_json(value)
            for name, value in record[EVENT_ATTRIBUTES_FIELD].items()
        }
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        message = f'Malformed event record {record!r} ({error!r})'
        raise TraceFormatError(message) from error
    return pygame.event.Event(event_type, attributes)


def take_internal_post(
    *, event: pygame.event.Event, pending: list[tuple[int, dict[str, Any]]]
) -> bool:
    """Remove the first post in ``pending`` with ``event``'s type and attributes, if any.

    Args:
        event: An event a pump returned.
        pending: Posts not yet matched to a pumped event (``pending_internal_posts()`` or a
            copy of it).

    Returns:
        True when a post matched (and was removed): code posted ``event``.

    """
    for index, (event_type, attributes) in enumerate(pending):
        if event_type == event.type and attributes == event.dict:
            del pending[index]
            return True
    return False


def event_origin(*, event: pygame.event.Event, pending: list[tuple[int, dict[str, Any]]]) -> str:
    """Decide whether a pumped event came from SDL or from code (see the module docstring).

    Args:
        event: An event the pump returned.
        pending: Posts not yet matched to a pumped event; a match is removed from it.

    Returns:
        ``INTERNAL_ORIGIN`` or ``EXTERNAL_ORIGIN``.

    """
    was_posted_by_code = take_internal_post(event=event, pending=pending)
    if was_posted_by_code or event.type >= pygame.USEREVENT:
        return INTERNAL_ORIGIN
    return EXTERNAL_ORIGIN


class TraceRecordingAlreadyStartedError(RuntimeError):
    """GameEngine.start_trace_recording() was called while the engine was already recording."""


class RecordedFrameFields(TypedDict, total=False):
    """The format-3 frame fields ``GameplayRecorder.record_frame`` takes by keyword.

    Each key is the frame field's name (the ``*_FIELD`` constants). Keyword arguments rather
    than parameters, so ``record_frame`` keeps one parameter per concept (dt, scene, fields).

    Attributes:
        input_changes: The frame's polled-input changes (``snapshot_changes``).
        control_events: The frame's control events (``ControlEvent.to_json``), in order.
        devices_opened: Descriptors of devices opened in the frame (``to_json``).
        saves_opened: Save namespaces first opened in the frame, each snapshotted.
        device_enumeration: Enumeration answers given in the frame (``to_json``).
        scene_start: The start of the scene that began in the frame (``SceneStart.to_json``).
        redelivered_events: Event records delivered before the frame's first pump that no door
            pumped in it (a playback scope's held events; ``event_to_record``).

    """

    input_changes: dict[str, Any] | None
    control_events: list[dict[str, Any]] | None
    devices_opened: list[dict[str, Any]] | None
    saves_opened: dict[str, Any] | None
    device_enumeration: list[dict[str, Any]] | None
    scene_start: dict[str, Any] | None
    redelivered_events: list[dict[str, Any]] | None


class RecordedFrameFieldSource(Protocol):
    """A recording's frames, as a recording made over its replay copies them."""

    def recorded_frame_fields(self, *, frame_index: int) -> dict[str, Any]:
        """Return a frame's recorded saves and device fields (whichever it has; none past the end).

        Args:
            frame_index: The recording's frame index.

        Returns:
            Its ``saves_opened``, ``devices_opened`` and ``device_enumeration``.

        """
        ...


class ReplayedRecording(Protocol):
    """Doors that serve a recording (a replay's), which a recording made over them copies.

    ``RecordingSources`` given one (``--rebaseline``) record what these doors served instead of
    asking the live trackers: each event's origin from the replay's merge, and each frame's
    saves and device fields from the recording being replayed.
    """

    @property
    def recording(self) -> RecordedFrameFieldSource:
        """The recording being replayed."""
        ...

    def last_batch_origins(self) -> list[str]:
        """Return each event's origin in the batch the last pump returned."""
        ...


class GameplayRecorder:
    """Write a live session to a trace file, one frame per ``record_frame()``.

    ``GameEngine`` creates it for ``--record-trace`` and installs ``RecordingSources`` around
    the run's doors: they hand it every batch the event pump returns (``record_event_batch``)
    and, once per frame after rendering, the frame's fields (``record_frame``).
    ``GameEngine._shutdown`` closes it. Every frame is flushed to the file as it is written, so
    a killed process leaves every finished frame readable. While open, it owns the
    internal-post tracker, to tell internal events from external ones.
    """

    def __init__(self, *, path: Path, header: dict[str, Any]) -> None:
        """Create the file, write the header and start tracking code-posted events.

        Args:
            path: The recording's file (parent directories are created).
            header: Header fields to add to ``source`` and ``frame_seconds``.

        """
        self._header = {'source': RECORDING_SOURCE, 'frame_seconds': None, **header}
        self._writer = TraceWriter(path=path, header=self._header)
        self._sprite_ids = StableSpriteIds()
        self._event_batches: list[list[dict[str, Any]]] = []
        self._previous_scene: Scene | None = None
        self._is_closed = False
        start_tracking_internal_posts()

    @property
    def path(self) -> Path:
        """The recording's file."""
        return self._writer.path

    @property
    def frame_count(self) -> int:
        """How many frames have been written."""
        return self._writer.frame_count

    @property
    def header(self) -> Mapping[str, Any]:
        """The header written to the file (read-only)."""
        return MappingProxyType(self._header)

    @property
    def is_closed(self) -> bool:
        """True once ``close()`` has run."""
        return self._is_closed

    def record_event_batch(
        self, *, raw_events: Iterable[pygame.event.Event], origins: list[str] | None = None
    ) -> None:
        """Add one batch the event pump returned to the current frame, exactly as returned.

        Args:
            raw_events: The batch, in the order the pump returned it.
            origins: Each event's origin, when the pump already knows it (a replay's merge:
                served recorded events are external, passed-through live events internal);
                None classifies the batch with the internal-post tracker.

        """
        pending = _INTERNAL_POSTS.pending
        if origins is None:
            batch = [
                event_to_record(event=event, origin=event_origin(event=event, pending=pending))
                for event in raw_events
            ]
        else:
            batch = [
                event_to_record(event=event, origin=origin)
                for event, origin in zip(raw_events, origins, strict=True)
            ]
        if origins is None and pending:
            # Posted but not returned: the queue was cleared or the type is blocked
            LOG.debug('Forgetting %d posted events the pump did not return', len(pending))
            pending.clear()
        self._event_batches.append(batch)

    def record_frame(
        self, *, dt: float, scene: Scene | None, **frame_fields: Unpack[RecordedFrameFields]
    ) -> None:
        """Write the frame just finished: its dt, its event batches and the scene's sprites.

        The format-3 fields (``RecordedFrameFields``, see the module docstring) are written
        only when given and not empty, so idle frames stay small.

        Args:
            dt: The frame's raw delta time (scene logic received it capped at the scene's
                MAX_FRAME_SECONDS, when the scene sets one).
            scene: The active scene at the end of the frame (None once the game has ended).
            **frame_fields: The frame's format-3 fields, by keyword.

        """
        frame_record = sample_scene_frame(
            frame_number=self._writer.frame_count, scene=scene, sprite_ids=self._sprite_ids
        )
        frame_record[DT_FIELD] = dt
        frame_record[EVENT_BATCHES_FIELD] = self._event_batches
        for field_name, value in frame_fields.items():
            # Omitted: a field not given or None, and an empty container (every format-3 field
            # is a dict or list). Any other value is written, so a future scalar field's 0 or
            # False is kept, not dropped as "empty"
            is_empty_container = isinstance(value, Sized) and len(value) == 0
            if value is not None and not is_empty_container:
                frame_record[field_name] = value
        is_new_scene_object = self._writer.frame_count > 0 and scene is not self._previous_scene
        self._writer.write_frame(frame_record=frame_record, force_keyframe=is_new_scene_object)
        self._previous_scene = scene
        self._event_batches = []

    def close(self) -> None:
        """Finish the file, give up tracking posts, and log the path and frame count (once)."""
        if self._is_closed:
            return
        self._is_closed = True
        stop_tracking_internal_posts()
        self._writer.close()
        self._previous_scene = None
        LOG.info('Recorded %d frames to %s', self.frame_count, self.path)

    def __enter__(self) -> Self:
        """Return the recorder for a ``with`` block.

        Returns:
            This recorder.

        """
        return self

    def __exit__(
        self,
        _exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the recorder when the ``with`` block ends."""
        self.close()


class RecordingSources:
    """Doors that record everything passing through them (implements EngineSources).

    ``GameEngine.start_trace_recording`` installs them around the run's doors (``inner``)
    before the first frame. Every read is served by ``inner``; what the run takes in is written
    to the recorder:

    - ``pump_events``: each batch, raw, with its events' origins (``record_event_batch``).
    - ``input_snapshot``: the frame's polled input, recorded at ``end_frame`` as its changes
      from the snapshot recorded the frame before (``IDLE_INPUT`` before the first).
    - ``saves``: a namespace first opened while recording is snapshotted into the frame's
      ``saves_opened`` before the game can write to it (namespaces already in the header's
      ``saves`` are not).
    - ``devices``: the registry's opened-device descriptors and enumeration answers, taken at
      ``end_frame`` into ``devices_opened`` and ``device_enumeration``.
    - ``captures_scene_starts``: True while recording, so every scene built captures its start
      (glitchygames/scene_start.py); ``end_frame`` writes the start of a scene that ends
      a frame active for the first time into that frame's ``scene_start`` (once per scene).
    - ``end_frame``: writes the frame (with its control events), then lets ``inner`` end it.

    Over a replay (``replayed`` given: ``--rebaseline``), what the replay served is recorded
    as served: each batch's origins come from ``replayed.last_batch_origins()``, and each
    frame's ``saves_opened``, ``devices_opened`` and ``device_enumeration`` are copied from the
    replayed recording's frame (``replayed.recording.recorded_frame_fields``), not snapshotted
    or taken from the registry. Frames are matched by count: both start at frame 0 and end one
    frame per ``end_frame``.

    Once the recorder is closed (``GameEngine.stop_trace_recording``, as the run ends) they only
    delegate.

    Attributes:
        inner: The doors read through.
        random_seed: The run's master seed (``inner``'s).

    """

    def __init__(
        self,
        *,
        inner: EngineSources,
        recorder: GameplayRecorder,
        replayed: ReplayedRecording | None = None,
    ) -> None:
        """Wrap ``inner`` and record to ``recorder``.

        Args:
            inner: The doors to read through (the run's live doors, or a replay's).
            recorder: The open recorder; its header's ``saves`` lists the namespaces already
                recorded.
            replayed: The replay ``inner`` is when recording over a replay (``--rebaseline``):
                origins and saves and device fields are copied from it. None for live doors.

        """
        self.inner = inner
        self._replayed = replayed
        self.random_seed = inner.random_seed
        self._recorder = recorder
        self._recorded_save_namespaces: set[str] = set(recorder.header.get(SAVES_HEADER_FIELD, {}))
        self._recorded_snapshot: InputSnapshot = IDLE_INPUT
        self._frame_snapshot: InputSnapshot | None = None
        self._frame_saves_opened: dict[str, Any] = {}
        # Events a playback scope held, delivered before this frame's first pump
        self._frame_redelivered_events: list[dict[str, Any]] = []
        # Scenes whose start a frame already holds (weak: a scene left behind is not kept alive)
        self._scenes_with_recorded_start: weakref.WeakSet[Scene] = weakref.WeakSet()

    @property
    def opened_save_namespaces(self) -> Mapping[str, SaveManager]:
        """Every save store ``inner`` opened so far, by namespace."""
        return self.inner.opened_save_namespaces

    @property
    def captures_scene_starts(self) -> bool:
        """True while recording (the frames hold the starts); once closed, ``inner``'s."""
        return not self._recorder.is_closed or self.inner.captures_scene_starts

    @property
    def stop_requested(self) -> bool:
        """Whether ``inner`` wants the run to end."""
        return self.inner.stop_requested

    def on_installed(self) -> None:
        """Tell ``inner`` it is (again) the run's doors, behind these."""
        self.inner.on_installed()

    def on_uninstalled(self) -> None:
        """Tell ``inner`` it stopped being the run's doors."""
        self.inner.on_uninstalled()

    def pump_events(self) -> list[pygame.event.Event]:
        """Return ``inner``'s next batch, recorded exactly as returned.

        Returns:
            The batch, in queue order.

        """
        raw_events = self.inner.pump_events()
        if self._recorder.is_closed:
            return raw_events
        # Waiting for this pump's batch (GameEngine._pump_events takes them after it): the
        # frame records them, so a playback starting on this frame delivers them too
        self._frame_redelivered_events.extend(
            event_to_record(event=event, origin=origin)
            for event, origin in pending_redelivered_events()
        )
        if self._replayed is None:
            # Live inner doors: origins come from the internal-post tracker
            self._recorder.record_event_batch(raw_events=raw_events)
        else:
            # A replay's merge already knows them (its pump consumed the tracker's posts)
            self._recorder.record_event_batch(
                raw_events=raw_events, origins=self._replayed.last_batch_origins()
            )
        return raw_events

    def frame_seconds(self, *, measured: float) -> float:
        """Return ``inner``'s frame time for logic.

        Returns:
            Seconds.

        """
        return self.inner.frame_seconds(measured=measured)

    def performance_frame_seconds(self, *, measured: float, frame_seconds: float) -> float:
        """Return ``inner``'s frame time for FPS events and the performance statistics.

        Returns:
            Seconds.

        """
        return self.inner.performance_frame_seconds(measured=measured, frame_seconds=frame_seconds)

    def paced_frame_seconds(self) -> float | None:
        """Return how ``inner`` paces the frame starting now (not recorded: it changes no input).

        Returns:
            Seconds, or None for the target FPS.

        """
        return self.inner.paced_frame_seconds()

    def hold_frame(self) -> bool:
        """Return whether ``inner`` holds the frame (not recorded: a held frame never runs).

        Returns:
            True to run no frame now.

        """
        return self.inner.hold_frame()

    @property
    def presents_frames(self) -> bool:
        """Whether ``inner`` presents the frames as they run."""
        return self.inner.presents_frames

    @property
    def draws_overlay(self) -> bool:
        """Whether ``inner`` draws an overlay of its own."""
        return self.inner.draws_overlay

    def draw_overlay(self, *, surface: pygame.Surface) -> None:
        """Let ``inner`` draw its overlay (never recorded: it is drawn on the presented frame)."""
        self.inner.draw_overlay(surface=surface)

    def input_snapshot(self) -> InputSnapshot:
        """Return ``inner``'s polled input, remembered for this frame's ``input_changes``.

        Returns:
            The snapshot.

        """
        snapshot = self.inner.input_snapshot()
        self._frame_snapshot = snapshot
        return snapshot

    def devices(self) -> DeviceRegistry:
        """Return ``inner``'s device registry (its answers are taken at ``end_frame``).

        Returns:
            The registry.

        """
        return self.inner.devices()

    def saves(self, *, namespace: str) -> SaveManager:
        """Return ``inner``'s store, snapshotted first if recording has not seen it yet.

        Args:
            namespace: The game's app name.

        Returns:
            The store.

        """
        store = self.inner.saves(namespace=namespace)
        # Over a replay, the frame's recorded saves_opened is copied at end_frame instead
        if (
            self._replayed is None
            and not self._recorder.is_closed
            and namespace not in self._recorded_save_namespaces
        ):
            self._recorded_save_namespaces.add(namespace)
            self._frame_saves_opened[namespace] = save_namespace_snapshot(saves=store)
        return store

    def wall_clock_time(self) -> datetime:
        """Return ``inner``'s wall-clock time.

        Returns:
            Timezone-aware UTC time.

        """
        return self.inner.wall_clock_time()

    def control_events_for_frame(self, *, frame_number: int) -> list[ControlEvent]:
        """Return the control events ``inner`` schedules for ``frame_number``.

        Returns:
            The control events.

        """
        return self.inner.control_events_for_frame(frame_number=frame_number)

    def end_frame(
        self,
        *,
        frame_number: int,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
    ) -> None:
        """Write the frame with everything that passed through the doors, then end it inside.

        The device answers are taken before ``inner.end_frame``, which discards untaken ones.
        Over a replay, the saves and device fields are the replayed recording's frame's.
        """
        if not self._recorder.is_closed:
            if self._replayed is None:
                registry = self.inner.devices()
                devices_opened = [
                    descriptor.to_json() for descriptor in registry.take_opened_descriptors()
                ]
                device_enumeration = [
                    answer.to_json() for answer in registry.take_enumeration_answers()
                ]
                saves_opened = self._frame_saves_opened
            else:
                # The frame being recorded is the replay's current one: both count from 0
                recorded_fields = self._replayed.recording.recorded_frame_fields(
                    frame_index=self._recorder.frame_count
                )
                devices_opened = recorded_fields.get(DEVICES_OPENED_FIELD, [])
                device_enumeration = recorded_fields.get(DEVICE_ENUMERATION_FIELD, [])
                saves_opened = recorded_fields.get(SAVES_OPENED_FIELD, {})
            scene_start = self._unrecorded_scene_start(scene=scene)
            input_changes: dict[str, Any] = {}
            if self._frame_snapshot is not None:
                input_changes = snapshot_changes(
                    previous=self._recorded_snapshot, current=self._frame_snapshot
                )
                self._recorded_snapshot = self._frame_snapshot
            self._recorder.record_frame(
                dt=dt,
                scene=scene,
                input_changes=input_changes,
                control_events=[control_event.to_json() for control_event in control_events],
                devices_opened=devices_opened,
                saves_opened=saves_opened,
                device_enumeration=device_enumeration,
                scene_start=None if scene_start is None else scene_start.to_json(),
                redelivered_events=self._frame_redelivered_events,
            )
        self._frame_snapshot = None
        self._frame_saves_opened = {}
        self._frame_redelivered_events = []
        self.inner.end_frame(
            frame_number=frame_number, dt=dt, scene=scene, control_events=control_events
        )

    def _unrecorded_scene_start(self, *, scene: Scene | None) -> SceneStart | None:
        """Return the start of the scene ending this frame, unless a frame already holds it.

        A start is complete once its first logic frame began (glitchygames/scene_start.py,
        rule 7: at the top of that frame), so the first frame that ends with it active and
        complete is its first logic frame: frame 0 for the scene set up before the first frame.
        Resuming it from the pause screen does not record it again. A scene that never runs a
        logic frame (set up and switched away from within one frame) is never written. Nor is
        the start of a scene that ends a frame while scoped doors are active (a playback
        scope's scene; see Playback scopes in the module docstring): the live session did not
        begin it.

        Args:
            scene: The active scene at the end of the frame.

        Returns:
            The start to write, or None (no scene, no capture, or already written).

        """
        if scene is None or scene in self._scenes_with_recorded_start:
            return None
        # Scoped doors serve this frame (a playback scope): its scene is not the session's
        if has_scoped_sources():
            return None
        # Looked up by name, as SceneManager._setup_new_scene does: a SceneInterface stand-in
        # has no capture
        start_capture = getattr(scene, 'scene_start_capture', None)
        if (
            not isinstance(start_capture, SceneStartCapture)
            or start_capture.start is None
            or start_capture.start.first_logic_frame is None
        ):
            return None
        self._scenes_with_recorded_start.add(scene)
        return start_capture.start
