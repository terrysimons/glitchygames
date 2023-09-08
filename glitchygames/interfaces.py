from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import pygame

class SpriteInterface:
    def update_nested_sprites(self: Self) -> None:
        pass

    def update(self: Self) -> None:
        pass

    def render(self: Self, screen: pygame.Surface) -> None:
        pass

class SceneInterface:
    def switch_to_scene(self: Self, next_scene: SceneInterface) -> None:
        pass

    def terminate(self: Self) -> None:
        pass
