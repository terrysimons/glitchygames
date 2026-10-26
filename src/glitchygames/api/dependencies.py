"""FastAPI dependency injection for GlitchyGames API."""

from functools import lru_cache

from glitchygames.services import RendererService, ServiceConfig, SpriteGenerationService


@lru_cache
def get_config() -> ServiceConfig:
    """Get the service configuration (cached).

    Returns:
        ServiceConfig instance from environment variables

    """
    return ServiceConfig.from_env()


@lru_cache
def get_sprite_generation_service() -> SpriteGenerationService:
    """Get the sprite generation service (cached).

    Returns:
        SpriteGenerationService instance

    """
    return SpriteGenerationService(get_config())


@lru_cache
def get_renderer_service() -> RendererService:
    """Get the renderer service (cached).

    Returns:
        RendererService instance

    """
    return RendererService(get_config())
