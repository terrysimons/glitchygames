"""Configuration for GlitchyGames services.

Configuration is loaded from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass, field


@dataclass
class ServiceConfig:
    """Configuration for sprite generation and rendering services.

    Attributes:
        ai_provider: AI provider to use (anthropic, openai, ollama, etc.)
        ai_model: Model identifier for the AI provider
        ai_timeout: Timeout in seconds for AI API calls
        default_sprite_width: Default sprite width if not specified
        default_sprite_height: Default sprite height if not specified
        max_sprite_size: Maximum allowed sprite dimension (width or height)
        png_scale: Default scale factor for PNG output

    """

    ai_provider: str = field(
        default_factory=lambda: os.environ.get("SPRITE_AI_PROVIDER", "anthropic")
    )
    ai_model: str = field(
        default_factory=lambda: os.environ.get("SPRITE_AI_MODEL", "claude-sonnet-4-5")
    )
    ai_timeout: int = field(default_factory=lambda: int(os.environ.get("SPRITE_AI_TIMEOUT", "120")))
    default_sprite_width: int = field(
        default_factory=lambda: int(os.environ.get("SPRITE_DEFAULT_WIDTH", "16"))
    )
    default_sprite_height: int = field(
        default_factory=lambda: int(os.environ.get("SPRITE_DEFAULT_HEIGHT", "16"))
    )
    max_sprite_size: int = field(
        default_factory=lambda: int(os.environ.get("SPRITE_MAX_SIZE", "64"))
    )
    png_scale: int = field(default_factory=lambda: int(os.environ.get("SPRITE_PNG_SCALE", "1")))

    @classmethod
    def from_env(cls) -> "ServiceConfig":
        """Create configuration from environment variables.

        Returns:
            ServiceConfig instance with values from environment

        """
        return cls()

    def get_ai_model_string(self) -> str:
        """Get the full model string for aisuite.

        Returns:
            Model string in format "provider:model"

        """
        return f"{self.ai_provider}:{self.ai_model}"
