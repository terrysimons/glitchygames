"""The intro: the sleepover, and the monsters coming out of the TV (feature plan 12).

The scene stages the intro's sprites (``art/intro_rig.py``) on the screen and plays the timeline
(``intro_timeline.INTRO_TIMELINE``): each frame it acts on the cues the frame's span of
``game_time`` crossed (``cues_crossed``), so every cue fires exactly once, in order, even across
a hitch. A dark oval frames the shot. At the burst the screen shakes, and at launch
(``IntroShowing.LAUNCH``) every connected pad rumbles; in the title's idle loop
(``IntroShowing.LOOP``) nothing rumbles: nobody may be holding a pad (the owner, 2026-11-19).

Any key press or pad button ends it at once, P included (the intro has no pause); releases,
sticks, hats and pads arriving or leaving do not. At its end, or a skip, the title follows.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, override

import pygame

from glitchygames.effects.shake import Shake, ShakeStyle, ShakeTarget
from glitchygames.sprites import AnimatedSprite
from glitchygames.sprites.root_sprite import RootSprite
from zombies_aint_my_neighbors.art.intro_rig import INTRO_ANIMATIONS
from zombies_aint_my_neighbors.intro_timeline import INTRO_TIMELINE, CueKind, IntroCue, cues_crossed
from zombies_aint_my_neighbors.pad_tolerant import PadTolerantScene
from zombies_aint_my_neighbors.sounds import (
    GROANS,
    SOUND_REFERENCES,
    TV_DESTROYED,
    TV_SPAWN,
    sound_reference,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from glitchygames.audio.library import Sound
    from glitchygames.events.base import (
        ControllerButtonEvent,
        JoyButtonEvent,
        KeyEvent,
    )

SPRITES_DIRECTORY: Final = Path(__file__).resolve().parent / 'sprites'
# The intro's sprites are drawn 3x: the 64-pixel TV fills 192 of the screen's 480 rows
INTRO_SCALE: Final = 3
# The burst's shake (the screen's, not the world's: the intro has no camera), and the rumble a
# launch showing sends to every pad: the TV-destroyed rumble's shape, stronger and longer
INTRO_BURST_SHAKE: Final = Shake(style=ShakeStyle.NOISE, strength=6.0, duration=0.5, frequency=24.0)
INTRO_RUMBLE_LOW: Final = 1.0
INTRO_RUMBLE_HIGH: Final = 0.7
INTRO_RUMBLE_MILLISECONDS: Final = 600
# The oval: everything outside it this dark, fading in over its first half second
OVAL_COLOUR: Final = (10, 8, 16)
OVAL_FADE_SECONDS: Final = 0.5
# The oval's half-width and half-height, as fractions of the screen's
OVAL_RADII: Final = (0.47, 0.47)
BACKGROUND_COLOUR: Final = (22, 18, 34)
# What plays with an animation's cue
CUE_SOUNDS: Final[Mapping[tuple[str, str], str]] = {
    ('intro_tv', 'bulge'): TV_SPAWN,
    ('intro_tv', 'burst'): TV_DESTROYED,
    ('intro_zombie', 'climb-out'): GROANS[0],
}
# Shown only from their cue on
_WAIT_FOR_THEIR_CUE: Final = frozenset({'intro_hands', 'intro_zombie'})


class IntroShowing(StrEnum):
    """Why the intro is playing: at launch (pads rumble), or unattended in the title's loop."""

    LAUNCH = 'launch'
    LOOP = 'loop'


class IntroActor(AnimatedSprite):
    """One of the intro's sprites, drawn at ``INTRO_SCALE`` in screen space."""

    def __init__(self, *, stem: str, groups: pygame.sprite.LayeredDirty[Any]) -> None:
        """Load an intro sprite.

        Args:
            stem: Its sprite file's stem (a key of ``INTRO_ANIMATIONS``).
            groups: The scene's sprites.

        """
        super().__init__(filename=str(SPRITES_DIRECTORY / f'{stem}.toml'), groups=groups)
        self.scale = INTRO_SCALE
        self.dirty = 2

    @override
    def update(self, dt: float = 0.016) -> None:
        """Do nothing: the animation advances in the scene's ``dt_tick`` only (``advance``)."""

    def advance(self, dt: float) -> None:
        """Advance the animation by a frame's time."""
        AnimatedSprite.update(self, dt)


class Oval(RootSprite):
    """The dark frame round the shot: the whole screen, clear inside an oval, fading in."""

    def __init__(self, *, size: tuple[int, int], groups: pygame.sprite.LayeredDirty[Any]) -> None:
        """Draw the oval once.

        Args:
            size: The screen's size.
            groups: The scene's sprites.

        """
        super().__init__(groups=groups)
        width, height = size
        self.image = pygame.Surface(size, pygame.SRCALPHA)
        self.image.fill((*OVAL_COLOUR, 255))
        radius_x, radius_y = width * OVAL_RADII[0], height * OVAL_RADII[1]
        hole = pygame.Rect(0, 0, round(radius_x * 2), round(radius_y * 2))
        hole.center = (width // 2, height // 2)
        pygame.draw.ellipse(self.image, (0, 0, 0, 0), hole)
        self.rect = self.image.get_rect()
        self.name = 'Intro oval'
        self.dirty = 2
        self.fade(seconds=0.0)

    def fade(self, *, seconds: float) -> None:
        """Show the oval as far faded in as ``seconds`` since it began."""
        self.image.set_alpha(round(255 * min(1.0, max(0.0, seconds / OVAL_FADE_SECONDS))))


class IntroScene(PadTolerantScene):
    """The intro: the sleepover, the TV bursting, the Lawn Zombie climbing out."""

    NAME = 'Intro'
    VERSION = '1.0'
    SOUNDS = SOUND_REFERENCES

    @override
    def __init__(
        self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
        showing: IntroShowing | str = IntroShowing.LOOP,
    ) -> None:
        """Make the intro.

        Args:
            options: The engine's options.
            groups: The sprite groups to draw into (a new LayeredDirty when None).
            showing: At launch (pads rumble) or in the title's idle loop (nothing rumbles), or
                its JSON form, as a replay passes it back.

        """
        super().__init__(options=options, groups=groups)
        self.showing = IntroShowing(showing)
        self.background_color = BACKGROUND_COLOUR
        self.actors: dict[str, IntroActor] = {}
        self.fired: tuple[IntroCue, ...] = ()
        self._oval: Oval | None = None
        self._oval_began: float | None = None
        self._sounds: dict[str, Sound] = {}
        self._before_seconds = 0.0

    @override
    def replay_arguments(self) -> dict[str, Any]:
        """Rebuild this intro as it began: how it is showing.

        Returns:
            The showing, as JSON reads it back.

        """
        return {'showing': self.showing.value}

    @override
    def setup(self) -> None:
        """Stage every sprite, draw the oval, and request the sounds (once each)."""
        super().setup()
        if self.actors:
            return
        audio = self.scene_manager.audio
        self._sounds = {
            name: audio.sound(sound_reference(name)) for name in set(CUE_SOUNDS.values())
        }
        for stem in INTRO_ANIMATIONS:
            actor = IntroActor(stem=stem, groups=self.all_sprites)
            actor.play(INTRO_ANIMATIONS[stem][0].state)
            actor.visible = 0 if stem in _WAIT_FOR_THEIR_CUE else 1
            self.actors[stem] = actor
        self._stage()
        self._oval = Oval(size=(self.screen_width, self.screen_height), groups=self.all_sprites)
        self.all_sprites.move_to_front(self._oval)

    def _stage(self) -> None:
        """Place the set: the TV centred above the four bags, the lamp and the popcorn beside it.

        The hands and the zombie are drawn on the TV's canvas, so they stand where it does.
        """
        width, height = self.screen_width, self.screen_height
        tv_bottom = height * 5 // 8
        for stem in ('intro_tv', 'intro_hands', 'intro_zombie'):
            self.actors[stem].rect.midbottom = (width // 2, tv_bottom)
        bags = [stem for stem in INTRO_ANIMATIONS if stem.startswith('intro_bag_')]
        bag_width = self.actors[bags[0]].rect.width
        row_left = (width - bag_width * len(bags)) // 2
        for index, stem in enumerate(bags):
            self.actors[stem].rect.midbottom = (
                row_left + bag_width * index + bag_width // 2,
                height * 15 // 16,
            )
        self.actors['intro_lamp'].rect.midbottom = (width // 4, tv_bottom)
        self.actors['intro_snacks'].rect.midbottom = (width * 3 // 4, tv_bottom)

    @override
    def dt_tick(self, dt: float) -> None:
        """Act on the cues this frame crossed, then advance every animation and the oval's fade.

        Args:
            dt: The frame's time, in seconds.

        """
        super().dt_tick(dt)
        crossed = cues_crossed(
            timeline=INTRO_TIMELINE, before_seconds=self._before_seconds, now_seconds=self.game_time
        )
        self._before_seconds = self.game_time
        for cue in crossed:
            self._act(cue)
        self.fired += crossed
        for actor in self.actors.values():
            actor.advance(dt)
        if self._oval is not None and self._oval_began is not None:
            self._oval.fade(seconds=self.game_time - self._oval_began)

    def _act(self, cue: IntroCue) -> None:
        """Do what one cue says."""
        if cue.kind is CueKind.ANIMATE and cue.actor is not None and cue.animation is not None:
            actor = self.actors[cue.actor]
            actor.visible = 1
            actor.play(cue.animation)
            sound = CUE_SOUNDS.get((cue.actor, cue.animation))
            if sound is not None:
                self._sounds[sound].play()
        elif cue.kind is CueKind.OVAL_FADE_IN:
            self._oval_began = cue.at_seconds
        elif cue.kind is CueKind.SHAKE:
            self.shake(INTRO_BURST_SHAKE, targets=ShakeTarget.SCREEN)
        elif cue.kind is CueKind.RUMBLE:
            self._rumble()
        elif cue.kind is CueKind.END:
            self._to_the_title()

    def _rumble(self) -> None:
        """At launch, rumble every connected pad; in the idle loop nothing: nobody may hold one."""
        if self.showing is not IntroShowing.LAUNCH:
            return
        for device in self.input_devices:
            device.rumble(
                low_frequency=INTRO_RUMBLE_LOW,
                high_frequency=INTRO_RUMBLE_HIGH,
                duration_milliseconds=INTRO_RUMBLE_MILLISECONDS,
            )

    def _to_the_title(self) -> None:
        """Hand over to the title (once)."""
        if self.next_scene is not None:
            return
        # Imported here: the title builds the intro in turn
        from zombies_aint_my_neighbors.title import TitleScene

        self.next_scene = TitleScene(options=self.options, opening=False, awaiting_release=True)

    @override
    def on_key_down_event(self, event: KeyEvent) -> None:
        """Any key skips the intro, P included (the intro has no pause)."""
        self._to_the_title()

    @override
    def on_key_up_event(self, event: KeyEvent) -> None:
        """A release is no press: nothing happens."""

    @override
    def on_controller_button_down_event(self, event: ControllerButtonEvent) -> None:
        """Any pad button skips the intro."""
        self._to_the_title()

    @override
    def on_controller_button_up_event(self, event: ControllerButtonEvent) -> None:
        """A release is no press: nothing happens."""

    @override
    def on_joy_button_down_event(self, event: JoyButtonEvent) -> None:
        """Any button on the joystick layer skips the intro."""
        self._to_the_title()

    @override
    def on_joy_button_up_event(self, event: JoyButtonEvent) -> None:
        """A release is no press: nothing happens."""
