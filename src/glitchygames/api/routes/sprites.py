"""Sprite generation endpoints for the GlitchyGames API.

The work is ``glitchygames.api.sprite_requests``'s, which ``glitchygames-client`` also calls in
its own process (plans/2026-11-16-console-sprite-generation.md, part 1); these routes only map its
errors to HTTP statuses: ``AIProviderError`` to 503, ``SpriteRequestRefusedError`` (an output
path off the allowed root) to 400, anything else to 500. A frame extraction's bad input is not an
HTTP error: the response (200) says it failed.
"""

# No `from __future__ import annotations`: FastAPI reads the routes' annotations (their request
# and response models) at run time, as api/routes/health.py does

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from glitchygames.api import sprite_requests
from glitchygames.api.dependencies import (
    get_renderer_service,
    get_sprite_generation_service,
)
from glitchygames.api.models import (  # ruff: ignore[typing-only-first-party-import] - FastAPI resolves the routes' request and response models at run time
    ApngExtractRequest,
    ApngExtractResponse,
    SpriteGenerationRequest,
    SpriteGenerationResponse,
    SpriteRefinementRequest,
)
from glitchygames.services import (
    AIProviderError,
    RendererService,
    SpriteGenerationService,
)

LOG = logging.getLogger('glitchygames.api.sprites')

router: Any = APIRouter(prefix='/sprites', tags=['sprites'])


def _get_services() -> tuple[SpriteGenerationService, RendererService]:
    """Get service instances.

    Returns:
        Tuple of (SpriteGenerationService, RendererService)

    """
    sprite_service = get_sprite_generation_service()
    renderer_service = get_renderer_service()
    return sprite_service, renderer_service


def _http_answer(error: Exception) -> tuple[int, str]:
    """The HTTP status and detail for a sprite request's error (the module docstring's mapping).

    Returns:
        The status code and the detail.
    """
    if isinstance(error, AIProviderError):
        LOG.error('AI provider error', exc_info=error)
        return 503, f'AI provider unavailable: {error}'
    if isinstance(error, sprite_requests.SpriteRequestRefusedError):
        return 400, str(error)
    LOG.error('Unexpected error', exc_info=error)
    return 500, f'Internal server error: {error}'


@router.post('/generate')
async def generate_sprite(request: SpriteGenerationRequest) -> SpriteGenerationResponse:
    """Generate a new sprite from a text prompt (``sprite_requests.generate_response``).

    Args:
        request: Sprite generation request with prompt and options

    Returns:
        Generated sprite data in the requested format

    Raises:
        HTTPException: 503 if the AI provider is unavailable, 400 for a refused output path,
            500 for other errors.

    """
    generation_service, renderer_service = _get_services()
    try:
        return sprite_requests.generate_response(
            request, generation_service=generation_service, renderer_service=renderer_service
        )
    except Exception as error:
        status_code, detail = _http_answer(error)
        raise HTTPException(status_code=status_code, detail=detail) from error


@router.post('/refine')
async def refine_sprite(request: SpriteRefinementRequest) -> SpriteGenerationResponse:
    """Refine an existing sprite from a text prompt (``sprite_requests.refine_response``).

    Args:
        request: Sprite refinement request with prompt, current TOML, and options

    Returns:
        Refined sprite data in the requested format

    Raises:
        HTTPException: 503 if the AI provider is unavailable, 400 for a refused output path,
            500 for other errors.

    """
    generation_service, renderer_service = _get_services()
    try:
        return sprite_requests.refine_response(
            request, generation_service=generation_service, renderer_service=renderer_service
        )
    except Exception as error:
        status_code, detail = _http_answer(error)
        raise HTTPException(status_code=status_code, detail=detail) from error


@router.post('/extract-frames')
async def extract_apng_frames(request: ApngExtractRequest) -> ApngExtractResponse:
    """Extract frames and metadata from an APNG (``sprite_requests.extract_frames_response``).

    Args:
        request: APNG extraction request with base64-encoded APNG data

    Returns:
        Extracted frames and metadata. Bad base64 or an APNG that cannot be parsed is not an
        HTTP error: the response (200) has success=False and the reason in its error field.

    Raises:
        HTTPException: 500 for any unexpected error

    """
    try:
        return sprite_requests.extract_frames_response(apng_base64=request.apng_base64)
    except Exception as error:
        LOG.exception('Unexpected error extracting APNG frames')
        raise HTTPException(status_code=500, detail=f'Internal server error: {error}') from error
