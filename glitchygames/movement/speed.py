#!/usr/bin/env python3
"""Speed.

This is a simple speed class that can be used to speed up sprites.
"""

from __future__ import annotations

from typing import Self


class Speed:
    """Speed in pixels per second."""

    def __init__(self: Self, x: float = 0, y: float = 0, increment: float = 0.2) -> None:
        """Initialize the speed.

        Args:
            x (float): The x speed in pixels per second.
            y (float): The y speed in pixels per second.
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

    def __add__(self: Self, other) -> int:
        """Add Speed to another value.

        Args:
            other: The value to add to this Speed.

        Returns:
            int: The sum of the Speed's y component and the other value.

        """
        if isinstance(other, (int, float)):
            return self.y + other
        return NotImplemented

    def __radd__(self: Self, other) -> int:
        """Add another value to Speed (right addition).

        Args:
            other: The value to add to this Speed.

        Returns:
            int: The sum of the other value and the Speed's y component.

        """
        if isinstance(other, (int, float)):
            return other + self.y
        return NotImplemented

    def __neg__(self: Self) -> Speed:
        """Negate the Speed object.

        Returns:
            Speed: A new Speed instance with negated x and y values.

        """
        return Speed(-self.x, -self.y, self.increment)

    def __sub__(self: Self, other) -> Speed:
        """Subtract another Speed object or scalar from this Speed.

        Args:
            other: Another Speed object or scalar value to subtract.

        Returns:
            Speed: A new Speed instance with the result of subtraction.

        """
        if isinstance(other, Speed):
            return Speed(self.x - other.x, self.y - other.y, self.increment)
        elif isinstance(other, (int, float)):
            return Speed(self.x - other, self.y - other, self.increment)
        else:
            return NotImplemented

    def __mul__(self: Self, other) -> Speed:
        """Multiply this Speed by a scalar value.

        Args:
            other: A scalar value to multiply by.

        Returns:
            Speed: A new Speed instance with the result of multiplication.

        """
        if isinstance(other, (int, float)):
            return Speed(self.x * other, self.y * other, self.increment)
        else:
            return NotImplemented

    def __add__(self: Self, other) -> Speed:
        """Add another Speed object or scalar to this Speed.

        Args:
            other: Another Speed object or scalar value to add.

        Returns:
            Speed: A new Speed instance with the result of addition.

        """
        if isinstance(other, Speed):
            return Speed(self.x + other.x, self.y + other.y, self.increment)
        elif isinstance(other, (int, float)):
            return Speed(self.x + other, self.y + other, self.increment)
        else:
            return NotImplemented

    def __truediv__(self: Self, other) -> Speed:
        """Divide this Speed by a scalar value.

        Args:
            other: A scalar value to divide by.

        Returns:
            Speed: A new Speed instance with the result of division.

        """
        if isinstance(other, (int, float)):
            if other == 0:
                raise ZeroDivisionError("Cannot divide Speed by zero")
            return Speed(self.x / other, self.y / other, self.increment)
        else:
            return NotImplemented

    def __mod__(self: Self, other) -> Speed:
        """Modulo this Speed by a scalar value.

        Args:
            other: A scalar value to modulo by.

        Returns:
            Speed: A new Speed instance with the result of modulo.

        """
        if isinstance(other, (int, float)):
            if other == 0:
                raise ZeroDivisionError("Cannot modulo Speed by zero")
            return Speed(self.x % other, self.y % other, self.increment)
        else:
            return NotImplemented

    def apply_dt(self: Self, dt: float) -> Speed:
        """Apply delta time to get frame-relative movement.

        Args:
            dt (float): The delta time in seconds.

        Returns:
            Speed: A new Speed instance with dt applied.

        """
        return Speed(self.x * dt, self.y * dt, self.increment)
