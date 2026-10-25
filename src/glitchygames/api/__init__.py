r"""GlitchyGames API - FastAPI application for sprite generation.

This module provides a REST API for generating and rendering pixel art sprites
using AI providers via aisuite.

Server Usage:
    # Run the server
    glitchygames-server

    # Or with uvicorn
    uvicorn glitchygames.api.main:app --reload

    # Generate a sprite (both TOML and PNG)
    curl -X POST http://localhost:8000/sprites/generate \
        -H "Content-Type: application/json" \
        -d '{"prompt": "16x16 red heart", "output_format": ["toml", "png"]}'

    # Generate sprite with TOML only
    curl -X POST http://localhost:8000/sprites/generate \
        -H "Content-Type: application/json" \
        -d '{"prompt": "16x16 red heart", "output_format": ["toml"]}'

Client Usage:
    # Generate a sprite using the CLI client
    glitchygames-client "16x16 red heart"

    # Generate with specific output formats
    glitchygames-client "16x16 red heart" -f toml -f png

    # Save to a directory
    glitchygames-client "16x16 red heart" -o ./sprites
"""

from glitchygames.api.main import app, create_app, run

__all__ = [
    'app',
    'create_app',
    'run',
]
