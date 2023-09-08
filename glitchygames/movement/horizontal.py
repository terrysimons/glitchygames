#!/usr/bin/env python3
"""
Horizontal:
Adds movement functions along the horizontal (X) axis to a game object
"""
from __future__ import annotations

from typing import Self


class Horizontal:
    def __init__(self: Self, speed: int) -> None:

        self.speed = speed
        self.current_speed = self.speed.x

    def _change_speed(self: Self, value: int) -> None:
        self.current_speed = value

    def left(self: Self) -> None:
        self._change_speed(-self.speed.x)

    def right(self: Self) -> None:
        self._change_speed(self.speed.x)

    def stop(self: Self) -> None:
        self._change_speed(0)
