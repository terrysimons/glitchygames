#!/usr/bin/env python3
"""Operation history tracking for undo/redo system."""

import logging
from typing import Any, Dict, List, Tuple

from .undo_redo_manager import OperationType

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class PixelChange:
    """Represents a single pixel change."""
    
    def __init__(self, x: int, y: int, old_color: Tuple[int, int, int], new_color: Tuple[int, int, int]):
        self.x = x
        self.y = y
        self.old_color = old_color
        self.new_color = new_color


class CanvasOperationTracker:
    """Tracks canvas operations for undo/redo."""
    
    def __init__(self, undo_redo_manager):
        self.undo_redo_manager = undo_redo_manager
        LOG.debug("CanvasOperationTracker initialized")
    
    def add_pixel_changes(self, pixels: List[Tuple[int, int, Tuple[int, int, int], Tuple[int, int, int]]]) -> None:
        """Add pixel changes to the undo/redo history.
        
        Args:
            pixels: List of (x, y, old_color, new_color) tuples
        """
        if not pixels:
            return
            
        # Convert to PixelChange objects for consistency
        pixel_changes = []
        for x, y, old_color, new_color in pixels:
            pixel_changes.append(PixelChange(x, y, old_color, new_color))
        
        # Create undo/redo data
        undo_pixels = [(pc.x, pc.y, pc.new_color, pc.old_color) for pc in pixel_changes]
        redo_pixels = [(pc.x, pc.y, pc.old_color, pc.new_color) for pc in pixel_changes]
        
        undo_data = {"pixels": undo_pixels}
        redo_data = {"pixels": redo_pixels}
        
        if len(pixel_changes) == 1:
            description = f"Pixel change at ({pixel_changes[0].x}, {pixel_changes[0].y})"
        else:
            description = f"Brush stroke ({len(pixel_changes)} pixels)"
        
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.CANVAS_BRUSH_STROKE,
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
            "old_color": new_color,
            "affected_pixels": affected_pixels
        }
        
        description = f"Flood fill at ({x}, {y}) - {len(affected_pixels)} pixels"
        
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.CANVAS_FLOOD_FILL,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data
        )
        
        LOG.debug(f"Tracked flood fill: {description}")
    
    def add_frame_pixel_changes(self, animation: str, frame: int, pixels: List) -> None:
        """Add pixel changes for a specific frame.
        
        Args:
            animation: Name of the animation
            frame: Frame index
            pixels: List of pixel changes (can be PixelChange objects or tuples)
        """
        if not pixels:
            return
            
        # Convert to consistent format
        pixel_changes = []
        for pixel in pixels:
            if isinstance(pixel, PixelChange):
                pixel_changes.append((pixel.x, pixel.y, pixel.old_color, pixel.new_color))
            else:
                # Assume it's a tuple (x, y, old_color, new_color)
                pixel_changes.append(pixel)
        
        # Create undo/redo data
        undo_pixels = [(x, y, new_color, old_color) for x, y, old_color, new_color in pixel_changes]
        redo_pixels = [(x, y, old_color, new_color) for x, y, old_color, new_color in pixel_changes]
        
        undo_data = {"pixels": undo_pixels}
        redo_data = {"pixels": redo_pixels}
        
        if len(pixel_changes) == 1:
            description = f"Frame {animation}[{frame}] pixel change at ({pixel_changes[0][0]}, {pixel_changes[0][1]})"
        else:
            description = f"Frame {animation}[{frame}] pixel changes ({len(pixel_changes)} pixels)"
        
        # Add to frame-specific undo stack
        self.undo_redo_manager.add_frame_operation(
            animation=animation,
            frame=frame,
            operation_type=OperationType.CANVAS_BRUSH_STROKE,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data
        )
        
        LOG.debug(f"Tracked frame pixel changes: {description}")


class FilmStripOperationTracker:
    """Tracks film strip operations for undo/redo."""
    
    def __init__(self, undo_redo_manager):
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
        """Track when a frame is reordered.
        
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
        
        description = f"Reordered frame {old_index} to {new_index} in '{animation_name}'"
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.FILM_STRIP_FRAME_REORDER,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data
        )
        
        LOG.debug(f"Tracked frame reorder: {description}")
    
    def add_animation_added(self, animation_name: str, animation_data: Dict[str, Any]) -> None:
        """Track when an animation is added.
        
        Args:
            animation_name: Name of the animation that was added
            animation_data: Data about the added animation
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
            animation_name: Name of the animation that was deleted
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
    
    def add_frame_selection(self, animation: str, frame: int) -> None:
        """Track when a frame is selected.
        
        Args:
            animation: Name of the animation being selected
            frame: Frame index being selected
        """
        # Get the previous frame selection from the undo/redo manager
        previous_animation = None
        previous_frame = None
        if hasattr(self.undo_redo_manager, 'current_frame') and self.undo_redo_manager.current_frame:
            previous_animation, previous_frame = self.undo_redo_manager.current_frame
        
        # Only track if we're actually changing selection
        if (previous_animation == animation and previous_frame == frame):
            LOG.debug(f"Frame selection unchanged: {animation}[{frame}]")
            return
            
        # Use current frame as previous if not provided, but don't use the same values
        if previous_animation is None or previous_frame is None:
            # If we don't have a previous frame, use the baseline frame 0
            previous_animation, previous_frame = "strip_1", 0
        
        undo_data = {
            "animation": previous_animation,
            "frame": previous_frame
        }
        
        redo_data = {
            "animation": animation,
            "frame": frame
        }
        
        description = f"Selected frame {animation}[{frame}]"
        
        # Add to global undo stack as a film strip operation
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.FRAME_SELECTION,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data
        )
        
        # Update current frame in undo/redo manager
        self.undo_redo_manager.current_frame = (animation, frame)
        
        LOG.debug(f"Tracked frame selection: {description}")


class CrossAreaOperationTracker:
    """Tracks cross-area operations (copy/paste between frames/animations)."""
    
    def __init__(self, undo_redo_manager):
        self.undo_redo_manager = undo_redo_manager
        LOG.debug("CrossAreaOperationTracker initialized")
    
    def add_frame_copied(self, source_frame: int, source_animation: str, 
                        frame_data: Dict[str, Any]) -> None:
        """Track when a frame is copied.
        
        Args:
            source_frame: Index of the source frame
            source_animation: Name of the source animation
            frame_data: Data about the copied frame
        """
        undo_data = {
            "source_frame": source_frame,
            "source_animation": source_animation,
            "action": "copy"
        }
        
        redo_data = {
            "source_frame": source_frame,
            "source_animation": source_animation,
            "action": "copy",
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
    
    def add_frame_pasted(self, target_frame: int, target_animation: str, 
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
            "action": "paste"
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