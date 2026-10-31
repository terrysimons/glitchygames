"""Health check endpoints for the GlitchyGames API."""

from typing import Any

from fastapi import APIRouter

from glitchygames.api.models import HealthResponse
from glitchygames.services import RendererService, ServiceConfig

router: Any = APIRouter(tags=['health'])


@router.get('/health')
async def health_check() -> HealthResponse:
    """Check the health status of the API.

    Returns service status, version, and configuration information.

    Returns:
        HealthResponse: The result.

    """
    config = ServiceConfig.from_env()

    # Whether pygame is running now (renderer will initialize it if needed): not only whether
    # it was started once, which stays True after pygame.quit() (BUGS.md #113)
    pygame_initialized: bool = RendererService.pygame_running()

    return HealthResponse(
        status='healthy',
        version='1.0.0',
        ai_provider=config.ai_provider,
        ai_model=config.ai_model,
        pygame_initialized=pygame_initialized,
    )


@router.get('/')
async def root() -> dict[str, str]:
    """Root endpoint with API information.

    Returns:
        dict: The result.

    """
    return {
        'name': 'GlitchyGames Sprite Generation API',
        'version': '1.0.0',
        'docs': '/docs',
        'health': '/health',
    }
