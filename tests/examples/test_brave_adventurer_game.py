"""Tests for the Brave Adventurer games' death and game-over rumble."""

import math
import tomllib

import pygame
import pytest

from glitchygames.animation.state_machine import AnimationStateMachine
from glitchygames.examples.brave_adventurer.constants import (
    DEATH_RUMBLE_DURATION,
    DEATH_RUMBLE_HIGH,
    DEATH_RUMBLE_LOW,
    GAME_OVER_RUMBLE_DURATION,
    GAME_OVER_RUMBLE_HIGH,
    GAME_OVER_RUMBLE_LOW,
)
from glitchygames.examples.brave_adventurer.game import BraveAdventurerScene
from glitchygames.examples.brave_adventurer_papyrus.constants import (
    FALLING_VELOCITY_THRESHOLD as PAPYRUS_FALLING_VELOCITY_THRESHOLD,
)
from glitchygames.examples.brave_adventurer_papyrus.constants import (
    SPRITES_DIR,
)
from glitchygames.examples.brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene


@pytest.fixture(params=[BraveAdventurerScene, PapyrusBraveAdventurerScene])
def adventurer_scene(request, mocker):
    """Each game's scene with rumble, sounds, respawn and saving replaced by mocks."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((800, 480))
    scene = request.param(options={'input_mode': 'joystick'})
    mocker.patch.object(scene.scene_manager.rumble, 'pulse')
    mocker.patch.object(scene, 'sounds')
    mocker.patch.object(scene, '_respawn_player')
    mocker.patch.object(scene, '_save_high_score', return_value=[])
    return scene


class TestDefaultTargetFps:
    """An explicit --target-fps 0 stays uncapped; the engine default supplies 60.44."""

    def test_setup_keeps_explicit_zero_target_fps_uncapped(self, adventurer_scene):
        adventurer_scene.target_fps = 0
        adventurer_scene.setup()
        assert math.isclose(adventurer_scene.target_fps, 0.0, abs_tol=1e-9)


class TestDeathRumble:
    """Losing a life rumbles; the last life rumbles harder."""

    def test_losing_a_life_pulses_the_death_rumble(self, adventurer_scene):
        adventurer_scene.player.lives = 2
        adventurer_scene._player_die()
        adventurer_scene.scene_manager.rumble.pulse.assert_called_once_with(
            low_frequency=DEATH_RUMBLE_LOW,
            high_frequency=DEATH_RUMBLE_HIGH,
            duration=DEATH_RUMBLE_DURATION,
        )

    def test_last_life_pulses_the_game_over_rumble(self, adventurer_scene):
        adventurer_scene.player.lives = 1
        adventurer_scene._player_die()
        adventurer_scene.scene_manager.rumble.pulse.assert_called_once_with(
            low_frequency=GAME_OVER_RUMBLE_LOW,
            high_frequency=GAME_OVER_RUMBLE_HIGH,
            duration=GAME_OVER_RUMBLE_DURATION,
        )


class _RecordingSprite:
    """Minimal sprite that records which animation the state machine plays."""

    def __init__(self) -> None:
        self.played_animations: list[str] = []

    def play(self, animation_name: str) -> None:
        self.played_animations.append(animation_name)


class TestPapyrusFallingTransitions:
    """Papyrus declares its falling transitions in player.toml, not in code."""

    @pytest.fixture
    def transitions(self):
        with (SPRITES_DIR / 'player.toml').open('rb') as toml_file:
            return tomllib.load(toml_file)['transition']

    def test_falling_transitions_are_declared_in_toml(self, transitions):
        expected_when = f'velocity_y > {PAPYRUS_FALLING_VELOCITY_THRESHOLD} and not on_ground'
        falling_sources = [
            transition['from'] for transition in transitions if transition['to'] == 'falling'
        ]
        assert falling_sources == ['idle', 'jumping']
        for transition in transitions:
            if transition['to'] == 'falling':
                assert transition['when'] == expected_when

    def test_toml_threshold_equals_constant(self, transitions):
        for transition in transitions:
            if transition['to'] == 'falling':
                threshold_text = transition['when'].split()[2]
                assert float(threshold_text) == pytest.approx(PAPYRUS_FALLING_VELOCITY_THRESHOLD)

    def test_falling_comes_after_other_rules_from_same_state(self, transitions):
        for source in ('idle', 'jumping'):
            targets = [
                transition['to'] for transition in transitions if transition['from'] == source
            ]
            assert targets[-1] == 'falling'

    def test_player_has_no_code_defined_falling_transitions(self):
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((800, 480))
        scene = PapyrusBraveAdventurerScene(options={'input_mode': 'joystick'})
        state_machine = scene.player.state_machine
        assert state_machine is not None
        falling_conditions = [
            transition.condition
            for transition in state_machine._transitions
            if transition.to_state == 'falling'
        ]
        assert len(falling_conditions) == 2
        for condition in falling_conditions:
            assert type(condition).__module__ == 'glitchygames.animation.expressions'

    def test_state_machine_idle_to_falling(self, transitions):
        sprite = _RecordingSprite()
        state_machine = AnimationStateMachine(sprite)
        state_machine.load_from_toml(transitions)
        state_machine.set_state('idle')
        state_machine.evaluate({'velocity_x': 0.0, 'velocity_y': 20.0, 'on_ground': False})
        assert state_machine.current_state == 'falling'

    def test_state_machine_jumping_to_falling(self, transitions):
        sprite = _RecordingSprite()
        state_machine = AnimationStateMachine(sprite)
        state_machine.load_from_toml(transitions)
        state_machine.set_state('jumping')
        state_machine.evaluate({'velocity_x': 0.0, 'velocity_y': 20.0, 'on_ground': False})
        assert state_machine.current_state == 'falling'

    def test_standing_still_on_ground_stays_idle(self, transitions):
        sprite = _RecordingSprite()
        state_machine = AnimationStateMachine(sprite)
        state_machine.load_from_toml(transitions)
        state_machine.set_state('idle')
        state_machine.evaluate({'velocity_x': 0.0, 'velocity_y': 20.0, 'on_ground': True})
        assert state_machine.current_state == 'idle'
