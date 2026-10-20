"""Gameplay recording: ``--record-trace PATH`` writes a live session as a sprite trace.

A recording is a trace in the format of ``glitchygames/tracing.py`` (gzip JSON Lines, a
header line, then one keyframe or delta line per frame), so the tools that read golden
traces read recordings too. On top of the sprite fields it records what a later exact replay
(the planned ``--replay-trace``, see ``plans/future-work.md``) needs:

- Header: ``source: "recording"``, ``frame_seconds: null`` (frame times vary; each frame
  carries its own), plus what ``GameEngine`` adds: game and scene class names, engine,
  pygame and Python versions, every command-line option, the screen size, the start time
  (ISO 8601, informational) and ``random_seed`` (see ``glitchygames/randomness.py``).
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

Limits: an SDL-type event a game posts with ``pygame.event.post`` directly (not
``post_event``) is recorded as external, so replay would deliver it twice; games should post
through ``post_event``. A posted event identical to an SDL event in the same batch is told
apart only by count (the first match is the internal one; the two are indistinguishable).
Posts the next pump does not return (the queue was cleared, or the type is blocked) are
forgotten at that pump. Events posted before recording started are classified by type alone.

Polled input
------------

Input read by polling pygame's state, outside the event queue, is not in any batch and is not
recorded: ``pygame.key.get_pressed`` (``bitmappy/editor.py``, ``bitmappy/film_strip_sprite.py``,
``bitmappy/animated_canvas.py``, ``examples/dt_demo.py``), ``pygame.key.get_mods``
(``ui/text_widgets.py``), ``pygame.mouse.get_pos`` (``ui/inputs.py``, ``ui/text_widgets.py``,
``bitmappy/editor.py``, ``bitmappy/film_strip_sprite.py``, ``bitmappy/file_io.py``) and
joystick or controller ``get_axis`` (``bitmappy/controllers/event_handler.py``,
``events/joystick.py``, ``events/controller.py``, ``examples/joystick_demo.py``). An exact
replay of code that polls needs a per-frame snapshot of the polled state (a follow-up in
``plans/future-work.md``). The debug overlay's mouse poll (``scenes/scene.py``) only draws the
overlay and does not affect the simulation.

Saves
-----

The header's ``saves`` and a frame's ``saves_opened`` map each save namespace (a game's app
name) to ``glitchygames.state.sandbox.save_namespace_snapshot`` of its store: slot name -> the
envelope ``load_raw`` returned, or ``{"__unreadable__": {"kind": "corrupt" | "os_error",
"message": ...}}`` for a slot that could not be read, either with an optional ``"__listing__"``
(what ``list_slots`` reported). The format is described in glitchygames/state/sandbox.py.

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
``order``; the recorder's own fields (``dt``, ``event_batches``) avoid them.
"""

from __future__ import annotations

import dataclasses
import logging
import math
import numbers
from typing import TYPE_CHECKING, Any, Self, cast

import numpy as np
import pygame

from glitchygames.tracing import StableSpriteIds, TraceFormatError, TraceWriter, sample_scene_frame

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path
    from types import TracebackType

    from glitchygames.scenes import Scene

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
SCENE_START_FIELD = 'scene_start'
# Device enumeration answers (glitchygames/input/devices.py): a header field for answers given
# before recording started, and a frame field for answers given during that frame
DEVICE_ENUMERATION_FIELD = 'device_enumeration'
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
        is_tracking: True while a ``GameplayRecorder`` is open.
        pending: (type, attributes) of each tracked post, in posting order.

    """

    is_tracking: bool = False
    pending: list[tuple[int, dict[str, Any]]] = dataclasses.field(default_factory=list)


_INTERNAL_POSTS = InternalEventPosts()


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


def _take_internal_post(
    event: pygame.event.Event, pending: list[tuple[int, dict[str, Any]]]
) -> bool:
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
    was_posted_by_code = _take_internal_post(event, pending)
    if was_posted_by_code or event.type >= pygame.USEREVENT:
        return INTERNAL_ORIGIN
    return EXTERNAL_ORIGIN


class GameplayRecorder:
    """Write a live session to a trace file, one frame per ``record_frame()``.

    ``GameEngine`` creates it for ``--record-trace``. ``GameEngine._pump_events`` hands it
    every batch it reads from SDL's queue (``record_event_batch``), ``SceneManager`` calls
    ``record_frame`` once per frame after rendering, and ``GameEngine._shutdown`` closes it.
    Every frame is flushed to the file as it is written, so a killed process leaves every
    finished frame readable. While open, it tracks ``post_event`` posts to tell internal
    events from external ones.
    """

    def __init__(self, *, path: Path, header: dict[str, Any]) -> None:
        """Create the file, write the header and start tracking code-posted events.

        Args:
            path: The recording's file (parent directories are created).
            header: Header fields to add to ``source`` and ``frame_seconds``.

        """
        self._writer = TraceWriter(
            path=path,
            header={'source': RECORDING_SOURCE, 'frame_seconds': None, **header},
        )
        self._sprite_ids = StableSpriteIds()
        self._event_batches: list[list[dict[str, Any]]] = []
        self._previous_scene: Scene | None = None
        self._is_closed = False
        _INTERNAL_POSTS.is_tracking = True
        _INTERNAL_POSTS.pending.clear()

    @property
    def path(self) -> Path:
        """The recording's file."""
        return self._writer.path

    @property
    def frame_count(self) -> int:
        """How many frames have been written."""
        return self._writer.frame_count

    def record_event_batch(self, *, raw_events: Iterable[pygame.event.Event]) -> None:
        """Add one batch read from SDL's queue to the current frame, exactly as returned.

        Args:
            raw_events: The batch, in the order pygame returned it.

        """
        pending = _INTERNAL_POSTS.pending
        batch = [
            event_to_record(event=event, origin=event_origin(event=event, pending=pending))
            for event in raw_events
        ]
        if pending:
            # Posted but not returned: the queue was cleared or the type is blocked
            LOG.debug('Forgetting %d posted events the pump did not return', len(pending))
            pending.clear()
        self._event_batches.append(batch)

    def record_frame(self, *, dt: float, scene: Scene | None) -> None:
        """Write the frame just finished: its dt, its event batches and the scene's sprites.

        Args:
            dt: The frame's raw delta time (scene logic received it capped at the scene's
                MAX_FRAME_SECONDS, when the scene sets one).
            scene: The active scene at the end of the frame (None once the game has ended).

        """
        frame_record = sample_scene_frame(
            frame_number=self._writer.frame_count, scene=scene, sprite_ids=self._sprite_ids
        )
        frame_record[DT_FIELD] = dt
        frame_record[EVENT_BATCHES_FIELD] = self._event_batches
        is_new_scene_object = self._writer.frame_count > 0 and scene is not self._previous_scene
        self._writer.write_frame(frame_record=frame_record, force_keyframe=is_new_scene_object)
        self._previous_scene = scene
        self._event_batches = []

    def close(self) -> None:
        """Finish the file, stop tracking posts, and log the path and frame count (once)."""
        if self._is_closed:
            return
        self._is_closed = True
        _INTERNAL_POSTS.is_tracking = False
        _INTERNAL_POSTS.pending.clear()
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
