"""Game Over scene with optional score display and high score tracking."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.scenes import Scene

if TYPE_CHECKING:
    from glitchygames.events.base import HashableEvent
from glitchygames.sprites import Sprite

log = logging.getLogger('game')


class GameOverScene(Scene):
    """Game Over scene with final score and high score display.

    Accepts an optional final_score to show the player's result and
    an optional high_scores list to display the leaderboard.
    """

    def __init__(
        self: Self,
        final_score: int | None = None,
        high_scores: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Game Over scene.

        Args:
            final_score: The player's final score (displayed if provided).
            high_scores: List of high score dicts with 'score' key,
                sorted descending. Top 5 are displayed.
            **kwargs: Additional keyword arguments.

        """
        super().__init__(**kwargs)
        self.final_score = final_score
        self.high_scores = high_scores or []
        self.text_sprite = None
        self._space_pressed = False
        # Don't set next_scene to self - this causes infinite loops
        # The scene will stay active until user input changes it

    @override
    def setup(self: Self) -> None:
        """Set up the Game Over scene with score display."""
        super().setup()
        log.info('GameOverScene setup() called')

        center_x = self.screen_width // 2
        current_y = self.screen_height // 4

        # Title
        self.text_sprite = TextSprite(
            'GAME OVER',
            (center_x, current_y),
            color=(255, 0, 0),
            font_size=48,
        )
        self.all_sprites.add(self.text_sprite)
        current_y += 60

        # Final score (if provided)
        if self.final_score is not None:
            score_sprite = TextSprite(
                f'Score: {self.final_score}',
                (center_x, current_y),
                color=(255, 255, 100),
                font_size=32,
            )
            self.all_sprites.add(score_sprite)
            current_y += 50

        # High scores (top 5)
        if self.high_scores:
            header = TextSprite(
                'HIGH SCORES',
                (center_x, current_y),
                color=(200, 200, 200),
                font_size=28,
            )
            self.all_sprites.add(header)
            current_y += 35

            max_displayed = 5
            for rank, entry in enumerate(self.high_scores[:max_displayed], start=1):
                score_value = entry.get('score', 0)
                entry_sprite = TextSprite(
                    f'{rank}. {score_value}',
                    (center_x, current_y),
                    color=(180, 180, 180),
                    font_size=24,
                )
                self.all_sprites.add(entry_sprite)
                current_y += 30

        # Subtitle
        current_y += 20
        subtitle = TextSprite(
            'Press SPACE to restart or ESC to quit',
            (center_x, current_y),
            color=(255, 255, 255),
            font_size=24,
        )
        self.all_sprites.add(subtitle)
        log.info('GameOverScene setup() completed')

    @override
    def update(self: Self) -> None:
        """Update the Game Over scene.

        Args:
            None

        """
        # Call the parent update method to handle sprite updates
        super().update()
        log.debug('GameOverScene update() called')

    @override
    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Handle key down events for the Game Over scene.

        Args:
            event (HashableEvent): The key down event.

        """
        if event.key == pygame.K_SPACE:
            # Track that spacebar is pressed (but don't act on it yet)
            self._space_pressed = True
        elif event.key == pygame.K_ESCAPE:
            # Quit the game
            self.scene_manager.quit()
        else:
            # Let the base Scene class handle other keys (like 'q' for quit)
            super().on_key_down_event(event)

    @override
    def on_key_up_event(self: Self, event: HashableEvent) -> None:
        """Handle key up events for the Game Over scene.

        Args:
            event (HashableEvent): The key up event.

        """
        if event.key == pygame.K_SPACE and self._space_pressed:
            # Spacebar was pressed and now released - restart the game
            self._space_pressed = False
            self.resume()
        else:
            # Let the base Scene class handle other keys
            super().on_key_up_event(event)

    @override
    def resume(self: Self) -> None:
        """Resume by creating a new game instance.

        Override the default resume behavior to create a fresh game
        instead of switching back to the previous scene.

        """
        # Get the game class from the previous scene
        if self.scene_manager.previous_scene:
            game_class = type(self.scene_manager.previous_scene)
            self.log.info('Restarting game with class: %s', game_class)

            # Create a new instance of the game with the same options
            new_game = game_class(options=self.options)

            # Switch to the new game instance
            self.scene_manager.switch_to_scene(new_game)
        else:
            self.log.warning('No previous scene found to restart')


class TextSprite(Sprite):
    """A sprite class for displaying text."""

    def __init__(
        self: Self,
        text: str,
        position: tuple[int, int],
        color: tuple[int, int, int] = (255, 255, 255),
        font_size: int = 24,
        **kwargs: Any,
    ) -> None:
        """Initialize the text sprite.

        Args:
            text: The text to display.
            position: The position of the text (x, y).
            color: The color of the text.
            font_size: The size of the font.
            **kwargs: Additional keyword arguments.

        """
        # Create a font
        font = pygame.font.Font(None, font_size)

        # Render the text
        text_surface = font.render(text, True, color)  # noqa: FBT003

        # Initialize the sprite with the text surface
        super().__init__(
            x=position[0] - text_surface.get_width() // 2,  # Center horizontally
            y=position[1] - text_surface.get_height() // 2,  # Center vertically
            width=text_surface.get_width(),
            height=text_surface.get_height(),
            **kwargs,
        )

        # Set the image to the text surface
        self.image = text_surface
