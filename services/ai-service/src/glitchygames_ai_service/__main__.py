"""Run the service: ``python -m glitchygames_ai_service``."""

from __future__ import annotations

import uvicorn

from glitchygames_ai_service.app import create_app
from glitchygames_ai_service.settings import load_settings


def main() -> None:
    """Serve on loopback until stopped."""
    settings = load_settings()
    uvicorn.run(
        create_app(settings=settings),
        host=settings.host,
        port=settings.port,
        log_level='warning',
        ws_max_size=settings.maximum_message_bytes,
    )


if __name__ == '__main__':  # pragma: no cover - run as a module by launchd
    main()
