#!/usr/bin/env python3
"""Undo/Redo Manager for Bitmappy Editor.

This module provides a comprehensive undo/redo system that works across both
canvas (pixel-level) and film strip (frame-level) operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import time

LOG = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of operations that can be undone/redone."""
    
    # Canvas operations
    CANVAS_PIXEL_CHANGE = "canvas_pixel_change"
    CANVAS_BRUSH_STROKE = "canvas_brush_stroke"
    CANVAS_FLOOD_FILL = "canvas_flood_fill"
    CANVAS_COLOR_CHANGE = "canvas_color_change"
    
    # Film strip operations
    FILM_STRIP_FRAME_ADD = "film_strip_frame_add"
    FILM_STRIP_FRAME_DELETE = "film_strip_frame_delete"
    FILM_STRIP_FRAME_REORDER = "film_strip_frame_reorder"
    FILM_STRIP_ANIMATION_ADD = "film_strip_animation_add"
    FILM_STRIP_ANIMATION_DELETE = "film_strip_animation_delete"
    
    # Cross-area operations
    FRAME_COPY = "frame_copy"
    FRAME_PASTE = "frame_paste"
    ANIMATION_COPY = "animation_copy"
    ANIMATION_PASTE = "animation_paste"


@dataclass
class Operation:
    """Represents a single operation in the undo/redo history."""
    
    operation_type: OperationType
    timestamp: float
    description: str
    undo_data: Dict[str, Any]
    redo_data: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate operation data after initialization."""
        if not self.undo_data:
            raise ValueError("Operation must have undo_data")
        if not self.redo_data:
            raise ValueError("Operation must have redo_data")


class UndoRedoManager:
    """Manages undo/redo operations for the Bitmappy editor."""
    
    def __init__(self, max_history: int = 50):
        """Initialize the undo/redo manager.
        
        Args:
            max_history: Maximum number of operations to keep in history
        """
        self.max_history = max_history
        self.undo_stack: List[Operation] = []
        self.redo_stack: List[Operation] = []
        self.current_operation: Optional[Operation] = None
        self.is_undoing = False
        self.is_redoing = False
        self.pixel_change_callback: Optional[callable] = None
        self.at_head_of_history = True  # Track if we're at the head of undo history
        
        # Frame-specific undo/redo stacks for canvas operations
        self.frame_undo_stacks: Dict[tuple[str, int], List[Operation]] = {}  # {(animation, frame): [operations]}
        self.frame_redo_stacks: Dict[tuple[str, int], List[Operation]] = {}  # {(animation, frame): [operations]}
        self.current_frame: Optional[tuple[str, int]] = None  # (animation, frame) currently being edited
        
        LOG.debug(f"UndoRedoManager initialized with max_history={max_history}")
    
    def can_undo(self) -> bool:
        """Check if undo is available.
        
        Returns:
            True if undo is available, False otherwise
        """
        return len(self.undo_stack) > 0 and not self.is_undoing
    
    def set_current_frame(self, animation: str, frame: int) -> None:
        """Set the current frame being edited.
        
        Args:
            animation: Name of the animation
            frame: Frame index
        """
        self.current_frame = (animation, frame)
        LOG.debug(f"Current frame set to: {animation}[{frame}]")
    
    def can_undo_frame(self, animation: str, frame: int) -> bool:
        """Check if undo is available for a specific frame.
        
        Args:
            animation: Name of the animation
            frame: Frame index
            
        Returns:
            True if undo is available for this frame, False otherwise
        """
        frame_key = (animation, frame)
        return (frame_key in self.frame_undo_stacks and 
                len(self.frame_undo_stacks[frame_key]) > 0 and 
                not self.is_undoing)
    
    def can_redo_frame(self, animation: str, frame: int) -> bool:
        """Check if redo is available for a specific frame.
        
        Args:
            animation: Name of the animation
            frame: Frame index
            
        Returns:
            True if redo is available for this frame, False otherwise
        """
        frame_key = (animation, frame)
        return (frame_key in self.frame_redo_stacks and 
                len(self.frame_redo_stacks[frame_key]) > 0 and 
                not self.is_redoing)
    
    def can_redo(self) -> bool:
        """Check if redo is available.
        
        Returns:
            True if redo is available, False otherwise
        """
        return len(self.redo_stack) > 0 and not self.is_redoing
    
    def get_undo_description(self) -> Optional[str]:
        """Get description of the next undo operation.
        
        Returns:
            Description of the next undo operation, or None if not available
        """
        if not self.can_undo():
            return None
        return self.undo_stack[-1].description
    
    def get_redo_description(self) -> Optional[str]:
        """Get description of the next redo operation.
        
        Returns:
            Description of the next redo operation, or None if not available
        """
        if not self.can_redo():
            return None
        return self.redo_stack[-1].description
    
    def add_operation(self, operation_type: OperationType, description: str, 
                     undo_data: Dict[str, Any], redo_data: Dict[str, Any],
                     context: Optional[Dict[str, Any]] = None) -> None:
        """Add a new operation to the history.
        
        Args:
            operation_type: Type of operation
            description: Human-readable description
            undo_data: Data needed to undo the operation
            redo_data: Data needed to redo the operation
            context: Additional context information
        """
        if self.is_undoing or self.is_redoing:
            LOG.debug("Skipping operation addition during undo/redo")
            return
        
        # Clear redo stack when new operation is added (only if we're at the head of undo history)
        # This prevents clearing redo stack when we're in the middle of an undo/redo sequence
        if self.redo_stack and self.at_head_of_history:
            LOG.debug(f"Clearing {len(self.redo_stack)} redo operations")
            self.redo_stack.clear()
        
        operation = Operation(
            operation_type=operation_type,
            timestamp=time.time(),
            description=description,
            undo_data=undo_data,
            redo_data=redo_data,
            context=context or {}
        )
        
        self.undo_stack.append(operation)
        
        # Maintain max history limit
        if len(self.undo_stack) > self.max_history:
            removed = self.undo_stack.pop(0)
            LOG.debug(f"Removed oldest operation: {removed.description}")
        
        # We're now at the head of history
        self.at_head_of_history = True
        
        LOG.debug(f"Added operation: {description} (undo stack size: {len(self.undo_stack)})")
    
    def add_frame_operation(self, animation: str, frame: int, operation_type: OperationType, 
                           description: str, undo_data: Dict[str, Any], 
                           redo_data: Dict[str, Any]) -> None:
        """Add a frame-specific operation to the undo/redo history.
        
        Args:
            animation: Name of the animation
            frame: Frame index
            operation_type: Type of operation
            description: Human-readable description
            undo_data: Data needed to undo the operation
            redo_data: Data needed to redo the operation
        """
        frame_key = (animation, frame)
        
        # Initialize stacks for this frame if they don't exist
        if frame_key not in self.frame_undo_stacks:
            self.frame_undo_stacks[frame_key] = []
        if frame_key not in self.frame_redo_stacks:
            self.frame_redo_stacks[frame_key] = []
        
        # Clear redo stack for this frame if we're at the head of history
        if not self.is_undoing and not self.is_redoing:
            self.frame_redo_stacks[frame_key].clear()
        
        operation = Operation(
            operation_type=operation_type,
            timestamp=time.time(),
            description=description,
            undo_data=undo_data,
            redo_data=redo_data,
            context={"frame": frame_key}
        )
        
        self.frame_undo_stacks[frame_key].append(operation)
        
        # Limit history size for this frame
        if len(self.frame_undo_stacks[frame_key]) > self.max_history:
            self.frame_undo_stacks[frame_key].pop(0)
        
        LOG.debug(f"Added frame operation for {animation}[{frame}]: {description}")
    
    def undo_frame(self, animation: str, frame: int) -> bool:
        """Undo the last operation for a specific frame.
        
        Args:
            animation: Name of the animation
            frame: Frame index
            
        Returns:
            True if undo was successful, False otherwise
        """
        frame_key = (animation, frame)
        
        if frame_key not in self.frame_undo_stacks or not self.frame_undo_stacks[frame_key]:
            LOG.debug(f"No undo operations available for {animation}[{frame}]")
            return False
        
        if self.is_undoing or self.is_redoing:
            LOG.debug("Already in undo/redo operation")
            return False
        
        self.is_undoing = True
        
        try:
            operation = self.frame_undo_stacks[frame_key].pop()
            self.frame_redo_stacks[frame_key].append(operation)
            
            # Execute the undo operation
            success = self._execute_undo(operation)
            
            if success:
                LOG.debug(f"Undid frame operation for {animation}[{frame}]: {operation.description}")
            else:
                LOG.warning(f"Failed to undo frame operation for {animation}[{frame}]")
                # Put the operation back if it failed
                self.frame_undo_stacks[frame_key].append(operation)
                self.frame_redo_stacks[frame_key].pop()
            
            return success
            
        except Exception as e:
            LOG.error(f"Error undoing frame operation for {animation}[{frame}]: {e}")
            return False
        finally:
            self.is_undoing = False
    
    def redo_frame(self, animation: str, frame: int) -> bool:
        """Redo the last undone operation for a specific frame.
        
        Args:
            animation: Name of the animation
            frame: Frame index
            
        Returns:
            True if redo was successful, False otherwise
        """
        frame_key = (animation, frame)
        
        if frame_key not in self.frame_redo_stacks or not self.frame_redo_stacks[frame_key]:
            LOG.debug(f"No redo operations available for {animation}[{frame}]")
            return False
        
        if self.is_undoing or self.is_redoing:
            LOG.debug("Already in undo/redo operation")
            return False
        
        self.is_redoing = True
        
        try:
            operation = self.frame_redo_stacks[frame_key].pop()
            self.frame_undo_stacks[frame_key].append(operation)
            
            # Execute the redo operation
            success = self._execute_redo(operation)
            
            if success:
                LOG.debug(f"Redid frame operation for {animation}[{frame}]: {operation.description}")
            else:
                LOG.warning(f"Failed to redo frame operation for {animation}[{frame}]")
                # Put the operation back if it failed
                self.frame_redo_stacks[frame_key].append(operation)
                self.frame_undo_stacks[frame_key].pop()
            
            return success
            
        except Exception as e:
            LOG.error(f"Error redoing frame operation for {animation}[{frame}]: {e}")
            return False
        finally:
            self.is_redoing = False
    
    def undo(self) -> bool:
        """Undo the last operation.
        
        Returns:
            True if undo was successful, False otherwise
        """
        if not self.can_undo():
            LOG.debug("Cannot undo: no operations available")
            return False
        
        self.is_undoing = True
        try:
            operation = self.undo_stack.pop()
            self.redo_stack.append(operation)
            
            LOG.debug(f"Undoing operation: {operation.description}")
            
            # Execute undo logic based on operation type
            success = self._execute_undo(operation)
            
            if success:
                LOG.debug(f"Successfully undone: {operation.description}")
                # We're no longer at the head of history after undoing
                self.at_head_of_history = False
            else:
                LOG.warning(f"Failed to undo: {operation.description}")
                # Put operation back on undo stack if it failed
                self.undo_stack.append(operation)
                self.redo_stack.pop()
            
            return success
            
        finally:
            self.is_undoing = False
    
    def redo(self) -> bool:
        """Redo the last undone operation.
        
        Returns:
            True if redo was successful, False otherwise
        """
        if not self.can_redo():
            LOG.debug("Cannot redo: no operations available")
            return False
        
        self.is_redoing = True
        try:
            operation = self.redo_stack.pop()
            self.undo_stack.append(operation)
            
            LOG.debug(f"Redoing operation: {operation.description}")
            
            # Execute redo logic based on operation type
            success = self._execute_redo(operation)
            
            if success:
                LOG.debug(f"Successfully redone: {operation.description}")
                # Check if we're back at the head of history (no more redo operations)
                if not self.redo_stack:
                    self.at_head_of_history = True
            else:
                LOG.warning(f"Failed to redo: {operation.description}")
                # Put operation back on redo stack if it failed
                self.redo_stack.append(operation)
                self.undo_stack.pop()
            
            return success
            
        finally:
            self.is_redoing = False
    
    def _execute_undo(self, operation: Operation) -> bool:
        """Execute the undo logic for an operation.
        
        Args:
            operation: The operation to undo
            
        Returns:
            True if undo was successful, False otherwise
        """
        try:
            if operation.operation_type in [
                OperationType.CANVAS_PIXEL_CHANGE,
                OperationType.CANVAS_BRUSH_STROKE,
                OperationType.CANVAS_FLOOD_FILL,
                OperationType.CANVAS_COLOR_CHANGE
            ]:
                return self._undo_canvas_operation(operation)
            elif operation.operation_type in [
                OperationType.FILM_STRIP_FRAME_ADD,
                OperationType.FILM_STRIP_FRAME_DELETE,
                OperationType.FILM_STRIP_FRAME_REORDER,
                OperationType.FILM_STRIP_ANIMATION_ADD,
                OperationType.FILM_STRIP_ANIMATION_DELETE
            ]:
                return self._undo_film_strip_operation(operation)
            elif operation.operation_type in [
                OperationType.FRAME_COPY,
                OperationType.FRAME_PASTE,
                OperationType.ANIMATION_COPY,
                OperationType.ANIMATION_PASTE
            ]:
                return self._undo_cross_area_operation(operation)
            else:
                LOG.warning(f"Unknown operation type: {operation.operation_type}")
                return False
                
        except Exception as e:
            LOG.error(f"Error executing undo for {operation.description}: {e}")
            return False
    
    def _execute_redo(self, operation: Operation) -> bool:
        """Execute the redo logic for an operation.
        
        Args:
            operation: The operation to redo
            
        Returns:
            True if redo was successful, False otherwise
        """
        try:
            if operation.operation_type in [
                OperationType.CANVAS_PIXEL_CHANGE,
                OperationType.CANVAS_BRUSH_STROKE,
                OperationType.CANVAS_FLOOD_FILL,
                OperationType.CANVAS_COLOR_CHANGE
            ]:
                return self._redo_canvas_operation(operation)
            elif operation.operation_type in [
                OperationType.FILM_STRIP_FRAME_ADD,
                OperationType.FILM_STRIP_FRAME_DELETE,
                OperationType.FILM_STRIP_FRAME_REORDER,
                OperationType.FILM_STRIP_ANIMATION_ADD,
                OperationType.FILM_STRIP_ANIMATION_DELETE
            ]:
                return self._redo_film_strip_operation(operation)
            elif operation.operation_type in [
                OperationType.FRAME_COPY,
                OperationType.FRAME_PASTE,
                OperationType.ANIMATION_COPY,
                OperationType.ANIMATION_PASTE
            ]:
                return self._redo_cross_area_operation(operation)
            else:
                LOG.warning(f"Unknown operation type: {operation.operation_type}")
                return False
                
        except Exception as e:
            LOG.error(f"Error executing redo for {operation.description}: {e}")
            return False
    
    def _undo_canvas_operation(self, operation: Operation) -> bool:
        """Undo a canvas operation.
        
        Args:
            operation: The canvas operation to undo
            
        Returns:
            True if undo was successful, False otherwise
        """
        try:
            if operation.operation_type == OperationType.CANVAS_PIXEL_CHANGE:
                # Undo single pixel change
                pixel_data = operation.undo_data.get("pixel")
                if pixel_data:
                    x, y, old_color = pixel_data
                    # Apply the old color to the pixel
                    # This will be handled by the canvas interface
                    return self._apply_pixel_change(x, y, old_color)
                    
            elif operation.operation_type == OperationType.CANVAS_BRUSH_STROKE:
                # Undo brush stroke
                pixels = operation.undo_data.get("pixels", [])
                success = True
                for pixel_data in pixels:
                    x, y, old_color = pixel_data
                    if not self._apply_pixel_change(x, y, old_color):
                        success = False
                return success
                
            elif operation.operation_type == OperationType.CANVAS_FLOOD_FILL:
                # Undo flood fill
                affected_pixels = operation.undo_data.get("affected_pixels", [])
                old_color = operation.undo_data.get("old_color")
                success = True
                for x, y in affected_pixels:
                    if not self._apply_pixel_change(x, y, old_color):
                        success = False
                return success
                
            else:
                LOG.warning(f"Unknown canvas operation type: {operation.operation_type}")
                return False
                
        except Exception as e:
            LOG.error(f"Error undoing canvas operation: {e}")
            return False
    
    def _undo_film_strip_operation(self, operation: Operation) -> bool:
        """Undo a film strip operation.
        
        Args:
            operation: The film strip operation to undo
            
        Returns:
            True if undo was successful, False otherwise
        """
        try:
            if operation.operation_type == OperationType.FILM_STRIP_FRAME_ADD:
                # Undo frame addition by deleting the frame
                frame_index = operation.undo_data.get("frame_index")
                animation_name = operation.undo_data.get("animation_name")
                return self._delete_frame(frame_index, animation_name)
                
            elif operation.operation_type == OperationType.FILM_STRIP_FRAME_DELETE:
                # Undo frame deletion by adding the frame back
                frame_index = operation.undo_data.get("frame_index")
                animation_name = operation.undo_data.get("animation_name")
                frame_data = operation.undo_data.get("frame_data")
                return self._add_frame(frame_index, animation_name, frame_data)
                
            elif operation.operation_type == OperationType.FILM_STRIP_FRAME_REORDER:
                # Undo frame reordering by reversing the operation
                old_index = operation.undo_data.get("old_index")
                new_index = operation.undo_data.get("new_index")
                animation_name = operation.undo_data.get("animation_name")
                return self._reorder_frame(new_index, old_index, animation_name)
                
            elif operation.operation_type == OperationType.FILM_STRIP_ANIMATION_ADD:
                # Undo animation addition by deleting the animation
                animation_name = operation.undo_data.get("animation_name")
                return self._delete_animation(animation_name)
                
            elif operation.operation_type == OperationType.FILM_STRIP_ANIMATION_DELETE:
                # Undo animation deletion by adding the animation back
                animation_name = operation.undo_data.get("animation_name")
                animation_data = operation.undo_data.get("animation_data")
                return self._add_animation(animation_name, animation_data)
                
            else:
                LOG.warning(f"Unknown film strip operation type: {operation.operation_type}")
                return False
                
        except Exception as e:
            LOG.error(f"Error undoing film strip operation: {e}")
            return False
    
    def _undo_cross_area_operation(self, operation: Operation) -> bool:
        """Undo a cross-area operation.
        
        Args:
            operation: The cross-area operation to undo
            
        Returns:
            True if undo was successful, False otherwise
        """
        # This will be implemented when we integrate with both systems
        LOG.debug(f"Undoing cross-area operation: {operation.description}")
        return True
    
    def _redo_canvas_operation(self, operation: Operation) -> bool:
        """Redo a canvas operation.
        
        Args:
            operation: The canvas operation to redo
            
        Returns:
            True if redo was successful, False otherwise
        """
        try:
            if operation.operation_type == OperationType.CANVAS_PIXEL_CHANGE:
                # Redo single pixel change
                pixel_data = operation.redo_data.get("pixel")
                if pixel_data:
                    x, y, new_color = pixel_data
                    return self._apply_pixel_change(x, y, new_color)
                    
            elif operation.operation_type == OperationType.CANVAS_BRUSH_STROKE:
                # Redo brush stroke
                pixels = operation.redo_data.get("pixels", [])
                success = True
                for pixel_data in pixels:
                    x, y, new_color = pixel_data
                    if not self._apply_pixel_change(x, y, new_color):
                        success = False
                return success
                
            elif operation.operation_type == OperationType.CANVAS_FLOOD_FILL:
                # Redo flood fill
                affected_pixels = operation.redo_data.get("affected_pixels", [])
                new_color = operation.redo_data.get("new_color")
                success = True
                for x, y in affected_pixels:
                    if not self._apply_pixel_change(x, y, new_color):
                        success = False
                return success
                
            else:
                LOG.warning(f"Unknown canvas operation type: {operation.operation_type}")
                return False
                
        except Exception as e:
            LOG.error(f"Error redoing canvas operation: {e}")
            return False
    
    def _redo_film_strip_operation(self, operation: Operation) -> bool:
        """Redo a film strip operation.
        
        Args:
            operation: The film strip operation to redo
            
        Returns:
            True if redo was successful, False otherwise
        """
        try:
            if operation.operation_type == OperationType.FILM_STRIP_FRAME_ADD:
                # Redo frame addition by adding the frame
                frame_index = operation.redo_data.get("frame_index")
                animation_name = operation.redo_data.get("animation_name")
                frame_data = operation.redo_data.get("frame_data")
                return self._add_frame(frame_index, animation_name, frame_data)
                
            elif operation.operation_type == OperationType.FILM_STRIP_FRAME_DELETE:
                # Redo frame deletion by deleting the frame
                frame_index = operation.redo_data.get("frame_index")
                animation_name = operation.redo_data.get("animation_name")
                return self._delete_frame(frame_index, animation_name)
                
            elif operation.operation_type == OperationType.FILM_STRIP_FRAME_REORDER:
                # Redo frame reordering
                old_index = operation.redo_data.get("old_index")
                new_index = operation.redo_data.get("new_index")
                animation_name = operation.redo_data.get("animation_name")
                return self._reorder_frame(old_index, new_index, animation_name)
                
            elif operation.operation_type == OperationType.FILM_STRIP_ANIMATION_ADD:
                # Redo animation addition by adding the animation
                animation_name = operation.redo_data.get("animation_name")
                animation_data = operation.redo_data.get("animation_data")
                return self._add_animation(animation_name, animation_data)
                
            elif operation.operation_type == OperationType.FILM_STRIP_ANIMATION_DELETE:
                # Redo animation deletion by deleting the animation
                animation_name = operation.redo_data.get("animation_name")
                return self._delete_animation(animation_name)
                
            else:
                LOG.warning(f"Unknown film strip operation type: {operation.operation_type}")
                return False
                
        except Exception as e:
            LOG.error(f"Error redoing film strip operation: {e}")
            return False
    
    def _redo_cross_area_operation(self, operation: Operation) -> bool:
        """Redo a cross-area operation.
        
        Args:
            operation: The cross-area operation to redo
            
        Returns:
            True if redo was successful, False otherwise
        """
        # This will be implemented when we integrate with both systems
        LOG.debug(f"Redoing cross-area operation: {operation.description}")
        return True
    
    def clear_history(self) -> None:
        """Clear all undo/redo history."""
        LOG.debug("Clearing undo/redo history")
        self.undo_stack.clear()
        self.redo_stack.clear()
    
    def get_history_info(self) -> Dict[str, Any]:
        """Get information about the current history state.
        
        Returns:
            Dictionary with history information
        """
        return {
            "undo_count": len(self.undo_stack),
            "redo_count": len(self.redo_stack),
            "can_undo": self.can_undo(),
            "can_redo": self.can_redo(),
            "next_undo": self.get_undo_description(),
            "next_redo": self.get_redo_description(),
            "max_history": self.max_history
        }
    
    def set_pixel_change_callback(self, callback: callable) -> None:
        """Set the callback function for applying pixel changes.
        
        Args:
            callback: Function that takes (x, y, color) and applies the pixel change
        """
        self.pixel_change_callback = callback
        LOG.debug("Pixel change callback set")
    
    def set_film_strip_callbacks(self, add_frame_callback: callable = None, 
                                delete_frame_callback: callable = None,
                                reorder_frame_callback: callable = None,
                                add_animation_callback: callable = None,
                                delete_animation_callback: callable = None) -> None:
        """Set the callback functions for film strip operations.
        
        Args:
            add_frame_callback: Function that takes (frame_index, animation_name, frame_data) and adds a frame
            delete_frame_callback: Function that takes (frame_index, animation_name) and deletes a frame
            reorder_frame_callback: Function that takes (old_index, new_index, animation_name) and reorders frames
            add_animation_callback: Function that takes (animation_name, animation_data) and adds an animation
            delete_animation_callback: Function that takes (animation_name) and deletes an animation
        """
        self.add_frame_callback = add_frame_callback
        self.delete_frame_callback = delete_frame_callback
        self.reorder_frame_callback = reorder_frame_callback
        self.add_animation_callback = add_animation_callback
        self.delete_animation_callback = delete_animation_callback
        LOG.debug("Film strip operation callbacks set")
    
    def _apply_pixel_change(self, x: int, y: int, color: tuple[int, int, int]) -> bool:
        """Apply a pixel change to the canvas.
        
        Args:
            x: X coordinate of the pixel
            y: Y coordinate of the pixel
            color: Color to set the pixel to
            
        Returns:
            True if the change was applied successfully, False otherwise
        """
        if self.pixel_change_callback:
            try:
                self.pixel_change_callback(x, y, color)
                LOG.debug(f"Applied pixel change at ({x}, {y}) to color {color}")
                return True
            except Exception as e:
                LOG.error(f"Error applying pixel change: {e}")
                return False
        else:
            LOG.warning("No pixel change callback set")
            return False
    
    def _add_frame(self, frame_index: int, animation_name: str, frame_data: dict) -> bool:
        """Add a frame to an animation.
        
        Args:
            frame_index: Index where to add the frame
            animation_name: Name of the animation
            frame_data: Data about the frame to add
            
        Returns:
            True if the frame was added successfully, False otherwise
        """
        if self.add_frame_callback:
            return self.add_frame_callback(frame_index, animation_name, frame_data)
        else:
            LOG.warning("Add frame callback not set")
            return False
    
    def _delete_frame(self, frame_index: int, animation_name: str) -> bool:
        """Delete a frame from an animation.
        
        Args:
            frame_index: Index of the frame to delete
            animation_name: Name of the animation
            
        Returns:
            True if the frame was deleted successfully, False otherwise
        """
        if self.delete_frame_callback:
            return self.delete_frame_callback(frame_index, animation_name)
        else:
            LOG.warning("Delete frame callback not set")
            return False
    
    def _reorder_frame(self, old_index: int, new_index: int, animation_name: str) -> bool:
        """Reorder frames in an animation.
        
        Args:
            old_index: Original index of the frame
            new_index: New index of the frame
            animation_name: Name of the animation
            
        Returns:
            True if the frame was reordered successfully, False otherwise
        """
        if self.reorder_frame_callback:
            return self.reorder_frame_callback(old_index, new_index, animation_name)
        else:
            LOG.warning("Reorder frame callback not set")
            return False
    
    def _delete_animation(self, animation_name: str) -> bool:
        """Delete an animation.
        
        Args:
            animation_name: Name of the animation to delete
            
        Returns:
            True if the animation was deleted successfully, False otherwise
        """
        if self.delete_animation_callback:
            return self.delete_animation_callback(animation_name)
        else:
            LOG.warning("Delete animation callback not set")
            return False
    
    def _add_animation(self, animation_name: str, animation_data: dict) -> bool:
        """Add an animation.
        
        Args:
            animation_name: Name of the animation to add
            animation_data: Data about the animation to add
            
        Returns:
            True if the animation was added successfully, False otherwise
        """
        if self.add_animation_callback:
            return self.add_animation_callback(animation_name, animation_data)
        else:
            LOG.warning("Add animation callback not set")
            return False
