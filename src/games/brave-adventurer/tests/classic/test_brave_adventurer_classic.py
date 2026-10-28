"""Brave Adventurer, the classic edition: what only its drawn sprites and voice assistant do."""

import os
from pathlib import Path

import pygame
import pytest

import brave_adventurer as brave_adventurer_package
import brave_adventurer_core as brave_adventurer_core_package
from brave_adventurer import game as brave_adventurer_game
from brave_adventurer.drawing import draw_cobra, draw_scarab, draw_scorpion
from brave_adventurer.enemies import Cobra, Scarab, Scorpion
from brave_adventurer.game import MIC_BUTTON_CONTROLLER, MIC_BUTTON_JOYSTICK, BraveAdventurerScene
from brave_adventurer.player import Player
from brave_adventurer.terrain import GoldScarab
from glitchygames.audio import VoiceAssistant
from glitchygames.display_mode import set_display_mode
from glitchygames.events.base import HashableEvent
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools.golden_traces import GoldenTraceEngine, command_line
from glitchygames.scenes import SceneManager
from glitchygames.world import CoordinateSpace, position_world_sprites

FRAME_SECONDS = 1 / 60
# The member's golden replays: golden-classic.jsonl.gz, golden-papyrus.jsonl.gz
REPLAY_FIXTURES_DIRECTORY = Path(__file__).parents[1] / 'fixtures' / 'replays'
BRAVE_ADVENTURER_PACKAGE = Path(brave_adventurer_package.__file__).parent
BRAVE_ADVENTURER_CORE_PACKAGE = Path(brave_adventurer_core_package.__file__).parent
BRAVE_WORLD_SPRITE_CLASSES = (Player, GoldScarab, Cobra, Scarab, Scorpion)
SCREEN_SIZE = (800, 480)


def _start_display():
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=SCREEN_SIZE)


def _surface_bytes(surface):
    return pygame.image.tobytes(surface, 'RGBA')


def _joystick_button_event(event_type, button):
    return HashableEvent(event_type, joy=0, instance_id=0, button=button)


def _controller_button_event(event_type, button):
    return HashableEvent(event_type, instance_id=0, button=button)


@pytest.fixture
def brave_scene(mocker):
    """A Brave Adventurer scene with sounds, rumble and saving mocked."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(800, 480))
    scene = BraveAdventurerScene(options={'input_mode': 'joystick'})
    mocker.patch.object(scene.scene_manager.rumble, 'pulse')
    mocker.patch.object(scene, 'sounds')
    mocker.patch.object(scene, '_save_high_score', return_value=[])
    return scene


class TestEngineWorldSpace:
    """Brave Adventurer's sprites are world sprites; the engine aims the camera and places them."""

    @pytest.mark.parametrize(
        'sprite_class', BRAVE_WORLD_SPRITE_CLASSES, ids=lambda cls: cls.__name__
    )
    def test_world_sprite_classes_declare_world_space(self, sprite_class):
        assert sprite_class.COORDINATE_SPACE is CoordinateSpace.WORLD

    @pytest.mark.parametrize(
        'sprite_class', BRAVE_WORLD_SPRITE_CLASSES, ids=lambda cls: cls.__name__
    )
    def test_no_sprite_class_positions_itself_from_the_camera(self, sprite_class):
        assert not hasattr(sprite_class, 'apply_camera')

    @pytest.mark.parametrize(
        'source_path',
        sorted([
            *BRAVE_ADVENTURER_PACKAGE.glob('*.py'),
            *BRAVE_ADVENTURER_CORE_PACKAGE.glob('*.py'),
        ]),
        ids=lambda path: f'{path.parent.name}/{path.name}',
    )
    def test_no_module_culls_or_positions_sprites_itself(self, source_path):
        """Culling and positioning are the engine's; only the pit gaps still use camera.apply."""
        source = source_path.read_text(encoding='utf-8')
        assert 'is_visible' not in source
        assert 'apply_camera' not in source

    def test_scene_has_no_camera_loop(self):
        assert '_follow_player_with_camera' not in vars(BraveAdventurerScene)


class TestEngineCullingKeepsEnemiesAnimated:
    """Off-screen enemies keep animating: engine culling never sets dirty = 0.

    The old per-sprite culling set dirty = 0 on a culled sprite, and Scene.update() calls
    update() only on dirty sprites, so an enemy that had been off screen drew once on coming
    back and then froze.
    """

    SCREEN_SIZE = (800, 480)

    def _position(self, scene, *, camera_x):
        scene.camera.world_x = camera_x
        position_world_sprites(
            sprites=scene.all_sprites, camera=scene.camera, screen_size=self.SCREEN_SIZE
        )

    def test_scarab_redraws_after_being_off_screen(self, brave_scene):
        scene = brave_scene
        scarab = Scarab(world_x=1000.0, groups=scene.all_sprites)
        scarab.roll_angle = 0.0

        self._position(scene, camera_x=scarab.world_x + 5000.0)  # far off screen
        assert not scarab.visible
        assert scarab.dirty == 2

        self._position(scene, camera_x=scarab.world_x - 100.0)  # back on screen
        assert scarab.visible
        assert scarab.dirty == 2
        # The pose is drawn in dt_tick (the pose rule), which every sprite gets, culled or not
        scarab.dt_tick(0.0)
        first_image = pygame.image.tobytes(scarab.image, 'RGBA')

        scarab.roll_angle = 1.2  # the wing line leans 3 px: a different picture
        self._position(scene, camera_x=scarab.world_x - 100.0)
        scarab.dt_tick(0.0)

        assert scarab.dirty == 2
        assert pygame.image.tobytes(scarab.image, 'RGBA') != first_image


class TestVoiceAssistantMicButton:
    """Brave Adventurer: holding the mic button records a question, releasing it answers.

    The voice assistant drives a controller's microphone and speaker (hardware), so it is a
    stand-in here. The scene is the classic one with its rumble, sounds and saving mocked
    (``brave_scene``).
    """

    @pytest.fixture
    def voice_assistant(self, mocker):
        return mocker.create_autospec(VoiceAssistant, instance=True)

    @staticmethod
    def _controller_scene():
        _start_display()
        return BraveAdventurerScene(options={'input_mode': 'controller'})

    def test_each_frame_collects_finished_responses(self, brave_scene, voice_assistant):
        brave_scene.voice_assistant = voice_assistant

        brave_scene.dt_tick(FRAME_SECONDS)

        voice_assistant.update.assert_called_once_with()

    def test_controller_mic_button_listens_and_answers(self, brave_scene, voice_assistant):
        scene = self._controller_scene()
        scene.voice_assistant = voice_assistant

        scene.on_controller_button_down_event(
            _controller_button_event(pygame.CONTROLLERBUTTONDOWN, MIC_BUTTON_CONTROLLER)
        )
        voice_assistant.start_listening.assert_called_once_with()
        scene.on_controller_button_up_event(
            _controller_button_event(pygame.CONTROLLERBUTTONUP, MIC_BUTTON_CONTROLLER)
        )

        voice_assistant.stop_listening_and_respond.assert_called_once_with()

    def test_joystick_mic_button_listens_and_answers(self, brave_scene, voice_assistant):
        brave_scene.voice_assistant = voice_assistant

        brave_scene.on_joy_button_down_event(
            _joystick_button_event(pygame.JOYBUTTONDOWN, MIC_BUTTON_JOYSTICK)
        )
        voice_assistant.start_listening.assert_called_once_with()
        brave_scene.on_joy_button_up_event(
            _joystick_button_event(pygame.JOYBUTTONUP, MIC_BUTTON_JOYSTICK)
        )

        voice_assistant.stop_listening_and_respond.assert_called_once_with()

    def test_mic_button_without_an_assistant_does_nothing(self, brave_scene):
        """No controller with a microphone was found: the mic button is ignored."""
        controller_scene = self._controller_scene()
        for scene in (brave_scene, controller_scene):
            scene.voice_assistant = None
            scene.dt_tick(FRAME_SECONDS)
        controller_scene.on_controller_button_down_event(
            _controller_button_event(pygame.CONTROLLERBUTTONDOWN, MIC_BUTTON_CONTROLLER)
        )
        controller_scene.on_controller_button_up_event(
            _controller_button_event(pygame.CONTROLLERBUTTONUP, MIC_BUTTON_CONTROLLER)
        )
        brave_scene.on_joy_button_down_event(
            _joystick_button_event(pygame.JOYBUTTONDOWN, MIC_BUTTON_JOYSTICK)
        )
        brave_scene.on_joy_button_up_event(
            _joystick_button_event(pygame.JOYBUTTONUP, MIC_BUTTON_JOYSTICK)
        )

        assert brave_scene.voice_assistant is None
        assert controller_scene.voice_assistant is None


class TestVoiceAssistantNeverStartsInAReplay:
    """A replay never touches real devices: no voice assistant is discovered in one (#208)."""

    def test_live_play_discovers_the_voice_assistant(self, mocker):
        _start_display()
        discover = mocker.patch.object(VoiceAssistant, 'discover', return_value=None)

        BraveAdventurerScene(options={'input_mode': 'joystick'})

        discover.assert_called_once_with()

    def test_a_replay_discovers_no_voice_assistant(self, mocker):
        discover = mocker.patch.object(VoiceAssistant, 'discover', return_value=None)
        mocker.patch.object(brave_adventurer_game, 'GameEngine', GoldenTraceEngine)
        # GameEngine._shutdown quits pygame; later tests on this worker still need it
        mocker.patch('pygame.quit')
        mocker.patch('pygame.display.quit')
        mocker.patch.dict(os.environ)  # --headless sets the SDL driver variables
        recording = REPLAY_FIXTURES_DIRECTORY / 'golden-classic.jsonl.gz'
        SceneManager._reset()
        try:
            with (
                command_line([
                    '--log-level',
                    'warning',
                    '--replay-trace',
                    str(recording),
                    '--headless',
                ]),
                pytest.raises(SystemExit) as exit_info,
            ):
                brave_adventurer_game.main()
        finally:
            pygame.event.clear()
            SceneManager._reset()

        assert exit_info.value.code == ExitCode.SUCCESS
        discover.assert_not_called()


class TestEnemyPoseIsDrawnInDtTick:
    """Cobra, Scarab and Scorpion draw their pose in dt_tick, before collision (#209.6).

    Their hitboxes are their visible pixels, so a pose drawn in update() (the render phase) was a
    frame late for collision, and nothing at all before the first draw.
    """

    @staticmethod
    def _drawn(draw_function, size, **arguments):
        surface = pygame.Surface(size, pygame.SRCALPHA)
        draw_function(surface, **arguments)
        return _surface_bytes(surface)

    def test_a_new_enemy_already_shows_its_pose(self):
        _start_display()
        group = pygame.sprite.LayeredDirty()
        cobra = Cobra(100.0, group)
        scarab = Scarab(100.0, group)
        scorpion = Scorpion(100.0, group)

        assert _surface_bytes(cobra.image) == self._drawn(
            draw_cobra, cobra.image.get_size(), striking=False, animation_timer=0.0
        )
        assert _surface_bytes(scarab.image) == self._drawn(
            draw_scarab, scarab.image.get_size(), roll_angle=0.0
        )
        assert _surface_bytes(scorpion.image) == self._drawn(
            draw_scorpion, scorpion.image.get_size(), facing_right=True
        )

    def test_cobra_dt_tick_draws_the_strike(self):
        _start_display()
        cobra = Cobra(100.0, pygame.sprite.LayeredDirty())

        cobra.dt_tick(Cobra.STRIKE_INTERVAL)

        assert cobra.striking
        expected = self._drawn(
            draw_cobra,
            cobra.image.get_size(),
            striking=True,
            animation_timer=cobra.dt_timer,
        )
        assert _surface_bytes(cobra.image) == expected

    def test_scarab_dt_tick_draws_the_roll(self):
        _start_display()
        scarab = Scarab(100.0, pygame.sprite.LayeredDirty())

        scarab.dt_tick(0.5)

        expected = self._drawn(draw_scarab, scarab.image.get_size(), roll_angle=scarab.roll_angle)
        assert _surface_bytes(scarab.image) == expected

    def test_scorpion_dt_tick_draws_the_turn_at_its_patrol_end(self):
        _start_display()
        scorpion = Scorpion(100.0, pygame.sprite.LayeredDirty(), patrol_range=10.0)

        scorpion.dt_tick(1.0)

        assert not scorpion.facing_right
        expected = self._drawn(draw_scorpion, scorpion.image.get_size(), facing_right=False)
        assert _surface_bytes(scorpion.image) == expected

    def test_update_leaves_the_pose_alone(self):
        _start_display()
        group = pygame.sprite.LayeredDirty()
        for enemy in (Cobra(100.0, group), Scarab(100.0, group), Scorpion(100.0, group)):
            enemy.dt_tick(0.25)
            pose = _surface_bytes(enemy.image)
            enemy.image.fill((0, 0, 0, 0))

            enemy.update()

            assert _surface_bytes(enemy.image) == _surface_bytes(
                pygame.Surface(enemy.image.get_size(), pygame.SRCALPHA)
            ), type(enemy).__name__
            assert pose != _surface_bytes(enemy.image)


# A player running right that has just left the ground and started to fall
RUNNING_OFF_A_LEDGE_CONTEXT = {'velocity_x': 200.0, 'velocity_y': 20.0, 'on_ground': False}


class TestRunningOffALedgeFalls:
    """Running off a ledge shows the falling pose in the classic edition (#209.7)."""

    def test_primitives_player_goes_from_running_to_falling(self):
        _start_display()
        player = Player(world_x=100.0, world_y=300.0, groups=pygame.sprite.LayeredDirty())
        player.state_machine.set_state(Player.RUNNING)

        player.state_machine.evaluate(RUNNING_OFF_A_LEDGE_CONTEXT)

        assert player.state_machine.current_state == Player.FALLING
