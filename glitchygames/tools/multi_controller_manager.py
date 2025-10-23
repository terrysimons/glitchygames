"""
Multi-Controller Manager for Bitmappy Tool

This module provides the core multi-controller system for the bitmappy tool,
enabling up to 4 simultaneous controllers with independent navigation and
visual distinction.

Features:
- Automatic controller assignment on first button press
- Controller reconnection handling
- Status tracking and display
- Event routing to appropriate controllers
- Visual collision management
"""

import pygame
import time
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum


class ControllerStatus(Enum):
    """Controller connection and assignment status."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ASSIGNED = "assigned"
    ACTIVE = "active"


@dataclass
class ControllerInfo:
    """Information about a connected controller."""
    controller_id: int
    instance_id: int
    status: ControllerStatus
    assigned_time: Optional[float] = None
    last_activity: Optional[float] = None
    color: Tuple[int, int, int] = (255, 0, 0)  # Default red


class MultiControllerManager:
    """
    Core multi-controller system for bitmappy tool.
    
    Manages up to 4 simultaneous controllers with automatic assignment,
    reconnection handling, and status tracking.
    """
    
    # Controller color scheme
    CONTROLLER_COLORS = [
        (255, 0, 0),    # Controller 0: Red
        (0, 255, 0),    # Controller 1: Green
        (0, 0, 255),    # Controller 2: Blue
        (255, 255, 0),  # Controller 3: Yellow
    ]
    
    MAX_CONTROLLERS = 4
    ASSIGNMENT_TIMEOUT = 5.0  # seconds
    
    def __init__(self):
        """Initialize the multi-controller manager."""
        self.controllers: Dict[int, ControllerInfo] = {}
        self.assigned_controllers: Dict[int, int] = {}  # instance_id -> controller_id
        self.next_controller_id = 0
        self.last_scan_time = 0
        self.scan_interval = 1.0  # seconds
        
    def scan_for_controllers(self) -> List[int]:
        """
        Scan for connected controllers and return list of instance IDs.
        
        Returns:
            List of controller instance IDs that are connected
        """
        current_time = time.time()
        if current_time - self.last_scan_time < self.scan_interval:
            return list(self.controllers.keys())
            
        self.last_scan_time = current_time
        
        # Get all connected controllers
        connected_instance_ids = []
        for i in range(pygame.joystick.get_count()):
            try:
                joystick = pygame.joystick.Joystick(i)
                if joystick.get_init():
                    instance_id = joystick.get_instance_id()
                    connected_instance_ids.append(instance_id)
            except pygame.error:
                continue
                
        # Update controller status
        for instance_id in list(self.controllers.keys()):
            if instance_id not in connected_instance_ids:
                # Controller disconnected
                self._handle_controller_disconnect(instance_id)
                
        # Add new controllers
        for instance_id in connected_instance_ids:
            if instance_id not in self.controllers:
                self._handle_controller_connect(instance_id)
                
        return connected_instance_ids
    
    def _handle_controller_connect(self, instance_id: int) -> None:
        """Handle a new controller connection."""
        controller_id = self._get_next_controller_id()
        color = self.CONTROLLER_COLORS[controller_id % len(self.CONTROLLER_COLORS)]
        
        self.controllers[instance_id] = ControllerInfo(
            controller_id=controller_id,
            instance_id=instance_id,
            status=ControllerStatus.CONNECTED,
            color=color
        )
        
        print(f"DEBUG: Controller {controller_id} connected (instance_id={instance_id}, color={color})")
    
    def _handle_controller_disconnect(self, instance_id: int) -> None:
        """Handle controller disconnection."""
        if instance_id in self.controllers:
            controller_info = self.controllers[instance_id]
            print(f"DEBUG: Controller {controller_info.controller_id} disconnected (instance_id={instance_id})")
            
            # Remove from assigned controllers
            if instance_id in self.assigned_controllers:
                del self.assigned_controllers[instance_id]
                
            del self.controllers[instance_id]
    
    def _get_next_controller_id(self) -> int:
        """Get the next available controller ID."""
        controller_id = self.next_controller_id
        self.next_controller_id = (self.next_controller_id + 1) % self.MAX_CONTROLLERS
        return controller_id
    
    def assign_controller(self, instance_id: int) -> Optional[int]:
        """
        Assign a controller on first button press.
        
        Args:
            instance_id: The controller instance ID
            
        Returns:
            Controller ID if assignment successful, None otherwise
        """
        if instance_id not in self.controllers:
            return None
            
        if instance_id in self.assigned_controllers:
            return self.assigned_controllers[instance_id]
            
        controller_info = self.controllers[instance_id]
        if controller_info.status != ControllerStatus.CONNECTED:
            return None
            
        # Assign the controller
        controller_info.status = ControllerStatus.ASSIGNED
        controller_info.assigned_time = time.time()
        controller_info.last_activity = time.time()
        
        self.assigned_controllers[instance_id] = controller_info.controller_id
        
        print(f"DEBUG: Controller {controller_info.controller_id} assigned (instance_id={instance_id})")
        return controller_info.controller_id
    
    def activate_controller(self, instance_id: int) -> bool:
        """
        Activate a controller for navigation.
        
        Args:
            instance_id: The controller instance ID
            
        Returns:
            True if activation successful, False otherwise
        """
        if instance_id not in self.assigned_controllers:
            return False
            
        if instance_id in self.controllers:
            self.controllers[instance_id].status = ControllerStatus.ACTIVE
            self.controllers[instance_id].last_activity = time.time()
            return True
            
        return False
    
    def get_controller_info(self, instance_id: int) -> Optional[ControllerInfo]:
        """
        Get controller information by instance ID.
        
        Args:
            instance_id: The controller instance ID
            
        Returns:
            ControllerInfo if found, None otherwise
        """
        return self.controllers.get(instance_id)
    
    def get_controller_id(self, instance_id: int) -> Optional[int]:
        """
        Get controller ID by instance ID.
        
        Args:
            instance_id: The controller instance ID
            
        Returns:
            Controller ID if assigned, None otherwise
        """
        return self.assigned_controllers.get(instance_id)
    
    def get_controller_color(self, instance_id: int) -> Optional[Tuple[int, int, int]]:
        """
        Get controller color by instance ID.
        
        Args:
            instance_id: The controller instance ID
            
        Returns:
            RGB color tuple if found, None otherwise
        """
        if instance_id in self.controllers:
            return self.controllers[instance_id].color
        return None
    
    def is_controller_active(self, instance_id: int) -> bool:
        """
        Check if a controller is active for navigation.
        
        Args:
            instance_id: The controller instance ID
            
        Returns:
            True if controller is active, False otherwise
        """
        if instance_id not in self.controllers:
            return False
        return self.controllers[instance_id].status == ControllerStatus.ACTIVE
    
    def update_controller_activity(self, instance_id: int) -> None:
        """
        Update controller activity timestamp.
        
        Args:
            instance_id: The controller instance ID
        """
        if instance_id in self.controllers:
            self.controllers[instance_id].last_activity = time.time()
    
    def get_active_controllers(self) -> List[int]:
        """
        Get list of active controller instance IDs.
        
        Returns:
            List of active controller instance IDs
        """
        active_controllers = []
        for instance_id, controller_info in self.controllers.items():
            if controller_info.status == ControllerStatus.ACTIVE:
                active_controllers.append(instance_id)
        return active_controllers
    
    def get_assigned_controllers(self) -> List[int]:
        """
        Get list of assigned controller instance IDs.
        
        Returns:
            List of assigned controller instance IDs
        """
        return list(self.assigned_controllers.keys())
    
    def cleanup_inactive_controllers(self) -> None:
        """
        Clean up controllers that have been inactive for too long.
        """
        current_time = time.time()
        inactive_controllers = []
        
        for instance_id, controller_info in self.controllers.items():
            if (controller_info.last_activity and 
                current_time - controller_info.last_activity > self.ASSIGNMENT_TIMEOUT):
                inactive_controllers.append(instance_id)
        
        for instance_id in inactive_controllers:
            if instance_id in self.assigned_controllers:
                del self.assigned_controllers[instance_id]
            if instance_id in self.controllers:
                self.controllers[instance_id].status = ControllerStatus.CONNECTED
                self.controllers[instance_id].assigned_time = None
                print(f"DEBUG: Controller {self.controllers[instance_id].controller_id} deactivated due to inactivity")
    
    def get_controller_status_summary(self) -> Dict[str, any]:
        """
        Get a summary of all controller statuses.
        
        Returns:
            Dictionary with controller status information
        """
        summary = {
            'total_connected': len(self.controllers),
            'total_assigned': len(self.assigned_controllers),
            'active_controllers': len(self.get_active_controllers()),
            'controllers': {}
        }
        
        for instance_id, controller_info in self.controllers.items():
            summary['controllers'][instance_id] = {
                'controller_id': controller_info.controller_id,
                'status': controller_info.status.value,
                'color': controller_info.color,
                'assigned_time': controller_info.assigned_time,
                'last_activity': controller_info.last_activity
            }
            
        return summary
