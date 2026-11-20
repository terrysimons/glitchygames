"""The game over: the TV switches off, GAME OVER shows, and the title returns.

Feature plan 7 (plans/2026-11-15-zombies-aint-my-neighbors-7-neighbors-and-lives.md), Task 8;
character BOM decision 5, less the villain's laugh until he is drawn. The picture collapses to a
bright line, then to a dot, then goes dark (``SWITCH_OFF_SECONDS``), as an old TV switching off
does: a screen-space sprite drawn in code each frame (``SwitchOff``). GAME OVER then shows; after
``GAME_OVER_SECONDS``, or a joined player's start, the title returns with everyone still joined.

Feature plan 11 (plans/2026-11-18-zombies-aint-my-neighbors-11-the-rest-of-the-sounds.md): the
tube's whine falls away with the picture (``switch-off``), and the organ's dun, dun, DUNNN
(``music.GAME_OVER``) plays as the words show.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, override

import pygame

from zombies_aint_my_neighbors import music, text
from zombies_aint_my_neighbors.roster_scene import RosterScene
from zombies_aint_my_neighbors.sounds import SWITCH_OFF, sound_reference

if TYPE_CHECKING:
    from glitchygames.audio import Sound
    from zombies_aint_my_neighbors.roster import DeviceIdentity, JoinRoster

SWITCH_OFF_SECONDS: Final = 0.6
GAME_OVER_SECONDS: Final = 4.0
# The switch-off's steps: the picture squashes to a line, the line shrinks to a dot, the dot fades
_SQUASH_SECONDS: Final = 0.3
_SHRINK_SECONDS: Final = 0.2
_LINE_HEIGHT: Final = 2
_DOT_SIZE: Final = 4
DARK: Final = (8, 8, 12)
GLOW: Final = (236, 240, 255)
GAME_OVER_TEXT: Final = 'GAME OVER'
GAME_OVER_COLOUR: Final = (230, 230, 210)
GAME_OVER_LARGEST_FONT_SIZE: Final = 48
# How much of the screen's width the words may use
TEXT_WIDTH_FRACTION: Final = 0.7


def switch_off_picture(*, size: tuple[int, int], seconds: float) -> pygame.Surface:
    """Return the screen at a moment of switching off.

    The glowing picture squashes to a line, the line shrinks to a dot, then the screen is dark.

    Args:
        size: The screen's size.
        seconds: Seconds since the switch-off began.

    Returns:
        A screen-sized picture.

    """
    width, height = size
    picture = pygame.Surface(size)
    picture.fill(DARK)
    centre_x, centre_y = width // 2, height // 2
    if seconds < _SQUASH_SECONDS:
        left = 1.0 - seconds / _SQUASH_SECONDS
        band = max(_LINE_HEIGHT, round(height * left))
        picture.fill(GLOW, pygame.Rect(0, centre_y - band // 2, width, band))
    elif seconds < _SQUASH_SECONDS + _SHRINK_SECONDS:
        left = 1.0 - (seconds - _SQUASH_SECONDS) / _SHRINK_SECONDS
        line = max(_DOT_SIZE, round(width * left))
        picture.fill(GLOW, pygame.Rect(centre_x - line // 2, centre_y - 1, line, _LINE_HEIGHT))
    elif seconds < SWITCH_OFF_SECONDS:
        picture.fill(
            GLOW,
            pygame.Rect(centre_x - _DOT_SIZE // 2, centre_y - _DOT_SIZE // 2, _DOT_SIZE, _DOT_SIZE),
        )
    return picture


class GameOverScene(RosterScene):
    """The TV switching off, then GAME OVER, then the title."""

    NAME = text.GAME_NAME
    VERSION = '1.0'

    @override
    def __init__(
        self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
        roster: JoinRoster | dict[str, Any] | None = None,
    ) -> None:
        """Make the game over for the players who were playing.

        Args:
            options: The engine's options.
            groups: The sprite groups to draw into (a new LayeredDirty when None).
            roster: The players: a roster, its JSON form (as a replay passes it back), or None.

        """
        super().__init__(options=options, groups=groups, roster=roster)
        self.background_color = DARK
        self._screen_picture: text.TextPicture | None = None
        self._game_over_text: text.TextPicture | None = None
        # Its sounds, got in setup, and whether each has played
        self._switch_off_sound: Sound | None = None
        self._game_over_music: Sound | None = None
        self._switched_off = False
        self._sting_played = False

    @property
    def switch_off_sound(self) -> Sound:
        """The tube's whine falling away (after ``setup``).

        Raises:
            RuntimeError: Before ``setup``.

        """
        if self._switch_off_sound is None:
            message = 'the game over is not set up'
            raise RuntimeError(message)
        return self._switch_off_sound

    @property
    def game_over_music(self) -> Sound:
        """The organ's dun, dun, DUNNN: the game over cue, one sound (after ``setup``).

        Raises:
            RuntimeError: Before ``setup``.

        """
        if self._game_over_music is None:
            message = 'the game over is not set up'
            raise RuntimeError(message)
        return self._game_over_music

    @property
    def screen_picture(self) -> text.TextPicture:
        """The switch-off picture (after ``setup``).

        Raises:
            RuntimeError: Before ``setup``.

        """
        if self._screen_picture is None:
            message = 'the game over is not set up'
            raise RuntimeError(message)
        return self._screen_picture

    @property
    def game_over_text(self) -> text.TextPicture:
        """GAME OVER (after ``setup``).

        Raises:
            RuntimeError: Before ``setup``.

        """
        if self._game_over_text is None:
            message = 'the game over is not set up'
            raise RuntimeError(message)
        return self._game_over_text

    @override
    def setup(self) -> None:
        """Get the sounds, make the switch-off's picture and the words (once each)."""
        super().setup()
        if self._switch_off_sound is None:
            audio = self.scene_manager.audio
            self._switch_off_sound = audio.sound(sound_reference(SWITCH_OFF))
            self._game_over_music = music.cue_sound(audio, music.GAME_OVER)
        if self._game_over_text is not None:
            return
        size = (self.screen_width, self.screen_height)
        self._screen_picture = text.TextPicture(
            image=switch_off_picture(size=size, seconds=0.0),
            centre=(self.screen_width // 2, self.screen_height // 2),
            name='Switch-off',
            groups=self.all_sprites,
        )
        font = text.fitted_title_font(
            texts=(GAME_OVER_TEXT,),
            width=int(self.screen_width * TEXT_WIDTH_FRACTION),
            largest=GAME_OVER_LARGEST_FONT_SIZE,
        )
        self._game_over_text = text.TextPicture(
            image=text.render_text(font=font, text=GAME_OVER_TEXT, colour=GAME_OVER_COLOUR),
            centre=(self.screen_width // 2, self.screen_height // 2),
            name='Game over',
            groups=self.all_sprites,
        )
        self._game_over_text.set_shown(shown=False)

    @override
    def dt_tick(self, dt: float) -> None:
        """Switch the picture off, then show GAME OVER; after its time, the title.

        Args:
            dt: The frame's time, in seconds.

        """
        super().dt_tick(dt)
        # The scene manager sets a scene up before its first tick
        self.screen_picture.show_image(
            image=switch_off_picture(
                size=(self.screen_width, self.screen_height), seconds=self.game_time
            )
        )
        words_shown = self.game_time >= SWITCH_OFF_SECONDS
        self.game_over_text.set_shown(shown=words_shown)
        if not self._switched_off:
            self.switch_off_sound.play()
            self._switched_off = True
        if words_shown and not self._sting_played:
            music.play_cue(music.GAME_OVER, self.game_over_music)
            self._sting_played = True
        if self.game_time >= GAME_OVER_SECONDS and self.next_scene is None:
            self._back_to_the_title()

    @override
    def _press_start(self, *, device: DeviceIdentity) -> None:
        """A joined player's start goes straight back to the title.

        Args:
            device: The device whose start was pressed.

        """
        if self.roster.holds(device=device):
            self._back_to_the_title()

    def _back_to_the_title(self) -> None:
        """Back to the title, everyone still joined."""
        # Imported here: the title leads, through the card and the neighborhood, back here
        from zombies_aint_my_neighbors.title import TitleScene

        self.next_scene = TitleScene(options=self.options, roster=self.roster, opening=False)
