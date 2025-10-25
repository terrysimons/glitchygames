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
        
        LOG.debug(f"UndoRedoManager initialized with max_history={max_history}")
    
    def can_undo(self) -> bool:
        """Check if undo is available.
        
        Returns:
            True if undo is available, False otherwise
        """
        return len(self.undo_stack) > 0 and not self.is_undoing
    
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
        
        # Clear redo stack when new operation is added
        if self.redo_stack:
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
        
        LOG.debug(f"Added operation: {description} (undo stack size: {len(self.undo_stack)})")
    
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
        # This will be implemented when we integrate with the canvas system
        LOG.debug(f"Undoing canvas operation: {operation.description}")
        return True
    
    def _undo_film_strip_operation(self, operation: Operation) -> bool:
        """Undo a film strip operation.
        
        Args:
            operation: The film strip operation to undo
            
        Returns:
            True if undo was successful, False otherwise
        """
        # This will be implemented when we integrate with the film strip system
        LOG.debug(f"Undoing film strip operation: {operation.description}")
        return True
    
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
        # This will be implemented when we integrate with the canvas system
        LOG.debug(f"Redoing canvas operation: {operation.description}")
        return True
    
    def _redo_film_strip_operation(self, operation: Operation) -> bool:
        """Redo a film strip operation.
        
        Args:
            operation: The film strip operation to redo
            
        Returns:
            True if redo was successful, False otherwise
        """
        # This will be implemented when we integrate with the film strip system
        LOG.debug(f"Redoing film strip operation: {operation.description}")
        return True
    
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
