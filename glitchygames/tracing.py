"""Sprite traces: the rect and visibility of every sprite in the active scene, frame by frame.

A trace in memory is a dict of header fields plus ``frames``, a list of full frame records::

    {
        'game': ...,
        'frame_seconds': ...,
        'frames': [
            {
                'frame': n,
                'scene': 'SceneClassName',
                'sprites': [
                    {'id': '<ClassName>#<n>', 'rect': [x, y, width, height], 'visible': bool},
                    ...,
                ],
            },
            ...,
        ],
    }

On disk (format version 2) a trace is gzip-compressed JSON Lines:

- Line 1 is the header: ``{"format_version": 2, ...}`` followed by the trace's header fields
  (``game`` or ``source``, ``frame_seconds`` or ``null`` for a live recording, and any other
  metadata the writer was given).
- Then one line per frame. Frame 0, every frame whose scene differs from the previous
  frame's, and any frame written with ``force_keyframe=True`` are keyframes, holding the
  full sprite list:
  ``{"frame": n, "kind": "keyframe", "scene": ..., "sprites": [...]}``.
  Every other frame is a delta against the previous frame:
  ``{"frame": n, "kind": "delta", "changed": [...], "added": [...], "removed": [id, ...]}``,
  where ``added`` holds full sprite records, ``changed`` holds each changed sprite's id plus
  only the fields that changed, and empty lists are left out. A changed ``rect`` of integers
  is written as ``rect_delta`` (current minus previous, component by component; integer
  arithmetic is exact); a rect with any non-integer component is written whole as ``rect``.
  A sprite keeps the same fields for as long as it is present. "Changed" means a different
  value or a different JSON type (``5`` -> ``5.0`` and ``True`` -> ``1`` are changes), so a
  trace reads back with exactly the types that were written.
- Sprite order inside a frame is the scene's draw order and is kept exactly: when a delta
  frame's order is not "the previous frame's sprites minus the removed ones, then the added
  ones", the delta also carries ``"order": [every id, in order]``.
- Any other frame field (a recording's ``dt`` or input events, for example) is written to
  the frame's line unchanged, keyframe or delta.

Reserved names (the encoding owns them; ``TraceWriter.write_frame`` and ``encode_frame``
reject a record that uses one, ``TraceWriter`` rejects a header that does):

- Frame fields: ``kind``, ``changed``, ``added``, ``removed``, ``order``. (``frame``,
  ``scene`` and ``sprites`` are required, with the meanings above.)
- Sprite fields: ``rect_delta``. (``id`` is required.)
- Header fields: ``format_version``, ``frames``.

Decoding rebuilds the full frames, so a trace read back equals the trace that was written,
frame by frame. The gzip header has mtime 0 and no file name, so identical traces give
identical bytes.

``TraceWriter`` streams: it writes the header when it opens and one line per
``write_frame()``. With ``flush_every_frame`` (the default), each frame is flushed through
gzip to the file, so a recorder that crashes leaves a file readable up to its last complete
frame.

``TraceReader`` streams the other way: it reads the header on open, then yields one full
frame at a time, decompressing the file a chunk at a time and keeping only the current
frame's sprite state, so a long recording is never held in memory as a whole.
``read_trace()``/``read_trace_result()`` build the whole in-memory trace on top of it. Both
tolerate what a crashed recorder leaves: a missing gzip end-of-stream and a final line cut
off part way (the partial line is dropped and reported). Malformed lines raise
``TraceFormatError`` naming the line and the frame.
"""

from __future__ import annotations

import dataclasses
import gzip
import json
import logging
import zlib
from typing import TYPE_CHECKING, Any, Self, cast

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path
    from types import TracebackType

    from glitchygames.scenes import Scene

LOG = logging.getLogger(__name__)

TRACE_FORMAT_VERSION = 2

KEYFRAME_KIND = 'keyframe'
DELTA_KIND = 'delta'

# Frame fields the encoding replaces or adds; a frame record may not use them for its own data
SCENE_FIELD = 'scene'
SPRITES_FIELD = 'sprites'
KIND_FIELD = 'kind'
CHANGED_FIELD = 'changed'
ADDED_FIELD = 'added'
REMOVED_FIELD = 'removed'
ORDER_FIELD = 'order'
ENCODING_FIELDS = (KIND_FIELD, CHANGED_FIELD, ADDED_FIELD, REMOVED_FIELD, ORDER_FIELD)

# Sprite fields: a changed entry's rect may be written as a delta instead of the rect itself
SPRITE_ID_FIELD = 'id'
RECT_FIELD = 'rect'
RECT_DELTA_FIELD = 'rect_delta'

# Header fields the writer owns
FORMAT_VERSION_FIELD = 'format_version'
FRAMES_FIELD = 'frames'
RESERVED_HEADER_FIELDS = (FORMAT_VERSION_FIELD, FRAMES_FIELD)

# zlib wbits for a gzip stream (16 + the 15-bit window)
GZIP_WINDOW_BITS = 16 + zlib.MAX_WBITS

_COMPACT_SEPARATORS = (',', ':')


class TraceFormatError(ValueError):
    """A trace file or frame record that does not follow the trace format."""


class StableSpriteIds:
    """Give each sprite an id the first time it is seen; ids never renumber.

    Ids are ``<ClassName>#<n>``, where n counts that class's sprites in order of first
    appearance over the whole run, so a removed sprite (a collected coin, a dead ball) never
    shifts the ids of the others.
    """

    def __init__(self) -> None:
        """Start with no sprites seen."""
        self._ids_by_object_id: dict[int, str] = {}
        self._class_counts: dict[str, int] = {}
        # Held so a removed sprite's id(sprite) can never be reused by a new object
        self._seen_objects: list[object] = []

    def id_for(self, sprite: object) -> str:
        """Return the sprite's id, assigning the next one for its class on first sight.

        Args:
            sprite: Any sprite.

        Returns:
            ``<ClassName>#<n>``.

        """
        sprite_id = self._ids_by_object_id.get(id(sprite))
        if sprite_id is None:
            class_name = type(sprite).__name__
            index = self._class_counts.get(class_name, 0)
            self._class_counts[class_name] = index + 1
            sprite_id = f'{class_name}#{index}'
            self._ids_by_object_id[id(sprite)] = sprite_id
            self._seen_objects.append(sprite)
        return sprite_id


def sample_scene_frame(
    *, frame_number: int, scene: Scene | None, sprite_ids: StableSpriteIds
) -> dict[str, Any]:
    """Record every sprite in a scene's ``all_sprites``, in group (draw) order.

    Args:
        frame_number: The frame just run.
        scene: The active scene after the frame, or None if there is none.
        sprite_ids: The run's sprite ids.

    Returns:
        The frame record.

    """
    sprites: list[dict[str, Any]] = []
    if scene is not None:
        for sprite in scene.all_sprites.sprites():
            rect = sprite.rect
            sprites.append({
                'id': sprite_ids.id_for(sprite),
                'rect': [rect.x, rect.y, rect.width, rect.height],
                'visible': bool(sprite.visible),
            })
    return {
        'frame': frame_number,
        SCENE_FIELD: None if scene is None else type(scene).__name__,
        SPRITES_FIELD: sprites,
    }


def _sprites_by_id(frame_record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index a frame's sprites by id, rejecting duplicate ids.

    Args:
        frame_record: A full frame record.

    Returns:
        Sprite id -> sprite record, in the frame's order.

    Raises:
        TraceFormatError: If two sprites share an id (a delta could not tell them apart).

    """
    sprites_by_id: dict[str, dict[str, Any]] = {}
    for sprite in frame_record[SPRITES_FIELD]:
        sprite_id = sprite['id']
        if sprite_id in sprites_by_id:
            message = f'Frame {frame_record.get("frame")} has two sprites with id {sprite_id!r}'
            raise TraceFormatError(message)
        sprites_by_id[sprite_id] = sprite
    return sprites_by_id


def _same_json_value(first: object, second: object) -> bool:
    """Compare two JSON values by value AND type, recursively.

    Python's ``==`` treats ``5 == 5.0`` and ``True == 1`` as equal, but the trace must give
    back the type that was written, so a change of type alone is a change.

    Args:
        first: A JSON value (None, bool, int, float, str, list or dict).
        second: Another JSON value.

    Returns:
        True if both have the same type and value at every level.

    """
    if type(first) is not type(second):
        return False
    if isinstance(first, list):
        first_list = cast('list[object]', first)
        second_list = cast('list[object]', second)
        return len(first_list) == len(second_list) and all(
            map(_same_json_value, first_list, second_list, strict=True)
        )
    if isinstance(first, dict):
        first_dict = cast('dict[str, object]', first)
        second_dict = cast('dict[str, object]', second)
        return first_dict.keys() == second_dict.keys() and all(
            _same_json_value(value, second_dict[key]) for key, value in first_dict.items()
        )
    return first == second


def _copy_json(value: Any) -> Any:
    """Copy a JSON value (lists and dicts are copied at every level; scalars are immutable).

    Much faster than ``copy.deepcopy`` for the plain JSON data traces hold.

    Args:
        value: A JSON value.

    Returns:
        An independent copy.

    """
    if isinstance(value, list):
        return [_copy_json(item) for item in cast('list[Any]', value)]
    if isinstance(value, dict):
        return {key: _copy_json(item) for key, item in cast('dict[str, Any]', value).items()}
    return value


def _is_integer_list(value: object) -> bool:
    if not isinstance(value, list):
        return False
    # bool is an int subclass, but a bool component would not survive a delta as a bool
    return all(
        isinstance(component, int) and not isinstance(component, bool)
        for component in cast('list[object]', value)
    )


def _sprite_change(
    *, previous_sprite: dict[str, Any], sprite: dict[str, Any], frame_number: object
) -> dict[str, Any]:
    """Describe how a sprite changed: its id plus each changed field.

    Args:
        previous_sprite: The sprite's record in the previous frame.
        sprite: The sprite's record in this frame (it differs from ``previous_sprite``).
        frame_number: This frame's number, for error messages.

    Returns:
        The changed entry: ``id``, then each changed field, with an integer ``rect`` written
        as ``rect_delta``.

    Raises:
        TraceFormatError: If the sprite gained or lost a field, or names the delta field.

    """
    if set(previous_sprite) != set(sprite) or RECT_DELTA_FIELD in sprite:
        message = (
            f'Frame {frame_number}: sprite {sprite[SPRITE_ID_FIELD]!r} changed its fields from '
            f'{sorted(previous_sprite)} to {sorted(sprite)} (a sprite keeps the same fields, '
            f'and {RECT_DELTA_FIELD!r} is reserved)'
        )
        raise TraceFormatError(message)
    change: dict[str, Any] = {SPRITE_ID_FIELD: sprite[SPRITE_ID_FIELD]}
    for field, value in sprite.items():
        previous_value = previous_sprite[field]
        if field == SPRITE_ID_FIELD or _same_json_value(value, previous_value):
            continue
        if (
            field == RECT_FIELD
            and _is_integer_list(value)
            and _is_integer_list(previous_value)
            and len(value) == len(previous_value)
        ):
            change[RECT_DELTA_FIELD] = [
                component - previous_component
                for component, previous_component in zip(value, previous_value, strict=True)
            ]
        else:
            change[field] = value
    return change


def _apply_sprite_change(
    *, previous_sprite: dict[str, Any], change: dict[str, Any]
) -> dict[str, Any]:
    """Rebuild a changed sprite from its previous record and its changed entry.

    Args:
        previous_sprite: The sprite's record in the previous frame.
        change: The changed entry, as written by ``_sprite_change``.

    Returns:
        The sprite's new record: a new dict, so ``previous_sprite`` is never changed.

    """
    sprite = dict(previous_sprite)
    for field, value in change.items():
        if field == RECT_DELTA_FIELD:
            sprite[RECT_FIELD] = [
                previous_component + component
                for previous_component, component in zip(sprite[RECT_FIELD], value, strict=True)
            ]
        else:
            sprite[field] = _copy_json(value)
    return sprite


def encode_frame(
    *, frame_record: dict[str, Any], previous_frame_record: dict[str, Any] | None
) -> dict[str, Any]:
    """Encode one full frame as its trace line: a keyframe or a delta.

    Args:
        frame_record: The full frame (``frame``, ``scene``, ``sprites`` and any other fields).
        previous_frame_record: The full previous frame, or None for the first frame.

    Returns:
        The line's JSON object.

    Raises:
        TraceFormatError: If the frame uses a field name the encoding reserves, or two of its
            sprites share an id.

    """
    reserved_fields = [field for field in ENCODING_FIELDS if field in frame_record]
    if reserved_fields:
        message = (
            f'Frame {frame_record.get("frame")} uses reserved frame field(s) {reserved_fields}; '
            f'the trace encoding owns {list(ENCODING_FIELDS)}, so rename the field'
        )
        raise TraceFormatError(message)
    sprites_by_id = _sprites_by_id(frame_record)
    other_fields = {
        field: value
        for field, value in frame_record.items()
        if field not in {'frame', SCENE_FIELD, SPRITES_FIELD}
    }
    if previous_frame_record is None or not _same_json_value(
        previous_frame_record[SCENE_FIELD], frame_record[SCENE_FIELD]
    ):
        return {
            'frame': frame_record['frame'],
            KIND_FIELD: KEYFRAME_KIND,
            **other_fields,
            SCENE_FIELD: frame_record[SCENE_FIELD],
            SPRITES_FIELD: frame_record[SPRITES_FIELD],
        }

    previous_sprites_by_id = _sprites_by_id(previous_frame_record)
    changed = [
        _sprite_change(
            previous_sprite=previous_sprites_by_id[sprite_id],
            sprite=sprite,
            frame_number=frame_record['frame'],
        )
        for sprite_id, sprite in sprites_by_id.items()
        if sprite_id in previous_sprites_by_id
        and not _same_json_value(previous_sprites_by_id[sprite_id], sprite)
    ]
    added = [
        sprite
        for sprite_id, sprite in sprites_by_id.items()
        if sprite_id not in previous_sprites_by_id
    ]
    removed = [sprite_id for sprite_id in previous_sprites_by_id if sprite_id not in sprites_by_id]
    line_record: dict[str, Any] = {
        'frame': frame_record['frame'],
        KIND_FIELD: DELTA_KIND,
        **other_fields,
    }
    if changed:
        line_record[CHANGED_FIELD] = changed
    if added:
        line_record[ADDED_FIELD] = added
    if removed:
        line_record[REMOVED_FIELD] = removed
    implied_order = [
        sprite_id for sprite_id in previous_sprites_by_id if sprite_id in sprites_by_id
    ] + [sprite['id'] for sprite in added]
    actual_order = list(sprites_by_id)
    if implied_order != actual_order:
        line_record[ORDER_FIELD] = actual_order
    return line_record


class _FrameDecoder:
    """Rebuild full frames from trace lines, one at a time.

    Holds the current frame's scene and its sprite records keyed by id (in draw order). A
    delta updates that state in place: a changed sprite gets a new record and the others are
    kept, so no frame is ever copied as a whole. Each decoded frame is an independent copy
    the caller owns.
    """

    def __init__(self) -> None:
        """Start with no frame decoded."""
        self.has_frame = False
        self.scene: object = None
        self.sprites_by_id: dict[str, dict[str, Any]] = {}

    def start_from(self, frame_record: dict[str, Any]) -> None:
        """Make a full frame the current state (for decoding a single line after it).

        Args:
            frame_record: The full previous frame. Its records are never changed.

        """
        self.scene = frame_record[SCENE_FIELD]
        self.sprites_by_id = _sprites_by_id(frame_record)
        self.has_frame = True

    def decode(self, line_record: dict[str, Any]) -> dict[str, Any]:
        """Apply one line and return the full frame it describes.

        Args:
            line_record: The frame's line, as written by ``encode_frame``.

        Returns:
            The full frame record (``frame``, any other fields, ``scene``, ``sprites``).

        Raises:
            TraceFormatError: If the line is not a keyframe, or not a delta that applies to
                the current frame; malformed records are reported with the frame number.

        """
        frame_number = line_record.get('frame')
        try:
            self._apply(line_record=line_record, frame_number=frame_number)
            other_fields = {
                field: _copy_json(value)
                for field, value in line_record.items()
                if field not in {'frame', SCENE_FIELD, SPRITES_FIELD, *ENCODING_FIELDS}
            }
        except TraceFormatError:
            raise
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            message = (
                f'Frame {frame_number}: malformed {line_record.get(KIND_FIELD)} line ({error!r})'
            )
            raise TraceFormatError(message) from error
        return {
            'frame': frame_number,
            **other_fields,
            SCENE_FIELD: self.scene,
            SPRITES_FIELD: [_copy_json(sprite) for sprite in self.sprites_by_id.values()],
        }

    def _apply(self, *, line_record: dict[str, Any], frame_number: object) -> None:
        kind = line_record.get(KIND_FIELD)
        if kind == KEYFRAME_KIND:
            scene = line_record[SCENE_FIELD]
            sprites_by_id = _sprites_by_id({
                'frame': frame_number,
                SPRITES_FIELD: [_copy_json(sprite) for sprite in line_record[SPRITES_FIELD]],
            })
            self.scene = scene
            self.sprites_by_id = sprites_by_id
            self.has_frame = True
            return
        if kind != DELTA_KIND:
            message = f'Frame {frame_number} has unknown line kind {kind!r}'
            raise TraceFormatError(message)
        if not self.has_frame:
            message = f'Frame {frame_number} is a delta with no previous frame to apply it to'
            raise TraceFormatError(message)
        self._apply_delta(line_record=line_record, frame_number=frame_number)

    def _apply_delta(self, *, line_record: dict[str, Any], frame_number: object) -> None:
        # Work on a copy of the index (not the records), so a bad line leaves the state alone
        sprites_by_id = dict(self.sprites_by_id)
        for change in line_record.get(CHANGED_FIELD, []):
            sprite_id = change[SPRITE_ID_FIELD]
            if sprite_id not in sprites_by_id:
                message = f'Frame {frame_number} changes sprite {sprite_id!r}, which is not present'
                raise TraceFormatError(message)
            sprites_by_id[sprite_id] = _apply_sprite_change(
                previous_sprite=sprites_by_id[sprite_id], change=change
            )
        for sprite_id in line_record.get(REMOVED_FIELD, []):
            if sprites_by_id.pop(sprite_id, None) is None:
                message = f'Frame {frame_number} removes sprite {sprite_id!r}, which is not present'
                raise TraceFormatError(message)
        for sprite in line_record.get(ADDED_FIELD, []):
            if sprite[SPRITE_ID_FIELD] in sprites_by_id:
                message = (
                    f'Frame {frame_number} adds sprite {sprite[SPRITE_ID_FIELD]!r}, '
                    f'which is present'
                )
                raise TraceFormatError(message)
            sprites_by_id[sprite[SPRITE_ID_FIELD]] = _copy_json(sprite)
        order: object = line_record.get(ORDER_FIELD)
        if order is not None:
            order_ids = cast('list[str]', order) if isinstance(order, list) else None
            if order_ids is None or sorted(order_ids) != sorted(sprites_by_id):
                message = f'Frame {frame_number} has an order that does not list its sprites'
                raise TraceFormatError(message)
            sprites_by_id = {sprite_id: sprites_by_id[sprite_id] for sprite_id in order_ids}
        self.sprites_by_id = sprites_by_id


def decode_frame(
    *, line_record: dict[str, Any], previous_frame_record: dict[str, Any] | None
) -> dict[str, Any]:
    """Rebuild one full frame from its trace line and the full previous frame.

    The returned frame shares no lists or sprite records with ``previous_frame_record``, and
    ``previous_frame_record`` is not changed. To decode a whole file, ``TraceReader`` keeps
    the state between lines instead of passing full frames around. A line that is not a
    keyframe, or not a delta that applies to the previous frame, or that holds a malformed
    record raises ``TraceFormatError`` naming the frame.

    Args:
        line_record: The frame's line, as written by ``encode_frame``.
        previous_frame_record: The full previous frame, or None for the first frame.

    Returns:
        The full frame record (``frame``, any other fields, ``scene``, ``sprites``).

    """
    decoder = _FrameDecoder()
    if previous_frame_record is not None:
        decoder.start_from(previous_frame_record)
    return decoder.decode(line_record)


def _json_line(record: dict[str, Any]) -> bytes:
    # ensure_ascii=False: text (an event's unicode) is written as is, in UTF-8
    return (json.dumps(record, separators=_COMPACT_SEPARATORS, ensure_ascii=False) + '\n').encode(
        'utf-8'
    )


class TraceWriter:
    """Stream a trace to a gzip JSON Lines file: header first, then one line per frame."""

    def __init__(
        self, *, path: Path, header: dict[str, Any], flush_every_frame: bool = True
    ) -> None:
        """Create the file and write the header line.

        Args:
            path: The destination file (its parent directories are created).
            header: The trace's header fields (not ``format_version`` or ``frames``).
            flush_every_frame: Flush each frame through gzip to the file, so a crash leaves
                every written frame readable. Each flush ends a deflate block, which costs
                some compression; a whole trace written at once can turn it off.

        Raises:
            TraceFormatError: If the header uses a field the writer owns.

        """
        reserved_fields = [field for field in RESERVED_HEADER_FIELDS if field in header]
        if reserved_fields:
            message = f'Trace headers may not set {reserved_fields}; the writer owns them'
            raise TraceFormatError(message)
        self.path = path
        self.flush_every_frame = flush_every_frame
        self.frame_count = 0
        self._previous_frame_record: dict[str, Any] | None = None
        path.parent.mkdir(parents=True, exist_ok=True)
        self._raw_file = path.open('wb')
        # mtime 0 and no file name in the gzip header: identical traces give identical bytes
        self._gzip_file: gzip.GzipFile | None = gzip.GzipFile(
            filename='', mode='wb', fileobj=self._raw_file, mtime=0
        )
        self._write_line({FORMAT_VERSION_FIELD: TRACE_FORMAT_VERSION, **header})

    def _write_line(self, record: dict[str, Any]) -> None:
        if self._gzip_file is None:
            message = f'Trace writer for {self.path} is closed'
            raise ValueError(message)
        self._gzip_file.write(_json_line(record))
        if self.flush_every_frame:
            self._gzip_file.flush()

    def write_frame(self, frame_record: dict[str, Any], *, force_keyframe: bool = False) -> None:
        """Encode and write one full frame.

        The writer keeps its own copy of the frame to encode the next one against, so the
        caller may reuse or change the record afterwards.

        Args:
            frame_record: The full frame record.
            force_keyframe: Write a keyframe even if the scene name matches the previous
                frame's (a recorder passes True when a new scene object of the same class
                became active, such as the next floor of a game).

        """
        line_record = encode_frame(
            frame_record=frame_record,
            previous_frame_record=None if force_keyframe else self._previous_frame_record,
        )
        self._write_line(line_record)
        self._previous_frame_record = _copy_json(frame_record)
        self.frame_count += 1

    def close(self) -> None:
        """Finish the gzip stream and close the file (closing twice does nothing)."""
        if self._gzip_file is None:
            return
        self._gzip_file.close()
        self._gzip_file = None
        self._raw_file.close()

    def __enter__(self) -> Self:
        """Return the writer for a ``with`` block.

        Returns:
            This writer.

        """
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the writer when the ``with`` block ends."""
        self.close()


def write_trace(trace: dict[str, Any], *, path: Path) -> None:
    """Write a whole in-memory trace (header fields plus ``frames``) to a file.

    Args:
        trace: The trace to write.
        path: The destination file.

    """
    header = {field: value for field, value in trace.items() if field != FRAMES_FIELD}
    with TraceWriter(path=path, header=header, flush_every_frame=False) as writer:
        for frame_record in trace[FRAMES_FIELD]:
            writer.write_frame(frame_record)


# How many compressed bytes TraceReader reads at a time
DEFAULT_READ_CHUNK_BYTES = 64 * 1024


def _parse_line(*, path: Path, line: bytes, line_number: int) -> dict[str, Any]:
    try:
        record: object = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        message = f'{path}: line {line_number} is not JSON ({error})'
        raise TraceFormatError(message) from error
    if not isinstance(record, dict):
        message = f'{path}: line {line_number} is not a JSON object'
        raise TraceFormatError(message)
    return cast('dict[str, Any]', record)


class TraceReader:
    """Stream a trace file: the header on open, then one full frame per iteration step.

    Usage::

        with TraceReader(path=path) as reader:
            game = reader.header['game']
            for frame in reader:
                ...
        if reader.dropped_partial_line is not None:
            ...  # the file was cut off part way through its last line

    The file is decompressed a chunk at a time and frames are rebuilt one by one, so a long
    recording is never held in memory as a whole. Each yielded frame is an independent copy
    the caller may keep or change. The frames can be iterated once.

    A file whose gzip stream stops part way (a recorder that never closed) reads up to its
    last complete line; ``is_complete`` and ``dropped_partial_line`` say what happened once
    iteration has finished.

    Attributes:
        path: The trace file.
        header: The header fields, without ``format_version``.
        bytes_read: Compressed bytes read from the file so far.
        dropped_partial_line: After iteration, the text after the last newline (a line cut
            off part way), or None if the file ended on a complete line.
        is_complete: After iteration, whether the gzip stream ended properly.

    """

    def __init__(self, *, path: Path, chunk_bytes: int = DEFAULT_READ_CHUNK_BYTES) -> None:
        """Open the file and read the header line.

        A file with no header line or an unknown ``format_version`` raises
        ``TraceFormatError`` here, before any frame is read.

        Args:
            path: The trace file.
            chunk_bytes: How many compressed bytes to read at a time.

        """
        self.path = path
        self.chunk_bytes = chunk_bytes
        self.bytes_read = 0
        self.dropped_partial_line: str | None = None
        self.is_complete = False
        self._file = path.open('rb')
        self._decompressor = zlib.decompressobj(wbits=GZIP_WINDOW_BITS)
        self._pending = b''
        self._line_number = 0
        self._has_iterated = False
        try:
            self.header = self._read_header()
        except BaseException:
            self.close()
            raise

    def _read_header(self) -> dict[str, Any]:
        header_line = self._next_line()
        if header_line is None:
            message = f'{self.path}: no header line (empty or cut off before the first line ended)'
            raise TraceFormatError(message)
        try:
            header = _parse_line(path=self.path, line=header_line, line_number=1)
        except TraceFormatError as error:
            message = (
                f'{self.path}: the header line is not a JSON object; format version 1 traces '
                f'(a single JSON document) are no longer read, re-record the trace'
            )
            raise TraceFormatError(message) from error
        format_version = header.pop(FORMAT_VERSION_FIELD, None)
        if format_version != TRACE_FORMAT_VERSION:
            message = (
                f'{self.path}: unsupported trace format_version {format_version} '
                f'(this reader understands {TRACE_FORMAT_VERSION})'
            )
            raise TraceFormatError(message)
        return header

    def _next_line(self) -> bytes | None:
        """Return the next complete line (without its newline), or None at the end.

        At the end, any bytes after the last newline become ``dropped_partial_line``.

        Raises:
            TraceFormatError: If data follows the end of the gzip stream.

        """
        while b'\n' not in self._pending:
            if self._decompressor.eof:
                break
            chunk = self._file.read(self.chunk_bytes)
            if not chunk:
                break
            self.bytes_read += len(chunk)
            self._pending += self._decompressor.decompress(chunk)
            if self._decompressor.unused_data:
                message = f'{self.path}: unexpected data after the end of the gzip stream'
                raise TraceFormatError(message)
        line, newline, rest = self._pending.partition(b'\n')
        if not newline:
            self.is_complete = self._decompressor.eof
            if self._decompressor.eof and self._file.read(1):
                message = f'{self.path}: unexpected data after the end of the gzip stream'
                raise TraceFormatError(message)
            # A cut-off stream can end inside a UTF-8 sequence; only this dropped line can
            self.dropped_partial_line = line.decode('utf-8', errors='replace') or None
            self._pending = b''
            return None
        self._pending = rest
        self._line_number += 1
        return line

    def __iter__(self) -> Iterator[dict[str, Any]]:
        """Yield each full frame in order.

        Yields:
            The next full frame record.

        Raises:
            ValueError: If the frames have already been iterated.
            TraceFormatError: If a line (other than a cut-off last one) is not a valid
                frame line; the message names the line and the frame.

        """
        if self._has_iterated:
            message = f'{self.path}: a TraceReader iterates its frames once'
            raise ValueError(message)
        self._has_iterated = True
        decoder = _FrameDecoder()
        while (line := self._next_line()) is not None:
            line_record = _parse_line(path=self.path, line=line, line_number=self._line_number)
            try:
                frame_record = decoder.decode(line_record)
            except TraceFormatError as error:
                message = f'{self.path}: line {self._line_number}: {error}'
                raise TraceFormatError(message) from error
            yield frame_record

    def close(self) -> None:
        """Close the file (closing twice does nothing)."""
        self._file.close()

    def __enter__(self) -> Self:
        """Return the reader for a ``with`` block.

        Returns:
            This reader.

        """
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the reader when the ``with`` block ends."""
        self.close()


@dataclasses.dataclass(frozen=True)
class TraceReadResult:
    """A trace read from a file, and how complete the file was.

    Attributes:
        trace: The header fields (without ``format_version``) plus the full ``frames``.
        dropped_partial_line: The text after the last newline (a frame line cut off part
            way), or None if the file ended on a complete line.
        is_complete: Whether the gzip stream ended properly (False for a recording whose
            writer never closed).

    """

    trace: dict[str, Any]
    dropped_partial_line: str | None
    is_complete: bool


def read_trace_result(*, path: Path) -> TraceReadResult:
    """Read a whole trace file into memory, reporting a final line cut off part way.

    Args:
        path: The trace file.

    Returns:
        The trace and how complete the file was.

    """
    with TraceReader(path=path) as reader:
        frames = list(reader)
    return TraceReadResult(
        trace={**reader.header, FRAMES_FIELD: frames},
        dropped_partial_line=reader.dropped_partial_line,
        is_complete=reader.is_complete,
    )


def read_trace(*, path: Path) -> dict[str, Any]:
    """Read a whole trace file; a final line cut off part way is dropped with a warning.

    Args:
        path: The trace file.

    Returns:
        The header fields (without ``format_version``) plus the full ``frames``.

    """
    result = read_trace_result(path=path)
    if result.dropped_partial_line is not None:
        LOG.warning(
            '%s: dropped a partial final line (%d characters) after %d complete frames',
            path,
            len(result.dropped_partial_line),
            len(result.trace[FRAMES_FIELD]),
        )
    return result.trace
