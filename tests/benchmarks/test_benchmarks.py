"""Performance benchmarks for core GlitchyGames operations.

Uses pytest-benchmark to measure and track performance of critical
code paths that run every frame or are called frequently.

Run benchmarks:
    pytest tests/benchmarks/ --benchmark-only
    nox -s performance_test
"""

from pathlib import Path

import pygame

from glitchygames.game_objects.ball import (
    BallSprite,
    SpeedUpAxes,
    SpeedUpCurve,
    SpeedUpSettings,
    SpeedUpTrigger,
)
from glitchygames.recording_history import frame_content_hash
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.tracing import read_trace_result

# The engine's own sprite test data (Bitmappy keeps its sprite library)
SPRITE_FIXTURES_DIRECTORY = Path(__file__).resolve().parents[1] / 'fixtures' / 'sprites'

# Path to the static sprite fixture
STATIC_TOML = str(
    SPRITE_FIXTURES_DIRECTORY / 'static.toml',
)

# Brave Adventurer's golden replay, in its own package's fixtures since it moved
BRAVE_ADVENTURER_GOLDEN = (
    Path(__file__).resolve().parents[2]
    / 'src'
    / 'games'
    / 'brave-adventurer'
    / 'tests'
    / 'fixtures'
    / 'replays'
    / 'golden-classic.jsonl.gz'
)

# Frame time at 60 FPS
DT_60FPS = 1.0 / 60.0


# ---------------------------------------------------------------------------
# Ball physics benchmarks
# ---------------------------------------------------------------------------
class TestBallPhysicsBenchmarks:
    """Benchmark BallSprite physics operations."""

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
        ball.speed_up_settings = SpeedUpSettings(
            triggers=SpeedUpTrigger.CONTINUOUS,
            curve=SpeedUpCurve.LINEAR,
            axes=SpeedUpAxes.BOTH,
        )

        benchmark(ball.dt_tick, DT_60FPS)

    def test_ball_dt_tick_with_logarithmic_speedup(self, benchmark):
        """Benchmark dt_tick with continuous logarithmic speed-up enabled."""
        ball = self._create_ball_at_center()
        ball.speed_up_settings = SpeedUpSettings(
            triggers=SpeedUpTrigger.CONTINUOUS,
            curve=SpeedUpCurve.LOGARITHMIC,
            axes=SpeedUpAxes.BOTH,
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

    def _create_multi_frame_sprite(self, frame_count):
        """Create an AnimatedSprite with the given number of frames.

        Returns:
            object: The result.

        """
        sprite = AnimatedSprite()
        surfaces = []
        for _ in range(frame_count):
            surface = pygame.Surface((8, 8))
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
        walk_frames = [SpriteFrame(pygame.Surface((8, 8)), duration=0.1) for _ in range(10)]
        sprite.add_animation('walk', walk_frames)

        animation_names = ['idle', 'walk']
        call_count = 0

        def switch_animation():
            nonlocal call_count
            sprite.play(animation_names[call_count % 2])
            call_count += 1

        benchmark(switch_animation)


def test_benchmark_frame_content_hash_of_the_largest_golden_frame(benchmark):
    """Hash one frame (105 sprites, about 7 KB of JSON): about 107 microseconds (2026-10-21)."""
    frames = read_trace_result(path=BRAVE_ADVENTURER_GOLDEN).trace['frames']
    largest = max(frames, key=lambda frame: len(frame.get('sprites', [])))
    digest = benchmark(lambda: frame_content_hash(frame_record=largest))
    assert len(digest) == 16
