#!/usr/bin/env python3
"""Speed.

This is a simple speed class that can be used to speed up sprites.
"""

from __future__ import annotations

from typing import Self


class Speed:
    """Speed."""

    def __init__(self: Self, x: int = 0, y: int = 0, increment: float = 0.2) -> None:
        """Initialize the speed.

        Args:
            x (int): The x speed.
            y (int): The y speed.
            increment (float): The amount to increment the speed by.

        Returns:
            None

        """
        self.x = x
        self.y = y
        self.increment = increment

    def speed_up(self: Self) -> None:
        """Speed up.

        Args:
            None

        Returns:
            None

        """
        self.speed_up_horizontal()
        self.speed_up_vertical()

    def speed_up_horizontal(self: Self) -> None:
        """Speed up horizontally.

        Args:
            None

        Returns:
            None

        """
        self.x += self.increment if self.x >= 0 else self.increment * -1

    def speed_up_vertical(self: Self) -> None:
        """Speed up vertically.

        Args:
            None

        Returns:
            None

        """
        self.y += self.increment if self.y >= 0 else self.increment * -1

    def __mul__(self: Self, scalar: float) -> Speed:
        """Multiply speed by a scalar value.

        Args:
            scalar (float): The scalar to multiply by.

        Returns:
            Speed: A new Speed instance with multiplied values.

        """
        return Speed(x=self.x * scalar, y=self.y * scalar, increment=self.increment)

    def __imul__(self: Self, scalar: float) -> Self:
        """In-place multiplication by a scalar value.

        Args:
            scalar (float): The scalar to multiply by.

        Returns:
            Speed: Self after multiplication.

        """
        self.x *= scalar
        self.y *= scalar
        return self
