"""Pluggable serializers for the save/load system.

Provides a Serializer Protocol and concrete implementations for
JSON (default, fast) and TOML (human-readable settings).
"""

from __future__ import annotations

import json
import tomllib
from typing import Any, Protocol, cast

import tomli_w


class Serializer(Protocol):
    """Protocol for save data serialization.

    Serializers convert between Python dicts and string representations.
    The SaveManager handles file I/O and encoding; serializers are
    purely data-to-string transformers.
    """

    def serialize(self, data: dict[str, Any]) -> str:
        """Convert a dict to a string representation.

        Args:
            data: The data dict to serialize.

        Returns:
            String representation of the data.

        """
        ...

    def deserialize(self, content: str) -> dict[str, Any]:
        """Parse a string representation back into a dict.

        Args:
            content: The string to deserialize.

        Returns:
            The reconstructed data dict.

        """
        ...

    @property
    def file_extension(self) -> str:
        """File extension for this format (e.g. '.json', '.toml')."""
        ...


class JsonSerializer:
    """JSON serializer for game state.

    Fast and supports the full range of JSON-compatible types.
    Default serializer for SaveManager.
    """

    def serialize(self, data: dict[str, Any]) -> str:
        """Serialize data to a JSON string.

        Args:
            data: The data dict to serialize.

        Returns:
            Pretty-printed JSON string.

        """
        return json.dumps(data, indent=2, ensure_ascii=False)

    def deserialize(self, content: str) -> dict[str, Any]:
        """Deserialize a JSON string to a dict.

        Args:
            content: JSON string to parse.

        Returns:
            The parsed data dict.

        Raises:
            TypeError: If the top-level JSON value is not an object.

        """
        parsed: Any = json.loads(content)
        if not isinstance(parsed, dict):
            msg = f'Expected JSON object at top level, got {type(parsed).__name__}'
            raise TypeError(msg)
        return cast('dict[str, Any]', parsed)

    @property
    def file_extension(self) -> str:
        """File extension for JSON files."""
        return '.json'


class TomlSerializer:
    """TOML serializer for human-readable config/settings.

    Best for settings files that users might edit by hand.
    Uses tomllib (stdlib) for reading and tomli_w for writing.
    """

    def serialize(self, data: dict[str, Any]) -> str:
        """Serialize data to a TOML string.

        Args:
            data: The data dict to serialize.

        Returns:
            TOML-formatted string.

        """
        return tomli_w.dumps(data)

    def deserialize(self, content: str) -> dict[str, Any]:
        """Deserialize a TOML string to a dict.

        Args:
            content: TOML string to parse.

        Returns:
            The parsed data dict.

        """
        return tomllib.loads(content)

    @property
    def file_extension(self) -> str:
        """File extension for TOML files."""
        return '.toml'
