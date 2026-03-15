"""FastAPI application for GlitchyGames sprite generation API.

This module provides the main FastAPI application factory and server entry point.

Usage:
    # Run with uvicorn directly
    uvicorn glitchygames.api.main:app --reload

    # Or use the entry point
    glitchygames-server

Environment Variables:
    SPRITE_AI_PROVIDER: AI provider (default: anthropic)
    SPRITE_AI_MODEL: AI model (default: claude-sonnet-4-5)
    SPRITE_AI_TIMEOUT: API timeout in seconds (default: 120)
    SPRITE_DEFAULT_WIDTH: Default sprite width (default: 16)
    SPRITE_DEFAULT_HEIGHT: Default sprite height (default: 16)
    SPRITE_MAX_SIZE: Maximum sprite dimension (default: 64)
    SPRITE_PNG_SCALE: Default PNG scale (default: 1)
"""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from glitchygames.api.routes import health_router, sprites_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

LOG = logging.getLogger("glitchygames.api")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None]:  # noqa: RUF029 - async required by FastAPI lifespan protocol
    """Manage application startup and shutdown lifecycle."""
    LOG.info("Starting GlitchyGames Sprite Generation API")

    # Pre-initialize renderer service to set up pygame in headless mode
    from glitchygames.services import RendererService

    RendererService()
    LOG.info("Renderer service initialized")

    yield

    LOG.info("Shutting down GlitchyGames Sprite Generation API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application

    """
    application = FastAPI(
        title="GlitchyGames Sprite Generation API",
        description=(
            "Generate pixel art sprites using AI. Supports static and animated sprites "
            "with TOML and PNG output formats."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        openapi_tags=[
            {
                "name": "health",
                "description": "Health check and status endpoints",
            },
            {
                "name": "sprites",
                "description": "Sprite generation and refinement endpoints",
            },
        ],
    )

    # Add CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    application.include_router(health_router)
    application.include_router(sprites_router)

    return application


# Create the application instance
app = create_app()


def run() -> None:
    """Entry point for the glitchygames-server command.

    This function is called when running `glitchygames-server` from the command line.
    """
    import uvicorn

    host = os.environ.get("GLITCHYGAMES_HOST", "0.0.0.0")
    port = int(os.environ.get("GLITCHYGAMES_PORT", "8000"))
    reload = os.environ.get("GLITCHYGAMES_RELOAD", "false").lower() == "true"

    LOG.info(f"Starting server on {host}:{port}")
    uvicorn.run(
        "glitchygames.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    run()
