"""The attract demo: the idle loop's second slot, after the intro (feature plan 13).

When nobody plays, the title loops: the title, the intro, then this demo, then the title again.
The demo is the game's bundled demo, ``demos/neighborhood_four_kids.jsonl.gz``: four kids
clearing stage 1 (recorded by ``scripts/record_bundled_demos.py``). The scene replays it as an
inner game (``glitchygames.inner_game.InnerGame.replay``, as the Arcade replays its tiles) on a
render target of the size it was recorded at, and draws that picture scaled to the screen,
letterboxed when the shapes differ, under a DEMO label. It is heard, as the intro is. Its pads
are the recording's stand-ins, so nothing it does rumbles a real pad.

Any key press or pad button ends it at once, P and Esc included; releases, sticks, hats and pads
arriving or leaving do not. The title that follows a press waits for that input's release, so
the press joins nobody. At the demo's end the title follows too, and a demo that can't play
(not installed, unreadable, another size, failing mid-way) sends the game straight back to the
title with a warning. Every way it ends finishes the inner game exactly once, which gives its
sound channels back for the next showing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final, override

import pygame

from glitchygames.bundled_demos import bundled_demos
from glitchygames.inner_game import InnerGame, InnerGameState
from glitchygames.sprites.root_sprite import RootSprite
from zombies_aint_my_neighbors import text
from zombies_aint_my_neighbors.pad_tolerant import PadTolerantScene

if TYPE_CHECKING:
    from pathlib import Path

    from glitchygames.events.base import ControllerButtonEvent, JoyButtonEvent, KeyEvent

LOG = logging.getLogger('game.zombies_aint_my_neighbors.attract')

# The demo: its file in the package's demos directory, the size it was recorded at (an inner
# game replays only at its recorded size), and the console script that replays it
DEMO_NAME: Final = 'neighborhood_four_kids.jsonl.gz'
DEMO_SIZE: Final = (800, 480)
DEMO_COMMAND: Final = 'zombies-aint-my-neighbors'
DEMO_PACKAGE: Final = 'zombies_aint_my_neighbors'
# The bars round a picture of another shape than the screen, and the label
LETTERBOX_COLOUR: Final = (22, 18, 34)
LABEL_TEXT: Final = 'DEMO'
LABEL_COLOUR: Final = (250, 206, 72)
LABEL_FONT_SIZE: Final = 40
# The label's centre, as fractions of the screen: below the HUD's player row, centred
LABEL_CENTRE: Final = (0.5, 0.16)


def attract_demo_path() -> Path | None:
    """Return the shipped demo where the package is installed, or None when it isn't there.

    Returns:
        Its path.

    """
    return next(
        (
            demo.path
            for demo in bundled_demos(packages=(DEMO_PACKAGE,))
            if demo.path.name == DEMO_NAME
        ),
        None,
    )


def fitted_rect(*, picture_size: tuple[int, int], screen_size: tuple[int, int]) -> pygame.Rect:
    """Return where a picture goes on a screen: as large as fits, its shape kept, centred.

    Returns:
        The picture's place on the screen.

    """
    picture_width, picture_height = picture_size
    screen_width, screen_height = screen_size
    scale = min(screen_width / picture_width, screen_height / picture_height)
    area = pygame.Rect(0, 0, round(picture_width * scale), round(picture_height * scale))
    area.center = (screen_width // 2, screen_height // 2)
    return area


class DemoPicture(RootSprite):
    """The whole screen: the demo's picture, fitted, with bars where the shapes differ."""

    def __init__(self, *, size: tuple[int, int], groups: pygame.sprite.LayeredDirty[Any]) -> None:
        """Make the screen-sized picture, all bars until the demo draws.

        Args:
            size: The screen's size.
            groups: The scene's sprites.

        """
        super().__init__(groups=groups)
        self.image = pygame.Surface(size)
        self.image.fill(LETTERBOX_COLOUR)
        self.rect = self.image.get_rect()
        self.name = 'Attract demo picture'
        self.dirty = 2
        self._area = fitted_rect(picture_size=DEMO_SIZE, screen_size=size)

    def show(self, *, picture: pygame.Surface) -> None:
        """Show the demo's latest frame, scaled into its place."""
        if self._area.size == picture.get_size():
            self.image.blit(picture, self._area)
        else:
            self.image.blit(pygame.transform.scale(picture, self._area.size), self._area)


class AttractScene(PadTolerantScene):
    """The attract demo: the shipped demo replayed inside the game, under a DEMO label."""

    NAME = 'Attract demo'
    VERSION = '1.0'

    @override
    def __init__(
        self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Make the attract scene.

        Args:
            options: The engine's options.
            groups: The sprite groups to draw into (a new LayeredDirty when None).

        """
        super().__init__(options=options, groups=groups)
        self.background_color = LETTERBOX_COLOUR
        self.label: text.TextPicture | None = None
        # The demo playing and the picture it shows on, until it is finished
        self._showing: tuple[InnerGame, DemoPicture] | None = None
        self._set_up = False

    @property
    def inner_game(self) -> InnerGame | None:
        """The demo's inner game while it plays; None before, and once it is finished."""
        return None if self._showing is None else self._showing[0]

    @override
    def replay_arguments(self) -> dict[str, Any]:
        """Rebuild this scene as it began: it takes nothing, always playing the shipped demo.

        Returns:
            No arguments.

        """
        return {}

    @override
    def setup(self) -> None:
        """Draw the picture and the label, then build the demo (once: a resume keeps it)."""
        super().setup()
        if self._set_up:
            return
        self._set_up = True
        size = (self.screen_width, self.screen_height)
        picture = DemoPicture(size=size, groups=self.all_sprites)
        font = text.title_font(size=LABEL_FONT_SIZE)
        self.label = text.TextPicture(
            image=text.render_text(font=font, text=LABEL_TEXT, colour=LABEL_COLOUR),
            centre=(round(size[0] * LABEL_CENTRE[0]), round(size[1] * LABEL_CENTRE[1])),
            name='Attract demo label',
            groups=self.all_sprites,
        )
        self.all_sprites.move_to_front(self.label)
        self._build_the_demo(picture=picture)

    def _build_the_demo(self, *, picture: DemoPicture) -> None:
        """Build the demo's inner game and make it heard; on any failure, back to the title.

        ``InnerGame.replay`` refuses only arguments its caller adds (the outer game's own are
        filtered first), and this scene adds none, so its refusal is never met here.
        """
        path = attract_demo_path()
        if path is None:
            self._give_up(reason=f'the demo {DEMO_NAME} is not installed')
            return
        game = InnerGame.replay(
            command=DEMO_COMMAND, path=path, name='attract demo', size=DEMO_SIZE
        )
        self._showing = (game, picture)
        if game.outcome.state is not InnerGameState.RUNNING:
            self._give_up(reason=f'{path.name} could not start: {game.outcome.error}')
            return
        game.set_audible(audible=True)
        picture.show(picture=game.surface)

    @override
    def dt_tick(self, dt: float) -> None:
        """Run the demo one frame (the host's frame paces it) and show it; at its end, the title.

        Args:
            dt: The frame's time, in seconds.

        """
        super().dt_tick(dt)
        if self._showing is None:
            return
        game, picture = self._showing
        running = game.step()
        picture.show(picture=game.surface)
        if running:
            return
        # step() finishes a game that has ended or failed: it is not finished again
        self._showing = None
        if game.outcome.state is InnerGameState.FAILED:
            self._give_up(reason=f'the demo failed: {game.outcome.error}')
            return
        self._to_the_title(awaiting_release=False)

    def _give_up(self, *, reason: str) -> None:
        """Log why the demo can't play and go back to the title."""
        LOG.warning('No attract demo this time: %s', reason)
        self._to_the_title(awaiting_release=False)

    def _to_the_title(self, *, awaiting_release: bool) -> None:
        """Finish the demo (silencing it) and hand over to the title (once).

        Args:
            awaiting_release: True after a press: the title ignores that input until it is up.

        """
        self._finish_the_demo()
        if self.next_scene is not None:
            return
        # Imported here: the title builds the intro, which builds this scene
        from zombies_aint_my_neighbors.title import TitleScene

        self.next_scene = TitleScene(
            options=self.options, opening=False, awaiting_release=awaiting_release
        )

    def _finish_the_demo(self) -> None:
        """Finish the inner game, once: it goes silent and gives its sound channels back."""
        showing, self._showing = self._showing, None
        if showing is not None:
            showing[0].finish()

    @override
    def cleanup(self) -> None:
        """Finish the demo however the scene ends (a hand-over, the game quitting)."""
        self._finish_the_demo()
        super().cleanup()

    @override
    def on_key_down_event(self, event: KeyEvent) -> None:
        """Any key ends the demo, P and Esc included (the demo has no pause)."""
        self._to_the_title(awaiting_release=True)

    @override
    def on_key_up_event(self, event: KeyEvent) -> None:
        """A release is no press: nothing happens."""

    @override
    def on_controller_button_down_event(self, event: ControllerButtonEvent) -> None:
        """Any pad button ends the demo."""
        self._to_the_title(awaiting_release=True)

    @override
    def on_controller_button_up_event(self, event: ControllerButtonEvent) -> None:
        """A release is no press: nothing happens."""

    @override
    def on_joy_button_down_event(self, event: JoyButtonEvent) -> None:
        """Any button on the joystick layer ends the demo."""
        self._to_the_title(awaiting_release=True)

    @override
    def on_joy_button_up_event(self, event: JoyButtonEvent) -> None:
        """A release is no press: nothing happens."""
