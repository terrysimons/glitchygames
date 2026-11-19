"""Tolerances shared by the game's timers.

Frame times add up in floats (30 sixtieths make 0.49999...), so a step ends within
``TIME_TOLERANCE`` of its time (feature plan 5). Its own module so any timer can use it without
importing the kid (``kid.py`` re-exports it, where it began).
"""

from __future__ import annotations

from typing import Final

TIME_TOLERANCE: Final = 1e-9
