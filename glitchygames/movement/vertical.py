#!/usr/bin/env python3
"""Vertical Movement.

This is a simple vertical movement class that can be used to move sprites up and down.
"""
from __future__ import annotations

from typing import Self


class Vertical:
    """Vertical movement."""

    def __init__(self: Self, speed: int) -> None:
        """Initialize the vertical movement.

        Args:
            speed (int): The speed to move at.

        Returns:
            None
        """
        self.speed = speed
        self.current_speed = self.speed.y

    def _change_speed(self: Self, value: int) -> None:
        """Change the current speed.

        Args:
            value (int): The value to change the speed by.

        Returns:
            None
        """
        self.current_speed = value

    def up(self: Self) -> None:
        """Move up.

        Args:
            None

        Returns:
            None
        """
        self._change_speed(-self.speed.y)

    def down(self: Self) -> None:
        """Move down.

        Args:
            None

        Returns:
            None
        """
        self._change_speed(self.speed.y)

    def stop(self: Self) -> None:
        """Stop moving.

        Args:
            None

        Returns:
            None
        """
        self._change_speed(0)
