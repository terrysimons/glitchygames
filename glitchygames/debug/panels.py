"""Debug overlay world panels: collision hitboxes and physics state.

These are pure drawing functions. They read scene, sprite and camera state and draw onto
the surface they are given; they never change positions, velocities, camera state or
sprite dirty flags.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import pygame

from glitchygames.collision.layers import get_sprite_collision_rect
from glitchygames.debug.overlay import PHYSICS_ARROW_MAXIMUM_PIXELS, PHYSICS_ARROW_SECONDS
from glitchygames.debug.protocols import HasPhysicsBody

if TYPE_CHECKING:
    from glitchygames.camera import Camera2D

type Color = tuple[int, int, int]

LAYER_PALETTE: tuple[Color, ...] = (
    (0, 200, 255),
    (255, 140, 0),
    (200, 80, 255),
    (255, 80, 160),
    (120, 255, 120),
    (255, 255, 120),
    (80, 140, 255),
    (0, 200, 150),
    (255, 120, 90),
    (180, 180, 255),
)
OVERLAP_COLOR: Color = (255, 255, 255)
UNLAYERED_COLOR: Color = (90, 90, 90)
GROUNDED_COLOR: Color = (60, 220, 60)
AIRBORNE_COLOR: Color = (230, 60, 60)
ARROW_COLOR: Color = (255, 220, 0)

LEGEND_MARGIN = 4
LEGEND_SWATCH_SIZE = 8
GROUND_BAR_HEIGHT = 3
ARROWHEAD_LENGTH = 6
ARROWHEAD_SPREAD_RADIANS = math.radians(30)


def screen_rect_for(
    *, sprite: Any, camera: Camera2D, screen_offset: tuple[int, int]
) -> pygame.Rect:
    """Compute where a sprite's collision rect appears on the presented frame.

    Sprites with world_x and world_y have a world-space collision rect, whose top-left is
    converted through the camera. Other sprites already have screen-space rects.

    Args:
        sprite (Any): The sprite to locate.
        camera (Camera2D): The active camera.
        screen_offset (tuple[int, int]): Extra offset applied to the whole frame (screen shake).

    Returns:
        pygame.Rect: A new rect in presented-frame coordinates.

    """
    world_rect = get_sprite_collision_rect(sprite)
    screen_rect = world_rect.copy()
    if hasattr(sprite, 'world_x') and hasattr(sprite, 'world_y'):
        screen_rect.topleft = camera.apply(world_rect.x, world_rect.y)
    screen_rect.move_ip(screen_offset)
    return screen_rect


def _layer_membership(*, collisions: Any) -> list[tuple[str, Color, list[Any]]]:
    """List each layer with its colour and sprites, in creation order.

    Returns:
        list[tuple[str, Color, list[Any]]]: Layer name, colour and sprites.

    """
    return [
        (name, LAYER_PALETTE[index % len(LAYER_PALETTE)], list(collisions.get_layer(name).sprites))
        for index, name in enumerate(collisions.layer_names)
    ]


def _overlapping_sprite_ids(*, layers: list[tuple[str, Color, list[Any]]]) -> set[int]:
    """Find sprites that overlap a sprite from a different layer (in world space).

    Returns:
        set[int]: The id() of every sprite with a cross-layer overlap.

    """
    overlapping: set[int] = set()
    for first_index, (_, _, first_sprites) in enumerate(layers):
        for _, _, second_sprites in layers[first_index + 1 :]:
            for first_sprite in first_sprites:
                first_rect = get_sprite_collision_rect(first_sprite)
                for second_sprite in second_sprites:
                    if first_sprite is second_sprite:
                        continue
                    if first_rect.colliderect(get_sprite_collision_rect(second_sprite)):
                        overlapping.add(id(first_sprite))
                        overlapping.add(id(second_sprite))
    return overlapping


def draw_collision_panel(
    *,
    surface: pygame.Surface,
    scene: Any,
    camera: Camera2D,
    screen_offset: tuple[int, int],
    font: Any,
) -> None:
    """Draw hitbox outlines coloured by collision layer, plus a legend.

    Sprites in different layers that overlap are outlined in OVERLAP_COLOR. Sprites in the
    scene's all_sprites that belong to no layer are outlined in UNLAYERED_COLOR. A scene
    without a collision manager draws nothing.

    Args:
        surface (pygame.Surface): The presented frame to draw onto.
        scene (Any): The active scene.
        camera (Camera2D): The active camera.
        screen_offset (tuple[int, int]): Extra offset applied to the whole frame.
        font (Any): Font used for the legend.

    """
    collisions = getattr(scene, 'collisions', None)
    if collisions is None:
        return

    layers = _layer_membership(collisions=collisions)
    overlapping_ids = _overlapping_sprite_ids(layers=layers)
    layered_ids: set[int] = set()

    for _, layer_color, layer_sprites in layers:
        for sprite in layer_sprites:
            if id(sprite) in layered_ids:
                continue
            layered_ids.add(id(sprite))
            outline_color = OVERLAP_COLOR if id(sprite) in overlapping_ids else layer_color
            outline_rect = screen_rect_for(
                sprite=sprite, camera=camera, screen_offset=screen_offset
            )
            pygame.draw.rect(surface, outline_color, outline_rect, width=1)

    for sprite in getattr(scene, 'all_sprites', ()):
        if id(sprite) in layered_ids:
            continue
        outline_rect = screen_rect_for(sprite=sprite, camera=camera, screen_offset=screen_offset)
        pygame.draw.rect(surface, UNLAYERED_COLOR, outline_rect, width=1)

    _draw_legend(surface=surface, layers=layers, font=font)


def _draw_legend(
    *, surface: pygame.Surface, layers: list[tuple[str, Color, list[Any]]], font: Any
) -> None:
    """Draw one legend row per layer along the bottom-left, last layer lowest."""
    row_bottom = surface.get_height() - LEGEND_MARGIN
    for name, layer_color, layer_sprites in reversed(layers):
        text_surface = font.render(
            f'{name}: {len(layer_sprites)}', antialias=False, color=layer_color
        )
        row_height = max(text_surface.get_height(), LEGEND_SWATCH_SIZE)
        row_top = row_bottom - row_height
        pygame.draw.rect(
            surface,
            layer_color,
            pygame.Rect(LEGEND_MARGIN, row_top, LEGEND_SWATCH_SIZE, LEGEND_SWATCH_SIZE),
        )
        surface.blit(text_surface, (LEGEND_MARGIN + LEGEND_SWATCH_SIZE + 4, row_top))
        row_bottom = row_top - 2


def _draw_arrow(
    *, surface: pygame.Surface, start: tuple[float, float], vector: tuple[float, float]
) -> None:
    """Draw a line from start along vector with a two-line arrowhead."""
    end_x = start[0] + vector[0]
    end_y = start[1] + vector[1]
    pygame.draw.line(surface, ARROW_COLOR, start, (end_x, end_y))
    if vector == (0, 0):
        return
    backward_angle = math.atan2(vector[1], vector[0]) + math.pi
    for spread in (-ARROWHEAD_SPREAD_RADIANS, ARROWHEAD_SPREAD_RADIANS):
        head_x = end_x + ARROWHEAD_LENGTH * math.cos(backward_angle + spread)
        head_y = end_y + ARROWHEAD_LENGTH * math.sin(backward_angle + spread)
        pygame.draw.line(surface, ARROW_COLOR, (end_x, end_y), (head_x, head_y))


def draw_physics_panel(
    *,
    surface: pygame.Surface,
    scene: Any,
    camera: Camera2D,
    screen_offset: tuple[int, int],
    font: Any,
) -> None:
    """Draw velocity arrows, ground state bars and velocity text for physics sprites.

    The arrow is the distance travelled in PHYSICS_ARROW_SECONDS, capped at
    PHYSICS_ARROW_MAXIMUM_PIXELS. The bar under the sprite is green when it is on the ground
    and red otherwise. Sprites without a physics body are skipped.

    Args:
        surface (pygame.Surface): The presented frame to draw onto.
        scene (Any): The active scene.
        camera (Camera2D): The active camera.
        screen_offset (tuple[int, int]): Extra offset applied to the whole frame.
        font (Any): Font used for the velocity text.

    """
    for sprite in getattr(scene, 'all_sprites', ()):
        if not isinstance(sprite, HasPhysicsBody):
            continue
        body = sprite.physics
        sprite_rect = screen_rect_for(sprite=sprite, camera=camera, screen_offset=screen_offset)

        vector_x = body.velocity_x * PHYSICS_ARROW_SECONDS
        vector_y = body.velocity_y * PHYSICS_ARROW_SECONDS
        vector_length = math.hypot(vector_x, vector_y)
        if vector_length > PHYSICS_ARROW_MAXIMUM_PIXELS:
            scale = PHYSICS_ARROW_MAXIMUM_PIXELS / vector_length
            vector_x *= scale
            vector_y *= scale
        _draw_arrow(
            surface=surface,
            start=(sprite_rect.centerx, sprite_rect.centery),
            vector=(round(vector_x), round(vector_y)),
        )

        ground_color = GROUNDED_COLOR if body.on_ground else AIRBORNE_COLOR
        pygame.draw.rect(
            surface,
            ground_color,
            pygame.Rect(sprite_rect.left, sprite_rect.bottom, sprite_rect.width, GROUND_BAR_HEIGHT),
        )

        velocity_text = f'({round(body.velocity_x)}, {round(body.velocity_y)})'
        surface.blit(
            font.render(velocity_text, antialias=False, color=ARROW_COLOR),
            (sprite_rect.right + 2, sprite_rect.top),
        )
