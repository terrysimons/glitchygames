"""
Enhanced Multi-Controller Integration for Bitmappy

This module provides enhanced multi-controller features for the bitmappy tool,
including advanced visual management, performance optimizations, and improved
user experience.
"""

import time
from typing import Dict, List, Optional, Tuple
import pygame

from glitchygames.tools.multi_controller_manager import MultiControllerManager
from glitchygames.tools.controller_selection import ControllerSelection
from glitchygames.tools.visual_collision_manager import VisualCollisionManager


class BitmappyMultiControllerEnhancements:
    """Enhanced multi-controller features for bitmappy."""
    
    def __init__(self, bitmappy_scene):
        """Initialize enhanced multi-controller features.
        
        Args:
            bitmappy_scene: The bitmappy scene instance
        """
        self.scene = bitmappy_scene
        self.manager = bitmappy_scene.multi_controller_manager
        self.visual_manager = bitmappy_scene.visual_collision_manager
        self.controller_selections = bitmappy_scene.controller_selections
        
        # Enhanced features
        self.controller_history: Dict[int, List[Dict]] = {}
        self.performance_metrics: Dict[str, float] = {}
        self.visual_customizations: Dict[int, Dict] = {}
        self.controller_groups: Dict[str, List[int]] = {}
        
        # Performance optimization
        self.last_update_time = 0
        self.update_throttle = 0.016  # 60 FPS max
        self.position_cache: Dict[int, Tuple[int, int]] = {}
        
    def enhanced_controller_activation(self, controller_id: int) -> bool:
        """Enhanced controller activation with advanced features.
        
        Args:
            controller_id: Controller ID to activate
            
        Returns:
            bool: True if activation successful
        """
        if controller_id not in self.controller_selections:
            return False
        
        controller_selection = self.controller_selections[controller_id]
        controller_selection.activate()
        
        # Initialize controller history
        self.controller_history[controller_id] = []
        
        # Set up visual customizations
        self.visual_customizations[controller_id] = {
            'size': 12,
            'shape': 'triangle',
            'pulse': False,
            'trail': False
        }
        
        # Update visual indicator with enhanced features
        self._update_enhanced_visual_indicator(controller_id)
        
        # Record activation in history
        self._record_controller_action(controller_id, 'activate', {})
        
        return True
    
    def enhanced_navigation(self, controller_id: int, direction: str, amount: int = 1) -> bool:
        """Enhanced navigation with advanced features.
        
        Args:
            controller_id: Controller ID
            direction: Navigation direction ('frame', 'animation')
            amount: Amount to navigate (can be negative)
            
        Returns:
            bool: True if navigation successful
        """
        if controller_id not in self.controller_selections:
            return False
        
        controller_selection = self.controller_selections[controller_id]
        current_animation, current_frame = controller_selection.get_selection()
        
        if direction == 'frame':
            new_frame = max(0, current_frame + amount)
            if current_animation in self.scene.film_strips:
                max_frames = len(self.scene.film_strips[current_animation].frames)
                new_frame = min(new_frame, max_frames - 1)
            controller_selection.set_selection(current_animation, new_frame)
            
        elif direction == 'animation':
            animations = list(self.scene.film_strips.keys())
            if animations:
                current_index = animations.index(current_animation) if current_animation in animations else 0
                new_index = (current_index + amount) % len(animations)
                new_animation = animations[new_index]
                
                # Preserve frame if possible
                if new_animation in self.scene.film_strips:
                    max_frames = len(self.scene.film_strips[new_animation].frames)
                    new_frame = min(current_frame, max_frames - 1)
                else:
                    new_frame = 0
                
                controller_selection.set_selection(new_animation, new_frame)
        
        # Update visual indicator
        self._update_enhanced_visual_indicator(controller_id)
        
        # Record navigation in history
        self._record_controller_action(controller_id, 'navigate', {
            'direction': direction,
            'amount': amount,
            'result': controller_selection.get_selection()
        })
        
        return True
    
    def enhanced_visual_management(self, controller_id: int) -> None:
        """Enhanced visual management with advanced features.
        
        Args:
            controller_id: Controller ID
        """
        if controller_id not in self.controller_selections:
            return
        
        controller_selection = self.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()
        
        if not animation or animation not in self.scene.film_strips:
            return
        
        # Calculate enhanced position
        position = self._calculate_enhanced_position(controller_id, animation, frame)
        
        # Apply visual customizations
        self._apply_visual_customizations(controller_id)
        
        # Update visual indicator
        if controller_id not in self.visual_manager.indicators:
            self._create_enhanced_visual_indicator(controller_id, position)
        else:
            self.visual_manager.update_controller_position(controller_id, position)
        
        # Update performance metrics
        self._update_performance_metrics('visual_update', time.time())
    
    def _calculate_enhanced_position(self, controller_id: int, animation: str, frame: int) -> Tuple[int, int]:
        """Calculate enhanced position for visual indicator.
        
        Args:
            controller_id: Controller ID
            animation: Animation name
            frame: Frame number
            
        Returns:
            Tuple[int, int]: Calculated position
        """
        # Use cached position if available and recent
        if controller_id in self.position_cache:
            return self.position_cache[controller_id]
        
        # Calculate position based on film strip layout
        base_x = 100
        base_y = 100
        
        # Find animation index
        animations = list(self.scene.film_strips.keys())
        animation_index = animations.index(animation) if animation in animations else 0
        
        # Calculate position
        x = base_x + animation_index * 150
        y = base_y + frame * 20
        
        # Apply controller-specific offset
        x += controller_id * 10
        y += controller_id * 5
        
        position = (x, y)
        
        # Cache position
        self.position_cache[controller_id] = position
        
        return position
    
    def _create_enhanced_visual_indicator(self, controller_id: int, position: Tuple[int, int]) -> None:
        """Create enhanced visual indicator.
        
        Args:
            controller_id: Controller ID
            position: Position for indicator
        """
        # Get controller info
        controller_info = None
        for instance_id, info in self.manager.controllers.items():
            if info.controller_id == controller_id:
                controller_info = info
                break
        
        if not controller_info:
            return
        
        # Create enhanced indicator
        self.visual_manager.add_controller_indicator(
            controller_id=controller_id,
            instance_id=controller_info.instance_id,
            color=controller_info.color,
            position=position
        )
        
        # Apply customizations
        self._apply_visual_customizations(controller_id)
    
    def _apply_visual_customizations(self, controller_id: int) -> None:
        """Apply visual customizations to controller indicator.
        
        Args:
            controller_id: Controller ID
        """
        if controller_id not in self.visual_customizations:
            return
        
        customizations = self.visual_customizations[controller_id]
        
        if controller_id in self.visual_manager.indicators:
            indicator = self.visual_manager.indicators[controller_id]
            
            # Apply size customization
            if 'size' in customizations:
                indicator.size = customizations['size']
            
            # Apply shape customization
            if 'shape' in customizations:
                from glitchygames.tools.visual_collision_manager import IndicatorShape
                if customizations['shape'] == 'circle':
                    indicator.shape = IndicatorShape.CIRCLE
                elif customizations['shape'] == 'square':
                    indicator.shape = IndicatorShape.SQUARE
                else:
                    indicator.shape = IndicatorShape.TRIANGLE
    
    def _update_enhanced_visual_indicator(self, controller_id: int) -> None:
        """Update enhanced visual indicator.
        
        Args:
            controller_id: Controller ID
        """
        # Throttle updates for performance
        current_time = time.time()
        if current_time - self.last_update_time < self.update_throttle:
            return
        
        self.last_update_time = current_time
        
        # Update visual management
        self.enhanced_visual_management(controller_id)
    
    def _record_controller_action(self, controller_id: int, action: str, data: Dict) -> None:
        """Record controller action in history.
        
        Args:
            controller_id: Controller ID
            action: Action performed
            data: Action data
        """
        if controller_id not in self.controller_history:
            self.controller_history[controller_id] = []
        
        action_record = {
            'timestamp': time.time(),
            'action': action,
            'data': data
        }
        
        self.controller_history[controller_id].append(action_record)
        
        # Limit history size
        if len(self.controller_history[controller_id]) > 100:
            self.controller_history[controller_id] = self.controller_history[controller_id][-100:]
    
    def _update_performance_metrics(self, operation: str, timestamp: float) -> None:
        """Update performance metrics.
        
        Args:
            operation: Operation name
            timestamp: Timestamp
        """
        if operation not in self.performance_metrics:
            self.performance_metrics[operation] = timestamp
        else:
            # Calculate time difference
            time_diff = timestamp - self.performance_metrics[operation]
            self.performance_metrics[operation] = time_diff
    
    def get_controller_performance_stats(self, controller_id: int) -> Dict:
        """Get performance statistics for a controller.
        
        Args:
            controller_id: Controller ID
            
        Returns:
            Dict: Performance statistics
        """
        stats = {
            'controller_id': controller_id,
            'history_length': len(self.controller_history.get(controller_id, [])),
            'last_action': None,
            'performance_metrics': self.performance_metrics.copy()
        }
        
        if controller_id in self.controller_history and self.controller_history[controller_id]:
            last_action = self.controller_history[controller_id][-1]
            stats['last_action'] = {
                'action': last_action['action'],
                'timestamp': last_action['timestamp']
            }
        
        return stats
    
    def create_controller_group(self, group_name: str, controller_ids: List[int]) -> bool:
        """Create a controller group for coordinated actions.
        
        Args:
            group_name: Name of the group
            controller_ids: List of controller IDs
            
        Returns:
            bool: True if group created successfully
        """
        # Validate controller IDs
        for controller_id in controller_ids:
            if controller_id not in self.controller_selections:
                return False
        
        self.controller_groups[group_name] = controller_ids.copy()
        return True
    
    def execute_group_action(self, group_name: str, action: str, **kwargs) -> bool:
        """Execute action on all controllers in a group.
        
        Args:
            group_name: Name of the group
            action: Action to execute
            **kwargs: Action parameters
            
        Returns:
            bool: True if action executed successfully
        """
        if group_name not in self.controller_groups:
            return False
        
        success = True
        for controller_id in self.controller_groups[group_name]:
            if action == 'navigate':
                direction = kwargs.get('direction', 'frame')
                amount = kwargs.get('amount', 1)
                if not self.enhanced_navigation(controller_id, direction, amount):
                    success = False
            elif action == 'activate':
                if not self.enhanced_controller_activation(controller_id):
                    success = False
        
        return success
    
    def get_controller_status_summary(self) -> Dict:
        """Get comprehensive status summary for all controllers.
        
        Returns:
            Dict: Status summary
        """
        summary = {
            'total_controllers': len(self.controller_selections),
            'active_controllers': 0,
            'controller_groups': len(self.controller_groups),
            'performance_metrics': self.performance_metrics.copy(),
            'controllers': {}
        }
        
        for controller_id, selection in self.controller_selections.items():
            if selection.is_active():
                summary['active_controllers'] += 1
            
            summary['controllers'][controller_id] = {
                'active': selection.is_active(),
                'selection': selection.get_selection(),
                'history_length': len(self.controller_history.get(controller_id, [])),
                'customizations': self.visual_customizations.get(controller_id, {})
            }
        
        return summary
    
    def cleanup_inactive_controllers(self) -> int:
        """Clean up inactive controllers and their resources.
        
        Returns:
            int: Number of controllers cleaned up
        """
        cleaned_count = 0
        
        # Find inactive controllers
        inactive_controllers = []
        for controller_id, selection in self.controller_selections.items():
            if not selection.is_active():
                inactive_controllers.append(controller_id)
        
        # Clean up inactive controllers
        for controller_id in inactive_controllers:
            # Remove from visual manager
            if controller_id in self.visual_manager.indicators:
                self.visual_manager.remove_controller_indicator(controller_id)
            
            # Remove from history
            if controller_id in self.controller_history:
                del self.controller_history[controller_id]
            
            # Remove from customizations
            if controller_id in self.visual_customizations:
                del self.visual_customizations[controller_id]
            
            # Remove from position cache
            if controller_id in self.position_cache:
                del self.position_cache[controller_id]
            
            # Remove from controller selections
            del self.controller_selections[controller_id]
            
            cleaned_count += 1
        
        return cleaned_count
    
    def optimize_performance(self) -> Dict:
        """Optimize performance by cleaning up resources and optimizing operations.
        
        Returns:
            Dict: Optimization results
        """
        optimization_results = {
            'controllers_cleaned': 0,
            'cache_cleared': 0,
            'performance_improved': False
        }
        
        # Clean up inactive controllers
        optimization_results['controllers_cleaned'] = self.cleanup_inactive_controllers()
        
        # Clear old position cache
        old_cache_size = len(self.position_cache)
        self.position_cache.clear()
        optimization_results['cache_cleared'] = old_cache_size
        
        # Optimize visual manager
        self.visual_manager.optimize_positioning()
        
        # Check if performance improved
        if optimization_results['controllers_cleaned'] > 0 or optimization_results['cache_cleared'] > 0:
            optimization_results['performance_improved'] = True
        
        return optimization_results
