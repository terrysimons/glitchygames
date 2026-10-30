"""The seam the browser page uses to wire a bitmappy scene to a MasterHUB web hub.

bitmappy can mirror its canvas to a MasterHUB web hub running in a sibling iframe, but only in the
browser: the wiring (browser/masterhub_bridge.py) imports ``js`` and lives in the page, outside this
type-checked package, so the editor never imports it. Instead the browser page (browser/boot.py)
registers an installer here with ``install_masterhub``; the editor pulls it with
``installed_masterhub`` and calls it with its scene. Off the browser nothing is registered, so the
editor mirrors to no hub. This mirrors the engine's own browser seams (clipboard, user files), but
stays in bitmappy because only bitmappy talks to a MasterHUB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import Callable


class _MasterHubRegistry:
    """The process's MasterHUB installer: registered by the browser page, None otherwise."""

    def __init__(self: Self) -> None:
        """Start with none registered."""
        self.installer: Callable[[object], None] | None = None


_REGISTRY = _MasterHubRegistry()


def install_masterhub(*, installer: Callable[[object], None] | None) -> None:
    """Make ``installer`` the one ``installed_masterhub`` returns (None registers nothing).

    Args:
        installer: Called once with a scene to wire it to the hub, or None for no hub (the desktop).

    """
    _REGISTRY.installer = installer


def installed_masterhub() -> Callable[[object], None] | None:
    """Return the installer the browser page registered.

    Returns:
        The installer, or None where there is no hub (off the browser).

    """
    return _REGISTRY.installer
