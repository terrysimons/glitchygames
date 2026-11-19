"""The intro's timeline: what happens when, as one table (feature plan 12, approach A).

``INTRO_TIMELINE`` is the plan's table, read top to bottom: at a time, a sprite plays an
animation, the oval fades in, the screen shakes, the pads rumble, or the intro ends. The scene
(``intro.py``) asks ``cues_crossed`` each frame which cues the frame's span of ``game_time``
crossed, and acts on them, so a long frame fires every cue it crosses, in order, and each cue
fires exactly once. Retiming the intro is editing the numbers here.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Final, Self

from pydantic import BaseModel, ConfigDict, model_validator

if TYPE_CHECKING:
    from collections.abc import Sequence


class CueKind(StrEnum):
    """What a cue does."""

    ANIMATE = 'animate'
    OVAL_FADE_IN = 'oval-fade-in'
    SHAKE = 'shake'
    RUMBLE = 'rumble'
    END = 'end'


class IntroCue(BaseModel):
    """One line of the timeline.

    Attributes:
        at_seconds: When it fires, on the intro's ``game_time``.
        kind: What it does.
        actor: The sprite file stem it animates (``ANIMATE`` only).
        animation: The animation it plays (``ANIMATE`` only).
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    at_seconds: float
    kind: CueKind
    actor: str | None = None
    animation: str | None = None

    @model_validator(mode='after')
    def _animates_exactly_with_an_actor_and_animation(self) -> Self:
        """Refuse an ANIMATE cue missing either, and any other cue with either.

        Returns:
            The cue.

        Raises:
            ValueError: Naming the cue's kind and what it lacks or should not have.
        """
        named = (self.actor is not None, self.animation is not None)
        if self.kind is CueKind.ANIMATE and named != (True, True):
            message = 'an ANIMATE cue needs an actor and an animation'
            raise ValueError(message)
        if self.kind is not CueKind.ANIMATE and any(named):
            message = f'a {self.kind.name} cue takes no actor or animation'
            raise ValueError(message)
        return self


# The plan's table (feature plan 12, "The intro, as a timeline"), in time order: every cue spelled
# out (frozen models, so the engine-context guard sees the table is immutable)
INTRO_TIMELINE: Final[tuple[IntroCue, ...]] = (
    IntroCue(at_seconds=0.0, kind=CueKind.OVAL_FADE_IN),
    IntroCue(at_seconds=0.0, kind=CueKind.ANIMATE, actor='intro_bag_dex', animation='sit'),
    IntroCue(at_seconds=0.0, kind=CueKind.ANIMATE, actor='intro_bag_marisol', animation='sit'),
    IntroCue(at_seconds=0.0, kind=CueKind.ANIMATE, actor='intro_bag_theo', animation='sit'),
    IntroCue(at_seconds=0.0, kind=CueKind.ANIMATE, actor='intro_bag_june', animation='sit'),
    IntroCue(at_seconds=0.0, kind=CueKind.ANIMATE, actor='intro_tv', animation='show'),
    IntroCue(at_seconds=0.0, kind=CueKind.ANIMATE, actor='intro_lamp', animation='still'),
    IntroCue(at_seconds=0.0, kind=CueKind.ANIMATE, actor='intro_snacks', animation='still'),
    IntroCue(at_seconds=4.0, kind=CueKind.ANIMATE, actor='intro_tv', animation='static'),
    IntroCue(at_seconds=4.0, kind=CueKind.ANIMATE, actor='intro_lamp', animation='flicker'),
    IntroCue(at_seconds=5.5, kind=CueKind.ANIMATE, actor='intro_tv', animation='bulge'),
    IntroCue(at_seconds=6.0, kind=CueKind.ANIMATE, actor='intro_tv', animation='burst'),
    IntroCue(at_seconds=6.0, kind=CueKind.ANIMATE, actor='intro_bag_dex', animation='startled'),
    IntroCue(at_seconds=6.0, kind=CueKind.ANIMATE, actor='intro_bag_marisol', animation='startled'),
    IntroCue(at_seconds=6.0, kind=CueKind.ANIMATE, actor='intro_bag_theo', animation='startled'),
    IntroCue(at_seconds=6.0, kind=CueKind.ANIMATE, actor='intro_bag_june', animation='startled'),
    IntroCue(at_seconds=6.0, kind=CueKind.SHAKE),
    IntroCue(at_seconds=6.0, kind=CueKind.RUMBLE),
    IntroCue(at_seconds=6.3, kind=CueKind.ANIMATE, actor='intro_hands', animation='reach'),
    IntroCue(at_seconds=6.8, kind=CueKind.ANIMATE, actor='intro_zombie', animation='climb-out'),
    IntroCue(at_seconds=8.0, kind=CueKind.END),
)
# How long the intro runs: its END cue's time
INTRO_SECONDS: Final = 8.0


def cues_crossed(
    *, timeline: Sequence[IntroCue], before_seconds: float, now_seconds: float
) -> tuple[IntroCue, ...]:
    """Return the cues a frame crossed: those at ``before_seconds`` up to, not at, ``now_seconds``.

    A frame running from ``before_seconds`` to ``now_seconds`` fires the cues timed inside it; a
    cue exactly on a boundary fires on the frame that starts at it, so frame by frame each fires
    once.

    Args:
        timeline: The cues, in time order.
        before_seconds: The frame's start (the previous frame's ``game_time``).
        now_seconds: The frame's end (this frame's ``game_time``).

    Returns:
        The cues crossed, in timeline order.
    """
    return tuple(cue for cue in timeline if before_seconds <= cue.at_seconds < now_seconds)
