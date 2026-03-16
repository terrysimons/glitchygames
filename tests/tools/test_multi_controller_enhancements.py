"""Tests for bitmappy multi-controller enhancements."""

import pytest

from glitchygames.tools.bitmappy_multi_controller_enhancements import (
    MAX_CONTROLLER_ACTION_HISTORY,
    BitmappyMultiControllerEnhancements,
)


@pytest.fixture
def mock_controller_selection(mocker):
    """Create a mock ControllerSelection.

    Returns:
        Mock: A mock ControllerSelection instance.

    """
    selection = mocker.Mock()
    selection.is_active.return_value = True
    selection.get_selection.return_value = ('walk', 0)
    return selection


@pytest.fixture
def mock_film_strip(mocker):
    """Create a mock film strip with frames.

    Returns:
        Mock: A mock film strip with 4 frames.

    """
    strip = mocker.Mock()
    strip.frames = [mocker.Mock() for _ in range(4)]
    return strip


@pytest.fixture
def mock_scene(mocker, mock_controller_selection, mock_film_strip):
    """Create a mock BitmapEditorScene.

    Returns:
        Mock: A mock BitmapEditorScene with controllers and film strips.

    """
    scene = mocker.Mock()
    scene.multi_controller_manager = mocker.Mock()
    scene.multi_controller_manager.controllers = {}
    scene.visual_collision_manager = mocker.Mock()
    scene.visual_collision_manager.indicators = {}
    scene.controller_selections = {0: mock_controller_selection, 1: mock_controller_selection}
    scene.film_strips = {'walk': mock_film_strip, 'run': mock_film_strip}
    return scene


@pytest.fixture
def enhancements(mock_scene):
    """Create a BitmappyMultiControllerEnhancements instance.

    Returns:
        BitmappyMultiControllerEnhancements: An initialized enhancements instance.

    """
    return BitmappyMultiControllerEnhancements(mock_scene)


class TestBitmappyMultiControllerEnhancements:
    """Tests for BitmappyMultiControllerEnhancements."""

    def test_initialization(self, enhancements, mock_scene):
        """Test initialization sets up correctly."""
        assert enhancements.scene is mock_scene
        assert enhancements.controller_history == {}
        assert enhancements.performance_metrics == {}
        assert enhancements.visual_customizations == {}
        assert enhancements.controller_groups == {}
        assert enhancements.update_throttle == pytest.approx(0.016)

    def test_enhanced_controller_activation_success(self, enhancements):
        """Test successful controller activation."""
        result = enhancements.enhanced_controller_activation(0)
        assert result is True
        assert 0 in enhancements.controller_history
        assert 0 in enhancements.visual_customizations
        assert enhancements.visual_customizations[0]['shape'] == 'triangle'
        assert enhancements.visual_customizations[0]['size'] == 12

    def test_enhanced_controller_activation_unknown_controller(self, enhancements):
        """Test activation of a controller not in selections."""
        result = enhancements.enhanced_controller_activation(99)
        assert result is False

    def test_enhanced_navigation_frame_forward(self, enhancements, mock_controller_selection):
        """Test navigating forward by frame."""
        mock_controller_selection.get_selection.return_value = ('walk', 0)
        # Force last_update_time far in the past so throttle doesn't block
        enhancements.last_update_time = 0

        result = enhancements.enhanced_navigation(0, 'frame', 1)
        assert result is True
        mock_controller_selection.set_selection.assert_called()

    def test_enhanced_navigation_frame_backward_clamps_to_zero(
        self, enhancements, mock_controller_selection
    ):
        """Test that navigating backward past frame 0 clamps to 0."""
        mock_controller_selection.get_selection.return_value = ('walk', 0)
        enhancements.last_update_time = 0

        result = enhancements.enhanced_navigation(0, 'frame', -1)
        assert result is True
        # Should have set frame to max(0, 0 + (-1)) = 0
        call_args = mock_controller_selection.set_selection.call_args
        assert call_args[0][1] == 0  # frame index should be 0

    def test_enhanced_navigation_animation_direction(self, enhancements, mock_controller_selection):
        """Test navigating between animations."""
        mock_controller_selection.get_selection.return_value = ('walk', 0)
        enhancements.last_update_time = 0

        result = enhancements.enhanced_navigation(0, 'animation', 1)
        assert result is True
        mock_controller_selection.set_selection.assert_called()

    def test_enhanced_navigation_unknown_controller(self, enhancements):
        """Test navigation with unknown controller ID."""
        result = enhancements.enhanced_navigation(99, 'frame', 1)
        assert result is False

    def test_record_controller_action(self, enhancements):
        """Test that actions are recorded in history."""
        enhancements._record_controller_action(0, 'test_action', {'key': 'value'})

        assert 0 in enhancements.controller_history
        assert len(enhancements.controller_history[0]) == 1
        assert enhancements.controller_history[0][0]['action'] == 'test_action'
        assert 'timestamp' in enhancements.controller_history[0][0]

    def test_record_controller_action_limits_history(self, enhancements):
        """Test that history is limited to MAX_CONTROLLER_ACTION_HISTORY."""
        for i in range(MAX_CONTROLLER_ACTION_HISTORY + 50):
            enhancements._record_controller_action(0, f'action_{i}', {})

        assert len(enhancements.controller_history[0]) == MAX_CONTROLLER_ACTION_HISTORY

    def test_get_controller_performance_stats(self, enhancements):
        """Test getting performance stats for a controller."""
        stats = enhancements.get_controller_performance_stats(0)
        assert stats['controller_id'] == 0
        assert stats['history_length'] == 0
        assert stats['last_action'] is None

    def test_get_controller_performance_stats_with_history(self, enhancements):
        """Test getting performance stats after recording actions."""
        enhancements._record_controller_action(0, 'paint', {'x': 10})

        stats = enhancements.get_controller_performance_stats(0)
        assert stats['history_length'] == 1
        assert stats['last_action'] is not None
        assert stats['last_action']['action'] == 'paint'

    def test_create_controller_group(self, enhancements):
        """Test creating a controller group."""
        result = enhancements.create_controller_group('team_a', [0, 1])
        assert result is True
        assert 'team_a' in enhancements.controller_groups
        assert enhancements.controller_groups['team_a'] == [0, 1]

    def test_create_controller_group_invalid_controller(self, enhancements):
        """Test creating a group with an invalid controller ID."""
        result = enhancements.create_controller_group('team_a', [0, 99])
        assert result is False

    def test_create_controller_group_is_copy(self, enhancements):
        """Test that the group stores a copy of the list."""
        controller_ids = [0, 1]
        enhancements.create_controller_group('team_a', controller_ids)
        controller_ids.append(99)
        assert enhancements.controller_groups['team_a'] == [0, 1]

    def test_execute_group_action_navigate(self, enhancements, mock_controller_selection):
        """Test executing a navigate action on a group."""
        enhancements.create_controller_group('team_a', [0, 1])
        enhancements.last_update_time = 0
        mock_controller_selection.get_selection.return_value = ('walk', 0)

        result = enhancements.execute_group_action(
            'team_a', 'navigate', direction='frame', amount=1
        )
        assert result is True

    def test_execute_group_action_unknown_group(self, enhancements):
        """Test executing action on a nonexistent group."""
        result = enhancements.execute_group_action('nonexistent', 'navigate')
        assert result is False

    def test_execute_group_action_activate(self, enhancements):
        """Test executing an activate action on a group."""
        enhancements.create_controller_group('team_a', [0, 1])
        enhancements.last_update_time = 0

        result = enhancements.execute_group_action('team_a', 'activate')
        assert result is True

    def test_get_controller_status_summary(self, enhancements, mock_controller_selection):
        """Test getting a comprehensive status summary."""
        mock_controller_selection.is_active.return_value = True
        mock_controller_selection.get_selection.return_value = ('walk', 0)

        summary = enhancements.get_controller_status_summary()
        assert summary['total_controllers'] == 2
        assert summary['active_controllers'] == 2
        assert summary['controller_groups'] == 0
        assert 0 in summary['controllers']
        assert 1 in summary['controllers']
        assert summary['controllers'][0]['active'] is True

    def test_cleanup_inactive_controllers(self, enhancements, mock_scene, mocker):
        """Test cleaning up inactive controllers."""
        # Make controller 1 inactive
        inactive_selection = mocker.Mock()
        inactive_selection.is_active.return_value = False
        inactive_selection.get_selection.return_value = ('walk', 0)
        mock_scene.controller_selections[1] = inactive_selection

        # Set up resources for controller 1
        enhancements.controller_history[1] = [{'action': 'test'}]
        enhancements.visual_customizations[1] = {'size': 12}
        enhancements.position_cache[1] = (10, 20)

        cleaned = enhancements.cleanup_inactive_controllers()
        assert cleaned == 1
        assert 1 not in mock_scene.controller_selections
        assert 1 not in enhancements.controller_history
        assert 1 not in enhancements.visual_customizations
        assert 1 not in enhancements.position_cache

    def test_optimize_performance(self, enhancements, mock_scene):
        """Test performance optimization."""
        # Add some cached positions
        enhancements.position_cache[0] = (10, 20)
        enhancements.position_cache[1] = (30, 40)

        results = enhancements.optimize_performance()
        assert results['cache_cleared'] == 2
        assert len(enhancements.position_cache) == 0
        mock_scene.visual_collision_manager.optimize_positioning.assert_called_once()

    def test_update_performance_metrics(self, enhancements):
        """Test performance metrics tracking."""
        enhancements._update_performance_metrics('test_op', 1000.0)
        assert 'test_op' in enhancements.performance_metrics
        assert enhancements.performance_metrics['test_op'] == pytest.approx(1000.0)

    def test_update_performance_metrics_calculates_diff(self, enhancements):
        """Test that subsequent calls calculate time difference."""
        enhancements._update_performance_metrics('test_op', 1000.0)
        enhancements._update_performance_metrics('test_op', 1001.5)
        assert enhancements.performance_metrics['test_op'] == pytest.approx(1.5)

    def test_calculate_enhanced_position(self, enhancements):
        """Test position calculation for visual indicators."""
        position = enhancements._calculate_enhanced_position(0, 'walk', 2)
        assert isinstance(position, tuple)
        assert len(position) == 2
        assert isinstance(position[0], int)
        assert isinstance(position[1], int)

    def test_calculate_enhanced_position_uses_cache(self, enhancements):
        """Test that position cache is used on second call."""
        enhancements.position_cache[0] = (999, 888)
        position = enhancements._calculate_enhanced_position(0, 'walk', 2)
        assert position == (999, 888)
