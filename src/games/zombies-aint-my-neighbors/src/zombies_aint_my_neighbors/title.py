"""The title screen: four player slots, each blinking PRESS START in its player's colour.

Until gameplay exists this scene is the game class, so the golden replay stays in one scene
(tests/replay/test_golden_replays.py: the header's game is the class given to GameEngine, and
the recording ends in it). Feature plan:
plans/2026-11-14-zombies-aint-my-neighbors-1-title-and-registration.md.

A start press from a device that holds no slot joins it; from a joined device it begins the
feature (the feature card, until gameplay exists). Every image is rendered once in ``setup()``;
each frame only picks which image a slot shows and whether it is shown (master plan,
decision 11).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Final, override

from glitchygames.input.state import current_input
from zombies_aint_my_neighbors import launch_showing, text
from zombies_aint_my_neighbors.roster import MAXIMUM_PLAYERS, PLAYER_COLOURS, DeviceKind
from zombies_aint_my_neighbors.roster_scene import RosterScene
from zombies_aint_my_neighbors.run_state import RunState, as_run
from zombies_aint_my_neighbors.tolerances import TIME_TOLERANCE

if TYPE_CHECKING:
    import argparse

    import pygame

    from glitchygames.events.base import ControllerButtonEvent, JoyButtonEvent, KeyEvent
    from zombies_aint_my_neighbors.roster import DeviceIdentity, JoinRoster

# Unjoined slots blink: shown this long, then hidden this long, all four in step
BLINK_SECONDS: Final = 0.5
# How long the title stands idle, nobody joined and no run, before the intro plays (feature plan
# 12's idle loop: long enough to read it and pick up a pad, short enough to start while someone
# is still looking)
IDLE_SECONDS: Final = 20.0
# The game's title, in the upper half of the screen
TITLE_TEXT: Final = "ZOMBIES AIN'T MY NEIGHBORS"
TITLE_COLOUR: Final = (230, 230, 210)
# The largest font sizes tried for the title and for the slots' lines
TITLE_LARGEST_FONT_SIZE: Final = 48
SLOT_LARGEST_FONT_SIZE: Final = 24
# How much of its width (and of the screen's) a line of text may use
TEXT_WIDTH_FRACTION: Final = 0.85
# What a slot says: unjoined, then joined from each kind of device
PRESS_START_TEXT: Final = 'PRESS START'
READY_TEXT: Final = 'READY'
DEVICE_TEXTS: Final[dict[DeviceKind, str]] = {
    DeviceKind.KEYBOARD: 'KEYBOARD',
    DeviceKind.GAMEPAD: 'GAMEPAD',
}


def slot_label(*, slot_index: int) -> str:
    """Return a slot's player label: P1 to P4.

    Returns:
        The label.

    """
    return f'P{slot_index + 1}'


class TitleScene(RosterScene):
    """Zombies Ain't My Neighbors' title screen."""

    NAME = "Zombies Ain't My Neighbors"
    VERSION = '1.0'

    @override
    def __init__(
        self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
        roster: JoinRoster | dict[str, Any] | None = None,
        run: RunState | dict[str, Any] | None = None,
        opening: bool = True,
        awaiting_release: bool = False,
    ) -> None:
        """Make the title screen.

        Args:
            options: The engine's options.
            groups: The sprite groups to draw into (a new LayeredDirty when None).
            roster: The players already joined: a roster, its JSON form (as a replay passes
                it back), or None for nobody.
            run: A run to go back to (Back on a later stage's card; feature plan 7): a run,
                its JSON form, or None, when the next start begins a new run.
            opening: Whether this is the title the engine builds at launch, which hands over to
                the intro on its first frame wherever the CRT power-on would play (feature plan
                12). Every other place that builds a title passes False (the intro's end, a
                card's Back, the last player leaving a stage, the game over).
            awaiting_release: Whether every press is ignored until a frame holds no key and no
                pad button (the title the intro hands back: the press that skipped it, still
                held or repeating, must not join anyone).

        """
        super().__init__(options=options, groups=groups, roster=roster)
        self.run = None if run is None else as_run(run)
        self.opening = opening
        self.awaiting_release = awaiting_release
        # When the title last saw a press or a join (the idle count starts from it)
        self._last_activity_seconds = 0.0
        # The opening title asks once, on its first frame, whether the intro opens the launch
        self._launch_asked = False
        self.slot_pictures: tuple[text.TextPicture, ...] = ()
        # Per slot: the unjoined image, and the joined image for each kind of device
        self._unjoined_images: tuple[pygame.Surface, ...] = ()
        self._joined_images: tuple[dict[DeviceKind, pygame.Surface], ...] = ()

    @override
    def replay_arguments(self) -> dict[str, Any]:
        """Rebuild this title as it began: the roster, the run it keeps, and whether it opens.

        Returns:
            Them, as JSON reads them back (no run key when it keeps none, no opening key for the
            opening title, so recordings made before feature plan 12 read the same).

        """
        arguments = super().replay_arguments()
        if self.run is not None:
            arguments['run'] = self.run.model_dump(mode='json')
        if not self.opening:
            arguments['opening'] = False
        if self.awaiting_release:
            arguments['awaiting_release'] = True
        return arguments

    @property
    def idle_seconds(self) -> float:
        """How long the title has stood with no press and no join, on its ``game_time``."""
        return self.game_time - self._last_activity_seconds

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add the game's own command-line options (none yet).

        Returns:
            The parser.

        """
        return parser

    @override
    def setup(self) -> None:
        """Render every image the title will show, and place the title and the slots."""
        super().setup()
        if self.slot_pictures:
            # Set up again (after a pause): the sprites already exist
            return
        screen_width, screen_height = self.screen_width, self.screen_height
        title_font = text.fitted_title_font(
            texts=(TITLE_TEXT,),
            width=int(screen_width * TEXT_WIDTH_FRACTION),
            largest=TITLE_LARGEST_FONT_SIZE,
        )
        text.TextPicture(
            image=text.render_text(font=title_font, text=TITLE_TEXT, colour=TITLE_COLOUR),
            centre=(screen_width // 2, screen_height // 3),
            name='Title',
            groups=self.all_sprites,
        )
        slot_width = screen_width // MAXIMUM_PLAYERS
        slot_texts = (
            PRESS_START_TEXT,
            *(f'{slot_label(slot_index=index)} {READY_TEXT}' for index in range(MAXIMUM_PLAYERS)),
            *DEVICE_TEXTS.values(),
        )
        slot_font = text.fitted_title_font(
            texts=slot_texts,
            width=int(slot_width * TEXT_WIDTH_FRACTION),
            largest=SLOT_LARGEST_FONT_SIZE,
        )
        unjoined: list[pygame.Surface] = []
        joined: list[dict[DeviceKind, pygame.Surface]] = []
        pictures: list[text.TextPicture] = []
        for slot_index, colour in enumerate(PLAYER_COLOURS):
            label = slot_label(slot_index=slot_index)
            unjoined.append(
                text.render_lines(font=slot_font, lines=(label, PRESS_START_TEXT), colour=colour)
            )
            joined.append({
                kind: text.render_lines(
                    font=slot_font, lines=(f'{label} {READY_TEXT}', device_text), colour=colour
                )
                for kind, device_text in DEVICE_TEXTS.items()
            })
            pictures.append(
                text.TextPicture(
                    image=unjoined[slot_index],
                    centre=(slot_width * slot_index + slot_width // 2, screen_height * 7 // 8),
                    name=f'Slot {label}',
                    groups=self.all_sprites,
                )
            )
        self._unjoined_images = tuple(unjoined)
        self._joined_images = tuple(joined)
        self.slot_pictures = tuple(pictures)
        self._pose_slots()

    @override
    def dt_tick(self, dt: float) -> None:
        """Pose the slots for this frame: joined ones steady, free ones blinking.

        Args:
            dt: The frame's time, in seconds.

        """
        super().dt_tick(dt)
        self._pose_slots()
        self._open_with_the_intro()
        self._wait_for_release()
        self._loop_to_the_intro()

    def _wait_for_release(self) -> None:
        """Stop ignoring presses on the first frame that holds no key and no pad button."""
        if not self.awaiting_release:
            return
        snapshot = current_input()
        held_buttons = any(
            any(buttons)
            for layer in (snapshot.device_buttons, snapshot.controller_buttons)
            for buttons in layer.values()
        )
        if not snapshot.pressed_scancodes and not held_buttons:
            self.awaiting_release = False

    def _loop_to_the_intro(self) -> None:
        """Idle long enough, nobody joined and no run: hand over to the intro, unattended."""
        if (
            self.next_scene is not None
            or self.roster.joined_players
            or self.run is not None
            or self.idle_seconds < IDLE_SECONDS - TIME_TOLERANCE
        ):
            return
        # Imported here: the intro returns to a title in turn
        from zombies_aint_my_neighbors.intro import IntroScene, IntroShowing

        self.next_scene = IntroScene(options=self.options, showing=IntroShowing.LOOP)

    def _note_activity(self) -> None:
        """A press or a join: the idle count starts again."""
        self._last_activity_seconds = self.game_time

    @override
    def on_key_down_event(self, event: KeyEvent) -> None:
        """Any key is activity; while awaiting release no key does anything else.

        Args:
            event: The key press.

        """
        self._note_activity()
        if not self.awaiting_release:
            super().on_key_down_event(event)

    @override
    def on_controller_button_down_event(self, event: ControllerButtonEvent) -> None:
        """Any pad button is activity; while awaiting release none does anything else.

        Args:
            event: The button press.

        """
        self._note_activity()
        if not self.awaiting_release:
            super().on_controller_button_down_event(event)

    @override
    def on_joy_button_down_event(self, event: JoyButtonEvent) -> None:
        """Any joystick-layer button is activity; while awaiting release none does else.

        Args:
            event: The button press.

        """
        self._note_activity()
        if not self.awaiting_release:
            super().on_joy_button_down_event(event)

    def _open_with_the_intro(self) -> None:
        """On the opening title's first frame, hand over to the intro if the launch shows it."""
        if not self.opening or self._launch_asked:
            return
        self._launch_asked = True
        if launch_showing.launch_showing_allowed(
            options=self.options, video_driver=launch_showing.current_video_driver()
        ):
            # Imported here: the intro returns to a title in turn
            from zombies_aint_my_neighbors.intro import IntroScene, IntroShowing

            self.next_scene = IntroScene(options=self.options, showing=IntroShowing.LAUNCH)

    @override
    def _press_start(self, *, device: DeviceIdentity) -> None:
        """Join a device that holds no slot; a joined device's start begins the feature.

        Args:
            device: The device whose start was pressed.

        """
        if self.roster.holds(device=device):
            # Imported here: the feature card builds a title in turn
            from zombies_aint_my_neighbors.feature_card import FeatureCardScene

            self.next_scene = FeatureCardScene(
                options=self.options, roster=self.roster, run=self.run
            )
            return
        self.roster = self.roster.join(device=device)
        self._note_activity()

    def _pose_slots(self) -> None:
        """Show each slot's image for the roster, and blink the free slots on game time."""
        blink_lit = math.floor(self.game_time / BLINK_SECONDS) % 2 == 0
        for slot_index, picture in enumerate(self.slot_pictures):
            player = self.roster.slots[slot_index]
            if player is None:
                picture.show_image(image=self._unjoined_images[slot_index])
                picture.set_shown(shown=blink_lit)
            else:
                picture.show_image(image=self._joined_images[slot_index][player.device.kind])
                picture.set_shown(shown=True)
