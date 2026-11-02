"""Debug overlay world panels: collision hitboxes and physics state.

These are pure drawing functions. They read scene, sprite and camera state and draw onto
the surface they are given; they never change positions, velocities, camera state or
sprite dirty flags.
"""

from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING, Any

import pygame

from glitchygames.collision.detection import is_world_rect_sprite, snapped_world_position
from glitchygames.collision.layers import get_sprite_collision_rect
from glitchygames.debug.protocols import HasPhysicsBody
from glitchygames.fonts import FontManager

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from glitchygames.audio.engine import AudioDiagnosticsSnapshot
    from glitchygames.audio.voices import ChannelState
    from glitchygames.camera import Camera2D
    from glitchygames.collision.layers import CollisionManager
    from glitchygames.debug.overlay import DebugOverlay, DebugPanel

type Color = tuple[int, int, int]

# Debug text sits on a translucent dark backing so it stays readable over game art and HUDs.
TEXT_BACKING_COLOR = (0, 0, 0, 170)
TEXT_BACKING_PADDING = 2
# Backings are reused by size (see _backing_surface); text widths vary, so the cache is
# cleared when it reaches this many sizes rather than growing without limit
BACKING_SURFACE_CACHE_LIMIT = 64
_BACKING_SURFACES: dict[tuple[int, int], pygame.Surface] = {}

PHYSICS_ARROW_SECONDS = 0.1
PHYSICS_ARROW_MAXIMUM_PIXELS = 80

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
GROUND_BAR_HEIGHT = 2
ARROWHEAD_LENGTH = 6
ARROWHEAD_SPREAD_RADIANS = math.radians(30)

HUD_MARGIN = 4
HUD_LINE_HEIGHT = 16
MOUSE_TEXT_OFFSET = 12
HUD_TEXT_COLOR: Color = (230, 230, 230)
BOUNDS_COLOR: Color = (255, 160, 0)
BOUNDS_DASH_LENGTH = 6
BOUNDS_DASH_GAP = 4
CROSSHAIR_COLOR: Color = (0, 255, 255)
CROSSHAIR_ARM_LENGTH = 6
GRAPH_WIDTH = 200
GRAPH_WINDOW_SECONDS = 2.0  # the graph's x-axis spans this much time
GRAPH_HEIGHT = 60
GRAPH_CEILING_MILLISECONDS = 50.0
GRAPH_BAR_COLOR: Color = (60, 200, 60)
SLOW_BAR_COLOR: Color = (255, 0, 0)
# A bar is red only when its frame took longer than the target frame time plus this much. Timer
# jitter puts many on-target frames a hair over (at 60.01 FPS most land just past 16.66 ms), so
# without it red would not mean a real hitch. The target line itself stays at the exact target.
SLOW_FRAME_TOLERANCE_MILLISECONDS = 1.0
TARGET_LINE_COLOR: Color = (255, 255, 0)
MILLISECONDS_PER_SECOND = 1000.0

# The Audio panel (sound engine impl spec 10.5): the audio-time graph shares the frame-time
# graph's place, size and x-axis; the rest stacks down the left side under the header
AUDIO_COMPILE_COLOR: Color = (230, 60, 60)
AUDIO_DECODE_COLOR: Color = (240, 150, 40)
AUDIO_LIVE_COLOR: Color = (70, 130, 240)
AUDIO_CACHE_COLOR: Color = (150, 150, 150)
# Stacked from the bottom of a bar upward, in this order; any other kind is drawn like a cache read
AUDIO_KIND_COLORS: dict[str, Color] = {
    'compile': AUDIO_COMPILE_COLOR,
    'decode': AUDIO_DECODE_COLOR,
    'live_chunk': AUDIO_LIVE_COLOR,
    'cache_read': AUDIO_CACHE_COLOR,
}
AUDIO_KIND_LEGEND: tuple[tuple[str, Color], ...] = (
    ('compile', AUDIO_COMPILE_COLOR),
    ('decode', AUDIO_DECODE_COLOR),
    ('live', AUDIO_LIVE_COLOR),
    ('cache', AUDIO_CACHE_COLOR),
)
AUDIO_FRAME_OUTLINE_COLOR: Color = (50, 50, 70)  # the frame's whole duration, behind its bar
AUDIO_CHANNEL_COLORS: dict[str, Color] = {
    'idle': (60, 60, 60),
    'playing': (80, 200, 100),
    'fading': (230, 200, 60),
    'paused': (120, 120, 200),
}
AUDIO_BUS_COLOR: Color = (90, 170, 210)
AUDIO_BUS_MUTED_COLOR: Color = (140, 60, 60)
AUDIO_PANEL_TOP = HUD_MARGIN + HUD_LINE_HEIGHT
# Under All panels only the header is drawn, below the camera panel's three possible lines
ALL_PANEL_AUDIO_HEADER_TOP = HUD_MARGIN + 4 * HUD_LINE_HEIGHT + HUD_MARGIN
AUDIO_HEADER_SCALE = 2  # the cache mode is drawn in type this many times larger
AUDIO_SECTION_GAP = 4
AUDIO_LABEL_WIDTH = 52
AUDIO_CELL_SIZE = 8
AUDIO_CELL_GAP = 1
AUDIO_ROW_HEIGHT = 12
AUDIO_BUS_BAR_WIDTH = 100  # a bus at gain 1.0
AUDIO_LEGEND_SWATCH_GAP = 3
AUDIO_LEGEND_ENTRY_WIDTH = 50


@dataclasses.dataclass(frozen=True)
class DebugFrameInfo:
    """Per-frame engine readings handed to the overlay.

    Attributes:
        target_fps (float): The engine's target FPS; 0 means uncapped.
        audio (AudioDiagnosticsSnapshot | None): The audio engine's readings, or None when the
            engine has not started (the overlay never starts it).
        rumble_levels (tuple[float, float]): Last (low, high) rumble levels sent.
        screen_shake_offset (tuple[float, float]): Current SCREEN shake offset.
        mouse_position (tuple[int, int] | None): Mouse position, or None.
        inspected_scene_label (str | None): Name of the scene being inspected when it is not
            the active scene (a paused game), named on the mode line; None otherwise.

    """

    target_fps: float
    audio: AudioDiagnosticsSnapshot | None
    rumble_levels: tuple[float, float]
    screen_shake_offset: tuple[float, float]
    mouse_position: tuple[int, int] | None
    inspected_scene_label: str | None = None


def screen_rect_for(*, sprite: object, screen_offset: tuple[int, int]) -> pygame.Rect:
    """Compute where a sprite's collision rect appears on the presented frame.

    Sprites with world_x and world_y have a world-space collision rect. Its box is placed
    where the sprite is actually drawn: the sprite's rect (which the engine, or a game, sets
    from the camera every frame, WORLD shake included, plus an anchored AnimatedSprite's
    draw_offset) less that draw_offset, plus the hitbox's offset from the snapped world
    position the collision rect was built from (which includes the draw_offset). Converting
    the already-rounded world rect through the camera would round twice and put the box a
    pixel off the sprite whenever the camera position is fractional. Other sprites already
    have screen-space rects.

    Args:
        sprite (object): The sprite to locate.
        screen_offset (tuple[int, int]): Extra offset applied to the whole frame (screen shake).

    Returns:
        pygame.Rect: A new rect in presented-frame coordinates.

    """
    collision_rect = get_sprite_collision_rect(sprite)
    screen_rect = collision_rect.copy()
    if is_world_rect_sprite(sprite):
        snapped_world_x, snapped_world_y = snapped_world_position(
            sprite, sprite.world_x, sprite.world_y
        )
        # An anchored AnimatedSprite's rect already includes its draw_offset (the FrameAnchor
        # contract: games place rect with it), and so does its collision rect, so take the
        # offset out once (sprites without one have (0, 0))
        draw_offset_x, draw_offset_y = getattr(sprite, 'draw_offset', (0, 0))
        screen_rect.topleft = (
            sprite.rect.x - draw_offset_x + collision_rect.x - snapped_world_x,
            sprite.rect.y - draw_offset_y + collision_rect.y - snapped_world_y,
        )
    screen_rect.move_ip(screen_offset)
    return screen_rect


def _layer_membership(*, collisions: CollisionManager) -> list[tuple[str, Color, list[Any]]]:
    """List each layer with its colour and sprites, in creation order.

    Returns:
        list[tuple[str, Color, list[Any]]]: Layer name, colour and sprites.

    """
    return [
        (name, LAYER_PALETTE[index % len(LAYER_PALETTE)], list(collisions.get_layer(name).sprites))
        for index, name in enumerate(collisions.layer_names)
    ]


def _overlapping_sprite_ids(*, layers: list[tuple[str, Color, list[Any]]]) -> set[int]:
    """Find sprites that overlap a sprite from a different layer.

    Overlap uses the same rects the collision manager uses (world rects for world sprites,
    screen rects for UI sprites), so it matches what collision checks would see. Each
    sprite's rect is computed once per layer, up front.

    Returns:
        set[int]: The id() of every sprite with a cross-layer overlap.

    """
    rects_per_layer = [
        {id(sprite): get_sprite_collision_rect(sprite) for sprite in layer_sprites}
        for _, _, layer_sprites in layers
    ]
    overlapping: set[int] = set()
    for first_index, first_rects in enumerate(rects_per_layer):
        for second_rects in rects_per_layer[first_index + 1 :]:
            for first_id, first_rect in first_rects.items():
                for second_id, second_rect in second_rects.items():
                    if first_id != second_id and first_rect.colliderect(second_rect):
                        overlapping.add(first_id)
                        overlapping.add(second_id)
    return overlapping


def draw_collision_panel(
    *,
    surface: pygame.Surface,
    scene: object,
    screen_offset: tuple[int, int],
    font: pygame.font.Font,
) -> None:
    """Draw hitbox outlines coloured by collision layer, plus a legend.

    Sprites in different layers that overlap are outlined in OVERLAP_COLOR. Sprites in the
    scene's all_sprites that belong to no layer have their full sprite.rect (not a trimmed
    collision rect) outlined in UNLAYERED_COLOR. A scene
    without a collision manager, or whose manager has no layers, draws nothing.

    Args:
        surface (pygame.Surface): The presented frame to draw onto.
        scene (object): The active scene (its `all_sprites` and `collisions` are optional).
        screen_offset (tuple[int, int]): Extra offset applied to the whole frame.
        font (pygame.font.Font): Font used for the legend.

    """
    collisions = getattr(scene, 'collisions', None)
    if collisions is None or not collisions.layer_names:
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
            outline_rect = screen_rect_for(sprite=sprite, screen_offset=screen_offset)
            pygame.draw.rect(surface, outline_color, outline_rect, width=1)

    for sprite in getattr(scene, 'all_sprites', ()):
        if id(sprite) in layered_ids:
            continue
        sprite_rect = getattr(sprite, 'rect', None)
        if sprite_rect is None:
            continue
        # Unlayered sprites never go through the collision manager, so their trimmed collision
        # rect means nothing; games that test them do so with the full rect (Clockwork Keep).
        outline_rect = pygame.Rect(sprite_rect).move(screen_offset)
        pygame.draw.rect(surface, UNLAYERED_COLOR, outline_rect, width=1)

    _draw_legend(surface=surface, layers=layers, font=font)


def _backing_surface(size: tuple[int, int]) -> pygame.Surface:
    """Return a translucent backing of the given size, reused instead of allocated per frame.

    Returns:
        pygame.Surface: An SRCALPHA surface filled with TEXT_BACKING_COLOR (do not draw on it).

    """
    backing = _BACKING_SURFACES.get(size)
    if backing is None:
        if len(_BACKING_SURFACES) >= BACKING_SURFACE_CACHE_LIMIT:
            _BACKING_SURFACES.clear()
        backing = pygame.Surface(size, pygame.SRCALPHA)
        backing.fill(TEXT_BACKING_COLOR)
        _BACKING_SURFACES[size] = backing
    return backing


def blit_text(
    *, surface: pygame.Surface, text_surface: pygame.Surface, position: tuple[int, int]
) -> None:
    """Blit rendered debug text over a translucent backing slightly larger than the text.

    The overlay's text helper, shared with the watched replay's status bar
    (glitchygames/replay/controls.py).
    """
    backing = _backing_surface((
        text_surface.get_width() + 2 * TEXT_BACKING_PADDING,
        text_surface.get_height() + 2 * TEXT_BACKING_PADDING,
    ))
    surface.blit(backing, (position[0] - TEXT_BACKING_PADDING, position[1] - TEXT_BACKING_PADDING))
    surface.blit(text_surface, position)


def _draw_legend(
    *, surface: pygame.Surface, layers: list[tuple[str, Color, list[Any]]], font: pygame.font.Font
) -> None:
    """Draw one legend row per layer along the bottom-left, last layer lowest."""
    row_bottom = surface.get_height() - LEGEND_MARGIN
    for name, layer_color, layer_sprites in reversed(layers):
        text_surface = font.render(
            f'{name}: {len(layer_sprites)}', antialias=FontManager.antialias(), color=layer_color
        )
        row_height = max(text_surface.get_height(), LEGEND_SWATCH_SIZE)
        row_top = row_bottom - row_height
        pygame.draw.rect(
            surface,
            layer_color,
            pygame.Rect(LEGEND_MARGIN, row_top, LEGEND_SWATCH_SIZE, LEGEND_SWATCH_SIZE),
        )
        blit_text(
            surface=surface,
            text_surface=text_surface,
            position=(LEGEND_MARGIN + LEGEND_SWATCH_SIZE + 4, row_top),
        )
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
    scene: object,
    screen_offset: tuple[int, int],
    font: pygame.font.Font,
) -> None:
    """Draw velocity arrows, ground state bars and velocity text for physics sprites.

    The arrow is the distance travelled in PHYSICS_ARROW_SECONDS, capped at
    PHYSICS_ARROW_MAXIMUM_PIXELS. The bar under the sprite is green when it is on the ground
    and red otherwise. Sprites without a physics body are skipped.

    Args:
        surface (pygame.Surface): The presented frame to draw onto.
        scene (object): The active scene (its `all_sprites` and `collisions` are optional).
        screen_offset (tuple[int, int]): Extra offset applied to the whole frame.
        font (pygame.font.Font): Font used for the velocity text.

    """
    for sprite in getattr(scene, 'all_sprites', ()):
        if not isinstance(sprite, HasPhysicsBody):
            continue
        body = sprite.physics
        sprite_rect = screen_rect_for(sprite=sprite, screen_offset=screen_offset)

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
        blit_text(
            surface=surface,
            text_surface=font.render(
                velocity_text, antialias=FontManager.antialias(), color=ARROW_COLOR
            ),
            position=(sprite_rect.right + 2, sprite_rect.top),
        )


def _draw_dashed_line(
    *, surface: pygame.Surface, start: tuple[int, int], end: tuple[int, int]
) -> None:
    """Draw a horizontal or vertical dashed line in BOUNDS_COLOR."""
    line_length = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
    direction_x = (end[0] > start[0]) - (end[0] < start[0])
    direction_y = (end[1] > start[1]) - (end[1] < start[1])
    for dash_start in range(0, line_length, BOUNDS_DASH_LENGTH + BOUNDS_DASH_GAP):
        dash_end = min(dash_start + BOUNDS_DASH_LENGTH, line_length)
        pygame.draw.line(
            surface,
            BOUNDS_COLOR,
            (start[0] + direction_x * dash_start, start[1] + direction_y * dash_start),
            (start[0] + direction_x * dash_end, start[1] + direction_y * dash_end),
        )


def _draw_bounds(
    *, surface: pygame.Surface, camera: Camera2D, screen_offset: tuple[int, int]
) -> None:
    """Draw dashed lines at each camera-bound world edge that is on the surface."""
    min_x, min_y, max_x, max_y = camera.bounds
    surface_width, surface_height = surface.get_size()
    # Right and bottom edges are exclusive (max + screen size), so with the camera clamped at its
    # maximum that coordinate lands one pixel off the surface. Draw the last world pixel instead.
    world_edges_x = (
        min_x,
        None if max_x is None else max_x + camera.screen_width - 1,
    )
    world_edges_y = (
        min_y,
        None if max_y is None else max_y + camera.screen_height - 1,
    )
    for world_edge_x in world_edges_x:
        if world_edge_x is None:
            continue
        line_x = camera.world_to_screen(world_edge_x, 0)[0] + screen_offset[0]
        if 0 <= line_x < surface_width:
            _draw_dashed_line(surface=surface, start=(line_x, 0), end=(line_x, surface_height))
    for world_edge_y in world_edges_y:
        if world_edge_y is None:
            continue
        line_y = camera.world_to_screen(0, world_edge_y)[1] + screen_offset[1]
        if 0 <= line_y < surface_height:
            _draw_dashed_line(surface=surface, start=(0, line_y), end=(surface_width, line_y))


def _draw_crosshair(
    *, surface: pygame.Surface, camera: Camera2D, screen_offset: tuple[int, int]
) -> None:
    """Draw the lead crosshair at (lead_x, lead_y) plus the screen offset."""
    center_x = round(camera.lead_x) + screen_offset[0]
    center_y = round(camera.lead_y) + screen_offset[1]
    pygame.draw.line(
        surface,
        CROSSHAIR_COLOR,
        (center_x - CROSSHAIR_ARM_LENGTH, center_y),
        (center_x + CROSSHAIR_ARM_LENGTH, center_y),
    )
    pygame.draw.line(
        surface,
        CROSSHAIR_COLOR,
        (center_x, center_y - CROSSHAIR_ARM_LENGTH),
        (center_x, center_y + CROSSHAIR_ARM_LENGTH),
    )


def draw_camera_panel(
    *,
    surface: pygame.Surface,
    camera: Camera2D,
    screen_offset: tuple[int, int],
    font: pygame.font.Font,
    frame_info: DebugFrameInfo,
) -> None:
    """Draw camera bounds, the lead crosshair and camera text readouts.

    `Camera2D.set_bounds` clamps the camera's top-left position, so the world's edges are
    left = min_x, top = min_y, right = max_x + screen_width - 1 and
    bottom = max_y + screen_height - 1 (the last world pixel, since the exclusive edge would
    land one pixel off the surface at the clamp).
    Those edges are drawn as dashed lines, and only when they fall on the surface. The camera
    is read through `world_to_screen`, which has no side effects (`apply` would mark the
    camera as used).

    Args:
        surface (pygame.Surface): The presented frame to draw onto.
        camera (Camera2D): The active camera.
        screen_offset (tuple[int, int]): Extra offset applied to the whole frame.
        font (pygame.font.Font): Font used for the text readouts.
        frame_info (DebugFrameInfo): Supplies the mouse position and SCREEN shake offset.

    """
    _draw_bounds(surface=surface, camera=camera, screen_offset=screen_offset)
    _draw_crosshair(surface=surface, camera=camera, screen_offset=screen_offset)

    lines = [f'camera: ({round(camera.world_x)}, {round(camera.world_y)})']
    world_shake_offset = camera.shake_effect.offset
    if world_shake_offset != (0.0, 0.0):
        lines.append(f'world shake: ({world_shake_offset[0]:.1f}, {world_shake_offset[1]:.1f})')
    screen_shake_offset = frame_info.screen_shake_offset
    if screen_shake_offset != (0.0, 0.0):
        lines.append(f'screen shake: ({screen_shake_offset[0]:.1f}, {screen_shake_offset[1]:.1f})')
    _draw_text_lines(surface=surface, font=font, lines=lines, top=HUD_MARGIN + HUD_LINE_HEIGHT)

    mouse_position = frame_info.mouse_position
    if mouse_position is not None:
        # Unshaken camera position plus the raw mouse position, drawn next to the cursor.
        mouse_world_x = round(camera.world_x) + mouse_position[0]
        mouse_world_y = round(camera.world_y) + mouse_position[1]
        mouse_text = font.render(
            f'mouse world: ({mouse_world_x}, {mouse_world_y})',
            antialias=FontManager.antialias(),
            color=HUD_TEXT_COLOR,
        )
        text_left = min(
            mouse_position[0] + MOUSE_TEXT_OFFSET, surface.get_width() - mouse_text.get_width()
        )
        text_top = min(
            mouse_position[1] + MOUSE_TEXT_OFFSET, surface.get_height() - mouse_text.get_height()
        )
        blit_text(surface=surface, text_surface=mouse_text, position=(text_left, text_top))


def _draw_text_lines(
    *,
    surface: pygame.Surface,
    font: pygame.font.Font,
    lines: list[str],
    top: int,
    right_aligned: bool = False,
) -> int:
    """Draw lines of HUD text one under another.

    Returns:
        int: The y coordinate just below the last line.

    """
    line_top = top
    for line in lines:
        text_surface = font.render(line, antialias=FontManager.antialias(), color=HUD_TEXT_COLOR)
        line_left = (
            surface.get_width() - HUD_MARGIN - text_surface.get_width()
            if right_aligned
            else HUD_MARGIN
        )
        blit_text(surface=surface, text_surface=text_surface, position=(line_left, line_top))
        line_top += HUD_LINE_HEIGHT
    return line_top


def _blit_backing(*, surface: pygame.Surface, rect: pygame.Rect) -> None:
    """Dim a rect with the translucent debug backing so its extent is visible."""
    surface.blit(_backing_surface(rect.size), rect.topleft)


def _frame_column_spans(*, frame_times: list[float]) -> Iterator[tuple[int, int, int]]:
    """Map frames onto the GRAPH_WIDTH columns of the graphs' shared time axis.

    The x-axis is time, newest at the right edge: each frame covers a width proportional to its
    duration, so a 50 ms hitch is three times as wide as a 16.7 ms frame and two seconds of
    frames always span the whole graph. The frame-time and audio-time graphs both use it.

    Args:
        frame_times: The frame durations inside the window, oldest first.

    Yields:
        (index into frame_times, first column, last column) for each frame, newest first.

    """
    pixels_per_second = GRAPH_WIDTH / GRAPH_WINDOW_SECONDS
    seconds_before_newest = 0.0
    for index in range(len(frame_times) - 1, -1, -1):
        frame_seconds = frame_times[index]
        right_edge = GRAPH_WIDTH - seconds_before_newest * pixels_per_second
        left_edge = right_edge - frame_seconds * pixels_per_second
        first_column = max(0, math.floor(left_edge))
        last_column = min(GRAPH_WIDTH - 1, math.ceil(right_edge) - 1)
        yield index, first_column, last_column
        seconds_before_newest += frame_seconds


def _slowest_frame_per_column(*, overlay: DebugOverlay) -> list[float | None]:
    """Map the last GRAPH_WINDOW_SECONDS of frames onto GRAPH_WIDTH columns of time.

    A column shows the slowest frame overlapping it, so a hitch is never hidden by a faster
    neighbour sharing its column.

    Returns:
        list[float | None]: Per column (left to right), the slowest frame time in seconds, or
            None where no recorded frame reaches (less than GRAPH_WINDOW_SECONDS of history).

    """
    columns: list[float | None] = [None] * GRAPH_WIDTH
    frame_times = overlay.graph_frame_times(window_seconds=GRAPH_WINDOW_SECONDS)
    for index, first_column, last_column in _frame_column_spans(frame_times=frame_times):
        frame_seconds = frame_times[index]
        for column in range(first_column, last_column + 1):
            slowest = columns[column]
            if slowest is None or frame_seconds > slowest:
                columns[column] = frame_seconds
    return columns


def _graph_rect(*, surface: pygame.Surface) -> pygame.Rect:
    """Locate the graph in the bottom-right corner (the Performance and Audio panels' graph).

    Returns:
        pygame.Rect: The graph's rect.

    """
    return pygame.Rect(
        surface.get_width() - HUD_MARGIN - GRAPH_WIDTH,
        surface.get_height() - HUD_MARGIN - GRAPH_HEIGHT - HUD_LINE_HEIGHT,
        GRAPH_WIDTH,
        GRAPH_HEIGHT,
    )


def _graph_scale(*, target_fps: float) -> tuple[float | None, float]:
    """Choose the graphs' vertical scale, so both draw the target frame time at the same height.

    Low targets (under 20 FPS) would put the line above the default ceiling, so the ceiling grows.

    Returns:
        tuple[float | None, float]: The target frame time in milliseconds (None when uncapped),
            and the pixels per millisecond.

    """
    target_milliseconds = MILLISECONDS_PER_SECOND / target_fps if target_fps > 0 else None
    ceiling_milliseconds = GRAPH_CEILING_MILLISECONDS
    if target_milliseconds is not None:
        ceiling_milliseconds = max(ceiling_milliseconds, 2 * target_milliseconds)
    return target_milliseconds, GRAPH_HEIGHT / ceiling_milliseconds


def _draw_frame_time_graph(
    *, surface: pygame.Surface, overlay: DebugOverlay, target_fps: float
) -> pygame.Rect:
    """Draw the frame-time bars and target line in the bottom-right corner.

    Returns:
        pygame.Rect: The graph's rect.

    """
    graph_rect = _graph_rect(surface=surface)
    target_milliseconds, pixels_per_millisecond = _graph_scale(target_fps=target_fps)

    _blit_backing(surface=surface, rect=graph_rect)
    for column, frame_seconds in enumerate(_slowest_frame_per_column(overlay=overlay)):
        if frame_seconds is None:
            continue
        frame_milliseconds = frame_seconds * MILLISECONDS_PER_SECOND
        bar_height = min(GRAPH_HEIGHT, max(1, round(frame_milliseconds * pixels_per_millisecond)))
        is_slow = (
            target_milliseconds is not None
            and frame_milliseconds > target_milliseconds + SLOW_FRAME_TOLERANCE_MILLISECONDS
        )
        bar_color = SLOW_BAR_COLOR if is_slow else GRAPH_BAR_COLOR
        bar_x = graph_rect.left + column
        pygame.draw.line(
            surface,
            bar_color,
            (bar_x, graph_rect.bottom - 1),
            (bar_x, graph_rect.bottom - bar_height),
        )
    if target_milliseconds is not None:
        line_y = graph_rect.bottom - 1 - round(target_milliseconds * pixels_per_millisecond)
        pygame.draw.line(
            surface, TARGET_LINE_COLOR, (graph_rect.left, line_y), (graph_rect.right - 1, line_y)
        )
    return graph_rect


def draw_performance_panel(
    *,
    surface: pygame.Surface,
    overlay: DebugOverlay,
    font: pygame.font.Font,
    frame_info: DebugFrameInfo,
) -> None:
    """Draw FPS text, the 1% low, optional audio/rumble lines and a frame-time graph.

    The panel sits in the top-right corner, with the graph in the bottom-right corner. Bars
    are red when the frame time exceeds the target frame time (1 / target FPS) by more than
    SLOW_FRAME_TOLERANCE_MILLISECONDS; the target line marks the exact target frame time. With
    no target (uncapped) there is no target line and no red bars.

    Args:
        surface (pygame.Surface): The presented frame to draw onto.
        overlay (DebugOverlay): The overlay holding the frame history.
        font (pygame.font.Font): Font used for the text.
        frame_info (DebugFrameInfo): Supplies the target FPS, audio readings and rumble levels.

    """
    target_fps = frame_info.target_fps
    audio = frame_info.audio
    rumble_levels = frame_info.rumble_levels
    current_fps = overlay.current_fps()
    one_percent_low = overlay.one_percent_low_fps()
    lines = [
        'FPS: n/a' if current_fps is None else f'FPS: {current_fps:.1f}',
        '1% low: n/a' if one_percent_low is None else f'1% low: {one_percent_low:.1f}',
        f'target: {target_fps:g}' if target_fps > 0 else 'target: uncapped',
    ]
    if current_fps is not None:
        # current_fps is 1 / the last frame time, so this avoids copying the whole history.
        lines.insert(1, f'frame: {MILLISECONDS_PER_SECOND / current_fps:.1f} ms')
    if audio is not None:
        lines.append(f'voices: {audio.voices_live}')
    if rumble_levels[0] > 0 or rumble_levels[1] > 0:
        lines.append(f'rumble: {rumble_levels[0]:.2f} / {rumble_levels[1]:.2f}')
    _draw_text_lines(
        surface=surface,
        font=font,
        lines=lines,
        top=HUD_MARGIN + HUD_LINE_HEIGHT,
        right_aligned=True,
    )

    graph_rect = _draw_frame_time_graph(surface=surface, overlay=overlay, target_fps=target_fps)
    footnote = font.render(
        'overlay drawing included', antialias=FontManager.antialias(), color=HUD_TEXT_COLOR
    )
    blit_text(
        surface=surface,
        text_surface=footnote,
        position=(graph_rect.right - footnote.get_width(), graph_rect.bottom + 2),
    )


def draw_audio_header(
    *, surface: pygame.Surface, font: pygame.font.Font, frame_info: DebugFrameInfo, top: int
) -> int:
    """Draw the Audio panel's header: the cache mode in large type, then the engine's readings.

    The cache mode is `CACHE: NONE` in compile red (every play compiles), `RAM` or `DISK` in the
    text colour. The lines under it are the mixer format and driver, the voices playing (live,
    library, legacy), the compiles in the last second and the cache hit rate. Without an audio
    engine (it has not started, and the overlay never starts it) the header is one line.

    Args:
        surface (pygame.Surface): The presented frame to draw onto.
        font (pygame.font.Font): Font used for the text.
        frame_info (DebugFrameInfo): Supplies the audio snapshot.
        top (int): The y coordinate of the header's first line.

    Returns:
        int: The y coordinate just below the header (the next line's top).

    """
    audio = frame_info.audio
    if audio is None:
        return _draw_text_lines(surface=surface, font=font, lines=['audio: not started'], top=top)

    cache_mode_color = AUDIO_COMPILE_COLOR if audio.cache_mode.value == 'none' else HUD_TEXT_COLOR
    cache_mode_text = font.render(
        f'CACHE: {audio.cache_mode.value.upper()}',
        antialias=FontManager.antialias(),
        color=cache_mode_color,
    )
    large_text = pygame.transform.scale_by(cache_mode_text, AUDIO_HEADER_SCALE)
    blit_text(surface=surface, text_surface=large_text, position=(HUD_MARGIN, top))
    hit_rate = 'n/a' if audio.cache_hit_rate is None else f'{audio.cache_hit_rate * 100:.1f}%'
    return _draw_text_lines(
        surface=surface,
        font=font,
        lines=[
            audio.device,
            (
                f'voices: live {audio.voices_live} / library {audio.voices_library}'
                f' / legacy {audio.voices_legacy}'
            ),
            f'compiles last second: {audio.compiles_last_second}',
            f'cache hit rate: {hit_rate}',
        ],
        top=top + large_text.get_height() + TEXT_BACKING_PADDING,
    )


def _draw_channel_strip(
    *,
    surface: pygame.Surface,
    font: pygame.font.Font,
    channels: tuple[ChannelState, ...],
    top: int,
) -> int:
    """Draw one cell per mixer channel, one labelled row per group, coloured by state.

    Returns:
        int: The y coordinate just below the strip.

    """
    row_top = top
    for group in ('live', 'library', 'legacy'):
        blit_text(
            surface=surface,
            text_surface=font.render(
                group, antialias=FontManager.antialias(), color=HUD_TEXT_COLOR
            ),
            position=(HUD_MARGIN, row_top),
        )
        cell_left = HUD_MARGIN + AUDIO_LABEL_WIDTH
        for channel in channels:
            if channel.group != group:
                continue
            pygame.draw.rect(
                surface,
                AUDIO_CHANNEL_COLORS[channel.state],
                pygame.Rect(cell_left, row_top, AUDIO_CELL_SIZE, AUDIO_CELL_SIZE),
            )
            cell_left += AUDIO_CELL_SIZE + AUDIO_CELL_GAP
        row_top += AUDIO_ROW_HEIGHT
    return row_top


def _draw_bus_meters(
    *,
    surface: pygame.Surface,
    font: pygame.font.Font,
    audio: AudioDiagnosticsSnapshot,
    top: int,
) -> int:
    """Draw one bar per bus: its estimated level (a gain of 1.0 fills the track), muted in red.

    Returns:
        int: The y coordinate just below the meters.

    """
    row_top = top
    for name, level in audio.bus_levels.items():
        is_muted = name in audio.muted_buses
        blit_text(
            surface=surface,
            text_surface=font.render(name, antialias=FontManager.antialias(), color=HUD_TEXT_COLOR),
            position=(HUD_MARGIN, row_top),
        )
        track_left = HUD_MARGIN + AUDIO_LABEL_WIDTH
        _blit_backing(
            surface=surface,
            rect=pygame.Rect(track_left, row_top, AUDIO_BUS_BAR_WIDTH, AUDIO_CELL_SIZE),
        )
        bar_width = round(min(max(level, 0.0), 1.0) * AUDIO_BUS_BAR_WIDTH)
        pygame.draw.rect(
            surface,
            AUDIO_BUS_MUTED_COLOR if is_muted else AUDIO_BUS_COLOR,
            pygame.Rect(track_left, row_top, bar_width, AUDIO_CELL_SIZE),
        )
        if is_muted:
            blit_text(
                surface=surface,
                text_surface=font.render(
                    'muted', antialias=FontManager.antialias(), color=HUD_TEXT_COLOR
                ),
                position=(track_left + AUDIO_BUS_BAR_WIDTH + HUD_MARGIN, row_top),
            )
        row_top += AUDIO_ROW_HEIGHT
    return row_top


def _draw_compile_log(
    *, surface: pygame.Surface, font: pygame.font.Font, audio: AudioDiagnosticsSnapshot, top: int
) -> None:
    """Draw the last compiles: frame, sound, milliseconds, and setup or gameplay (gameplay red)."""
    line_top = top
    for record in audio.compile_log:
        frame = '-' if record.frame_number is None else str(record.frame_number)
        phase = 'setup' if record.during_setup else 'gameplay'
        text_surface = font.render(
            f'{frame:>6}  {record.name}  {record.milliseconds:.1f} ms  {phase}',
            antialias=FontManager.antialias(),
            color=HUD_TEXT_COLOR if record.during_setup else AUDIO_COMPILE_COLOR,
        )
        blit_text(surface=surface, text_surface=text_surface, position=(HUD_MARGIN, line_top))
        line_top += HUD_LINE_HEIGHT


def _audio_frame_per_column(
    *, overlay: DebugOverlay
) -> list[tuple[float, Mapping[str, float]] | None]:
    """Map the graph window's frames onto the shared time axis, keeping each column's audio peak.

    A column shows the frame overlapping it with the most audio work (the slowest, among equals),
    so a compile spike is never hidden by a quiet neighbour sharing its column.

    Returns:
        Per column (left to right), the frame's duration and audio work, or None where no
            recorded frame reaches.

    """
    columns: list[tuple[float, Mapping[str, float]] | None] = [None] * GRAPH_WIDTH
    frame_times = overlay.graph_frame_times(window_seconds=GRAPH_WINDOW_SECONDS)
    audio_work = overlay.graph_audio_work(window_seconds=GRAPH_WINDOW_SECONDS)
    for index, first_column, last_column in _frame_column_spans(frame_times=frame_times):
        candidate = (frame_times[index], audio_work[index])
        candidate_rank = (sum(candidate[1].values()), candidate[0])
        for column in range(first_column, last_column + 1):
            current = columns[column]
            if current is None or candidate_rank > (sum(current[1].values()), current[0]):
                columns[column] = candidate
    return columns


def _kind_order(kind: str) -> int:
    """Rank a kind of audio work for stacking: known kinds in AUDIO_KIND_COLORS order, then others.

    Returns:
        int: The rank (lowest is drawn at the bottom of the bar).

    """
    known_kinds = list(AUDIO_KIND_COLORS)
    return known_kinds.index(kind) if kind in known_kinds else len(known_kinds)


def _draw_audio_time_graph(
    *, surface: pygame.Surface, overlay: DebugOverlay, font: pygame.font.Font, target_fps: float
) -> None:
    """Draw one bar per frame of audio work, stacked by kind, in the frame-time graph's place.

    Each frame's whole duration is a faint column behind its bar and the frame budget is a line,
    so the audio share of every frame is visible at a glance. A kind with any work is at least
    one pixel tall.
    """
    graph_rect = _graph_rect(surface=surface)
    target_milliseconds, pixels_per_millisecond = _graph_scale(target_fps=target_fps)
    _blit_backing(surface=surface, rect=graph_rect)
    for column, entry in enumerate(_audio_frame_per_column(overlay=overlay)):
        if entry is None:
            continue
        frame_seconds, work_by_kind = entry
        bar_x = graph_rect.left + column
        outline_height = min(
            GRAPH_HEIGHT,
            max(1, round(frame_seconds * MILLISECONDS_PER_SECOND * pixels_per_millisecond)),
        )
        pygame.draw.line(
            surface,
            AUDIO_FRAME_OUTLINE_COLOR,
            (bar_x, graph_rect.bottom - 1),
            (bar_x, graph_rect.bottom - outline_height),
        )
        segment_bottom = graph_rect.bottom - 1
        for kind in sorted(work_by_kind, key=_kind_order):
            if work_by_kind[kind] <= 0.0 or segment_bottom < graph_rect.top:
                continue
            segment_height = max(
                1, round(work_by_kind[kind] * MILLISECONDS_PER_SECOND * pixels_per_millisecond)
            )
            segment_top = max(graph_rect.top, segment_bottom - segment_height + 1)
            pygame.draw.line(
                surface,
                AUDIO_KIND_COLORS.get(kind, AUDIO_CACHE_COLOR),
                (bar_x, segment_bottom),
                (bar_x, segment_top),
            )
            segment_bottom = segment_top - 1
    if target_milliseconds is not None:
        line_y = graph_rect.bottom - 1 - round(target_milliseconds * pixels_per_millisecond)
        pygame.draw.line(
            surface, TARGET_LINE_COLOR, (graph_rect.left, line_y), (graph_rect.right - 1, line_y)
        )
    _draw_audio_graph_legend(surface=surface, font=font, graph_rect=graph_rect)


def _draw_audio_graph_legend(
    *, surface: pygame.Surface, font: pygame.font.Font, graph_rect: pygame.Rect
) -> None:
    """Name the four kinds of audio work above the graph, each beside its colour swatch."""
    entry_left = graph_rect.left
    # Above the graph, clear of the text backing's padding, which would dim the graph's top row
    entry_top = graph_rect.top - HUD_LINE_HEIGHT - TEXT_BACKING_PADDING
    for label, color in AUDIO_KIND_LEGEND:
        pygame.draw.rect(
            surface, color, pygame.Rect(entry_left, entry_top + 2, AUDIO_CELL_SIZE, AUDIO_CELL_SIZE)
        )
        blit_text(
            surface=surface,
            text_surface=font.render(label, antialias=FontManager.antialias(), color=color),
            position=(entry_left + AUDIO_CELL_SIZE + AUDIO_LEGEND_SWATCH_GAP, entry_top),
        )
        entry_left += AUDIO_LEGEND_ENTRY_WIDTH


def draw_audio_panel(
    *,
    surface: pygame.Surface,
    overlay: DebugOverlay,
    font: pygame.font.Font,
    frame_info: DebugFrameInfo,
) -> None:
    """Draw the Audio panel: header, channel strip, bus meters, compile log and audio-time graph.

    The header, strip, meters and log stack down the left side; the graph sits where the
    Performance panel's frame-time graph does, over the same time window. Without an audio engine
    only the header's one line is drawn.

    Args:
        surface (pygame.Surface): The presented frame to draw onto.
        overlay (DebugOverlay): The overlay holding the frame and audio-work history.
        font (pygame.font.Font): Font used for the text.
        frame_info (DebugFrameInfo): Supplies the audio snapshot and the target FPS.

    """
    next_top = draw_audio_header(
        surface=surface, font=font, frame_info=frame_info, top=AUDIO_PANEL_TOP
    )
    audio = frame_info.audio
    if audio is None:
        return
    next_top = _draw_channel_strip(
        surface=surface, font=font, channels=audio.channels, top=next_top + AUDIO_SECTION_GAP
    )
    next_top = _draw_bus_meters(
        surface=surface, font=font, audio=audio, top=next_top + AUDIO_SECTION_GAP
    )
    _draw_compile_log(surface=surface, font=font, audio=audio, top=next_top + AUDIO_SECTION_GAP)
    _draw_audio_time_graph(
        surface=surface, overlay=overlay, font=font, target_fps=frame_info.target_fps
    )


def draw_mode_line(
    *,
    surface: pygame.Surface,
    font: pygame.font.Font,
    panel: DebugPanel,
    inspected_scene_label: str | None = None,
) -> None:
    """Draw the mode line at the top centre of the surface.

    Args:
        surface (pygame.Surface): The presented frame to draw onto.
        font (pygame.font.Font): Font used for the text.
        panel (DebugPanel): The selected panel, named in the text.
        inspected_scene_label (str | None): The paused scene being shown, if any.

    """
    mode_text = f'DEBUG: {panel.value.capitalize()} (F3 off, F4 next)'
    if inspected_scene_label is not None:
        mode_text += f' | paused: {inspected_scene_label}'
    text_surface = font.render(
        mode_text,
        antialias=FontManager.antialias(),
        color=HUD_TEXT_COLOR,
    )
    blit_text(
        surface=surface,
        text_surface=text_surface,
        position=((surface.get_width() - text_surface.get_width()) // 2, TEXT_BACKING_PADDING),
    )
