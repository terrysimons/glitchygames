"""Test suite for hardware-level animation rendering verification.

This module tests that animated sprites properly reach the display surface, providing
multiple layers of verification to quickly identify where rendering problems occur in the
pipeline.

The tests draw on a real pygame display: ``tests/conftest.py`` sets ``SDL_VIDEODRIVER`` to
``dummy``, so ``pygame.display.set_mode`` gives a headless display surface that holds real
pixels (set ``SDL_VIDEODRIVER=cocoa`` or similar to watch them in a window). They used to
run on the shared pygame mocks, whose display surface answers black for every pixel, so
they checked no rendering at all. Pixels are read in bulk with ``pygame.surfarray``: never
read the screen one ``get_at`` call at a time (BUGS.md #85).
"""

import sys
import time
import tomllib
from pathlib import Path

import numpy as np
import pygame
import pytest

from glitchygames.color import MAGENTA_TRANSPARENCY_KEY
from glitchygames.display_mode import set_display_mode
from glitchygames.scenes import Scene
from glitchygames.sprites import SpriteFactory

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def get_resource_path(filename: str) -> str:
    """Get the full path to a resource file.

    Returns:
        str: The resource path.

    """
    return str(
        Path(__file__).parent.parent.parent
        / 'glitchygames'
        / 'examples'
        / 'resources'
        / 'sprites'
        / filename,
    )


def toml_frame_colors(animation_file: str) -> list[tuple[int, int, int]]:
    """Read the colour of each frame of a sprite file whose frames are one colour each.

    The colours come straight from the TOML, independently of the sprite loader, so they
    are what the display should show.

    Returns:
        list[tuple[int, int, int]]: The colour of every frame of the first animation.

    """
    with Path(animation_file).open(mode='rb') as toml_file:
        sprite_data = tomllib.load(toml_file)
    glyph_colors = {
        glyph: (color['red'], color['green'], color['blue'])
        for glyph, color in sprite_data['colors'].items()
    }
    frame_colors = []
    for frame in sprite_data['animation'][0]['frame']:
        frame_glyphs = set(''.join(frame['pixels'].split()))
        assert len(frame_glyphs) == 1, 'Each frame of the test sprite must be one colour'
        frame_colors.append(glyph_colors[frame_glyphs.pop()])
    return frame_colors


def region_colors(surface: pygame.Surface, region: pygame.Rect) -> set[tuple[int, int, int]]:
    """Read the distinct colours inside a region of a surface, in bulk.

    Returns:
        set[tuple[int, int, int]]: The RGB colours present in the region.

    """
    region_pixels = pygame.surfarray.array3d(surface.subsurface(region)).reshape(-1, 3)
    return {tuple(int(channel) for channel in color) for color in np.unique(region_pixels, axis=0)}


# Constants for test thresholds
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
BACKGROUND_COLOR = (20, 20, 40)
# colors.toml: ten one-colour 2x2 frames; frame 0 red for 0.25 s, frame 1 green for 0.75 s,
# frame 2 blue, ...
COLORS_FILE = get_resource_path('colors.toml')
FRAME_COLORS = toml_frame_colors(COLORS_FILE)
FIRST_FRAME_SECONDS = 0.25
SECOND_FRAME_SECONDS = 0.75
MAX_PERFORMANCE_TIME = 2.0
PERFORMANCE_FRAME_COUNT = 5


class HardwareAnimationTestScene(Scene):
    """Test scene for hardware-level animation testing."""

    NAME = 'Hardware Animation Test Scene'

    def __init__(self, animation_file: str, groups: pygame.sprite.LayeredDirty | None = None):
        """Initialize the test scene with an animated sprite."""
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        # Initialize with minimal options
        options = {'width': SCREEN_WIDTH, 'height': SCREEN_HEIGHT, 'fullscreen': False}
        super().__init__(options=options, groups=groups)

        # Set up the scene
        self.background_color = BACKGROUND_COLOR
        self.fps = 60
        self.animation_file = animation_file
        self.animated_sprite = None

        # Load the animated sprite
        self._load_animated_sprite()

        # Add sprite to the group for rendering
        assert self.animated_sprite is not None
        self.all_sprites.add(self.animated_sprite)

        # A scene starts on a full background (SceneManager blits it when a scene is set up);
        # after that, render() only restores the background behind dirty sprites
        assert self.screen is not None
        self.screen.blit(self.background, (0, 0))

    def _load_animated_sprite(self) -> None:
        """Load the animated sprite from the specified file."""
        self.animated_sprite = SpriteFactory.load_sprite(filename=self.animation_file)
        self.animated_sprite.play()
        # Center on screen
        assert self.animated_sprite.rect is not None
        assert self.screen is not None
        self.animated_sprite.rect.center = self.screen.get_rect().center

    def dt_tick(self, dt: float) -> None:
        """Advance the animation by the frame's dt, as the example games' sprites do."""
        assert self.animated_sprite is not None
        self.animated_sprite.update(dt)

    def update(self) -> None:
        """Do no animation work in the render phase.

        Scene.update() calls each dirty sprite's update() with no dt, which advances an
        AnimatedSprite by its default 0.016 s on every rendered frame whatever the frame's
        real dt. The animation advances only in dt_tick() here (as PapyrusCobra's does), so
        a test controls exactly how far it moves.
        """

    def force_display_update(self) -> None:
        """Render the scene to the display and present it, as the engine's frame does."""
        self.update()
        assert self.screen is not None
        self.render(self.screen)
        pygame.display.flip()

    @staticmethod
    def capture_hardware_display_buffer() -> np.ndarray:
        """Capture the display surface's pixels in one bulk read.

        Returns:
            np.ndarray: The RGB pixels, indexed [x, y, channel].

        """
        display_surface = pygame.display.get_surface()
        assert display_surface is not None
        return pygame.surfarray.array3d(display_surface)

    def compose_expected_frame(self) -> np.ndarray:
        """Compose, off screen, what the display should show: the background and the sprite.

        Returns:
            np.ndarray: The expected RGB pixels, indexed [x, y, channel].

        """
        assert self.animated_sprite is not None
        assert self.animated_sprite.image is not None
        assert self.animated_sprite.rect is not None
        expected_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        expected_surface.blit(self.background, (0, 0))
        expected_surface.blit(self.animated_sprite.image, self.animated_sprite.rect)
        return pygame.surfarray.array3d(expected_surface)

    def sprite_area_colors_on_display(self) -> set[tuple[int, int, int]]:
        """Read the colours the display shows where the sprite is.

        Returns:
            set[tuple[int, int, int]]: The RGB colours in the sprite's rect on the display.

        """
        display_surface = pygame.display.get_surface()
        assert display_surface is not None
        assert self.animated_sprite is not None
        assert self.animated_sprite.rect is not None
        return region_colors(display_surface, self.animated_sprite.rect)


class TestAnimationHardware:
    """Test hardware-level animation rendering and display buffer verification."""

    @pytest.fixture(autouse=True)
    def real_display(self):
        """Open a real (headless under the dummy video driver) display for each test.

        Yields:
            pygame.Surface: The display surface.

        """
        pygame.init()
        yield set_display_mode(size=(SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.quit()

    def test_hardware_display_buffer_access(self, real_display):
        """Test that the scene renders to the real display, background everywhere but the sprite."""
        scene = HardwareAnimationTestScene(COLORS_FILE)
        assert scene.screen is real_display

        scene.force_display_update()

        display_pixels = scene.capture_hardware_display_buffer()
        assert display_pixels.shape == (SCREEN_WIDTH, SCREEN_HEIGHT, 3)
        background_pixel_count = int(np.all(display_pixels == BACKGROUND_COLOR, axis=2).sum())
        assert scene.animated_sprite is not None
        assert scene.animated_sprite.rect is not None
        sprite_area = scene.animated_sprite.rect.width * scene.animated_sprite.rect.height
        assert background_pixel_count == SCREEN_WIDTH * SCREEN_HEIGHT - sprite_area

    def test_sprite_visibility_in_hardware_buffer(self):
        """Test that the sprite's first frame colour is on the display where the sprite is."""
        scene = HardwareAnimationTestScene(COLORS_FILE)

        scene.force_display_update()

        assert scene.sprite_area_colors_on_display() == {FRAME_COLORS[0]}

    def test_hardware_vs_surface_consistency(self):
        """Test that the display matches the background with the sprite composed on top."""
        scene = HardwareAnimationTestScene(COLORS_FILE)

        scene.force_display_update()

        assert np.array_equal(
            scene.capture_hardware_display_buffer(), scene.compose_expected_frame()
        )

    def test_animation_frame_transitions_in_hardware(self):
        """Test that each frame's colour reaches the display as the frame changes."""
        scene = HardwareAnimationTestScene(COLORS_FILE)
        assert scene.animated_sprite is not None

        displayed_colors = []
        for frame_index in range(len(FRAME_COLORS)):
            scene.animated_sprite.set_frame(frame_index)
            scene.force_display_update()
            displayed_colors.append(scene.sprite_area_colors_on_display())

        # Every frame shows its colour, except the magenta one: magenta is the transparency
        # key, so that frame shows the background (BUGS.md #133)
        assert displayed_colors == [
            {BACKGROUND_COLOR if color == MAGENTA_TRANSPARENCY_KEY else color}
            for color in FRAME_COLORS
        ]

    def test_hardware_rendering_performance(self):
        """Test that rendering and reading back the display performs within acceptable limits."""
        scene = HardwareAnimationTestScene(COLORS_FILE)
        assert scene.animated_sprite is not None

        start_time = time.perf_counter()
        for frame_index in range(PERFORMANCE_FRAME_COUNT):
            scene.animated_sprite.set_frame(frame_index)
            scene.force_display_update()
            scene.capture_hardware_display_buffer()
        total_time = time.perf_counter() - start_time

        assert total_time < MAX_PERFORMANCE_TIME, f'Rendering should be fast: {total_time:.3f}s'

    def test_hardware_buffer_integrity(self):
        """Test that presenting an unchanged scene again leaves the display unchanged."""
        scene = HardwareAnimationTestScene(COLORS_FILE)
        scene.force_display_update()
        first_capture = scene.capture_hardware_display_buffer()

        scene.force_display_update()
        second_capture = scene.capture_hardware_display_buffer()

        assert np.array_equal(first_capture, second_capture)

    def test_sprite_positioning_in_hardware_buffer(self):
        """Test that the drawn pixels sit exactly in the sprite's rect, centred on screen."""
        scene = HardwareAnimationTestScene(COLORS_FILE)

        scene.force_display_update()

        display_pixels = scene.capture_hardware_display_buffer()
        drawn_x, drawn_y = np.nonzero(np.any(display_pixels != BACKGROUND_COLOR, axis=2))
        drawn_rect = pygame.Rect(
            int(drawn_x.min()),
            int(drawn_y.min()),
            int(drawn_x.max() - drawn_x.min()) + 1,
            int(drawn_y.max() - drawn_y.min()) + 1,
        )
        assert scene.animated_sprite is not None
        assert drawn_rect == scene.animated_sprite.rect
        assert drawn_rect.center == (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

    def test_hardware_vs_sprite_surface_consistency(self):
        """Test that the display's sprite area holds exactly the sprite image's pixels."""
        scene = HardwareAnimationTestScene(COLORS_FILE)

        scene.force_display_update()

        assert scene.animated_sprite is not None
        assert scene.animated_sprite.image is not None
        assert scene.animated_sprite.rect is not None
        display_surface = pygame.display.get_surface()
        assert display_surface is not None
        sprite_area_pixels = pygame.surfarray.array3d(
            display_surface.subsurface(scene.animated_sprite.rect),
        )
        assert np.array_equal(
            sprite_area_pixels,
            pygame.surfarray.array3d(scene.animated_sprite.image),
        )

    def test_animation_timing_affects_hardware_buffer(self):
        """Test that the display changes frame only once the frame's duration has passed."""
        scene = HardwareAnimationTestScene(COLORS_FILE)

        scene.dt_tick(FIRST_FRAME_SECONDS / 2)
        scene.force_display_update()
        assert scene.sprite_area_colors_on_display() == {FRAME_COLORS[0]}

        scene.dt_tick(FIRST_FRAME_SECONDS / 2)
        scene.force_display_update()
        assert scene.sprite_area_colors_on_display() == {FRAME_COLORS[1]}

        scene.dt_tick(SECOND_FRAME_SECONDS / 2)
        scene.force_display_update()
        assert scene.sprite_area_colors_on_display() == {FRAME_COLORS[1]}

        scene.dt_tick(SECOND_FRAME_SECONDS / 2)
        scene.force_display_update()
        assert scene.sprite_area_colors_on_display() == {FRAME_COLORS[2]}
