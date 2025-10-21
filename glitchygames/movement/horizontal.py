#!/usr/bin/env python3
"""Horizontal Movement.

This is a simple horizontal movement class that can be used to move sprites left and right.
"""

from __future__ import annotations

from typing import Self

from .speed import Speed


class Horizontal:
    """Horizontal movement."""

    def __init__(self: Self, speed: Speed) -> None:
        """Initialize the horizontal movement.

        Args:
            speed (Speed): The speed object to move at.

        Returns:
            None

        """
        self.speed = speed
        self.current_speed = self.speed.x

    def _change_speed(self: Self, value: int) -> None:
        """Change the current speed.

        Args:
            value (int): The value to change the speed by.

        Returns:
            None

        """
        self.current_speed = value

    def left(self: Self) -> None:
        """Move left.

        Args:
            None

        Returns:
            None

        """
        self._change_speed(-self.speed.x)

    def right(self: Self) -> None:
        """Move right.

        Args:
            None

        Returns:
            None

        """
        self._change_speed(self.speed.x)

    def stop(self: Self) -> None:
        """Stop moving.

        Args:
            None

        Returns:
            None

        """
        self._change_speed(0)

    def get_movement_with_dt(self: Self, dt: float) -> float:
        """Get the movement amount for this frame with delta time applied.

        Args:
            dt (float): The delta time in seconds.

        Returns:
            float: The movement amount for this frame.

        """
        return self.current_speed * dt
