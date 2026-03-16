"""Tests for the performance example usage module."""

from glitchygames.performance.example_usage import ExampleGameObject, example_game_loop


class TestExampleGameObject:
    """Tests for the ExampleGameObject class."""

    def test_initialization(self):
        """Test default initialization values."""
        obj = ExampleGameObject()
        assert obj.x == 0
        assert obj.y == 0
        assert obj.speed == 100

    def test_dt_tick_updates_position(self):
        """Test that dt_tick moves the object."""
        obj = ExampleGameObject()
        obj.dt_tick(0.1)

        # Position should have changed from (0, 0)
        # The exact value depends on adaptive dt adjustment,
        # but it should have moved in the positive direction
        assert obj.x > 0
        assert obj.y > 0

    def test_dt_tick_proportional_to_speed(self):
        """Test that movement is proportional to speed."""
        obj1 = ExampleGameObject()
        obj1.speed = 100
        obj1.dt_tick(0.01)

        obj2 = ExampleGameObject()
        obj2.speed = 200
        obj2.dt_tick(0.01)

        # obj2 should have moved further than obj1 (approximately 2x)
        assert obj2.x > obj1.x

    def test_dt_tick_multiple_calls(self):
        """Test that multiple dt_tick calls accumulate position."""
        obj = ExampleGameObject()
        obj.dt_tick(0.01)
        pos_after_first = obj.x

        obj.dt_tick(0.01)
        pos_after_second = obj.x

        assert pos_after_second > pos_after_first

    def test_get_performance_info_returns_string(self):
        """Test that get_performance_info returns a formatted string."""
        obj = ExampleGameObject()
        obj.dt_tick(0.016)

        info = obj.get_performance_info()
        assert isinstance(info, str)
        assert 'Avg FPS' in info
        assert 'History' in info


class TestExampleGameLoop:
    """Tests for the example_game_loop function."""

    def test_example_game_loop_runs_without_error(self):
        """Test that the example game loop executes without exceptions."""
        # The function should complete without raising
        example_game_loop()
