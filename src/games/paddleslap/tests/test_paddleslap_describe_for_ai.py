"""What PaddleSlap tells the AI console: what no sprite shows."""

from __future__ import annotations

from typing import Self

from paddleslap import Game


class CountOnly:
    """The two attributes the description reads."""

    rally_count = 7
    balls = (object(), object())


def test_it_says_the_score_and_the_balls_in_play() -> None:
    """Read straight from the game's own state."""
    instance: Self = CountOnly()  # type: ignore[assignment]

    assert Game.describe_for_ai(instance) == {'rally_count': 7, 'balls_in_play': 2}
