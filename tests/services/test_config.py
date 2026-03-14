"""Tests for service configuration."""

import os

import pytest
from glitchygames.services.config import ServiceConfig


class TestServiceConfig:
    """Test suite for ServiceConfig."""

    def test_default_values(self, mocker):
        """Test that default values are set correctly."""
        mocker.patch.dict(os.environ, {}, clear=True)
        config = ServiceConfig()

        assert config.ai_provider == "anthropic"
        assert config.ai_model == "claude-sonnet-4-5"
        assert config.ai_timeout == 120
        assert config.default_sprite_width == 16
        assert config.default_sprite_height == 16
        assert config.max_sprite_size == 64
        assert config.png_scale == 1

    def test_from_environment(self, mocker):
        """Test that configuration is loaded from environment variables."""
        env_vars = {
            "SPRITE_AI_PROVIDER": "openai",
            "SPRITE_AI_MODEL": "gpt-4",
            "SPRITE_AI_TIMEOUT": "60",
            "SPRITE_DEFAULT_WIDTH": "32",
            "SPRITE_DEFAULT_HEIGHT": "32",
            "SPRITE_MAX_SIZE": "128",
            "SPRITE_PNG_SCALE": "2",
        }

        mocker.patch.dict(os.environ, env_vars, clear=True)
        config = ServiceConfig.from_env()

        assert config.ai_provider == "openai"
        assert config.ai_model == "gpt-4"
        assert config.ai_timeout == 60
        assert config.default_sprite_width == 32
        assert config.default_sprite_height == 32
        assert config.max_sprite_size == 128
        assert config.png_scale == 2

    def test_get_ai_model_string(self):
        """Test that AI model string is formatted correctly."""
        config = ServiceConfig(ai_provider="anthropic", ai_model="claude-sonnet-4-5")

        assert config.get_ai_model_string() == "anthropic:claude-sonnet-4-5"

    def test_get_ai_model_string_ollama(self):
        """Test AI model string for ollama provider."""
        config = ServiceConfig(ai_provider="ollama", ai_model="llama2")

        assert config.get_ai_model_string() == "ollama:llama2"
