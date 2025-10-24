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


class LocationType(Enum):
    """Location types for visual indicators."""
    FILM_STRIP = "film_strip"
    CANVAS = "canvas"
    SLIDER = "slider"


@dataclass
class VisualIndicator:
    """Visual indicator information."""
    controller_id: int
    instance_id: int
    position: Tuple[int, int]
    color: Tuple[int, int, int]
    shape: IndicatorShape
    size: int
    location_type: LocationType
    offset: Tuple[int, int] = (0, 0)
    is_visible: bool = True
    transparency: float = 1.0  # 1.0 = opaque, 0.0 = transparent


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
        # Location-specific indicator tracking
        self.indicators: Dict[int, VisualIndicator] = {}
        self.film_strip_indicators: Dict[int, VisualIndicator] = {}
        self.canvas_indicators: Dict[int, VisualIndicator] = {}
        self.slider_indicators: Dict[int, VisualIndicator] = {}
        
        # Location-specific collision groups
        self.collision_groups: Dict[Tuple[int, int], List[int]] = {}
        self.film_strip_collision_groups: Dict[Tuple[int, int], List[int]] = {}
        self.canvas_collision_groups: Dict[Tuple[int, int], List[int]] = {}
        self.slider_collision_groups: Dict[Tuple[int, int], List[int]] = {}
        
        # Position cache for performance
        self.position_cache: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        
    def add_controller_indicator(self, controller_id: int, instance_id: int, 
                               color: Tuple[int, int, int], 
                               position: Tuple[int, int],
                               location_type: LocationType = LocationType.FILM_STRIP) -> VisualIndicator:
        """
        Add a visual indicator for a controller.
        
        Args:
            controller_id: Unique controller ID
            instance_id: Pygame controller instance ID
            color: RGB color tuple
            position: Base position (x, y)
            location_type: Location type (FILM_STRIP or CANVAS)
            
        Returns:
            VisualIndicator object
        """
        # Set appropriate shape and transparency based on location type
        if location_type == LocationType.CANVAS:
            shape = IndicatorShape.SQUARE
            transparency = 0.5  # 50% transparent for canvas
        elif location_type == LocationType.SLIDER:
            shape = IndicatorShape.CIRCLE
            transparency = 0.8  # 80% opaque for sliders
        else:  # FILM_STRIP
            shape = IndicatorShape.TRIANGLE
            transparency = 1.0  # Fully opaque for film strip
        
        indicator = VisualIndicator(
            controller_id=controller_id,
            instance_id=instance_id,
            position=position,
            color=color,
            shape=shape,
            size=self.DEFAULT_SIZE,
            location_type=location_type,
            transparency=transparency
        )
        
        # Add to appropriate location-specific tracking
        if location_type == LocationType.FILM_STRIP:
            self.film_strip_indicators[controller_id] = indicator
            print(f"DEBUG: Added to film_strip_indicators - now {len(self.film_strip_indicators)} indicators")
        elif location_type == LocationType.CANVAS:
            self.canvas_indicators[controller_id] = indicator
            print(f"DEBUG: Added to canvas_indicators - now {len(self.canvas_indicators)} indicators")
        elif location_type == LocationType.SLIDER:
            self.slider_indicators[controller_id] = indicator
            print(f"DEBUG: Added to slider_indicators - now {len(self.slider_indicators)} indicators")
        
        # Keep main indicators dict for backward compatibility
        # Note: This will overwrite if same controller_id is used for different locations
        self.indicators[controller_id] = indicator
        
        # Update collision groups for the specific location
        self._update_collision_groups(location_type)
        
        print(f"DEBUG: Added {location_type.value} indicator for controller {controller_id} at {position}")
        return indicator
    
    def remove_controller_indicator(self, controller_id: int) -> None:
        """
        Remove a visual indicator for a controller.
        
        Args:
            controller_id: Controller ID to remove
        """
        if controller_id in self.indicators:
            # Get the location type before removing
            location_type = self.indicators[controller_id].location_type
            
            # Remove from location-specific dictionaries first
            if location_type == LocationType.FILM_STRIP and controller_id in self.film_strip_indicators:
                del self.film_strip_indicators[controller_id]
            elif location_type == LocationType.CANVAS and controller_id in self.canvas_indicators:
                del self.canvas_indicators[controller_id]
            elif location_type == LocationType.SLIDER and controller_id in self.slider_indicators:
                del self.slider_indicators[controller_id]
            
            # Remove from main indicators dict
            del self.indicators[controller_id]
            
            self._update_collision_groups()
            print(f"DEBUG: Removed indicator for controller {controller_id}")
    
    def remove_controller_indicator_for_location(self, controller_id: int, location_type: LocationType) -> None:
        """
        Remove a visual indicator for a controller from a specific location.
        
        Args:
            controller_id: Controller ID to remove
            location_type: Location type to remove from
        """
        # Remove from location-specific dictionary
        if location_type == LocationType.FILM_STRIP and controller_id in self.film_strip_indicators:
            del self.film_strip_indicators[controller_id]
        elif location_type == LocationType.CANVAS and controller_id in self.canvas_indicators:
            del self.canvas_indicators[controller_id]
        elif location_type == LocationType.SLIDER and controller_id in self.slider_indicators:
            del self.slider_indicators[controller_id]
        
        # Update collision groups for the specific location
        self._update_collision_groups(location_type)
        
        print(f"DEBUG: Removed {location_type.value} indicator for controller {controller_id}")
    
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
    
    def get_indicators_for_position(self, position: Tuple[int, int], 
                                   location_type: LocationType = None) -> List[VisualIndicator]:
        """
        Get all indicators at a specific position.
        
        Args:
            position: Position to check
            location_type: Specific location type to check (None for all)
            
        Returns:
            List of indicators at the position
        """
        indicators = []
        
        if location_type is None:
            # Check all location types
            for indicator in self.indicators.values():
                if indicator.position == position:
                    indicators.append(indicator)
        else:
            # Check specific location type
            if location_type == LocationType.FILM_STRIP:
                indicators_dict = self.film_strip_indicators
            elif location_type == LocationType.CANVAS:
                indicators_dict = self.canvas_indicators
            elif location_type == LocationType.SLIDER:
                indicators_dict = self.slider_indicators
            else:
                indicators_dict = self.indicators
                
            for indicator in indicators_dict.values():
                if indicator.position == position:
                    indicators.append(indicator)
        
        return indicators
    
    def _update_collision_groups(self, location_type: LocationType = None) -> None:
        """Update collision groups based on current positions."""
        if location_type is None:
            # Update all location types
            self._update_collision_groups(LocationType.FILM_STRIP)
            self._update_collision_groups(LocationType.CANVAS)
            self._update_collision_groups(LocationType.SLIDER)
            return
        
        # Clear the appropriate collision groups
        if location_type == LocationType.FILM_STRIP:
            self.film_strip_collision_groups.clear()
            indicators_dict = self.film_strip_indicators
        elif location_type == LocationType.CANVAS:
            self.canvas_collision_groups.clear()
            indicators_dict = self.canvas_indicators
        elif location_type == LocationType.SLIDER:
            self.slider_collision_groups.clear()
            indicators_dict = self.slider_indicators
        else:
            return
        
        # Group indicators by position for the specific location
        for controller_id, indicator in indicators_dict.items():
            if indicator.is_visible:
                position = indicator.position
                collision_groups = self._get_collision_groups_for_location(location_type)
                if position not in collision_groups:
                    collision_groups[position] = []
                collision_groups[position].append(controller_id)
        
        # Apply collision avoidance for groups with multiple indicators
        collision_groups = self._get_collision_groups_for_location(location_type)
        for position, controller_ids in collision_groups.items():
            if len(controller_ids) > 1:
                self._apply_collision_avoidance(position, controller_ids, location_type)
    
    def _get_collision_groups_for_location(self, location_type: LocationType) -> Dict[Tuple[int, int], List[int]]:
        """Get collision groups for a specific location type."""
        if location_type == LocationType.FILM_STRIP:
            return self.film_strip_collision_groups
        elif location_type == LocationType.CANVAS:
            return self.canvas_collision_groups
        elif location_type == LocationType.SLIDER:
            return self.slider_collision_groups
        else:
            return self.collision_groups
    
    def _apply_collision_avoidance(self, position: Tuple[int, int], 
                                 controller_ids: List[int],
                                 location_type: LocationType = LocationType.FILM_STRIP) -> None:
        """
        Apply collision avoidance for indicators at the same position.
        
        Args:
            position: Base position
            controller_ids: List of controller IDs at this position
            location_type: Location type for the indicators
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
        
        # Get the appropriate indicators dictionary
        if location_type == LocationType.FILM_STRIP:
            indicators_dict = self.film_strip_indicators
        elif location_type == LocationType.CANVAS:
            indicators_dict = self.canvas_indicators
        elif location_type == LocationType.SLIDER:
            indicators_dict = self.slider_indicators
        else:
            indicators_dict = self.indicators
        
        # Apply offsets to indicators
        for i, controller_id in enumerate(controller_ids):
            if controller_id in indicators_dict:
                if i < len(offsets):
                    indicators_dict[controller_id].offset = offsets[i]
                    print(f"DEBUG: Applied {location_type.value} offset {offsets[i]} to controller {controller_id}")
                else:
                    # Fallback to default offset
                    indicators_dict[controller_id].offset = (0, 0)
                    print(f"DEBUG: Applied fallback {location_type.value} offset (0, 0) to controller {controller_id}")
    
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
    
    def get_indicators_by_location(self, location_type: LocationType) -> Dict[int, VisualIndicator]:
        """
        Get all indicators for a specific location type.
        
        Args:
            location_type: Location type to get indicators for
            
        Returns:
            Dictionary of controller_id -> VisualIndicator
        """
        if location_type == LocationType.FILM_STRIP:
            print(f"DEBUG: get_indicators_by_location FILM_STRIP - {len(self.film_strip_indicators)} indicators")
            return self.film_strip_indicators
        elif location_type == LocationType.CANVAS:
            print(f"DEBUG: get_indicators_by_location CANVAS - {len(self.canvas_indicators)} indicators")
            return self.canvas_indicators
        elif location_type == LocationType.SLIDER:
            print(f"DEBUG: get_indicators_by_location SLIDER - {len(self.slider_indicators)} indicators")
            return self.slider_indicators
        else:
            return self.indicators
    
    def optimize_positioning(self) -> None:
        """
        Optimize positioning to minimize collisions and improve visual clarity.
        """
        # Clear position cache to force recalculation
        self.position_cache.clear()
        
        # Recalculate all positions
        self._update_collision_groups()
        
        print("DEBUG: Optimized positioning for all indicators")
