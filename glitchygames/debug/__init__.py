"""Debug overlay: state, protocols and (in later tasks) drawing for engine debugging aids."""

from glitchygames.debug.overlay import DebugOverlay, DebugPanel
from glitchygames.debug.panels import DebugFrameInfo
from glitchygames.debug.protocols import DebugDrawable, HasPhysicsBody, PhysicsState

__all__ = [
    'DebugDrawable',
    'DebugFrameInfo',
    'DebugOverlay',
    'DebugPanel',
    'HasPhysicsBody',
    'PhysicsState',
]
