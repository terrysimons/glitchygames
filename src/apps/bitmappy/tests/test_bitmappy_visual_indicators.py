"""Tests for src/apps/bitmappy/src/bitmappy/controllers/visual_indicators.py.

Drives the VisualIndicators delegate through a real ControllerEventHandler with real
ModeSwitcher, ControllerSelection, VisualCollisionManager and MultiControllerManager
objects, and small fake sliders, film strips and canvas that record what was asked of them.
"""

import pygame
import pytest

from bitmappy.controllers.event_handler import ControllerEventHandler
from bitmappy.controllers.manager import (
    ControllerInfo,
    ControllerStatus,
    MultiControllerManager,
)
from bitmappy.controllers.modes import ControllerMode, ModeSwitcher
from bitmappy.controllers.selection import ControllerSelection
from bitmappy.indicators.collision import (
    IndicatorShape,
    LocationType,
    VisualCollisionManager,
)
from glitchygames import clock

RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
PURPLE = (128, 0, 128)
BLACK = (0, 0, 0)


class FakeTextSprite:
    """A slider text sprite stand-in with a dirty flag."""

    def __init__(self) -> None:
        """Start clean."""
        self.dirty = 0


class FakeSlider:
    """A slider stand-in with a rect and a text sprite."""

    def __init__(self, rect: pygame.Rect) -> None:
        """Hold the slider's rect and a clean text sprite."""
        self.rect = rect
        self.text_sprite = FakeTextSprite()


class FakeFilmStrip:
    """A film strip widget stand-in that counts dirty marks."""

    def __init__(self) -> None:
        """Start with no dirty marks."""
        self.dirty_mark_count = 0

    def mark_dirty(self) -> None:
        """Count a dirty mark."""
        self.dirty_mark_count += 1


class FakeCanvas:
    """A canvas stand-in that counts forced redraws."""

    def __init__(self) -> None:
        """Start with no redraws."""
        self.redraw_count = 0

    def force_redraw(self) -> None:
        """Count a forced redraw."""
        self.redraw_count += 1


class FakeEditor:
    """An editor stand-in exposing the state VisualIndicators reads and writes."""

    def __init__(self, manager: MultiControllerManager) -> None:
        """Set up sliders, film strips, canvas and the controller services."""
        self.controller_selections: dict[int, ControllerSelection] = {}
        self.mode_switcher = ModeSwitcher()
        self.multi_controller_manager = manager
        self.visual_collision_manager = VisualCollisionManager()
        self.film_strips = {'walk': FakeFilmStrip(), 'run': FakeFilmStrip()}
        self.canvas = FakeCanvas()
        self.alpha_slider = FakeSlider(rect=pygame.Rect(100, 100, 200, 20))
        self.red_slider = FakeSlider(rect=pygame.Rect(100, 10, 200, 20))
        self.green_slider = FakeSlider(rect=pygame.Rect(100, 40, 200, 20))
        self.blue_slider = FakeSlider(rect=pygame.Rect(100, 70, 200, 20))
        self.all_sprites = pygame.sprite.Group()
        self.dirty = 0


@pytest.fixture
def manager(mocker) -> MultiControllerManager:
    """Give the test a fresh MultiControllerManager singleton.

    Returns:
        MultiControllerManager: The fresh singleton.

    """
    mocker.patch.object(MultiControllerManager, '_instance', None)
    return MultiControllerManager.get_instance()


@pytest.fixture
def editor(manager) -> FakeEditor:
    """Build the fake editor around the fresh manager.

    Returns:
        FakeEditor: The editor.

    """
    return FakeEditor(manager=manager)


@pytest.fixture
def handler(editor) -> ControllerEventHandler:
    """Build a real controller event handler over the fake editor.

    Returns:
        ControllerEventHandler: The handler.

    """
    return ControllerEventHandler(editor=editor)  # type: ignore[arg-type]


def add_controller(
    editor: FakeEditor,
    controller_id: int,
    color: tuple[int, int, int] = RED,
    mode: ControllerMode | None = ControllerMode.FILM_STRIP,
    selection: tuple[str, int] = ('walk', 0),
) -> ControllerSelection:
    """Add a connected, active controller with a selection and, optionally, a mode.

    The controller's instance id is its controller id.

    Returns:
        ControllerSelection: The controller's selection.

    """
    editor.multi_controller_manager.controllers[controller_id] = ControllerInfo(
        controller_id=controller_id,
        instance_id=controller_id,
        status=ControllerStatus.ACTIVE,
        color=color,
    )
    controller_selection = ControllerSelection(
        controller_id=controller_id, instance_id=controller_id
    )
    animation, frame = selection
    if animation or frame:
        controller_selection.set_selection(animation, frame)
    controller_selection.activate()
    editor.controller_selections[controller_id] = controller_selection
    if mode is not None:
        editor.mode_switcher.register_controller(controller_id, mode)
    return controller_selection


class TestUpdateControllerCanvasVisualIndicator:
    """Test update_controller_canvas_visual_indicator."""

    def test_replaces_indicator_with_canvas_indicator(self, handler, editor):
        """A film strip indicator is replaced by a canvas square at the saved position."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.CANVAS, color=GREEN)
        editor.mode_switcher.save_controller_position(0, (5, 7))
        editor.visual_collision_manager.add_controller_indicator(0, 0, GREEN, (1, 1))

        handler.indicators.update_controller_canvas_visual_indicator(controller_id=0)

        indicator = editor.visual_collision_manager.indicators[0]
        assert indicator.location_type == LocationType.CANVAS
        assert indicator.shape == IndicatorShape.SQUARE
        assert indicator.position == (5, 7)
        assert indicator.color == GREEN
        assert 0 not in editor.visual_collision_manager.film_strip_indicators

    def test_unknown_controller_adds_nothing(self, handler, editor):
        """A controller the manager does not know gets no indicator."""
        handler.indicators.update_controller_canvas_visual_indicator(controller_id=0)

        assert editor.visual_collision_manager.indicators == {}

    def test_controller_without_mode_adds_nothing(self, handler, editor):
        """A controller with no mode (no position) gets no indicator."""
        add_controller(editor=editor, controller_id=0, mode=None)

        handler.indicators.update_controller_canvas_visual_indicator(controller_id=0)

        assert editor.visual_collision_manager.indicators == {}

    def test_without_collision_manager_changes_nothing(self, handler, editor):
        """An editor with no collision manager is left alone."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.CANVAS)
        del editor.visual_collision_manager

        handler.indicators.update_controller_canvas_visual_indicator(controller_id=0)

        assert not hasattr(editor, 'visual_collision_manager')

    def test_controller_whose_instance_id_differs_gets_indicator(self, handler, editor):
        """A controller whose instance id is not its controller id still gets one (#96)."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.CANVAS)
        controller_info = editor.multi_controller_manager.controllers.pop(0)
        controller_info.instance_id = 7
        editor.multi_controller_manager.controllers[7] = controller_info

        handler.indicators.update_controller_canvas_visual_indicator(controller_id=0)

        assert 0 in editor.visual_collision_manager.canvas_indicators


class TestUpdateControllerVisualIndicatorForMode:
    """Test update_controller_visual_indicator_for_mode and its helpers."""

    def test_canvas_mode_uses_saved_position_and_redraws(self, handler, editor):
        """Entering canvas mode places a square at the saved position and redraws."""
        add_controller(editor=editor, controller_id=1, mode=ControllerMode.CANVAS, color=BLUE)
        editor.mode_switcher.save_controller_position(1, (3, 4))

        handler.indicators.update_controller_visual_indicator_for_mode(
            controller_id=1, new_mode=ControllerMode.CANVAS
        )

        indicator = editor.visual_collision_manager.indicators[1]
        assert indicator.location_type == LocationType.CANVAS
        assert indicator.position == (3, 4)
        # Once for the canvas mode itself and once to clear old canvas markers
        assert editor.canvas.redraw_count == 2
        assert all(strip.dirty_mark_count == 1 for strip in editor.film_strips.values())

    def test_controllers_with_swapped_instance_ids_get_their_own_colors(self, handler, editor):
        """Each controller's indicator uses its own info, found by controller id (#96)."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.CANVAS, color=RED)
        add_controller(editor=editor, controller_id=1, mode=ControllerMode.CANVAS, color=BLUE)
        first_info = editor.multi_controller_manager.controllers.pop(0)
        second_info = editor.multi_controller_manager.controllers.pop(1)
        first_info.instance_id = 1
        second_info.instance_id = 0
        editor.multi_controller_manager.controllers[1] = first_info
        editor.multi_controller_manager.controllers[0] = second_info

        handler.indicators.update_controller_visual_indicator_for_mode(
            controller_id=0, new_mode=ControllerMode.CANVAS
        )

        indicator = editor.visual_collision_manager.indicators[0]
        assert indicator.color == RED
        assert indicator.instance_id == 1

    def test_slider_mode_marks_sliders_and_scene_dirty(self, handler, editor):
        """Entering a slider mode marks every slider's text and the scene dirty."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.G_SLIDER)

        handler.indicators.update_controller_visual_indicator_for_mode(
            controller_id=0, new_mode=ControllerMode.G_SLIDER
        )

        assert editor.visual_collision_manager.indicators[0].shape == IndicatorShape.CIRCLE
        assert editor.red_slider.text_sprite.dirty == 2
        assert editor.green_slider.text_sprite.dirty == 2
        assert editor.blue_slider.text_sprite.dirty == 2
        assert editor.dirty == 1

    def test_slider_mode_without_sliders_marks_scene_dirty(self, handler, editor):
        """With no sliders a slider mode still marks the scene dirty."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.R_SLIDER)
        del editor.red_slider
        del editor.green_slider
        del editor.blue_slider

        handler.indicators.update_controller_visual_indicator_for_mode(
            controller_id=0, new_mode=ControllerMode.R_SLIDER
        )

        assert editor.dirty == 1

    def test_film_strip_mode_marks_strips_dirty(self, handler, editor):
        """Entering film strip mode marks the strips dirty for the mode and the cleanup."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.FILM_STRIP)

        handler.indicators.update_controller_visual_indicator_for_mode(
            controller_id=0, new_mode=ControllerMode.FILM_STRIP
        )

        assert editor.visual_collision_manager.indicators[0].shape == IndicatorShape.TRIANGLE
        assert all(strip.dirty_mark_count == 2 for strip in editor.film_strips.values())
        assert editor.canvas.redraw_count == 1

    def test_film_strip_mode_without_strips_or_canvas(self, handler, editor):
        """Without film strips or canvas the indicator is still placed."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.FILM_STRIP)
        del editor.film_strips
        del editor.canvas

        handler.indicators.update_controller_visual_indicator_for_mode(
            controller_id=0, new_mode=ControllerMode.FILM_STRIP
        )

        assert editor.visual_collision_manager.indicators[0].position == (0, 0)

    def test_canvas_location_without_canvas_marks_strips(self, handler, editor):
        """A canvas location with no canvas still marks the film strips dirty."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.CANVAS)
        del editor.canvas

        handler.indicators.update_controller_visual_indicator_for_mode(
            controller_id=0, new_mode=ControllerMode.CANVAS
        )

        assert all(strip.dirty_mark_count == 1 for strip in editor.film_strips.values())

    def test_unknown_location_type_marks_nothing(self, handler, editor):
        """A location type that is not canvas, slider or film strip marks nothing dirty."""
        handler.indicators._mark_dirty_for_specific_mode(controller_id=0, location_type='elsewhere')

        assert editor.canvas.redraw_count == 0
        assert editor.dirty == 0
        assert all(strip.dirty_mark_count == 0 for strip in editor.film_strips.values())

    def test_unknown_controller_changes_nothing(self, handler, editor):
        """A controller the manager does not know gets no indicator."""
        handler.indicators.update_controller_visual_indicator_for_mode(
            controller_id=0, new_mode=ControllerMode.CANVAS
        )

        assert editor.visual_collision_manager.indicators == {}
        assert editor.canvas.redraw_count == 0

    def test_controller_without_mode_changes_nothing(self, handler, editor):
        """A controller with no registered mode gets no indicator."""
        add_controller(editor=editor, controller_id=0, mode=None)

        handler.indicators.update_controller_visual_indicator_for_mode(
            controller_id=0, new_mode=ControllerMode.CANVAS
        )

        assert editor.visual_collision_manager.indicators == {}
        assert editor.canvas.redraw_count == 0

    def test_without_collision_manager_still_marks_dirty(self, handler, editor):
        """With no collision manager the mode change still redraws."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.CANVAS)
        del editor.visual_collision_manager

        handler.indicators.update_controller_visual_indicator_for_mode(
            controller_id=0, new_mode=ControllerMode.CANVAS
        )

        assert editor.canvas.redraw_count == 2

    @pytest.mark.parametrize(
        ('new_mode', 'expected_position'),
        [
            (ControllerMode.CANVAS, (0, 0)),
            (ControllerMode.R_SLIDER, (0, 0)),
            (ControllerMode.G_SLIDER, (0, 0)),
            (ControllerMode.B_SLIDER, (0, 0)),
            (ControllerMode.FILM_STRIP, (100, 100)),
        ],
    )
    def test_default_position_for_invalid_saved_position(
        self, handler, editor, new_mode, expected_position
    ):
        """An invalid saved position falls back to each mode's default position."""
        add_controller(editor=editor, controller_id=0, mode=new_mode)
        editor.mode_switcher.get_controller_position(0).is_valid = False

        position = handler.indicators._get_controller_mode_position(
            controller_id=0, new_mode=new_mode
        )

        assert position == expected_position

    def test_default_position_for_unregistered_controller(self, handler, editor):
        """A controller with no saved position at all gets the mode's default."""
        position = handler.indicators._get_controller_mode_position(
            controller_id=3, new_mode=ControllerMode.FILM_STRIP
        )

        assert position == (100, 100)


class TestRenderVisualIndicators:
    """Test render_visual_indicators, the main entry point."""

    @pytest.fixture
    def recently_scanned_manager(self, manager) -> MultiControllerManager:
        """Mark the manager as just scanned, so its controllers survive the render's scan.

        Returns:
            MultiControllerManager: The manager.

        """
        manager.last_scan_time = clock.elapsed_seconds()
        return manager

    def test_creates_missing_services(self, mocker, handler, editor, manager):
        """An editor without selections, mode switcher or manager gets all three."""
        mocker.patch.object(manager, 'scan_for_controllers', return_value=[])
        del editor.controller_selections
        del editor.mode_switcher
        del editor.multi_controller_manager

        handler.indicators.render_visual_indicators()

        assert editor.controller_selections == {}
        assert isinstance(editor.mode_switcher, ModeSwitcher)
        assert editor.multi_controller_manager is manager

    def test_registers_new_controller_and_tracks_film_strip_selection(
        self, handler, editor, recently_scanned_manager
    ):
        """A newly found controller is registered active in film strip mode."""
        recently_scanned_manager.controllers[4] = ControllerInfo(
            controller_id=2, instance_id=4, status=ControllerStatus.CONNECTED, color=YELLOW
        )

        handler.indicators.render_visual_indicators()

        selection = editor.controller_selections[2]
        assert selection.instance_id == 4
        assert selection.is_active()
        assert editor.mode_switcher.get_controller_mode(2) == ControllerMode.FILM_STRIP

    def test_without_screen_stops_before_updating(
        self, mocker, handler, editor, recently_scanned_manager
    ):
        """With no display surface no indicators are updated."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.FILM_STRIP)
        handler.film_strip_controller_selections['stale'] = {}
        mocker.patch.object(pygame.display, 'get_surface', return_value=None)

        handler.indicators.render_visual_indicators()

        assert handler.film_strip_controller_selections == {'stale': {}}

    def test_updates_sliders_film_strips_and_canvas(
        self, handler, editor, recently_scanned_manager
    ):
        """One render places slider indicators, tracks film strip selections and redraws."""
        add_controller(editor=editor, controller_id=0, color=RED, mode=ControllerMode.R_SLIDER)
        add_controller(editor=editor, controller_id=1, color=GREEN, selection=('run', 1))
        add_controller(editor=editor, controller_id=2, color=BLUE, mode=ControllerMode.CANVAS)

        handler.indicators.render_visual_indicators()

        assert list(handler.slider_indicators) == [0]
        assert handler.film_strip_controller_selections == {
            'run': {1: {'controller_id': 1, 'frame': 1, 'color': GREEN}},
        }
        assert editor.canvas.redraw_count == 1


class TestSliderIndicatorSprites:
    """Test the slider indicator sprite helpers."""

    def test_created_sprite_is_centered_circle(self, handler, editor):
        """The sprite sits centered on the slider and draws a colored, white-ringed dot."""
        indicator = handler.indicators._create_slider_indicator_sprite(
            controller_id=0, color=GREEN, slider_rect=pygame.Rect(0, 0, 100, 20)
        )

        assert indicator.name == 'SliderIndicator_0'
        assert indicator.rect.topleft == (42, 2)
        assert indicator in editor.all_sprites
        assert indicator.image.get_colorkey()[:3] == BLACK
        assert indicator.image.get_at((8, 8))[:3] == GREEN
        assert indicator.image.get_at((8, 1))[:3] == WHITE
        assert indicator.image.get_at((0, 0))[:3] == BLACK

    def test_remove_slider_indicator_without_sprite_group(self, handler, editor):
        """Removing still forgets the indicator when the editor has no sprite group."""
        handler.slider_indicators[0] = handler.indicators._create_slider_indicator_sprite(
            controller_id=0, color=RED, slider_rect=pygame.Rect(0, 0, 100, 20)
        )
        del editor.all_sprites

        handler.indicators._remove_slider_indicator(controller_id=0)

        assert handler.slider_indicators == {}

    def test_remove_slider_indicator_for_unknown_controller(self, handler, editor):
        """Removing an indicator that does not exist changes nothing."""
        handler.indicators._remove_slider_indicator(controller_id=5)

        assert handler.slider_indicators == {}

    def test_remove_slider_indicator_without_tracking(self, handler, editor):
        """A handler without indicator tracking is left alone."""
        del handler.slider_indicators

        handler.indicators._remove_slider_indicator(controller_id=0)

        assert not hasattr(handler, 'slider_indicators')


class TestSliderIndicatorsWithCollisionAvoidance:
    """Test _update_all_slider_indicators and slider grouping."""

    def test_spreads_controllers_on_one_slider_in_color_order(self, handler, editor):
        """Controllers on one slider are spaced 20 px apart, red, green, blue, yellow, other."""
        add_controller(editor=editor, controller_id=0, color=PURPLE, mode=ControllerMode.G_SLIDER)
        add_controller(editor=editor, controller_id=1, color=YELLOW, mode=ControllerMode.G_SLIDER)
        add_controller(editor=editor, controller_id=2, color=BLUE, mode=ControllerMode.G_SLIDER)
        add_controller(editor=editor, controller_id=3, color=GREEN, mode=ControllerMode.G_SLIDER)
        add_controller(editor=editor, controller_id=4, color=RED, mode=ControllerMode.G_SLIDER)

        handler.indicators._update_all_slider_indicators()

        slider_center = editor.green_slider.rect.center
        centers_by_controller = {
            controller_id: indicator.rect.center
            for controller_id, indicator in handler.slider_indicators.items()
        }
        assert centers_by_controller == {
            4: (slider_center[0] - 40, slider_center[1]),
            3: (slider_center[0] - 20, slider_center[1]),
            2: (slider_center[0], slider_center[1]),
            1: (slider_center[0] + 20, slider_center[1]),
            0: (slider_center[0] + 40, slider_center[1]),
        }
        assert handler.slider_indicators[0].image.get_at((8, 8))[:3] == PURPLE

    def test_each_slider_gets_its_controllers(self, handler, editor):
        """Controllers on different sliders are centered on their own slider."""
        add_controller(editor=editor, controller_id=0, color=RED, mode=ControllerMode.R_SLIDER)
        add_controller(editor=editor, controller_id=1, color=BLUE, mode=ControllerMode.B_SLIDER)
        add_controller(editor=editor, controller_id=2, color=GREEN, mode=ControllerMode.A_SLIDER)

        handler.indicators._update_all_slider_indicators()

        assert handler.slider_indicators[0].rect.center == editor.red_slider.rect.center
        assert handler.slider_indicators[1].rect.center == editor.blue_slider.rect.center
        assert handler.slider_indicators[2].rect.center == editor.alpha_slider.rect.center

    def test_replaces_previous_indicators(self, handler, editor):
        """Old indicator sprites are removed from the sprite group before new ones are made."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.R_SLIDER)
        handler.indicators._update_all_slider_indicators()
        old_indicator = handler.slider_indicators[0]

        handler.indicators._update_all_slider_indicators()

        assert old_indicator not in editor.all_sprites
        assert len(editor.all_sprites) == 1

    def test_skips_inactive_unknown_and_non_slider_controllers(self, handler, editor):
        """Inactive, unregistered, non-slider and unknown controllers get no indicator."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.R_SLIDER).deactivate()
        add_controller(editor=editor, controller_id=1, mode=None)
        add_controller(editor=editor, controller_id=2, mode=ControllerMode.CANVAS)
        add_controller(editor=editor, controller_id=3, mode=ControllerMode.R_SLIDER)
        del editor.multi_controller_manager.controllers[3]

        handler.indicators._update_all_slider_indicators()

        assert handler.slider_indicators == {}

    def test_without_mode_switcher_creates_nothing(self, handler, editor):
        """With no mode switcher no controller is grouped onto a slider."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.R_SLIDER)
        del editor.mode_switcher

        handler.indicators._update_all_slider_indicators()

        assert handler.slider_indicators == {}

    @pytest.mark.parametrize(
        'slider_mode', ['a_slider', 'r_slider', 'g_slider', 'b_slider', 'x_slider']
    )
    def test_missing_slider_creates_nothing(self, handler, editor, slider_mode):
        """A slider mode with no slider on the editor creates no indicators."""
        del editor.alpha_slider
        del editor.red_slider
        del editor.green_slider
        del editor.blue_slider

        handler.indicators._create_slider_indicators_with_collision_avoidance(
            slider_mode=slider_mode,
            controllers=[{'controller_id': 0, 'color': RED}],
        )

        assert handler.slider_indicators == {}


class TestFilmStripControllerSelections:
    """Test _update_film_strip_controller_selections."""

    def test_groups_film_strip_controllers_by_animation(self, handler, editor):
        """Active, colored film strip controllers are grouped by their animation."""
        add_controller(editor=editor, controller_id=0, color=RED, selection=('walk', 2))
        add_controller(editor=editor, controller_id=1, color=GREEN, selection=('walk', 3))
        add_controller(editor=editor, controller_id=2, color=BLUE, selection=('run', 0))

        handler.indicators._update_film_strip_controller_selections()

        assert handler.film_strip_controller_selections == {
            'walk': {
                0: {'controller_id': 0, 'frame': 2, 'color': RED},
                1: {'controller_id': 1, 'frame': 3, 'color': GREEN},
            },
            'run': {2: {'controller_id': 2, 'frame': 0, 'color': BLUE}},
        }

    def test_skips_controllers_that_should_not_show(self, handler, editor):
        """Inactive, non-film-strip, unknown, gray and animation-less controllers are skipped."""
        add_controller(editor=editor, controller_id=0).deactivate()
        add_controller(editor=editor, controller_id=1, mode=ControllerMode.CANVAS)
        add_controller(editor=editor, controller_id=2, mode=None)
        add_controller(editor=editor, controller_id=3)
        del editor.multi_controller_manager.controllers[3]
        add_controller(editor=editor, controller_id=4, color=GRAY)
        add_controller(editor=editor, controller_id=5, selection=('', 0))

        handler.indicators._update_film_strip_controller_selections()

        assert handler.film_strip_controller_selections == {}

    def test_clears_stale_selections(self, handler, editor):
        """Selections from an earlier update are cleared."""
        handler.film_strip_controller_selections['stale'] = {}

        handler.indicators._update_film_strip_controller_selections()

        assert handler.film_strip_controller_selections == {}

    def test_without_controller_selections_only_clears(self, handler, editor):
        """An editor without controller selections leaves the map empty."""
        handler.film_strip_controller_selections['stale'] = {}
        del editor.controller_selections

        handler.indicators._update_film_strip_controller_selections()

        assert handler.film_strip_controller_selections == {}

    def test_without_mode_switcher_skips_all(self, handler, editor):
        """With no mode switcher no controller counts as in film strip mode."""
        add_controller(editor=editor, controller_id=0)
        del editor.mode_switcher

        handler.indicators._update_film_strip_controller_selections()

        assert handler.film_strip_controller_selections == {}

    def test_a_controller_moving_frames_marks_its_strip_dirty(self, handler, editor):
        """The strip re-renders the moved triangle right away (BUGS.md #154).

        A strip redraws only when dirty, and nothing marked it dirty when a controller moved,
        so the triangle lagged until the strip's preview next advanced.
        """
        selection = add_controller(editor=editor, controller_id=0, selection=('walk', 0))
        handler.indicators._update_film_strip_controller_selections()
        walk_marks_before = editor.film_strips['walk'].dirty_mark_count

        selection.set_frame(1)
        handler.indicators._update_film_strip_controller_selections()

        assert editor.film_strips['walk'].dirty_mark_count == walk_marks_before + 1
        assert editor.film_strips['run'].dirty_mark_count == 0

    def test_a_controller_moving_animations_marks_both_strips_dirty(self, handler, editor):
        """The strip it left drops its triangle and the strip it joined draws it."""
        selection = add_controller(editor=editor, controller_id=0, selection=('walk', 0))
        handler.indicators._update_film_strip_controller_selections()
        walk_marks_before = editor.film_strips['walk'].dirty_mark_count

        selection.set_selection('run', 0)
        handler.indicators._update_film_strip_controller_selections()

        assert editor.film_strips['walk'].dirty_mark_count == walk_marks_before + 1
        assert editor.film_strips['run'].dirty_mark_count == 1

    def test_unchanged_selections_leave_the_strips_alone(self, handler, editor):
        """An update with nothing moved does not make any strip re-render."""
        add_controller(editor=editor, controller_id=0, selection=('walk', 0))
        handler.indicators._update_film_strip_controller_selections()
        walk_marks_before = editor.film_strips['walk'].dirty_mark_count

        handler.indicators._update_film_strip_controller_selections()

        assert editor.film_strips['walk'].dirty_mark_count == walk_marks_before
        assert editor.film_strips['run'].dirty_mark_count == 0

    def test_selections_update_without_film_strips(self, handler, editor):
        """An editor with no film strips still gets its selections, with nothing to mark."""
        add_controller(editor=editor, controller_id=0, selection=('walk', 0))
        del editor.film_strips

        handler.indicators._update_film_strip_controller_selections()

        assert handler.film_strip_controller_selections == {
            'walk': {0: {'controller_id': 0, 'frame': 0, 'color': RED}},
        }


class TestCanvasIndicators:
    """Test _update_canvas_indicators."""

    def test_redraws_for_controller_in_canvas_mode(self, handler, editor):
        """An active canvas-mode controller at a valid position triggers a redraw."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.CANVAS)

        handler.indicators._update_canvas_indicators()

        assert editor.canvas.redraw_count == 1

    def test_no_redraw_without_canvas_controller(self, handler, editor):
        """No redraw when no controller qualifies for a canvas marker."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.CANVAS).deactivate()
        add_controller(editor=editor, controller_id=1, mode=ControllerMode.FILM_STRIP)
        add_controller(editor=editor, controller_id=2, mode=ControllerMode.CANVAS)
        del editor.multi_controller_manager.controllers[2]
        add_controller(editor=editor, controller_id=3, mode=ControllerMode.CANVAS)
        editor.mode_switcher.get_controller_position(3).is_valid = False

        handler.indicators._update_canvas_indicators()

        assert editor.canvas.redraw_count == 0

    def test_without_canvas_does_nothing(self, handler, editor):
        """An editor with no canvas is left alone."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.CANVAS)
        editor.canvas = None

        handler.indicators._update_canvas_indicators()

        assert editor.canvas is None

    def test_without_mode_switcher_no_redraw(self, handler, editor):
        """With no mode switcher no controller is in canvas mode."""
        add_controller(editor=editor, controller_id=0, mode=ControllerMode.CANVAS)
        del editor.mode_switcher

        handler.indicators._update_canvas_indicators()

        assert editor.canvas.redraw_count == 0


class TestRegisterNewControllers:
    """Test _register_new_controllers."""

    def test_keeps_existing_selection(self, handler, editor):
        """A controller that already has a selection is not replaced."""
        selection = add_controller(editor=editor, controller_id=0)
        selection.deactivate()

        handler.indicators._register_new_controllers()

        assert editor.controller_selections[0] is selection
        assert selection.is_active() is False

    def test_without_mode_switcher_registers_selection_only(self, handler, editor):
        """With no mode switcher the new controller still gets an active selection."""
        editor.multi_controller_manager.controllers[0] = ControllerInfo(
            controller_id=0, instance_id=0, status=ControllerStatus.CONNECTED
        )
        del editor.mode_switcher

        handler.indicators._register_new_controllers()

        assert editor.controller_selections[0].is_active()

    def test_without_manager_registers_nothing(self, handler, editor):
        """With no controller manager nothing is registered."""
        del editor.multi_controller_manager

        handler.indicators._register_new_controllers()

        assert editor.controller_selections == {}
