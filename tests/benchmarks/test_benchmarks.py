"""Performance benchmarks for core GlitchyGames operations.

Uses pytest-benchmark to measure and track performance of critical
code paths that run every frame or are called frequently.

Run benchmarks:
    pytest tests/benchmarks/ --benchmark-only
    nox -s performance_test
"""

from pathlib import Path

import pygame
import pytest

from glitchygames.bitmappy.controllers.selection import ControllerSelection
from glitchygames.bitmappy.indicators.collision import VisualCollisionManager
from glitchygames.game_objects.ball import BallSprite, SpeedUpMode
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from tests.mocks import MockFactory

# Path to the static sprite fixture
STATIC_TOML = str(
    Path(__file__).parent.parent.parent
    / 'glitchygames'
    / 'examples'
    / 'resources'
    / 'sprites'
    / 'static.toml',
)

# Frame time at 60 FPS
DT_60FPS = 1.0 / 60.0


# ---------------------------------------------------------------------------
# Ball physics benchmarks
# ---------------------------------------------------------------------------
class TestBallPhysicsBenchmarks:
    """Benchmark BallSprite physics operations."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for ball creation."""
        if not pygame.get_init():
            pygame.init()

        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def _create_ball_at_center(self):
        """Create a ball positioned at center with diagonal velocity.

        Returns:
            object: The result.

        """
        ball = BallSprite()
        assert ball.rect is not None
        ball.rect.x = 400
        ball.rect.y = 300
        ball.speed.x = 200.0
        ball.speed.y = 150.0
        return ball

    def test_ball_dt_tick_single_frame(self, benchmark):
        """Benchmark a single dt_tick call (the per-frame physics update)."""
        ball = self._create_ball_at_center()

        benchmark(ball.dt_tick, DT_60FPS)

    def test_ball_dt_tick_60_frames(self, benchmark):
        """Benchmark 60 consecutive dt_tick calls (one second of physics)."""
        ball = self._create_ball_at_center()

        def run_one_second():
            for _ in range(60):
                ball.dt_tick(DT_60FPS)

        benchmark(run_one_second)

    def test_ball_dt_tick_with_linear_speedup(self, benchmark):
        """Benchmark dt_tick with continuous linear speed-up enabled."""
        ball = self._create_ball_at_center()
        ball.speed_up_mode = SpeedUpMode.CONTINUOUS_LINEAR

        benchmark(ball.dt_tick, DT_60FPS)

    def test_ball_dt_tick_with_logarithmic_speedup(self, benchmark):
        """Benchmark dt_tick with continuous logarithmic speed-up enabled."""
        ball = self._create_ball_at_center()
        ball.speed_up_mode = (
            SpeedUpMode.CONTINUOUS_LOGARITHMIC_X | SpeedUpMode.CONTINUOUS_LOGARITHMIC_Y
        )

        benchmark(ball.dt_tick, DT_60FPS)

    def test_ball_bounce_detection(self, benchmark):
        """Benchmark boundary collision detection when ball hits a wall."""
        ball = self._create_ball_at_center()
        # Position ball at top boundary to trigger bounce
        assert ball.rect is not None
        ball.rect.y = 0
        ball.speed.y = -100.0

        benchmark(ball.dt_tick, DT_60FPS)


# ---------------------------------------------------------------------------
# Animated sprite benchmarks
# ---------------------------------------------------------------------------
class TestAnimatedSpriteBenchmarks:
    """Benchmark AnimatedSprite operations."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks."""
        if not pygame.get_init():
            pygame.init()

        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def _create_multi_frame_sprite(self, frame_count):
        """Create an AnimatedSprite with the given number of frames.

        Returns:
            object: The result.

        """
        sprite = AnimatedSprite()
        surfaces = []
        for _ in range(frame_count):
            surface = MockFactory.create_pygame_surface_mock(8, 8)
            surfaces.append(SpriteFrame(surface, duration=0.1))
        sprite._animations = {'idle': surfaces}
        sprite.frame_manager.current_animation = 'idle'
        sprite._is_playing = True
        sprite._is_looping = True
        return sprite

    def test_animated_sprite_update_10_frames(self, benchmark):
        """Benchmark animation update with 10 frames."""
        sprite = self._create_multi_frame_sprite(10)
        benchmark(sprite.update, DT_60FPS)

    def test_animated_sprite_update_50_frames(self, benchmark):
        """Benchmark animation update with 50 frames."""
        sprite = self._create_multi_frame_sprite(50)
        benchmark(sprite.update, DT_60FPS)

    def test_animated_sprite_update_100_frames(self, benchmark):
        """Benchmark animation update with 100 frames."""
        sprite = self._create_multi_frame_sprite(100)
        benchmark(sprite.update, DT_60FPS)

    def test_animated_sprite_set_frame(self, benchmark):
        """Benchmark direct frame selection."""
        sprite = self._create_multi_frame_sprite(50)

        frame_index = 0

        def cycle_frames():
            nonlocal frame_index
            sprite.set_frame(frame_index % 50)
            frame_index += 1

        benchmark(cycle_frames)

    def test_animated_sprite_load_from_toml(self, benchmark):
        """Benchmark loading a sprite from TOML file."""
        benchmark(AnimatedSprite, filename=STATIC_TOML)

    def test_animated_sprite_play_animation(self, benchmark):
        """Benchmark switching to an animation."""
        sprite = self._create_multi_frame_sprite(10)
        walk_frames = [
            SpriteFrame(MockFactory.create_pygame_surface_mock(8, 8), duration=0.1)
            for _ in range(10)
        ]
        sprite.add_animation('walk', walk_frames)

        animation_names = ['idle', 'walk']
        call_count = 0

        def switch_animation():
            nonlocal call_count
            sprite.play(animation_names[call_count % 2])
            call_count += 1

        benchmark(switch_animation)


# ---------------------------------------------------------------------------
# Controller selection benchmarks
# ---------------------------------------------------------------------------
class TestControllerSelectionBenchmarks:
    """Benchmark ControllerSelection operations."""

    def test_selection_set_and_get(self, benchmark):
        """Benchmark rapid selection changes."""
        selection = ControllerSelection(0, 0)
        selection.activate()

        call_count = 0

        def set_selection():
            nonlocal call_count
            selection.set_selection(f'animation_{call_count % 10}', call_count % 50)
            call_count += 1

        benchmark(set_selection)

    def test_selection_frame_preservation(self, benchmark):
        """Benchmark frame preservation during animation switching."""
        selection = ControllerSelection(0, 0)
        selection.activate()

        # Build up navigation history
        for i in range(20):
            selection.set_selection(f'animation_{i % 5}', i % 10)

        call_count = 0

        def preserve_frame():
            nonlocal call_count
            selection.preserve_frame_for_animation(
                f'animation_{call_count % 5}', available_frames=20,
            )
            call_count += 1

        benchmark(preserve_frame)

    def test_selection_navigation_history(self, benchmark):
        """Benchmark navigation history retrieval with deep history."""
        selection = ControllerSelection(0, 0)
        selection.activate()

        # Build deep history
        for i in range(100):
            selection.set_selection(f'animation_{i % 10}', i % 50)

        benchmark(selection.get_navigation_history)

    def test_selection_state_summary(self, benchmark):
        """Benchmark state summary generation."""
        selection = ControllerSelection(0, 0)
        selection.activate()
        selection.set_selection('idle', 5)

        benchmark(selection.get_state_summary)


# ---------------------------------------------------------------------------
# Visual collision manager benchmarks
# ---------------------------------------------------------------------------
class TestVisualCollisionBenchmarks:
    """Benchmark VisualCollisionManager operations."""

    def test_add_single_indicator(self, benchmark):
        """Benchmark adding a single controller indicator."""
        manager = VisualCollisionManager()

        call_count = 0

        def add_indicator():
            nonlocal call_count
            manager.add_controller_indicator(
                controller_id=call_count % 4,
                instance_id=call_count % 4,
                color=(255, 0, 0),
                position=(call_count * 10, 0),
            )
            call_count += 1

        benchmark(add_indicator)

    def test_collision_detection_4_controllers(self, benchmark):
        """Benchmark collision group update with 4 controllers at same position."""
        manager = VisualCollisionManager()
        for i in range(4):
            manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(100, 100),
            )

        def update_positions():
            for i in range(4):
                manager.update_controller_position(i, (100, 100))

        benchmark(update_positions)

    def test_position_update_no_collision(self, benchmark):
        """Benchmark position updates when controllers are far apart."""
        manager = VisualCollisionManager()
        for i in range(4):
            manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(i * 100, i * 100),
            )

        call_count = 0

        def update_position():
            nonlocal call_count
            controller_id = call_count % 4
            manager.update_controller_position(
                controller_id, (controller_id * 100 + call_count, controller_id * 100),
            )
            call_count += 1

        benchmark(update_position)
