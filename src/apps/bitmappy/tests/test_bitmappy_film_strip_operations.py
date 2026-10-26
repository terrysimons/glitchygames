"""Tests for src/apps/bitmappy/src/bitmappy/controllers/film_strip_operations.py.

Drives the FilmStripOperations delegate through a real ControllerEventHandler, real
ControllerSelection, VisualCollisionManager and MultiControllerManager objects, and small
fake film strips, canvas and editor that record what the delegate asked of them.
"""

import logging
import sys

import pytest

from bitmappy import onion_skinning
from bitmappy.controllers.event_handler import ControllerEventHandler
from bitmappy.controllers.manager import (
    ControllerInfo,
    ControllerStatus,
    MultiControllerManager,
)
from bitmappy.controllers.selection import ControllerSelection
from bitmappy.indicators.collision import VisualCollisionManager
from bitmappy.onion_skinning import OnionSkinningManager

HANDLER_LOGGER_NAME = 'game.tools.bitmappy.controllers.event_handler'
GRAY = (128, 128, 128)
RED = (255, 0, 0)


class FakeAnimatedSprite:
    """An animated sprite stand-in holding frame lists per animation."""

    def __init__(self, frames_by_animation: dict[str, int], current_animation: str) -> None:
        """Build frame lists of the given lengths and pick the current animation."""
        self._animations = {
            animation_name: [f'{animation_name}-frame-{index}' for index in range(frame_count)]
            for animation_name, frame_count in frames_by_animation.items()
        }
        self.current_animation_frame_count = frames_by_animation[current_animation]


class FakeFilmStripWithoutScroll:
    """A film strip widget stand-in that cannot scroll to a frame."""

    def __init__(self, animated_sprite: FakeAnimatedSprite | None) -> None:
        """Record the animated sprite and count dirty marks."""
        self.animated_sprite = animated_sprite
        self.dirty_mark_count = 0

    def mark_dirty(self) -> None:
        """Count a dirty mark."""
        self.dirty_mark_count += 1


class FakeFilmStrip(FakeFilmStripWithoutScroll):
    """A film strip widget stand-in that records the frames it was scrolled to."""

    def __init__(self, animated_sprite: FakeAnimatedSprite | None) -> None:
        """Record the animated sprite, dirty marks and scroll requests."""
        super().__init__(animated_sprite)
        self.scrolled_to_frames: list[int] = []

    def update_scroll_for_frame(self, frame: int) -> None:
        """Record a scroll request."""
        self.scrolled_to_frames.append(frame)


class FakeCanvas:
    """A canvas stand-in that records redraws and shown frames."""

    def __init__(self) -> None:
        """Start with no redraws and no shown frames."""
        self.redraw_count = 0
        self.shown_frames: list[tuple[str, int]] = []

    def force_redraw(self) -> None:
        """Count a forced redraw."""
        self.redraw_count += 1

    def show_frame(self, animation: str, frame: int) -> None:
        """Record the frame shown."""
        self.shown_frames.append((animation, frame))


class FakeFilmStripSprite:
    """A film strip sprite stand-in with a dirty flag."""

    def __init__(self) -> None:
        """Start clean."""
        self.dirty = 0


class FakeControllerManager:
    """A controller manager stand-in whose scan finds the controllers it was given."""

    def __init__(self, controllers: dict[int, ControllerInfo]) -> None:
        """Hold the controllers and count scans."""
        self.controllers = controllers
        self.scan_count = 0

    def scan_for_controllers(self) -> list[int]:
        """Count a scan and report the known instance ids.

        Returns:
            list[int]: The instance ids of the held controllers.

        """
        self.scan_count += 1
        return list(self.controllers.keys())


class FakeEditor:
    """An editor stand-in exposing the state FilmStripOperations reads and writes."""

    def __init__(self, film_strips: dict) -> None:
        """Set up the editor state with the given film strips."""
        self.controller_selections: dict[int, ControllerSelection] = {}
        self.film_strips = film_strips
        self.film_strip_sprites: dict[str, FakeFilmStripSprite] = {}
        self.multi_controller_manager = FakeControllerManager(controllers={})
        self.visual_collision_manager = VisualCollisionManager()
        self.canvas = FakeCanvas()
        self.selected_animation: str | None = None
        self.selected_frame: int | None = None
        self.selected_frame_visible = True
        self.film_strip_scroll_offset = 0
        self.max_visible_strips = 2
        self.visibility_update_count = 0
        self.scroll_arrow_update_count = 0
        self.selection_state_update_count = 0
        self.frame_selected_calls: list[tuple[object, str, int]] = []

    def update_film_strip_visibility(self) -> None:
        """Count a visibility update."""
        self.visibility_update_count += 1

    def update_scroll_arrows(self) -> None:
        """Count a scroll arrow update."""
        self.scroll_arrow_update_count += 1

    def update_film_strip_selection_state(self) -> None:
        """Count a selection state update."""
        self.selection_state_update_count += 1

    def on_film_strip_frame_selected(
        self, strip_widget: object, animation: str, frame: int
    ) -> None:
        """Record a frame selection."""
        self.frame_selected_calls.append((strip_widget, animation, frame))


def make_strip(frames_by_animation: dict[str, int], current_animation: str) -> FakeFilmStrip:
    """Build a scrollable film strip around a fake animated sprite.

    Returns:
        FakeFilmStrip: The film strip.

    """
    return FakeFilmStrip(
        FakeAnimatedSprite(
            frames_by_animation=frames_by_animation, current_animation=current_animation
        ),
    )


@pytest.fixture
def editor() -> FakeEditor:
    """Build an editor with three animations: walk (4 frames), run (2), jump (6).

    Returns:
        FakeEditor: The editor.

    """
    return FakeEditor(
        film_strips={
            'walk': make_strip(frames_by_animation={'walk': 4}, current_animation='walk'),
            'run': make_strip(frames_by_animation={'run': 2}, current_animation='run'),
            'jump': make_strip(frames_by_animation={'jump': 6}, current_animation='jump'),
        },
    )


@pytest.fixture
def handler(editor: FakeEditor) -> ControllerEventHandler:
    """Build a real controller event handler over the fake editor.

    Returns:
        ControllerEventHandler: The handler.

    """
    return ControllerEventHandler(editor=editor)  # type: ignore[arg-type]


def add_selection(
    editor: FakeEditor,
    controller_id: int,
    animation: str = '',
    frame: int = 0,
    *,
    active: bool = True,
) -> ControllerSelection:
    """Add a controller selection to the editor.

    Returns:
        ControllerSelection: The selection added.

    """
    selection = ControllerSelection(controller_id=controller_id, instance_id=controller_id + 10)
    if animation or frame:
        selection.set_selection(animation, frame)
    if active:
        selection.activate()
    editor.controller_selections[controller_id] = selection
    return selection


def add_controller_info(
    editor: FakeEditor,
    controller_id: int,
    status: ControllerStatus = ControllerStatus.CONNECTED,
    color: tuple[int, int, int] = RED,
) -> ControllerInfo:
    """Add controller info for the controller to the editor's manager.

    Returns:
        ControllerInfo: The info added.

    """
    info = ControllerInfo(
        controller_id=controller_id,
        instance_id=controller_id + 10,
        status=status,
        color=color,
    )
    editor.multi_controller_manager.controllers[info.instance_id] = info
    return info


class TestSelectCurrentFrame:
    """Test the deprecated _select_current_frame."""

    def test_selects_matching_strip(self, handler, editor):
        """The strip named by the editor's selection is selected with its frame."""
        editor.selected_animation = 'run'
        editor.selected_frame = 1

        handler.film_strip._select_current_frame()

        assert editor.frame_selected_calls == [(editor.film_strips['run'], 'run', 1)]

    def test_without_selection_attributes_does_nothing(self, handler, editor):
        """An editor without a selected animation selects nothing."""
        del editor.selected_animation

        handler.film_strip._select_current_frame()

        assert editor.frame_selected_calls == []

    def test_without_selected_frame_attribute_does_nothing(self, handler, editor):
        """An editor without a selected frame selects nothing."""
        editor.selected_animation = 'walk'
        del editor.selected_frame

        handler.film_strip._select_current_frame()

        assert editor.frame_selected_calls == []

    def test_unknown_animation_selects_nothing(self, handler, editor):
        """A selected animation with no strip selects nothing."""
        editor.selected_animation = 'swim'
        editor.selected_frame = 0

        handler.film_strip._select_current_frame()

        assert editor.frame_selected_calls == []

    def test_none_frame_selects_nothing(self, handler, editor):
        """A selected animation with no selected frame selects nothing."""
        editor.selected_animation = 'walk'
        editor.selected_frame = None

        handler.film_strip._select_current_frame()

        assert editor.frame_selected_calls == []

    def test_none_animation_matching_a_none_key_selects_nothing(self, handler, editor):
        """A None selected animation never matches, even a strip keyed by None."""
        editor.film_strips = {None: make_strip(frames_by_animation={'x': 1}, current_animation='x')}
        editor.selected_animation = None
        editor.selected_frame = 0

        handler.film_strip._select_current_frame()

        assert editor.frame_selected_calls == []

    def test_without_film_strips_selects_nothing(self, handler, editor):
        """An editor with no film strips selects nothing."""
        editor.film_strips = {}
        editor.selected_animation = 'walk'
        editor.selected_frame = 0

        handler.film_strip._select_current_frame()

        assert editor.frame_selected_calls == []


class TestDeprecatedSingleControllerMethods:
    """Test that the disabled single-controller methods only log."""

    @pytest.mark.parametrize(
        'disabled_call',
        [
            ('controller_cancel', (), 'Controller cancel action'),
            ('_controller_select_current_frame', (), '_controller_select_current_frame called'),
            ('_controller_previous_frame', (), '_controller_previous_frame called'),
            ('_controller_next_frame', (), '_controller_next_frame called'),
            ('_controller_previous_animation', (), '_controller_previous_animation called'),
            ('_controller_next_animation', (), '_controller_next_animation called'),
            ('_validate_controller_selection', (), '_validate_controller_selection called'),
            ('_initialize_controller_selection', (), '_initialize_controller_selection called'),
            ('_controller_select_frame', ('walk', 2), '_controller_select_frame called'),
        ],
    )
    def test_logs_and_changes_nothing(self, handler, editor, caplog, disabled_call):
        """Each disabled method logs its message and leaves the selections alone."""
        method_name, arguments, expected_message = disabled_call
        selection = add_selection(editor=editor, controller_id=0, animation='walk', frame=1)
        caplog.set_level(logging.DEBUG, logger=HANDLER_LOGGER_NAME)

        getattr(handler.film_strip, method_name)(*arguments)

        assert expected_message in caplog.text
        assert selection.get_selection() == ('walk', 1)
        assert editor.frame_selected_calls == []


class TestMultiControllerActivate:
    """Test multi_controller_activate."""

    @pytest.fixture
    def singleton_manager(self, mocker, editor) -> MultiControllerManager:
        """Give the test a fresh MultiControllerManager singleton shared with the editor.

        Returns:
            MultiControllerManager: The fresh singleton.

        """
        mocker.patch.object(MultiControllerManager, '_instance', None)
        manager = MultiControllerManager.get_instance()
        editor.multi_controller_manager = manager
        return manager

    def test_unknown_controller_is_ignored(self, handler, editor, singleton_manager):
        """Activating a controller without a selection changes nothing."""
        handler.film_strip.multi_controller_activate(controller_id=3)

        assert editor.controller_selections == {}
        assert editor.visual_collision_manager.indicators == {}

    def test_activates_assigns_color_and_starts_on_first_animation(
        self, handler, editor, singleton_manager
    ):
        """A fresh controller is activated, colored, placed and every strip is redrawn."""
        selection = add_selection(editor=editor, controller_id=1, active=False)
        add_controller_info(editor=editor, controller_id=1, color=GRAY)
        film_strip_sprite = FakeFilmStripSprite()
        editor.film_strip_sprites = {'walk': film_strip_sprite}

        handler.film_strip.multi_controller_activate(controller_id=1)

        assert selection.is_active()
        assert selection.get_selection() == ('walk', 0)
        assert singleton_manager.controllers[11].color == RED
        indicator = editor.visual_collision_manager.indicators[1]
        assert indicator.position == (150, 100)
        assert indicator.color == RED
        assert all(strip.dirty_mark_count == 1 for strip in editor.film_strips.values())
        assert film_strip_sprite.dirty == 1

    def test_keeps_existing_animation(self, handler, editor, singleton_manager):
        """A controller that already has an animation keeps its selection."""
        selection = add_selection(
            editor=editor, controller_id=0, animation='jump', frame=3, active=False
        )
        add_controller_info(editor=editor, controller_id=0, color=GRAY)

        handler.film_strip.multi_controller_activate(controller_id=0)

        assert selection.is_active()
        assert selection.get_selection() == ('jump', 3)

    def test_without_film_strips_only_activates(self, handler, editor, singleton_manager):
        """With no film strips or strip sprites the controller is still activated."""
        selection = add_selection(editor=editor, controller_id=0, active=False)
        add_controller_info(editor=editor, controller_id=0, color=GRAY)
        del editor.film_strips
        del editor.film_strip_sprites

        handler.film_strip.multi_controller_activate(controller_id=0)

        assert selection.is_active()
        assert selection.get_selection() == ('', 0)
        assert singleton_manager.controllers[10].color == RED

    def test_with_empty_film_strips_only_activates(self, handler, editor, singleton_manager):
        """With empty film strips the controller is activated with no animation."""
        selection = add_selection(editor=editor, controller_id=0, active=False)
        editor.film_strips = {}

        handler.film_strip.multi_controller_activate(controller_id=0)

        assert selection.is_active()
        assert selection.get_selection() == ('', 0)


class TestMultiControllerFrameNavigation:
    """Test multi_controller_previous_frame and multi_controller_next_frame."""

    @pytest.mark.parametrize(
        'method_name', ['multi_controller_previous_frame', 'multi_controller_next_frame']
    )
    def test_unknown_controller_is_ignored(self, handler, editor, method_name):
        """Navigating a controller without a selection changes nothing."""
        getattr(handler.film_strip, method_name)(controller_id=2)

        assert editor.controller_selections == {}

    @pytest.mark.parametrize(
        'method_name', ['multi_controller_previous_frame', 'multi_controller_next_frame']
    )
    @pytest.mark.parametrize('animation', ['', 'swim'])
    def test_invalid_animation_is_ignored(self, handler, editor, method_name, animation):
        """A controller on no animation, or one without a strip, keeps its frame."""
        selection = add_selection(editor=editor, controller_id=0, animation=animation, frame=1)

        getattr(handler.film_strip, method_name)(controller_id=0)

        assert selection.get_selection() == (animation, 1)

    @pytest.mark.parametrize(
        'method_name', ['multi_controller_previous_frame', 'multi_controller_next_frame']
    )
    def test_strip_without_animated_sprite_is_ignored(self, handler, editor, method_name):
        """A strip with no animated sprite leaves the frame alone."""
        editor.film_strips['walk'] = FakeFilmStrip(animated_sprite=None)
        selection = add_selection(editor=editor, controller_id=0, animation='walk', frame=1)

        getattr(handler.film_strip, method_name)(controller_id=0)

        assert selection.get_selection() == ('walk', 1)
        assert editor.film_strips['walk'].scrolled_to_frames == []

    def test_previous_frame_wraps_and_scrolls(self, handler, editor):
        """Previous from frame 0 wraps to the last frame and scrolls the strip there."""
        selection = add_selection(editor=editor, controller_id=0, animation='walk', frame=0)
        add_controller_info(editor=editor, controller_id=0)

        handler.film_strip.multi_controller_previous_frame(controller_id=0)

        assert selection.get_selection() == ('walk', 3)
        assert editor.film_strips['walk'].scrolled_to_frames == [3]
        assert editor.visual_collision_manager.indicators[0].position == (100, 100)

    def test_next_frame_wraps_and_scrolls(self, handler, editor):
        """Next from the last frame wraps to frame 0 and scrolls the strip there."""
        selection = add_selection(editor=editor, controller_id=0, animation='walk', frame=3)

        handler.film_strip.multi_controller_next_frame(controller_id=0)

        assert selection.get_selection() == ('walk', 0)
        assert editor.film_strips['walk'].scrolled_to_frames == [0]

    @pytest.mark.parametrize(
        ('method_name', 'expected_frame'),
        [('multi_controller_previous_frame', 0), ('multi_controller_next_frame', 2)],
    )
    def test_strip_without_scrolling_still_moves(
        self, handler, editor, method_name, expected_frame
    ):
        """A strip that cannot scroll still moves the controller's frame."""
        editor.film_strips['walk'] = FakeFilmStripWithoutScroll(
            FakeAnimatedSprite(frames_by_animation={'walk': 4}, current_animation='walk'),
        )
        selection = add_selection(editor=editor, controller_id=0, animation='walk', frame=1)

        getattr(handler.film_strip, method_name)(controller_id=0)

        assert selection.get_selection() == ('walk', expected_frame)


class TestMultiControllerAnimationNavigation:
    """Test multi_controller_previous_animation and multi_controller_next_animation."""

    @pytest.mark.parametrize(
        'method_name', ['multi_controller_previous_animation', 'multi_controller_next_animation']
    )
    def test_unknown_controller_is_ignored(self, handler, editor, method_name):
        """Navigating a controller without a selection changes nothing."""
        getattr(handler.film_strip, method_name)(controller_id=2)

        assert editor.controller_selections == {}
        assert editor.visibility_update_count == 0

    @pytest.mark.parametrize(
        'method_name', ['multi_controller_previous_animation', 'multi_controller_next_animation']
    )
    def test_without_film_strips_keeps_selection(self, handler, editor, method_name):
        """With no film strips attribute the selection is unchanged."""
        selection = add_selection(editor=editor, controller_id=0, animation='walk', frame=1)
        del editor.film_strips

        getattr(handler.film_strip, method_name)(controller_id=0)

        assert selection.get_selection() == ('walk', 1)

    @pytest.mark.parametrize(
        'method_name', ['multi_controller_previous_animation', 'multi_controller_next_animation']
    )
    def test_with_empty_film_strips_keeps_selection(self, handler, editor, method_name):
        """With empty film strips the selection is unchanged."""
        selection = add_selection(editor=editor, controller_id=0, animation='walk', frame=1)
        editor.film_strips = {}

        getattr(handler.film_strip, method_name)(controller_id=0)

        assert selection.get_selection() == ('walk', 1)

    def test_previous_animation_wraps_to_last(self, handler, editor):
        """Previous from the first animation wraps to the last and keeps the frame."""
        selection = add_selection(editor=editor, controller_id=0, animation='walk', frame=2)

        handler.film_strip.multi_controller_previous_animation(controller_id=0)

        assert selection.get_selection() == ('jump', 2)
        # jump is index 2, past the two visible strips, so the view scrolls down by one
        assert editor.film_strip_scroll_offset == 1
        assert editor.visibility_update_count == 1
        assert editor.scroll_arrow_update_count == 1

    def test_next_animation_clamps_frame(self, handler, editor):
        """Next from walk frame 3 moves to run, clamping to its last frame."""
        selection = add_selection(editor=editor, controller_id=0, animation='walk', frame=3)

        handler.film_strip.multi_controller_next_animation(controller_id=0)

        assert selection.get_selection() == ('run', 1)

    def test_next_animation_wraps_to_first(self, handler, editor):
        """Next from the last animation wraps to the first and scrolls up to it."""
        editor.film_strip_scroll_offset = 1
        selection = add_selection(editor=editor, controller_id=0, animation='jump', frame=5)

        handler.film_strip.multi_controller_next_animation(controller_id=0)

        assert selection.get_selection() == ('walk', 3)
        assert editor.film_strip_scroll_offset == 0

    def test_previous_animation_from_unknown_animation_starts_at_first(self, handler, editor):
        """An unknown current animation counts as the first, so previous goes to the last."""
        selection = add_selection(editor=editor, controller_id=0, animation='swim', frame=0)

        handler.film_strip.multi_controller_previous_animation(controller_id=0)

        assert selection.get_selection() == ('jump', 0)

    def test_next_animation_from_unknown_animation_goes_to_second(self, handler, editor):
        """An unknown current animation counts as the first, so next goes to the second."""
        selection = add_selection(editor=editor, controller_id=0, animation='swim', frame=0)

        handler.film_strip.multi_controller_next_animation(controller_id=0)

        assert selection.get_selection() == ('run', 0)

    def test_returning_to_animation_restores_its_frame(self, handler, editor):
        """Going back to an animation restores the frame it was left on."""
        selection = add_selection(editor=editor, controller_id=0, animation='jump', frame=4)
        handler.film_strip.multi_controller_next_animation(controller_id=0)
        selection.set_frame(1)

        handler.film_strip.multi_controller_previous_animation(controller_id=0)

        assert selection.get_selection() == ('jump', 4)


class TestUpdateControllerVisualIndicator:
    """Test _update_controller_visual_indicator."""

    def test_unknown_controller_adds_nothing(self, handler, editor):
        """A controller without a selection gets no indicator."""
        handler.film_strip._update_controller_visual_indicator(controller_id=0)

        assert editor.visual_collision_manager.indicators == {}

    @pytest.mark.parametrize('animation', ['', 'swim'])
    def test_invalid_animation_adds_nothing(self, handler, editor, animation):
        """A controller on no animation, or one without a strip, gets no indicator."""
        add_selection(editor=editor, controller_id=0, animation=animation)
        add_controller_info(editor=editor, controller_id=0)

        handler.film_strip._update_controller_visual_indicator(controller_id=0)

        assert editor.visual_collision_manager.indicators == {}

    def test_missing_controller_info_adds_nothing(self, handler, editor):
        """A controller the manager does not know gets no indicator."""
        add_selection(editor=editor, controller_id=0, animation='walk')
        add_controller_info(editor=editor, controller_id=1)

        handler.film_strip._update_controller_visual_indicator(controller_id=0)

        assert editor.visual_collision_manager.indicators == {}

    def test_adds_then_updates_indicator(self, handler, editor):
        """The first call adds the indicator; a later call moves the same one back."""
        add_selection(editor=editor, controller_id=2, animation='walk')
        add_controller_info(editor=editor, controller_id=2)

        handler.film_strip._update_controller_visual_indicator(controller_id=2)
        indicator = editor.visual_collision_manager.indicators[2]
        indicator.position = (0, 0)
        handler.film_strip._update_controller_visual_indicator(controller_id=2)

        assert editor.visual_collision_manager.indicators[2] is indicator
        assert indicator.position == (200, 100)
        assert indicator.instance_id == 12


class TestOnionSkinningToggle:
    """Test multi_controller_toggle_onion_skinning."""

    @pytest.fixture
    def onion_manager(self, mocker) -> OnionSkinningManager:
        """Replace the global onion skinning manager with a fresh one.

        Returns:
            OnionSkinningManager: The fresh manager.

        """
        fresh_manager = OnionSkinningManager()
        mocker.patch.object(onion_skinning, 'onion_skinning_manager', fresh_manager)
        return fresh_manager

    def test_unknown_controller_toggles_nothing(self, handler, editor, onion_manager):
        """A controller without a selection toggles nothing."""
        handler.film_strip.multi_controller_toggle_onion_skinning(controller_id=0)

        assert onion_manager.onion_skinning_enabled == {}
        assert editor.canvas.redraw_count == 0

    def test_no_animation_toggles_nothing(self, handler, editor, onion_manager):
        """A controller on no animation toggles nothing."""
        add_selection(editor=editor, controller_id=0)

        handler.film_strip.multi_controller_toggle_onion_skinning(controller_id=0)

        assert onion_manager.onion_skinning_enabled == {}

    def test_toggles_frame_on_and_off(self, handler, editor, onion_manager):
        """Toggling twice turns the frame's onion skinning on, then off, redrawing each time."""
        add_selection(editor=editor, controller_id=0, animation='run', frame=1)

        handler.film_strip.multi_controller_toggle_onion_skinning(controller_id=0)
        enabled_after_first = onion_manager.is_frame_onion_skinned('run', 1)
        handler.film_strip.multi_controller_toggle_onion_skinning(controller_id=0)

        assert enabled_after_first is True
        assert onion_manager.is_frame_onion_skinned('run', 1) is False
        assert editor.canvas.redraw_count == 2

    def test_without_canvas_still_toggles(self, handler, editor, onion_manager):
        """With no canvas the frame is toggled without a redraw."""
        add_selection(editor=editor, controller_id=0, animation='run', frame=0)
        editor.canvas = None

        handler.film_strip.multi_controller_toggle_onion_skinning(controller_id=0)

        assert onion_manager.is_frame_onion_skinned('run', 0) is True


class TestSelectedFrameVisibilityToggle:
    """Test multi_controller_toggle_selected_frame_visibility."""

    def test_toggles_visibility_and_redraws(self, handler, editor):
        """Each toggle flips the selected frame's visibility and redraws the canvas."""
        handler.film_strip.multi_controller_toggle_selected_frame_visibility(controller_id=0)
        hidden_after_first = editor.selected_frame_visible
        handler.film_strip.multi_controller_toggle_selected_frame_visibility(controller_id=0)

        assert hidden_after_first is False
        assert editor.selected_frame_visible is True
        assert editor.canvas.redraw_count == 2

    def test_without_canvas_still_toggles(self, handler, editor):
        """With no canvas attribute the visibility still flips."""
        del editor.canvas

        handler.film_strip.multi_controller_toggle_selected_frame_visibility(controller_id=0)

        assert editor.selected_frame_visible is False


class TestMultiControllerSelectCurrentFrame:
    """Test multi_controller_select_current_frame."""

    def test_selects_frame_on_canvas_and_globally(self, handler, editor):
        """An active controller's frame is shown and becomes the global selection."""
        editor.film_strips['walk'] = FakeFilmStrip(
            FakeAnimatedSprite(frames_by_animation={'walk': 4}, current_animation='walk'),
        )
        add_selection(editor=editor, controller_id=0, animation='walk', frame=2)

        handler.film_strip.multi_controller_select_current_frame(controller_id=0)

        assert editor.canvas.shown_frames == [('walk', 2)]
        assert editor.selected_animation == 'walk'
        assert editor.selected_frame == 2
        assert editor.selection_state_update_count == 1

    def test_unknown_controller_selects_nothing(self, handler, editor):
        """A controller without a selection selects nothing."""
        handler.film_strip.multi_controller_select_current_frame(controller_id=0)

        assert editor.canvas.shown_frames == []

    def test_inactive_controller_selects_nothing(self, handler, editor):
        """An inactive controller selects nothing."""
        add_selection(editor=editor, controller_id=0, animation='walk', frame=1, active=False)

        handler.film_strip.multi_controller_select_current_frame(controller_id=0)

        assert editor.canvas.shown_frames == []
        assert editor.selected_animation is None

    def test_animation_without_strip_selects_nothing(self, handler, editor):
        """An animation with no strip selects nothing."""
        add_selection(editor=editor, controller_id=0, animation='swim', frame=0)

        handler.film_strip.multi_controller_select_current_frame(controller_id=0)

        assert editor.canvas.shown_frames == []

    def test_strip_without_animated_sprite_selects_nothing(self, handler, editor):
        """A strip with no animated sprite selects nothing."""
        editor.film_strips['walk'] = FakeFilmStrip(animated_sprite=None)
        add_selection(editor=editor, controller_id=0, animation='walk', frame=0)

        handler.film_strip.multi_controller_select_current_frame(controller_id=0)

        assert editor.canvas.shown_frames == []

    def test_animation_missing_from_sprite_selects_nothing(self, handler, editor):
        """A strip whose sprite lacks the animation selects nothing."""
        editor.film_strips['walk'] = make_strip(
            frames_by_animation={'other': 3}, current_animation='other'
        )
        add_selection(editor=editor, controller_id=0, animation='walk', frame=0)

        handler.film_strip.multi_controller_select_current_frame(controller_id=0)

        assert editor.canvas.shown_frames == []

    def test_out_of_bounds_frame_selects_nothing(self, handler, editor):
        """A frame past the animation's end selects nothing."""
        editor.film_strips['run'] = make_strip(
            frames_by_animation={'run': 2}, current_animation='run'
        )
        add_selection(editor=editor, controller_id=0, animation='run', frame=5)

        handler.film_strip.multi_controller_select_current_frame(controller_id=0)

        assert editor.canvas.shown_frames == []
        assert editor.selected_frame is None


class TestMultiControllerCancel:
    """Test _multi_controller_cancel."""

    def test_deactivates_controller(self, handler, editor):
        """Cancelling deactivates the controller's selection."""
        selection = add_selection(editor=editor, controller_id=0, animation='walk')

        handler.film_strip._multi_controller_cancel(controller_id=0)

        assert selection.is_active() is False

    def test_unknown_controller_is_ignored(self, handler, editor):
        """Cancelling a controller without a selection changes nothing."""
        selection = add_selection(editor=editor, controller_id=0, animation='walk')

        handler.film_strip._multi_controller_cancel(controller_id=1)

        assert selection.is_active() is True


class TestScrollToControllerAnimation:
    """Test _scroll_to_controller_animation."""

    def test_without_film_strips_does_nothing(self, handler, editor):
        """With no film strips nothing scrolls or updates."""
        editor.film_strips = {}

        handler.film_strip._scroll_to_controller_animation(animation_name='walk')

        assert editor.visibility_update_count == 0

    def test_unknown_animation_does_nothing(self, handler, editor):
        """An animation with no strip scrolls nothing."""
        handler.film_strip._scroll_to_controller_animation(animation_name='swim')

        assert editor.visibility_update_count == 0
        assert editor.film_strip_scroll_offset == 0

    def test_animation_above_view_scrolls_up(self, handler, editor):
        """An animation above the visible strips scrolls the view up to it."""
        editor.film_strip_scroll_offset = 2

        handler.film_strip._scroll_to_controller_animation(animation_name='run')

        assert editor.film_strip_scroll_offset == 1

    def test_animation_below_view_scrolls_down(self, handler, editor):
        """An animation below the visible strips scrolls the view down to show it last."""
        editor.max_visible_strips = 1

        handler.film_strip._scroll_to_controller_animation(animation_name='jump')

        assert editor.film_strip_scroll_offset == 2

    def test_visible_animation_keeps_offset(self, handler, editor):
        """An animation already visible keeps the offset but refreshes the view."""
        handler.film_strip._scroll_to_controller_animation(animation_name='run')

        assert editor.film_strip_scroll_offset == 0
        assert editor.visibility_update_count == 1
        assert editor.scroll_arrow_update_count == 1


class TestReinitializeMultiControllerSystem:
    """Test reinitialize_multi_controller_system and its helpers."""

    def test_empty_selections_return_without_scanning(self, handler, editor):
        """With no selections (a recreated scene) nothing is scanned or created."""
        add_controller_info(editor=editor, controller_id=0)

        handler.film_strip.reinitialize_multi_controller_system()

        assert editor.multi_controller_manager.scan_count == 0
        assert editor.controller_selections == {}

    def test_restores_active_controller_to_first_animation(self, handler, editor):
        """An active controller is reset to the first animation, frame 0, and stays active."""
        selection = add_selection(editor=editor, controller_id=0, animation='jump', frame=4)
        add_controller_info(editor=editor, controller_id=0, status=ControllerStatus.ACTIVE)

        handler.film_strip.reinitialize_multi_controller_system()

        assert editor.multi_controller_manager.scan_count == 1
        assert editor.controller_selections[0] is selection
        assert selection.get_selection() == ('walk', 0)
        assert selection.is_active()

    def test_creates_inactive_selection_for_new_controller(self, handler, editor):
        """A connected controller without a selection gets a new, inactive one."""
        add_selection(editor=editor, controller_id=0, animation='run', active=False)
        add_controller_info(editor=editor, controller_id=0, status=ControllerStatus.ASSIGNED)
        add_controller_info(editor=editor, controller_id=1, status=ControllerStatus.CONNECTED)

        handler.film_strip.reinitialize_multi_controller_system()

        new_selection = editor.controller_selections[1]
        assert new_selection.instance_id == 11
        assert new_selection.is_active() is False
        assert editor.controller_selections[0].get_selection() == ('run', 0)

    def test_skips_disconnected_controller(self, handler, editor):
        """A disconnected controller gets no selection."""
        add_selection(editor=editor, controller_id=0, animation='run')
        add_controller_info(editor=editor, controller_id=1, status=ControllerStatus.DISCONNECTED)

        handler.film_strip.reinitialize_multi_controller_system()

        assert 1 not in editor.controller_selections

    def test_preserved_selections_decide_which_controllers_are_active(self, handler, editor):
        """Preserved selections, not the current state, mark a controller active again."""
        selection = add_selection(editor=editor, controller_id=0, animation='jump', active=False)
        add_controller_info(editor=editor, controller_id=0)

        handler.film_strip.reinitialize_multi_controller_system(
            preserved_controller_selections={0: ('jump', 2)},
        )

        assert selection.is_active()
        assert selection.get_selection() == ('walk', 0)

    def test_active_controller_without_film_strips_keeps_selection(self, handler, editor):
        """With no film strips an active controller keeps its old selection."""
        selection = add_selection(editor=editor, controller_id=0, animation='jump', frame=4)
        add_controller_info(editor=editor, controller_id=0)
        editor.film_strips = {}

        handler.film_strip.reinitialize_multi_controller_system()

        assert selection.get_selection() == ('jump', 4)
        assert selection.is_active()

    @pytest.mark.parametrize('has_film_strips', [True, False])
    def test_outside_pytest_logs_state(self, mocker, handler, editor, caplog, has_film_strips):
        """Outside pytest the current selections and film strips are logged first."""
        add_selection(editor=editor, controller_id=0, animation='walk')
        if not has_film_strips:
            editor.film_strips = {}
        caplog.set_level(logging.DEBUG, logger=HANDLER_LOGGER_NAME)
        mocker.patch.dict(sys.modules)
        del sys.modules['pytest']

        handler.film_strip.reinitialize_multi_controller_system()

        expected_strips = "['walk', 'run', 'jump']" if has_film_strips else 'None'
        assert f'Current film_strips: {expected_strips}' in caplog.text
        assert 'Current controller_selections: [0]' in caplog.text

    def test_outside_pytest_logs_recreated_scene(self, mocker, handler, editor, caplog):
        """Outside pytest an empty selection map is logged as a recreated scene."""
        caplog.set_level(logging.DEBUG, logger=HANDLER_LOGGER_NAME)
        mocker.patch.dict(sys.modules)
        del sys.modules['pytest']

        handler.film_strip.reinitialize_multi_controller_system()

        assert 'scene was likely recreated' in caplog.text
        assert editor.multi_controller_manager.scan_count == 0
