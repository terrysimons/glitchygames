"""The saves door: games open their save store through the active sources.

Live play gets a ``DiskSaveManager``. A recording stores each opened store's snapshot
(``save_namespace_snapshot``) when recording starts or when the store is opened later, and a
replay or in-game playback gets a ``MemorySaveManager`` seeded from it: reads see what the
original session saw, and writes stay in memory and are discarded, so a replay never touches
real saves. Both are ``SaveManager``s, which hold every rule of the save format, so the memory
store answers exactly as the disk store did.

Snapshot format (slot name -> entry, JSON-safe):

- A slot ``load_raw`` could read: its envelope, exactly as ``load_raw`` returned it
  (``{"_meta": {...}, "data": {...}}``, or whatever the file held).
- A slot it could not read: ``{"__unreadable__": {"kind": "corrupt" | "os_error", "message":
  "<the error's message>"}}``. In replay ``exists()`` is True and ``load``/``load_raw`` raise
  ``SaveCorruptedError`` (``corrupt``) or ``OSError`` (``os_error``) with that message.
- Either may hold ``"__listing__": {"timestamp": <ISO 8601>, "version": n, "app_name": "...",
  "size_bytes": n}``, what ``list_slots`` reported for the slot; a slot without it is one
  ``list_slots`` skipped (unreadable metadata).

The keys ``__unreadable__`` and ``__listing__`` are reserved: ``load_raw`` never returns them.
Limits: a slot stored as both ``.json`` and ``.toml`` is recorded once (the file ``load`` reads,
``.json``), while the disk store lists both; ``load(..., serializer=...)`` in replay reads the
recorded envelope whatever the serializer; ``list_slots`` errors other than unreadable slots (a
non-numeric version) are raised while snapshotting.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast, override

from glitchygames.sources import active_sources
from glitchygames.state.exceptions import SaveCorruptedError
from glitchygames.state.manager import SaveManager, SaveSlotInfo

if TYPE_CHECKING:
    from glitchygames.state.serializers import Serializer

# Reserved snapshot entry keys (see the module docstring)
UNREADABLE_SLOT_KEY = '__unreadable__'
LISTING_KEY = '__listing__'
RESERVED_SNAPSHOT_KEYS = frozenset({UNREADABLE_SLOT_KEY, LISTING_KEY})
# Kinds of unreadable slot
CORRUPT_SLOT_KIND = 'corrupt'
OS_ERROR_SLOT_KIND = 'os_error'


def _listing_record(*, slot_info: SaveSlotInfo) -> dict[str, Any]:
    """Return a SaveSlotInfo as a snapshot's JSON-safe ``__listing__`` record.

    Returns:
        The record (the path is left out: a memory store has no files).

    """
    return {
        'timestamp': slot_info.timestamp.isoformat(),
        'version': slot_info.version,
        'app_name': slot_info.app_name,
        'size_bytes': slot_info.size_bytes,
    }


class MemorySaveManager(SaveManager):
    """A SaveManager holding slots in memory, seeded from a recorded snapshot.

    This is what replays and in-game playback use: reads answer from the snapshot exactly as
    the recorded ``DiskSaveManager`` did, and writes stay in memory and are discarded when the
    store goes away, so real saves are never touched.
    """

    def __init__(
        self,
        *,
        app_name: str,
        snapshot: dict[str, dict[str, Any]],
        default_serializer: Serializer | None = None,
    ) -> None:
        """Copy the recorded snapshot (the recording is never modified).

        Args:
            app_name: The application name (the save namespace) this store stands in for.
            snapshot: Slot name -> entry, as save_namespace_snapshot returns.
            default_serializer: Serializer to use when none is specified per-operation.
                Defaults to JsonSerializer, as live stores use.

        """
        super().__init__(app_name, default_serializer=default_serializer)
        self._entries: dict[str, dict[str, Any]] = copy.deepcopy(snapshot)

    @property
    @override
    def _storage_location(self) -> Path:
        """A stand-in directory named after the app (there are no files)."""
        return Path('<replay save snapshot>') / self.app_name

    def _slot_path(self, *, slot_name: str) -> Path:
        """Return the stand-in path of a slot (for errors and return values).

        Returns:
            ``<storage location>/<slot_name><default extension>``.

        """
        return self._storage_location / f'{slot_name}{self._default_serializer.file_extension}'

    @override
    def _existing_slot_path(self, *, slot_name: str) -> Path | None:
        """Return the slot's stand-in path, or None if the snapshot has no such slot.

        Returns:
            The path, or None.

        """
        if slot_name not in self._entries:
            return None
        return self._slot_path(slot_name=slot_name)

    @override
    def _slot_file_paths(self) -> list[Path]:
        """Return every slot's stand-in path.

        Returns:
            The paths, in snapshot order.

        """
        return [self._slot_path(slot_name=slot_name) for slot_name in self._entries]

    @override
    def _read_slot(self, *, slot_name: str, path: Path, serializer: Serializer) -> dict[str, Any]:
        """Return the recorded envelope, or raise the error reading it raised when recorded.

        Returns:
            A copy of the envelope, without the snapshot's reserved keys.

        Raises:
            SaveCorruptedError: If the slot was recorded as corrupt.
            OSError: If the slot was recorded as unreadable.

        """
        del serializer  # The recorded envelope is already parsed (SaveManager signature)
        entry = self._entries[slot_name]
        unreadable = entry.get(UNREADABLE_SLOT_KEY)
        if unreadable is not None:
            message = str(unreadable['message'])
            if unreadable['kind'] == CORRUPT_SLOT_KIND:
                raise SaveCorruptedError(message=message, path=path)
            raise OSError(message)
        return {
            key: copy.deepcopy(value)
            for key, value in entry.items()
            if key not in RESERVED_SNAPSHOT_KEYS
        }

    @override
    def _write_slot(self, *, slot_name: str, content: str, serializer: Serializer) -> Path:
        """Keep the slot in memory, read back through the serializer as a file would be.

        Returns:
            The slot's stand-in path.

        """
        path = self._storage_location / f'{slot_name}{serializer.file_extension}'
        envelope = serializer.deserialize(content)
        slot_info = self._slot_info_from_envelope(
            envelope=envelope,
            path=path,
            size_bytes=len(content.encode('utf-8')),
            # A file just written has the current modification time
            fallback_timestamp=lambda: datetime.now(tz=UTC),
        )
        self._entries[slot_name] = {**envelope, LISTING_KEY: _listing_record(slot_info=slot_info)}
        return path

    @override
    def _delete_slot(self, *, slot_name: str, path: Path) -> None:
        """Forget the slot."""
        del path  # Nothing is stored at the stand-in path (SaveManager signature)
        del self._entries[slot_name]

    @override
    def _read_slot_info(self, *, path: Path) -> SaveSlotInfo:
        """Return what list_slots reported for the slot when recorded.

        Returns:
            The SaveSlotInfo (with the stand-in path).

        Raises:
            SaveCorruptedError: If list_slots skipped the slot when recorded.

        """
        record = self._entries[path.stem].get(LISTING_KEY)
        if record is None:
            message = f'Save file at {path} had unreadable metadata when recorded'
            raise SaveCorruptedError(message=message, path=path)
        listing = cast('dict[str, Any]', record)
        return SaveSlotInfo(
            name=path.stem,
            path=path,
            timestamp=datetime.fromisoformat(str(listing['timestamp'])),
            version=int(listing['version']),
            app_name=str(listing['app_name']),
            size_bytes=int(listing['size_bytes']),
        )


def save_namespace_snapshot(*, saves: SaveManager) -> dict[str, dict[str, Any]]:
    """Return every slot of a store as a snapshot entry (see the module docstring).

    Args:
        saves: A disk store, or the memory store a replay hands out (``--rebaseline``).

    Returns:
        The JSON-safe snapshot a recording stores.

    """
    listings = {slot_info.path: slot_info for slot_info in saves.list_slots()}
    snapshot: dict[str, dict[str, Any]] = {}
    for slot_name in saves.slot_names():
        entry: dict[str, Any]
        try:
            entry = copy.deepcopy(saves.load_raw(slot_name))
        except SaveCorruptedError as error:
            entry = {UNREADABLE_SLOT_KEY: {'kind': CORRUPT_SLOT_KIND, 'message': str(error)}}
        except OSError as error:
            entry = {UNREADABLE_SLOT_KEY: {'kind': OS_ERROR_SLOT_KIND, 'message': str(error)}}
        slot_info = listings.get(saves.find_slot_path(slot_name))
        if slot_info is not None:
            entry[LISTING_KEY] = _listing_record(slot_info=slot_info)
        snapshot[slot_name] = entry
    return snapshot


def open_saves(*, app_name: str) -> SaveManager:
    """Open a game's save store through the active sources (glitchygames/sources.py).

    Args:
        app_name: The application name (the save namespace).

    Returns:
        The store: a DiskSaveManager live, a MemorySaveManager in a replay.

    """
    return active_sources().saves(namespace=app_name)
