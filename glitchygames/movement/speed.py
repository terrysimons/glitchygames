#!/usr/bin/env python3
from __future__ import annotations

from typing import Self


class Speed:
    def __init__(self: Self, x: int = 0, y: int = 0, increment: float = 0.2) -> None:
        self.x = x
        self.y = y
        self.increment = increment

    def speed_up(self: Self) -> None:
        self.speed_up_horizontal()
        self.speed_up_vertical()

    def speed_up_horizontal(self: Self) -> None:
        self.x += self.increment if self.x >= 0 else self.increment * -1

    def speed_up_vertical(self: Self) -> None:
        self.y += self.increment if self.y >= 0 else self.increment * -1
