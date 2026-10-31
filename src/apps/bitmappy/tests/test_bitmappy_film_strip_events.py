"""Tests for bitmappy.film_strip_events: clicks, tabs, paste and selection colours."""

from types import SimpleNamespace

import pygame
import pytest

from bitmappy.controllers.manager import (
    ControllerInfo,
    ControllerStatus,
    MultiControllerManager,
)
from bitmappy.controllers.selection import ControllerSelection
from bitmappy.film_strip import FilmStripWidget, FilmTabWidget
from bitmappy.film_strip_coordinator import FilmStripCoordinator
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

FRAME_SIZE = 4


def make_frame(*, color: tuple[int, int, int, int] = (10, 20, 30, 255)) -> SpriteFrame:
    """Build a single-colour frame.

    Args:
        color: The frame's colour.

    Returns:
        The frame.

    """
    surface = pygame.Surface((FRAME_SIZE, FRAME_SIZE), pygame.SRCALPHA)
    surface.fill(color)
    frame = SpriteFrame(surface, duration=0.5)
    frame.pixels = [color] * (FRAME_SIZE * FRAME_SIZE)
    return frame


def make_animated_sprite(*, frame_counts: dict[str, int]) -> AnimatedSprite:
    """Build an animated sprite with the given number of frames per animation.

    Args:
        frame_counts: Animation name to frame count.

    Returns:
        The animated sprite.

    """
    animated_sprite = AnimatedSprite()
    for animation_name, frame_count in frame_counts.items():
        animated_sprite.add_animation(animation_name, [make_frame() for _ in range(frame_count)])
    return animated_sprite


def make_film_strip(*, frame_counts: dict[str, int] | None = None) -> FilmStripWidget:
    """Build a film strip showing the first animation of a fresh sprite.

    Args:
        frame_counts: Animation name to frame count (default: 'idle' with two frames).

    Returns:
        The film strip widget.

    """
    frame_counts = frame_counts or {'idle': 2}
    animated_sprite = make_animated_sprite(frame_counts=frame_counts)
    film_strip = FilmStripWidget(x=0, y=0, width=400, height=120)
    film_strip.set_animated_sprite(animated_sprite)
    film_strip.current_animation = next(iter(frame_counts))
    film_strip.current_frame = 0
    return film_strip


class RecordingCoordinator:
    """Film strip coordinator stand-in that records the animation operations it is asked for."""

    def __init__(self) -> None:
        """Start with no recorded operations."""
        self.deleted_animations: list[str] = []
        self.frame_deletion_dialogs: list[tuple[str, int]] = []

    def _delete_animation(self, animation_name: str) -> None:
        """Remember the animation that would be deleted."""
        self.deleted_animations.append(animation_name)

    def _show_delete_frame_confirmation(self, animation_name: str, frame_index: int) -> None:
        """Remember the frame whose deletion dialog would open."""
        self.frame_deletion_dialogs.append((animation_name, frame_index))


class CanvasStandIn:
    """Canvas stand-in with the dimensions and frame display the film strip uses."""

    def __init__(self, *, animated_sprite: AnimatedSprite) -> None:
        """Remember the sprite and start with nothing shown."""
        self.animated_sprite = animated_sprite
        self.pixels_across = FRAME_SIZE
        self.pixels_tall = FRAME_SIZE
        self.shown_frames: list[tuple[str, int]] = []

    def show_frame(self, animation_name: str, frame_index: int) -> None:
        """Remember the frame shown."""
        self.shown_frames.append((animation_name, frame_index))


@pytest.fixture
def isolated_controller_manager(mocker):
    """Give each test its own MultiControllerManager singleton.

    Returns:
        MultiControllerManager: A fresh manager with no controllers.

    """
    mocker.patch.object(MultiControllerManager, '_instance', None)
    return MultiControllerManager.get_instance()


class TestGetControllerSelectionColor:
    """Test FilmStripEventHandler.get_controller_selection_color."""

    def test_selecting_controller_unknown_to_the_manager_has_no_color(
        self,
        isolated_controller_manager,
    ):
        """A controller selecting the frame that the manager does not know gives no colour."""
        film_strip = make_film_strip()
        selection = ControllerSelection(controller_id=7, instance_id=70)
        selection.activate()
        selection.set_selection('idle', 1)
        film_strip.parent_scene = SimpleNamespace(controller_selections={7: selection})
        isolated_controller_manager.controllers[0] = ControllerInfo(
            controller_id=0,
            instance_id=10,
            status=ControllerStatus.ACTIVE,
            color=(0, 255, 0),
        )

        color = film_strip.event_handler.get_controller_selection_color('idle', 1)

        assert color is None

    def test_selecting_controller_known_to_the_manager_gives_its_color(
        self,
        isolated_controller_manager,
    ):
        """The colour comes from the manager's entry for the selecting controller."""
        film_strip = make_film_strip()
        selection = ControllerSelection(controller_id=1, instance_id=11)
        selection.activate()
        selection.set_selection('idle', 1)
        film_strip.parent_scene = SimpleNamespace(controller_selections={1: selection})
        for controller_id, color in ((0, (255, 0, 0)), (1, (0, 0, 255))):
            isolated_controller_manager.controllers[controller_id] = ControllerInfo(
                controller_id=controller_id,
                instance_id=10 + controller_id,
                status=ControllerStatus.ACTIVE,
                color=color,
            )

        assert film_strip.event_handler.get_controller_selection_color('idle', 1) == (0, 0, 255)


class TestPasteToCurrentFrame:
    """Test FilmStripEventHandler.paste_to_current_frame."""

    def test_paste_succeeds_when_the_scene_does_not_listen_for_pastes(self):
        """A parent scene without _on_frame_pasted still gets the pasted frame."""
        film_strip = make_film_strip()
        film_strip.copied_frame = make_frame(color=(200, 0, 0, 255))
        film_strip.current_frame = 1
        film_strip.parent_scene = SimpleNamespace()

        assert film_strip.event_handler.paste_to_current_frame() is True

        pasted_frame = film_strip.animated_sprite.animations['idle'][1]
        assert pasted_frame.pixels[0] == (200, 0, 0, 255)


class TestSetFrameIndex:
    """Test FilmStripEventHandler.set_frame_index."""

    def test_without_a_parent_canvas_only_the_strip_changes(self):
        """With no parent canvas the strip still moves to the frame."""
        film_strip = make_film_strip()
        film_strip.parent_canvas = None

        film_strip.event_handler.set_frame_index(1)

        assert film_strip.current_frame == 1


class TestHandleFrameClick:
    """Test FilmStripEventHandler.handle_frame_click."""

    def test_click_on_a_frame_names_it(self):
        """A click inside the second frame's rect returns that frame."""
        film_strip = make_film_strip()
        frame_rect = film_strip.frame_layouts['idle', 1]

        assert film_strip.event_handler.handle_frame_click(frame_rect.center) == ('idle', 1)

    def test_click_between_frames_hits_nothing(self):
        """A click inside the strip that misses every frame returns None."""
        film_strip = make_film_strip()
        miss_position = (1, film_strip.rect.height - 1)
        assert all(
            not frame_rect.collidepoint(miss_position)
            for frame_rect in film_strip.frame_layouts.values()
        )

        assert film_strip.event_handler.handle_frame_click(miss_position) is None


class TestHandleDeleteAnimationTabClick:
    """Test FilmStripEventHandler.handle_delete_animation_tab_click."""

    def test_last_animation_is_not_deleted(self):
        """The delete tab does nothing when the sprite has only one animation."""
        film_strip = make_film_strip()
        coordinator = RecordingCoordinator()
        film_strip.parent_scene = SimpleNamespace(
            canvas=CanvasStandIn(animated_sprite=film_strip.animated_sprite),
            film_strip_coordinator=coordinator,
        )

        film_strip.event_handler.handle_delete_animation_tab_click()

        assert coordinator.deleted_animations == []


def make_tab(*, insertion_type: str, target_frame_index: int) -> FilmTabWidget:
    """Build a film tab that inserts relative to a frame.

    Args:
        insertion_type: 'before' or 'after'.
        target_frame_index: The frame the tab sits next to.

    Returns:
        The tab.

    """
    tab = FilmTabWidget(x=0, y=0, width=10, height=10)
    tab.set_insertion_type(insertion_type, target_frame_index)
    return tab


class TestInsertFrameAtTab:
    """Test FilmStripEventHandler.insert_frame_at_tab."""

    def test_strip_without_a_sprite_inserts_nothing(self):
        """A film strip with no animated sprite ignores the tab."""
        film_strip = FilmStripWidget(x=0, y=0, width=400, height=120)

        film_strip.event_handler.insert_frame_at_tab(
            make_tab(insertion_type='after', target_frame_index=0),
        )

        assert film_strip.animated_sprite is None

    def test_unknown_current_animation_inserts_nothing(self):
        """A current animation the sprite does not have leaves every animation as it was."""
        film_strip = make_film_strip()
        film_strip.current_animation = 'missing'

        film_strip.event_handler.insert_frame_at_tab(
            make_tab(insertion_type='after', target_frame_index=0),
        )

        assert len(film_strip.animated_sprite.animations['idle']) == 2

    def test_without_a_parent_scene_inserts_nothing(self):
        """Without a parent scene there are no canvas dimensions, so no frame is made."""
        film_strip = make_film_strip()
        film_strip.parent_scene = None

        film_strip.event_handler.insert_frame_at_tab(
            make_tab(insertion_type='before', target_frame_index=0),
        )

        assert len(film_strip.animated_sprite.animations['idle']) == 2

    def test_scene_without_undo_tracking_still_gets_the_new_frame(self):
        """A scene with no operation tracker gets the blank frame, shown on its canvas."""
        film_strip = make_film_strip()
        canvas = CanvasStandIn(animated_sprite=film_strip.animated_sprite)
        selected_frames = []
        parent_scene = SimpleNamespace(
            canvas=canvas,
            _creating_frame=False,
            # The coordinator now hears of the insertion (BUGS.md #119) and reads this, which
            # the real editor sets in __init__ ('' until an animation is selected)
            selected_animation='',
            on_film_strip_frame_selected=lambda _strip, animation, frame: selected_frames.append(
                (animation, frame),
            ),
        )
        parent_scene.film_strip_coordinator = FilmStripCoordinator(parent_scene)  # type: ignore[arg-type]
        film_strip.parent_scene = parent_scene

        film_strip.event_handler.insert_frame_at_tab(
            make_tab(insertion_type='after', target_frame_index=0),
        )

        frames = film_strip.animated_sprite.animations['idle']
        assert len(frames) == 3
        assert frames[1].pixels == [(255, 0, 255, 255)] * (FRAME_SIZE * FRAME_SIZE)
        assert canvas.shown_frames == [('idle', 1)]
        assert parent_scene._creating_frame is False
        assert film_strip.selected_frame == 1
        assert selected_frames == [('idle', 1)]


class TestHandleRemovalButtonClick:
    """Test FilmStripEventHandler.handle_removal_button_click."""

    def test_click_without_a_parent_scene_is_consumed_without_a_dialog(self):
        """A valid removal button click with no scene reports a hit but opens nothing."""
        film_strip = make_film_strip()
        film_strip.parent_scene = None
        button_rect = pygame.Rect(10, 10, 8, 8)
        film_strip.removal_button_layouts = {('idle', 1): button_rect}

        assert film_strip.event_handler.handle_removal_button_click(button_rect.center) is True

        assert len(film_strip.animated_sprite.animations['idle']) == 2

    def test_click_with_a_parent_scene_opens_the_frame_deletion_dialog(self):
        """A valid removal button click asks the scene's coordinator to confirm the deletion."""
        film_strip = make_film_strip()
        coordinator = RecordingCoordinator()
        film_strip.parent_scene = SimpleNamespace(film_strip_coordinator=coordinator)
        button_rect = pygame.Rect(10, 10, 8, 8)
        film_strip.removal_button_layouts = {('idle', 1): button_rect}

        assert film_strip.event_handler.handle_removal_button_click(button_rect.center) is True

        assert coordinator.frame_deletion_dialogs == [('idle', 1)]
