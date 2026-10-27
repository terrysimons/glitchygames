"""Argparse value types shared by the engine's command line and its tools' command.

``non_negative_int``, ``non_negative_percent`` and ``percent_from_zero_to_one_hundred`` check
option values on a game's own command line (``GameEngine.args``,
glitchygames/engine/game_engine.py) and on the ``glitchygames`` command's
(glitchygames/replay/tools/registry.py), which describe the replay tools' options once. They live
here, a leaf module, because the registry is imported by the engine and so cannot
import it back.
"""

from __future__ import annotations

import argparse
import math

# The largest percentage percent_from_zero_to_one_hundred reads
ONE_HUNDRED_PERCENT = 100.0


def non_negative_percent(value: str) -> float:
    """Argparse type: a finite percentage >= 0.

    Args:
        value: The command-line text.

    Returns:
        The parsed percentage.

    Raises:
        argparse.ArgumentTypeError: If the text is not a finite number >= 0.

    """
    try:
        number = float(value)
    except ValueError as error:
        message = f'{value!r} is not a number'
        raise argparse.ArgumentTypeError(message) from error
    if not math.isfinite(number) or number < 0:
        message = f'{value!r} must be a finite number >= 0'
        raise argparse.ArgumentTypeError(message)
    return number


def percent_from_zero_to_one_hundred(value: str) -> float:
    """Argparse type: a percentage from 0 to 100 (``--compare-alpha``: how opaque OLD is drawn).

    Args:
        value: The command-line text.

    Returns:
        The parsed percentage.

    Raises:
        argparse.ArgumentTypeError: If the text is not a number from 0 to 100.

    """
    number = non_negative_percent(value)
    if number > ONE_HUNDRED_PERCENT:
        message = f'{value!r} must be a number from 0 to {ONE_HUNDRED_PERCENT:g}'
        raise argparse.ArgumentTypeError(message)
    return number


def non_negative_int(value: str) -> int:
    """Argparse type: an integer >= 0.

    Args:
        value: The command-line text.

    Returns:
        The parsed integer.

    Raises:
        argparse.ArgumentTypeError: If the text is not an integer >= 0.

    """
    try:
        number = int(value)
    except ValueError as error:
        message = f'{value!r} is not an integer'
        raise argparse.ArgumentTypeError(message) from error
    if number < 0:
        message = f'{value!r} must be >= 0'
        raise argparse.ArgumentTypeError(message)
    return number
