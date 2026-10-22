"""Ghosts (glitchygames/replay/ghosts.py): a recorded sprite's appearance drawn beside live play."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import pygame
import pytest
from pydantic import ValidationError

from glitchygames.replay.ghosts import (
    GhostRecorder,
    GhostSample,
    GhostSprite,
    GhostTrack,
    default_appearance,
    images_from_animated_sprite,
)
from glitchygames.scenes import SceneManager
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.world import CoordinateSpace, is_world_positioned

if TYPE_CHECKING:
    from glitchygames.scenes import Scene

GHOST_SIZE = (4, 4)
# The track's sprite is drawn this far below the top
SAMPLE_WORLD_Y = 10.0
SIXTY_FRAMES_PER_SECOND = 60
DEFAULT_GHOST_ALPHA = 96
LEFT_COLOR = (255, 0, 0)
RIGHT_COLOR = (0, 0, 255)


class GameTimedStandIn:
    """A scene stand-in: only ``game_time``, which a ghost reads."""

    def __init__(self, *, game_time: float) -> None:
        """Start at a game time.

        Args:
            game_time: The scene's game time in seconds.

        """
        self.game_time = game_time


class WorldStandIn:
    """A recorded sprite stand-in: a world position, ``hidden`` and the engine's ``visible``."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(self, *, world_x: float, hidden: bool = False, visible: int = 1) -> None:
        """Place the stand-in.

        Args:
            world_x: World X.
            hidden: Whether the game hid it.
            visible: What the engine's culling last decided.

        """
        self.world_x = world_x
        self.world_y = SAMPLE_WORLD_Y
        self.hidden = hidden
        self.visible = visible


class ScreenStandIn(WorldStandIn):
    """The same stand-in in screen space (no coordinate space declared)."""

    COORDINATE_SPACE = None


def sample(*, seconds: float, x: float, appearance: dict[str, Any] | None = None) -> GhostSample:
    """Return a visible sample at a game time and world X.

    Returns:
        The sample.

    """
    return GhostSample(
        game_seconds=seconds,
        world_x=x,
        world_y=SAMPLE_WORLD_Y,
        appearance=appearance or {},
        visible=True,
    )


def stand_in_scene(*, game_time: float = 0.1) -> Scene:
    """Return a scene stand-in typed as a Scene (a recorder reads only its ``game_time``).

    Returns:
        The stand-in.

    """
    return cast('Scene', GameTimedStandIn(game_time=game_time))


def plain_image(_sample: GhostSample) -> pygame.Surface:
    """Return a small surface for any sample.

    Returns:
        A new surface.

    """
    return pygame.Surface(GHOST_SIZE)


def two_frame_sprite() -> AnimatedSprite:
    """Return an animated sprite with one animation of two differently coloured frames.

    The first frame is red on its left half, so a horizontal flip is visible.

    Returns:
        The sprite.

    """
    first_image = pygame.Surface((2, 1))
    first_image.set_at((0, 0), LEFT_COLOR)
    first_image.set_at((1, 0), RIGHT_COLOR)
    second_image = pygame.Surface((2, 1))
    second_image.fill(RIGHT_COLOR)
    sprite = AnimatedSprite()
    sprite.add_animation('walk', [SpriteFrame(first_image), SpriteFrame(second_image)])
    sprite.set_animation('walk')
    return sprite


class TestGhostTrack:
    """A track is a time-ordered tuple of samples, looked up by game time."""

    def test_sample_at_picks_the_last_sample_not_after_the_time(self):
        track = GhostTrack(
            samples=(
                sample(seconds=0.0, x=0.0),
                sample(seconds=0.5, x=5.0),
                sample(seconds=1.0, x=10.0),
            )
        )
        found = track.sample_at(game_seconds=0.75)
        assert found is not None
        assert found.world_x == pytest.approx(5.0)
        exact = track.sample_at(game_seconds=0.5)
        assert exact is not None
        assert exact.world_x == pytest.approx(5.0)
        assert track.sample_at(game_seconds=-1.0) is None

    def test_an_empty_track_has_no_sample(self):
        assert GhostTrack(samples=()).sample_at(game_seconds=1.0) is None

    def test_track_json_round_trip(self):
        track = GhostTrack(
            samples=(
                sample(seconds=0.0, x=1.5, appearance={'animation': 'walk', 'frame': 1}),
                sample(seconds=0.016, x=2.5),
            )
        )
        assert GhostTrack.from_json(json.loads(json.dumps(track.to_json()))) == track

    def test_samples_out_of_time_order_are_refused(self):
        with pytest.raises(ValidationError, match='time order'):
            GhostTrack(samples=(sample(seconds=1.0, x=0.0), sample(seconds=0.5, x=1.0)))

    def test_unknown_fields_are_refused(self):
        record = GhostTrack(samples=(sample(seconds=0.0, x=0.0),)).to_json()
        record['samples'][0]['speed'] = 3
        with pytest.raises(ValidationError):
            GhostTrack.from_json(record)

    def test_samples_are_frozen(self):
        frozen_sample = sample(seconds=0.0, x=0.0)
        with pytest.raises(ValidationError):
            frozen_sample.world_x = 1.0

    def test_the_appearance_is_a_read_only_copy(self):
        """Its JSON keys a ghost's image cache, so nobody may change it after the fact."""
        given: dict[str, Any] = {'animation': 'walk', 'draw_offset': [1, 2]}
        frozen_sample = sample(seconds=0.0, x=0.0, appearance=given)
        given['animation'] = 'run'
        given['draw_offset'].append(3)
        appearance = frozen_sample.appearance
        assert appearance['animation'] == 'walk'
        assert tuple(appearance['draw_offset']) == (1, 2)
        with pytest.raises(TypeError):
            # A Mapping has no item assignment to type-check; the cast lets the test try it
            cast('dict[str, Any]', appearance)['animation'] = 'run'
        with pytest.raises(AttributeError):
            appearance['draw_offset'].append(3)

    def test_an_appearance_that_is_not_a_mapping_is_refused(self):
        with pytest.raises(ValidationError, match='must be a mapping of JSON values, got list'):
            GhostSample(game_seconds=0.0, world_x=0.0, world_y=0.0, appearance=[], visible=True)

    def test_to_json_gives_plain_json_types(self):
        track = GhostTrack(
            samples=(sample(seconds=0.0, x=0.0, appearance={'nested': {'offset': [1, 2]}}),)
        )
        record = track.to_json()
        appearance = record['samples'][0]['appearance']
        assert type(appearance) is dict
        assert type(appearance['nested']) is dict
        assert type(appearance['nested']['offset']) is list
        assert json.loads(json.dumps(record)) == record


class TestGhostSprite:
    """A ghost is a world sprite whose position and image follow its scene's game time."""

    def test_ghost_sprite_is_world_positioned_and_follows_game_time(self):
        track = GhostTrack(samples=(sample(seconds=0.0, x=0.0), sample(seconds=1.0, x=50.0)))
        ghost = GhostSprite(track=track, image_for=plain_image)
        ghost.scene = GameTimedStandIn(game_time=1.25)
        ghost.update()
        assert is_world_positioned(ghost)
        assert ghost.COORDINATE_SPACE is CoordinateSpace.WORLD
        assert (ghost.world_x, ghost.world_y) == (50.0, SAMPLE_WORLD_Y)
        assert ghost.hidden is False

    def test_ghost_plays_at_the_right_speed_at_another_frame_rate(self):
        track = GhostTrack(
            samples=tuple(
                sample(seconds=index / SIXTY_FRAMES_PER_SECOND, x=float(index))
                for index in range(SIXTY_FRAMES_PER_SECOND + 1)
            )
        )
        ghost = GhostSprite(track=track, image_for=plain_image)
        # Half a second into a 30 FPS run: game time does not depend on the frame rate
        ghost.scene = GameTimedStandIn(game_time=0.5)
        ghost.update()
        assert ghost.world_x == pytest.approx(30.0)

    def test_the_position_is_read_from_game_time_without_update(self):
        """The engine positions world sprites before update(): the read alone is current."""
        track = GhostTrack(samples=(sample(seconds=0.0, x=0.0), sample(seconds=1.0, x=50.0)))
        ghost = GhostSprite(track=track, image_for=plain_image)
        scene = GameTimedStandIn(game_time=0.0)
        ghost.scene = scene
        assert ghost.world_x == pytest.approx(0.0)
        scene.game_time = 1.0
        assert ghost.world_x == pytest.approx(50.0)

    def test_before_its_first_sample_or_without_a_scene_the_ghost_draws_nothing(self):
        """An empty image: the engine's culling hides it, and ``hidden`` stays the game's."""
        track = GhostTrack(samples=(sample(seconds=1.0, x=50.0),))
        ghost = GhostSprite(track=track, image_for=plain_image)
        ghost.update()
        assert ghost.image.get_size() == (0, 0)
        scene = GameTimedStandIn(game_time=0.5)
        ghost.scene = scene
        ghost.update()
        assert ghost.image.get_size() == (0, 0)
        scene.game_time = 1.0
        ghost.update()
        assert ghost.image.get_size() == GHOST_SIZE
        assert ghost.rect.size == GHOST_SIZE
        assert ghost.hidden is False

    def test_an_invisible_sample_draws_nothing_until_a_visible_one(self):
        invisible = GhostSample(
            game_seconds=0.0, world_x=0.0, world_y=0.0, appearance={}, visible=False
        )
        track = GhostTrack(samples=(invisible, sample(seconds=1.0, x=0.0)))
        ghost = GhostSprite(track=track, image_for=plain_image)
        scene = GameTimedStandIn(game_time=0.0)
        ghost.scene = scene
        ghost.update()
        assert ghost.rect.size == (0, 0)
        assert ghost.hidden is False
        scene.game_time = 1.0
        ghost.update()
        assert ghost.rect.size == GHOST_SIZE

    def test_a_shown_ghost_goes_back_to_nothing_at_an_invisible_sample_or_without_a_scene(
        self,
    ):
        """After a visible sample, an invisible one (or no scene) shows the empty image again."""
        invisible = GhostSample(
            game_seconds=1.0, world_x=0.0, world_y=0.0, appearance={}, visible=False
        )
        track = GhostTrack(samples=(sample(seconds=0.0, x=0.0), invisible))
        ghost = GhostSprite(track=track, image_for=plain_image)
        scene = GameTimedStandIn(game_time=0.0)
        ghost.scene = scene
        ghost.update()
        assert ghost.rect.size == GHOST_SIZE
        scene.game_time = 1.0
        ghost.update()
        assert ghost.image.get_size() == (0, 0)
        assert ghost.rect.size == (0, 0)
        scene.game_time = 0.0
        ghost.update()
        assert ghost.rect.size == GHOST_SIZE
        ghost.scene = None
        ghost.update()
        assert ghost.image.get_size() == (0, 0)
        assert ghost.hidden is False

    def test_hidden_is_the_games_own_flag_and_round_trips(self):
        """A ghost the track hides is not ``hidden``, so saving and restoring the flag is safe."""
        track = GhostTrack(samples=(sample(seconds=1.0, x=0.0),))
        ghost = GhostSprite(track=track, image_for=plain_image)
        scene = GameTimedStandIn(game_time=0.0)  # before the first sample
        ghost.scene = scene
        was_hidden = ghost.hidden
        ghost.hidden = True
        assert ghost.hidden is True
        ghost.hidden = was_hidden
        scene.game_time = 1.0
        ghost.update()
        assert ghost.hidden is False
        assert ghost.rect.size == GHOST_SIZE

    def test_the_image_is_a_translucent_copy_sized_into_the_rect(self):
        source_image = pygame.Surface((6, 3))
        track = GhostTrack(samples=(sample(seconds=0.0, x=0.0),))
        ghost = GhostSprite(track=track, image_for=lambda _sample: source_image)
        ghost.rect.topleft = (40, 50)  # where the engine placed it
        ghost.scene = GameTimedStandIn(game_time=0.0)
        ghost.update()
        assert ghost.image is not source_image
        assert ghost.image.get_alpha() == DEFAULT_GHOST_ALPHA
        assert source_image.get_alpha() is None
        assert ghost.rect.size == (6, 3)
        assert ghost.rect.topleft == (40, 50)

    def test_the_image_is_made_once_per_appearance(self, mocker):
        image_for = mocker.Mock(side_effect=plain_image)
        track = GhostTrack(
            samples=(
                sample(seconds=0.0, x=0.0, appearance={'frame': 0}),
                sample(seconds=0.5, x=1.0, appearance={'frame': 0}),
                sample(seconds=1.0, x=2.0, appearance={'frame': 1}),
            )
        )
        ghost = GhostSprite(track=track, image_for=image_for)
        scene = GameTimedStandIn(game_time=0.0)
        ghost.scene = scene
        for game_time in (0.0, 0.5, 1.0, 0.25):
            scene.game_time = game_time
            ghost.update()
        assert image_for.call_count == 2

    def test_the_draw_offset_comes_from_the_appearance(self):
        anchored = sample(seconds=0.0, x=0.0, appearance={'draw_offset': [3, -2]})
        track = GhostTrack(samples=(anchored,))
        ghost = GhostSprite(track=track, image_for=plain_image)
        assert ghost.draw_offset == (0, 0)
        ghost.scene = GameTimedStandIn(game_time=0.0)
        assert ghost.draw_offset == (3, -2)

    def test_a_new_image_marks_a_clean_ghost_dirty(self):
        track = GhostTrack(
            samples=(
                sample(seconds=0.0, x=0.0, appearance={'frame': 0}),
                sample(seconds=1.0, x=0.0, appearance={'frame': 1}),
            )
        )
        ghost = GhostSprite(track=track, image_for=plain_image)
        scene = GameTimedStandIn(game_time=0.0)
        ghost.scene = scene
        ghost.update()
        ghost.dirty = 0  # drawn
        scene.game_time = 1.0
        ghost.update()
        assert ghost.dirty == 1

    def test_update_nested_sprites_does_nothing(self):
        """Scene.update() calls it on every sprite; a ghost has no nested sprites."""
        track = GhostTrack(samples=(sample(seconds=0.0, x=0.0),))
        ghost = GhostSprite(track=track, image_for=plain_image)
        ghost.scene = GameTimedStandIn(game_time=0.0)
        ghost.update()
        image_before, rect_before, dirty_before = ghost.image, ghost.rect.copy(), ghost.dirty
        assert ghost.update_nested_sprites() is None
        assert ghost.image is image_before
        assert ghost.rect == rect_before
        assert ghost.dirty == dirty_before


class TestAppearance:
    """What a recorder keeps of a sprite's looks, and the images drawn from it."""

    def test_default_appearance_of_an_animated_sprite(self):
        sprite = two_frame_sprite()
        sprite.set_frame(1)
        sprite.hitbox_flip_x = True
        assert default_appearance(sprite) == {
            'animation': 'walk',
            'frame': 1,
            'flip_x': True,
            'draw_offset': [0, 0],
        }

    def test_default_appearance_of_any_other_sprite_is_empty(self):
        assert default_appearance(WorldStandIn(world_x=0.0)) == {}

    def test_images_from_animated_sprite_draws_the_sampled_frame(self):
        sprite = two_frame_sprite()
        image_for = images_from_animated_sprite(sprite)
        second_frame = default_appearance(sprite) | {'frame': 1}
        second = image_for(sample(seconds=0.0, x=0.0, appearance=second_frame))
        assert tuple(second.get_at((0, 0)))[:3] == RIGHT_COLOR

    def test_images_from_animated_sprite_flips_when_the_sample_does(self):
        sprite = two_frame_sprite()
        image_for = images_from_animated_sprite(sprite)
        appearance = default_appearance(sprite)
        unflipped = image_for(sample(seconds=0.0, x=0.0, appearance=appearance))
        flipped = image_for(sample(seconds=0.0, x=0.0, appearance=appearance | {'flip_x': True}))
        assert tuple(unflipped.get_at((0, 0)))[:3] == LEFT_COLOR
        assert tuple(flipped.get_at((0, 0)))[:3] == RIGHT_COLOR
        assert tuple(flipped.get_at((1, 0)))[:3] == LEFT_COLOR


class TestGhostRecorder:
    """A supervisor that samples one sprite of one scene, live frames only."""

    @pytest.fixture
    def scene_manager(self):
        """Return the scene manager, with no supervisors before or after the test.

        Yields:
            The scene manager.

        """
        manager = SceneManager()
        manager.reset_supervision()
        assert manager.playback_session is None
        yield manager
        manager.reset_supervision()

    def test_the_recorder_registers_itself_and_finish_removes_it(self, scene_manager, mocker):
        add_supervisor = mocker.spy(scene_manager, 'add_supervisor')
        remove_supervisor = mocker.spy(scene_manager, 'remove_supervisor')
        recorder = GhostRecorder(sprite=WorldStandIn(world_x=0.0), scene=stand_in_scene())
        add_supervisor.assert_called_once_with(supervisor=recorder)
        recorder.finish()
        remove_supervisor.assert_called_once_with(supervisor=recorder)

    def test_visible_is_the_games_hidden_flag_not_the_engines_culling(self, scene_manager):
        """A sprite culled off screen live is still shown by its ghost where it is on screen."""
        sprite = WorldStandIn(world_x=0.0, visible=0)
        stand_in = GameTimedStandIn(game_time=0.1)
        # The recorder reads only the scene's game_time
        scene = cast('Scene', stand_in)
        recorder = GhostRecorder(sprite=sprite, scene=scene)
        recorder.on_frame(frame_number=1, scene=scene)
        sprite.hidden = True
        stand_in.game_time = 0.2
        recorder.on_frame(frame_number=2, scene=scene)
        track = recorder.finish()
        assert [recorded.visible for recorded in track.samples] == [True, False]

    def test_frames_inside_a_playback_scope_are_not_sampled(self, scene_manager, mocker):
        """A demo or instant replay plays a rebuilt scene: no live frame of the recorded one."""
        scene = stand_in_scene()
        recorder = GhostRecorder(sprite=WorldStandIn(world_x=0.0), scene=scene)
        mocker.patch.object(
            type(scene_manager),
            'in_playback_scope',
            new_callable=mocker.PropertyMock,
            return_value=True,
        )
        recorder.on_frame(frame_number=1, scene=scene)
        assert recorder.finish().samples == ()

    def test_a_recorder_bound_to_one_scene_ignores_the_frames_of_another(self, scene_manager):
        """Another scene's game time is not the recorded scene's: its frames are skipped."""
        bound_scene = stand_in_scene(game_time=0.1)
        other_scene = stand_in_scene(game_time=5.0)
        recorder = GhostRecorder(sprite=WorldStandIn(world_x=0.0), scene=bound_scene)
        recorder.on_frame(frame_number=1, scene=other_scene)
        recorder.on_frame(frame_number=2, scene=bound_scene)
        recorder.on_frame(frame_number=3, scene=other_scene)
        recorder.on_frame(frame_number=4, scene=None)
        track = recorder.finish()
        assert [recorded.game_seconds for recorded in track.samples] == [0.1]

    def test_a_screen_space_sprite_is_shown_as_its_visible_says(self, scene_manager):
        """No engine culling touches a screen-space sprite: its ``visible`` is the game's."""
        scene = stand_in_scene()
        recorder = GhostRecorder(sprite=ScreenStandIn(world_x=0.0, visible=0), scene=scene)
        recorder.on_frame(frame_number=1, scene=scene)
        assert [recorded.visible for recorded in recorder.finish().samples] == [False]

    def test_a_recorder_never_finished_stays_registered_until_finish(self, scene_manager):
        """A scene left (or paused) may come back, so its recorder stays, sampling nothing."""
        scene = stand_in_scene(game_time=0.1)
        recorder = GhostRecorder(sprite=WorldStandIn(world_x=0.0), scene=scene)
        recorder.on_frame(frame_number=1, scene=scene)
        recorder.on_frame(frame_number=2, scene=stand_in_scene(game_time=9.0))
        assert recorder in scene_manager._supervisors
        track = recorder.finish()
        assert recorder not in scene_manager._supervisors
        assert [recorded.game_seconds for recorded in track.samples] == [0.1]

    def test_finish_twice_returns_the_same_track(self, scene_manager):
        recorder = GhostRecorder(sprite=WorldStandIn(world_x=0.0), scene=stand_in_scene())
        assert recorder.finish() == recorder.finish()
