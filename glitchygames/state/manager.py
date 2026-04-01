"""SaveManager: orchestrates game state persistence.

Handles save/load operations with atomic writes, pluggable
serializers, and cross-platform save directory resolution.
Wraps game data with metadata (version, timestamp, app_name)
for forward compatibility and debugging.

Usage:
    saves = SaveManager(app_name='brave_adventurer')
    saves.save('slot_1', {'score': 100, 'level': 2})
    data = saves.load('slot_1')
"""

from __future__ import annotations

import contextlib
import importlib.metadata
import logging
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from glitchygames.state.exceptions import (
    SaveCorruptedError,
    SaveNotFoundError,
    SaveVersionError,
)
from glitchygames.state.paths import get_save_directory
from glitchygames.state.serializers import JsonSerializer, Serializer

log: logging.Logger = logging.getLogger('game.state.manager')

# Current save format version. Increment when the metadata schema changes.
SAVE_FORMAT_VERSION: int = 1

# Metadata key used in save files
_META_KEY: str = '_meta'
_DATA_KEY: str = 'data'


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


class SaveManager:
    """Manages game state persistence with pluggable serializers.

    Each SaveManager instance is scoped to an application name which
    determines the save directory. Games create a SaveManager and use
    it to save/load named slots.

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
        self._app_name = app_name
        self._default_serializer: Serializer = default_serializer or JsonSerializer()
        self._save_dir = save_dir or get_save_directory(app_name)

    @property
    def app_name(self) -> str:
        """The application name this manager is scoped to."""
        return self._app_name

    @property
    def save_dir(self) -> Path:
        """The directory where save files are stored."""
        return self._save_dir

    def save(
        self,
        slot_name: str,
        data: dict[str, Any],
        *,
        serializer: Serializer | None = None,
    ) -> Path:
        """Save game state to a named slot.

        Wraps the data with metadata and writes atomically to prevent
        corruption on crash. The save directory is created if it
        doesn't exist.

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
                'timestamp': datetime.now(tz=UTC).isoformat(),
                'app_name': self._app_name,
                'engine_version': _get_engine_version(),
            },
            _DATA_KEY: data,
        }

        content = active_serializer.serialize(envelope)
        save_path = self._slot_path(slot_name, active_serializer)

        # Ensure directory exists (created on first save, not on init)
        self._save_dir.mkdir(parents=True, exist_ok=True)

        # Atomic write: temp file in same dir → os.replace()
        self._atomic_write(save_path, content)

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
                path=self._find_slot_path(slot_name),
            )
        meta = cast('dict[str, Any]', meta_raw)

        file_version: int = int(meta.get('version', 0))
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
                path=self._find_slot_path(slot_name),
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

        Returns:
            The full save envelope dict (metadata + data).

        Raises:
            SaveCorruptedError: If the file can't be parsed.

        """
        save_path = self._find_slot_path(slot_name)
        active_serializer = serializer or self._default_serializer

        content = save_path.read_text(encoding='utf-8')

        try:
            result = active_serializer.deserialize(content)
        except Exception as error:
            msg = f"Failed to parse save file for slot '{slot_name}': {error}"
            raise SaveCorruptedError(
                message=msg,
                path=save_path,
                original_error=error,
            ) from error

        return result

    def exists(self, slot_name: str) -> bool:
        """Check if a save slot exists.

        Args:
            slot_name: Name of the save slot to check.

        Returns:
            True if the slot exists on disk.

        """
        try:
            self._find_slot_path(slot_name)
        except SaveNotFoundError:
            return False
        return True

    def delete(self, slot_name: str) -> None:
        """Delete a save slot.

        Args:
            slot_name: Name of the save slot to delete.

        """
        save_path = self._find_slot_path(slot_name)
        save_path.unlink()
        log.info('Deleted slot %r at %s', slot_name, save_path)

    def list_slots(self) -> list[SaveSlotInfo]:
        """List all save slots with metadata.

        Returns:
            List of SaveSlotInfo, sorted by timestamp (newest first).

        """
        if not self._save_dir.exists():
            return []

        slots: list[SaveSlotInfo] = []
        for path in self._save_dir.iterdir():
            if not path.is_file():
                continue
            # Skip files without recognized extensions
            if path.suffix not in {'.json', '.toml'}:
                continue

            try:
                slot_info = self._read_slot_info(path)
            except SaveCorruptedError, SaveVersionError, OSError:
                log.warning('Skipping unreadable save file: %s', path)
                continue

            slots.append(slot_info)

        # Sort newest first
        slots.sort(key=lambda slot: slot.timestamp, reverse=True)
        return slots

    # --- Private helpers ---

    def _slot_path(self, slot_name: str, serializer: Serializer) -> Path:
        """Build the file path for a slot with the serializer's extension.

        Args:
            slot_name: Slot name.
            serializer: Serializer to get the file extension from.

        Returns:
            Full path to the save file.

        """
        return self._save_dir / f'{slot_name}{serializer.file_extension}'

    def _find_slot_path(self, slot_name: str) -> Path:
        """Find an existing save file for a slot, checking all extensions.

        Args:
            slot_name: Slot name to search for.

        Returns:
            Path to the existing save file.

        Raises:
            SaveNotFoundError: If no file exists for this slot.

        """
        for extension in ('.json', '.toml'):
            candidate = self._save_dir / f'{slot_name}{extension}'
            if candidate.is_file():
                return candidate

        msg = f"Save slot '{slot_name}' not found in {self._save_dir}"
        raise SaveNotFoundError(message=msg, slot_name=slot_name)

    def _read_slot_info(self, path: Path) -> SaveSlotInfo:
        """Read metadata from a save file to build a SaveSlotInfo.

        Args:
            path: Path to the save file.

        Returns:
            SaveSlotInfo with metadata from the file.

        Raises:
            SaveCorruptedError: If the file has invalid metadata.

        """
        # Pick serializer based on file extension
        if path.suffix == '.toml':
            from glitchygames.state.serializers import TomlSerializer

            active_serializer: Serializer = TomlSerializer()
        else:
            active_serializer = JsonSerializer()

        content = path.read_text(encoding='utf-8')
        envelope = active_serializer.deserialize(content)

        meta_raw = envelope.get(_META_KEY, {})
        if not isinstance(meta_raw, dict):
            msg = f'Save file at {path} has invalid metadata'
            raise SaveCorruptedError(message=msg, path=path)
        meta = cast('dict[str, Any]', meta_raw)

        timestamp_str: str = str(meta.get('timestamp', ''))
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
        except ValueError, TypeError:
            timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)

        version: int = int(meta.get('version', 0))
        app_name: str = str(meta.get('app_name', ''))

        return SaveSlotInfo(
            name=path.stem,
            path=path,
            timestamp=timestamp,
            version=version,
            app_name=app_name,
            size_bytes=path.stat().st_size,
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
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
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
