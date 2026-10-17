"""Tests for the Clockwork Keep example game."""

import pygame
import pytest

from glitchygames.events.base import HashableEvent
from glitchygames.examples.clockwork_keep.game import ClockworkKeepScene

FRAME_TIME = 1.0 / 60.0


@pytest.fixture
def clockwork_scene(mocker):
    """A floor-0 scene with transition_to recorded instead of performed."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((800, 480))
    scene = ClockworkKeepScene(options={'input_mode': 'joystick'})
    mocker.patch.object(scene, 'transition_to')
    return scene


def _stand_on_first_elevator(scene):
    elevator = scene.elevator_sprites[0]
    scene.player.world_x = elevator.world_x + 5
    scene.player.world_y = elevator.world_y - scene.player.rect.height
    for _ in range(5):
        scene.dt_tick(FRAME_TIME)


def _press_key(scene, key):
    scene.on_key_down_event(HashableEvent(pygame.KEYDOWN, key=key, mod=0, unicode='', scancode=0))


class TestElevatorActivation:
    """BUGS.md #24: interact rides the elevator, jump always jumps."""

    def test_interact_rides(self, clockwork_scene):
        _stand_on_first_elevator(clockwork_scene)
        _press_key(clockwork_scene, pygame.K_w)
        clockwork_scene.dt_tick(FRAME_TIME)
        clockwork_scene.transition_to.assert_called_once()

    def test_jump_jumps_and_does_not_ride(self, clockwork_scene):
        _stand_on_first_elevator(clockwork_scene)
        _press_key(clockwork_scene, pygame.K_SPACE)
        clockwork_scene.dt_tick(FRAME_TIME)
        assert clockwork_scene.player.velocity_y < 0
        clockwork_scene.transition_to.assert_not_called()

    def test_jump_while_held_never_rides(self, clockwork_scene):
        """Even if on_ground is restored before the check, jump alone never rides."""
        _stand_on_first_elevator(clockwork_scene)
        clockwork_scene.actions.handle_event(
            HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode='', scancode=0)
        )
        clockwork_scene._check_elevator()
        clockwork_scene.transition_to.assert_not_called()
