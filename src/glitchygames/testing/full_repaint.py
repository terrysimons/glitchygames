"""Check every frame a scene draws against a full repaint of the same frame.

Dirty-rect drawing (``pygame.sprite.LayeredDirty``) redraws only the sprites marked dirty and the
background under where they were. A sprite whose picture, place or visibility changes without
being marked leaves the screen showing its old state. This compares each rendered frame with a
full repaint: the frame's background copied, then every visible sprite blitted over it in layer
order with its own ``image``, ``rect``, ``source_rect`` and ``blendmode``. The repaint never uses
the group's own bookkeeping (no ``repaint_rect``, no second ``draw``), so a bookkeeping bug cannot
hide on both sides.

It wraps ``SceneManager._render_scene`` (after ``Scene.update`` and the scene's ``render``,
before the present, whose overlays and shake work on a copy), so every scene is covered, whether
or not it overrides ``render``. Every frame is compared, a scene presenting the whole screen
(``rects = None``) too: ``rects`` decide what is presented, not how the surface was drawn. What a
scene draws outside its sprites (a score blitted straight onto the screen) is named per scene
(``excluded_areas_of``) and left out on both sides, and counted, so it stays visible. Pixels are
compared as RGB: the present makes the display opaque (``glitchygames.opacity``), so alpha never
shows.

Counts make a case prove it reached its hazard: frames compared, frames presented whole, frames
with excluded areas, frames during a SCREEN shake, frames after a gap (the scene drew no frame
just before: after a pause, a transition or another scene), and any named ``buckets`` a game adds
(Mr. Muncher: frames on its flashing maze).

Used by the sweep over every golden and bundled demo (tests/replay/) and by games' own cases:
one helper shared with Mr. Muncher's dirty-sprite work (the coordinator, 2026-11-21).
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Self

import pygame

from glitchygames.scenes import scene as scene_module

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping, Sequence

    from glitchygames.scenes import Scene, SceneManager

# The most mismatches a collecting comparison keeps (the first ones: later frames usually repeat)
KEPT_MISMATCHES = 20
# What an excluded area is filled with on both sides before comparing
EXCLUDED_FILL = (0, 0, 0)
# The wrapped SceneManager method: the frame's update and render (scenes/scene.py)
RENDER_METHOD = '_render_scene'


class FullRepaintMismatchError(AssertionError):
    """A frame differs from its full repaint."""


def no_excluded_areas(scene: Scene) -> list[pygame.Rect]:  # ruff: ignore[unused-function-argument] - the getter's signature
    """Exclude nothing: every pixel of every frame is compared.

    Returns:
        No areas.

    """
    return []


def default_background(scene: Scene) -> pygame.Surface:
    """Return the background a scene's frame shows: ``scene.background``.

    Returns:
        The background surface.

    """
    return scene.background


def full_repaint(*, scene: Scene, background: pygame.Surface) -> pygame.Surface:
    """Draw the scene's frame again from nothing: its background, then every visible sprite.

    Args:
        scene: The scene.
        background: The background its frame shows.

    Returns:
        The repainted frame.

    """
    repainted = background.copy()
    for sprite in scene.all_sprites.sprites():
        if sprite.visible:
            repainted.blit(sprite.image, sprite.rect, sprite.source_rect, sprite.blendmode)
    return repainted


def differing_area(*, drawn: pygame.Surface, repainted: pygame.Surface) -> pygame.Rect | None:
    """Return the rectangle bounding every pixel where two same-sized surfaces differ in RGB.

    Args:
        drawn: The frame as drawn.
        repainted: Its full repaint.

    Returns:
        The bounding rectangle, or None when they are equal.

    """
    width, height = drawn.get_size()
    drawn_bytes = pygame.image.tobytes(drawn, 'RGB')
    repainted_bytes = pygame.image.tobytes(repainted, 'RGB')
    if drawn_bytes == repainted_bytes:
        return None
    stride = width * 3
    left, right, top, bottom = width, -1, height, -1
    for row in range(height):
        start = row * stride
        drawn_row = drawn_bytes[start : start + stride]
        repainted_row = repainted_bytes[start : start + stride]
        if drawn_row == repainted_row:
            continue
        top = min(top, row)
        bottom = max(bottom, row)
        columns = [
            column
            for column in range(width)
            if drawn_row[column * 3 : column * 3 + 3] != repainted_row[column * 3 : column * 3 + 3]
        ]
        left = min(left, columns[0])
        right = max(right, columns[-1])
    return pygame.Rect(left, top, right - left + 1, bottom - top + 1)


def describe_mismatch(*, scene: Scene, frame_number: int, area: pygame.Rect) -> str:
    """Describe a differing frame: the scene, the frame, the area and the sprites over it.

    Args:
        scene: The scene.
        frame_number: The scene manager's frame number.
        area: The rectangle bounding the differing pixels.

    Returns:
        One line.

    """
    over = [
        f'{type(sprite).__name__}(dirty={sprite.dirty}, visible={sprite.visible})'
        for sprite in scene.all_sprites.sprites()
        if sprite.rect is not None and sprite.rect.colliderect(area)
    ]
    sprites = ', '.join(over) if over else 'no sprite (the background)'
    return (
        f'{type(scene).__name__} frame {frame_number} differs from a full repaint in '
        f'{tuple(area)}; sprites over it: {sprites}'
    )


class FullRepaintComparison:
    """What a comparison saw: its counts and, when collecting, its mismatches."""

    def __init__(
        self: Self,
        *,
        background_of: Callable[[Scene], pygame.Surface],
        excluded_areas_of: Callable[[Scene], Sequence[pygame.Rect]],
        buckets: Mapping[str, Callable[[Scene], bool]],
        raise_on_mismatch: bool,
    ) -> None:
        """Start with nothing counted.

        Args:
            background_of: The background a scene's frame shows.
            excluded_areas_of: The areas of a scene's frame drawn outside its sprites (a score
                drawn straight onto the screen), left out of the comparison on both sides.
            buckets: Named tests of a scene; each frame passing one is counted under its name.
            raise_on_mismatch: True to raise ``FullRepaintMismatchError`` at the first
                differing frame; False to keep the first ``KEPT_MISMATCHES`` in ``mismatches``.

        """
        self.background_of = background_of
        self.excluded_areas_of = excluded_areas_of
        self.buckets = dict(buckets)
        self.raise_on_mismatch = raise_on_mismatch
        self.compared = 0
        self.whole_screen_frames = 0
        self.frames_with_excluded_areas = 0
        self.shaken = 0
        self.after_a_gap = 0
        self.bucket_counts = dict.fromkeys(self.buckets, 0)
        self.mismatch_count = 0
        self.mismatches: list[str] = []
        self._last_frame_by_scene: dict[int, int] = {}

    def check(self: Self, *, manager: SceneManager) -> None:
        """Compare the frame just rendered with its full repaint, and count it.

        Args:
            manager: The scene manager that rendered it.

        Raises:
            FullRepaintMismatchError: If the frame differs and ``raise_on_mismatch`` is set.

        """
        scene = manager.active_scene
        screen = manager.screen
        if scene is None or screen is None:
            return
        self._count(manager=manager, scene=scene)
        drawn, repainted = self._both_sides(scene=scene, screen=screen)
        area = differing_area(drawn=drawn, repainted=repainted)
        if area is None:
            return
        self.mismatch_count += 1
        description = describe_mismatch(scene=scene, frame_number=manager.frame_number, area=area)
        if self.raise_on_mismatch:
            raise FullRepaintMismatchError(description)
        if len(self.mismatches) < KEPT_MISMATCHES:
            self.mismatches.append(description)

    def _count(self: Self, *, manager: SceneManager, scene: Scene) -> None:
        """Count a compared frame in every count it belongs to."""
        frame_number = manager.frame_number
        last_frame = self._last_frame_by_scene.get(id(scene))
        self._last_frame_by_scene[id(scene)] = frame_number
        self.compared += 1
        # A scene presenting the whole screen still draws its sprites through the group, so it
        # is compared like any other: rects decide the present, not the drawing
        if scene.rects is None:
            self.whole_screen_frames += 1
        if manager.screen_shake.offset != (0, 0):
            self.shaken += 1
        if last_frame is not None and frame_number != last_frame + 1:
            self.after_a_gap += 1
        for name, test in self.buckets.items():
            if test(scene):
                self.bucket_counts[name] += 1

    def _both_sides(
        self: Self, *, scene: Scene, screen: pygame.Surface
    ) -> tuple[pygame.Surface, pygame.Surface]:
        """Return the frame as drawn and its full repaint, each with the excluded areas filled.

        Returns:
            The drawn frame (the screen itself when nothing is excluded) and the repaint.

        """
        repainted = full_repaint(scene=scene, background=self.background_of(scene))
        excluded_areas = list(self.excluded_areas_of(scene))
        if not excluded_areas:
            return screen, repainted
        self.frames_with_excluded_areas += 1
        drawn = screen.copy()
        for area in excluded_areas:
            drawn.fill(EXCLUDED_FILL, area)
            repainted.fill(EXCLUDED_FILL, area)
        return drawn, repainted

    def counts(self: Self) -> dict[str, Any]:
        """Return the counts, for a report.

        Returns:
            Each count by name, the buckets under ``buckets``.

        """
        return {
            'compared': self.compared,
            'whole_screen_frames': self.whole_screen_frames,
            'frames_with_excluded_areas': self.frames_with_excluded_areas,
            'shaken': self.shaken,
            'after_a_gap': self.after_a_gap,
            'buckets': dict(self.bucket_counts),
            'mismatch_count': self.mismatch_count,
        }


@contextlib.contextmanager
def compare_each_frame_with_a_full_repaint(
    *,
    background_of: Callable[[Scene], pygame.Surface] = default_background,
    excluded_areas_of: Callable[[Scene], Sequence[pygame.Rect]] = no_excluded_areas,
    buckets: Mapping[str, Callable[[Scene], bool]] | None = None,
    raise_on_mismatch: bool = True,
) -> Generator[FullRepaintComparison]:
    """Compare every frame any scene renders with its full repaint while the block runs.

    Args:
        background_of: The background a scene's frame shows (a game that swaps backgrounds
            passes its own getter).
        excluded_areas_of: The areas a scene draws outside its sprites, left out of the
            comparison (``frames_with_excluded_areas`` counts the frames that had any).
        buckets: Named tests of a scene, each counted (``FullRepaintComparison.bucket_counts``).
        raise_on_mismatch: True (the default) raises at the first differing frame; False keeps
            the first ones in ``mismatches`` and counts them all.

    Yields:
        The comparison, whose counts a test asserts so it cannot pass vacuously.

    """
    comparison = FullRepaintComparison(
        background_of=background_of,
        excluded_areas_of=excluded_areas_of,
        buckets=buckets or {},
        raise_on_mismatch=raise_on_mismatch,
    )
    manager_class = scene_module.SceneManager
    original: Callable[[SceneManager], None] = getattr(manager_class, RENDER_METHOD)

    def render_and_compare(manager: SceneManager) -> None:
        original(manager)
        comparison.check(manager=manager)

    setattr(manager_class, RENDER_METHOD, render_and_compare)
    try:
        yield comparison
    finally:
        setattr(manager_class, RENDER_METHOD, original)
