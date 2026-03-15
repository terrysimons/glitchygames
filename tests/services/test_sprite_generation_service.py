"""Tests for sprite generation service."""

import pytest
from glitchygames.services.config import ServiceConfig
from glitchygames.services.exceptions import AIProviderError
from glitchygames.services.sprite_generation_service import (
    GenerationResult,
    SpriteGenerationService,
)


class TestGenerationResult:
    """Test suite for GenerationResult dataclass."""

    def test_successful_result(self):
        """Test successful generation result."""
        result = GenerationResult(
            success=True,
            toml_content="[sprite]\nname = 'test'",
            sprite_name="test",
            is_animated=False,
            frame_count=1,
        )

        assert result.success is True
        assert result.sprite_name == "test"
        assert result.error is None

    def test_failed_result(self):
        """Test failed generation result."""
        result = GenerationResult(
            success=False,
            error="AI response invalid",
        )

        assert result.success is False
        assert result.toml_content is None
        assert result.error == "AI response invalid"


class TestSpriteGenerationService:
    """Test suite for SpriteGenerationService."""

    def test_initialization_with_config(self):
        """Test service initialization with custom config."""
        config = ServiceConfig(ai_provider="openai", ai_model="gpt-4")
        service = SpriteGenerationService(config)

        assert service.config.ai_provider == "openai"
        assert service.config.ai_model == "gpt-4"

    def test_initialization_default_config(self):
        """Test service initialization with default config."""
        service = SpriteGenerationService()

        assert service.config is not None
        assert service._client is None  # Lazy initialization

    def test_ensure_client_no_aisuite(self, mocker):
        """Test that AIProviderError is raised when aisuite is not available."""
        service = SpriteGenerationService()

        mocker.patch.dict("sys.modules", {"aisuite": None})
        # Mock import to fail
        mocker.patch(
            "builtins.__import__", side_effect=ImportError("No module named 'aisuite'")
        )
        # This should raise an error on import attempt
        with pytest.raises(AIProviderError):
            service._ensure_client()

    def test_is_animation_request_true(self):
        """Test animation detection for animation keywords."""
        service = SpriteGenerationService()

        assert service.is_animation_request("create a walking animation") is True
        assert service.is_animation_request("make a 2-frame idle sprite") is True
        assert service.is_animation_request("bouncing ball") is True

    def test_is_animation_request_false(self):
        """Test animation detection for static requests."""
        service = SpriteGenerationService()

        assert service.is_animation_request("16x16 red heart") is False
        assert service.is_animation_request("simple sword sprite") is False

    def test_extract_sprite_metadata_static(self):
        """Test metadata extraction from static sprite."""
        service = SpriteGenerationService()

        toml_content = """
[sprite]
name = "heart"
pixels = \"\"\"
##
##
\"\"\"

[colors."#"]
red = 255
green = 0
blue = 0
"""
        name, is_animated, frame_count = service._extract_sprite_metadata(toml_content)

        assert name == "heart"
        assert is_animated is False
        assert frame_count == 1

    def test_extract_sprite_metadata_animated(self):
        """Test metadata extraction from animated sprite."""
        service = SpriteGenerationService()

        toml_content = """
[sprite]
name = "blink"

[[animation]]
namespace = "idle"
frame_interval = 0.5

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = "##"

[[animation.frame]]
namespace = "idle"
frame_index = 1
pixels = ".."

[colors."#"]
red = 255
green = 255
blue = 255

[colors."."]
red = 0
green = 0
blue = 0
"""
        name, is_animated, frame_count = service._extract_sprite_metadata(toml_content)

        assert name == "blink"
        assert is_animated is True
        assert frame_count == 2

    def test_extract_sprite_metadata_invalid_toml(self):
        """Test metadata extraction with invalid TOML."""
        service = SpriteGenerationService()

        toml_content = "this is not valid toml {"

        name, is_animated, frame_count = service._extract_sprite_metadata(toml_content)

        assert name == "unknown"
        assert is_animated is False
        assert frame_count == 1
