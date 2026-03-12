"""API route modules for GlitchyGames server."""

from glitchygames.api.routes.health import router as health_router
from glitchygames.api.routes.sprites import router as sprites_router

__all__ = [
    "health_router",
    "sprites_router",
]
