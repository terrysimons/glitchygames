"""Multi-controller system for the Bitmappy editor."""

from __future__ import annotations

from .enhancements import (
    MAX_CONTROLLER_ACTION_HISTORY,
    BitmappyMultiControllerEnhancements,
)
from .error_handling import (
    ErrorInfo,
    ErrorSeverity,
    MultiControllerConfig,
    MultiControllerErrorHandler,
    MultiControllerLogger,
    MultiControllerValidator,
)
from .manager import (
    ControllerInfo,
    ControllerStatus,
    MultiControllerManager,
)
from .modes import (
    ControllerMode,
    ControllerModeState,
    ModePosition,
    ModeSwitcher,
    TriggerDetector,
)
from .performance import (
    CachedPositionManager,
    MemoryManager,
    MultiControllerPerformanceOptimizer,
    OptimizedVisualCollisionManager,
    PerformanceMetrics,
    PerformanceMonitor,
)
from .selection import ControllerSelection

__all__ = [
    'MAX_CONTROLLER_ACTION_HISTORY',
    'BitmappyMultiControllerEnhancements',
    'CachedPositionManager',
    'ControllerInfo',
    'ControllerMode',
    'ControllerModeState',
    'ControllerSelection',
    'ControllerStatus',
    'ErrorInfo',
    'ErrorSeverity',
    'MemoryManager',
    'ModePosition',
    'ModeSwitcher',
    'MultiControllerConfig',
    'MultiControllerErrorHandler',
    'MultiControllerLogger',
    'MultiControllerManager',
    'MultiControllerPerformanceOptimizer',
    'MultiControllerValidator',
    'OptimizedVisualCollisionManager',
    'PerformanceMetrics',
    'PerformanceMonitor',
    'TriggerDetector',
]
