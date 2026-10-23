#!/usr/bin/env python3
"""Pause scene for paddleslap game."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame

from glitchygames.color import BLACK
from glitchygames.scenes import Scene

if TYPE_CHECKING:
    from glitchygames.events.base import KeyEvent, WindowEvent
from glitchygames.sprites import Sprite
from glitchygames.ui.message_screen import MessageScreen


class PauseOverlay(Sprite):
    """Semi-transparent overlay for pause screen."""

    def __init__(self: Self, game: Scene, screenshot: pygame.Surface) -> None:
        """Initialize the pause overlay.

        Args:
            game (Scene): The game instance
            screenshot (pygame.Surface): Screenshot of the game when paused

        """
        # Initialize the sprite with the screenshot dimensions
        super().__init__(x=0, y=0, width=screenshot.get_width(), height=screenshot.get_height())

        # The screenshot dimmed, with PAUSED centred on the game's screen: the shared
        # pause-style look (the replay's start screen draws the same way;
        # glitchygames/ui/message_screen.py)
        self.image = MessageScreen().render(
            backdrop=screenshot, area_size=(game.screen_width, game.screen_height)
        )

        self.rect = self.image.get_rect()
        self.dirty = 1


class PauseScene(Scene):
    """Pause scene that shows a semi-transparent overlay over the game."""

    # It presents the paused scene, so it cannot be rebuilt on its own (glitchygames/scene_start.py)
    CAPTURES_SCENE_START: ClassVar[bool] = False

    def __init__(self: Self, **kwargs: Any) -> None:
        """Initialize the pause scene.

        Args:
            **kwargs: Additional keyword arguments.

        """
        super().__init__(**kwargs)
        # Black under the overlay (named: a scene that sets no background shows the test
        # pattern), so the pause screen's own background is never the pattern wherever the
        # frozen screenshot does not cover it (a custom screenshot may be smaller)
        self.background_color = BLACK
        self.overlay = None
        self._space_pressed = False
        # The gameplay scene this pause screen froze; the debug overlay inspects it instead
        self._paused_scene: Scene | None = None

    @override
    def setup(self: Self) -> None:
        """Set up the pause scene."""
        super().setup()

        # Create the pause overlay using the previous scene's screenshot
        previous_scene = self.scene_manager.previous_scene
        self._paused_scene = previous_scene
        if previous_scene:
            # Use the scene's screenshot property (which will use custom screenshot if set)
            screenshot = previous_scene.screenshot
        else:
            # This should not happen - scene manager should always have a previous_scene
            self.log.warning('No previous scene found - this should not happen!')
            # Fallback: create a black screenshot
            screenshot = pygame.Surface((self.screen_width, self.screen_height))
            screenshot.fill((0, 0, 0))

        assert self.scene_manager.game_engine is not None
        self.overlay = PauseOverlay(self.scene_manager.game_engine.game, screenshot)
        self.all_sprites.add(self.overlay)

        self.log.info('Pause scene setup complete')

    @property
    @override
    def debug_subject(self: Self) -> Scene:
        """The paused gameplay scene, so the debug overlay keeps showing its hitboxes."""
        return self._paused_scene if self._paused_scene is not None else self

    @override
    def on_key_down_event(self: Self, event: KeyEvent) -> None:
        """Handle key down events for the pause scene.

        Args:
            event: The key down event

        """
        if event.key == pygame.K_SPACE:
            # Track that spacebar is pressed (but don't act on it yet)
            self._space_pressed = True
        elif event.key == pygame.K_ESCAPE:
            # Quit the game
            self.scene_manager.quit()
        else:
            super().on_key_down_event(event)

    @override
    def on_key_up_event(self: Self, event: KeyEvent) -> None:
        """Handle key up events for the pause scene.

        Args:
            event: The key up event

        """
        if event.key == pygame.K_SPACE and self._space_pressed:
            # Spacebar was pressed and now released - resume the game
            self._space_pressed = False
            self.log.info('Resuming game...')
            self.resume()
        else:
            super().on_key_up_event(event)

    @override
    def on_window_focus_gained_event(self: Self, event: WindowEvent) -> None:
        """Auto-resume when the window regains focus.

        Waits a short time after setup to avoid the focus gained event
        that fires immediately when the pause scene is first displayed.

        Args:
            event: The focus gained event.

        """
        super().on_window_focus_gained_event(event)
        # Ignore focus events in the first 0.5s — the scene switch itself
        # triggers a focus lost/gained pair that we don't want to act on
        min_pause_duration = 0.5
        if self.dt_timer > min_pause_duration:
            self.log.info('Window focus regained — auto-resuming')
            self.resume()
