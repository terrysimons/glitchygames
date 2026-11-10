"""bitmappy.masterhub: the seam the browser page uses to wire a scene to a MasterHUB web hub.

Off the browser nothing is installed, so ``installed_masterhub()`` is None and a scene mirrors to no
hub. The browser page (browser/boot.py, with browser/masterhub_bridge.py) installs an installer that
wires the scene; these pin the install/installed round-trip and the default, with no browser or
``js`` in sight.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from bitmappy.masterhub import install_masterhub, installed_masterhub

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _reset_installer() -> Iterator[None]:
    """Each test starts and ends with no installer, so the module global never leaks."""
    install_masterhub(installer=None)
    yield
    install_masterhub(installer=None)


def test_nothing_is_installed_by_default():
    """Off the browser no installer is registered, so a scene mirrors to no hub."""
    assert installed_masterhub() is None


def test_installed_masterhub_returns_what_was_installed():
    """The page installs an installer; installed_masterhub returns that exact callable, usable."""
    scenes_wired: list[object] = []

    def installer(scene: object) -> None:
        scenes_wired.append(scene)

    install_masterhub(installer=installer)

    returned = installed_masterhub()
    assert returned is installer
    scene = object()
    assert returned is not None
    returned(scene)
    assert scenes_wired == [scene]


def test_install_none_clears_it():
    """Installing None restores the no-hub state (used between platforms, and between tests)."""
    install_masterhub(installer=lambda _scene: None)
    install_masterhub(installer=None)
    assert installed_masterhub() is None
