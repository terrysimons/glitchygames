#!/usr/bin/env python3
"""Tests for onion skinning functionality."""

import math

import pytest

from bitmappy.onion_skinning import OnionSkinningManager, get_onion_skinning_manager
from glitchygames.engine_context import EngineContext


class TestOnionSkinningManager:
    """Test cases for OnionSkinningManager."""

    def test_initialization(self):
        """Test that OnionSkinningManager initializes correctly."""
        manager = OnionSkinningManager()

        assert manager.onion_skinning_enabled == {}
        assert manager.global_onion_skinning_enabled is True
        assert math.isclose(manager.onion_transparency, 0.5)

    def test_toggle_frame_onion_skinning(self):
        """Test toggling onion skinning for a specific frame."""
        manager = OnionSkinningManager()

        # Initially disabled
        assert not manager.is_frame_onion_skinned('animation1', 0)

        # Toggle on
        result = manager.toggle_frame_onion_skinning('animation1', 0)
        assert result is True
        assert manager.is_frame_onion_skinned('animation1', 0)

        # Toggle off
        result = manager.toggle_frame_onion_skinning('animation1', 0)
        assert result is False
        assert not manager.is_frame_onion_skinned('animation1', 0)

    def test_multiple_frames_same_animation(self):
        """Test onion skinning for multiple frames in the same animation."""
        manager = OnionSkinningManager()

        # Enable onion skinning for frames 0 and 2
        manager.toggle_frame_onion_skinning('animation1', 0)
        manager.toggle_frame_onion_skinning('animation1', 2)

        assert manager.is_frame_onion_skinned('animation1', 0)
        assert not manager.is_frame_onion_skinned('animation1', 1)
        assert manager.is_frame_onion_skinned('animation1', 2)

    def test_multiple_animations(self):
        """Test onion skinning across multiple animations."""
        manager = OnionSkinningManager()

        # Enable onion skinning for different animations
        manager.toggle_frame_onion_skinning('animation1', 0)
        manager.toggle_frame_onion_skinning('animation2', 1)

        assert manager.is_frame_onion_skinned('animation1', 0)
        assert manager.is_frame_onion_skinned('animation2', 1)
        assert not manager.is_frame_onion_skinned('animation1', 1)
        assert not manager.is_frame_onion_skinned('animation2', 0)

    def test_get_onion_skinned_frames_old_approach(self):
        """Test the old approach for getting onion skinned frames (deprecated)."""
        manager = OnionSkinningManager()

        # Enable onion skinning for frames 0, 2, and 4
        manager.toggle_frame_onion_skinning('animation1', 0)
        manager.toggle_frame_onion_skinning('animation1', 2)
        manager.toggle_frame_onion_skinning('animation1', 4)

        # Test the old individual frame checking approach
        assert manager.is_frame_onion_skinned('animation1', 0)
        assert not manager.is_frame_onion_skinned('animation1', 1)
        assert manager.is_frame_onion_skinned('animation1', 2)
        assert not manager.is_frame_onion_skinned('animation1', 3)
        assert manager.is_frame_onion_skinned('animation1', 4)

    def test_global_onion_skinning_toggle(self):
        """Test global onion skinning toggle."""
        manager = OnionSkinningManager()

        # Enable a frame
        manager.toggle_frame_onion_skinning('animation1', 0)
        assert manager.is_frame_onion_skinned('animation1', 0)

        # Disable global onion skinning
        manager.toggle_global_onion_skinning()
        assert not manager.global_onion_skinning_enabled
        assert not manager.is_frame_onion_skinned('animation1', 0)

        # Re-enable global onion skinning
        manager.toggle_global_onion_skinning()
        assert manager.global_onion_skinning_enabled
        assert manager.is_frame_onion_skinned('animation1', 0)

    def test_global_onion_skinning_is_reported_on_at_startup_and_follows_its_toggle(self):
        """is_global_onion_skinning_enabled reports the startup True, then each toggle's state.

        Covered on purpose: the suite once reached it only from other files' tests, so this file
        alone left it uncovered (coverage that followed the test order).
        """
        manager = OnionSkinningManager()

        assert manager.is_global_onion_skinning_enabled() is True
        manager.toggle_global_onion_skinning()
        assert manager.is_global_onion_skinning_enabled() is False
        manager.toggle_global_onion_skinning()
        assert manager.is_global_onion_skinning_enabled() is True

    def test_set_transparency(self):
        """Test setting onion skinning transparency."""
        manager = OnionSkinningManager()

        # Test valid transparency values
        manager.set_transparency(0.3)
        assert math.isclose(manager.onion_transparency, 0.3)

        manager.set_transparency(0.8)
        assert math.isclose(manager.onion_transparency, 0.8)

        # Test clamping
        manager.set_transparency(1.5)
        assert math.isclose(manager.onion_transparency, 1.0)

        manager.set_transparency(-0.5)
        assert math.isclose(manager.onion_transparency, 0.0, abs_tol=1e-9)

    def test_clear_animation_onion_skinning(self):
        """Test clearing onion skinning for an animation."""
        manager = OnionSkinningManager()

        # Enable onion skinning for multiple frames
        manager.toggle_frame_onion_skinning('animation1', 0)
        manager.toggle_frame_onion_skinning('animation1', 1)
        manager.toggle_frame_onion_skinning('animation2', 0)

        # Clear animation1
        manager.clear_animation_onion_skinning('animation1')

        assert not manager.is_frame_onion_skinned('animation1', 0)
        assert not manager.is_frame_onion_skinned('animation1', 1)
        assert manager.is_frame_onion_skinned('animation2', 0)  # animation2 should be unaffected

    def test_clearing_an_animation_with_no_onion_state_changes_nothing(self):
        """Clearing an animation that was never onion-skinned is a no-op for every animation.

        Its own branch, covered on purpose: the suite once reached it only through state that
        earlier tests left in the shared manager, so its coverage followed the test order
        (CircleCI's coverage-combine-linux at 99.99% under a rolled order, #257).
        """
        manager = OnionSkinningManager()
        manager.toggle_frame_onion_skinning('animation1', 0)
        before = {name: dict(frames) for name, frames in manager.onion_skinning_enabled.items()}

        manager.clear_animation_onion_skinning('never-skinned')

        assert manager.onion_skinning_enabled == before
        assert 'never-skinned' not in manager.onion_skinning_enabled

    def test_get_animation_onion_state(self):
        """Test getting onion skinning state for an animation."""
        manager = OnionSkinningManager()

        # Enable onion skinning for some frames
        manager.toggle_frame_onion_skinning('animation1', 0)
        manager.toggle_frame_onion_skinning('animation1', 2)

        state = manager.get_animation_onion_state('animation1')
        expected = {0: True, 2: True}
        assert state == expected

    def test_set_animation_onion_state(self):
        """Test setting onion skinning state for an animation."""
        manager = OnionSkinningManager()

        # Set state for animation1
        state = {0: True, 1: False, 2: True}
        manager.set_animation_onion_state('animation1', state)

        assert manager.is_frame_onion_skinned('animation1', 0)
        assert not manager.is_frame_onion_skinned('animation1', 1)
        assert manager.is_frame_onion_skinned('animation1', 2)

    def test_get_onion_skinned_frames_new_approach(self):
        """Test the new get_onion_skinned_frames method that returns all non-current frames."""
        manager = OnionSkinningManager()

        # Test with global onion skinning enabled
        assert manager.global_onion_skinning_enabled is True

        # Should return all frames except current when global is enabled
        onion_frames = manager.get_onion_skinned_frames(
            'animation1',
            1,
            5,
        )  # 5 total frames, current is 1
        expected_frames = {0, 2, 3, 4}  # All frames except 1
        assert onion_frames == expected_frames

        # Test with global onion skinning disabled
        manager.global_onion_skinning_enabled = False
        onion_frames = manager.get_onion_skinned_frames('animation1', 1, 5)
        assert onion_frames == set()  # Should return empty set


class TestOnionSkinningIntegration:
    """Integration tests for onion skinning functionality."""

    def test_global_manager_singleton(self):
        """get_onion_skinning_manager returns the same manager each time within one context."""
        manager1 = get_onion_skinning_manager()
        manager2 = get_onion_skinning_manager()

        assert manager1 is manager2

    def test_manager_state_persistence(self):
        """Test that manager state persists across calls."""
        manager = get_onion_skinning_manager()

        # Enable onion skinning for a frame
        manager.toggle_frame_onion_skinning('test_animation', 0)

        # Get manager again and check state
        manager2 = get_onion_skinning_manager()
        assert manager2.is_frame_onion_skinned('test_animation', 0)

    def test_error_handling(self):
        """Test error handling in onion skinning operations."""
        manager = OnionSkinningManager()

        # Test with invalid animation names
        assert not manager.is_frame_onion_skinned('nonexistent', 0)

        # Test with negative frame indices
        assert not manager.is_frame_onion_skinned('animation1', -1)

        # Test transparency clamping
        manager.set_transparency(2.0)
        assert math.isclose(manager.onion_transparency, 1.0)

        manager.set_transparency(-1.0)
        assert math.isclose(manager.onion_transparency, 0.0, abs_tol=1e-9)


class TestEveryTestGetsAFreshSharedManager:
    """The conftest's autouse ``fresh_onion_skinning_manager`` resets the default context's."""

    def test_the_shared_manager_starts_in_its_startup_state(self):
        """No frame is on, global onion skinning is on and transparency is 0.5, for every test.

        Then it leaves state behind on purpose: any later test on this worker that saw it would
        fail this same check, as the film strip tests once drew the indicator from leftovers.
        """
        manager = get_onion_skinning_manager()

        assert manager.onion_skinning_enabled == {}
        assert manager.global_onion_skinning_enabled is True
        assert math.isclose(manager.onion_transparency, 0.5)
        manager.toggle_frame_onion_skinning('left_behind', 0)
        manager.toggle_global_onion_skinning()


def check_onion_skinning_manager(*, first: EngineContext, second: EngineContext) -> None:
    """Each context keeps its own onion skinning, and the default context sees neither's.

    Args:
        first: One context.
        second: Another.

    """
    with first.active():
        get_onion_skinning_manager().toggle_frame_onion_skinning('walk', 0)
    with second.active():
        get_onion_skinning_manager().toggle_frame_onion_skinning('walk', 1)
        get_onion_skinning_manager().toggle_global_onion_skinning()

    with first.active():
        first_manager = get_onion_skinning_manager()
        assert first_manager.is_frame_onion_skinned('walk', 0)
        assert not first_manager.onion_skinning_enabled['walk'].get(1, False)
        assert first_manager.is_global_onion_skinning_enabled()
    with second.active():
        second_manager = get_onion_skinning_manager()
        assert second_manager.onion_skinning_enabled['walk'] == {1: True}
        assert not second_manager.is_global_onion_skinning_enabled()
    assert first_manager is not second_manager
    assert get_onion_skinning_manager().onion_skinning_enabled == {}


# Every Bitmappy slot, with the check that proves its values never leak between contexts: the
# member's own isolation checks, which tests/test_engine_context_source_guards.py finds in this
# file by name (the engine's tests never import a member)
MEMBER_ISOLATION_CHECKS = {
    'bitmappy.onion_skinning.manager': check_onion_skinning_manager,
}


@pytest.mark.parametrize('slot_name', sorted(MEMBER_ISOLATION_CHECKS))
def test_no_bitmappy_slot_value_leaks_between_two_contexts(slot_name):
    """Two contexts beside the default one: each keeps its own value of the slot."""
    MEMBER_ISOLATION_CHECKS[slot_name](
        first=EngineContext(name='first'), second=EngineContext(name='second')
    )


if __name__ == '__main__':
    pytest.main([__file__])
