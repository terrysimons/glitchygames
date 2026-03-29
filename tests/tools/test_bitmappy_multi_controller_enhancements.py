"""Tests covering uncovered lines in bitmappy_multi_controller_enhancements.py.

Targets uncovered lines: 119, 147, 153, 165, 224-226, 232-240,
255-270, 392, 395.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.bitmappy.controllers.enhancements import (
    BitmappyMultiControllerEnhancements,
)


@pytest.fixture
def mock_enhancements(mocker):
    """Create a BitmappyMultiControllerEnhancements with mocked dependencies."""
    mock_scene = mocker.Mock()

    # Set up film_strips
    mock_film_strip = mocker.Mock()
    mock_film_strip.frames = [mocker.Mock(), mocker.Mock(), mocker.Mock()]
    mock_scene.film_strips = {'idle': mock_film_strip, 'walk': mock_film_strip}

    # Set up controller_selections
    mock_selection_0 = mocker.Mock()
    mock_selection_0.get_selection.return_value = ('idle', 0)
    mock_selection_0.is_active.return_value = True

    mock_selection_1 = mocker.Mock()
    mock_selection_1.get_selection.return_value = ('idle', 1)
    mock_selection_1.is_active.return_value = False

    mock_scene.controller_selections = {0: mock_selection_0, 1: mock_selection_1}

    # Set up multi_controller_manager
    mock_controller_info_0 = mocker.Mock()
    mock_controller_info_0.controller_id = 0
    mock_controller_info_0.instance_id = 100
    mock_controller_info_0.color = (255, 0, 0)

    mock_controller_info_1 = mocker.Mock()
    mock_controller_info_1.controller_id = 1
    mock_controller_info_1.instance_id = 101
    mock_controller_info_1.color = (0, 255, 0)

    mock_scene.multi_controller_manager = mocker.Mock()
    mock_scene.multi_controller_manager.controllers = {
        100: mock_controller_info_0,
        101: mock_controller_info_1,
    }

    # Set up visual_collision_manager
    mock_scene.visual_collision_manager = mocker.Mock()
    mock_scene.visual_collision_manager.indicators = {}
    mock_scene.visual_collision_manager.add_controller_indicator = mocker.Mock()
    mock_scene.visual_collision_manager.update_controller_position = mocker.Mock()
    mock_scene.visual_collision_manager.remove_controller_indicator = mocker.Mock()
    mock_scene.visual_collision_manager.optimize_positioning = mocker.Mock()

    enhancements = BitmappyMultiControllerEnhancements(mock_scene)

    return enhancements


class TestEnhancedNavigationAnimationWrap:
    """Test enhanced_navigation animation direction with frame preservation (line 119)."""

    def test_navigate_animation_preserves_frame_or_defaults(self, mock_enhancements, mocker):
        """Test navigating to an animation that doesn't exist in film_strips (line 119).

        When the new animation is not in film_strips, new_frame defaults to 0.
        """
        enhancements = mock_enhancements

        # Remove walk from film_strips to trigger the else at line 119
        del enhancements.scene.film_strips['walk']

        # Set last_update_time to past to allow visual update
        enhancements.last_update_time = 0

        result = enhancements.enhanced_navigation(0, 'animation', amount=1)

        assert result is True


class TestEnhancedVisualManagementEdgeCases:
    """Test enhanced_visual_management edge cases (lines 147, 153, 165)."""

    def test_enhanced_visual_management_invalid_controller(self, mock_enhancements):
        """Test enhanced_visual_management with non-existent controller (line 147).

        When controller_id is not in controller_selections, the method
        returns early.
        """
        enhancements = mock_enhancements
        # Controller 99 doesn't exist
        enhancements.enhanced_visual_management(99)

        # No crash, no visual manager calls
        enhancements.visual_manager.update_controller_position.assert_not_called()

    def test_enhanced_visual_management_invalid_animation(self, mock_enhancements):
        """Test enhanced_visual_management with invalid animation (line 153).

        When the controller's selection has an animation not in film_strips,
        the method returns early.
        """
        enhancements = mock_enhancements

        # Set selection to a non-existent animation
        enhancements.controller_selections[0].get_selection.return_value = ('nonexistent', 0)

        enhancements.enhanced_visual_management(0)

        # Should return early without updating
        enhancements.visual_manager.update_controller_position.assert_not_called()

    def test_enhanced_visual_management_creates_indicator_when_missing(self, mock_enhancements):
        """Test enhanced_visual_management creates indicator when not present (line 165).

        When controller_id is not in visual_manager.indicators, a new
        enhanced indicator is created via _create_enhanced_visual_indicator.
        """
        enhancements = mock_enhancements

        # Ensure indicator doesn't exist yet
        enhancements.visual_manager.indicators = {}

        enhancements.enhanced_visual_management(0)

        # Should have called add_controller_indicator
        enhancements.visual_manager.add_controller_indicator.assert_called()

    def test_enhanced_visual_management_updates_existing_indicator(self, mock_enhancements):
        """Test enhanced_visual_management updates existing indicator (line 165 else).

        When controller_id IS in visual_manager.indicators, it calls
        update_controller_position instead.
        """
        enhancements = mock_enhancements

        # Put an indicator in the dict
        enhancements.visual_manager.indicators = {0: 'existing_indicator'}

        enhancements.enhanced_visual_management(0)

        enhancements.visual_manager.update_controller_position.assert_called()


class TestCreateEnhancedVisualIndicatorNoMatch:
    """Test _create_enhanced_visual_indicator when no controller_info found (lines 224-226)."""

    def test_create_indicator_no_controller_info(self, mock_enhancements, mocker):
        """Test _create_enhanced_visual_indicator returns early when no matching info.

        When no ControllerInfo has the matching controller_id, the method
        returns early (lines 228-229).
        """
        enhancements = mock_enhancements

        # Clear controllers so no match is found
        enhancements.manager.controllers = {}

        enhancements._create_enhanced_visual_indicator(0, (100, 100))

        # Should not have called add_controller_indicator
        enhancements.visual_manager.add_controller_indicator.assert_not_called()


class TestApplyVisualCustomizations:
    """Test _apply_visual_customizations with shape options (lines 232-240, 255-270)."""

    def test_apply_customizations_no_customizations(self, mock_enhancements):
        """Test _apply_visual_customizations when controller not in customizations.

        Covers line 249 early return.
        """
        enhancements = mock_enhancements
        enhancements.visual_customizations = {}

        enhancements._apply_visual_customizations(0)

        # No crash, no changes

    def test_apply_customizations_circle_shape(self, mock_enhancements, mocker):
        """Test _apply_visual_customizations with circle shape (line 266)."""
        from glitchygames.bitmappy.indicators.collision import IndicatorShape

        enhancements = mock_enhancements

        mock_indicator = mocker.Mock()
        enhancements.visual_manager.indicators = {0: mock_indicator}
        enhancements.visual_customizations[0] = {
            'size': 14,
            'shape': 'circle',
        }

        enhancements._apply_visual_customizations(0)

        assert mock_indicator.size == 14
        assert mock_indicator.shape == IndicatorShape.CIRCLE

    def test_apply_customizations_square_shape(self, mock_enhancements, mocker):
        """Test _apply_visual_customizations with square shape (line 268)."""
        from glitchygames.bitmappy.indicators.collision import IndicatorShape

        enhancements = mock_enhancements

        mock_indicator = mocker.Mock()
        enhancements.visual_manager.indicators = {0: mock_indicator}
        enhancements.visual_customizations[0] = {
            'size': 10,
            'shape': 'square',
        }

        enhancements._apply_visual_customizations(0)

        assert mock_indicator.shape == IndicatorShape.SQUARE

    def test_apply_customizations_triangle_shape(self, mock_enhancements, mocker):
        """Test _apply_visual_customizations with triangle (default) shape (line 270)."""
        from glitchygames.bitmappy.indicators.collision import IndicatorShape

        enhancements = mock_enhancements

        mock_indicator = mocker.Mock()
        enhancements.visual_manager.indicators = {0: mock_indicator}
        enhancements.visual_customizations[0] = {
            'size': 12,
            'shape': 'triangle',
        }

        enhancements._apply_visual_customizations(0)

        assert mock_indicator.shape == IndicatorShape.TRIANGLE


class TestExecuteGroupActionPaths:
    """Test execute_group_action with navigate and activate (lines 392, 395)."""

    def test_execute_group_action_navigate_failure(self, mock_enhancements, mocker):
        """Test execute_group_action navigate that fails (line 392).

        When enhanced_navigation returns False for a controller, success
        is set to False.
        """
        enhancements = mock_enhancements

        # Create a group
        enhancements.create_controller_group('test_group', [0])

        # Make navigation fail
        mocker.patch.object(enhancements, 'enhanced_navigation', return_value=False)

        result = enhancements.execute_group_action('test_group', 'navigate', direction='frame')

        assert result is False

    def test_execute_group_action_activate_failure(self, mock_enhancements, mocker):
        """Test execute_group_action activate that fails (line 395).

        When enhanced_controller_activation returns False, success
        is set to False.
        """
        enhancements = mock_enhancements

        enhancements.create_controller_group('test_group', [0])

        mocker.patch.object(enhancements, 'enhanced_controller_activation', return_value=False)

        result = enhancements.execute_group_action('test_group', 'activate')

        assert result is False

    def test_execute_group_action_unknown_action(self, mock_enhancements):
        """Test execute_group_action with unknown action name."""
        enhancements = mock_enhancements

        enhancements.create_controller_group('test_group', [0])

        # Unknown action - no handler, success stays True
        result = enhancements.execute_group_action('test_group', 'unknown_action')

        assert result is True
