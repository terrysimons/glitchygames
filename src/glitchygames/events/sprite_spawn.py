"""The sprite spawn event: a sprite's file text and a world point, added to the game's scene.

The AI console's ``/sprite`` posts one with ``recording.post_input_event`` once a generated
sprite is ready (plans/2026-11-17-sprite-command.md). The engine handles it before any scene sees
it, in every game (``GameEngine.process_events``), so no game's own handlers meet it and every
game gets ``/sprite`` without code of its own. A recording keeps the event, the sprite's whole
text included, so a replay adds the same sprite at the same frame and place without the AI and
without the saved file.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames import recording
from glitchygames.events.base import named_custom_event_type
from glitchygames.sprites.spawned import SpawnedSprite

if TYPE_CHECKING:
    from glitchygames.scenes import Scene

LOG: logging.Logger = logging.getLogger('game.events.sprite_spawn')

# Registered by name at import, before any recording starts, so recordings name it
SPRITE_SPAWN_EVENT: int = named_custom_event_type('glitchygames.sprite_spawn')


class SpriteSpawn(BaseModel):
    """One sprite to add: its file's text, its name, and the world point its center goes at."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    toml_text: str
    sprite_name: str
    world_x: float
    world_y: float

    def to_event(self) -> pygame.event.Event:
        """Return the event that carries this spawn.

        Returns:
            A ``SPRITE_SPAWN_EVENT`` with this spawn's fields as its attributes.

        """
        return pygame.event.Event(SPRITE_SPAWN_EVENT, self.model_dump())

    @classmethod
    def from_event(cls, event: pygame.event.Event) -> SpriteSpawn:
        """Read a spawn back from its event (live, or served by a replay).

        Args:
            event: A ``SPRITE_SPAWN_EVENT``.

        Returns:
            The spawn.

        """
        return cls.model_validate(dict(event.dict))


def post_sprite_spawn(*, spawn: SpriteSpawn) -> bool:
    """Post a spawn as input from outside the game's logic, so a recording keeps it.

    Args:
        spawn: The sprite to add.

    Returns:
        What ``recording.post_input_event`` returns: whether the event was queued.

    """
    return recording.post_input_event(spawn.to_event())


def add_spawned_sprite(*, spawn: SpriteSpawn, scene: Scene) -> SpawnedSprite | None:
    """Build the spawn's sprite and add it to the game's own scene.

    The game's own scene is ``scene.debug_subject``: under the pause screen, the paused game,
    as the AI console's ``/inspect`` describes it. Text that cannot build a sprite is logged as
    one warning line and adds nothing; the game goes on.

    Args:
        spawn: The sprite to add.
        scene: The active scene.

    Returns:
        The sprite added, or None when its text could not build one.

    """
    try:
        sprite = SpawnedSprite.from_text(
            text=spawn.toml_text,
            source_name=f'spawned sprite {spawn.sprite_name!r}',
            center_x=spawn.world_x,
            center_y=spawn.world_y,
        )
    except ValueError as error:
        LOG.warning('Not added: %s', error)
        return None
    scene.debug_subject.all_sprites.add(sprite)
    return sprite
