"""Game Over scene for the paddleslap game."""

import logging
from typing import Self

import pygame
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite

log = logging.getLogger("game")


class GameOverScene(Scene):
    """Game Over scene that displays when all balls are dead."""

    def __init__(self: Self, **kwargs) -> None:
        """Initialize the Game Over scene.

        Args:
            **kwargs: Additional keyword arguments.

        Returns:
            None

        """
        super().__init__(**kwargs)
        self.text_sprite = None
        # Don't set next_scene to self - this causes infinite loops
        # The scene will stay active until user input changes it

    def setup(self: Self) -> None:
        """Set up the Game Over scene.

        Args:
            None

        Returns:
            None

        """
        super().setup()
        log.info("GameOverScene setup() called")

        # Create a text sprite for "Game Over"
        self.text_sprite = TextSprite(
            "GAME OVER",
            (self.screen_width // 2, self.screen_height // 2),
            color=(255, 0, 0),  # Red color
            font_size=48
        )
        self.all_sprites.add(self.text_sprite)

        # Create a subtitle
        subtitle = TextSprite(
            "Press SPACE to restart or ESC to quit",
            (self.screen_width // 2, self.screen_height // 2 + 60),
            color=(255, 255, 255),  # White color
            font_size=24
        )
        self.all_sprites.add(subtitle)
        log.info("GameOverScene setup() completed")

    def update(self: Self) -> None:
        """Update the Game Over scene.

        Args:
            None

        Returns:
            None

        """
        # Call the parent update method to handle sprite updates
        super().update()
        log.debug("GameOverScene update() called")

    def handle_key_down(self: Self, event) -> None:
        """Handle key down events.

        Args:
            event: The key down event.

        Returns:
            None

        """
        if event.key == pygame.K_SPACE:
            # Restart the game - switch to the previous scene
            if self.scene_manager.previous_scene:
                self.scene_manager.switch_to_scene(self.scene_manager.previous_scene)
        elif event.key == pygame.K_ESCAPE:
            # Quit the game
            self.scene_manager.quit()
        else:
            # Let the base Scene class handle other keys (like 'q' for quit)
            super().handle_key_down(event)


class TextSprite(Sprite):
    """A sprite class for displaying text."""

    def __init__(
        self: Self,
        text: str,
        position: tuple[int, int],
        color: tuple[int, int, int] = (255, 255, 255),
        font_size: int = 24,
        **kwargs
    ) -> None:
        """Initialize the text sprite.

        Args:
            text: The text to display.
            position: The position of the text (x, y).
            color: The color of the text.
            font_size: The size of the font.
            **kwargs: Additional keyword arguments.

        Returns:
            None

        """
        # Create a font
        font = pygame.font.Font(None, font_size)

        # Render the text
        text_surface = font.render(text, True, color)

        # Initialize the sprite with the text surface
        super().__init__(
            x=position[0] - text_surface.get_width() // 2,  # Center horizontally
            y=position[1] - text_surface.get_height() // 2,   # Center vertically
            width=text_surface.get_width(),
            height=text_surface.get_height(),
            **kwargs
        )

        # Set the image to the text surface
        self.image = text_surface
