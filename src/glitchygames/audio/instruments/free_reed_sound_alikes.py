"""Free reeds' sound-alikes: listed instruments that share another entry's build.

A sound-alike is a distinct instrument, verified by its source, that no fetched source sets apart
in sound from an existing entry. The owner ruled (2026-11-08) that each is a catalog entry of its
own rather than an alias: "could we also consider making them full on instruments that inherit
from the parent and change their details? ... I want them to all show up." Each is listed under
its own name, so a person finds it by the name they know, and each builds its parent's
instrument through ``sounds_like`` (assembled in ``registry.sound_alikes_from``). It gives its own
sourced range, since a sound-alike of another size plays another span. A true alias, another name
for the same instrument, stays in ``aliases.py``. Once the builders take them, a sound-alike whose
source gives it a detune between its reed sets, an octave reed set or drones its parent lacks will
carry them as ``sound_changes``, its only changes. The family's builds are in ``free_reeds.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from glitchygames.audio.instruments.catalog import CatalogEntry

FREE_REED_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = ()
