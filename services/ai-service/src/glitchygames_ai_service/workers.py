"""The private model servers: which are answering, and which one a request means."""

from __future__ import annotations

import httpx2

from glitchygames_ai_service.schemas import ModelDescription, ModelState
from glitchygames_ai_service.settings import ModelEntry, ModelRole, Settings

HEALTH_TIMEOUT_SECONDS = 1.0
HTTP_OK = 200
HTTP_LOADING = 503


class ModelUnavailableError(Exception):
    """The request names a model that isn't running, or none at all."""


class Workers:
    """Talks to the model servers, with one reused connection pool."""

    def __init__(self, *, settings: Settings) -> None:
        """Prepare the connection pool.

        Args:
            settings: The service's settings.

        """
        self.settings = settings
        worker_key = settings.worker_key_file.read_text(encoding='utf-8').strip()
        self.client = httpx2.AsyncClient(
            headers={'Authorization': f'Bearer {worker_key}'},
            timeout=httpx2.Timeout(settings.request_timeout_seconds, connect=5.0),
        )

    async def close(self) -> None:
        """Close the connection pool."""
        await self.client.aclose()

    def base_url(self, *, model: ModelEntry) -> str:
        """Return where a model is served.

        Args:
            model: The model.

        Returns:
            Its base URL.

        """
        return f'http://{self.settings.host}:{model.port}'

    async def state_of(self, *, model: ModelEntry) -> ModelState:
        """Ask a model server how it is.

        Args:
            model: The model.

        Returns:
            Stopped if nothing answers, loading on a 503, else ready.

        """
        try:
            response = await self.client.get(
                f'{self.base_url(model=model)}/health', timeout=HEALTH_TIMEOUT_SECONDS
            )
        except httpx2.TransportError:
            return ModelState.STOPPED
        if response.status_code == HTTP_LOADING:
            return ModelState.LOADING
        return ModelState.READY if response.status_code == HTTP_OK else ModelState.STOPPED

    async def describe_all(self) -> list[ModelDescription]:
        """Describe every installed model as it is now.

        Returns:
            One description per model.

        """
        return [
            ModelDescription(
                id=model.alias,
                role=model.role.value,
                state=await self.state_of(model=model),
                dimensions=model.dimensions,
            )
            for model in self.settings.models
        ]

    async def resolve(self, *, name: str, role: ModelRole) -> ModelEntry:
        """Find the running model a request means.

        Args:
            name: An exact alias, or a role name (``vision`` means a reasoning model).
            role: The role the endpoint needs.

        Returns:
            The model.

        Raises:
            ModelUnavailableError: If it isn't installed for this role, or isn't ready. It's never
                silently replaced with another size.

        """
        role_names = {role.value} | ({'vision'} if role is ModelRole.REASONING else set())
        candidates = [
            model
            for model in self.settings.models
            if model.role is role and (name in role_names or name == model.alias)
        ]
        if not candidates:
            message = f'{name!r} is not an installed {role.value} model'
            raise ModelUnavailableError(message)
        for model in candidates:
            if await self.state_of(model=model) is ModelState.READY:
                return model
        message = f'{name!r} is not ready'
        raise ModelUnavailableError(message)
