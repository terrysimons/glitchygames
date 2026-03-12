"""Core services for GlitchyGames.

This module provides framework-agnostic services that can be used by
CLI tools, APIs, or any other interface.
"""

from glitchygames.services.config import ServiceConfig
from glitchygames.services.exceptions import (
    AIProviderError,
    RenderingError,
    SpriteServiceError,
    ValidationError,
)
from glitchygames.services.renderer_service import RenderedFrame, RendererService
from glitchygames.services.sprite_generation_service import SpriteGenerationService

__all__ = [
    "AIProviderError",
    "RenderedFrame",
    "RendererService",
    "RenderingError",
    "ServiceConfig",
    "SpriteGenerationService",
    "SpriteServiceError",
    "ValidationError",
]
