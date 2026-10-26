#!/usr/bin/env python3
"""Test coverage for BallSprite's public trajectory API."""

from glitchygames.game_objects.ball import BallSprite

TRAJECTORY_LIMIT = 5


def _record_points(ball: BallSprite, count: int) -> None:
    """Record count points whose x is the point's index."""
    for index in range(count):
        ball.record_trajectory_point(
            x=float(index),
            y=float(index) * 2,
            speed_x=1.5,
            speed_y=-2.5,
            limit=TRAJECTORY_LIMIT,
        )


class TestBallTrajectory:
    """Test BallSprite.trajectory and record_trajectory_point."""

    def test_a_new_ball_has_no_trajectory(self):
        """A new ball has recorded nothing."""
        ball = BallSprite()

        assert ball.trajectory == ()

    def test_recorded_points_come_back_oldest_first(self):
        """Each point holds x, y, speed x and speed y, in the order recorded."""
        ball = BallSprite()

        _record_points(ball, 3)

        assert ball.trajectory == (
            (0.0, 0.0, 1.5, -2.5),
            (1.0, 2.0, 1.5, -2.5),
            (2.0, 4.0, 1.5, -2.5),
        )

    def test_the_trajectory_keeps_only_the_latest_limit_points(self):
        """Recording limit + 2 points drops the first two."""
        ball = BallSprite()

        _record_points(ball, TRAJECTORY_LIMIT + 2)

        assert len(ball.trajectory) == TRAJECTORY_LIMIT
        assert [point[0] for point in ball.trajectory] == [2.0, 3.0, 4.0, 5.0, 6.0]

    def test_the_trajectory_cannot_be_changed_through_the_property(self):
        """The property hands back a tuple, and a later record does not alter an earlier read."""
        ball = BallSprite()
        _record_points(ball, 1)

        earlier_read = ball.trajectory
        _record_points(ball, 1)

        assert isinstance(earlier_read, tuple)
        assert len(earlier_read) == 1
        assert len(ball.trajectory) == 2
