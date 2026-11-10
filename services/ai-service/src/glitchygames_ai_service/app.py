"""The service: REST for models, status and docs, and a WebSocket for each game's live link."""

import asyncio
import hmac
import json
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated, Any

import httpx2
from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse

from glitchygames_ai_service.schemas import (
    ChatRequest,
    EmbeddingRequest,
    ErrorBody,
    ErrorResponse,
    LiveResponse,
    ModelList,
    ModelState,
    ReadyResponse,
    StatusResponse,
)
from glitchygames_ai_service.sessions import SessionTracker
from glitchygames_ai_service.settings import ModelRole, Settings
from glitchygames_ai_service.workers import ModelUnavailableError, Workers

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

LOG = logging.getLogger(__name__)

# Bumped when the WebSocket's messages change incompatibly. A game and a service can be different
# versions, as they share no code, so they exchange this on connect
PROTOCOL_VERSION = 1
CLOSE_POLICY_VIOLATION = 1008
# WebSocket close codes in the range kept for applications
CLOSE_PROTOCOL_MISMATCH = 4001
CLOSE_BAD_HELLO = 4002

# The default fonts off, as they'd reach the network, and no proxy configured for the same reason
DOCS_PAGE = """<!doctype html>
<html>
  <head>
    <title>GlitchyGames Local AI</title>
    <meta charset="utf-8">
  </head>
  <body>
    <script id="api-reference" data-url="/openapi.json"
      data-configuration='{"withDefaultFonts": false}'></script>
    <script src="/docs/scalar.js"></script>
  </body>
</html>
"""

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {'model': ErrorResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {'model': ErrorResponse},
}


class ServiceError(Exception):
    """An error with its own HTTP status, reported in the service's error format."""

    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        """Describe the error.

        Args:
            status_code: The HTTP status.
            code: A stable, machine-readable name.
            message: What went wrong, for a person.

        """
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class RequestSlots:
    """A limit on requests in progress: over it, refuse rather than build an unbounded queue."""

    def __init__(self, *, limit: int) -> None:
        """Start with every slot free.

        Args:
            limit: How many requests may run at once.

        """
        self.limit = limit
        self.in_use = 0

    def take(self) -> None:
        """Claim a slot.

        Raises:
            ServiceError: If every slot is in use.

        """
        if self.in_use >= self.limit:
            raise ServiceError(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code='too_many_requests',
                message='Every request slot is in use; try again shortly',
            )
        self.in_use += 1

    def release(self) -> None:
        """Give a slot back."""
        self.in_use -= 1


def error_json(*, code: str, message: str) -> dict[str, Any]:
    """Build the service's error body.

    Args:
        code: A stable, machine-readable name.
        message: What went wrong, for a person.

    Returns:
        The JSON-ready body.

    """
    return ErrorResponse(error=ErrorBody(code=code, message=message)).model_dump()


def token_matches(*, authorization: str | None, expected: str) -> bool:
    """Check a request's bearer token, in constant time.

    Args:
        authorization: The Authorization header, if any.
        expected: The service's token.

    Returns:
        Whether it matches.

    """
    return hmac.compare_digest(authorization or '', f'Bearer {expected}')


def merged_messages(*, request: ChatRequest) -> list[dict[str, Any]]:
    """Merge every system message into one leading message.

    Bonsai 2's template answers anything else with an HTTP 500. See
    https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/blob/main/KNOWN_ISSUES.md

    Args:
        request: The chat request.

    Returns:
        The messages to send.

    """
    system_texts = [
        str(message.content) for message in request.messages if message.role == 'system'
    ]
    others = [message.model_dump() for message in request.messages if message.role != 'system']
    if system_texts:
        return [{'role': 'system', 'content': '\n\n'.join(system_texts)}, *others]
    return others


def worker_chat_body(*, request: ChatRequest, alias: str) -> dict[str, Any]:
    """Build what a model server receives for a chat request.

    Args:
        request: The chat request.
        alias: The model that will answer.

    Returns:
        The JSON-ready body.

    """
    body: dict[str, Any] = {
        'model': alias,
        'messages': merged_messages(request=request),
        'stream': request.stream,
    }
    for name in ('max_tokens', 'temperature', 'top_p', 'response_format'):
        value = getattr(request, name)
        if value is not None:
            body[name] = value
    if request.reasoning_effort is not None:
        body['chat_template_kwargs'] = {'reasoning_effort': request.reasoning_effort.value}
    return body


def worker_failed(*, error: httpx2.HTTPError) -> ServiceError:
    """Describe a model server's failure, without its request or any payload.

    Args:
        error: What httpx2 raised.

    Returns:
        The error to report.

    """
    LOG.warning('A model server failed: %s', type(error).__name__)
    return ServiceError(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code='model_failed',
        message=f'The model server failed: {type(error).__name__}',
    )


def workers_of(request: Request) -> Workers:
    """Return the app's model servers.

    Args:
        request: The current request.

    Returns:
        The workers.

    """
    return request.app.state.workers


WorkersDependency = Annotated[Workers, Depends(workers_of)]


async def stream_chat(
    *, workers: Workers, url: str, body: dict[str, Any], slots: RequestSlots
) -> StreamingResponse:
    """Start a streamed chat request, holding its slot until the stream ends.

    Args:
        workers: The model servers.
        url: The model server's chat URL.
        body: What to send it.
        slots: Where the request's slot goes back.

    Returns:
        The streaming response.

    Raises:
        ServiceError: If the model server can't be reached.

    """
    try:
        upstream = await workers.client.send(
            workers.client.build_request('POST', url, json=body), stream=True
        )
    except httpx2.HTTPError as error:
        slots.release()
        raise worker_failed(error=error) from error

    async def forward() -> AsyncIterator[bytes]:
        # Closing the upstream when the client leaves is what cancels the model's work. A failure
        # mid-stream is never retried, as part of the answer has already gone out
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            slots.release()

    return StreamingResponse(
        forward(), status_code=upstream.status_code, media_type='text/event-stream'
    )


async def serve_session(*, websocket: WebSocket, maximum_message_bytes: int) -> None:
    """Answer a session's messages until it closes. Agents join this in a later stage.

    Args:
        websocket: The session.
        maximum_message_bytes: The largest message accepted.

    """
    while True:
        text = await websocket.receive_text()
        if len(text) > maximum_message_bytes:
            await websocket.send_json({'type': 'error', 'code': 'message_too_large'})
            continue
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            await websocket.send_json({'type': 'error', 'code': 'invalid_json'})
            continue
        if isinstance(message, dict) and message.get('type') == 'ping':
            await websocket.send_json({'type': 'pong', 'sequence': message.get('sequence')})
        else:
            await websocket.send_json({'type': 'error', 'code': 'unknown_message'})


async def read_hello(*, websocket: WebSocket) -> dict[str, Any] | None:
    """Read a session's first message.

    Args:
        websocket: The session.

    Returns:
        The hello, or None if the first message isn't one (the session is then closed).

    """
    hello: object = None
    try:
        hello = json.loads(await websocket.receive_text())
    except json.JSONDecodeError:
        LOG.info('A session opened with something other than JSON')
    except WebSocketDisconnect:
        return None
    if isinstance(hello, dict) and hello.get('type') == 'hello':
        return hello
    await websocket.close(code=CLOSE_BAD_HELLO, reason='Expected a hello')
    return None


def create_app(*, settings: Settings) -> FastAPI:  # noqa: C901, PLR0915 - every route, in one place
    """Build the service.

    Args:
        settings: The service's settings.

    Returns:
        The application.

    """
    service_key = settings.service_key_file.read_text(encoding='utf-8').strip()

    async def stop_models() -> None:
        """Run ``ai-service.sh stop``, which stops this service last."""
        process = await asyncio.create_subprocess_exec(str(settings.control_script), 'stop')
        await process.wait()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.workers = Workers(settings=settings)
        application.state.sessions = SessionTracker(
            grace_seconds=settings.shutdown_grace_seconds,
            on_last_session_gone=stop_models,
        )
        application.state.slots = RequestSlots(limit=settings.maximum_concurrent_requests)
        yield
        await application.state.workers.close()

    application = FastAPI(
        title='GlitchyGames Local AI',
        version='0.1.0',
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )

    @application.exception_handler(ServiceError)
    async def service_error(_request: Request, error: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=error_json(code=error.code, message=error.message),
        )

    @application.exception_handler(ModelUnavailableError)
    async def model_unavailable(_request: Request, error: ModelUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error_json(code='model_unavailable', message=str(error)),
        )

    async def require_token(request: Request) -> None:
        if not token_matches(
            authorization=request.headers.get('authorization'), expected=service_key
        ):
            raise ServiceError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code='unauthorized',
                message='A valid bearer token is required',
            )

    authorized = [Depends(require_token)]

    @application.get('/health/live', operation_id='healthLive', tags=['health'])
    async def health_live() -> LiveResponse:
        """Whether the API process is up."""
        return LiveResponse()

    @application.get(
        '/health/ready',
        operation_id='healthReady',
        tags=['health'],
        response_model=ReadyResponse,
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {'model': ReadyResponse}},
    )
    async def health_ready(workers: WorkersDependency) -> JSONResponse:
        """Whether a reasoning and an embedding model are both answering."""
        models = await workers.describe_all()
        ready_roles = {model.role for model in models if model.state is ModelState.READY}
        ready = {ModelRole.REASONING.value, ModelRole.EMBEDDING.value} <= ready_roles
        return JSONResponse(
            status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ReadyResponse(ready=ready, models=models).model_dump(mode='json'),
        )

    @application.get(
        '/v1/models',
        operation_id='listModels',
        tags=['models'],
        dependencies=authorized,
        responses=ERROR_RESPONSES,
    )
    async def list_models(workers: WorkersDependency) -> ModelList:
        """Every installed model and its state. Installed isn't the same as ready."""
        return ModelList(data=await workers.describe_all())

    @application.get(
        '/v1/status',
        operation_id='getStatus',
        tags=['status'],
        dependencies=authorized,
        responses=ERROR_RESPONSES,
    )
    async def get_status(request: Request, workers: WorkersDependency) -> StatusResponse:
        """Live sessions and each model's state."""
        return StatusResponse(
            protocol_version=PROTOCOL_VERSION,
            sessions=request.app.state.sessions.count,
            models=await workers.describe_all(),
        )

    @application.post(
        '/v1/embeddings',
        operation_id='createEmbeddings',
        tags=['models'],
        dependencies=authorized,
        responses=ERROR_RESPONSES,
    )
    async def create_embeddings(
        body: EmbeddingRequest, request: Request, workers: WorkersDependency
    ) -> Response:
        """Dense vectors from the embedding model."""
        slots: RequestSlots = request.app.state.slots
        slots.take()
        try:
            model = await workers.resolve(name=body.model, role=ModelRole.EMBEDDING)
            if body.dimensions is not None and body.dimensions != model.dimensions:
                raise ServiceError(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    code='unsupported_dimensions',
                    message=f'{model.alias} makes {model.dimensions} dimensions only, for now',
                )
            response = await workers.client.post(
                f'{workers.base_url(model=model)}/v1/embeddings',
                json={'model': model.alias, 'input': body.input},
            )
        except httpx2.HTTPError as error:
            raise worker_failed(error=error) from error
        finally:
            slots.release()
        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type='application/json',
        )

    @application.post(
        '/v1/chat/completions',
        operation_id='createChatCompletion',
        tags=['models'],
        dependencies=authorized,
        responses=ERROR_RESPONSES,
    )
    async def create_chat_completion(
        body: ChatRequest, request: Request, workers: WorkersDependency
    ) -> Response:
        """Text and image requests to the reasoning model.

        With ``stream``, the answer arrives as server-sent events, and disconnecting cancels it.
        """
        slots: RequestSlots = request.app.state.slots
        slots.take()
        try:
            model = await workers.resolve(name=body.model, role=ModelRole.REASONING)
        except ModelUnavailableError:
            slots.release()
            raise
        url = f'{workers.base_url(model=model)}/v1/chat/completions'
        worker_body = worker_chat_body(request=body, alias=model.alias)
        if body.stream:
            return await stream_chat(workers=workers, url=url, body=worker_body, slots=slots)
        try:
            response = await workers.client.post(url, json=worker_body)
        except httpx2.HTTPError as error:
            raise worker_failed(error=error) from error
        finally:
            slots.release()
        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type='application/json',
        )

    @application.get('/docs', include_in_schema=False)
    async def docs() -> HTMLResponse:
        return HTMLResponse(DOCS_PAGE)

    @application.get('/docs/scalar.js', include_in_schema=False)
    async def scalar_script() -> FileResponse:
        return FileResponse(settings.scalar_file, media_type='text/javascript')

    @application.websocket('/v1/session')
    async def session(websocket: WebSocket) -> None:
        """One game's live link. A browser can reach loopback, so token and Origin both count."""
        origin = websocket.headers.get('origin')
        if origin is not None and origin not in settings.allowed_origins:
            await websocket.close(code=CLOSE_POLICY_VIOLATION, reason='Origin not allowed')
            return
        if not token_matches(
            authorization=websocket.headers.get('authorization'), expected=service_key
        ):
            await websocket.close(code=CLOSE_POLICY_VIOLATION, reason='Invalid token')
            return
        await websocket.accept()
        hello = await read_hello(websocket=websocket)
        if hello is None:
            return
        if hello.get('protocol_version') != PROTOCOL_VERSION:
            await websocket.send_json(
                {
                    'type': 'refused',
                    'reason': 'protocol_version',
                    'protocol_version': PROTOCOL_VERSION,
                }
            )
            await websocket.close(code=CLOSE_PROTOCOL_MISMATCH, reason='Protocol version')
            return

        tracker: SessionTracker = websocket.app.state.sessions
        tracker.opened()
        try:
            workers: Workers = websocket.app.state.workers
            models = await workers.describe_all()
            await websocket.send_json(
                {
                    'type': 'welcome',
                    'protocol_version': PROTOCOL_VERSION,
                    'models': [model.model_dump(mode='json') for model in models],
                }
            )
            await serve_session(
                websocket=websocket, maximum_message_bytes=settings.maximum_message_bytes
            )
        except WebSocketDisconnect:
            LOG.info('A session closed')
        finally:
            tracker.closed()

    return application
