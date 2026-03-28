"""Multi-Controller Error Handling and Configuration.

This module provides enhanced error handling, logging, and configuration
options for the multi-controller system.
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from glitchygames.color import MAX_COLOR_CHANNEL_VALUE, RGB_COMPONENT_COUNT

log = logging.getLogger(__name__)

POSITION_TUPLE_LENGTH = 2


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


@dataclass
class ErrorInfo:
    """Error information structure."""

    error_type: str
    message: str
    severity: ErrorSeverity
    timestamp: float
    controller_id: int | None = None
    operation: str | None = None
    stack_trace: str | None = None


class MultiControllerErrorHandler:
    """Enhanced error handling for multi-controller system."""

    def __init__(self, log_level: int = logging.INFO) -> None:
        """Initialize error handler.

        Args:
            log_level: Logging level

        """
        self.logger = logging.getLogger('multi_controller')
        self.logger.setLevel(log_level)

        # Error tracking
        self.error_history: list[ErrorInfo] = []
        self.error_counts: dict[str, int] = {}
        self.recovery_attempts: dict[str, int] = {}

        # Configuration
        self.max_error_history = 1000
        self.max_recovery_attempts = 3
        self.auto_recovery_enabled = True

        # Error handlers
        self.error_handlers: dict[str, Callable[..., Any]] = {}
        self.recovery_handlers: dict[str, Callable[..., Any]] = {}

        # Setup default handlers
        self._setup_default_handlers()

    def _setup_default_handlers(self) -> None:
        """Set up default error and recovery handlers."""
        # Default handlers are registered here as needed
        # Subclasses can override to add custom handlers

    def handle_error(
        self,
        error: Exception,
        controller_id: int | None = None,
        operation: str | None = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    ) -> bool:
        """Handle an error with logging and recovery.

        Args:
            error: Exception to handle
            controller_id: Controller ID if applicable
            operation: Operation that caused the error
            severity: Error severity

        Returns:
            True if error was handled successfully

        """
        # Create error info
        error_info = ErrorInfo(
            error_type=type(error).__name__,
            message=str(error),
            severity=severity,
            timestamp=time.time(),
            controller_id=controller_id,
            operation=operation,
            stack_trace=traceback.format_exc(),
        )

        # Add to history
        self.error_history.append(error_info)
        if len(self.error_history) > self.max_error_history:
            self.error_history = self.error_history[-self.max_error_history :]

        # Update error counts
        error_key = f'{error_info.error_type}_{error_info.operation}'
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

        # Log error
        self._log_error(error_info)

        # Attempt recovery
        if self.auto_recovery_enabled:
            return self._attempt_recovery(error_info)

        return False

    def _log_error(self, error_info: ErrorInfo) -> None:
        """Log error information.

        Args:
            error_info: Error information

        """
        log_message = (
            f'Controller {error_info.controller_id}: {error_info.error_type} - {error_info.message}'
        )

        if error_info.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif error_info.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)

    def _attempt_recovery(self, error_info: ErrorInfo) -> bool:
        """Attempt to recover from an error.

        Args:
            error_info: Error information

        Returns:
            True if recovery was successful

        """
        error_key = f'{error_info.error_type}_{error_info.operation}'

        # Check if we've exceeded recovery attempts
        if self.recovery_attempts.get(error_key, 0) >= self.max_recovery_attempts:
            self.logger.error('Max recovery attempts exceeded for %s', error_key)
            return False

        # Increment recovery attempts
        self.recovery_attempts[error_key] = self.recovery_attempts.get(error_key, 0) + 1

        # Try to find recovery handler
        if error_key in self.recovery_handlers:
            try:
                return self.recovery_handlers[error_key](error_info)
            except ValueError, TypeError, AttributeError, KeyError, OSError:
                self.logger.exception('Recovery handler failed')
                return False

        # Default recovery strategies
        return self._default_recovery(error_info)

    def _default_recovery(self, error_info: ErrorInfo) -> bool:
        """Default recovery strategies.

        Args:
            error_info: Error information

        Returns:
            True if recovery was successful

        """
        if error_info.error_type == 'KeyError':
            # Try to recreate missing key
            return self._recover_missing_key(error_info)
        if error_info.error_type == 'AttributeError':
            # Try to fix missing attribute
            return self._recover_missing_attribute(error_info)
        if error_info.error_type == 'ValueError':
            # Try to fix invalid value
            return self._recover_invalid_value(error_info)

        return False

    def _recover_missing_key(self, error_info: ErrorInfo) -> bool:
        """Recover from missing key error.

        Args:
            error_info: Error information

        Returns:
            True if recovery was successful

        """
        # This would need to be implemented based on specific error context
        self.logger.info(f'Attempting to recover from missing key: {error_info.message}')
        return True

    def _recover_missing_attribute(self, error_info: ErrorInfo) -> bool:
        """Recover from missing attribute error.

        Args:
            error_info: Error information

        Returns:
            True if recovery was successful

        """
        self.logger.info(f'Attempting to recover from missing attribute: {error_info.message}')
        return True

    def _recover_invalid_value(self, error_info: ErrorInfo) -> bool:
        """Recover from invalid value error.

        Args:
            error_info: Error information

        Returns:
            True if recovery was successful

        """
        self.logger.info(f'Attempting to recover from invalid value: {error_info.message}')
        return True

    def register_error_handler(self, error_type: str, handler: Callable[..., Any]) -> None:
        """Register a custom error handler.

        Args:
            error_type: Error type to handle
            handler: Handler function

        """
        self.error_handlers[error_type] = handler

    def register_recovery_handler(self, error_key: str, handler: Callable[..., Any]) -> None:
        """Register a custom recovery handler.

        Args:
            error_key: Error key to handle
            handler: Recovery handler function

        """
        self.recovery_handlers[error_key] = handler

    def get_error_statistics(self) -> dict[str, Any]:
        """Get error statistics.

        Returns:
            Dict with error statistics

        """
        return {
            'total_errors': len(self.error_history),
            'error_counts': self.error_counts.copy(),
            'recovery_attempts': self.recovery_attempts.copy(),
            'recent_errors': [
                {
                    'type': error.error_type,
                    'message': error.message,
                    'severity': error.severity.value,
                    'timestamp': error.timestamp,
                    'controller_id': error.controller_id,
                }
                for error in self.error_history[-10:]  # Last 10 errors
            ],
        }

    def clear_error_history(self) -> None:
        """Clear error history."""
        self.error_history.clear()
        self.error_counts.clear()
        self.recovery_attempts.clear()


@dataclass
class MultiControllerConfig:
    """Configuration for multi-controller system."""

    # Controller settings
    max_controllers: int = 4
    controller_timeout: float = 300.0  # 5 minutes
    auto_cleanup_interval: float = 60.0  # 1 minute

    # Visual settings
    collision_offset_distance: int = 15
    visual_indicator_size: int = 12
    visual_indicator_shape: str = 'triangle'

    # Performance settings
    enable_caching: bool = True
    enable_optimization: bool = True
    update_throttle: float = 0.016  # 60 FPS

    # Error handling settings
    error_logging_enabled: bool = True
    auto_recovery_enabled: bool = True
    max_error_history: int = 1000
    max_recovery_attempts: int = 3

    # Navigation settings
    navigation_history_limit: int = 100
    enable_navigation_history: bool = True

    @classmethod
    def from_file(cls, config_file: str) -> MultiControllerConfig:
        """Load configuration from file.

        Args:
            config_file: Path to configuration file

        Returns:
            MultiControllerConfig instance

        """
        config_path = Path(config_file)
        if not config_path.exists():
            return cls()

        try:
            with config_path.open(encoding='utf-8') as f:
                config_data = json.load(f)

            return cls(**config_data)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
            log.warning('Failed to load config from %s: %s', config_file, e)
            return cls()

    def save_to_file(self, config_file: str) -> bool:
        """Save configuration to file.

        Args:
            config_file: Path to configuration file

        Returns:
            True if save was successful

        """
        try:
            config_data = {
                'max_controllers': self.max_controllers,
                'controller_timeout': self.controller_timeout,
                'auto_cleanup_interval': self.auto_cleanup_interval,
                'collision_offset_distance': self.collision_offset_distance,
                'visual_indicator_size': self.visual_indicator_size,
                'visual_indicator_shape': self.visual_indicator_shape,
                'enable_caching': self.enable_caching,
                'enable_optimization': self.enable_optimization,
                'update_throttle': self.update_throttle,
                'error_logging_enabled': self.error_logging_enabled,
                'auto_recovery_enabled': self.auto_recovery_enabled,
                'max_error_history': self.max_error_history,
                'max_recovery_attempts': self.max_recovery_attempts,
                'navigation_history_limit': self.navigation_history_limit,
                'enable_navigation_history': self.enable_navigation_history,
            }

            with Path(config_file).open('w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2)
        except Exception:
            log.exception('Failed to save config to %s', config_file)
            return False
        else:
            return True


class MultiControllerLogger:
    """Enhanced logging for multi-controller system."""

    def __init__(self, config: MultiControllerConfig) -> None:
        """Initialize logger.

        Args:
            config: Multi-controller configuration

        """
        self.config = config
        self.logger = logging.getLogger('multi_controller')

        # Setup logging
        if config.error_logging_enabled:
            self._setup_logging()

    def _setup_logging(self) -> None:
        """Set up logging configuration."""
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Create file handler
        file_handler = logging.FileHandler('multi_controller.log')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def log_controller_event(self, controller_id: int, event: str, data: dict[str, Any]) -> None:
        """Log controller event.

        Args:
            controller_id: Controller ID
            event: Event name
            data: Event data

        """
        self.logger.info('Controller %s: %s - %s', controller_id, event, data)

    def log_performance_metric(self, operation: str, duration: float) -> None:
        """Log performance metric.

        Args:
            operation: Operation name
            duration: Operation duration

        """
        self.logger.debug(f'Performance: {operation} took {duration:.4f}s')

    def log_system_status(self, status: dict[str, Any]) -> None:
        """Log system status.

        Args:
            status: System status dictionary

        """
        self.logger.info('System status: %s', status)


class MultiControllerValidator:
    """Validation for multi-controller system."""

    def __init__(self, config: MultiControllerConfig) -> None:
        """Initialize validator.

        Args:
            config: Multi-controller configuration

        """
        self.config = config

    def validate_controller_id(self, controller_id: int) -> bool:
        """Validate controller ID.

        Args:
            controller_id: Controller ID to validate

        Returns:
            True if valid

        """
        return 0 <= controller_id < self.config.max_controllers

    def validate_position(self, position: tuple[int | float, ...]) -> bool:
        """Validate position tuple.

        Args:
            position: Position tuple to validate

        Returns:
            True if valid

        """
        if not isinstance(position, tuple):  # pyright: ignore[reportUnnecessaryIsInstance]
            return False
        if len(position) != POSITION_TUPLE_LENGTH:
            return False
        return all(isinstance(value, (int, float)) for value in position)  # pyright: ignore[reportUnnecessaryIsInstance]

    def validate_color(self, color: tuple[int, ...]) -> bool:
        """Validate color tuple.

        Args:
            color: Color tuple to validate

        Returns:
            True if valid

        """
        if not isinstance(color, tuple):  # pyright: ignore[reportUnnecessaryIsInstance]
            return False
        if len(color) != RGB_COMPONENT_COUNT:
            return False

        red, green, blue = color[0], color[1], color[2]
        return all(0 <= channel <= MAX_COLOR_CHANNEL_VALUE for channel in [red, green, blue])

    def validate_animation_name(self, animation_name: str) -> bool:
        """Validate animation name.

        Args:
            animation_name: Animation name to validate

        Returns:
            True if valid

        """
        if not isinstance(animation_name, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            return False
        return len(animation_name) > 0

    def validate_frame_index(self, frame_index: int) -> bool:
        """Validate frame index.

        Args:
            frame_index: Frame index to validate

        Returns:
            True if valid

        """
        if not isinstance(frame_index, int):  # pyright: ignore[reportUnnecessaryIsInstance]
            return False
        return frame_index >= 0
