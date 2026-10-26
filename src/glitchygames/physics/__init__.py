"""Physics engine for GlitchyGames.

Composable force/behavior accumulator inspired by Nintendo's TotK
2D prototyping engine. Stack behaviors additively on any object
for emergent gameplay.

Usage:
    body = PhysicsBody.platformer(gravity=1200, ground_y=400, body_height=48)
    body.velocity_y = -500  # jump
    body.get_behavior(AccelerationBehavior).target_velocity_x = 200  # run right
    body.tick(dt)
"""

from glitchygames.physics.behaviors import (
    AccelerationBehavior,
    FrictionBehavior,
    GravityBehavior,
    PhysicsBehavior,
)
from glitchygames.physics.body import PhysicsBody
from glitchygames.physics.constraints import (
    BoundsConstraint,
    GroundConstraint,
    PhysicsConstraint,
)
from glitchygames.physics.protocols import (
    HasDirtyFlag,
    HasFacing,
    HasGroundState,
    HasMass,
    HasRect,
    HasVelocity,
)

__all__ = [
    'AccelerationBehavior',
    'BoundsConstraint',
    'FrictionBehavior',
    'GravityBehavior',
    'GroundConstraint',
    'HasDirtyFlag',
    'HasFacing',
    'HasGroundState',
    'HasMass',
    'HasRect',
    'HasVelocity',
    'PhysicsBehavior',
    'PhysicsBody',
    'PhysicsConstraint',
]
