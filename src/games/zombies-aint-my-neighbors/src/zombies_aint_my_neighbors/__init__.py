"""Zombies Ain't My Neighbors: a 4-player creature-feature run-and-gun on GlitchyGames.

Everything this game needs lives in this member (src/games/zombies-aint-my-neighbors/): its
code, its sprite TOML, its sound files and its caches. It uses the engine but never changes it;
what the engine should grow is recorded in the master plan's Engine wishlist
(plans/2026-11-14-zombies-aint-my-neighbors.md).
"""

from zombies_aint_my_neighbors.launcher import main

__all__ = ['main']
