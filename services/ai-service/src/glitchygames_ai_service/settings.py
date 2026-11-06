"""What the service knows about this install, read from one JSON file Ansible renders."""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

CONFIG_ENVIRONMENT_VARIABLE = 'GLITCHYGAMES_AI_SERVICE_CONFIG'


class ModelRole(StrEnum):
    """What a model is for, and the name a client can ask for it by."""

    REASONING = 'reasoning'
    EMBEDDING = 'embedding'


class ModelEntry(BaseModel):
    """One installed model."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    alias: str
    role: ModelRole
    port: int
    # What an embedding model's vectors hold; None for a reasoning model
    dimensions: int | None = None


class Settings(BaseModel):
    """The service's settings.

    Attributes:
        host: Where it listens: loopback, always.
        port: The port games and tools use.
        models: Every model installed here, running or not.
        service_key_file: Holds the token clients send.
        worker_key_file: Holds the token the model servers require.
        control_script: ``ai-service.sh``, which starts and stops the models.
        scalar_file: The local copy of Scalar's script, served by ``/docs``.
        allowed_origins: Browser origins allowed in. Native clients send none.
        shutdown_grace_seconds: How long after the last session closes the models stop.
        maximum_concurrent_requests: Requests served at once; more get a 503.
        request_timeout_seconds: The longest one model request may take.
        maximum_message_bytes: The largest WebSocket message accepted.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    host: str = '127.0.0.1'
    port: int = 11449
    models: tuple[ModelEntry, ...]
    service_key_file: Path
    worker_key_file: Path
    control_script: Path
    scalar_file: Path
    allowed_origins: tuple[str, ...] = ()
    shutdown_grace_seconds: float = 30.0
    maximum_concurrent_requests: int = 4
    request_timeout_seconds: float = 900.0
    maximum_message_bytes: int = 1_048_576


def load_settings() -> Settings:
    """Read the settings file the environment names.

    Returns:
        The settings.

    """
    path = Path(os.environ[CONFIG_ENVIRONMENT_VARIABLE])
    return Settings.model_validate_json(path.read_text(encoding='utf-8'))
