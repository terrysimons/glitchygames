"""Tests for SpacebarMixin single-shot spacebar press/release pattern."""

import sys
from pathlib import Path

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.scenes.singleshot_spacebar_mixin import SpacebarMixin


class MockBaseClass:
    """Mock base class that provides on_key_down_event and on_key_up_event methods."""

    def __init__(self):
        """Initialize tracking lists for event calls forwarded from SpacebarMixin."""
        self.key_down_events = []
        self.key_up_events = []

    def on_key_down_event(self, event):
        """Track key down events that are forwarded by the mixin.

        Args:
            event: The key down event.

        """
        self.key_down_events.append(event)

    def on_key_up_event(self, event):
        """Track key up events that are forwarded by the mixin.

        Args:
            event: The key up event.

        """
        self.key_up_events.append(event)


class SpacebarTestClass(SpacebarMixin, MockBaseClass):
    """Test class combining SpacebarMixin with MockBaseClass via MRO."""

    def __init__(self):
        """Initialize the test class."""
        super().__init__()
        self.spacebar_release_count = 0

    def on_spacebar_release(self):
        """Track spacebar release calls."""
        self.spacebar_release_count += 1


class TestSpacebarMixinInit:
    """Tests for SpacebarMixin initialization."""

    def test_init_sets_space_pressed_false(self):
        """Test that __init__ sets _space_pressed to False."""
        instance = SpacebarTestClass()
        assert instance._space_pressed is False

    def test_init_spacebar_release_count_zero(self):
        """Test that spacebar_release_count starts at zero."""
        instance = SpacebarTestClass()
        assert instance.spacebar_release_count == 0


class TestSpacebarMixinKeyDown:
    """Tests for SpacebarMixin.on_key_down_event."""

    def test_spacebar_press_sets_flag(self, mocker):
        """Test that pressing spacebar sets _space_pressed to True."""
        instance = SpacebarTestClass()
        event = mocker.Mock()
        event.key = pygame.K_SPACE

        instance.on_key_down_event(event)

        assert instance._space_pressed is True

    def test_non_spacebar_key_forwarded_to_super(self, mocker):
        """Test that non-spacebar keys are forwarded to the base class."""
        instance = SpacebarTestClass()
        event = mocker.Mock()
        event.key = pygame.K_RETURN

        instance.on_key_down_event(event)

        assert instance._space_pressed is False
        assert len(instance.key_down_events) == 1
        assert instance.key_down_events[0] is event

    def test_spacebar_press_does_not_forward_to_super(self, mocker):
        """Test that spacebar press is consumed and not forwarded."""
        instance = SpacebarTestClass()
        event = mocker.Mock()
        event.key = pygame.K_SPACE

        instance.on_key_down_event(event)

        assert len(instance.key_down_events) == 0


class TestSpacebarMixinKeyUp:
    """Tests for SpacebarMixin.on_key_up_event."""

    def test_spacebar_release_after_press_triggers_action(self, mocker):
        """Test that releasing spacebar after pressing it triggers on_spacebar_release."""
        instance = SpacebarTestClass()
        press_event = mocker.Mock()
        press_event.key = pygame.K_SPACE
        release_event = mocker.Mock()
        release_event.key = pygame.K_SPACE

        # Press then release
        instance.on_key_down_event(press_event)
        instance.on_key_up_event(release_event)

        assert instance.spacebar_release_count == 1
        assert instance._space_pressed is False

    def test_spacebar_release_without_press_forwards_to_super(self, mocker):
        """Test that releasing spacebar without prior press forwards to super."""
        instance = SpacebarTestClass()
        event = mocker.Mock()
        event.key = pygame.K_SPACE

        # Release without pressing first (_space_pressed is False)
        instance.on_key_up_event(event)

        assert instance.spacebar_release_count == 0
        assert len(instance.key_up_events) == 1

    def test_non_spacebar_key_up_forwarded_to_super(self, mocker):
        """Test that non-spacebar key up events are forwarded to the base class."""
        instance = SpacebarTestClass()
        event = mocker.Mock()
        event.key = pygame.K_RETURN

        instance.on_key_up_event(event)

        assert instance.spacebar_release_count == 0
        assert len(instance.key_up_events) == 1
        assert instance.key_up_events[0] is event

    def test_double_press_single_release(self, mocker):
        """Test pressing spacebar twice then releasing once triggers action once."""
        instance = SpacebarTestClass()
        press_event = mocker.Mock()
        press_event.key = pygame.K_SPACE
        release_event = mocker.Mock()
        release_event.key = pygame.K_SPACE

        instance.on_key_down_event(press_event)
        instance.on_key_down_event(press_event)
        instance.on_key_up_event(release_event)

        assert instance.spacebar_release_count == 1
        assert instance._space_pressed is False

    def test_release_resets_flag(self, mocker):
        """Test that spacebar release resets the _space_pressed flag."""
        instance = SpacebarTestClass()
        press_event = mocker.Mock()
        press_event.key = pygame.K_SPACE
        release_event = mocker.Mock()
        release_event.key = pygame.K_SPACE

        instance.on_key_down_event(press_event)
        assert instance._space_pressed is True

        instance.on_key_up_event(release_event)
        assert instance._space_pressed is False

        # Second release without press should forward to super
        instance.on_key_up_event(release_event)
        assert instance.spacebar_release_count == 1


class TestSpacebarMixinDefaultRelease:
    """Tests for the default on_spacebar_release no-op."""

    def test_default_on_spacebar_release_is_noop(self, mocker):
        """Test that the base SpacebarMixin.on_spacebar_release does nothing."""

        class MinimalSpacebarClass(SpacebarMixin, MockBaseClass):
            """Minimal class that does NOT override on_spacebar_release."""

        instance = MinimalSpacebarClass()
        press_event = mocker.Mock()
        press_event.key = pygame.K_SPACE
        release_event = mocker.Mock()
        release_event.key = pygame.K_SPACE

        instance.on_key_down_event(press_event)
        # Should not raise even though on_spacebar_release is a no-op
        instance.on_key_up_event(release_event)

        assert instance._space_pressed is False
