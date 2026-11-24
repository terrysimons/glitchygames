"""What a rebaselined recording changed, and the check that it changed only what was named.

A reviewed re-record (plans/2026-11-20-game-code-into-the-engine.md, Sub-plan 3, part C) replays
a recording, OLD, under new code with ``--replay-trace OLD --rebaseline NEW --headless``
(glitchygames/replay/rebaseline.py), so OLD and NEW are the same session frame for frame and
every difference between them is the code's. ``compare_recordings`` reads both and fails unless
the only differences are the ones its ``RecordingAllowances`` name:

- The same number of frames, and in each frame the same fields: the scene, ``dt``, the served
  event batches (external input and internal events, record by record), the saves and devices
  opened, the polled-input changes, the scene start, and every other field a frame holds.
- The same sprites in every frame (id, rect, visible, draw order), once the allowed sprite ids
  are set aside; each allowed id must appear in NEW and never in OLD.
- The same header fields.
- Values compare by type as well as value (``5`` and ``5.0`` differ), as a recording reads back
  with exactly the types it was written with (glitchygames/tracing.py).
- A custom event compares by its type's name, not its number: a rebaseline records the events in
  this process's custom event numbers and rewrites ``custom_event_types`` to match (BUGS.md
  #211.1), so the same event may carry another number in NEW, and another event the same one.

What it does not compare, because a rebaseline rewrites it whatever the code does: the
measurement histories each frame stacks (``content_hash``, ``processing_seconds``,
``audio_seconds``, ``audio_work``) and the header fields ``rebaseline_header`` sets (the
measurement runs, which hold the source revision, ``rebaselined_from``, the engine, pygame and
Python versions, ``custom_event_types`` (compared through the events instead), and the format,
bookmark and unreleased fields it drops). The recorded start time is compared: a rebaseline
keeps OLD's.

An allowance that matches nothing fails the check too, so an allowance cannot outlive the change
it was written for, and a passing check shows that every named difference really appears.

Pixels are not in a recording; the check's command line (scripts/check_rebaselined_recordings.py)
compares them separately, from frame fingerprints.
"""

from __future__ import annotations

from collections import Counter
from enum import Enum
from itertools import zip_longest
from typing import TYPE_CHECKING, Any, Self, TypeIs, cast, override

import pydantic

from glitchygames.events.base import LEGACY_CUSTOM_EVENT_TYPES
from glitchygames.recording import (
    CUSTOM_EVENT_TYPES_HEADER_FIELD,
    EVENT_BATCHES_FIELD,
    EVENT_ORIGIN_FIELD,
    EVENT_TYPE_FIELD,
    INTERNAL_ORIGIN,
)
from glitchygames.recording_history import (
    AUDIO_SECONDS_FIELD,
    AUDIO_WORK_FIELD,
    CONTENT_HASH_FIELD,
    MEASUREMENT_RUNS_HEADER_FIELD,
    PROCESSING_SECONDS_FIELD,
)
from glitchygames.replay.driver import (
    ENGINE_VERSION_HEADER_FIELD,
    INPUT_CAPTURE_FORMAT_HEADER_FIELD,
)
from glitchygames.replay.rebaseline import (
    PYGAME_VERSION_HEADER_FIELD,
    PYTHON_VERSION_HEADER_FIELD,
    REBASELINED_FROM_HEADER_FIELD,
    UNRELEASED_HEADER_FIELDS,
)
from glitchygames.tracing import (
    BOOKMARKED_COPY_OF_HEADER_FIELD,
    SPRITES_FIELD,
    TraceReader,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

# Header fields a rebaseline rewrites whatever the code does (rebaseline_header)
REBASELINE_HEADER_FIELDS = frozenset({
    MEASUREMENT_RUNS_HEADER_FIELD,
    REBASELINED_FROM_HEADER_FIELD,
    ENGINE_VERSION_HEADER_FIELD,
    PYGAME_VERSION_HEADER_FIELD,
    PYTHON_VERSION_HEADER_FIELD,
    INPUT_CAPTURE_FORMAT_HEADER_FIELD,
    BOOKMARKED_COPY_OF_HEADER_FIELD,
    CUSTOM_EVENT_TYPES_HEADER_FIELD,
    *UNRELEASED_HEADER_FIELDS,
})
# Frame fields that hold measurement histories (glitchygames/recording_history.py)
MEASUREMENT_FRAME_FIELDS = frozenset({
    CONTENT_HASH_FIELD,
    PROCESSING_SECONDS_FIELD,
    AUDIO_SECONDS_FIELD,
    AUDIO_WORK_FIELD,
})
# The sprite record field that names it
SPRITE_ID_FIELD = 'id'
# The path segment a draw-order difference is reported under
ORDER_SEGMENT = 'order'
# The report's default number of differences listed
REPORT_LIMIT = 20

type Where = tuple[str | int, ...]


class Absent(Enum):
    """The value on the side of a difference that does not have the field, sprite or frame."""

    ABSENT = 'absent'

    @override
    def __repr__(self: Self) -> str:
        """Return how a report shows it.

        Returns:
            ``absent``.

        """
        return self.value


ABSENT = Absent.ABSENT


class AllowedField(pydantic.BaseModel):
    """A header or frame field that may differ, everything under it included."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    # From the root: ('header', field, ...) or ('frame', frame index, field, ...)
    where: tuple[str | int, ...]
    # Why it differs (for the reviewer)
    reason: str

    @property
    def label(self: Self) -> str:
        """The allowance's name in a report: its path, dotted."""
        return dotted(self.where)


class RecordingAllowances(pydantic.BaseModel):
    """What may differ between one OLD and NEW pair, and nothing else."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    # Sprite ids NEW alone has (a new sprite's records are not compared; its pixels are)
    sprite_ids: frozenset[str] = frozenset()
    # Custom event types (names in NEW's custom_event_types header) whose internal events NEW
    # alone posts
    internal_event_types: frozenset[str] = frozenset()
    # Header and frame fields that may differ
    fields: tuple[AllowedField, ...] = ()


class RecordingDifference(pydantic.BaseModel):
    """One difference between OLD and NEW: where it is, and each side's value (or ``ABSENT``)."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    where: tuple[str | int, ...]
    old: Any
    new: Any

    def describe(self: Self) -> str:
        """Return the difference on one line.

        Returns:
            ``path: old -> new``.

        """
        return f'{dotted(self.where)}: {self.old!r} -> {self.new!r}'


class RecordingComparison(pydantic.BaseModel):
    """The check's verdict on one OLD and NEW pair."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    # The recordings' files, as given
    old: str
    new: str
    frame_counts: tuple[int, int]
    # The differences no allowance covers
    differences: list[RecordingDifference]
    # How much each allowance covered, by its label (only those that covered something)
    allowed_counts: dict[str, int]
    # Allowances that matched nothing, or a sprite id or event type OLD already has
    unused_allowances: list[str]

    @property
    def passed(self: Self) -> bool:
        """Whether NEW differs from OLD only as allowed, and in every allowed way."""
        return not self.differences and not self.unused_allowances

    def report(self: Self, *, limit: int = REPORT_LIMIT) -> str:
        """Return the verdict, each allowance's count and the first ``limit`` differences.

        Args:
            limit: How many differences to list.

        Returns:
            The report, one item per line.

        """
        verdict = 'PASS' if self.passed else 'FAIL'
        old_count, new_count = self.frame_counts
        frames = (
            f'{old_count} frames each'
            if old_count == new_count
            else f'{old_count} and {new_count} frames'
        )
        lines = [f'{verdict} {self.old} -> {self.new}: {frames}']
        lines.extend(
            f'  allowed: {label} {_count_phrase(label=label, count=count)}'
            for label, count in self.allowed_counts.items()
        )
        lines.extend(f'  allowance not met: {label}' for label in self.unused_allowances)
        lines.extend(
            f'  differs: {difference.describe()}' for difference in self.differences[:limit]
        )
        if len(self.differences) > limit:
            lines.append(f'  ... and {len(self.differences) - limit} more differences')
        return '\n'.join(lines)


def dotted(where: Where) -> str:
    """Return a path as a report writes it.

    Returns:
        The segments joined with dots.

    """
    return '.'.join(str(segment) for segment in where)


def _count_phrase(*, label: str, count: int) -> str:
    """Return how a report counts an allowance.

    Returns:
        ``in N frames`` for a sprite, ``N events`` for internal events, else ``N differences``.

    """
    if label.startswith(_SPRITE_LABEL):
        return f'in {count} frames'
    if label.startswith(_EVENT_LABEL):
        return f'{count} events'
    return f'{count} differences'


_SPRITE_LABEL = 'sprite '
_EVENT_LABEL = 'internal event '


def compare_recordings(
    *, old: Path, new: Path, allowances: RecordingAllowances | None = None
) -> RecordingComparison:
    """Compare a recording with its rebaselined copy.

    Args:
        old: The recording before the change (OLD).
        new: Its rebaseline under the change (NEW).
        allowances: What may differ (None: nothing).

    Returns:
        The comparison.

    """
    allowed = RecordingAllowances() if allowances is None else allowances
    comparison = _Comparison(allowances=allowed)
    with TraceReader(path=old) as old_reader, TraceReader(path=new) as new_reader:
        comparison.compare_headers(old=old_reader.header, new=new_reader.header)
        old_count = new_count = 0
        for old_frame, new_frame in zip_longest(old_reader, new_reader):
            if old_frame is not None:
                old_count += 1
            if new_frame is not None:
                new_count += 1
            if old_frame is not None and new_frame is not None:
                comparison.compare_frames(index=old_count - 1, old=old_frame, new=new_frame)
    if old_count != new_count:
        comparison.differ(where=('frames',), old=old_count, new=new_count)
    return RecordingComparison(
        old=str(old),
        new=str(new),
        frame_counts=(old_count, new_count),
        differences=comparison.differences,
        allowed_counts=comparison.allowed_counts(),
        unused_allowances=comparison.unused_allowances(),
    )


class _Comparison:
    """The differences found so far, and what each allowance has covered."""

    def __init__(self: Self, *, allowances: RecordingAllowances) -> None:
        self.allowances = allowances
        self.differences: list[RecordingDifference] = []
        self.counts: Counter[str] = Counter()
        # Allowed sprite ids or event types OLD has: the allowance does not hold
        self.found_in_old: set[str] = set()
        # Each recording's custom event names, by number
        self.old_event_names: dict[int, str] = {}
        self.new_event_names: dict[int, str] = {}

    def compare_headers(self: Self, *, old: dict[str, Any], new: dict[str, Any]) -> None:
        """Compare the header fields a rebaseline keeps."""
        self.old_event_names = _custom_event_names(header=old)
        self.new_event_names = _custom_event_names(header=new)
        for field in _field_order(old=old, new=new):
            if field not in REBASELINE_HEADER_FIELDS:
                self.compare_values(
                    where=('header', field),
                    old=old.get(field, ABSENT),
                    new=new.get(field, ABSENT),
                )

    def compare_frames(self: Self, *, index: int, old: dict[str, Any], new: dict[str, Any]) -> None:
        """Compare one frame of each recording."""
        for field in _field_order(old=old, new=new):
            where = ('frame', index, field)
            if field in MEASUREMENT_FRAME_FIELDS:
                continue
            if field == SPRITES_FIELD:
                self.compare_sprites(where=where, old=old.get(field, []), new=new.get(field, []))
            elif field == EVENT_BATCHES_FIELD:
                self.compare_values(
                    where=where,
                    old=self._comparable_events(old.get(field, ABSENT), side_is_old=True),
                    new=self._comparable_events(new.get(field, ABSENT), side_is_old=False),
                )
            else:
                self.compare_values(
                    where=where, old=old.get(field, ABSENT), new=new.get(field, ABSENT)
                )

    def compare_sprites(
        self: Self, *, where: Where, old: list[dict[str, Any]], new: list[dict[str, Any]]
    ) -> None:
        """Compare a frame's sprites, by id, once the allowed ids are set aside."""
        old_sprites = self._without_allowed_sprites(old, side_is_old=True)
        new_sprites = self._without_allowed_sprites(new, side_is_old=False)
        for sprite_id in _field_order(old=old_sprites, new=new_sprites):
            self.compare_values(
                where=(*where, sprite_id),
                old=old_sprites.get(sprite_id, ABSENT),
                new=new_sprites.get(sprite_id, ABSENT),
            )
        old_order = [sprite_id for sprite_id in old_sprites if sprite_id in new_sprites]
        new_order = [sprite_id for sprite_id in new_sprites if sprite_id in old_sprites]
        if old_order != new_order:
            self.differ(where=(*where, ORDER_SEGMENT), old=old_order, new=new_order)

    def _without_allowed_sprites(
        self: Self, sprites: list[dict[str, Any]], *, side_is_old: bool
    ) -> dict[str, dict[str, Any]]:
        """Return the sprites by id, in draw order, the allowed ids counted and left out.

        Returns:
            The other sprites.

        """
        kept: dict[str, dict[str, Any]] = {}
        for sprite in sprites:
            sprite_id = sprite[SPRITE_ID_FIELD]
            if sprite_id not in self.allowances.sprite_ids:
                kept[sprite_id] = sprite
            elif side_is_old:
                self.found_in_old.add(_SPRITE_LABEL + sprite_id)
            else:
                self.counts[_SPRITE_LABEL + sprite_id] += 1
        return kept

    def _comparable_events(self: Self, batches: object, *, side_is_old: bool) -> object:
        """Return the event batches with custom types named and allowed internal events left out.

        Returns:
            The batches (anything but a list of batches unchanged, for the comparison to report).

        """
        event_names = self.old_event_names if side_is_old else self.new_event_names
        if not isinstance(batches, list):
            return batches
        kept_batches: list[list[dict[str, Any]]] = []
        for batch in cast('list[list[dict[str, Any]]]', batches):
            kept: list[dict[str, Any]] = []
            for event in batch:
                name = event_names.get(event.get(EVENT_TYPE_FIELD, -1))
                if name is None:
                    kept.append(event)
                elif (
                    name not in self.allowances.internal_event_types
                    or event.get(EVENT_ORIGIN_FIELD) != INTERNAL_ORIGIN
                ):
                    kept.append({**event, EVENT_TYPE_FIELD: name})
                elif side_is_old:
                    self.found_in_old.add(_EVENT_LABEL + name)
                else:
                    self.counts[_EVENT_LABEL + name] += 1
            kept_batches.append(kept)
        return kept_batches

    def compare_values(self: Self, *, where: Where, old: object, new: object) -> None:
        """Compare two values, descending into mappings and equal-length lists."""
        for difference_where, old_value, new_value in _leaf_differences(
            where=where, old=old, new=new
        ):
            self.differ(where=difference_where, old=old_value, new=new_value)

    def differ(self: Self, *, where: Where, old: object, new: object) -> None:
        """Record a difference, unless an allowed field covers it."""
        for allowed in self.allowances.fields:
            if where[: len(allowed.where)] == allowed.where:
                self.counts[allowed.label] += 1
                return
        self.differences.append(RecordingDifference(where=where, old=old, new=new))

    def _labels(self: Self) -> list[str]:
        """Return every allowance's label, in report order.

        Returns:
            Sprite ids, then event types (each sorted), then fields as declared.

        """
        return [
            *(_SPRITE_LABEL + sprite_id for sprite_id in sorted(self.allowances.sprite_ids)),
            *(_EVENT_LABEL + name for name in sorted(self.allowances.internal_event_types)),
            *(allowed.label for allowed in self.allowances.fields),
        ]

    def allowed_counts(self: Self) -> dict[str, int]:
        """Return what each allowance covered, for those that hold.

        Returns:
            The counts by label.

        """
        return {
            label: self.counts[label]
            for label in self._labels()
            if self.counts[label] and label not in self.found_in_old
        }

    def unused_allowances(self: Self) -> list[str]:
        """Return the allowances that covered nothing, or that OLD already has.

        Returns:
            Their labels.

        """
        return [
            label
            for label in self._labels()
            if not self.counts[label] or label in self.found_in_old
        ]


def _custom_event_names(*, header: dict[str, Any]) -> dict[int, str]:
    """Return the custom event names a recording's header gives its event numbers.

    A header without ``custom_event_types`` was made with the legacy numbers, as a replay reads
    it (``custom_event_type_remap``).

    Returns:
        Each number's name.

    """
    custom_types = cast(
        'Mapping[str, int]',
        header.get(CUSTOM_EVENT_TYPES_HEADER_FIELD, LEGACY_CUSTOM_EVENT_TYPES),
    )
    return {number: name for name, number in custom_types.items()}


def _field_order[KeyT](*, old: dict[KeyT, Any], new: dict[KeyT, Any]) -> list[KeyT]:
    """Return OLD's keys in order, then NEW's that OLD lacks.

    Returns:
        The keys.

    """
    return [*old, *(key for key in new if key not in old)]


def _leaf_differences(
    *, where: Where, old: object, new: object
) -> Iterator[tuple[Where, Any, Any]]:
    """Yield each place two values differ, by type or value.

    Mappings are compared key by key, and lists of records (mappings or lists) of the same
    length item by item; anything else (a rect, a list of another length, a value on one side
    only) is one difference, reported whole.

    Yields:
        Each difference's path and both values.

    """
    if _is_mapping(old) and _is_mapping(new):
        for key in _field_order(old=old, new=new):
            yield from _leaf_differences(
                where=(*where, key), old=old.get(key, ABSENT), new=new.get(key, ABSENT)
            )
    elif _is_list_of_records(old) and _is_list_of_records(new) and len(old) == len(new):
        for index, (old_item, new_item) in enumerate(zip(old, new, strict=True)):
            yield from _leaf_differences(where=(*where, index), old=old_item, new=new_item)
    elif type(old) is not type(new) or old != new:
        yield where, old, new


def _is_mapping(value: object) -> TypeIs[dict[str, Any]]:
    """Return whether a value is a mapping (a JSON object, as a recording holds it).

    Returns:
        True for a dict.

    """
    return isinstance(value, dict)


def _is_list_of_records(value: object) -> TypeIs[list[Any]]:
    """Return whether a value is a list whose items are all mappings or lists.

    Returns:
        True for a list of records (an empty list included).

    """
    return isinstance(value, list) and all(
        isinstance(item, (dict, list)) for item in cast('list[Any]', value)
    )
