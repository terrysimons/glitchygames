"""Tests for service exceptions."""

import pytest
from glitchygames.services.exceptions import (
    AIProviderError,
    RenderingError,
    SpriteServiceError,
    ValidationError,
)


class TestSpriteServiceError:
    """Test suite for SpriteServiceError base exception."""

    def test_basic_exception(self):
        """Test basic exception creation."""
        error = SpriteServiceError("Something went wrong")

        assert str(error) == "Something went wrong"


class TestAIProviderError:
    """Test suite for AIProviderError."""

    def test_basic_error(self):
        """Test basic AI provider error."""
        error = AIProviderError("Connection failed")

        assert str(error) == "Connection failed"
        assert error.provider is None
        assert error.original_error is None

    def test_with_provider(self):
        """Test AI provider error with provider info."""
        error = AIProviderError("API key invalid", provider="anthropic")

        assert str(error) == "API key invalid"
        assert error.provider == "anthropic"

    def test_with_original_error(self):
        """Test AI provider error with original exception."""
        original = ValueError("Invalid API key")
        error = AIProviderError("API error", provider="openai", original_error=original)

        assert error.original_error is original
        assert error.provider == "openai"


class TestValidationError:
    """Test suite for ValidationError."""

    def test_basic_error(self):
        """Test basic validation error."""
        error = ValidationError("Invalid TOML")

        assert str(error) == "Invalid TOML"
        assert error.validation_errors == []

    def test_with_validation_errors(self):
        """Test validation error with specific errors."""
        errors = ["Missing [sprite] section", "No colors defined"]
        error = ValidationError("TOML validation failed", validation_errors=errors)

        assert str(error) == "TOML validation failed"
        assert error.validation_errors == errors


class TestRenderingError:
    """Test suite for RenderingError."""

    def test_basic_error(self):
        """Test basic rendering error."""
        error = RenderingError("Failed to render")

        assert str(error) == "Failed to render"
        assert error.sprite_name is None
        assert error.original_error is None

    def test_with_sprite_name(self):
        """Test rendering error with sprite name."""
        error = RenderingError("Invalid surface", sprite_name="my_sprite")

        assert error.sprite_name == "my_sprite"

    def test_with_original_error(self):
        """Test rendering error with original exception."""
        original = Exception("Surface too large")
        error = RenderingError("Render failed", sprite_name="big_sprite", original_error=original)

        assert error.sprite_name == "big_sprite"
        assert error.original_error is original
