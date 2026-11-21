#!/usr/bin/env python3
"""Tests for onion skinning functionality."""

import ast
import math
from pathlib import Path
from typing import TypeIs

import pytest

from bitmappy.onion_skinning import OnionSkinningManager, get_onion_skinning_manager


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
        """Test that get_onion_skinning_manager returns a singleton."""
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
    """The conftest's autouse ``fresh_onion_skinning_manager`` resets the shared manager."""

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


SHARED_MANAGER_NAME = 'onion_skinning_manager'
BITMAPPY_ROOT = Path(__file__).resolve().parent.parent
# The manager's own module defines it and its getter returns it (the conftest's patch names it as a
# string, which the scan does not see)
NAME_HOLDERS_ALLOWED = {'src/bitmappy/onion_skinning.py'}


def names_holding_the_shared_manager(*, source: str) -> list[int]:
    """Return the lines that import, read or rebind ``onion_skinning_manager`` by name.

    Code must reach the shared manager only through ``get_onion_skinning_manager()`` at use time:
    a name imported or copied at import time would keep the old instance, which the conftest's
    reset (a patch of the module attribute) cannot reach.

    Returns:
        Each offending line, in order.

    """
    return sorted(node.lineno for node in ast.walk(ast.parse(source)) if holds_the_name(node))


def holds_the_name(node: ast.AST) -> TypeIs[ast.ImportFrom | ast.Name | ast.Attribute]:
    """Tell whether a node imports, reads or binds ``onion_skinning_manager`` by name.

    Returns:
        True when it does.

    """
    match node:
        case ast.ImportFrom(names=names):
            return any(alias.name == SHARED_MANAGER_NAME for alias in names)
        case ast.Name(id=name) | ast.Attribute(attr=name):
            return name == SHARED_MANAGER_NAME
        case _:
            return False


class TestNothingHoldsTheSharedManagerByName:
    """Bitmappy's source and tests reach the shared manager only through its getter."""

    def test_no_bitmappy_file_holds_the_shared_manager_by_name(self):
        """Every Bitmappy source and test file, except the manager's own module, is clean."""
        files = sorted(BITMAPPY_ROOT.glob('src/bitmappy/**/*.py')) + sorted(
            BITMAPPY_ROOT.glob('tests/**/*.py')
        )
        findings = [
            f'{path.relative_to(BITMAPPY_ROOT).as_posix()}:{line}'
            for path in files
            if path.relative_to(BITMAPPY_ROOT).as_posix() not in NAME_HOLDERS_ALLOWED
            for line in names_holding_the_shared_manager(source=path.read_text(encoding='utf-8'))
        ]

        assert len(files) > 50  # not a vacuous pass: the scan reads the member's files
        assert findings == []

    def test_every_way_of_holding_it_is_found(self):
        """A by-name import (absolute or relative), an attribute read and a rebinding are found."""
        source = (
            'from bitmappy.onion_skinning import onion_skinning_manager\n'  # line 1
            'from .onion_skinning import onion_skinning_manager as manager\n'  # line 2
            'MANAGER = onion_skinning.onion_skinning_manager\n'  # line 3
            'onion_skinning_manager = None\n'  # line 4
            'manager = get_onion_skinning_manager()\n'  # the getter: not reported
        )

        assert names_holding_the_shared_manager(source=source) == [1, 2, 3, 4]


if __name__ == '__main__':
    pytest.main([__file__])
