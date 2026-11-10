"""Record Brave Adventurer for the AI behaviour tests: walls, pits, one missed jump, and a cobra.

The golden stops on screen 1, before any hazard. This runs right from the start, jumping each
wall and pit as it comes, except that it deliberately walks into the first pit once, so "why did
I miss that jump?" has a death to explain. After respawning it jumps that pit and goes on past
screen 5's cobra. It steers from the scene each frame, so the recording is deterministic, as
every scripted session is (seed: the goldens').

Usage:
    uv run python -m scripts.ai_behaviour.record_brave_adventurer
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
# No AI: a recording session must never reach for the service
os.environ['GLITCHYGAMES_AI_INSTALL_ROOT'] = '/nonexistent-glitchygames-ai'

import pygame

from brave_adventurer_core.scene import BraveAdventurerSceneBase
from glitchygames.replay.tools.golden_traces import (
    RANDOM_SEED,
    InputScript,
    press,
    release,
)
from glitchygames.replay.tools.scripted_sessions import record_scripted_session

if TYPE_CHECKING:
    from brave_adventurer.player import Player
    from glitchygames.scenes import Scene

RECORDING = Path(__file__).parent / 'recordings' / 'brave-adventurer-hazards.jsonl.gz'
FRAMES = 2400
START_RUNNING_FRAME = 10
JUMP_HELD_FRAMES = 12
# How close an obstacle's near edge must be before jumping
WALL_JUMP_DISTANCE = 30
PIT_JUMP_DISTANCE = 12


class HazardRunner:
    """Hold Right, and press Up for each wall and pit ahead, missing the first pit once."""

    def __init__(self) -> None:
        """Start standing, with nothing missed yet."""
        self.frame = 0
        self.release_jump_at: int | None = None
        self.missed_a_pit = False
        self.lives_seen: int | None = None

    def __call__(self, scene: Scene) -> list[pygame.event.Event]:
        """Steer one frame.

        Returns:
            The key events to post before it.

        """
        events: list[pygame.event.Event] = []
        self.frame += 1
        if self.frame == START_RUNNING_FRAME:
            events.append(press(pygame.K_RIGHT))
        if self.release_jump_at == self.frame:
            events.append(release(pygame.K_UP))
            self.release_jump_at = None
        # A pause or game-over screen has no player to steer
        if not isinstance(scene, BraveAdventurerSceneBase):
            return events
        player: Player | None = getattr(scene, 'player', None)
        if player is None or self.release_jump_at is not None or not player.on_ground:
            return events
        if self.lives_seen is not None and player.lives < self.lives_seen:
            # The miss happened: from now on every pit is jumped
            self.missed_a_pit = True
        self.lives_seen = player.lives
        if self.should_jump(scene=scene, player=player):
            events.append(press(pygame.K_UP))
            self.release_jump_at = self.frame + JUMP_HELD_FRAMES
        return events

    def should_jump(self, *, scene: BraveAdventurerSceneBase, player: Player) -> bool:
        """Whether a wall or a pit is just ahead, and this is not the deliberate miss.

        Returns:
            True to jump now.

        """
        front = player.world_x + player.rect.width
        for wall in scene.wall_sprites:
            if 0 <= wall.world_x - front <= WALL_JUMP_DISTANCE:
                return True
        segments = sorted(scene.ground_sprites, key=lambda segment: segment.world_x)
        for segment in segments:
            end = segment.world_x + segment.rect.width
            if 0 <= end - front <= PIT_JUMP_DISTANCE:
                # The first pit is walked into once, on purpose
                return self.missed_a_pit
        return False


def main() -> int:
    """Record the scenario.

    Returns:
        The exit code.

    """
    from brave_adventurer.game import BraveAdventurerScene

    RECORDING.parent.mkdir(parents=True, exist_ok=True)
    record_scripted_session(
        scene_class=BraveAdventurerScene,
        script=InputScript(per_frame=HazardRunner()),
        frame_count=FRAMES,
        path=RECORDING,
        random_seed=RANDOM_SEED,
    )
    sys.stdout.write(f'{RECORDING} ({RECORDING.stat().st_size} bytes)\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
