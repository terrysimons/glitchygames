"""Main game scene for Brave Adventurer - a Pitfall clone set in ancient Egypt."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self, override

from brave_adventurer.constants import PLAYER_HEIGHT
from brave_adventurer.levels import ClassicLevelManager
from brave_adventurer.player import Player
from brave_adventurer_core.constants import (
    GROUND_Y,
)
from brave_adventurer_core.scene import BraveAdventurerSceneBase
from glitchygames.audio import VoiceAssistant
from glitchygames.collision.layers import collision_rect_offset, get_sprite_collision_rect
from glitchygames.engine import GameEngine
from glitchygames.input.devices import LiveDeviceRegistry
from glitchygames.sources import active_sources

if TYPE_CHECKING:
    import pygame

    from brave_adventurer.enemies import Scarab
    from glitchygames.events.base import (
        ControllerButtonEvent,
        JoyButtonEvent,
    )
    from glitchygames.input import ActionMap

log = logging.getLogger('game')

# DualSense mic mute button indices differ between APIs:
# SDL Game Controller API reports button 15
# Raw joystick API reports button 16
MIC_BUTTON_CONTROLLER = 15
MIC_BUTTON_JOYSTICK = 16


class BraveAdventurerScene(BraveAdventurerSceneBase):
    """Main gameplay scene for Brave Adventurer.

    Orchestrates the player, camera, terrain, enemies, parallax backgrounds,
    and HUD. The game is a Pitfall-style side-scrolling platformer set in
    ancient Egypt.
    """

    NAME = 'Brave Adventurer'
    LEVEL_MANAGER_CLASS = ClassicLevelManager
    PLAYER_CLASS = Player
    PLAYER_START_WORLD_Y = GROUND_Y - PLAYER_HEIGHT
    SAVE_APP_NAME = 'brave-adventurer'

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize the game scene: the shared scene, then the voice assistant.

        Args:
            options: Command-line options dict from GameEngine.
            groups: Sprite group (created if not provided).

        """
        super().__init__(options=options, groups=groups)

        # Voice assistant: a controller's mic and speaker, found through miniaudio (live play
        # only: see _discover_voice_assistant)
        self.voice_assistant: VoiceAssistant | None = self._discover_voice_assistant()

    @staticmethod
    def _discover_voice_assistant() -> VoiceAssistant | None:
        """Find a controller's microphone and speaker, unless the engine's doors are a replay's.

        A replay never touches real devices (BUGS.md #208): the doors of a replay (or of a
        rebaseline or playback) serve recorded devices, and there the voice assistant is not
        started, so a recorded mic press neither listens nor calls the AI service. Live play
        (and a recording, whose doors wrap the live ones) has the real device registry.

        Returns:
            The voice assistant, or None in a replay or when no controller has audio.

        """
        if not isinstance(active_sources().devices(), LiveDeviceRegistry):
            log.info('Replaying: the voice assistant stays off (a replay uses no real devices)')
            return None
        return VoiceAssistant.discover()

    @staticmethod
    @override
    def _create_action_map(*, input_mode: str) -> ActionMap:
        """Bind the shared controls, then the gamepad's mic button (the voice assistant).

        Args:
            input_mode: Gamepad event family ('joystick', 'controller' or 'auto').

        Returns:
            The action map (the golden replays' controls check reads it too).

        """
        actions = BraveAdventurerSceneBase._create_action_map(input_mode=input_mode)

        # Mic mute button — bind both APIs since button indices differ
        actions.bind(
            'mic_toggle',
            controller_button=MIC_BUTTON_CONTROLLER,
            joystick_button=MIC_BUTTON_JOYSTICK,
        )
        return actions

    def _player_feet_below_world_y(self: Self) -> int:
        """Return how far below world_y the player's hitbox bottom (visible feet) is.

        Returns:
            int: The hitbox's offset from the snapped world y plus its height.

        """
        _, player_offset_y = collision_rect_offset(self.player)
        return player_offset_y + get_sprite_collision_rect(self.player).height

    @override
    def _player_top_and_foot_line(self: Self, player_rect: pygame.Rect) -> tuple[int, int]:
        """Return the player's hitbox top and bottom: the bottom is its visible feet.

        Vertical contact uses the hitbox bottom: the figure's visible feet end 1 px above its
        48 px image, so standing on PLAYER_HEIGHT floated it.

        Args:
            player_rect: The player's collision rect (hitbox) in world pixels.

        Returns:
            tuple[int, int]: The hitbox's top and bottom.

        """
        return player_rect.top, player_rect.bottom

    @override
    def _player_world_y_standing_on(self: Self, surface_y: int) -> float:
        """Return the world y that stands the hitbox bottom on a surface (a float).

        Args:
            surface_y: The world y of the ground's or a wall's top.

        Returns:
            float: The player's world y.

        """
        return float(surface_y - self._player_feet_below_world_y())

    @override
    def _scarab_class(self: Self) -> type[Scarab]:
        """Return this game's scarab (imported here, where the terrain collision imported it).

        Returns:
            type[Scarab]: The scarab class.

        """
        from brave_adventurer.enemies import Scarab

        return Scarab

    # -----------------------------------------------------------------------
    # Voice assistant (the shared scene's hooks: Papyrus has none)
    # -----------------------------------------------------------------------

    @override
    def _update_voice_assistant(self: Self) -> None:
        """Check for completed voice assistant responses."""
        if self.voice_assistant is not None:
            self.voice_assistant.update()

    @override
    def _on_voice_button_down(self: Self, action: str | None) -> None:
        """Start listening when the mic button is pressed (and a voice assistant was found).

        Args:
            action: The pressed button's action (None when it has no binding).

        """
        if action == 'mic_toggle' and self.voice_assistant is not None:
            self.voice_assistant.start_listening()

    @override
    def _on_voice_button_up(self: Self, event: ControllerButtonEvent | JoyButtonEvent) -> None:
        """Answer the question asked when the mic button is released.

        Args:
            event: The controller or joystick button up event.

        """
        action = self.actions.get_action(event)
        if action == 'mic_toggle' and self.voice_assistant is not None:
            self.voice_assistant.stop_listening_and_respond()


def main() -> None:
    """Run the Brave Adventurer game."""
    GameEngine(game=BraveAdventurerScene).start()


if __name__ == '__main__':
    main()
