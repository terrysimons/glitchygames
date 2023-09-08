#!/usr/bin/env python3
"""
Vertical:
Adds movement functions along the vertical (Y) axis to a game object
"""
from __future__ import annotations

from typing import Self


class Vertical:
    def __init__(self: Self, speed: int) -> None:
        self.speed = speed
        self.current_speed = self.speed.y

    def _change_speed(self: Self, value: int) -> None:
        self.current_speed = value

    def up(self: Self) -> None:
        self._change_speed(-self.speed.y)

    def down(self: Self) -> None:
        self._change_speed(self.speed.y)

    def stop(self: Self) -> None:
        self._change_speed(0)
