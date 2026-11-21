"""The full-repaint comparison (glitchygames/testing/full_repaint.py) on a real scene manager.

Each test renders a real scene through ``SceneManager._render_scene`` onto the real display and
plants the defect the comparison exists for: a sprite changed without being marked dirty. The
scene's own ``dirty`` flag is cleared after the first frame, since while it is set
``Scene.update`` marks every sprite dirty and hides any missed mark.
"""

from __future__ import annotations

import pygame
import pytest

from glitchygames.effects.shake import Shake, ShakeStyle
from glitchygames.scenes import Scene, SceneManager
from glitchygames.scenes import scene as scene_module
from glitchygames.testing.full_repaint import (
    KEPT_MISMATCHES,
    NAMED_SPRITES,
    RENDER_METHOD,
    FullRepaintMismatchError,
    compare_each_frame_with_a_full_repaint,
    differing_area,
)

BACKGROUND = (10, 20, 30)
SPRITE_COLOR = (0, 200, 0)
CHANGED_COLOR = (200, 0, 200)
SPRITE_RECT = (100, 100, 20, 10)
# A strip the scene draws straight onto the screen, outside its sprites (a score)
STRAIGHT_DRAWN_AREA = pygame.Rect(0, 0, 50, 8)


class SolidSprite(pygame.sprite.DirtySprite):
    """A dirty sprite of one color (``Scene.update`` calls ``update_nested_sprites``)."""

    def update_nested_sprites(self) -> None:
        """Update no nested sprites (this sprite has none)."""


class SpriteScene(Scene):
    """A scene with one solid sprite on a plain background."""

    def __init__(self) -> None:
        """Make the scene and its sprite."""
        super().__init__()
        self.background_color = BACKGROUND
        self.sprite = SolidSprite()
        self.sprite.image = pygame.Surface(SPRITE_RECT[2:])
        self.sprite.image.fill(SPRITE_COLOR)
        self.sprite.rect = pygame.Rect(SPRITE_RECT)
        self.all_sprites.add(self.sprite)


class WholeScreenScene(SpriteScene):
    """Presents the whole screen every frame (``rects = None``), as the parallax games do."""

    def render(self, screen: pygame.Surface) -> None:
        """Draw through the group, then present the whole screen."""
        super().render(screen)
        self.rects = None


class StraightDrawingScene(SpriteScene):
    """Draws a strip straight onto the screen after its sprites."""

    def render(self, screen: pygame.Surface) -> None:
        """Draw through the group, then the strip."""
        super().render(screen)
        screen.fill(CHANGED_COLOR, STRAIGHT_DRAWN_AREA)


@pytest.fixture
def manager():
    """Return a fresh scene manager drawing on the real display.

    Yields:
        The scene manager.

    """
    SceneManager._reset()
    scene_manager = SceneManager()
    scene_manager.screen = pygame.display.get_surface()
    yield scene_manager
    SceneManager._reset()


def show(manager: SceneManager, scene: Scene) -> None:
    """Make ``scene`` active and render its first frame, then clear its scene-wide dirty flag."""
    manager.active_scene = scene
    manager.frame_number = 0
    getattr(manager, RENDER_METHOD)()
    scene.dirty = 0


def render_next(manager: SceneManager) -> None:
    """Render the next frame."""
    manager.frame_number += 1
    getattr(manager, RENDER_METHOD)()


def change_without_marking(scene: SpriteScene) -> None:
    """Plant the defect: repaint the sprite's picture and leave it marked clean."""
    scene.sprite.image.fill(CHANGED_COLOR)
    scene.sprite.dirty = 0


class TestComparison:
    """Every frame is compared with its full repaint and counted."""

    def test_frames_drawn_by_dirty_rects_match_and_are_counted(self, manager):
        scene = SpriteScene()
        with compare_each_frame_with_a_full_repaint() as comparison:
            show(manager, scene)
            render_next(manager)

        assert comparison.compared == 2
        assert comparison.mismatch_count == 0

    def test_a_sprite_changed_without_a_dirty_mark_fails_naming_its_frame_and_sprite(self, manager):
        scene = SpriteScene()
        with compare_each_frame_with_a_full_repaint():
            show(manager, scene)
            change_without_marking(scene)
            with pytest.raises(FullRepaintMismatchError) as mismatch:
                render_next(manager)

        message = str(mismatch.value)
        assert message.startswith('SpriteScene frame 1 differs from a full repaint in ')
        assert str(tuple(SPRITE_RECT)) in message
        assert f'1 sprites over it: SolidSprite(dirty=0, visible=1, rect={SPRITE_RECT})' in message

    def test_the_same_change_marked_dirty_matches(self, manager):
        scene = SpriteScene()
        with compare_each_frame_with_a_full_repaint() as comparison:
            show(manager, scene)
            scene.sprite.image.fill(CHANGED_COLOR)
            scene.sprite.dirty = 1
            render_next(manager)

        assert comparison.mismatch_count == 0

    def test_a_scene_presenting_the_whole_screen_is_still_compared(self, manager):
        """``rects = None`` decides the present, not the drawing: a missed mark still fails."""
        scene = WholeScreenScene()
        with compare_each_frame_with_a_full_repaint(raise_on_mismatch=False) as comparison:
            show(manager, scene)
            change_without_marking(scene)
            render_next(manager)

        assert comparison.whole_screen_frames == 2
        assert comparison.compared == 2
        assert comparison.mismatch_count == 1


class TestWhatIsLeftOut:
    """A hidden sprite is not in the repaint; a frame with no scene is not compared."""

    def test_a_hidden_sprite_is_not_repainted(self, manager):
        scene = SpriteScene()
        with compare_each_frame_with_a_full_repaint() as comparison:
            show(manager, scene)
            scene.sprite.visible = 0
            render_next(manager)

        assert comparison.mismatch_count == 0
        assert comparison.compared == 2

    def test_a_frame_with_no_active_scene_is_not_compared(self, manager):
        with compare_each_frame_with_a_full_repaint() as comparison:
            manager.active_scene = None
            comparison.check(manager=manager)

        assert comparison.compared == 0


class TestExcludedAreas:
    """What a scene draws outside its sprites is named, masked on both sides, and counted."""

    def test_straight_drawing_differs_from_a_full_repaint(self, manager):
        with compare_each_frame_with_a_full_repaint(raise_on_mismatch=False) as comparison:
            show(manager, StraightDrawingScene())

        assert comparison.mismatch_count == 1
        assert str(tuple(STRAIGHT_DRAWN_AREA)) in comparison.mismatches[0]
        assert 'no sprite (the background)' in comparison.mismatches[0]

    def test_an_excluded_area_is_left_out_and_counted(self, manager):
        with compare_each_frame_with_a_full_repaint(
            excluded_areas_of=lambda scene: [STRAIGHT_DRAWN_AREA]
        ) as comparison:
            show(manager, StraightDrawingScene())
            render_next(manager)

        assert comparison.frames_with_excluded_areas == 2
        assert comparison.mismatch_count == 0

    def test_a_missed_mark_outside_the_excluded_area_still_fails(self, manager):
        scene = StraightDrawingScene()
        with compare_each_frame_with_a_full_repaint(
            excluded_areas_of=lambda scene: [STRAIGHT_DRAWN_AREA]
        ):
            show(manager, scene)
            change_without_marking(scene)
            with pytest.raises(FullRepaintMismatchError):
                render_next(manager)


class TestCounts:
    """The counts a case asserts, so it cannot pass without reaching its hazard."""

    def test_a_frame_after_a_gap_is_counted(self, manager):
        """The scene drew no frame just before (a pause, a transition, another scene)."""
        with compare_each_frame_with_a_full_repaint() as comparison:
            show(manager, SpriteScene())
            manager.frame_number += 30
            getattr(manager, RENDER_METHOD)()
            render_next(manager)

        assert comparison.after_a_gap == 1

    def test_a_frame_during_a_screen_shake_is_counted(self, manager):
        """A SCREEN shake's offset is applied to a copy at present; the frame is still compared."""
        with compare_each_frame_with_a_full_repaint() as comparison:
            show(manager, SpriteScene())
            manager.screen_shake.add(
                Shake(style=ShakeStyle.BOUNCE, strength=6.0, duration=1.0, frequency=20.0)
            )
            manager.screen_shake.update(0.01)
            render_next(manager)

        assert comparison.shaken == 1
        assert comparison.mismatch_count == 0

    def test_named_buckets_count_the_frames_they_match(self, manager):
        with compare_each_frame_with_a_full_repaint(
            buckets={'second frame on': lambda scene: scene.scene_manager.frame_number >= 1}
        ) as comparison:
            show(manager, SpriteScene())
            render_next(manager)
            render_next(manager)

        assert comparison.bucket_counts == {'second frame on': 2}
        assert comparison.counts()['buckets'] == {'second frame on': 2}

    def test_collecting_keeps_the_first_mismatches_and_counts_them_all(self, manager):
        scene = SpriteScene()
        frames = KEPT_MISMATCHES + 5
        with compare_each_frame_with_a_full_repaint(raise_on_mismatch=False) as comparison:
            show(manager, scene)
            change_without_marking(scene)
            for _ in range(frames):
                render_next(manager)

        assert comparison.mismatch_count == frames
        assert len(comparison.mismatches) == KEPT_MISMATCHES
        assert comparison.mismatches[0].startswith('SpriteScene frame 1 ')


def test_the_render_step_is_restored_after_the_block():
    """The block ends with SceneManager's own render step back in place."""
    original = getattr(scene_module.SceneManager, RENDER_METHOD)
    with compare_each_frame_with_a_full_repaint():
        assert getattr(scene_module.SceneManager, RENDER_METHOD) is not original

    assert getattr(scene_module.SceneManager, RENDER_METHOD) is original


def test_differing_area_bounds_every_differing_pixel():
    """The rectangle reaches from the first differing pixel to the last; equal is None."""
    drawn = pygame.Surface((16, 12))
    repainted = drawn.copy()
    drawn.set_at((3, 2), (255, 0, 0))
    drawn.set_at((9, 7), (255, 0, 0))

    assert differing_area(drawn=drawn, repainted=repainted) == pygame.Rect(3, 2, 7, 6)
    assert differing_area(drawn=repainted, repainted=repainted.copy()) is None


def test_many_sprites_over_a_difference_are_grouped_by_class(manager):
    """Past ``NAMED_SPRITES``, the sprites over the area are counted by class, not listed."""
    scene = SpriteScene()
    extras = []
    for _ in range(NAMED_SPRITES):
        extra = SolidSprite()
        extra.image = pygame.Surface(SPRITE_RECT[2:])
        extra.image.fill(SPRITE_COLOR)
        extra.rect = pygame.Rect(SPRITE_RECT)
        # Visible, under the changed sprite: a hidden sprite would stay dirty in LayeredDirty
        # (its flag is cleared only when drawn) and redraw the area every frame
        scene.all_sprites.add(extra, layer=-1)
        extras.append(extra)
    with compare_each_frame_with_a_full_repaint(raise_on_mismatch=False) as comparison:
        show(manager, scene)
        # The group's first draw repaints everything and leaves every flag as it was
        for extra in extras:
            extra.dirty = 0
        change_without_marking(scene)
        render_next(manager)

    description = comparison.mismatches[0]
    assert f'{NAMED_SPRITES + 1} sprites over it: SolidSprite x{NAMED_SPRITES + 1} ' in description
    assert f'(dirty: 0, visible: {NAMED_SPRITES + 1})' in description
