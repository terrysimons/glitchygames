"""A module's own ``time``, for a test that replaces some of its clock or sleep functions.

``mocker.patch('time.sleep')`` and ``mocker.patch.object(module.time, 'sleep')`` replace the one
shared ``time`` module's function, for every thread: the suite runs threads (the memory guard's
sampler, a module's own worker threads), which would then sleep or read the clock through the
test's mock (ruff's shared-clock-mock). ``patch_module_time`` replaces only the module under
test's ``time`` attribute, with a ``TimeStandIn`` that carries the test's overrides and passes
every other name through to the real ``time``, so a function the module also uses is still there.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

    from pytest_mock import MockerFixture


class TimeStandIn:
    """A stand-in for the ``time`` module: the overrides, and the real ``time`` for the rest."""

    def __init__(self, **overrides: object) -> None:
        """Hold the overrides as attributes.

        Args:
            **overrides: Each replaced ``time`` function by name (``sleep=mock_sleep``).

        """
        for name, replacement in overrides.items():
            setattr(self, name, replacement)

    def __getattr__(self, name: str) -> object:
        """Pass a name the stand-in does not override through to the real ``time``.

        Returns:
            The real ``time`` module's attribute.

        """
        return getattr(time, name)


def patch_module_time(
    *, mocker: MockerFixture, module: ModuleType, create: bool = False, **overrides: object
) -> None:
    """Replace ``module.time`` with a ``TimeStandIn`` for the rest of the test.

    Args:
        mocker: pytest-mock's fixture (it undoes the patch after the test).
        module: The module under test, whose global ``time`` its code calls through.
        create: Add ``module.time`` when the module does not import ``time`` (a test that the
            module never reads the clock, which would then read the stand-in).
        **overrides: The ``time`` functions to replace, by name (``sleep=mock_sleep``).

    """
    mocker.patch.object(module, 'time', TimeStandIn(**overrides), create=create)
