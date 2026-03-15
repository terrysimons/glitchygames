"""Multi-Controller Manager for Bitmappy Tool.

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

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Self

import pygame

LOG = logging.getLogger("game.tools.multi_controller_manager")


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
    assigned_time: float | None = None
    last_activity: float | None = None
    color: tuple[int, int, int] = (255, 0, 0)  # Default red


class MultiControllerManager:
    """Core multi-controller system for bitmappy tool.

    Manages up to 4 simultaneous controllers with automatic assignment,
    reconnection handling, and status tracking.

    This is a singleton class to ensure consistent color assignment across the application.
    """

    # Controller color scheme
    CONTROLLER_COLORS: ClassVar[list[tuple[int, int, int]]] = [
        (255, 0, 0),  # Controller 0: Red
        (0, 255, 0),  # Controller 1: Green
        (0, 0, 255),  # Controller 2: Blue
        (255, 255, 0),  # Controller 3: Yellow
    ]

    MAX_CONTROLLERS = 4
    ASSIGNMENT_TIMEOUT = 5.0  # seconds

    _instance = None
    _initialized = False

    def __new__(cls) -> Self:
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the multi-controller manager (only once)."""
        if self._initialized:
            return

        self.controllers: dict[int, ControllerInfo] = {}
        self.assigned_controllers: dict[int, int] = {}  # instance_id -> controller_id
        self.next_controller_id = 0
        self.next_color_index = 0  # Track color assignment order
        self.last_scan_time = 0
        self.scan_interval = 1.0  # seconds
        self._initialized = True

        LOG.debug("MultiControllerManager singleton initialized")

    @classmethod
    def get_instance(cls) -> Self:
        """Get the singleton instance of MultiControllerManager.

        Returns:
            Self: The instance.

        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def scan_for_controllers(self) -> list[int]:
        """Scan for connected controllers and return list of instance IDs.

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
        # Don't assign color here - it will be assigned when controller is activated
        color = (128, 128, 128)  # Default gray color until activated

        self.controllers[instance_id] = ControllerInfo(
            controller_id=controller_id,
            instance_id=instance_id,
            status=ControllerStatus.CONNECTED,
            color=color,
        )

        LOG.debug(
            "Controller %s connected (instance_id=%s, color=%s)",
            controller_id,
            instance_id,
            color,
        )

    def _get_next_controller_id(self) -> int:
        """Get the next available controller ID.

        Returns:
            int: The next controller id.

        """
        controller_id = self.next_controller_id
        self.next_controller_id = (self.next_controller_id + 1) % self.MAX_CONTROLLERS
        return controller_id

    def _handle_controller_disconnect(self, instance_id: int) -> None:
        """Handle controller disconnection."""
        if instance_id in self.controllers:
            controller_info = self.controllers[instance_id]
            LOG.debug(
                "Controller %s disconnected (instance_id=%s)",
                controller_info.controller_id,
                instance_id,
            )

            # Remove from assigned controllers
            if instance_id in self.assigned_controllers:
                del self.assigned_controllers[instance_id]

            del self.controllers[instance_id]

    def assign_color_to_controller(self, controller_id: int) -> None:
        """Assign a color to a controller based on activation order."""
        LOG.debug("assign_color_to_controller called with controller_id=%s", controller_id)
        LOG.debug("Available controllers: %s", list(self.controllers.keys()))
        LOG.debug("Current next_color_index: %s", self.next_color_index)

        # Find the controller by controller_id and assign the next color
        for instance_id, info in self.controllers.items():
            LOG.debug(
                "Checking instance_id=%s, info.controller_id=%s",
                instance_id,
                info.controller_id,
            )
            if info.controller_id == controller_id:
                color = self.CONTROLLER_COLORS[self.next_color_index % len(self.CONTROLLER_COLORS)]
                old_color = info.color
                info.color = color
                self.next_color_index += 1
                LOG.debug(
                    "Assigned color %s to controller %s (was %s)",
                    color,
                    controller_id,
                    old_color,
                )
                LOG.debug("next_color_index is now %s", self.next_color_index)
                break
        else:
            LOG.debug(
                "Controller %s not found in controllers: %s",
                controller_id,
                list(self.controllers.keys()),
            )
            LOG.debug(
                "Available controller_ids: %s",
                [info.controller_id for info in self.controllers.values()],
            )

    def assign_controller(self, instance_id: int) -> int | None:
        """Assign a controller on first button press.

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

        LOG.debug(
            "Controller %s assigned (instance_id=%s)",
            controller_info.controller_id,
            instance_id,
        )
        return controller_info.controller_id

    def activate_controller(self, instance_id: int) -> bool:
        """Activate a controller for navigation.

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

    def get_controller_info(self, instance_id: int) -> ControllerInfo | None:
        """Get controller information by instance ID.

        Args:
            instance_id: The controller instance ID

        Returns:
            ControllerInfo if found, None otherwise

        """
        return self.controllers.get(instance_id)

    def get_controller_id(self, instance_id: int) -> int | None:
        """Get controller ID by instance ID.

        Args:
            instance_id: The controller instance ID

        Returns:
            Controller ID if assigned, None otherwise

        """
        return self.assigned_controllers.get(instance_id)

    def get_controller_color(self, instance_id: int) -> tuple[int, int, int] | None:
        """Get controller color by instance ID.

        Args:
            instance_id: The controller instance ID

        Returns:
            RGB color tuple if found, None otherwise

        """
        if instance_id in self.controllers:
            return self.controllers[instance_id].color
        return None

    def is_controller_active(self, instance_id: int) -> bool:
        """Check if a controller is active for navigation.

        Args:
            instance_id: The controller instance ID

        Returns:
            True if controller is active, False otherwise

        """
        if instance_id not in self.controllers:
            return False
        return self.controllers[instance_id].status == ControllerStatus.ACTIVE

    def update_controller_activity(self, instance_id: int) -> None:
        """Update controller activity timestamp.

        Args:
            instance_id: The controller instance ID

        """
        if instance_id in self.controllers:
            self.controllers[instance_id].last_activity = time.time()

    def get_active_controllers(self) -> list[int]:
        """Get list of active controller instance IDs.

        Returns:
            List of active controller instance IDs

        """
        active_controllers = []
        for instance_id, controller_info in self.controllers.items():
            if controller_info.status == ControllerStatus.ACTIVE:
                active_controllers.append(instance_id)
        return active_controllers

    def get_assigned_controllers(self) -> list[int]:
        """Get list of assigned controller instance IDs.

        Returns:
            List of assigned controller instance IDs

        """
        return list(self.assigned_controllers.keys())

    def cleanup_inactive_controllers(self) -> None:
        """Clean up controllers that have been inactive for too long."""
        current_time = time.time()
        inactive_controllers = []

        for instance_id, controller_info in self.controllers.items():
            if (
                controller_info.last_activity
                and current_time - controller_info.last_activity > self.ASSIGNMENT_TIMEOUT
            ):
                inactive_controllers.append(instance_id)

        for instance_id in inactive_controllers:
            if instance_id in self.assigned_controllers:
                del self.assigned_controllers[instance_id]
            if instance_id in self.controllers:
                self.controllers[instance_id].status = ControllerStatus.CONNECTED
                self.controllers[instance_id].assigned_time = None
                LOG.debug(
                    "Controller %s deactivated due to inactivity",
                    self.controllers[instance_id].controller_id,
                )

    def get_controller_status_summary(self) -> dict[str, Any]:
        """Get a summary of all controller statuses.

        Returns:
            Dictionary with controller status information

        """
        summary = {
            "total_connected": len(self.controllers),
            "total_assigned": len(self.assigned_controllers),
            "active_controllers": len(self.get_active_controllers()),
            "controllers": {},
        }

        for instance_id, controller_info in self.controllers.items():
            summary["controllers"][instance_id] = {
                "controller_id": controller_info.controller_id,
                "status": controller_info.status.value,
                "color": controller_info.color,
                "assigned_time": controller_info.assigned_time,
                "last_activity": controller_info.last_activity,
            }

        return summary
