"""The REST API's request and response bodies. Anything not declared here is refused."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReasoningEffort(StrEnum):
    """The efforts Bonsai 2's chat template accepts.

    Its template answers ``high`` with an HTTP 500, so that value is refused here. See
    https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/blob/main/KNOWN_ISSUES.md
    """

    NONE = 'none'
    LOW = 'low'
    MEDIUM = 'medium'
    XHIGH = 'xhigh'


class ChatMessage(BaseModel):
    """One message: text, or a list of text and image parts."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    role: str = Field(pattern='^(system|user|assistant|tool)$')
    content: str | list[dict[str, Any]]


class ChatRequest(BaseModel):
    """A chat completion request."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    model: str = 'reasoning'
    messages: list[ChatMessage] = Field(min_length=1)
    # Small limits end the model's reasoning before it answers, which returns nothing
    max_tokens: int = Field(default=16384, gt=0)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, gt=0.0, le=1.0)
    stream: bool = False
    response_format: dict[str, Any] | None = None
    reasoning_effort: ReasoningEffort | None = None


class EmbeddingRequest(BaseModel):
    """An embedding request."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    model: str = 'embedding'
    input: str | list[str]
    dimensions: int | None = Field(default=None, gt=0)


class ModelState(StrEnum):
    """A model's state. Each is distinct: installed isn't loaded, and loading isn't ready."""

    STOPPED = 'stopped'
    READY = 'ready'
    LOADING = 'loading'


class ModelDescription(BaseModel):
    """One model, as ``/v1/models`` and ``/v1/status`` report it."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    id: str
    role: str
    state: ModelState
    dimensions: int | None = None


class ModelList(BaseModel):
    """The ``/v1/models`` response."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    object: str = 'list'
    data: list[ModelDescription]


class StatusResponse(BaseModel):
    """The ``/v1/status`` response."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    protocol_version: int
    sessions: int
    models: list[ModelDescription]


class LiveResponse(BaseModel):
    """The ``/health/live`` response."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    status: str = 'live'


class ReadyResponse(BaseModel):
    """The ``/health/ready`` response: ready means a reasoning and an embedding model answer."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    ready: bool
    models: list[ModelDescription]


class ErrorBody(BaseModel):
    """An error's details."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Every error the service itself returns."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    error: ErrorBody
