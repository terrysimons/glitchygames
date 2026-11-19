"""The sprite kit: the next stage's sprites, built ahead and each used once.

Feature plan 9 (plans/2026-11-15-zombies-aint-my-neighbors-9-sprite-kit.md). Building a stage
loads about 340 ms of sprite files; the stage card's two idle seconds build them ahead instead,
a sprite a frame, and the stage takes them as it is built.

The rules:

1. The kit is handed from scene to scene: the stage card makes one (or is given the last
   stage's), builds into it and gives it to its stage, and a cleared stage gives it to the next
   card. A scene given none makes its own, as a playback's rebuilt scene does, so a replay never
   touches the live game's kit and two games in one process (the Arcade) never share one. Built
   sprites wait, with every companion sprite they made (a kid's remote, laser pointer, dot and
   beam; a neighbor's rescue and loss effects), in the kit's own group, ``storage``, never in a
   scene's.
2. Building only loads: no position and no random number. A stage places what it takes and
   draws every random number as it is built, as a replay rebuilds it from the streams its
   constructor began with (glitchygames/scene_start.py rule 4).
3. Each sprite is handed over once (``take_*``): moved, companions after it in the order they
   were made, out of ``storage`` into the scene's group. Nothing comes back, and a sprite no
   stage takes (a kid for a player who unplugged on the card) stays until the kit is dropped
   (the title makes a new one); no recording samples it. A sprite seen for
   the first time in its own stage gets its replay id as a sprite built there would; a sprite
   reused across stages would not (the plan's finding).
4. Taking a part that is not ready builds it at once, the same way, so a stage's group receives
   its sprites in the same order whether they were built ahead or not.

Not an engine context slot (the owner's first thought): the repository's guards
(tests/test_engine_context_source_guards.py) require an isolation check for every slot in the
engine's own tests, which may never import a member, so a member cannot declare one yet
(feature plan 9).
"""

from __future__ import annotations

from collections import Counter, deque
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, override

import pygame
from pydantic import BaseModel, ConfigDict

from zombies_aint_my_neighbors.art.palettes import KIDS
from zombies_aint_my_neighbors.exit_door import ExitDoor
from zombies_aint_my_neighbors.kid import Kid, MirrorCache
from zombies_aint_my_neighbors.neighbor import Neighbor
from zombies_aint_my_neighbors.run_state import NeighborKind
from zombies_aint_my_neighbors.tv import Tv
from zombies_aint_my_neighbors.zap import Zap
from zombies_aint_my_neighbors.zombie import Zombie

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

# Every kid's look (its sprite file's name)
KID_LOOKS: Final = frozenset(kid.name for kid in KIDS)
# Where a part waits until its stage places it
UNPLACED: Final = 0.0


class PartKind(StrEnum):
    """What a part of a stage is."""

    KID = 'kid'
    TV = 'tv'
    ZOMBIE = 'zombie'
    ZAP = 'zap'
    NEIGHBOR = 'neighbor'
    DOOR = 'door'


class Part(BaseModel):
    """One sprite a stage needs: its kind, and which one (a kid's look, a neighbor's kind)."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    kind: PartKind
    variant: str = ''

    @override
    def __hash__(self) -> int:
        """Hash the kind and the variant (a frozen model hashes alike; the type checkers see it).

        Returns:
            The hash.

        """
        return hash((self.kind, self.variant))


class SpriteKit:
    """Sprites built ahead, waiting in a group of their own until a stage takes each one."""

    def __init__(self) -> None:
        """Make an empty kit."""
        self.storage: pygame.sprite.LayeredDirty[Any] = pygame.sprite.LayeredDirty()
        # Mirrored frames, shared by every kid and monster the kit builds
        self.mirror_cache = MirrorCache()
        # Each part's built sprites, oldest first: each the part's sprite, then its companions
        self._ready: dict[Part, deque[list[pygame.sprite.Sprite]]] = {}
        self._builders: Mapping[PartKind, Callable[[str], pygame.sprite.Sprite]] = {
            PartKind.KID: self._build_kid,
            PartKind.TV: lambda _variant: Tv(groups=self.storage),
            PartKind.ZOMBIE: self._build_zombie,
            PartKind.ZAP: self._build_zap,
            PartKind.NEIGHBOR: lambda variant: Neighbor(
                kind=NeighborKind(variant), world_x=UNPLACED, world_y=UNPLACED, groups=self.storage
            ),
            PartKind.DOOR: lambda _variant: ExitDoor(
                world_x=UNPLACED, world_y=UNPLACED, groups=self.storage
            ),
        }

    def ready(self, part: Part) -> int:
        """Return how many of a part are built and waiting.

        Returns:
            The count.

        """
        return len(self._ready.get(part, ()))

    def is_ready_for(self, *, needs: Counter[Part]) -> bool:
        """Return whether every part a stage needs is built.

        Returns:
            True when nothing is missing.

        """
        return all(self.ready(part) >= count for part, count in needs.items())

    def build_one_toward(self, *, needs: Counter[Part]) -> bool:
        """Build the first part still missing for a stage, in the needs' order.

        Args:
            needs: Each part the stage takes, and how many.

        Returns:
            True if a part was built; False when every one was ready already.

        """
        for part, count in needs.items():
            if self.ready(part) < count:
                self._ready.setdefault(part, deque()).append(self._build(part))
                return True
        return False

    def take_kid(self, *, look_name: str, groups: pygame.sprite.LayeredDirty[Any]) -> Kid:
        """Hand over a kid (and its props), unplaced.

        Returns:
            The kid.

        Raises:
            ValueError: If no kid has that look.

        """
        if look_name not in KID_LOOKS:
            message = f'No kid looks like {look_name!r} (one of {sorted(KID_LOOKS)})'
            raise ValueError(message)
        return _as(Kid, self._take(Part(kind=PartKind.KID, variant=look_name), groups=groups))

    def take_tv(self, *, groups: pygame.sprite.LayeredDirty[Any]) -> Tv:
        """Hand over a TV, unplaced (``Tv.place`` puts it in the yard).

        Returns:
            The TV.

        """
        return _as(Tv, self._take(Part(kind=PartKind.TV), groups=groups))

    def take_zombie(self, *, groups: pygame.sprite.LayeredDirty[Any]) -> Zombie:
        """Hand over a zombie, put away, as a pool keeps it.

        Returns:
            The zombie.

        """
        return _as(Zombie, self._take(Part(kind=PartKind.ZOMBIE), groups=groups))

    def take_zap(self, *, groups: pygame.sprite.LayeredDirty[Any]) -> Zap:
        """Hand over a zap, put away, as a pool keeps it (its stage sets its bounds).

        Returns:
            The zap.

        """
        return _as(Zap, self._take(Part(kind=PartKind.ZAP), groups=groups))

    def take_neighbor(
        self, *, kind: NeighborKind, groups: pygame.sprite.LayeredDirty[Any]
    ) -> Neighbor:
        """Hand over a neighbor of a kind (and its effects), unplaced.

        Returns:
            The neighbor.

        """
        return _as(Neighbor, self._take(Part(kind=PartKind.NEIGHBOR, variant=kind), groups=groups))

    def take_door(self, *, groups: pygame.sprite.LayeredDirty[Any]) -> ExitDoor:
        """Hand over the exit door, unplaced.

        Returns:
            The door.

        """
        return _as(ExitDoor, self._take(Part(kind=PartKind.DOOR), groups=groups))

    def _take(self, part: Part, *, groups: pygame.sprite.LayeredDirty[Any]) -> pygame.sprite.Sprite:
        """Move a part's oldest built sprites (built now if none wait) into a group.

        Returns:
            The part's sprite.

        """
        waiting = self._ready.get(part)
        sprites = waiting.popleft() if waiting else self._build(part)
        for sprite in sprites:
            self.storage.remove(sprite)
            groups.add(sprite)
        return sprites[0]

    def _build(self, part: Part) -> list[pygame.sprite.Sprite]:
        """Build a part in ``storage``.

        Returns:
            The part's sprite, then every companion it made, in the order made.

        """
        before = set(self.storage.sprites())
        sprite = self._builders[part.kind](part.variant)
        made = [other for other in self.storage.sprites() if other not in before]
        return [sprite, *(other for other in made if other is not sprite)]

    def _build_kid(self, look_name: str) -> Kid:
        """Build a kid of a look, unplaced.

        Returns:
            The kid.

        """
        return Kid(
            look_name=look_name,
            world_x=UNPLACED,
            world_y=UNPLACED,
            mirror_cache=self.mirror_cache,
            groups=self.storage,
        )

    def _build_zombie(self, _variant: str) -> Zombie:
        """Build a zombie, put away.

        Returns:
            The zombie.

        """
        zombie = Zombie(
            world_x=UNPLACED, world_y=UNPLACED, mirror_cache=self.mirror_cache, groups=self.storage
        )
        zombie.put_away()
        return zombie

    def _build_zap(self, _variant: str) -> Zap:
        """Build a zap, put away, inside no yard until its stage gives it one.

        Returns:
            The zap.

        """
        zap = Zap(
            centre=(UNPLACED, UNPLACED),
            direction=(1.0, 0.0),
            bounds=pygame.Rect(0, 0, 0, 0),
            groups=self.storage,
        )
        zap.put_away()
        return zap


def _as[T](kind: type[T], sprite: object) -> T:
    """Return a sprite as the type its part makes.

    Returns:
        The sprite.

    Raises:
        TypeError: If it is another type (a builder bug).

    """
    if not isinstance(sprite, kind):
        message = f'Expected a {kind.__name__}, got {type(sprite).__name__}'
        raise TypeError(message)
    return sprite
