#!/usr/bin/env python3
"""Onion skinning system for bitmappy tool.

This module provides onion skinning functionality for the bitmappy sprite editor,
allowing users to see previous and future frames as semi-transparent overlays
while editing the current frame.
"""

import logging
from typing import Dict, Set, Tuple, Optional, Any

LOG = logging.getLogger("game.tools.onion_skinning")
LOG.addHandler(logging.NullHandler())


class OnionSkinningManager:
    """Manages onion skinning state for animated sprites.
    
    This class tracks which frames have onion skinning enabled and provides
    methods to toggle onion skinning on/off for individual frames.
    """
    
    def __init__(self):
        """Initialize the onion skinning manager."""
        # Track onion skinning state per animation and frame
        # Format: {animation_name: {frame_index: bool}}
        self.onion_skinning_enabled: Dict[str, Dict[int, bool]] = {}
        
        # Global onion skinning toggle
        self.global_onion_skinning_enabled = True
        
        # Transparency level for onion frames (0.0 = transparent, 1.0 = opaque)
        self.onion_transparency = 0.5
        
        LOG.debug("OnionSkinningManager initialized")
    
    def toggle_frame_onion_skinning(self, animation: str, frame: int) -> bool:
        """Toggle onion skinning for a specific frame.
        
        Args:
            animation: Name of the animation
            frame: Frame index
            
        Returns:
            bool: New onion skinning state for the frame
        """
        if animation not in self.onion_skinning_enabled:
            self.onion_skinning_enabled[animation] = {}
        
        current_state = self.onion_skinning_enabled[animation].get(frame, False)
        new_state = not current_state
        self.onion_skinning_enabled[animation][frame] = new_state
        
        LOG.debug(f"Toggled onion skinning for {animation}[{frame}]: {new_state}")
        return new_state
    
    def is_frame_onion_skinned(self, animation: str, frame: int) -> bool:
        """Check if a frame has onion skinning enabled.
        
        Args:
            animation: Name of the animation
            frame: Frame index
            
        Returns:
            bool: True if onion skinning is enabled for this frame
        """
        if not self.global_onion_skinning_enabled:
            return False
            
        return self.onion_skinning_enabled.get(animation, {}).get(frame, False)
    
    def get_onion_skinned_frames(self, animation: str, current_frame: int, total_frames: int) -> Set[int]:
        """Get all frames that should be rendered with onion skinning.
        
        Args:
            animation: Name of the animation
            current_frame: Current frame being edited (excluded from onion frames)
            total_frames: Total number of frames in the animation
            
        Returns:
            Set[int]: Set of frame indices that should be onion skinned
        """
        if not self.global_onion_skinning_enabled:
            return set()
        
        # NEW APPROACH: Return all frames except current when global onion skinning is enabled
        all_frames = set(range(total_frames))
        return all_frames - {current_frame}
    
    def toggle_global_onion_skinning(self) -> bool:
        """Toggle global onion skinning on/off.
        
        Returns:
            bool: New global onion skinning state
        """
        self.global_onion_skinning_enabled = not self.global_onion_skinning_enabled
        LOG.debug(f"Global onion skinning toggled: {self.global_onion_skinning_enabled}")
        return self.global_onion_skinning_enabled
    
    def is_global_onion_skinning_enabled(self) -> bool:
        """Check if global onion skinning is enabled.
        
        Returns:
            bool: True if global onion skinning is enabled
        """
        return self.global_onion_skinning_enabled
    
    def set_transparency(self, transparency: float) -> None:
        """Set the transparency level for onion frames.
        
        Args:
            transparency: Transparency level (0.0 = transparent, 1.0 = opaque)
        """
        self.onion_transparency = max(0.0, min(1.0, transparency))
        LOG.debug(f"Onion transparency set to: {self.onion_transparency}")
    
    def clear_animation_onion_skinning(self, animation: str) -> None:
        """Clear all onion skinning for a specific animation.
        
        Args:
            animation: Name of the animation
        """
        if animation in self.onion_skinning_enabled:
            self.onion_skinning_enabled[animation].clear()
            LOG.debug(f"Cleared onion skinning for animation: {animation}")
    
    def get_animation_onion_state(self, animation: str) -> Dict[int, bool]:
        """Get the onion skinning state for all frames in an animation.
        
        Args:
            animation: Name of the animation
            
        Returns:
            Dict[int, bool]: Frame index to onion skinning state mapping
        """
        return self.onion_skinning_enabled.get(animation, {}).copy()
    
    def set_animation_onion_state(self, animation: str, frame_states: Dict[int, bool]) -> None:
        """Set the onion skinning state for all frames in an animation.
        
        Args:
            animation: Name of the animation
            frame_states: Frame index to onion skinning state mapping
        """
        self.onion_skinning_enabled[animation] = frame_states.copy()
        LOG.debug(f"Set onion skinning state for animation {animation}: {frame_states}")


# Global onion skinning manager instance
onion_skinning_manager = OnionSkinningManager()


def get_onion_skinning_manager() -> OnionSkinningManager:
    """Get the global onion skinning manager instance.
    
    Returns:
        OnionSkinningManager: The global onion skinning manager
    """
    return onion_skinning_manager
