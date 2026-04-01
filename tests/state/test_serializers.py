"""Tests for save/load serializers."""

from __future__ import annotations

import pytest

from glitchygames.state.serializers import JsonSerializer, TomlSerializer


class TestJsonSerializer:
    """Tests for the JSON serializer."""

    def test_round_trip_simple(self) -> None:
        """Data survives a serialize → deserialize round trip."""
        serializer = JsonSerializer()
        data = {'score': 100, 'level': 2, 'name': 'player_one'}
        content = serializer.serialize(data)
        result = serializer.deserialize(content)
        assert result == data

    def test_round_trip_nested(self) -> None:
        """Nested structures survive a round trip."""
        serializer = JsonSerializer()
        data = {
            'player': {'score': 500, 'lives': 3},
            'inventory': ['sword', 'shield'],
            'settings': {'volume': 0.8},
        }
        content = serializer.serialize(data)
        result = serializer.deserialize(content)
        assert result == data

    def test_round_trip_empty(self) -> None:
        """Empty dict round-trips correctly."""
        serializer = JsonSerializer()
        data: dict[str, object] = {}
        content = serializer.serialize(data)
        result = serializer.deserialize(content)
        assert result == data

    def test_round_trip_unicode(self) -> None:
        """Unicode strings survive a round trip."""
        serializer = JsonSerializer()
        data = {'name': 'プレイヤー', 'greeting': '¡Hola!'}
        content = serializer.serialize(data)
        result = serializer.deserialize(content)
        assert result == data

    def test_deserialize_non_object_raises(self) -> None:
        """Deserializing a non-object JSON value raises TypeError."""
        serializer = JsonSerializer()
        with pytest.raises(TypeError, match='Expected JSON object'):
            serializer.deserialize('[1, 2, 3]')

    def test_deserialize_invalid_json_raises(self) -> None:
        """Deserializing invalid JSON raises json.JSONDecodeError."""
        import json

        serializer = JsonSerializer()
        with pytest.raises(json.JSONDecodeError):
            serializer.deserialize('not valid json {{{')

    def test_file_extension(self) -> None:
        """File extension is .json."""
        serializer = JsonSerializer()
        assert serializer.file_extension == '.json'

    def test_null_values(self) -> None:
        """JSON null values round-trip as None."""
        serializer = JsonSerializer()
        data = {'value': None, 'present': True}
        content = serializer.serialize(data)
        result = serializer.deserialize(content)
        assert result == data


class TestTomlSerializer:
    """Tests for the TOML serializer."""

    def test_round_trip_simple(self) -> None:
        """Data survives a serialize → deserialize round trip."""
        serializer = TomlSerializer()
        data = {'volume': 0.8, 'fullscreen': False, 'language': 'en'}
        content = serializer.serialize(data)
        result = serializer.deserialize(content)
        assert result == data

    def test_round_trip_nested(self) -> None:
        """Nested tables survive a round trip."""
        serializer = TomlSerializer()
        data = {
            'audio': {'master': 1.0, 'music': 0.7, 'sfx': 0.9},
            'display': {'fullscreen': True, 'resolution': '1920x1080'},
        }
        content = serializer.serialize(data)
        result = serializer.deserialize(content)
        assert result == data

    def test_round_trip_empty(self) -> None:
        """Empty dict round-trips correctly."""
        serializer = TomlSerializer()
        data: dict[str, object] = {}
        content = serializer.serialize(data)
        result = serializer.deserialize(content)
        assert result == data

    def test_deserialize_invalid_toml_raises(self) -> None:
        """Deserializing invalid TOML raises TOMLDecodeError."""
        import tomllib

        serializer = TomlSerializer()
        with pytest.raises(tomllib.TOMLDecodeError):
            serializer.deserialize('= invalid toml ][')

    def test_file_extension(self) -> None:
        """File extension is .toml."""
        serializer = TomlSerializer()
        assert serializer.file_extension == '.toml'
