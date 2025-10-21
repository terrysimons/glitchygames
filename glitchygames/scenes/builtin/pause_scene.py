#!/usr/bin/env python3
"""Pause scene for paddleslap game."""

import pygame
from typing import Self

from .. import Scene
from glitchygames.sprites import Sprite
from glitchygames.color import WHITE


class PauseOverlay(Sprite):
    """Semi-transparent overlay for pause screen."""
    
    def __init__(self: Self, game, screenshot: pygame.Surface) -> None:
        """Initialize the pause overlay.
        
        Args:
            game: The game instance
            screenshot: Screenshot of the game when paused
        """
        # Initialize the sprite with the screenshot dimensions
        super().__init__(
            x=0,
            y=0,
            width=screenshot.get_width(),
            height=screenshot.get_height()
        )
        
        # Create a semi-transparent overlay
        self.overlay = pygame.Surface((game.screen_width, game.screen_height))
        self.overlay.fill((0, 0, 0))  # Black background
        self.overlay.set_alpha(128)  # 50% transparency
        
        # Create the paused text
        font = pygame.font.Font(None, 72)
        text_surface = font.render("PAUSED", True, WHITE)
        
        # Center the text on screen
        text_rect = text_surface.get_rect()
        text_rect.center = (game.screen_width // 2, game.screen_height // 2)
        
        # Blit the screenshot first, then overlay, then text
        self.image = screenshot.copy()
        self.image.blit(self.overlay, (0, 0))
        self.image.blit(text_surface, text_rect)
        
        self.rect = self.image.get_rect()
        self.dirty = 1


class PauseScene(Scene):
    """Pause scene that shows a semi-transparent overlay over the game."""
    
    def __init__(self: Self, **kwargs) -> None:
        """Initialize the pause scene.
        
        Args:
            **kwargs: Additional keyword arguments.
        """
        super().__init__(**kwargs)
        self.overlay = None
        self._space_pressed = False
    
    def setup(self: Self) -> None:
        """Set up the pause scene."""
        super().setup()
        
        # Create the pause overlay using the previous scene's screenshot
        previous_scene = self.scene_manager.previous_scene
        if previous_scene:
            # Use the scene's screenshot property (which will use custom screenshot if set)
            screenshot = previous_scene.screenshot
        else:
            # This should not happen - scene manager should always have a previous_scene
            self.log.warning("No previous scene found - this should not happen!")
            # Fallback: create a black screenshot
            screenshot = pygame.Surface((self.screen_width, self.screen_height))
            screenshot.fill((0, 0, 0))
        
        self.overlay = PauseOverlay(self.scene_manager.game_engine.game, screenshot)
        self.all_sprites.add(self.overlay)
        
        self.log.info("Pause scene setup complete")
    
    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key down events for the pause scene.
        
        Args:
            event: The key down event
            
        Returns:
            None
        """
        if event.key == pygame.K_SPACE:
            # Track that spacebar is pressed (but don't act on it yet)
            self._space_pressed = True
        elif event.key == pygame.K_ESCAPE:
            # Quit the game
            self.scene_manager.quit()
        else:
            super().on_key_down_event(event)
    
    def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key up events for the pause scene.
        
        Args:
            event: The key up event
            
        Returns:
            None
        """
        if event.key == pygame.K_SPACE and self._space_pressed:
            # Spacebar was pressed and now released - resume the game
            self._space_pressed = False
            self.log.info("Resuming game...")
            self.resume()
        else:
            super().on_key_up_event(event)
