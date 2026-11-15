"""The feature card: a TV title card, FEATURE PRESENTATION, before the neighborhood.

It shows each joined player's label in their colour for ``CARD_SECONDS``, then the neighborhood
begins; a joined player's start skips straight to it. Back (Backspace, or a pad's BACK) returns
to the title with everyone still joined, so more players can join. An unplugged pad drops its
player, and with nobody left the card goes back to the title (feature plans 1 and 4).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, override

import pygame

from zombies_aint_my_neighbors import text
from zombies_aint_my_neighbors.neighborhood import NeighborhoodScene
from zombies_aint_my_neighbors.roster import MAXIMUM_PLAYERS, PLAYER_COLOURS
from zombies_aint_my_neighbors.roster_scene import RosterScene

if TYPE_CHECKING:
    from collections.abc import Mapping

    from glitchygames.events.base import ControllerButtonEvent, JoyButtonEvent, KeyEvent
    from glitchygames.input.action_map import ActionMap
    from zombies_aint_my_neighbors.roster import DeviceIdentity, JoinRoster

CARD_TEXT: Final = 'FEATURE PRESENTATION'
CARD_COLOUR: Final = (230, 230, 210)
CARD_LARGEST_FONT_SIZE: Final = 40
LABEL_LARGEST_FONT_SIZE: Final = 32
# How much of the screen's width the card's line may use
TEXT_WIDTH_FRACTION: Final = 0.85
# How long the card shows before the neighborhood begins
CARD_SECONDS: Final = 2.0
# Back to the title: Backspace, by position, or a pad's BACK
BACK_ACTION: Final = 'back'


class FeatureCardScene(RosterScene):
    """The title card before the neighborhood: who is playing."""

    NAME = 'Feature Presentation'
    VERSION = '1.0'

    @override
    def __init__(
        self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
        roster: JoinRoster | dict[str, Any] | None = None,
    ) -> None:
        """Make the card.

        Args:
            options: The engine's options.
            groups: The sprite groups to draw into (a new LayeredDirty when None).
            roster: The players joined: a roster, its JSON form (as a replay passes it back),
                or None for nobody.

        """
        super().__init__(options=options, groups=groups, roster=roster)
        self.player_pictures: tuple[text.TextPicture, ...] = ()

    @override
    @staticmethod
    def _create_action_map(*, options: Mapping[str, Any]) -> ActionMap:
        """Bind the roster screens' controls, and back: Backspace, or a pad's BACK.

        Returns:
            The action map.

        """
        actions = RosterScene._create_action_map(options=options)
        actions.bind(
            BACK_ACTION,
            scancode=pygame.KSCAN_BACKSPACE,
            controller_button=pygame.CONTROLLER_BUTTON_BACK,
        )
        return actions

    @override
    def on_key_down_event(self, event: KeyEvent) -> None:
        """Backspace goes back to the title; other keys as on every roster screen.

        Args:
            event: The key press.

        """
        if self.actions.get_action(event) == BACK_ACTION:
            self._back_to_the_title()
        else:
            super().on_key_down_event(event)

    @override
    def on_controller_button_down_event(self, event: ControllerButtonEvent) -> None:
        """A pad's BACK goes back to the title; its other buttons as on every roster screen.

        Args:
            event: The button press.

        """
        if self.actions.get_action(event) == BACK_ACTION:
            self._back_to_the_title()
        else:
            super().on_controller_button_down_event(event)

    @override
    def on_joy_button_down_event(self, event: JoyButtonEvent) -> None:
        """BACK on the joystick layer goes back to the title too.

        Args:
            event: The button press.

        """
        if self.actions.get_action(event) == BACK_ACTION:
            self._back_to_the_title()
        else:
            super().on_joy_button_down_event(event)

    @override
    def setup(self) -> None:
        """Render the card's line and every player's label, and place them."""
        super().setup()
        if self.player_pictures:
            # Set up again (after a pause): the sprites already exist
            return
        screen_width, screen_height = self.screen_width, self.screen_height
        card_font = text.fitted_title_font(
            texts=(CARD_TEXT,),
            width=int(screen_width * TEXT_WIDTH_FRACTION),
            largest=CARD_LARGEST_FONT_SIZE,
        )
        text.TextPicture(
            image=text.render_text(font=card_font, text=CARD_TEXT, colour=CARD_COLOUR),
            centre=(screen_width // 2, screen_height // 3),
            name='Feature card',
            groups=self.all_sprites,
        )
        label_font = text.title_font(size=LABEL_LARGEST_FONT_SIZE)
        column_width = screen_width // MAXIMUM_PLAYERS
        self.player_pictures = tuple(
            text.TextPicture(
                image=text.render_text(font=label_font, text=f'P{slot_index + 1}', colour=colour),
                centre=(column_width * slot_index + column_width // 2, screen_height * 2 // 3),
                name=f'Player P{slot_index + 1}',
                groups=self.all_sprites,
            )
            for slot_index, colour in enumerate(PLAYER_COLOURS)
        )
        self._pose_players()

    @override
    def dt_tick(self, dt: float) -> None:
        """Show the labels of the players still joined; after ``CARD_SECONDS``, begin the show.

        Args:
            dt: The frame's time, in seconds.

        """
        super().dt_tick(dt)
        self._pose_players()
        if self.game_time >= CARD_SECONDS and self.next_scene is None:
            self._begin_the_neighborhood()

    @override
    def _press_start(self, *, device: DeviceIdentity) -> None:
        """A joined player's start skips the card; anyone else's does nothing.

        Args:
            device: The device whose start was pressed.

        """
        if self.roster.holds(device=device):
            self._begin_the_neighborhood()

    @override
    def _device_left(self, *, device: DeviceIdentity) -> None:
        """Drop an unplugged player; with nobody left, go back to the title.

        Args:
            device: The device that was unplugged.

        """
        super()._device_left(device=device)
        if not self.roster.joined_players:
            self._back_to_the_title()

    def _begin_the_neighborhood(self) -> None:
        """Begin the neighborhood with whoever is joined."""
        self.next_scene = NeighborhoodScene(options=self.options, roster=self.roster)

    def _back_to_the_title(self) -> None:
        """Go back to the title, keeping whoever is joined."""
        # Imported here: the title builds a feature card in turn
        from zombies_aint_my_neighbors.title import TitleScene

        self.next_scene = TitleScene(options=self.options, roster=self.roster)

    def _pose_players(self) -> None:
        """Show each joined player's label and hide the free slots'."""
        for slot_index, picture in enumerate(self.player_pictures):
            picture.set_shown(shown=self.roster.slots[slot_index] is not None)
