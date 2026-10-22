"""SaveManager: orchestrates game state persistence.

``SaveManager`` holds the save logic: it wraps game data with metadata (version, timestamp,
app_name) for forward compatibility and debugging, validates it on load, lists slots and raises
the save errors. Its subclasses provide the storage: ``DiskSaveManager`` (files with atomic
writes, pluggable serializers and cross-platform save directory resolution) for live play, and
``MemorySaveManager`` (glitchygames/state/sandbox.py) for replays, so a replay's store answers
exactly as the live one did.

Usage:
    saves = DiskSaveManager(app_name='brave_adventurer')
    saves.save('slot_1', {'score': 100, 'level': 2})
    data = saves.load('slot_1')
"""

from __future__ import annotations

import abc
import contextlib
import importlib.metadata
import logging
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast, override

from glitchygames.clock import wall_clock_time
from glitchygames.state.exceptions import (
    SaveCorruptedError,
    SaveNotFoundError,
    SaveVersionError,
)
from glitchygames.state.paths import get_save_directory
from glitchygames.state.serializers import JsonSerializer, Serializer, TomlSerializer

if TYPE_CHECKING:
    from collections.abc import Callable

log: logging.Logger = logging.getLogger('game.state.manager')

# Current save format version. Increment when the metadata schema changes.
SAVE_FORMAT_VERSION: int = 1

# Metadata key used in save files
_META_KEY: str = '_meta'
_DATA_KEY: str = 'data'

# Save file extensions, in the order a slot's file is looked up
_SLOT_FILE_EXTENSIONS: tuple[str, ...] = ('.json', '.toml')


def _get_engine_version() -> str:
    """Get the installed glitchygames engine version.

    Returns:
        Version string, or 'unknown' if not installed as a package.

    """
    try:
        return importlib.metadata.version('glitchygames')
    except importlib.metadata.PackageNotFoundError:
        return 'unknown'


@dataclass(frozen=True)
class SaveSlotInfo:
    """Read-only metadata about a save slot.

    Attributes:
        name: Slot name (filename stem without extension).
        path: Full path to the save file.
        timestamp: When the save was last written (UTC).
        version: Save format version from metadata.
        app_name: Application name from metadata.
        size_bytes: File size in bytes.

    """

    name: str
    path: Path
    timestamp: datetime
    version: int
    app_name: str
    size_bytes: int


class SaveManager(abc.ABC):
    """Manages game state persistence with pluggable serializers.

    Each SaveManager instance is scoped to an application name. Games
    open one (``glitchygames.state.open_saves``) and use it to save/load
    named slots. This base class holds every rule of the save format;
    its subclasses only store slots: ``DiskSaveManager`` as files,
    ``MemorySaveManager`` (glitchygames/state/sandbox.py) in memory.

    Args:
        app_name: Application name (the save namespace).
        default_serializer: Serializer to use when none is specified
            per-operation. Defaults to JsonSerializer.

    """

    def __init__(
        self,
        app_name: str,
        *,
        default_serializer: Serializer | None = None,
    ) -> None:
        """Initialize the save manager."""
        self._app_name = app_name
        self._default_serializer: Serializer = default_serializer or JsonSerializer()

    @property
    def app_name(self) -> str:
        """The application name this manager is scoped to."""
        return self._app_name

    def save(
        self,
        slot_name: str,
        data: dict[str, Any],
        *,
        serializer: Serializer | None = None,
    ) -> Path:
        """Save game state to a named slot.

        Wraps the data with metadata and hands the serialized envelope
        to the storage (a disk store writes it atomically to prevent
        corruption on crash).

        Args:
            slot_name: Name of the save slot (becomes the filename stem).
            data: Game state to save.
            serializer: Override the default serializer for this save.

        Returns:
            Path to the written save file.

        """
        active_serializer = serializer or self._default_serializer

        # Build the save envelope with metadata
        envelope: dict[str, Any] = {
            _META_KEY: {
                'version': SAVE_FORMAT_VERSION,
                'timestamp': wall_clock_time().isoformat(),
                'app_name': self._app_name,
                'engine_version': _get_engine_version(),
            },
            _DATA_KEY: data,
        }

        content = active_serializer.serialize(envelope)
        save_path = self._write_slot(
            slot_name=slot_name, content=content, serializer=active_serializer
        )

        log.info('Saved slot %r to %s', slot_name, save_path)
        return save_path

    def load(self, slot_name: str, *, serializer: Serializer | None = None) -> dict[str, Any]:
        """Load game state from a named slot.

        Returns only the game data (not metadata). Use load_raw()
        to access the full envelope including metadata.

        Args:
            slot_name: Name of the save slot to load.
            serializer: Override the default serializer for this load.

        Returns:
            The saved game state dict.

        Raises:
            SaveCorruptedError: If the file can't be parsed or is missing data.
            SaveVersionError: If the save format version doesn't match.

        """
        raw = self.load_raw(slot_name=slot_name, serializer=serializer)

        # Validate metadata
        meta_raw = raw.get(_META_KEY)
        if not isinstance(meta_raw, dict):
            msg = f"Save file for slot '{slot_name}' is missing metadata"
            raise SaveCorruptedError(
                message=msg,
                path=self.find_slot_path(slot_name),
            )
        meta = cast('dict[str, Any]', meta_raw)

        file_version = self._metadata_version(meta=meta)
        if file_version is None:
            msg = f"Save file for slot '{slot_name}' has an invalid version"
            raise SaveCorruptedError(
                message=msg,
                path=self.find_slot_path(slot_name),
            )
        if file_version != SAVE_FORMAT_VERSION:
            msg = (
                f"Save file for slot '{slot_name}' has version {file_version}, "
                f'expected {SAVE_FORMAT_VERSION}'
            )
            raise SaveVersionError(
                message=msg,
                file_version=file_version,
                expected_version=SAVE_FORMAT_VERSION,
            )

        data_raw = raw.get(_DATA_KEY)
        if not isinstance(data_raw, dict):
            msg = f"Save file for slot '{slot_name}' is missing data section"
            raise SaveCorruptedError(
                message=msg,
                path=self.find_slot_path(slot_name),
            )

        return cast('dict[str, Any]', data_raw)

    def load_raw(
        self,
        slot_name: str,
        *,
        serializer: Serializer | None = None,
    ) -> dict[str, Any]:
        """Load the full save envelope including metadata.

        Useful for implementing custom migration logic. Does NOT
        validate the format version.

        Args:
            slot_name: Name of the save slot to load.
            serializer: Override the default serializer for this load.

        The storage raises SaveCorruptedError if the file can't be parsed.

        Returns:
            The full save envelope dict (metadata + data).

        """
        save_path = self.find_slot_path(slot_name)
        active_serializer = serializer or self._default_serializer
        return self._read_slot(slot_name=slot_name, path=save_path, serializer=active_serializer)

    def exists(self, slot_name: str) -> bool:
        """Check if a save slot exists.

        Args:
            slot_name: Name of the save slot to check.

        Returns:
            True if the slot exists in the store.

        """
        return self._existing_slot_path(slot_name=slot_name) is not None

    def delete(self, slot_name: str) -> None:
        """Delete a save slot.

        Args:
            slot_name: Name of the save slot to delete.

        """
        save_path = self.find_slot_path(slot_name)
        self._delete_slot(slot_name=slot_name, path=save_path)
        log.info('Deleted slot %r at %s', slot_name, save_path)

    def list_slots(self) -> list[SaveSlotInfo]:
        """List all save slots with metadata.

        Slots whose metadata can't be read are skipped (with a warning).

        Returns:
            List of SaveSlotInfo, sorted by timestamp (newest first), slots saved at the same
            time by name, so the order never depends on the order the files are found in (a
            replay's memory store lists them as the disk did).

        """
        slots: list[SaveSlotInfo] = []
        for path in self._slot_file_paths():
            try:
                slot_info = self._read_slot_info(path=path)
            except SaveCorruptedError, SaveVersionError, OSError:
                log.warning('Skipping unreadable save file: %s', path)
                continue

            slots.append(slot_info)

        # By name first, so the newest-first sort below (stable) leaves ties in name order
        slots.sort(key=lambda slot: slot.name)
        # Sort newest first (a timestamp without a time zone sorts as UTC, so a hand-written
        # file beside engine-written ones cannot make the comparison raise)
        slots.sort(
            key=lambda slot: (
                slot.timestamp if slot.timestamp.tzinfo else slot.timestamp.replace(tzinfo=UTC)
            ),
            reverse=True,
        )
        return slots

    def slot_names(self) -> list[str]:
        """List the name of every stored slot, readable or not.

        Returns:
            Slot names, sorted.

        """
        return sorted({path.stem for path in self._slot_file_paths()})

    def find_slot_path(self, slot_name: str) -> Path:
        """Find an existing save file for a slot, checking all extensions.

        Public because a recording's save snapshot (glitchygames/state/sandbox.py) records which
        file ``load`` reads (its extension), which list_slots alone cannot tell.

        Args:
            slot_name: Slot name to search for.

        Returns:
            Path to the existing save file.

        Raises:
            SaveNotFoundError: If no file exists for this slot.

        """
        save_path = self._existing_slot_path(slot_name=slot_name)
        if save_path is None:
            msg = f"Save slot '{slot_name}' not found in {self._storage_location}"
            raise SaveNotFoundError(message=msg, slot_name=slot_name)
        return save_path

    # --- Shared helpers for the storage ---

    @staticmethod
    def _parse_slot_content(
        *, slot_name: str, path: Path, read_content: Callable[[], str], serializer: Serializer
    ) -> dict[str, Any]:
        """Read and deserialize a slot file's content.

        Args:
            slot_name: Slot name (for the error message).
            path: The slot's file (for the error).
            read_content: Returns the file's text (decoding it as UTF-8).
            serializer: The serializer to parse with.

        Returns:
            The envelope.

        Raises:
            SaveCorruptedError: If the content can't be decoded or parsed.
            OSError: If the file can't be read (passed through: not a corrupt save).

        """
        try:
            return serializer.deserialize(read_content())
        except OSError:
            # The file could not be read at all: not a corrupt save
            raise
        except Exception as error:
            msg = f"Failed to parse save file for slot '{slot_name}': {error}"
            raise SaveCorruptedError(
                message=msg,
                path=path,
                original_error=error,
            ) from error

    @staticmethod
    def _metadata_version(*, meta: dict[str, Any]) -> int | None:
        """Return the metadata's save format version, or None if it is not a finite number.

        Returns:
            The version (0 when missing), or None.

        """
        try:
            return int(meta.get('version', 0))
        except ValueError, TypeError, OverflowError:
            # Not a number, or an infinite float (JSON Infinity/1e999, TOML inf)
            return None

    def _slot_info_from_content(
        self,
        *,
        path: Path,
        read_content: Callable[[], str],
        size_bytes: Callable[[], int],
        fallback_timestamp: Callable[[], datetime],
    ) -> SaveSlotInfo:
        """Build a slot file's SaveSlotInfo, parsing it with the serializer its extension names.

        Args:
            path: The slot's file.
            read_content: Returns the file's text.
            size_bytes: Returns the file's size.
            fallback_timestamp: See _slot_info_from_envelope.

        Returns:
            SaveSlotInfo with metadata from the file.

        """
        # Pick serializer based on file extension
        active_serializer: Serializer = (
            TomlSerializer() if path.suffix == '.toml' else JsonSerializer()
        )
        envelope = self._parse_slot_content(
            slot_name=path.stem, path=path, read_content=read_content, serializer=active_serializer
        )
        return self._slot_info_from_envelope(
            envelope=envelope,
            path=path,
            size_bytes=size_bytes(),
            fallback_timestamp=fallback_timestamp,
        )

    @classmethod
    def _slot_info_from_envelope(
        cls,
        *,
        envelope: dict[str, Any],
        path: Path,
        size_bytes: int,
        fallback_timestamp: Callable[[], datetime],
    ) -> SaveSlotInfo:
        """Build a slot's SaveSlotInfo from its envelope's metadata.

        Args:
            envelope: The slot's envelope.
            path: The slot's file.
            size_bytes: The file's size.
            fallback_timestamp: Returns the time to report when the metadata has no valid
                timestamp (a disk store: the file's modification time).

        Returns:
            SaveSlotInfo with metadata from the envelope.

        Raises:
            SaveCorruptedError: If the envelope has invalid metadata.

        """
        meta_raw = envelope.get(_META_KEY, {})
        if not isinstance(meta_raw, dict):
            msg = f'Save file at {path} has invalid metadata'
            raise SaveCorruptedError(message=msg, path=path)
        meta = cast('dict[str, Any]', meta_raw)

        timestamp_str: str = str(meta.get('timestamp', ''))
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
        except ValueError, TypeError:
            timestamp = fallback_timestamp()

        version = cls._metadata_version(meta=meta)
        if version is None:
            msg = f'Save file at {path} has an invalid version'
            raise SaveCorruptedError(message=msg, path=path)
        app_name: str = str(meta.get('app_name', ''))

        return SaveSlotInfo(
            name=path.stem,
            path=path,
            timestamp=timestamp,
            version=version,
            app_name=app_name,
            size_bytes=size_bytes,
        )

    # --- Storage (the subclasses) ---

    @property
    @abc.abstractmethod
    def _storage_location(self) -> Path:
        """Where the slots are stored (named in SaveNotFoundError)."""

    @abc.abstractmethod
    def _existing_slot_path(self, *, slot_name: str) -> Path | None:
        """Return the path of the slot's stored file, or None if the slot does not exist."""

    @abc.abstractmethod
    def _slot_file_paths(self) -> list[Path]:
        """Return the path of every stored slot file."""

    @abc.abstractmethod
    def _read_slot(self, *, slot_name: str, path: Path, serializer: Serializer) -> dict[str, Any]:
        """Return the envelope stored for an existing slot.

        Raises:
            SaveCorruptedError: If it can't be parsed.
            OSError: If it can't be read.

        """

    @abc.abstractmethod
    def _write_slot(self, *, slot_name: str, content: str, serializer: Serializer) -> Path:
        """Store a slot's serialized envelope and return its path."""

    @abc.abstractmethod
    def _delete_slot(self, *, slot_name: str, path: Path) -> None:
        """Remove an existing slot."""

    @abc.abstractmethod
    def _read_slot_info(self, *, path: Path) -> SaveSlotInfo:
        """Return a stored slot file's SaveSlotInfo.

        Raises:
            SaveCorruptedError: If its metadata can't be read.
            SaveVersionError: If its metadata version is unusable.
            OSError: If it can't be read.

        """


class DiskSaveManager(SaveManager):
    """A SaveManager storing slots as files on disk (live play).

    Each instance's app name determines the save directory.

    Args:
        app_name: Application name for the save directory.
        default_serializer: Serializer to use when none is specified
            per-operation. Defaults to JsonSerializer.
        save_dir: Override the platform-specific save directory.
            Primarily useful for testing with tmp_path.

    """

    def __init__(
        self,
        app_name: str,
        *,
        default_serializer: Serializer | None = None,
        save_dir: Path | None = None,
    ) -> None:
        """Initialize the save manager."""
        super().__init__(app_name, default_serializer=default_serializer)
        self._save_dir = save_dir or get_save_directory(app_name)

    @property
    def save_dir(self) -> Path:
        """The directory where save files are stored."""
        return self._save_dir

    @property
    @override
    def _storage_location(self) -> Path:
        """The save directory."""
        return self._save_dir

    @override
    def _existing_slot_path(self, *, slot_name: str) -> Path | None:
        """Return the slot's file, checking all extensions, or None.

        Returns:
            The first existing ``<slot_name><extension>`` file, or None.

        """
        for extension in _SLOT_FILE_EXTENSIONS:
            candidate = self._save_dir / f'{slot_name}{extension}'
            if candidate.is_file():
                return candidate
        return None

    @override
    def _slot_file_paths(self) -> list[Path]:
        """Return every file in the save directory with a recognized extension.

        Returns:
            The files, in directory order.

        """
        if not self._save_dir.exists():
            return []
        return [
            path
            for path in self._save_dir.iterdir()
            # Skip files without recognized extensions
            if path.is_file() and path.suffix in _SLOT_FILE_EXTENSIONS
        ]

    @override
    def _read_slot(self, *, slot_name: str, path: Path, serializer: Serializer) -> dict[str, Any]:
        """Read and parse the slot's file.

        Returns:
            The envelope.

        """
        return self._parse_slot_content(
            slot_name=slot_name,
            path=path,
            read_content=lambda: path.read_text(encoding='utf-8'),
            serializer=serializer,
        )

    @override
    def _write_slot(self, *, slot_name: str, content: str, serializer: Serializer) -> Path:
        """Write the slot's file atomically.

        Returns:
            Path to the written save file.

        """
        save_path = self._save_dir / f'{slot_name}{serializer.file_extension}'

        # Ensure directory exists (created on first save, not on init)
        self._save_dir.mkdir(parents=True, exist_ok=True)

        # Atomic write: temp file in same dir → os.replace()
        self._atomic_write(save_path, content)
        return save_path

    @override
    def _delete_slot(self, *, slot_name: str, path: Path) -> None:
        """Remove the slot's file."""
        del slot_name  # The file is enough (SaveManager signature)
        path.unlink()

    @override
    def _read_slot_info(self, *, path: Path) -> SaveSlotInfo:
        """Read metadata from a save file to build a SaveSlotInfo.

        Args:
            path: Path to the save file.

        Returns:
            SaveSlotInfo with metadata from the file.

        """
        return self._slot_info_from_content(
            path=path,
            read_content=lambda: path.read_text(encoding='utf-8'),
            size_bytes=lambda: path.stat().st_size,
            fallback_timestamp=lambda: datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
        )

    def _atomic_write(self, target_path: Path, content: str) -> None:
        """Write content to a file atomically.

        Writes to a temp file in the same directory, then replaces
        the target. This ensures no partial writes on crash.

        Args:
            target_path: Final destination path.
            content: String content to write.

        """
        temp_path: Path | None = None
        try:
            # Write to temp file in the same directory (same filesystem
            # guarantees atomic replace)
            # newline='\n': never translated, so a save has the same bytes (and size) on
            # every OS; Windows would otherwise write \r\n (reading accepts either)
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                newline='\n',
                dir=target_path.parent,
                suffix='.tmp',
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(content)

            # Atomic replace — safe on all platforms
            temp_path.replace(target_path)
            temp_path = None  # Mark as consumed so finally doesn't delete

        finally:
            # Clean up temp file if the replace failed
            if temp_path is not None:
                with contextlib.suppress(OSError):
                    temp_path.unlink()
