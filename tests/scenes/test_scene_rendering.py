"""Test scene rendering functionality on the real display.

This module tests scene rendering including:
- Scene rendering and drawing
- Render surface management
- Rendering order and layering
- Scene visibility and rendering
- Render state management

Every test draws for real: onto the display conftest opens (800x600) or onto real surfaces.
Colors are compared as RGB only, because the display's pixel format differs by driver (cocoa's
has per-pixel alpha, dummy's and x11's do not).
"""

import pygame
import pytest

from glitchygames.backgrounds import BackgroundPattern, background_pattern_surface
from glitchygames.opacity import OPAQUE, has_per_pixel_alpha
from glitchygames.scenes import Scene, SceneManager

SCREEN_SIZE = (800, 600)
BACKGROUND = (10, 20, 30)
OTHER_BACKGROUND = (0, 0, 99)
SPRITE_COLOR = (0, 255, 0)
TOP_SPRITE_COLOR = (255, 0, 255)
MARKER_COLOR = (250, 250, 0)
TRANSLUCENT_SPRITE_COLOR = (80, 220, 120)
TRANSLUCENT_SPRITE_ALPHA = 137


def _rgb_at(surface: pygame.Surface, position: tuple[int, int]) -> tuple[int, int, int]:
    """Return the RGB of one pixel (alpha left out: it depends on the display's format).

    Returns:
        tuple[int, int, int]: The pixel's red, green and blue.

    """
    color = surface.get_at(position)
    return (color.r, color.g, color.b)


def _count_rgb(surface: pygame.Surface, color: tuple[int, int, int]) -> int:
    """Count the pixels of the surface whose RGB is exactly color, in one bulk call.

    Returns:
        int: How many pixels match.

    """
    return pygame.transform.threshold(
        None, surface, search_color=color, threshold=(0, 0, 0, 255), set_behavior=0
    )


class SolidSprite(pygame.sprite.DirtySprite):
    """A real dirty sprite of one color.

    Scene.update() calls update_nested_sprites() on every sprite, as glitchygames sprites
    have it; this one has no nested sprites.
    """

    def update_nested_sprites(self):
        """Update no nested sprites (this sprite has none)."""


def _solid_sprite(
    *, color: tuple[int, int, int], rect: tuple[int, int, int, int], layer: int = 0
) -> SolidSprite:
    """Return a real dirty sprite whose image is a solid color.

    Returns:
        SolidSprite: The sprite, dirty so it is drawn on the next render.

    """
    sprite = SolidSprite()
    sprite.image = pygame.Surface(rect[2:])
    sprite.image.fill(color)
    sprite.rect = pygame.Rect(rect)
    sprite._layer = layer
    sprite.dirty = 1
    return sprite


def _scene_with_background(color: tuple[int, int, int]) -> Scene:
    """Return a real scene whose background is the given color.

    Returns:
        Scene: The scene.

    """
    scene = Scene()
    scene.background_color = color
    return scene


@pytest.fixture
def display():
    """Return the real display, filled with a color no test draws, so stale pixels show.

    Returns:
        pygame.Surface: The display surface.

    """
    surface = pygame.display.get_surface()
    assert surface is not None
    assert surface.get_size() == SCREEN_SIZE
    surface.fill((123, 45, 67))
    return surface


class TestSceneRendering:
    """Test scene rendering functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()
        self.scene_manager = SceneManager()

    def teardown_method(self):
        """Clean up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()

    def test_scene_rendering(self, display):
        """The first render paints the scene's background over the whole display."""
        scene = _scene_with_background(BACKGROUND)

        scene.render(display)

        assert _count_rgb(display, BACKGROUND) == SCREEN_SIZE[0] * SCREEN_SIZE[1]
        # The first draw of a group reports the whole screen as changed
        assert scene.rects == [pygame.Rect((0, 0), SCREEN_SIZE)]

    def test_scene_rendering_with_surface(self, display):
        """A scene renders onto any surface it is given, leaving the display alone."""
        scene = _scene_with_background(BACKGROUND)
        scene.all_sprites.add(_solid_sprite(color=SPRITE_COLOR, rect=(100, 100, 20, 30)))
        offscreen = pygame.Surface(SCREEN_SIZE)

        scene.render(offscreen)

        assert _count_rgb(offscreen, SPRITE_COLOR) == 20 * 30
        assert _count_rgb(offscreen, BACKGROUND) == SCREEN_SIZE[0] * SCREEN_SIZE[1] - 20 * 30
        assert _count_rgb(display, BACKGROUND) == 0

    def test_scene_rendering_with_manager(self, display):
        """Switching to a scene paints its background on the display at once."""
        scene = _scene_with_background(BACKGROUND)

        self.scene_manager.switch_to_scene(scene)

        assert self.scene_manager.active_scene is scene
        assert _count_rgb(display, BACKGROUND) == SCREEN_SIZE[0] * SCREEN_SIZE[1]

    def test_scene_rendering_multiple_scenes(self, display):
        """Two scenes keep their own backgrounds and sprites: each renders only its own."""
        first_scene = _scene_with_background(BACKGROUND)
        second_scene = _scene_with_background(OTHER_BACKGROUND)
        first_scene.all_sprites.add(_solid_sprite(color=SPRITE_COLOR, rect=(0, 0, 10, 10)))
        first_surface = pygame.Surface(SCREEN_SIZE)
        second_surface = pygame.Surface(SCREEN_SIZE)

        first_scene.render(first_surface)
        second_scene.render(second_surface)

        assert _count_rgb(first_surface, SPRITE_COLOR) == 100
        assert _rgb_at(first_surface, (400, 300)) == BACKGROUND
        assert _count_rgb(second_surface, SPRITE_COLOR) == 0
        assert _count_rgb(second_surface, OTHER_BACKGROUND) == SCREEN_SIZE[0] * SCREEN_SIZE[1]

    def test_scene_rendering_scene_transition(self, display):
        """A switch from one scene to another replaces the first's picture with the second's."""
        first_scene = _scene_with_background(BACKGROUND)
        first_scene.all_sprites.add(_solid_sprite(color=SPRITE_COLOR, rect=(50, 50, 40, 40)))
        second_scene = _scene_with_background(OTHER_BACKGROUND)
        self.scene_manager.switch_to_scene(first_scene)
        first_scene.render(display)
        assert _count_rgb(display, SPRITE_COLOR) == 40 * 40

        self.scene_manager.switch_to_scene(second_scene)

        assert self.scene_manager.active_scene is second_scene
        assert self.scene_manager.previous_scene is first_scene
        # Nothing of the first scene is left: no stale sprite, all the second's background
        assert _count_rgb(display, SPRITE_COLOR) == 0
        assert _count_rgb(display, OTHER_BACKGROUND) == SCREEN_SIZE[0] * SCREEN_SIZE[1]

    def test_scene_rendering_with_visibility(self, display):
        """An invisible sprite is not drawn; making it visible draws it on the next render."""
        scene = _scene_with_background(BACKGROUND)
        sprite = _solid_sprite(color=SPRITE_COLOR, rect=(200, 200, 16, 16))
        sprite.visible = 0
        scene.all_sprites.add(sprite)

        scene.render(display)
        assert _count_rgb(display, SPRITE_COLOR) == 0

        sprite.visible = 1
        sprite.dirty = 1
        scene.render(display)
        assert _count_rgb(display, SPRITE_COLOR) == 16 * 16

    def test_scene_rendering_with_visibility_manager(self, display):
        """A visible sprite of the scene switched to is drawn by its next render."""
        scene = _scene_with_background(BACKGROUND)
        scene.all_sprites.add(_solid_sprite(color=SPRITE_COLOR, rect=(300, 300, 12, 8)))
        hidden_sprite = _solid_sprite(color=TOP_SPRITE_COLOR, rect=(500, 300, 12, 8))
        hidden_sprite.visible = 0
        scene.all_sprites.add(hidden_sprite)

        self.scene_manager.switch_to_scene(scene)
        scene.render(display)

        assert _count_rgb(display, SPRITE_COLOR) == 12 * 8
        assert _count_rgb(display, TOP_SPRITE_COLOR) == 0

    def test_scene_rendering_with_custom_drawing(self, display):
        """A scene that overrides render() can draw on top of the sprites it renders."""

        class MarkerScene(Scene):
            """Draws a marker over its sprites."""

            def render(self, screen):
                super().render(screen)
                pygame.draw.rect(screen, MARKER_COLOR, (0, 0, 5, 5))

        scene = MarkerScene()
        scene.background_color = BACKGROUND
        scene.all_sprites.add(_solid_sprite(color=SPRITE_COLOR, rect=(0, 0, 10, 10)))

        scene.render(display)

        assert _count_rgb(display, MARKER_COLOR) == 5 * 5
        # The marker covers a quarter of the sprite
        assert _count_rgb(display, SPRITE_COLOR) == 10 * 10 - 5 * 5

    def test_scene_rendering_with_layering(self, display):
        """Where sprites overlap, the higher layer is drawn on top, whatever the add order."""
        scene = _scene_with_background(BACKGROUND)
        top_sprite = _solid_sprite(color=TOP_SPRITE_COLOR, rect=(100, 100, 20, 20), layer=2)
        bottom_sprite = _solid_sprite(color=SPRITE_COLOR, rect=(110, 100, 20, 20), layer=1)
        scene.all_sprites.add(top_sprite)
        scene.all_sprites.add(bottom_sprite)

        scene.render(display)

        assert _count_rgb(display, TOP_SPRITE_COLOR) == 20 * 20
        assert _count_rgb(display, SPRITE_COLOR) == 10 * 20
        assert _rgb_at(display, (115, 110)) == TOP_SPRITE_COLOR

    def test_scene_rendering_with_render_state(self, display):
        """A render cleans dirty=1 sprites; dirty=2 sprites stay dirty and redraw every frame."""
        scene = _scene_with_background(BACKGROUND)
        # The group's first draw repaints the whole screen and leaves every flag as it was
        scene.render(display)
        once_sprite = _solid_sprite(color=SPRITE_COLOR, rect=(0, 0, 4, 4))
        always_sprite = _solid_sprite(color=TOP_SPRITE_COLOR, rect=(10, 0, 4, 4))
        always_sprite.dirty = 2
        scene.all_sprites.add(once_sprite, always_sprite)

        scene.render(display)

        assert once_sprite.dirty == 0
        assert always_sprite.dirty == 2

        # A clean sprite whose image changed is not redrawn; the always-dirty one is
        once_sprite.image.fill(MARKER_COLOR)
        always_sprite.image.fill(MARKER_COLOR)
        scene.render(display)
        assert _rgb_at(display, (1, 1)) == SPRITE_COLOR
        assert _rgb_at(display, (11, 1)) == MARKER_COLOR

    def test_scene_rendering_with_render_state_manager(self, display):
        """Switching to a scene marks it dirty, so its sprites are redrawn on its next update."""
        scene = _scene_with_background(BACKGROUND)
        # The group's first draw repaints the whole screen and leaves every flag as it was
        scene.render(display)
        sprite = _solid_sprite(color=SPRITE_COLOR, rect=(0, 0, 4, 4))
        scene.all_sprites.add(sprite)
        scene.render(display)
        scene.dirty = 0
        assert sprite.dirty == 0

        self.scene_manager.switch_to_scene(scene)
        scene.update()

        assert scene.dirty == 1
        assert sprite.dirty == 1
        scene.render(display)
        assert _count_rgb(display, SPRITE_COLOR) == 4 * 4

    def test_scene_rendering_with_exceptions(self, display):
        """Rendering onto a surface smaller than the scene clips instead of raising."""
        scene = _scene_with_background(BACKGROUND)
        scene.all_sprites.add(_solid_sprite(color=SPRITE_COLOR, rect=(30, 30, 20, 20)))
        small_surface = pygame.Surface((40, 40))

        scene.render(small_surface)

        assert _count_rgb(small_surface, SPRITE_COLOR) == 10 * 10
        assert _count_rgb(small_surface, BACKGROUND) == 40 * 40 - 10 * 10

    def test_scene_rendering_with_manager_exceptions(self, display):
        """Switching to no scene ends the run without drawing over the last scene's picture."""
        scene = _scene_with_background(BACKGROUND)
        self.scene_manager.switch_to_scene(scene)

        self.scene_manager.switch_to_scene(None)

        assert self.scene_manager.active_scene is None
        assert self.scene_manager.previous_scene is scene
        assert _count_rgb(display, BACKGROUND) == SCREEN_SIZE[0] * SCREEN_SIZE[1]

    def test_scene_rendering_with_surface_management(self, display):
        """A scene draws to the display it was made with; its background is display-sized."""
        scene = _scene_with_background(BACKGROUND)

        assert scene.screen is display
        assert scene.background.get_size() == SCREEN_SIZE
        assert (scene.screen_width, scene.screen_height) == SCREEN_SIZE
        assert _count_rgb(scene.background, BACKGROUND) == SCREEN_SIZE[0] * SCREEN_SIZE[1]

    def test_scene_rendering_with_surface_management_manager(self, display):
        """A screenshot is a copy of the display: later drawing does not change it."""
        scene = _scene_with_background(BACKGROUND)
        self.scene_manager.switch_to_scene(scene)

        screenshot = scene.screenshot
        display.fill(OTHER_BACKGROUND)

        assert screenshot.get_size() == SCREEN_SIZE
        assert _count_rgb(screenshot, BACKGROUND) == SCREEN_SIZE[0] * SCREEN_SIZE[1]

    def test_scene_rendering_with_custom_surface(self, display):
        """Sprites are placed by their rects on whatever surface the scene renders to."""
        scene = _scene_with_background(BACKGROUND)
        scene.all_sprites.add(_solid_sprite(color=SPRITE_COLOR, rect=(5, 6, 3, 2)))
        custom_surface = pygame.Surface(SCREEN_SIZE)

        scene.render(custom_surface)

        assert custom_surface.get_bounding_rect() is not None
        sprite_area = custom_surface.subsurface((5, 6, 3, 2))
        assert _count_rgb(sprite_area, SPRITE_COLOR) == 3 * 2
        assert _count_rgb(custom_surface, SPRITE_COLOR) == 3 * 2

    def test_scene_rendering_with_render_order(self, display):
        """On one layer, a sprite added later is drawn over one added earlier."""
        scene = _scene_with_background(BACKGROUND)
        scene.all_sprites.add(_solid_sprite(color=SPRITE_COLOR, rect=(100, 100, 20, 20)))
        scene.all_sprites.add(_solid_sprite(color=TOP_SPRITE_COLOR, rect=(110, 100, 20, 20)))

        scene.render(display)

        assert _rgb_at(display, (115, 110)) == TOP_SPRITE_COLOR
        assert _count_rgb(display, SPRITE_COLOR) == 10 * 20

    def test_scene_rendering_with_render_order_transition(self, display):
        """Switching back to a scene shows its background, then its sprites in order again."""
        first_scene = _scene_with_background(BACKGROUND)
        first_scene.all_sprites.add(_solid_sprite(color=SPRITE_COLOR, rect=(100, 100, 20, 20)))
        first_scene.all_sprites.add(_solid_sprite(color=TOP_SPRITE_COLOR, rect=(110, 100, 20, 20)))
        second_scene = _scene_with_background(OTHER_BACKGROUND)
        self.scene_manager.switch_to_scene(first_scene)
        first_scene.render(display)
        self.scene_manager.switch_to_scene(second_scene)
        assert _count_rgb(display, OTHER_BACKGROUND) == SCREEN_SIZE[0] * SCREEN_SIZE[1]

        self.scene_manager.switch_to_scene(first_scene)
        first_scene.update()
        first_scene.render(display)

        assert _rgb_at(display, (115, 110)) == TOP_SPRITE_COLOR
        assert _count_rgb(display, SPRITE_COLOR) == 10 * 20
        assert _count_rgb(display, OTHER_BACKGROUND) == 0


class TestSceneRenderingEdgeCases:
    """Test scene rendering edge cases."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()
        self.scene_manager = SceneManager()

    def teardown_method(self):
        """Clean up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()

    def test_scene_rendering_with_render_state_changes(self, display):
        """A sprite that moves leaves background where it was, not a stale copy of itself."""
        scene = _scene_with_background(BACKGROUND)
        sprite = _solid_sprite(color=SPRITE_COLOR, rect=(100, 100, 10, 10))
        scene.all_sprites.add(sprite)
        scene.render(display)

        sprite.rect.x = 300
        sprite.dirty = 1
        scene.render(display)

        assert _count_rgb(display, SPRITE_COLOR) == 10 * 10
        assert _rgb_at(display, (105, 105)) == BACKGROUND
        assert _rgb_at(display, (305, 105)) == SPRITE_COLOR

    def test_scene_rendering_with_render_state_changes_manager(self, display):
        """A new background color set while a scene is showing reaches the whole display."""
        scene = _scene_with_background(BACKGROUND)
        self.scene_manager.switch_to_scene(scene)
        scene.render(display)

        scene.background_color = OTHER_BACKGROUND
        scene.update()
        scene.render(display)

        assert _count_rgb(display, OTHER_BACKGROUND) == SCREEN_SIZE[0] * SCREEN_SIZE[1]

    def test_background_pattern_set_while_showing_reaches_the_whole_display(self, display):
        """A pattern set while a scene is showing replaces the old color everywhere (#166)."""
        scene = _scene_with_background(BACKGROUND)
        self.scene_manager.switch_to_scene(scene)
        scene.render(display)

        scene.background_pattern = BackgroundPattern.CHANNEL_THREE
        scene.update()
        scene.render(display)

        expected = background_pattern_surface(
            pattern=BackgroundPattern.CHANNEL_THREE, size=SCREEN_SIZE
        )
        assert _count_rgb(display, BACKGROUND) == _count_rgb(expected, BACKGROUND)
        assert scene.rects == [pygame.Rect((0, 0), SCREEN_SIZE)]

    def test_scene_rendering_with_edge_cases(self, display):
        """An empty scene renders only its background; later renders report no changes."""
        scene = _scene_with_background(BACKGROUND)

        scene.render(display)
        scene.render(display)

        assert scene.rects == []
        assert _count_rgb(display, BACKGROUND) == SCREEN_SIZE[0] * SCREEN_SIZE[1]

    def test_scene_rendering_with_edge_cases_manager(self, display):
        """A sprite partly off the display is clipped to the visible part."""
        scene = _scene_with_background(BACKGROUND)
        scene.all_sprites.add(_solid_sprite(color=SPRITE_COLOR, rect=(790, 590, 20, 20)))
        self.scene_manager.switch_to_scene(scene)

        scene.render(display)

        assert _count_rgb(display, SPRITE_COLOR) == 10 * 10
        assert _rgb_at(display, (799, 599)) == SPRITE_COLOR


class TestSceneBackgroundOpacity:
    """The scene background is opaque, so sprites blend over it (BUGS.md #142)."""

    def test_a_translucent_sprite_blends_over_the_bare_background(self, display):
        """BUGS.md #142: the background is opaque, so a translucent sprite blends over it.

        With an alpha-0 background, a display with per-pixel alpha (cocoa's) got the sprite's
        colour copied unblended, and the background pixels showed black in the window.
        """
        scene = _scene_with_background(BACKGROUND)
        translucent_sprite = SolidSprite()
        translucent_sprite.image = pygame.Surface((20, 10), pygame.SRCALPHA)
        translucent_sprite.image.fill((*TRANSLUCENT_SPRITE_COLOR, TRANSLUCENT_SPRITE_ALPHA))
        translucent_sprite.rect = pygame.Rect(100, 100, 20, 10)
        translucent_sprite.dirty = 1
        scene.all_sprites.add(translucent_sprite)

        scene.render(display)

        blended_color = tuple(
            round(
                sprite_channel * TRANSLUCENT_SPRITE_ALPHA / 255
                + background_channel * (255 - TRANSLUCENT_SPRITE_ALPHA) / 255
            )
            for sprite_channel, background_channel in zip(
                TRANSLUCENT_SPRITE_COLOR, BACKGROUND, strict=True
            )
        )
        for channel, expected_channel in zip(
            _rgb_at(display, (105, 105)), blended_color, strict=True
        ):
            # pygame's blitter divides by 256, not 255: within one step of the exact blend
            assert abs(channel - expected_channel) <= 1
        if has_per_pixel_alpha(surface=display):
            assert display.get_at((105, 105)).a == OPAQUE
            assert display.get_at((0, 0)).a == OPAQUE
