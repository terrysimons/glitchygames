"""PaddleSlap's ball-ball collisions, swept around the full circle through the real pipeline.

Moved from the engine's tests (tests/game_objects/test_ball_collision_physics.py): the subject is
the game's own per-frame collision path (``Game._handle_ball_collisions``,
``Game._calculate_ball_distance``), driven with real ``BallSprite`` objects.
"""

import math

import pytest

import paddleslap
from glitchygames.collision.layers import CollisionManager
from glitchygames.game_objects.ball import BallSprite
from glitchygames.movement import Speed
from paddleslap import Game
from tests.game_objects.ball_helpers import drawn_position, place_ball_center

# ---------------------------------------------------------------------------
# Full-circle collision sweep against the real PaddleSlap collision pipeline.
#
# The engine's tests in tests/game_objects/test_ball_collision_physics.py re-implement the
# collision math inside the test, so they cannot catch bugs in the game's own code. These
# tests drive real BallSprites through BallSprite.dt_tick() and Game._handle_ball_collisions()
# (collision manager broad phase -> circle check -> elastic exchange -> separation -> cooldown)
# exactly as the game loop does each frame.
#
# Expected behavior: for two equal-mass balls whose centers are aimed at the
# same point at the same time, the contact normal is parallel to their relative
# velocity, so a perfectly elastic collision swaps their velocities exactly.
# A moving ball hitting a stationary ball is the special case where the mover
# stops dead and the target leaves with the mover's original velocity.
# ---------------------------------------------------------------------------

SWEEP_ANGLES_DEGREES = tuple(range(0, 360, 15))
STATIONARY_TARGET_MOVER_SPEEDS = (60.0, 180.0, 400.0)
MOVING_PAIR_SPEEDS = ((100.0, 100.0), (100.0, 300.0), (300.0, 100.0), (300.0, 300.0))
SWEEP_FRAME_DT = 1 / 60
SWEEP_MEETING_POINT = (400.0, 240.0)
SWEEP_MINIMUM_TIME_TO_MEET = 0.3  # seconds
SWEEP_MINIMUM_STARTING_GAP = 40.0  # pixels between centers; collision distance is 10
SWEEP_FRAMES_AFTER_COLLISION = 30
# How far inside the collision distance the centres are on the first frame they could touch
SWEEP_CONTACT_INSET = 2.0  # pixels
SWEEP_BALL_SIZE = 20
# Ball centers live on integer pixels, so the collision normal the game computes can
# be a few degrees off the ideal one. Allow 10% of the relative speed (plus 1 px/s)
# of velocity error for that rounding; real bugs produce errors far larger than this.
# The visible circles are only 10 px across, so this holds because the balls are first
# sampled SWEEP_CONTACT_INSET inside the collision distance (8 px apart): at 3 px or
# less apart, a pixel of rounding turns the normal by 10 degrees or more.
SWEEP_VELOCITY_TOLERANCE_FRACTION = 0.1
SWEEP_CONSERVATION_TOLERANCE = 1e-6


def _velocity_from_angle(angle_degrees: float, speed: float) -> tuple[float, float]:
    """Return the (x, y) velocity for a heading in degrees (0 = right, 90 = down)."""
    angle_radians = math.radians(angle_degrees)
    return (speed * math.cos(angle_radians), speed * math.sin(angle_radians))


class _CollisionSweepHarness:
    """Runs two real BallSprites through the real PaddleSlap per-frame collision path.

    It runs the ball-ball physics step (_handle_ball_collisions) only, not the playability
    rule PaddleSlap's dt_tick applies afterwards (_keep_collided_balls_playable), so the
    sweeps check exact equal-mass elastic physics: swapped velocities, a mover that stops
    dead, and conserved momentum and energy.
    """

    def __init__(
        self,
        first_velocity: tuple[float, float],
        second_velocity: tuple[float, float],
        *,
        meet_on_frame: bool = False,
    ) -> None:
        self.game = Game.__new__(Game)
        self.game.collisions = CollisionManager()
        self.game.collisions.add_layer('balls')
        self.game._ball_collision_cooldowns = {}

        self.first_ball = self._create_ball(first_velocity)
        self.second_ball = self._create_ball(second_velocity)
        # The game's own threshold: the visible circles' radii, not the image size
        _, _, _, self.collision_distance = Game._calculate_ball_distance(
            self.first_ball, self.second_ball
        )

        # The centres reach the meeting point a fraction of a frame after a whole frame,
        # chosen so that on that whole frame they are SWEEP_CONTACT_INSET inside the
        # collision distance, still on the line of their relative velocity. The game
        # computes the contact normal from whole-pixel centres (up to about a pixel off
        # each way), so the normal's error shrinks as the contact distance grows. Without
        # the phase, a pair could first be sampled a few pixels apart (or, meeting exactly
        # on a frame, centred on the same point, where no normal exists and the game skips
        # the pair) and the frames either side are a full step away.
        relative_speed = math.dist(first_velocity, second_velocity)
        minimum_time_to_meet = max(
            SWEEP_MINIMUM_TIME_TO_MEET,
            SWEEP_MINIMUM_STARTING_GAP / relative_speed,
        )
        # meet_on_frame puts the meeting exactly on a frame (the pass-through pin below)
        contact_distance = 0.0 if meet_on_frame else self.collision_distance - SWEEP_CONTACT_INSET
        time_to_meet = (
            math.ceil(minimum_time_to_meet / SWEEP_FRAME_DT) * SWEEP_FRAME_DT
            + contact_distance / relative_speed
        )
        self._aim_at_meeting_point(ball=self.first_ball, time_to_meet=time_to_meet)
        self._aim_at_meeting_point(ball=self.second_ball, time_to_meet=time_to_meet)

        self.maximum_frames_to_collision = round(time_to_meet / SWEEP_FRAME_DT) + 30
        # Balls whose rect the last collision step wrote directly (see step())
        self.rects_written_by_collisions: list[str] = []

    def _create_ball(self, velocity: tuple[float, float]) -> BallSprite:
        """Create a ball with the given velocity, registered in the 'balls' collision layer.

        Returns:
            BallSprite: The ball (placed later by _aim_at_meeting_point).

        """
        ball = BallSprite(
            width=SWEEP_BALL_SIZE,
            height=SWEEP_BALL_SIZE,
            collision_sound=None,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )
        ball.speed = Speed(velocity[0], velocity[1])
        self.game.collisions.get_layer('balls').add(ball)
        return ball

    @staticmethod
    def _aim_at_meeting_point(*, ball: BallSprite, time_to_meet: float) -> None:
        """Place a ball so its visible center reaches SWEEP_MEETING_POINT after time_to_meet."""
        place_ball_center(
            ball,
            center_x=SWEEP_MEETING_POINT[0] - ball.speed.x * time_to_meet,
            center_y=SWEEP_MEETING_POINT[1] - ball.speed.y * time_to_meet,
        )

    def center_distance(self) -> float:
        """Return the distance between ball centers, as the game measures it (integer rects)."""
        _, _, distance, _ = Game._calculate_ball_distance(self.first_ball, self.second_ball)
        return distance

    def world_center_distance(self) -> float:
        """Return the distance between ball centers using sub-pixel world positions."""
        return math.dist(
            (self.first_ball.world_x, self.first_ball.world_y),
            (self.second_ball.world_x, self.second_ball.world_y),
        )

    def velocities(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Return both balls' current velocities."""
        return (
            (self.first_ball.speed.x, self.first_ball.speed.y),
            (self.second_ball.speed.x, self.second_ball.speed.y),
        )

    def step(self) -> bool:
        """Advance one frame exactly as the game loop does.

        Returns:
            bool: True if a collision changed either ball's velocity this frame.

        """
        self.first_ball.dt_tick(SWEEP_FRAME_DT)
        self.second_ball.dt_tick(SWEEP_FRAME_DT)
        velocities_before = self.velocities()
        balls = (('first', self.first_ball), ('second', self.second_ball))
        rects_before = {label: ball.rect.topleft for label, ball in balls}
        self.game._handle_ball_collisions()
        # Collision handling must move the world positions only: the engine rebuilds rect
        # from world_x/world_y before each render, so a rect written here would be undone
        self.rects_written_by_collisions = [
            f'{label} ball rect {rects_before[label]} -> {ball.rect.topleft}, '
            f'world=({ball.world_x:.1f}, {ball.world_y:.1f})'
            for label, ball in balls
            if ball.rect.topleft != rects_before[label]
        ]
        # Then the engine positions the world sprites, as the frame loop does after dt_tick
        for _label, ball in balls:
            drawn_position(ball)
        return self.velocities() != velocities_before


def _assert_velocities_swapped(
    harness: _CollisionSweepHarness,
    first_velocity: tuple[float, float],
    second_velocity: tuple[float, float],
    case_description: str,
) -> None:
    """Assert an equal-mass, head-on elastic collision swapped the balls' velocities."""
    (first_after, second_after) = harness.velocities()
    tolerance = SWEEP_VELOCITY_TOLERANCE_FRACTION * math.dist(first_velocity, second_velocity) + 1.0
    first_error = math.dist(first_after, second_velocity)
    second_error = math.dist(second_after, first_velocity)
    assert first_error <= tolerance and second_error <= tolerance, (
        f'Velocities did not swap ({case_description}). '
        f'Expected first=({second_velocity[0]:.1f}, {second_velocity[1]:.1f}) '
        f'second=({first_velocity[0]:.1f}, {first_velocity[1]:.1f}); '
        f'actual first=({first_after[0]:.1f}, {first_after[1]:.1f}) '
        f'second=({second_after[0]:.1f}, {second_after[1]:.1f}); '
        f'errors {first_error:.1f}, {second_error:.1f} (tolerance {tolerance:.1f})'
    )


def _assert_momentum_and_energy_conserved(
    harness: _CollisionSweepHarness,
    first_velocity: tuple[float, float],
    second_velocity: tuple[float, float],
    case_description: str,
) -> None:
    """Assert the collision conserved total momentum and kinetic energy."""
    (first_after, second_after) = harness.velocities()
    momentum_before = (
        first_velocity[0] + second_velocity[0],
        first_velocity[1] + second_velocity[1],
    )
    momentum_after = (first_after[0] + second_after[0], first_after[1] + second_after[1])
    assert math.dist(momentum_before, momentum_after) <= SWEEP_CONSERVATION_TOLERANCE * max(
        1.0, math.hypot(*momentum_before)
    ), f'Momentum not conserved ({case_description}): {momentum_before} -> {momentum_after}'
    energy_before = math.hypot(*first_velocity) ** 2 + math.hypot(*second_velocity) ** 2
    energy_after = math.hypot(*first_after) ** 2 + math.hypot(*second_after) ** 2
    assert energy_after == pytest.approx(energy_before, rel=SWEEP_CONSERVATION_TOLERANCE), (
        f'Kinetic energy not conserved ({case_description}): '
        f'{energy_before:.1f} -> {energy_after:.1f}'
    )


def _assert_rects_in_sync_after_collision(
    harness: _CollisionSweepHarness,
    case_description: str,
) -> None:
    """Assert collision handling moved only world positions, never a ball's rect.

    The engine rebuilds rect from world_x/world_y before each render, so a rect written by
    collision handling would silently undo the overlap separation.
    """
    out_of_sync_balls = harness.rects_written_by_collisions
    assert not out_of_sync_balls, (
        f'Collision handling wrote rect directly ({case_description}): '
        f'{"; ".join(out_of_sync_balls)}. The engine rebuilds rect from world_x/world_y '
        f'before rendering, undoing the separation (distance '
        f'{harness.center_distance():.1f} now, collision distance '
        f'{harness.collision_distance})'
    )


def _assert_balls_separate_and_stay_apart(
    harness: _CollisionSweepHarness,
    case_description: str,
) -> None:
    """Assert no further collisions and a never-shrinking true (sub-pixel) gap."""
    previous_world_distance = harness.world_center_distance()
    for frames_since_collision in range(1, SWEEP_FRAMES_AFTER_COLLISION + 1):
        collided_again = harness.step()
        world_distance = harness.world_center_distance()
        assert not collided_again, (
            f'Balls collided again {frames_since_collision} frame(s) after the first '
            f'collision ({case_description}); distance {harness.center_distance():.1f}'
        )
        assert world_distance >= previous_world_distance, (
            f'Balls moved back toward each other {frames_since_collision} frame(s) after '
            f'colliding ({case_description}): world distance '
            f'{previous_world_distance:.2f} -> {world_distance:.2f}'
        )
        previous_world_distance = world_distance
    final_distance = harness.center_distance()
    assert final_distance > harness.collision_distance, (
        f'Balls still overlapping {SWEEP_FRAMES_AFTER_COLLISION} frames after colliding '
        f'({case_description}): distance {final_distance:.1f}'
    )


def _run_collision_sweep_case(
    first_velocity: tuple[float, float],
    second_velocity: tuple[float, float],
    *,
    meet_on_frame: bool = False,
) -> None:
    """Collide two balls aimed at the same point and verify the result against physics."""
    harness = _CollisionSweepHarness(first_velocity, second_velocity, meet_on_frame=meet_on_frame)
    case_description = (
        f'first ball velocity=({first_velocity[0]:.1f}, {first_velocity[1]:.1f}), '
        f'second ball velocity=({second_velocity[0]:.1f}, {second_velocity[1]:.1f})'
    )

    collided = any(harness.step() for _ in range(harness.maximum_frames_to_collision))
    assert collided, (
        f'Balls aimed at the same point never collided ({case_description}); '
        f'final distance {harness.center_distance():.1f}'
    )

    _assert_velocities_swapped(harness, first_velocity, second_velocity, case_description)
    _assert_momentum_and_energy_conserved(
        harness, first_velocity, second_velocity, case_description
    )
    _assert_rects_in_sync_after_collision(harness, case_description)
    _assert_balls_separate_and_stay_apart(harness, case_description)


class TestBallCollisionSweepStationaryTarget:
    """A moving ball hits a stationary ball from every direction around the circle."""

    @pytest.mark.parametrize('mover_speed', STATIONARY_TARGET_MOVER_SPEEDS, ids='{:.0f}px/s'.format)
    @pytest.mark.parametrize('approach_angle', SWEEP_ANGLES_DEGREES, ids='from{:03d}deg'.format)
    def test_mover_stops_and_target_takes_its_velocity(self, approach_angle, mover_speed):
        """The mover stops dead and the target leaves with the mover's velocity."""
        _run_collision_sweep_case(
            first_velocity=_velocity_from_angle(approach_angle, mover_speed),
            second_velocity=(0.0, 0.0),
        )


def _moving_pair_cases():
    """Every pair of headings for both balls, at several speed combinations.

    Returns:
        list: pytest params of (first_angle, first_speed, second_angle, second_speed).

    """
    cases = []
    for first_speed, second_speed in MOVING_PAIR_SPEEDS:
        for first_angle in SWEEP_ANGLES_DEGREES:
            for second_angle in SWEEP_ANGLES_DEGREES:
                if first_angle == second_angle and first_speed == second_speed:
                    continue  # identical velocities never approach each other
                cases.append(
                    pytest.param(
                        first_angle,
                        first_speed,
                        second_angle,
                        second_speed,
                        id=(
                            f'first{first_angle:03d}deg@{first_speed:.0f}'
                            f'-second{second_angle:03d}deg@{second_speed:.0f}'
                        ),
                    ),
                )
    return cases


class TestBallCollisionSweepMovingPair:
    """Two moving balls collide at every combination of headings."""

    @pytest.mark.parametrize(
        ('first_angle', 'first_speed', 'second_angle', 'second_speed'),
        _moving_pair_cases(),
    )
    def test_balls_swap_velocities(self, first_angle, first_speed, second_angle, second_speed):
        """Two equal-mass balls aimed at the same point swap velocities."""
        _run_collision_sweep_case(
            first_velocity=_velocity_from_angle(first_angle, first_speed),
            second_velocity=_velocity_from_angle(second_angle, second_speed),
        )


# Head-on pairs closing at 10 px a frame (300 px/s each at 60 FPS), the visible circles' whole
# collision distance (10). Aimed to meet exactly on a frame, the frame before has them just
# touching (distance 10, no AABB overlap) and the meeting frame has their centres on the same
# pixel (no contact normal): the end-of-frame check sees no collision on any frame, and they
# passed through each other until the swept check (BUGS.md #174)
FRAME_ALIGNED_HEAD_ON_ANGLES_DEGREES = (0, 15, 45, 90)
FRAME_ALIGNED_HEAD_ON_SPEED = 300.0
# PaddleSlap's speed cap (Game._cap_ball_speeds): two balls at it close about 16.7 px a frame, so
# from 11 px apart they end crossed and overlapping on the wrong sides (5.7 px), where the
# end-of-frame check computes a reversed contact direction
CAPPED_SPEED = 500.0
PARTLY_CROSSING_START_X = (394.5, 405.5)
# Faster than the cap (a ball's speed-ups can pass it; the cap applies after ball collisions):
# 23.3 px a frame closing, so from 11 px apart they end 12.3 px apart on the far side
OVER_CAP_SPEED = 700.0


class TestBallCollisionSweepFrameAlignedMeeting:
    """Balls whose centres coincide on a frame still collide (the swept check, BUGS.md #174)."""

    @pytest.mark.parametrize(
        'first_angle', FRAME_ALIGNED_HEAD_ON_ANGLES_DEGREES, ids='first{:03d}deg'.format
    )
    def test_head_on_balls_meeting_on_a_frame_collide(self, first_angle):
        """Two head-on balls aimed to meet exactly on a frame swap velocities."""
        _run_collision_sweep_case(
            first_velocity=_velocity_from_angle(first_angle, FRAME_ALIGNED_HEAD_ON_SPEED),
            second_velocity=_velocity_from_angle(first_angle + 180, FRAME_ALIGNED_HEAD_ON_SPEED),
            meet_on_frame=True,
        )


def _ticked_pair(
    *, first_start: tuple[float, float], second_start: tuple[float, float], velocity: float
) -> tuple[_CollisionSweepHarness, BallSprite, BallSprite]:
    """Return a harness with two head-on balls on the x axis, placed and ticked one frame.

    Returns:
        The harness and its two balls, each at its frame's end with its frame start recorded.

    """
    harness = _CollisionSweepHarness((velocity, 0.0), (-velocity, 0.0))
    first_ball, second_ball = harness.first_ball, harness.second_ball
    place_ball_center(first_ball, center_x=first_start[0], center_y=first_start[1])
    place_ball_center(second_ball, center_x=second_start[0], center_y=second_start[1])
    first_ball.dt_tick(SWEEP_FRAME_DT)
    second_ball.dt_tick(SWEEP_FRAME_DT)
    return harness, first_ball, second_ball


class TestSweptBallCollision:
    """The swept check catches only what the end-of-frame check cannot (BUGS.md #174)."""

    @pytest.mark.parametrize(
        ('speed', 'end_state'),
        [(CAPPED_SPEED, 'overlapping-crossed'), (OVER_CAP_SPEED, 'apart-again')],
        ids=['overlapping-crossed', 'apart-again'],
    )
    def test_a_pair_that_crossed_within_the_frame_collides_where_it_touched(
        self, speed, end_state, mocker
    ):
        """Crossed by the frame's end: put back where it touched, bounced back, with its sound."""
        harness, first_ball, second_ball = _ticked_pair(
            first_start=(PARTLY_CROSSING_START_X[0], 240.0),
            second_start=(PARTLY_CROSSING_START_X[1], 240.0),
            velocity=speed,
        )
        first_ball.snd = mocker.Mock()
        _dx, _dy, end_distance, collision_distance = Game._calculate_ball_distance(
            first_ball, second_ball
        )
        assert first_ball.world_x > second_ball.world_x  # crossed
        assert (end_distance > collision_distance) is (end_state == 'apart-again')

        harness.game._ball_collision_pairs = []
        harness.game._handle_ball_collisions()

        assert harness.game._ball_collision_pairs == [(first_ball, second_ball)]
        assert first_ball.speed.x < 0 < second_ball.speed.x  # bounced back, not on through
        assert first_ball.world_x < second_ball.world_x  # back on its own side
        first_ball.snd.play.assert_called_once_with()

    def test_an_overlap_that_did_not_cross_is_the_end_checks(self):
        """Closing into an overlap without crossing: the end check collides it, as before."""
        harness, first_ball, second_ball = _ticked_pair(
            first_start=(384.0, 240.0), second_start=(398.0, 240.0), velocity=300.0
        )

        assert Game._swept_contact(first_ball, second_ball) is None
        harness.game._ball_collision_pairs = []
        harness.game._handle_ball_collisions()
        assert harness.game._ball_collision_pairs == [(first_ball, second_ball)]

    def test_a_pair_touching_only_at_the_frames_end_is_left_to_the_next_frame(self):
        """Exactly touching at the end, as before the swept check: the next frame collides it."""
        closing_per_frame = 2 * 300.0 * SWEEP_FRAME_DT
        harness, first_ball, _second_ball = _ticked_pair(
            first_start=(390.0 - closing_per_frame / 2 - 5.0, 240.0),
            second_start=(390.0 + closing_per_frame / 2 + 5.0, 240.0),
            velocity=300.0,
        )

        harness.game._ball_collision_pairs = []
        harness.game._collide_balls_that_met_within_the_frame()

        assert harness.game._ball_collision_pairs == []
        assert first_ball.speed.x > 0

    def test_a_ball_that_never_ticked_is_not_swept(self):
        """No frame start yet (a ball added this frame): nothing to follow."""
        harness = _CollisionSweepHarness((CAPPED_SPEED, 0.0), (-CAPPED_SPEED, 0.0))

        assert harness.first_ball.frame_start_world_position is None
        assert Game._swept_contact(harness.first_ball, harness.second_ball) is None

    def test_a_pair_in_cooldown_is_not_swept_again(self):
        """A pair that just collided waits out its cooldown, whichever way its key was written."""
        harness, first_ball, second_ball = _ticked_pair(
            first_start=(PARTLY_CROSSING_START_X[0], 240.0),
            second_start=(PARTLY_CROSSING_START_X[1], 240.0),
            velocity=CAPPED_SPEED,
        )
        harness.game._ball_collision_cooldowns = {(id(second_ball), id(first_ball)): 5}

        harness.game._ball_collision_pairs = []
        harness.game._collide_balls_that_met_within_the_frame()

        assert harness.game._ball_collision_pairs == []


class TestFirstContactFraction:
    """When in a frame a closing pair first touches (paddleslap.first_contact_fraction)."""

    @pytest.mark.parametrize(
        ('start', 'motion', 'expected'),
        [
            ((20.0, 0.0), (-20.0, 0.0), 0.5),  # touches halfway
            ((8.0, 0.0), (-8.0, 0.0), 0.0),  # already touching (closer) at the start
            ((20.0, 0.0), (20.0, 0.0), None),  # separating
            ((20.0, 0.0), (0.0, 0.0), None),  # not moving
            ((20.0, 20.0), (-20.0, 0.0), None),  # passes wide
            ((20.0, 0.0), (-10.0, 0.0), None),  # touches exactly at the frame's end
            ((40.0, 0.0), (-20.0, 0.0), None),  # touches after the frame
        ],
        ids=['halfway', 'at-start', 'separating', 'still', 'wide', 'at-end', 'after'],
    )
    def test_the_fraction(self, start, motion, expected):
        assert paddleslap.first_contact_fraction(
            start=start, motion=motion, contact_distance=10.0
        ) == (None if expected is None else pytest.approx(expected))
