"""The game an engine runs: its scene class, and the scene ``start()`` builds from it.

``engine.game`` is the game's scene class, before and after ``start()``; the scene built from it
is ``engine.running_game.instance`` (the owner, 2026-10-29: "RunningGame is good"). Engine
context sub-plan 2's Task 7 had made ``engine.game`` the class until ``start()`` and the
instance after, one name for two kinds of thing; this keeps each in its own place, with room for
more facts about the running game later.

A ``RunningGame`` is frozen: an engine holds one with no instance from its construction, and
replaces it with one holding the built scene when the scene is built (``GameEngine._build_game``,
and the golden-trace harness's ``install_game``).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class RunningGame(BaseModel):
    """The game an engine runs.

    Attributes:
        game_class: The game's scene class (``engine.game``). Typed ``Any`` as ``engine.game``
            is: tests and harnesses hand the engine stand-ins that are not ``Scene`` classes.
        instance: The scene built from it, or None until the engine builds it. ``Any`` for the
            same reason.

    """

    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    game_class: Any
    instance: Any = None
