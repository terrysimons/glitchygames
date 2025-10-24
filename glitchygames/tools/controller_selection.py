"""
Controller Selection State Management

This module provides individual controller state management for the multi-controller
system, handling independent navigation, frame preservation, and selection state
for each controller.

Features:
- Independent frame/animation selection per controller
- Frame preservation when switching between controllers
- Controller-specific scrolling and navigation
- Selection state management
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
import time


@dataclass
class ControllerSelectionState:
    """State information for a controller's selection."""
    controller_id: int
    instance_id: int
    selected_animation: str = ""
    selected_frame: int = 0
    selected_slider: str = "R"  # R, G, or B
    is_active: bool = False
    last_update_time: float = 0.0
    navigation_history: list = None
    
    def __post_init__(self):
        """Initialize navigation history if not provided."""
        if self.navigation_history is None:
            self.navigation_history = []


class ControllerSelection:
    """
    Individual controller selection state management.
    
    Handles independent navigation, frame preservation, and selection state
    for a single controller.
    """
    
    def __init__(self, controller_id: int, instance_id: int):
        """
        Initialize controller selection state.
        
        Args:
            controller_id: Unique controller ID (0-3)
            instance_id: Pygame controller instance ID
        """
        self.controller_id = controller_id
        self.instance_id = instance_id
        self.state = ControllerSelectionState(
            controller_id=controller_id,
            instance_id=instance_id
        )
        self.creation_time = time.time()
        
    def set_animation(self, animation_name: str) -> None:
        """
        Set the selected animation for this controller.
        
        Args:
            animation_name: Name of the animation strip
        """
        if self.state.selected_animation != animation_name:
            # Preserve frame index when switching animations
            self.state.navigation_history.append({
                'animation': self.state.selected_animation,
                'frame': self.state.selected_frame,
                'timestamp': time.time()
            })
            
            self.state.selected_animation = animation_name
            self.state.last_update_time = time.time()
            
            print(f"DEBUG: Controller {self.controller_id} selected animation '{animation_name}'")
    
    def set_frame(self, frame_index: int) -> None:
        """
        Set the selected frame for this controller.
        
        Args:
            frame_index: Index of the frame
        """
        if self.state.selected_frame != frame_index:
            self.state.selected_frame = frame_index
            self.state.last_update_time = time.time()
            
            print(f"DEBUG: Controller {self.controller_id} selected frame {frame_index}")
    
    def set_selection(self, animation_name: str, frame_index: int) -> None:
        """
        Set both animation and frame selection.
        
        Args:
            animation_name: Name of the animation strip
            frame_index: Index of the frame
        """
        animation_changed = self.state.selected_animation != animation_name
        frame_changed = self.state.selected_frame != frame_index
        
        if animation_changed or frame_changed:
            # Only add to history if we had a previous selection (not initial empty state)
            if animation_changed and self.state.selected_animation:
                # Preserve frame index when switching animations
                self.state.navigation_history.append({
                    'animation': self.state.selected_animation,
                    'frame': self.state.selected_frame,
                    'timestamp': time.time()
                })
            
            self.state.selected_animation = animation_name
            self.state.selected_frame = frame_index
            self.state.last_update_time = time.time()
            
            print(f"DEBUG: Controller {self.controller_id} selected animation '{animation_name}', frame {frame_index}")
    
    def get_selection(self) -> tuple[str, int]:
        """
        Get current selection (animation, frame).
        
        Returns:
            Tuple of (animation_name, frame_index)
        """
        return (self.state.selected_animation, self.state.selected_frame)
    
    def get_animation(self) -> str:
        """
        Get current animation.
        
        Returns:
            Current animation name
        """
        return self.state.selected_animation
    
    def get_frame(self) -> int:
        """
        Get current frame.
        
        Returns:
            Current frame index
        """
        return self.state.selected_frame
    
    def set_slider(self, slider_name: str) -> None:
        """
        Set the selected slider for this controller.
        
        Args:
            slider_name: Name of the slider (R, G, or B)
        """
        if slider_name in ["R", "G", "B"] and self.state.selected_slider != slider_name:
            self.state.selected_slider = slider_name
            self.state.last_update_time = time.time()
            
            print(f"DEBUG: Controller {self.controller_id} selected slider '{slider_name}'")
    
    def get_slider(self) -> str:
        """
        Get the current slider selection.
        
        Returns:
            Name of the selected slider (R, G, or B)
        """
        return self.state.selected_slider
    
    def activate(self) -> None:
        """Activate this controller for navigation."""
        if not self.state.is_active:
            self.state.is_active = True
            self.state.last_update_time = time.time()
            print(f"DEBUG: Controller {self.controller_id} activated")
    
    def deactivate(self) -> None:
        """Deactivate this controller."""
        if self.state.is_active:
            self.state.is_active = False
            print(f"DEBUG: Controller {self.controller_id} deactivated")
    
    def is_active(self) -> bool:
        """
        Check if controller is active.
        
        Returns:
            True if active, False otherwise
        """
        return self.state.is_active
    
    def preserve_frame_for_animation(self, new_animation: str, available_frames: int) -> int:
        """
        Preserve frame index when switching animations.
        
        Args:
            new_animation: Name of the new animation
            available_frames: Number of frames available in new animation
            
        Returns:
            Preserved frame index (clamped to available range)
        """
        # Try to preserve the current frame index
        target_frame = self.state.selected_frame
        
        # Clamp to available range
        if target_frame >= available_frames:
            target_frame = max(0, available_frames - 1)
        elif target_frame < 0:
            target_frame = 0
            
        # Check if we have a previous selection for this animation
        for history_entry in reversed(self.state.navigation_history):
            if history_entry['animation'] == new_animation:
                # Use the frame from the last time we were on this animation
                target_frame = history_entry['frame']
                if target_frame >= available_frames:
                    target_frame = max(0, available_frames - 1)
                elif target_frame < 0:
                    target_frame = 0
                break
        
        return target_frame
    
    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.state.last_update_time = time.time()
    
    def get_activity_age(self) -> float:
        """
        Get the age of the last activity in seconds.
        
        Returns:
            Age in seconds since last activity
        """
        return time.time() - self.state.last_update_time
    
    def get_navigation_history(self) -> list:
        """
        Get the navigation history.
        
        Returns:
            List of navigation history entries
        """
        return self.state.navigation_history.copy()
    
    def clear_navigation_history(self) -> None:
        """Clear the navigation history."""
        self.state.navigation_history.clear()
    
    def get_state_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the controller selection state.
        
        Returns:
            Dictionary with state information
        """
        return {
            'controller_id': self.controller_id,
            'instance_id': self.instance_id,
            'selected_animation': self.state.selected_animation,
            'selected_frame': self.state.selected_frame,
            'is_active': self.state.is_active,
            'last_update_time': self.state.last_update_time,
            'activity_age': self.get_activity_age(),
            'navigation_history_count': len(self.state.navigation_history),
            'creation_time': self.creation_time
        }
    
    def reset_to_default(self) -> None:
        """Reset controller selection to default state."""
        self.state.selected_animation = ""
        self.state.selected_frame = 0
        self.state.is_active = False
        self.state.last_update_time = time.time()
        self.state.navigation_history.clear()
        print(f"DEBUG: Controller {self.controller_id} reset to default state")
    
    def clone_state_to(self, target_controller: 'ControllerSelection') -> None:
        """
        Clone this controller's state to another controller.
        
        Args:
            target_controller: Controller to clone state to
        """
        target_controller.set_selection(
            self.state.selected_animation,
            self.state.selected_frame
        )
        if self.state.is_active:
            target_controller.activate()
        else:
            target_controller.deactivate()
        
        print(f"DEBUG: Controller {self.controller_id} state cloned to controller {target_controller.controller_id}")
