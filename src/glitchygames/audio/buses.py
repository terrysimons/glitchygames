"""The bus tree: per-bus volume, mute, solo and channel reservations (impl spec 7.4).

Every bus hangs under ``master``. A voice's gain is its own volume times its bus's
``effective_gain()``: the product of the volumes along the path to ``master``, zero when a bus on
the path is muted or a non-soloed sibling of a soloed bus. Each change moves the tree's
``revision``, so the voice table re-applies gains to playing channels on its next ``advance``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

MASTER_BUS = 'master'
DEFAULT_BUS_NAMES = (MASTER_BUS, 'music', 'effects', 'ui', 'ambience', 'dialogue')
# Feature spec 6.1: a storm of effects can never silence a menu click or the music
DEFAULT_RESERVED_CHANNELS = {'ui': 2, 'music': 2}


def _checked_volume(volume: float) -> float:
    """A bus volume, 0-1.

    Returns:
        The volume as a float.

    Raises:
        ValueError: If the volume is outside 0-1 (or NaN).
    """
    if not 0.0 <= volume <= 1.0:
        message = f'volume must be between 0 and 1, got {volume}'
        raise ValueError(message)
    return float(volume)


def _checked_reservation(reserved_channels: int) -> int:
    """A channel reservation, a count.

    Returns:
        The count.

    Raises:
        ValueError: If the count is negative.
    """
    if reserved_channels < 0:
        message = f'reserved_channels must be >= 0, got {reserved_channels}'
        raise ValueError(message)
    return reserved_channels


class Bus:
    """One bus of the tree; ``volume``, ``mute``, ``solo`` and ``reserved_channels`` may change.

    Attributes:
        name: The bus's name.
        parent: The parent bus's name, or None for ``master``.
    """

    def __init__(  # ruff: ignore[too-many-arguments] - one construction site
        self,
        *,
        name: str,
        parent: str | None,
        volume: float,
        reserved_channels: int,
        tree: BusTree,
        on_change: Callable[[], None],
    ) -> None:
        """Make a bus; only ``BusTree`` makes them.

        Args:
            name: The bus's name.
            parent: The parent's name (None for ``master``).
            volume: The volume, 0-1.
            reserved_channels: Library channels kept for this bus's voices.
            tree: The tree the bus belongs to (for the path and siblings).
            on_change: Called after every change.
        """
        self.name = name
        self.parent = parent
        self._volume = _checked_volume(volume)
        self._mute = False
        self._solo = False
        self._reserved_channels = _checked_reservation(reserved_channels)
        self._tree = tree
        self._on_change = on_change

    @property
    def volume(self) -> float:
        """The bus's own volume, 0-1."""
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        checked = _checked_volume(value)
        if checked != self._volume:
            self._volume = checked
            self._on_change()

    @property
    def mute(self) -> bool:
        """Whether the bus (and so its subtree) is silent."""
        return self._mute

    @mute.setter
    def mute(self, value: bool) -> None:
        if value != self._mute:
            self._mute = value
            self._on_change()

    @property
    def solo(self) -> bool:
        """Whether the bus is soloed: its non-soloed siblings (and their subtrees) go silent."""
        return self._solo

    @solo.setter
    def solo(self, value: bool) -> None:
        if value != self._solo:
            self._solo = value
            self._on_change()

    @property
    def reserved_channels(self) -> int:
        """The library channels kept free for this bus's voices."""
        return self._reserved_channels

    @reserved_channels.setter
    def reserved_channels(self, value: int) -> None:
        self._reserved_channels = _checked_reservation(value)

    def effective_gain(self) -> float:
        """The gain a voice on this bus gets from the buses.

        Returns:
            The product of the volumes from this bus up to ``master``; 0.0 when a bus on the path
            is muted, or is not soloed while one of its siblings is.
        """
        gain = 1.0
        bus: Bus | None = self
        while bus is not None:
            if bus.mute or self._tree.silenced_by_a_soloed_sibling(bus):
                return 0.0
            gain *= bus.volume
            bus = self._tree[bus.parent] if bus.parent is not None else None
        return gain


class BusTree:
    """The buses, ``master`` at the root; the default buses always exist.

    Attributes:
        revision: Moves on every change of a volume, mute, solo or the tree's shape.
    """

    def __init__(self) -> None:
        """Make the tree with the default buses and reservations."""
        self.revision = 0
        self._buses: dict[str, Bus] = {}
        self._buses[MASTER_BUS] = self._make_bus(MASTER_BUS, parent=None, volume=1.0)
        for name in DEFAULT_BUS_NAMES[1:]:
            self._buses[name] = self._make_bus(
                name,
                parent=MASTER_BUS,
                volume=1.0,
                reserved_channels=DEFAULT_RESERVED_CHANNELS.get(name, 0),
            )

    def add(
        self,
        name: str,
        *,
        parent: str = MASTER_BUS,
        volume: float = 1.0,
        reserved_channels: int = 0,
    ) -> Bus:
        """Add a bus under an existing one (so the tree can have no cycle).

        Args:
            name: The new bus's name.
            parent: The existing bus it hangs under.
            volume: Its volume, 0-1.
            reserved_channels: Library channels kept for its voices.

        Returns:
            The new bus.

        Raises:
            ValueError: If a bus of that name exists, or the volume or reservation is invalid.
        """
        if name in self._buses:
            message = f'bus {name!r} already exists'
            raise ValueError(message)
        self[parent]  # raises KeyError naming the buses for an unknown parent
        bus = self._make_bus(
            name, parent=parent, volume=volume, reserved_channels=reserved_channels
        )
        self._buses[name] = bus
        self._changed()
        return bus

    def __getitem__(self, name: str) -> Bus:
        """Look a bus up by name.

        Returns:
            The bus.

        Raises:
            KeyError: If there is no such bus; the message names the buses there are.
        """
        bus = self._buses.get(name)
        if bus is None:
            message = f'no bus {name!r}; the buses are {", ".join(self._buses)}'
            raise KeyError(message)
        return bus

    def names(self) -> tuple[str, ...]:
        """The bus names, in the order they were added.

        Returns:
            The names.
        """
        return tuple(self._buses)

    def silenced_by_a_soloed_sibling(self, bus: Bus) -> bool:
        """Whether a sibling of ``bus`` is soloed while ``bus`` is not.

        Returns:
            True when the solo rule silences ``bus`` (and so its subtree).
        """
        if bus.solo or bus.parent is None:
            return False
        return any(other.solo for other in self._buses.values() if other.parent == bus.parent)

    def _make_bus(
        self, name: str, *, parent: str | None, volume: float, reserved_channels: int = 0
    ) -> Bus:
        """Make a bus that reports its changes to this tree.

        Returns:
            The bus.
        """
        return Bus(
            name=name,
            parent=parent,
            volume=volume,
            reserved_channels=reserved_channels,
            tree=self,
            on_change=self._changed,
        )

    def _changed(self) -> None:
        """Move the revision."""
        self.revision += 1
