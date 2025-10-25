#!/usr/bin/env python3
"""Operation History Tracker for Undo/Redo System.

This module provides specialized operation tracking for different types of
editing operations in the Bitmappy editor.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import time

from .undo_redo_manager import OperationType, UndoRedoManager

LOG = logging.getLogger(__name__)


@dataclass
class PixelChange:
    """Represents a change to a single pixel."""
    
    x: int
    y: int
    old_color: Tuple[int, int, int]
    new_color: Tuple[int, int, int]
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class BrushStroke:
    """Represents a brush stroke operation."""
    
    pixels: List[PixelChange]
    brush_size: int
    brush_type: str
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class FrameOperation:
    """Represents a frame-level operation."""
    
    frame_index: int
    animation_name: str
    operation_data: Dict[str, Any]
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class CanvasOperationTracker:
    """Tracks canvas-specific operations for undo/redo."""
    
    def __init__(self, undo_redo_manager: UndoRedoManager):
        """Initialize the canvas operation tracker.
        
        Args:
            undo_redo_manager: The undo/redo manager to use
        """
        self.undo_redo_manager = undo_redo_manager
        self.current_stroke: Optional[BrushStroke] = None
        self.stroke_pixels: List[PixelChange] = []
        
        LOG.debug("CanvasOperationTracker initialized")
    
    def start_brush_stroke(self, brush_size: int, brush_type: str) -> None:
        """Start tracking a new brush stroke.
        
        Args:
            brush_size: Size of the brush
            brush_type: Type of brush being used
        """
        if self.current_stroke is not None:
            # Finish the previous stroke if one exists
            self.end_brush_stroke()
        
        self.current_stroke = BrushStroke(
            pixels=[],
            brush_size=brush_size,
            brush_type=brush_type
        )
        self.stroke_pixels = []
        
        LOG.debug(f"Started brush stroke: {brush_type} (size: {brush_size})")
    
    def add_pixel_change(self, x: int, y: int, old_color: Tuple[int, int, int], 
                        new_color: Tuple[int, int, int]) -> None:
        """Add a pixel change to the current stroke.
        
        Args:
            x: X coordinate of the pixel
            y: Y coordinate of the pixel
            old_color: Previous color of the pixel
            new_color: New color of the pixel
        """
        if self.current_stroke is None:
            # Create a single-pixel stroke if none exists
            self.start_brush_stroke(1, "single_pixel")
        
        pixel_change = PixelChange(
            x=x, y=y, old_color=old_color, new_color=new_color
        )
        
        self.stroke_pixels.append(pixel_change)
        
        LOG.debug(f"Added pixel change at ({x}, {y}): {old_color} -> {new_color}")
    
    def end_brush_stroke(self) -> None:
        """End the current brush stroke and add it to history."""
        if self.current_stroke is None:
            return
        
        # Update the stroke with all collected pixels
        self.current_stroke.pixels = self.stroke_pixels.copy()
        
        if not self.stroke_pixels:
            # No pixels changed, don't create an operation
            LOG.debug("Brush stroke ended with no pixel changes")
            self.current_stroke = None
            self.stroke_pixels = []
            return
        
        # Create undo/redo data
        undo_data = {
            "pixels": [(p.x, p.y, p.old_color) for p in self.stroke_pixels],
            "brush_size": self.current_stroke.brush_size,
            "brush_type": self.current_stroke.brush_type
        }
        
        redo_data = {
            "pixels": [(p.x, p.y, p.new_color) for p in self.stroke_pixels],
            "brush_size": self.current_stroke.brush_size,
            "brush_type": self.current_stroke.brush_type
        }
        
        # Add to undo/redo manager
        description = f"Brush stroke ({self.current_stroke.brush_type}, {len(self.stroke_pixels)} pixels)"
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.CANVAS_BRUSH_STROKE,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data,
            context={"stroke_timestamp": self.current_stroke.timestamp}
        )
        
        LOG.debug(f"Ended brush stroke: {description}")
        
        # Reset for next stroke
        self.current_stroke = None
        self.stroke_pixels = []
    
    def add_pixel_changes(self, pixel_changes: List[Tuple[int, int, Tuple[int, int, int], Tuple[int, int, int]]]) -> None:
        """Add a list of pixel changes as a single operation.
        
        Args:
            pixel_changes: List of (x, y, old_color, new_color) tuples
        """
        if not pixel_changes:
            return
            
        # Create undo/redo data
        undo_pixels = [(x, y, old_color) for x, y, old_color, new_color in pixel_changes]
        redo_pixels = [(x, y, new_color) for x, y, old_color, new_color in pixel_changes]
        
        # Use consistent format for both single and multiple pixel changes
        undo_data = {
            "pixels": undo_pixels
        }
        redo_data = {
            "pixels": redo_pixels
        }
        
        if len(pixel_changes) == 1:
            description = f"Pixel change at ({pixel_changes[0][0]}, {pixel_changes[0][1]})"
            operation_type = OperationType.CANVAS_BRUSH_STROKE  # Use same type for consistency
        else:
            description = f"Pixel changes ({len(pixel_changes)} pixels)"
            operation_type = OperationType.CANVAS_BRUSH_STROKE
            
        self.undo_redo_manager.add_operation(
            operation_type=operation_type,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data
        )
        
        LOG.debug(f"Tracked pixel changes: {description}")
    
    def add_single_pixel_change(self, x: int, y: int, old_color: Tuple[int, int, int], 
                               new_color: Tuple[int, int, int]) -> None:
        """Add a single pixel change operation.
        
        Args:
            x: X coordinate of the pixel
            y: Y coordinate of the pixel
            old_color: Previous color of the pixel
            new_color: New color of the pixel
        """
        # Use the new method for consistency
        self.add_pixel_changes([(x, y, old_color, new_color)])
    
    def add_flood_fill(self, x: int, y: int, old_color: Tuple[int, int, int], 
                      new_color: Tuple[int, int, int], affected_pixels: List[Tuple[int, int]]) -> None:
        """Add a flood fill operation.
        
        Args:
            x: Starting X coordinate
            y: Starting Y coordinate
            old_color: Color that was replaced
            new_color: Color that was filled
            affected_pixels: List of all pixels that were changed
        """
        undo_data = {
            "start_pos": (x, y),
            "old_color": old_color,
            "affected_pixels": affected_pixels
        }
        
        redo_data = {
            "start_pos": (x, y),
            "new_color": new_color,
            "affected_pixels": affected_pixels
        }
        
        description = f"Flood fill at ({x}, {y}) - {len(affected_pixels)} pixels"
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.CANVAS_FLOOD_FILL,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data
        )
        
        LOG.debug(f"Added flood fill operation: {description}")


class FilmStripOperationTracker:
    """Tracks film strip-specific operations for undo/redo."""
    
    def __init__(self, undo_redo_manager: UndoRedoManager):
        """Initialize the film strip operation tracker.
        
        Args:
            undo_redo_manager: The undo/redo manager to use
        """
        self.undo_redo_manager = undo_redo_manager
        
        LOG.debug("FilmStripOperationTracker initialized")
    
    def add_frame_added(self, frame_index: int, animation_name: str, 
                       frame_data: Dict[str, Any]) -> None:
        """Track when a frame is added.
        
        Args:
            frame_index: Index where the frame was added
            animation_name: Name of the animation
            frame_data: Data about the added frame
        """
        undo_data = {
            "frame_index": frame_index,
            "animation_name": animation_name,
            "action": "delete"
        }
        
        redo_data = {
            "frame_index": frame_index,
            "animation_name": animation_name,
            "action": "add",
            "frame_data": frame_data
        }
        
        description = f"Added frame {frame_index} to '{animation_name}'"
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.FILM_STRIP_FRAME_ADD,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data
        )
        
        LOG.debug(f"Tracked frame addition: {description}")
    
    def add_frame_deleted(self, frame_index: int, animation_name: str, 
                         frame_data: Dict[str, Any]) -> None:
        """Track when a frame is deleted.
        
        Args:
            frame_index: Index of the deleted frame
            animation_name: Name of the animation
            frame_data: Data about the deleted frame
        """
        undo_data = {
            "frame_index": frame_index,
            "animation_name": animation_name,
            "action": "add",
            "frame_data": frame_data
        }
        
        redo_data = {
            "frame_index": frame_index,
            "animation_name": animation_name,
            "action": "delete"
        }
        
        description = f"Deleted frame {frame_index} from '{animation_name}'"
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.FILM_STRIP_FRAME_DELETE,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data
        )
        
        LOG.debug(f"Tracked frame deletion: {description}")
    
    def add_frame_reordered(self, old_index: int, new_index: int, animation_name: str) -> None:
        """Track when frames are reordered.
        
        Args:
            old_index: Original index of the frame
            new_index: New index of the frame
            animation_name: Name of the animation
        """
        undo_data = {
            "old_index": old_index,
            "new_index": new_index,
            "animation_name": animation_name,
            "action": "reorder"
        }
        
        redo_data = {
            "old_index": new_index,
            "new_index": old_index,
            "animation_name": animation_name,
            "action": "reorder"
        }
        
        description = f"Moved frame {old_index} to {new_index} in '{animation_name}'"
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.FILM_STRIP_FRAME_REORDER,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data
        )
        
        LOG.debug(f"Tracked frame reordering: {description}")
    
    def add_animation_added(self, animation_name: str, animation_data: Dict[str, Any]) -> None:
        """Track when an animation is added.
        
        Args:
            animation_name: Name of the animation
            animation_data: Data about the animation
        """
        undo_data = {
            "animation_name": animation_name,
            "action": "delete"
        }
        
        redo_data = {
            "animation_name": animation_name,
            "action": "add",
            "animation_data": animation_data
        }
        
        description = f"Added animation '{animation_name}'"
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.FILM_STRIP_ANIMATION_ADD,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data
        )
        
        LOG.debug(f"Tracked animation addition: {description}")
    
    def add_animation_deleted(self, animation_name: str, animation_data: Dict[str, Any]) -> None:
        """Track when an animation is deleted.
        
        Args:
            animation_name: Name of the animation
            animation_data: Data about the deleted animation
        """
        undo_data = {
            "animation_name": animation_name,
            "action": "add",
            "animation_data": animation_data
        }
        
        redo_data = {
            "animation_name": animation_name,
            "action": "delete"
        }
        
        description = f"Deleted animation '{animation_name}'"
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.FILM_STRIP_ANIMATION_DELETE,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data
        )
        
        LOG.debug(f"Tracked animation deletion: {description}")


class CrossAreaOperationTracker:
    """Tracks operations that span both canvas and film strip areas."""
    
    def __init__(self, undo_redo_manager: UndoRedoManager):
        """Initialize the cross-area operation tracker.
        
        Args:
            undo_redo_manager: The undo/redo manager to use
        """
        self.undo_redo_manager = undo_redo_manager
        
        LOG.debug("CrossAreaOperationTracker initialized")
    
    def add_frame_copy(self, source_frame: int, source_animation: str, 
                      frame_data: Dict[str, Any]) -> None:
        """Track when a frame is copied.
        
        Args:
            source_frame: Index of the source frame
            source_animation: Name of the source animation
            frame_data: Data about the copied frame
        """
        undo_data = {
            "action": "clear_clipboard"
        }
        
        redo_data = {
            "action": "copy",
            "source_frame": source_frame,
            "source_animation": source_animation,
            "frame_data": frame_data
        }
        
        description = f"Copied frame {source_frame} from '{source_animation}'"
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.FRAME_COPY,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data
        )
        
        LOG.debug(f"Tracked frame copy: {description}")
    
    def add_frame_paste(self, target_frame: int, target_animation: str, 
                       frame_data: Dict[str, Any]) -> None:
        """Track when a frame is pasted.
        
        Args:
            target_frame: Index of the target frame
            target_animation: Name of the target animation
            frame_data: Data about the pasted frame
        """
        undo_data = {
            "target_frame": target_frame,
            "target_animation": target_animation,
            "action": "delete"
        }
        
        redo_data = {
            "target_frame": target_frame,
            "target_animation": target_animation,
            "action": "paste",
            "frame_data": frame_data
        }
        
        description = f"Pasted frame to {target_frame} in '{target_animation}'"
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.FRAME_PASTE,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data
        )
        
        LOG.debug(f"Tracked frame paste: {description}")
