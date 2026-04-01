"""Custom exceptions for the save/load system."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class SaveError(Exception):
    """Base exception for save/load operations."""


class SaveCorruptedError(SaveError):
    """Save file exists but cannot be deserialized or has invalid structure.

    Args:
        message: Human-readable error description.
        path: Path to the corrupted save file.
        original_error: The underlying parsing/decoding exception.

    """

    def __init__(
        self,
        message: str,
        path: Path,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize SaveCorruptedError."""
        super().__init__(message)
        self.path = path
        self.original_error = original_error


class SaveNotFoundError(SaveError):
    """Requested save slot does not exist.

    Args:
        message: Human-readable error description.
        slot_name: The slot that was not found.

    """

    def __init__(self, message: str, slot_name: str) -> None:
        """Initialize SaveNotFoundError."""
        super().__init__(message)
        self.slot_name = slot_name


class SaveVersionError(SaveError):
    """Save file metadata version is incompatible.

    Args:
        message: Human-readable error description.
        file_version: The version found in the save file.
        expected_version: The version this engine expects.

    """

    def __init__(
        self,
        message: str,
        file_version: int,
        expected_version: int,
    ) -> None:
        """Initialize SaveVersionError."""
        super().__init__(message)
        self.file_version = file_version
        self.expected_version = expected_version
