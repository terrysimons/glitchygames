"""Test suite for bitmappy film strip functionality.

This module tests the film strip add/delete functionality, scroll behavior,
and integration with the bitmap editor scene.
"""

import pygame
import pytest
from src.apps.bitmappy.tests.film_strip_support import make_real_animated_sprite

from bitmappy.controllers.manager import MultiControllerManager
from bitmappy.editor import BitmapEditorScene
from bitmappy.film_strip import FilmStripDeleteTab, FilmStripTab, FilmStripWidget
from glitchygames.ui.dialogs import DeleteAnimationDialogScene

# Test constants to avoid magic values
TEST_SIZE_10 = 10
TEST_SIZE_20 = 20
TEST_SIZE_40 = 40
TEST_SIZE_2 = 2
TEST_SIZE_3 = 3


@pytest.fixture
def real_editor(mocker):
    """Build a real Bitmappy editor on the real display, with a fresh controller manager.

    The editor starts with one animation ('strip_1') of one blank frame.

    Returns:
        BitmapEditorScene: The editor.

    """
    mocker.patch.object(MultiControllerManager, '_instance', None)
    return BitmapEditorScene(options={})


def animation_names(editor):
    """Return the editor sprite's animation names, in order.

    Returns:
        list[str]: The names.

    """
    return list(editor.canvas.animated_sprite.animations)


def assert_scroll_shows_the_selected_strip(editor):
    """Check the scroll offset is in range and the selected animation's strip is visible."""
    strip_count = len(editor.film_strips)
    max_scroll = max(0, strip_count - editor.max_visible_strips)
    assert 0 <= editor.film_strip_scroll_offset <= max_scroll
    assert editor.film_strip_sprites[editor.selected_animation].visible


def add_strips(editor, *, count):
    """Add ``count`` new animations at the end, as the add-animation tab does."""
    for _ in range(count):
        editor.film_strip_coordinator._add_new_animation()


class TestFilmStripAddDeleteFunctionality:
    """Test film strip add/delete functionality."""

    def test_film_strip_tab_initialization(self):
        """Test FilmStripTab initialization."""
        # Act
        tab = FilmStripTab(x=10, y=20, width=40, height=10)

        # Assert
        assert tab.rect is not None
        assert tab.rect.x == TEST_SIZE_10
        assert tab.rect.y == TEST_SIZE_20
        assert tab.rect.width == TEST_SIZE_40
        assert tab.rect.height == TEST_SIZE_10
        assert tab.insertion_type == 'after'
        assert tab.target_frame_index == 0
        assert not tab.is_clicked
        assert not tab.is_hovered

    def test_film_strip_delete_tab_initialization(self):
        """Test FilmStripDeleteTab initialization."""
        # Act
        delete_tab = FilmStripDeleteTab(x=10, y=20, width=40, height=10)

        # Assert
        assert delete_tab.rect is not None
        assert delete_tab.rect.x == TEST_SIZE_10
        assert delete_tab.rect.y == TEST_SIZE_20
        assert delete_tab.rect.width == TEST_SIZE_40
        assert delete_tab.rect.height == TEST_SIZE_10
        assert delete_tab.insertion_type == 'delete'
        assert delete_tab.target_frame_index == 0
        assert not delete_tab.is_clicked
        assert not delete_tab.is_hovered

    def test_film_strip_tab_click_handling(self):
        """Test FilmStripTab click handling."""
        # Arrange
        tab = FilmStripTab(x=10, y=20, width=40, height=10)
        click_pos = (30, 25)  # Inside the tab

        # Act
        result = tab.handle_click(click_pos)

        # Assert
        assert result is True
        assert tab.is_clicked is True

    def test_film_strip_delete_tab_click_handling(self):
        """Test FilmStripDeleteTab click handling."""
        # Arrange
        delete_tab = FilmStripDeleteTab(x=10, y=20, width=40, height=10)
        click_pos = (30, 25)  # Inside the tab

        # Act
        result = delete_tab.handle_click(click_pos)

        # Assert
        assert result is True
        assert delete_tab.is_clicked is True

    def test_film_strip_tab_hover_handling(self):
        """Test FilmStripTab hover handling."""
        # Arrange
        tab = FilmStripTab(x=10, y=20, width=40, height=10)
        hover_pos = (30, 25)  # Inside the tab

        # Act
        tab.handle_hover(hover_pos)

        # Assert
        assert tab.is_hovered is True

    def test_film_strip_tab_reset_click_state(self):
        """Test FilmStripTab click state reset."""
        # Arrange
        tab = FilmStripTab(x=10, y=20, width=40, height=10)
        tab.is_clicked = True

        # Act
        tab.reset_click_state()

        # Assert
        assert tab.is_clicked is False

    def test_film_strip_tab_set_insertion_type(self):
        """Test FilmStripTab insertion type setting."""
        # Arrange
        tab = FilmStripTab(x=10, y=20, width=40, height=10)

        # Act
        tab.set_insertion_type('after', 2)

        # Assert
        assert tab.insertion_type == 'after'
        assert tab.target_frame_index == TEST_SIZE_2

    def test_film_strip_delete_tab_set_insertion_type(self):
        """Test FilmStripDeleteTab insertion type setting."""
        # Arrange
        delete_tab = FilmStripDeleteTab(x=10, y=20, width=40, height=10)

        # Act
        delete_tab.set_insertion_type('delete', 0)

        # Assert
        assert delete_tab.insertion_type == 'delete'
        assert delete_tab.target_frame_index == 0


class TestBitmapEditorFilmStripIntegration:
    """Test bitmap editor film strip integration, in a real editor."""

    def test_add_new_animation_creates_strip(self, real_editor):
        """Test that adding new animation creates a new film strip incrementally."""
        existing_strip = real_editor.film_strips['strip_1']

        real_editor.film_strip_coordinator._add_new_animation()

        assert animation_names(real_editor) == ['strip_1', 'strip_2']
        assert set(real_editor.film_strips) == {'strip_1', 'strip_2'}
        assert set(real_editor.film_strip_sprites) == {'strip_1', 'strip_2'}
        # Incremental: the existing strip is kept, not rebuilt
        assert real_editor.film_strips['strip_1'] is existing_strip
        # The new animation is selected and shown, so it can be edited right away
        assert real_editor.selected_animation == 'strip_2'
        assert real_editor.selected_frame == 0
        assert real_editor.canvas.current_animation == 'strip_2'

    def test_add_new_animation_with_insert_after_index(self, real_editor):
        """Test adding new animation at specific index."""
        add_strips(real_editor, count=1)

        # Insert after index 0 (between strip_1 and strip_2)
        real_editor.film_strip_coordinator._add_new_animation(insert_after_index=0)

        assert animation_names(real_editor) == ['strip_1', 'strip_3', 'strip_2']

    def test_delete_animation_removes_strip(self, real_editor):
        """Test that deleting animation removes the film strip."""
        add_strips(real_editor, count=1)

        real_editor.film_strip_coordinator._delete_animation('strip_1', confirmed=True)

        assert animation_names(real_editor) == ['strip_2']
        assert set(real_editor.film_strips) == {'strip_2'}
        assert set(real_editor.film_strip_sprites) == {'strip_2'}

    def test_delete_animation_prevents_last_strip_deletion(self, real_editor):
        """Test that deleting the last remaining strip is prevented."""
        last_strip = real_editor.film_strips['strip_1']

        real_editor.film_strip_coordinator._delete_animation('strip_1')

        assert animation_names(real_editor) == ['strip_1']
        assert real_editor.film_strips == {'strip_1': last_strip}
        # No confirmation dialog is offered either
        assert not isinstance(real_editor.next_scene, DeleteAnimationDialogScene)

    def test_unconfirmed_delete_asks_for_confirmation_first(self, real_editor):
        """Test that a delete without confirmation opens the dialog and deletes nothing yet."""
        add_strips(real_editor, count=1)

        real_editor.film_strip_coordinator._delete_animation('strip_2')

        assert animation_names(real_editor) == ['strip_1', 'strip_2']
        assert isinstance(real_editor.next_scene, DeleteAnimationDialogScene)

    def test_delete_animation_scroll_offset_calculation(self, real_editor):
        """Test that deleting the middle of three strips scrolls to show the selected strip."""
        add_strips(real_editor, count=2)

        real_editor.film_strip_coordinator._delete_animation('strip_2', confirmed=True)

        assert_scroll_shows_the_selected_strip(real_editor)

    def test_delete_animation_scroll_offset_last_strip(self, real_editor):
        """Test that deleting the last strip scrolls back to show the selected strip."""
        add_strips(real_editor, count=2)
        # Adding scrolled to the newest strip
        assert real_editor.film_strip_scroll_offset == 3 - real_editor.max_visible_strips

        real_editor.film_strip_coordinator._delete_animation('strip_3', confirmed=True)

        assert_scroll_shows_the_selected_strip(real_editor)

    def test_delete_animation_scroll_offset_many_strips(self, real_editor):
        """Test that deleting one of five strips scrolls to show the selected strip."""
        add_strips(real_editor, count=4)

        real_editor.film_strip_coordinator._delete_animation('strip_3', confirmed=True)

        assert animation_names(real_editor) == ['strip_1', 'strip_2', 'strip_4', 'strip_5']
        assert_scroll_shows_the_selected_strip(real_editor)

    def test_delete_animation_keeps_a_scroll_offset_that_is_still_valid(self, real_editor):
        """Test that a delete with no scrolling needed leaves the offset at 0."""
        add_strips(real_editor, count=1)
        real_editor.film_strip_scroll_offset = 0

        real_editor.film_strip_coordinator._delete_animation('strip_2', confirmed=True)

        assert real_editor.film_strip_scroll_offset == 0
        assert real_editor.film_strip_sprites['strip_1'].visible

    def test_delete_animation_switches_to_first_remaining(self, real_editor):
        """Test that deleting animation switches to first remaining animation."""
        add_strips(real_editor, count=2)

        real_editor.film_strip_coordinator._delete_animation('strip_2', confirmed=True)

        assert real_editor.selected_animation == 'strip_1'
        assert real_editor.selected_frame == 0
        assert real_editor.canvas.current_animation == 'strip_1'
        assert real_editor.canvas.current_frame == 0

    def test_adding_after_a_delete_does_not_replace_an_existing_animation(self, real_editor):
        """Test that a new animation added after a delete gets a name of its own."""
        add_strips(real_editor, count=2)
        real_editor.film_strip_coordinator._delete_animation('strip_1', confirmed=True)
        strip_3_frames = list(real_editor.canvas.animated_sprite.animations['strip_3'])

        real_editor.film_strip_coordinator._add_new_animation()

        assert len(animation_names(real_editor)) == 3
        assert real_editor.canvas.animated_sprite.animations['strip_3'] == strip_3_frames

    def test_inserting_after_a_delete_does_not_replace_an_existing_animation(self, real_editor):
        """Test that a strip inserted after a delete (the add tab's path) gets its own name."""
        add_strips(real_editor, count=2)
        real_editor.film_strip_coordinator._delete_animation('strip_1', confirmed=True)
        strip_3_frames = list(real_editor.canvas.animated_sprite.animations['strip_3'])

        real_editor.film_strip_coordinator._add_new_animation(insert_after_index=0)

        assert animation_names(real_editor) == ['strip_2', 'strip_4', 'strip_3']
        assert real_editor.canvas.animated_sprite.animations['strip_3'] == strip_3_frames
        assert real_editor.selected_animation == 'strip_4'

    def test_adding_to_a_loaded_sprite_does_not_replace_its_animation(self, real_editor):
        """Test that a new strip never takes a name a loaded sprite already uses."""
        loaded_sprite = make_real_animated_sprite(frame_counts={'strip_2': 2})
        real_editor.canvas.animated_sprite = loaded_sprite
        real_editor.film_strip_coordinator.on_sprite_loaded(loaded_sprite)
        loaded_frames = list(real_editor.canvas.animated_sprite.animations['strip_2'])

        real_editor.film_strip_coordinator._add_new_animation()

        assert animation_names(real_editor) == ['strip_2', 'strip_3']
        assert real_editor.canvas.animated_sprite.animations['strip_2'] == loaded_frames


class TestFilmStripWidgetIntegration:
    """Test film strip widget integration with tabs, in a real editor."""

    @pytest.fixture
    def editor_with_two_animations(self, real_editor):
        """Load 'test_animation' (two frames) and 'another_animation' (one frame).

        Returns:
            BitmapEditorScene: The editor.

        """
        real_editor.film_strip_coordinator.on_sprite_loaded(
            make_real_animated_sprite(
                frame_counts={'test_animation': 2, 'another_animation': 1},
            ),
        )
        return real_editor

    def test_film_strip_widget_creates_tabs(self, editor_with_two_animations):
        """Test that film strip widget creates appropriate tabs."""
        widget = editor_with_two_animations.film_strips['test_animation']

        widget._create_film_tabs()

        # One add tab, one delete tab (there is more than one animation) and the frame tabs
        assert sum(type(tab) is FilmStripTab for tab in widget.film_tabs) == 1
        assert sum(type(tab) is FilmStripDeleteTab for tab in widget.film_tabs) == 1
        assert len(widget.film_tabs) > TEST_SIZE_2

    def test_film_strip_widget_has_no_delete_tab_for_the_only_animation(self, real_editor):
        """Test that the only animation's strip offers no delete tab (it cannot be deleted)."""
        widget = real_editor.film_strips['strip_1']

        widget._create_film_tabs()

        assert any(type(tab) is FilmStripTab for tab in widget.film_tabs)
        assert not any(type(tab) is FilmStripDeleteTab for tab in widget.film_tabs)

    def test_film_strip_widget_handles_tab_clicks(self, editor_with_two_animations):
        """Test that clicking the add tab adds an animation after the strip's own."""
        widget = editor_with_two_animations.film_strips['test_animation']
        add_tab = next(tab for tab in widget.film_tabs if type(tab) is FilmStripTab)

        result = widget._handle_tab_click(add_tab.rect.center)

        assert result is True
        assert animation_names(editor_with_two_animations) == [
            'test_animation',
            'strip_3',
            'another_animation',
        ]

    def test_film_strip_widget_handles_delete_tab_clicks(self, editor_with_two_animations):
        """Test that clicking the delete tab asks to confirm deleting the strip's animation."""
        widget = editor_with_two_animations.film_strips['test_animation']
        delete_tab = next(tab for tab in widget.film_tabs if type(tab) is FilmStripDeleteTab)

        result = widget._handle_tab_click(delete_tab.rect.center)

        assert result is True
        dialog = editor_with_two_animations.next_scene
        assert isinstance(dialog, DeleteAnimationDialogScene)
        assert dialog.animation_name == 'test_animation'
        # Nothing is deleted until the dialog is confirmed
        assert 'test_animation' in animation_names(editor_with_two_animations)

    def test_film_strip_widget_no_tabs_without_frames(self):
        """Test that film strip widget doesn't create tabs without frames."""
        widget = FilmStripWidget(x=0, y=0, width=100, height=50)
        widget.set_animated_sprite(make_real_animated_sprite(frame_counts={'test_animation': 0}))

        widget._create_film_tabs()

        assert widget.film_tabs == []


class TestFilmStripAnimationTransitions:
    """Renaming or deleting an animation in Bitmappy keeps the sprite's transitions valid."""

    TOML = (
        '[sprite]\nname = "machine"\n\n'
        '[[animation]]\nnamespace = "idle"\n\n'
        '[[animation.frame]]\nnamespace = "idle"\nframe_index = 0\npixels = """\n#\n"""\n\n'
        # run is a one-shot animation with a non-default frame interval (BUGS.md #45)
        '[[animation]]\nnamespace = "run"\nframe_interval = 0.25\nloop = false\n\n'
        '[[animation.frame]]\nnamespace = "run"\nframe_index = 0\npixels = """\n#\n"""\n\n'
        '[[animation.frame]]\nnamespace = "run"\nframe_index = 1\npixels = """\n#\n"""\n\n'
        '[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n\n'
        '[[transition]]\nfrom = "idle"\nto = "run"\nwhen = "velocity_x > 0.1"\n\n'
        '[[transition]]\nfrom = "run"\nto = "idle"\nwhen = "velocity_x <= 0.1"\n'
    )

    # Three animations, so an undone delete must put the middle one back in place
    THREE_ANIMATION_TOML = (
        '[sprite]\nname = "machine"\n\n'
        '[[animation]]\nnamespace = "idle"\n\n'
        '[[animation.frame]]\nnamespace = "idle"\nframe_index = 0\npixels = """\n#\n"""\n\n'
        '[[animation]]\nnamespace = "run"\nframe_interval = 0.25\nloop = false\n\n'
        '[[animation.frame]]\nnamespace = "run"\nframe_index = 0\npixels = """\n#\n"""\n\n'
        '[[animation]]\nnamespace = "jump"\n\n'
        '[[animation.frame]]\nnamespace = "jump"\nframe_index = 0\npixels = """\n#\n"""\n\n'
        '[colors."#"]\nred = 200\ngreen = 0\nblue = 0\n\n'
        '[[transition]]\nfrom = "idle"\nto = "run"\nwhen = "velocity_x > 0.1"\n\n'
        '[[transition]]\nfrom = "idle"\nto = "jump"\nwhen = "velocity_y < 0"\n\n'
        '[[transition]]\nfrom = "run"\nto = "idle"\nwhen = "velocity_x <= 0.1"\n\n'
        '[[transition]]\nfrom = "jump"\nto = "idle"\nwhen = "on_ground"\n'
    )

    def _scene_with_real_sprite(self, mocker, tmp_path, toml_text=None):
        from glitchygames.sprites import AnimatedSprite

        mocker.patch('bitmappy.editor_setup.EditorSetup.setup_canvas')
        scene = BitmapEditorScene({})
        sprite_file = tmp_path / 'machine.toml'
        sprite_file.write_text(self.TOML if toml_text is None else toml_text, encoding='utf-8')
        scene.canvas = mocker.Mock()
        scene.canvas.animated_sprite = AnimatedSprite(str(sprite_file))
        return scene

    def test_renaming_an_animation_renames_its_transitions(self, mocker, tmp_path):
        """on_animation_rename renames the animation in the sprite's transitions too."""
        scene = self._scene_with_real_sprite(mocker, tmp_path)
        coordinator = scene.film_strip_coordinator

        coordinator._rename_animation_in_sprite(scene.canvas.animated_sprite, 'run', 'sprint')

        assert scene.canvas.animated_sprite.transition_data == [
            {'from': 'idle', 'to': 'sprint', 'when': 'velocity_x > 0.1'},
            {'from': 'sprint', 'to': 'idle', 'when': 'velocity_x <= 0.1'},
        ]

    def test_deleting_an_animation_drops_its_transitions(self, mocker, tmp_path):
        """Deleting an animation drops the transitions from or to it (with a warning)."""
        scene = self._scene_with_real_sprite(mocker, tmp_path)
        coordinator = scene.film_strip_coordinator
        coordinator.on_sprite_loaded = mocker.Mock()
        scene.update_film_strip_visibility = mocker.Mock()
        scene.update_scroll_arrows = mocker.Mock()
        scene.canvas.show_frame = mocker.Mock()
        mocker.patch.object(coordinator, '_select_animation_after_deletion')

        coordinator._delete_animation('run', confirmed=True)

        assert 'run' not in scene.canvas.animated_sprite._animations
        assert scene.canvas.animated_sprite.transition_data == []

    def test_undoing_an_animation_delete_restores_its_transitions_and_settings(
        self, mocker, tmp_path
    ):
        """Undo puts back the animation, its place, settings and dropped transitions; redo drops."""
        import tomllib

        scene = self._scene_with_real_sprite(mocker, tmp_path, self.THREE_ANIMATION_TOML)
        sprite = scene.canvas.animated_sprite
        coordinator = scene.film_strip_coordinator
        coordinator.on_sprite_loaded = mocker.Mock()
        mocker.patch.object(coordinator, '_select_animation_after_deletion')
        original_transitions = [dict(transition) for transition in sprite.transition_data]
        transitions_without_run = [
            {'from': 'idle', 'to': 'jump', 'when': 'velocity_y < 0'},
            {'from': 'jump', 'to': 'idle', 'when': 'on_ground'},
        ]

        coordinator._delete_animation('run', confirmed=True)
        assert list(sprite._animations) == ['idle', 'jump']
        assert sprite.animation_order == ['idle', 'jump']
        assert sprite.transition_data == transitions_without_run
        assert 'run' not in sprite._loop_flags
        assert 'run' not in sprite._animation_frame_intervals

        assert scene.undo_redo_manager.undo() is True
        assert list(sprite._animations) == ['idle', 'run', 'jump']
        assert tuple(sprite._animations['run'][0].image.get_at((0, 0)))[:3] == (200, 0, 0)
        assert sprite._animations['run'][0].duration == pytest.approx(0.25)
        assert sprite.animation_order == ['idle', 'run', 'jump']
        assert sprite.transition_data == original_transitions
        assert sprite._loop_flags['run'] is False
        assert sprite._animation_frame_intervals['run'] == pytest.approx(0.25)
        saved_file = tmp_path / 'restored.toml'
        sprite.save(str(saved_file), 'toml')
        saved = tomllib.loads(saved_file.read_text(encoding='utf-8'))
        assert [animation['namespace'] for animation in saved['animation']] == [
            'idle',
            'run',
            'jump',
        ]
        assert saved['animation'][1]['loop'] is False
        assert saved['transition'] == original_transitions

        assert scene.undo_redo_manager.redo() is True
        assert list(sprite._animations) == ['idle', 'jump']
        assert sprite.animation_order == ['idle', 'jump']
        assert sprite.transition_data == transitions_without_run
        assert 'run' not in sprite._loop_flags

        assert scene.undo_redo_manager.undo() is True
        assert sprite.transition_data == original_transitions

    def test_renaming_an_animation_moves_its_loop_flag_and_frame_interval(self, mocker, tmp_path):
        """The loop flag and frame interval follow a renamed animation (BUGS.md #45)."""
        import tomllib

        scene = self._scene_with_real_sprite(mocker, tmp_path)
        sprite = scene.canvas.animated_sprite

        scene.film_strip_coordinator._rename_animation_in_sprite(sprite, 'run', 'sprint')

        assert sprite._loop_flags == {'idle': True, 'sprint': False}
        assert sprite._animation_frame_intervals == {'idle': 0.5, 'sprint': 0.25}
        # The renamed animation keeps its place in the animation order
        assert list(sprite._animations) == ['idle', 'sprint']
        assert sprite.animation_order == ['idle', 'sprint']

        # The runtime honours the moved loop flag: a one-shot animation stops on its last frame
        sprite.play(animation_name='sprint')
        assert sprite.is_looping is False
        sprite.update(dt=0.3)
        sprite.update(dt=0.3)
        assert sprite.current_frame == 1
        assert sprite.is_playing is False

        saved_file = tmp_path / 'renamed.toml'
        sprite.save(str(saved_file), 'toml')
        saved_animations = {
            animation['namespace']: animation
            for animation in tomllib.loads(saved_file.read_text(encoding='utf-8'))['animation']
        }
        assert list(saved_animations) == ['idle', 'sprint']
        assert saved_animations['sprint']['loop'] is False
        assert saved_animations['sprint']['frame_interval'] == pytest.approx(0.25)

    def test_renaming_the_current_animation_keeps_it_current(self, mocker, tmp_path):
        """Renaming the animation the sprite is showing points the sprite at the new name."""
        scene = self._scene_with_real_sprite(mocker, tmp_path)
        sprite = scene.canvas.animated_sprite
        sprite.set_animation('run')
        sprite.set_frame(1)

        scene.film_strip_coordinator._rename_animation_in_sprite(sprite, 'run', 'sprint')

        assert sprite.current_animation == 'sprint'
        assert sprite.current_frame == 1

    def test_renaming_onto_an_existing_animation_is_refused(self, mocker, tmp_path):
        """Renaming to a name already in use keeps both animations (and records no undo)."""
        scene = self._scene_with_real_sprite(mocker, tmp_path)
        sprite = scene.canvas.animated_sprite
        idle_frames = sprite._animations['idle']

        scene.on_animation_rename('run', 'idle')

        assert list(sprite._animations) == ['idle', 'run']
        assert sprite._animations['idle'] is idle_frames
        assert scene.undo_redo_manager.can_undo() is False

    def test_undoing_an_animation_rename_restores_the_old_name_and_its_data(self, mocker, tmp_path):
        """Undo restores the old name, loop flag, interval and transitions; redo renames again."""
        scene = self._scene_with_real_sprite(mocker, tmp_path)
        sprite = scene.canvas.animated_sprite

        scene.on_animation_rename('run', 'sprint')
        assert list(sprite._animations) == ['idle', 'sprint']

        assert scene.undo_redo_manager.undo() is True
        assert list(sprite._animations) == ['idle', 'run']
        assert sprite._loop_flags == {'idle': True, 'run': False}
        assert sprite._animation_frame_intervals == {'idle': 0.5, 'run': 0.25}
        assert sprite.transition_data == [
            {'from': 'idle', 'to': 'run', 'when': 'velocity_x > 0.1'},
            {'from': 'run', 'to': 'idle', 'when': 'velocity_x <= 0.1'},
        ]

        assert scene.undo_redo_manager.redo() is True
        assert list(sprite._animations) == ['idle', 'sprint']
        assert sprite._loop_flags == {'idle': True, 'sprint': False}
        assert sprite._animation_frame_intervals == {'idle': 0.5, 'sprint': 0.25}
        assert sprite.transition_data[0] == {
            'from': 'idle',
            'to': 'sprint',
            'when': 'velocity_x > 0.1',
        }


class TestFilmStripFrameDeleteUndo:
    """Undoing a Bitmappy frame delete puts the frame back; redoing deletes it again."""

    # Three frames in run with different colors; the middle one has its own interval, an
    # explicit hitbox and a half-transparent pixel, so the restore must keep all of them
    TOML = (
        '[sprite]\nname = "runner"\n\n'
        '[[animation]]\nnamespace = "run"\n\n'
        '[[animation.frame]]\nnamespace = "run"\nframe_index = 0\npixels = """\n##\n"""\n\n'
        '[[animation.frame]]\nnamespace = "run"\nframe_index = 1\nframe_interval = 0.3\n'
        'pixels = """\n%@\n"""\n\n'
        '[animation.frame.hitbox]\noffset_x = 1\noffset_y = 0\nwidth = 1\nheight = 1\n\n'
        '[[animation.frame]]\nnamespace = "run"\nframe_index = 2\npixels = """\n&&\n"""\n\n'
        '[colors."#"]\nred = 10\ngreen = 0\nblue = 0\n\n'
        '[colors."%"]\nred = 0\ngreen = 200\nblue = 0\n\n'
        '[colors."@"]\nred = 0\ngreen = 0\nblue = 200\nalpha = 128\n\n'
        '[colors."&"]\nred = 30\ngreen = 30\nblue = 30\n'
    )

    def _scene_with_film_strip(self, mocker, tmp_path):
        """Return an editor scene and a film strip widget showing a real three-frame sprite.

        Returns:
            tuple: The scene and the film strip widget.

        """
        from glitchygames.sprites import AnimatedSprite

        mocker.patch('bitmappy.editor_setup.EditorSetup.setup_canvas')
        scene = BitmapEditorScene({})
        sprite_file = tmp_path / 'runner.toml'
        sprite_file.write_text(self.TOML, encoding='utf-8')
        scene.canvas = mocker.Mock()
        scene.canvas.animated_sprite = AnimatedSprite(str(sprite_file))
        scene.canvas.current_animation = 'run'
        scene.canvas.current_frame = 0
        # No pan gesture in progress, as on a real canvas (a Mock attribute would look like one)
        scene.canvas.pan_session = None
        widget = FilmStripWidget(x=0, y=0, width=400, height=100)
        widget.parent_scene = scene
        widget.set_animated_sprite(scene.canvas.animated_sprite)
        return scene, widget

    @staticmethod
    def _assert_middle_frame_restored(frames):
        """Assert the deleted middle frame is back at index 1 with all its data."""
        assert len(frames) == TEST_SIZE_3
        restored_frame = frames[1]
        assert restored_frame.pixels == [(0, 200, 0, 255), (0, 0, 200, 128)]
        assert tuple(restored_frame.image.get_at((0, 0))) == (0, 200, 0, 255)
        assert tuple(restored_frame.image.get_at((1, 0))) == (0, 0, 200, 128)
        assert restored_frame.duration == pytest.approx(0.3)
        assert restored_frame.has_explicit_hitbox is True
        assert restored_frame.hitbox == pygame.Rect(1, 0, 1, 1)
        assert tuple(frames[0].image.get_at((0, 0)))[:3] == (10, 0, 0)
        assert tuple(frames[2].image.get_at((0, 0)))[:3] == (30, 30, 30)

    def test_undoing_a_frame_delete_restores_the_frame_in_place(self, mocker, tmp_path):
        """Undo puts the frame's pixels, duration and hitbox back at its index; redo deletes."""
        import tomllib

        scene, widget = self._scene_with_film_strip(mocker, tmp_path)
        sprite = scene.canvas.animated_sprite
        frames = sprite._animations['run']
        third_frame = frames[2]

        widget.event_handler.remove_frame(animation_name='run', frame_index=1)
        assert len(frames) == TEST_SIZE_2
        assert frames[1] is third_frame

        assert scene.undo_redo_manager.undo() is True
        self._assert_middle_frame_restored(frames)
        saved_file = tmp_path / 'restored.toml'
        sprite.save(str(saved_file), 'toml')
        saved_frames = tomllib.loads(saved_file.read_text(encoding='utf-8'))['animation'][0][
            'frame'
        ]
        assert len(saved_frames) == TEST_SIZE_3
        assert saved_frames[1]['hitbox'] == {'offset_x': 1, 'offset_y': 0, 'width': 1, 'height': 1}

        assert scene.undo_redo_manager.redo() is True
        assert len(frames) == TEST_SIZE_2
        assert frames[1] is third_frame

        assert scene.undo_redo_manager.undo() is True
        self._assert_middle_frame_restored(frames)

    def test_a_film_strip_delete_moves_the_editor_selection_back(self, mocker, tmp_path):
        """Deleting a frame through the film strip reaches the coordinator (BUGS.md #119).

        The film strip asked the editor scene for on_frame_removed, which only the coordinator
        has, so the editor's selected frame kept pointing past the deleted frame.
        """
        scene, widget = self._scene_with_film_strip(mocker, tmp_path)
        scene.selected_animation = 'run'
        scene.selected_frame = 2

        widget.event_handler.remove_frame(animation_name='run', frame_index=1)

        assert scene.selected_frame == 1
        scene.canvas.show_frame.assert_called_with('run', 1)

    def test_undoing_a_frame_delete_restores_a_frame_without_a_pixel_list(self, mocker, tmp_path):
        """A frame known only by its surface (empty pixels list) is restored from that surface."""
        from glitchygames.sprites.animated import SpriteFrame

        scene, widget = self._scene_with_film_strip(mocker, tmp_path)
        frames = scene.canvas.animated_sprite._animations['run']
        surface = pygame.Surface((2, 1), pygame.SRCALPHA)
        surface.fill((90, 80, 70, 255))
        frames.insert(1, SpriteFrame(surface, duration=0.7))

        widget.event_handler.remove_frame(animation_name='run', frame_index=1)
        assert len(frames) == TEST_SIZE_3

        assert scene.undo_redo_manager.undo() is True
        assert len(frames) == TEST_SIZE_3 + 1
        assert tuple(frames[1].image.get_at((1, 0))) == (90, 80, 70, 255)
        assert frames[1].duration == pytest.approx(0.7)
        assert frames[1].has_explicit_hitbox is False

    def test_editor_undo_and_redo_restore_and_delete_the_frame(self, mocker, tmp_path):
        """The editor's undo and redo actions (Ctrl+Z / Ctrl+Y) undo and redo a frame delete."""
        scene, widget = self._scene_with_film_strip(mocker, tmp_path)
        frames = scene.canvas.animated_sprite._animations['run']
        third_frame = frames[2]

        widget.event_handler.remove_frame(animation_name='run', frame_index=1)
        scene.handle_undo()
        self._assert_middle_frame_restored(frames)

        scene.handle_redo()
        assert len(frames) == TEST_SIZE_2
        assert frames[1] is third_frame
