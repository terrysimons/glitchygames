"""Brave Adventurer's launcher: one command for both games, Classic and Papyrus.

``main()`` (brave_adventurer_modes/launcher.py) starts the game ``--game`` names, else the game a
recording to replay was made in, else the title screen (brave_adventurer_modes/title.py), which
offers both.
"""

from __future__ import annotations

from brave_adventurer_modes.launcher import (
    GAMES_BY_NAME,
    game_for_recording,
    main,
    recorded_game,
)
from brave_adventurer_modes.title import TitleScene

__all__ = [
    'GAMES_BY_NAME',
    'TitleScene',
    'game_for_recording',
    'main',
    'recorded_game',
]
