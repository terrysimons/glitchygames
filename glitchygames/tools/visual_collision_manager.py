"""
Visual Collision Manager for Multi-Controller System

This module provides smart positioning and collision avoidance for multiple
controller indicators, ensuring clear visual distinction and preventing
overlap when multiple controllers select the same frame.

Features:
- Smart positioning algorithms
- Collision detection and avoidance
- Visual indicator management
- Controller-specific positioning
"""

import pygame
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class IndicatorShape(Enum):
    """Visual indicator shapes."""
    TRIANGLE = "triangle"
    CIRCLE = "circle"
    SQUARE = "square"
    DIAMOND = "diamond"


@dataclass
class VisualIndicator:
    """Visual indicator information."""
    controller_id: int
    instance_id: int
    position: Tuple[int, int]
    color: Tuple[int, int, int]
    shape: IndicatorShape
    size: int
    offset: Tuple[int, int] = (0, 0)
    is_visible: bool = True


class VisualCollisionManager:
    """
    Manages visual indicators for multiple controllers with collision avoidance.
    
    Provides smart positioning to prevent visual overlap when multiple
    controllers select the same frame or area.
    """
    
    # Default indicator properties
    DEFAULT_SIZE = 12
    MIN_SPACING = 8
    MAX_OFFSET = 20
    
    # Positioning patterns for collision avoidance
    POSITION_PATTERNS = [
        (0, 0),      # Center
        (-15, -15),  # Top-left
        (15, -15),   # Top-right
        (-15, 15),   # Bottom-left
        (15, 15),    # Bottom-right
        (-25, 0),    # Far left
        (25, 0),     # Far right
        (0, -25),    # Far top
        (0, 25),     # Far bottom
    ]
    
    def __init__(self):
        """Initialize the visual collision manager."""
        self.indicators: Dict[int, VisualIndicator] = {}
        self.collision_groups: Dict[Tuple[int, int], List[int]] = {}
        self.position_cache: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        
    def add_controller_indicator(self, controller_id: int, instance_id: int, 
                               color: Tuple[int, int, int], 
                               position: Tuple[int, int]) -> VisualIndicator:
        """
        Add a visual indicator for a controller.
        
        Args:
            controller_id: Unique controller ID
            instance_id: Pygame controller instance ID
            color: RGB color tuple
            position: Base position (x, y)
            
        Returns:
            VisualIndicator object
        """
        indicator = VisualIndicator(
            controller_id=controller_id,
            instance_id=instance_id,
            position=position,
            color=color,
            shape=IndicatorShape.TRIANGLE,
            size=self.DEFAULT_SIZE
        )
        
        self.indicators[controller_id] = indicator
        self._update_collision_groups()
        
        print(f"DEBUG: Added indicator for controller {controller_id} at {position}")
        return indicator
    
    def remove_controller_indicator(self, controller_id: int) -> None:
        """
        Remove a visual indicator for a controller.
        
        Args:
            controller_id: Controller ID to remove
        """
        if controller_id in self.indicators:
            del self.indicators[controller_id]
            self._update_collision_groups()
            print(f"DEBUG: Removed indicator for controller {controller_id}")
    
    def update_controller_position(self, controller_id: int, 
                                  new_position: Tuple[int, int]) -> None:
        """
        Update the position of a controller indicator.
        
        Args:
            controller_id: Controller ID
            new_position: New position (x, y)
        """
        if controller_id in self.indicators:
            self.indicators[controller_id].position = new_position
            self._update_collision_groups()
            print(f"DEBUG: Updated position for controller {controller_id} to {new_position}")
    
    def get_controller_indicator(self, controller_id: int) -> Optional[VisualIndicator]:
        """
        Get visual indicator for a controller.
        
        Args:
            controller_id: Controller ID
            
        Returns:
            VisualIndicator if found, None otherwise
        """
        return self.indicators.get(controller_id)
    
    def get_indicators_for_position(self, position: Tuple[int, int]) -> List[VisualIndicator]:
        """
        Get all indicators at a specific position.
        
        Args:
            position: Position to check
            
        Returns:
            List of indicators at the position
        """
        indicators = []
        for indicator in self.indicators.values():
            if indicator.position == position:
                indicators.append(indicator)
        return indicators
    
    def _update_collision_groups(self) -> None:
        """Update collision groups based on current positions."""
        self.collision_groups.clear()
        
        # Group indicators by position
        for controller_id, indicator in self.indicators.items():
            if indicator.is_visible:
                position = indicator.position
                if position not in self.collision_groups:
                    self.collision_groups[position] = []
                self.collision_groups[position].append(controller_id)
        
        # Apply collision avoidance for groups with multiple indicators
        for position, controller_ids in self.collision_groups.items():
            if len(controller_ids) > 1:
                self._apply_collision_avoidance(position, controller_ids)
    
    def _apply_collision_avoidance(self, position: Tuple[int, int], 
                                 controller_ids: List[int]) -> None:
        """
        Apply collision avoidance for indicators at the same position.
        
        Args:
            position: Base position
            controller_ids: List of controller IDs at this position
        """
        if len(controller_ids) <= 1:
            return
            
        # Use cached positions if available
        cache_key = (position[0], position[1])
        if cache_key in self.position_cache:
            offsets = self.position_cache[cache_key]
        else:
            offsets = self._calculate_offsets(len(controller_ids))
            self.position_cache[cache_key] = offsets
        
        # Apply offsets to indicators
        for i, controller_id in enumerate(controller_ids):
            if controller_id in self.indicators:
                if i < len(offsets):
                    self.indicators[controller_id].offset = offsets[i]
                else:
                    # Fallback to default offset
                    self.indicators[controller_id].offset = (0, 0)
                
                print(f"DEBUG: Applied offset {offsets[i]} to controller {controller_id}")
    
    def _calculate_offsets(self, count: int) -> List[Tuple[int, int]]:
        """
        Calculate offsets for collision avoidance.
        
        Args:
            count: Number of indicators to position
            
        Returns:
            List of offset tuples
        """
        if count <= 1:
            return [(0, 0)]
        
        # Use predefined patterns for common cases
        if count <= len(self.POSITION_PATTERNS):
            return self.POSITION_PATTERNS[:count]
        
        # Generate additional patterns for more indicators
        offsets = list(self.POSITION_PATTERNS)
        
        # Add more patterns if needed
        for i in range(len(self.POSITION_PATTERNS), count):
            # Create a spiral pattern
            angle = (i * 2 * 3.14159) / count
            radius = 15 + (i // 8) * 10
            x = int(radius * pygame.math.Vector2(1, 0).rotate(angle * 180 / 3.14159).x)
            y = int(radius * pygame.math.Vector2(1, 0).rotate(angle * 180 / 3.14159).y)
            offsets.append((x, y))
        
        return offsets[:count]
    
    def get_final_position(self, controller_id: int) -> Tuple[int, int]:
        """
        Get the final position of a controller indicator (base + offset).
        
        Args:
            controller_id: Controller ID
            
        Returns:
            Final position (x, y)
        """
        if controller_id not in self.indicators:
            return (0, 0)
        
        indicator = self.indicators[controller_id]
        base_x, base_y = indicator.position
        offset_x, offset_y = indicator.offset
        
        return (base_x + offset_x, base_y + offset_y)
    
    def get_all_indicators(self) -> List[VisualIndicator]:
        """
        Get all visual indicators.
        
        Returns:
            List of all indicators
        """
        return list(self.indicators.values())
    
    def get_visible_indicators(self) -> List[VisualIndicator]:
        """
        Get all visible indicators.
        
        Returns:
            List of visible indicators
        """
        return [indicator for indicator in self.indicators.values() if indicator.is_visible]
    
    def set_indicator_visibility(self, controller_id: int, visible: bool) -> None:
        """
        Set visibility of a controller indicator.
        
        Args:
            controller_id: Controller ID
            visible: Visibility state
        """
        if controller_id in self.indicators:
            self.indicators[controller_id].is_visible = visible
            self._update_collision_groups()
            print(f"DEBUG: Set visibility for controller {controller_id} to {visible}")
    
    def set_indicator_color(self, controller_id: int, color: Tuple[int, int, int]) -> None:
        """
        Set color of a controller indicator.
        
        Args:
            controller_id: Controller ID
            color: RGB color tuple
        """
        if controller_id in self.indicators:
            self.indicators[controller_id].color = color
            print(f"DEBUG: Set color for controller {controller_id} to {color}")
    
    def set_indicator_shape(self, controller_id: int, shape: IndicatorShape) -> None:
        """
        Set shape of a controller indicator.
        
        Args:
            controller_id: Controller ID
            shape: Indicator shape
        """
        if controller_id in self.indicators:
            self.indicators[controller_id].shape = shape
            print(f"DEBUG: Set shape for controller {controller_id} to {shape}")
    
    def set_indicator_size(self, controller_id: int, size: int) -> None:
        """
        Set size of a controller indicator.
        
        Args:
            controller_id: Controller ID
            size: Indicator size
        """
        if controller_id in self.indicators:
            self.indicators[controller_id].size = size
            print(f"DEBUG: Set size for controller {controller_id} to {size}")
    
    def clear_all_indicators(self) -> None:
        """Clear all visual indicators."""
        self.indicators.clear()
        self.collision_groups.clear()
        self.position_cache.clear()
        print("DEBUG: Cleared all indicators")
    
    def get_collision_summary(self) -> Dict[str, any]:
        """
        Get a summary of collision groups and positioning.
        
        Returns:
            Dictionary with collision information
        """
        summary = {
            'total_indicators': len(self.indicators),
            'collision_groups': len(self.collision_groups),
            'groups_with_collisions': 0,
            'position_cache_size': len(self.position_cache)
        }
        
        for position, controller_ids in self.collision_groups.items():
            if len(controller_ids) > 1:
                summary['groups_with_collisions'] += 1
        
        return summary
    
    def optimize_positioning(self) -> None:
        """
        Optimize positioning to minimize collisions and improve visual clarity.
        """
        # Clear position cache to force recalculation
        self.position_cache.clear()
        
        # Recalculate all positions
        self._update_collision_groups()
        
        print("DEBUG: Optimized positioning for all indicators")
