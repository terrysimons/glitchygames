"""Tests for PhysicsBody, behaviors, constraints, and protocols."""

import pytest

from glitchygames.physics import (
    AccelerationBehavior,
    BoundsConstraint,
    FrictionBehavior,
    GravityBehavior,
    GroundConstraint,
    HasFacing,
    HasGroundState,
    HasVelocity,
    PhysicsBody,
)

# --- PhysicsBody core ---


class TestPhysicsBodyTick:
    """Core physics integration: force → acceleration → velocity → position."""

    def test_no_behaviors_no_movement(self):
        """Body with no behaviors stays still."""
        body = PhysicsBody(world_x=100.0, world_y=200.0)
        body.tick(dt=1.0 / 60.0)
        assert body.world_x == pytest.approx(100.0)
        assert body.world_y == pytest.approx(200.0)

    def test_velocity_integrates_position(self):
        """Velocity moves the body each tick."""
        body = PhysicsBody(world_x=0.0, world_y=0.0)
        body.velocity_x = 60.0  # 60 pixels/sec
        body.tick(dt=1.0)  # 1 second
        assert body.world_x == pytest.approx(60.0)

    def test_facing_direction_from_velocity(self):
        """Facing direction tracks velocity sign."""
        body = PhysicsBody()
        body.velocity_x = 100.0
        body.tick(dt=0.016)
        assert body.facing_right is True

        body.velocity_x = -100.0
        body.tick(dt=0.016)
        assert body.facing_right is False

    def test_zero_mass_no_crash(self):
        """Zero-mass body doesn't crash (no division by zero)."""
        body = PhysicsBody(mass=0.0)
        body.add_behavior(GravityBehavior())
        body.tick(dt=0.016)  # Should not raise


# --- GravityBehavior ---


class TestGravityBehavior:
    """Downward force with terminal velocity cap."""

    def test_gravity_accelerates_downward(self):
        """Gravity increases downward velocity."""
        body = PhysicsBody()
        body.add_behavior(GravityBehavior(strength=1200.0))
        body.tick(dt=1.0 / 60.0)
        assert body.velocity_y > 0.0  # Positive Y = down in pygame

    def test_terminal_velocity_cap(self):
        """Velocity doesn't exceed terminal velocity."""
        body = PhysicsBody()
        body.add_behavior(
            GravityBehavior(
                strength=1200.0,
                terminal_velocity=800.0,
            )
        )
        # Run for many frames to reach terminal velocity
        for _ in range(600):
            body.tick(dt=1.0 / 60.0)
        assert body.velocity_y <= 800.0 + 0.1  # Small tolerance

    def test_no_terminal_velocity(self):
        """With terminal_velocity=0, speed is uncapped."""
        body = PhysicsBody()
        body.add_behavior(
            GravityBehavior(
                strength=1200.0,
                terminal_velocity=0.0,
            )
        )
        for _ in range(600):
            body.tick(dt=1.0 / 60.0)
        assert body.velocity_y > 800.0  # Exceeds what would be the cap


# --- AccelerationBehavior ---


class TestAccelerationBehavior:
    """Smooth horizontal acceleration/deceleration."""

    def test_accelerates_to_target(self):
        """Velocity ramps toward target over time."""
        body = PhysicsBody()
        accel = AccelerationBehavior(
            acceleration=1600.0,
            deceleration=1200.0,
        )
        accel.target_velocity_x = 200.0
        body.add_behavior(accel)

        for _ in range(60):
            body.tick(dt=1.0 / 60.0)
        assert body.velocity_x == pytest.approx(200.0, abs=1.0)

    def test_decelerates_to_zero(self):
        """Velocity decelerates to zero when target is zero."""
        body = PhysicsBody()
        body.velocity_x = 200.0
        accel = AccelerationBehavior(
            acceleration=1600.0,
            deceleration=1200.0,
        )
        accel.target_velocity_x = 0.0
        body.add_behavior(accel)

        for _ in range(60):
            body.tick(dt=1.0 / 60.0)
        assert body.velocity_x == pytest.approx(0.0, abs=1.0)

    def test_direction_change(self):
        """Can accelerate in the opposite direction."""
        body = PhysicsBody()
        body.velocity_x = 200.0
        accel = AccelerationBehavior(acceleration=1600.0)
        accel.target_velocity_x = -200.0
        body.add_behavior(accel)

        for _ in range(120):
            body.tick(dt=1.0 / 60.0)
        assert body.velocity_x < 0.0


# --- FrictionBehavior ---


class TestFrictionBehavior:
    """Velocity damping."""

    def test_friction_slows_down(self):
        """Friction reduces velocity over time."""
        body = PhysicsBody()
        body.velocity_x = 100.0
        body.velocity_y = 100.0
        body.add_behavior(FrictionBehavior(coefficient=0.1))

        body.tick(dt=0.016)
        assert body.velocity_x < 100.0
        assert body.velocity_y < 100.0

    def test_zero_friction_no_change(self):
        """Zero friction preserves velocity."""
        body = PhysicsBody()
        body.velocity_x = 100.0
        body.add_behavior(FrictionBehavior(coefficient=0.0))

        body.tick(dt=0.016)
        assert body.velocity_x == pytest.approx(100.0, abs=0.01)


# --- BoundsConstraint ---


class TestBoundsConstraint:
    """World boundary clamping."""

    def test_clamp_left(self):
        """Position doesn't go below min_x."""
        body = PhysicsBody(world_x=10.0)
        body.velocity_x = -1000.0
        body.add_constraint(BoundsConstraint(min_x=0.0))
        body.tick(dt=1.0)
        assert body.world_x == 0.0
        assert body.velocity_x == 0.0

    def test_clamp_bottom(self):
        """Position doesn't go below max_y."""
        body = PhysicsBody(world_y=100.0)
        body.velocity_y = 1000.0
        body.add_constraint(BoundsConstraint(max_y=500.0))
        body.tick(dt=1.0)
        assert body.world_y == 500.0
        assert body.velocity_y == 0.0

    def test_no_clamp_when_in_bounds(self):
        """Constraint doesn't affect position when within bounds."""
        body = PhysicsBody(world_x=50.0)
        body.velocity_x = 10.0
        body.add_constraint(BoundsConstraint(min_x=0.0, max_x=100.0))
        body.tick(dt=1.0)
        assert body.world_x == pytest.approx(60.0)


# --- GroundConstraint ---


class TestGroundConstraint:
    """Ground contact detection and snapping."""

    def test_landing_sets_on_ground(self):
        """Falling body snaps to ground and sets on_ground."""
        body = PhysicsBody(world_y=390.0)
        body.velocity_y = 100.0
        body.add_constraint(GroundConstraint(ground_y=400.0, body_height=48.0))
        body.tick(dt=1.0)  # Falls well past ground
        assert body.on_ground is True
        assert body.world_y == pytest.approx(352.0)  # ground_y - body_height
        assert body.velocity_y == 0.0

    def test_airborne_clears_on_ground(self):
        """Body above ground has on_ground=False."""
        body = PhysicsBody(world_y=100.0)
        body.on_ground = True
        body.add_constraint(GroundConstraint(ground_y=400.0, body_height=48.0))
        body.tick(dt=0.016)
        assert body.on_ground is False

    def test_upward_movement_doesnt_snap(self):
        """Body moving upward through ground level isn't snapped."""
        body = PhysicsBody(world_y=360.0)
        body.velocity_y = -500.0  # Moving up
        body.add_constraint(GroundConstraint(ground_y=400.0, body_height=48.0))
        body.tick(dt=0.016)
        # Should NOT snap to ground when moving up
        assert body.velocity_y < 0.0


# --- Presets ---


class TestPresets:
    """Convenience preset factory methods."""

    def test_platformer_has_gravity(self):
        """Platformer preset includes gravity."""
        body = PhysicsBody.platformer()
        assert body.get_behavior(GravityBehavior) is not None

    def test_platformer_has_acceleration(self):
        """Platformer preset includes acceleration."""
        body = PhysicsBody.platformer()
        assert body.get_behavior(AccelerationBehavior) is not None

    def test_platformer_has_bounds(self):
        """Platformer preset includes left boundary."""
        body = PhysicsBody.platformer()
        bounds = [
            constraint
            for constraint in body.constraints
            if isinstance(constraint, BoundsConstraint)
        ]
        assert len(bounds) == 1

    def test_platformer_has_ground(self):
        """Platformer preset includes ground constraint."""
        body = PhysicsBody.platformer()
        ground = [
            constraint
            for constraint in body.constraints
            if isinstance(constraint, GroundConstraint)
        ]
        assert len(ground) == 1

    def test_top_down_has_friction(self):
        """Top-down preset includes friction."""
        body = PhysicsBody.top_down()
        assert body.get_behavior(FrictionBehavior) is not None

    def test_static_has_no_behaviors(self):
        """Static preset has no behaviors or constraints."""
        body = PhysicsBody.static(world_x=50.0, world_y=100.0)
        assert len(body.behaviors) == 0
        assert len(body.constraints) == 0
        assert body.world_x == 50.0


# --- Protocols ---


class TestProtocols:
    """Verify PhysicsBody satisfies pairwise protocols."""

    def test_has_velocity(self):
        """PhysicsBody satisfies HasVelocity."""
        body = PhysicsBody()
        assert isinstance(body, HasVelocity)

    def test_has_ground_state(self):
        """PhysicsBody satisfies HasGroundState."""
        body = PhysicsBody()
        assert isinstance(body, HasGroundState)

    def test_has_facing(self):
        """PhysicsBody satisfies HasFacing."""
        body = PhysicsBody()
        assert isinstance(body, HasFacing)


# --- Composability ---


class TestComposability:
    """Multiple behaviors compose correctly."""

    def test_gravity_plus_acceleration(self):
        """Platformer: gravity pulls down while acceleration moves right."""
        body = PhysicsBody.platformer(
            gravity=1200.0,
            ground_y=1000.0,
            body_height=48.0,
        )
        accel = body.get_behavior(AccelerationBehavior)
        accel.target_velocity_x = 200.0

        for _ in range(60):
            body.tick(dt=1.0 / 60.0)

        # Should have moved right and fallen
        assert body.world_x > 0.0
        assert body.world_y > 0.0
        assert body.velocity_x > 0.0
        assert body.velocity_y > 0.0

    def test_platformer_lands_on_ground(self):
        """Platformer falls and lands on ground."""
        body = PhysicsBody.platformer(
            world_y=300.0,
            gravity=1200.0,
            ground_y=400.0,
            body_height=48.0,
        )
        for _ in range(120):
            body.tick(dt=1.0 / 60.0)

        assert body.on_ground is True
        assert body.world_y == pytest.approx(352.0)  # 400 - 48

    def test_platformer_jump(self):
        """Platformer can jump (negative velocity) and land again."""
        body = PhysicsBody.platformer(
            world_y=352.0,
            gravity=1200.0,
            ground_y=400.0,
            body_height=48.0,
        )
        # Start on ground
        body.tick(dt=0.016)
        assert body.on_ground is True

        # Jump
        body.velocity_y = -500.0
        body.on_ground = False

        # Run physics for ~1 second
        for _ in range(60):
            body.tick(dt=1.0 / 60.0)

        # Should have landed again
        assert body.on_ground is True
        assert body.world_y == pytest.approx(352.0)

    def test_add_remove_behavior(self):
        """Behaviors can be added and removed at runtime."""
        body = PhysicsBody()
        gravity = GravityBehavior()
        body.add_behavior(gravity)
        assert len(body.behaviors) == 1

        body.remove_behavior(gravity)
        assert len(body.behaviors) == 0
