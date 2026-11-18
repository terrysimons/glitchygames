"""A stand-in for the local AI service's chat client (glitchygames.ai.local_service).

Built from the client's contract as the sprite service uses it:
``chat.completions.create(**request)`` returns choices whose first message holds the model's
text, or raises (``LocalAIServiceError`` when the service fails). Shared by the sprite
service's, the sprite requests' and the client's tests.
"""

from __future__ import annotations

import types


class FakeAIClient:
    """Stands in for the local service's client: answers a scripted reply, recording requests."""

    def __init__(self, *, reply):
        """Answer `reply` to every request."""
        self.reply = reply
        self.requests: list[dict] = []
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self._create),
        )

    def _create(self, **request):
        self.requests.append(request)
        if isinstance(self.reply, Exception):
            raise self.reply
        message = types.SimpleNamespace(content=self.reply)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])
