#!/usr/bin/env python3
"""Test suite for film strip undo/redo functionality.

Tests complex scenarios involving:
- Multiple animation strips
- Frame creation and editing
- Frame selection switching
- Strip creation and deletion
- Mixed undo/redo operations
"""

from typing import cast

import pygame
import pytest

from glitchygames.bitmappy.history.operations import (
    CanvasOperationTracker,
    CrossAreaOperationTracker,
    FilmStripOperationTracker,
)
from glitchygames.bitmappy.history.undo_redo import UndoRedoManager
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame


class TestFilmStripUndoRedo:
    """Test film strip undo/redo functionality."""

    @pytest.fixture
    def mock_scene(self):
        """Create a mock scene for testing.

        Returns:
            object: The result.

        """

        class MockScene:
            def __init__(self):
                self._applying_undo_redo = False
                self.canvas = MockCanvas(scene=self)
                self.undo_redo_manager = UndoRedoManager(max_history=50)
                self.canvas_operation_tracker = CanvasOperationTracker(
                    self.undo_redo_manager, editor=self,
                )
                self.film_strip_operation_tracker = FilmStripOperationTracker(
                    self.undo_redo_manager, editor=self,
                )
                self.cross_area_operation_tracker = CrossAreaOperationTracker(
                    self.undo_redo_manager, editor=self,
                )

                # Stub film_strip_coordinator so FrameAddCommand/AnimationAddCommand
                # don't raise AttributeError during undo/redo operations
                self.film_strip_coordinator = MockFilmStripCoordinator()

                # Track current state
                self.current_animation = 'strip_1'
                self.current_frame = 0
                self.animated_sprite = self._create_test_sprite()

            def _create_test_sprite(self):
                """Create a test animated sprite with initial data.

                Returns:
                    object: The result.

                """
                sprite = AnimatedSprite()

                # Create initial animation with one frame
                frame1 = SpriteFrame(surface=pygame.Surface((32, 32)), duration=1.0)
                pixel_data = cast('list[tuple[int, ...]]', [(255, 0, 0)] * (32 * 32))  # Red frame
                frame1.pixels = pixel_data

                sprite._animations = {'strip_1': [frame1]}

                return sprite

            def _apply_pixel_change(self, x, y, color):
                """Mock pixel change application.

                Returns:
                    object: The result.

                """
                return True

            def _add_frame(self, frame_index, animation_name, frame_data):
                """Mock frame addition.

                Returns:
                    object: The result.

                """
                return True

            def _delete_frame(self, frame_index, animation_name):
                """Mock frame deletion.

                Returns:
                    object: The result.

                """
                return True

            def _reorder_frame(self, old_index, new_index, animation_name):
                """Mock frame reordering.

                Returns:
                    object: The result.

                """
                return True

            def _add_animation(self, animation_name, animation_data):
                """Mock animation addition.

                Returns:
                    object: The result.

                """
                return True

            def _delete_animation(self, animation_name):
                """Mock animation deletion.

                Returns:
                    object: The result.

                """
                return True

            def _apply_frame_selection(self, animation, frame):
                """Mock frame selection.

                Returns:
                    object: The result.

                """
                self.current_animation = animation
                self.current_frame = frame
                return True

            def switch_to_frame(self, animation, frame):
                """Switch to a specific frame and track the selection."""
                self.film_strip_operation_tracker.add_frame_selection(animation, frame)

            def create_frame(self, animation, frame_index):
                """Create a new frame and track it.

                Ensures the animated sprite's frame list has enough entries so
                that ``frame_index`` is valid for both insertion and undo.
                """
                # Use empty pixels to avoid PixelArray.flat issues during redo
                frame_data = {
                    'width': 32,
                    'height': 32,
                    'pixels': [],
                    'duration': 1.0,
                }
                # Ensure the animation list exists and is long enough
                frame = SpriteFrame(surface=pygame.Surface((32, 32)), duration=1.0)
                if animation not in self.canvas.animated_sprite._animations:
                    self.canvas.animated_sprite._animations[animation] = []
                frames_list = self.canvas.animated_sprite._animations[animation]
                # Pad with placeholder frames if needed so insert(frame_index) works
                while len(frames_list) < frame_index:
                    placeholder = SpriteFrame(surface=pygame.Surface((32, 32)), duration=1.0)
                    frames_list.append(placeholder)
                frames_list.insert(frame_index, frame)

                self.film_strip_operation_tracker.add_frame_added(
                    frame_index, animation, frame_data,
                )

            def create_animation(self, animation_name):
                """Create a new animation and track it."""
                # Use empty pixels to avoid PixelArray.flat issues during redo
                animation_data = {
                    'frames': [
                        {
                            'width': 32,
                            'height': 32,
                            'pixels': [],
                            'duration': 1.0,
                        },
                    ],
                    'frame_count': 1,
                }
                # Actually add the animation to the animated sprite so undo can find it
                frame = SpriteFrame(surface=pygame.Surface((32, 32)), duration=1.0)
                self.canvas.animated_sprite._animations[animation_name] = [frame]

                self.film_strip_operation_tracker.add_animation_added(
                    animation_name, animation_data,
                )

            def edit_pixel(self, x, y, old_color, new_color):
                """Edit a pixel and track it."""
                self.canvas_operation_tracker.add_single_pixel_change(x, y, old_color, new_color)

            def undo(self):
                """Perform undo operation.

                Returns:
                    object: The result.

                """
                return self.undo_redo_manager.undo()

            def redo(self):
                """Perform redo operation.

                Returns:
                    object: The result.

                """
                return self.undo_redo_manager.redo()

            def get_undo_count(self):
                """Get number of operations in undo stack.

                Returns:
                    object: The undo count.

                """
                return len(self.undo_redo_manager.undo_stack)

            def get_redo_count(self):
                """Get number of operations in redo stack.

                Returns:
                    object: The redo count.

                """
                return len(self.undo_redo_manager.redo_stack)

        class MockCanvasInterface:
            def set_pixel_at(self, x, y, color):
                """Mock pixel setter."""
                return True

        class MockFilmStripCoordinator:
            """Stub coordinator so command objects don't raise AttributeError."""

            def refresh_all_film_strip_widgets(self, animation_name):
                """No-op."""

            def on_frame_inserted(self, animation_name, frame_index):
                """No-op."""

            def on_frame_removed(self, animation_name, frame_index):
                """No-op."""

            def on_sprite_loaded(self, animated_sprite):
                """No-op."""

        class MockFrameManager:
            def __init__(self):
                self.current_animation = 'strip_1'
                self.current_frame = 0

        class MockAnimatedSprite:
            def __init__(self):
                # Start with one frame in strip_1, matching _create_test_sprite
                initial_frame = SpriteFrame(surface=pygame.Surface((32, 32)), duration=1.0)
                self._animations = {'strip_1': [initial_frame]}
                self._is_playing = False
                self.frame_manager = MockFrameManager()

            def add_frame(self, animation_name, frame, index=None):
                """Mock frame addition."""
                if animation_name not in self._animations:
                    self._animations[animation_name] = []
                if index is not None:
                    self._animations[animation_name].insert(index, frame)
                else:
                    self._animations[animation_name].append(frame)

        class MockCanvas:
            def __init__(self, scene):
                self.current_animation = 'strip_1'
                self.current_frame = 0
                self.canvas_interface = MockCanvasInterface()
                self.animated_sprite = MockAnimatedSprite()
                self._scene = scene

            def show_frame(self, animation, frame):
                """Mock frame selection, also updates parent scene and frame manager."""
                self.current_animation = animation
                self.current_frame = frame
                # Keep scene-level state in sync for tests that check it
                self._scene.current_animation = animation
                self._scene.current_frame = frame
                # Keep frame_manager in sync so FrameAddCommand adjustments work
                self.animated_sprite.frame_manager.current_animation = animation
                self.animated_sprite.frame_manager.current_frame = frame

        return MockScene()

    def test_basic_frame_editing_and_switching(self, mock_scene):
        """Test basic frame editing and switching operations."""
        # Edit some pixels
        mock_scene.edit_pixel(10, 10, (255, 0, 0), (255, 255, 0))
        mock_scene.edit_pixel(15, 15, (255, 0, 0), (255, 255, 0))

        assert mock_scene.get_undo_count() == 2

        # Switch to different frame (should create frame selection operation)
        mock_scene.switch_to_frame('strip_1', 0)

        assert mock_scene.get_undo_count() == 3

        # Undo the frame selection
        assert mock_scene.undo()
        assert mock_scene.get_undo_count() == 2
        assert mock_scene.get_redo_count() == 1

    def test_frame_creation_and_editing(self, mock_scene):
        """Test frame creation and editing operations."""
        # Create a new frame
        mock_scene.create_frame('strip_1', 1)
        assert mock_scene.get_undo_count() == 1

        # Switch to the new frame (optimized: collapsed with preceding frame create)
        mock_scene.switch_to_frame('strip_1', 1)
        assert mock_scene.get_undo_count() == 1

        # Edit the new frame
        mock_scene.edit_pixel(20, 20, (0, 255, 0), (255, 0, 255))
        assert mock_scene.get_undo_count() == 2

        # Undo the edit
        assert mock_scene.undo()
        assert mock_scene.get_undo_count() == 1

        # Undo the frame creation
        assert mock_scene.undo()
        assert mock_scene.get_undo_count() == 0

    def test_animation_creation_and_frame_operations(self, mock_scene):
        """Test animation creation and frame operations."""
        # Create a new animation
        mock_scene.create_animation('strip_2')
        assert mock_scene.get_undo_count() == 1

        # Switch to the new animation
        mock_scene.switch_to_frame('strip_2', 0)
        assert mock_scene.get_undo_count() == 2

        # Create a frame in the new animation
        mock_scene.create_frame('strip_2', 1)
        assert mock_scene.get_undo_count() == 3

        # Switch to the new frame (optimized: collapsed with preceding frame create)
        mock_scene.switch_to_frame('strip_2', 1)
        assert mock_scene.get_undo_count() == 3

        # Edit the frame
        mock_scene.edit_pixel(25, 25, (0, 0, 255), (255, 255, 255))
        assert mock_scene.get_undo_count() == 4

    def test_complex_undo_sequence(self, mock_scene):
        """Test complex undo sequence."""
        # Create operations
        mock_scene.create_animation('strip_2')
        mock_scene.switch_to_frame('strip_2', 0)
        mock_scene.create_frame('strip_2', 1)
        mock_scene.switch_to_frame('strip_2', 1)
        mock_scene.edit_pixel(25, 25, (0, 0, 255), (255, 255, 255))

        initial_undo_count = mock_scene.get_undo_count()

        # Undo the edit
        assert mock_scene.undo()
        assert mock_scene.get_undo_count() == initial_undo_count - 1

        # Undo the frame creation
        assert mock_scene.undo()
        assert mock_scene.get_undo_count() == initial_undo_count - 2

        # Undo the animation creation
        assert mock_scene.undo()
        assert mock_scene.get_undo_count() == initial_undo_count - 3

    def test_redo_sequence(self, mock_scene):
        """Test redo sequence."""
        # Create operations
        mock_scene.create_animation('strip_2')
        mock_scene.switch_to_frame('strip_2', 0)
        mock_scene.create_frame('strip_2', 1)

        initial_undo_count = mock_scene.get_undo_count()

        # Undo all operations
        assert mock_scene.undo()
        assert mock_scene.undo()
        assert mock_scene.undo()

        assert mock_scene.get_undo_count() == initial_undo_count - 3
        assert mock_scene.get_redo_count() == 3

        # Redo all operations
        assert mock_scene.redo()
        assert mock_scene.redo()
        assert mock_scene.redo()

        assert mock_scene.get_undo_count() == initial_undo_count
        assert mock_scene.get_redo_count() == 0

    def test_mixed_operations_with_frame_switching(self, mock_scene):
        """Test mixed operations with frame switching."""
        # Create operations
        mock_scene.create_animation('strip_2')
        mock_scene.switch_to_frame('strip_2', 0)
        mock_scene.create_frame('strip_2', 1)
        mock_scene.switch_to_frame('strip_2', 1)
        mock_scene.edit_pixel(25, 25, (0, 0, 255), (255, 255, 255))

        # Switch back to strip_1
        mock_scene.switch_to_frame('strip_1', 0)

        # Create another frame in strip_1
        mock_scene.create_frame('strip_1', 2)
        mock_scene.switch_to_frame('strip_1', 2)
        mock_scene.edit_pixel(30, 30, (255, 0, 0), (0, 255, 255))

        # Switch back to strip_2
        mock_scene.switch_to_frame('strip_2', 1)
        mock_scene.edit_pixel(5, 5, (0, 0, 255), (255, 0, 0))

        # Should have many operations
        assert mock_scene.get_undo_count() > 5

    def test_edge_case_multiple_rapid_operations(self, mock_scene):
        """Test edge case with multiple rapid operations."""
        # Rapid frame creation and switching
        # Each create+switch pair is collapsed by the optimizer
        mock_scene.create_frame('strip_1', 3)
        mock_scene.switch_to_frame('strip_1', 3)  # collapsed with create
        mock_scene.create_frame('strip_1', 4)
        mock_scene.switch_to_frame('strip_1', 4)  # collapsed with create
        mock_scene.edit_pixel(1, 1, (255, 0, 0), (0, 0, 0))

        # 3 operations after optimization: create_frame x2 + edit_pixel
        assert mock_scene.get_undo_count() == 3

        # Undo all operations
        for i in range(3):
            assert mock_scene.undo()
            assert mock_scene.get_undo_count() == 2 - i

    def test_animation_deletion_operations(self, mock_scene):
        """Test animation deletion operations."""
        # Create another animation
        mock_scene.create_animation('strip_3')
        mock_scene.switch_to_frame('strip_3', 0)
        mock_scene.create_frame('strip_3', 1)
        mock_scene.switch_to_frame('strip_3', 1)
        mock_scene.edit_pixel(10, 10, (0, 0, 255), (255, 255, 0))

        initial_undo_count = mock_scene.get_undo_count()

        # Undo the edit
        assert mock_scene.undo()
        assert mock_scene.get_undo_count() == initial_undo_count - 1

        # Undo the frame creation
        assert mock_scene.undo()
        assert mock_scene.get_undo_count() == initial_undo_count - 2

        # Undo the animation creation
        assert mock_scene.undo()
        assert mock_scene.get_undo_count() == initial_undo_count - 3

    def test_stress_test_many_operations(self, mock_scene):
        """Test stress test with many operations."""
        # Create many operations (create+switch pairs are collapsed by optimizer)
        for i in range(10):
            mock_scene.create_frame('strip_1', i + 5)
            mock_scene.switch_to_frame('strip_1', i + 5)  # collapsed with create
            mock_scene.edit_pixel(i, i, (255, 0, 0), (i * 25, i * 25, i * 25))

        # Should have 20 operations (2 per iteration: create + edit, switch is collapsed)
        assert mock_scene.get_undo_count() == 20

        # Undo all operations
        for i in range(20):
            assert mock_scene.undo()
            assert mock_scene.get_undo_count() == 19 - i

    def test_frame_selection_undo_redo(self, mock_scene):
        """Test frame selection undo/redo specifically."""
        # Switch between frames multiple times
        mock_scene.switch_to_frame('strip_1', 0)
        mock_scene.switch_to_frame('strip_1', 0)  # Same frame, should not create operation
        mock_scene.switch_to_frame('strip_1', 1)  # Different frame, should create operation

        # Should have 2 operations (first switch and second switch)
        assert mock_scene.get_undo_count() == 2

        # Undo frame selection
        assert mock_scene.undo()
        assert mock_scene.get_undo_count() == 1

        # Redo frame selection
        assert mock_scene.redo()
        assert mock_scene.get_undo_count() == 2

    def test_operation_descriptions(self, mock_scene):
        """Test that operations have proper descriptions."""
        # Create various operations
        mock_scene.edit_pixel(10, 10, (255, 0, 0), (255, 255, 0))
        mock_scene.create_frame('strip_1', 1)
        mock_scene.create_animation('strip_2')
        mock_scene.switch_to_frame('strip_1', 1)

        # Check operation descriptions
        operations = mock_scene.undo_redo_manager.undo_stack
        assert len(operations) == 4

        # Check that descriptions are meaningful
        assert 'Pixel change' in operations[0].description
        assert 'Added frame' in operations[1].description
        assert 'Added animation' in operations[2].description
        assert 'Selected frame' in operations[3].description

    def test_undo_redo_stack_limits(self, mock_scene):
        """Test that undo/redo stacks respect size limits."""
        # Create more operations than the limit
        for i in range(60):  # More than max_history of 50
            mock_scene.edit_pixel(i, i, (255, 0, 0), (i, i, i))

        # Should be limited to max_history
        assert mock_scene.get_undo_count() == 50

        # Undo all operations
        for i in range(50):
            assert mock_scene.undo()
            assert mock_scene.get_undo_count() == 49 - i

    def test_mixed_operation_types(self, mock_scene):
        """Test mixed operation types in undo stack."""
        # Create different types of operations
        mock_scene.edit_pixel(10, 10, (255, 0, 0), (255, 255, 0))  # Canvas operation
        mock_scene.create_frame('strip_1', 1)  # Film strip operation
        mock_scene.switch_to_frame('strip_1', 1)  # Frame selection (collapsed with create)
        mock_scene.create_animation('strip_2')  # Film strip operation

        # 3 operations after optimization (create+switch collapsed)
        assert mock_scene.get_undo_count() == 3

        # Undo all operations
        for i in range(3):
            assert mock_scene.undo()
            assert mock_scene.get_undo_count() == 2 - i
