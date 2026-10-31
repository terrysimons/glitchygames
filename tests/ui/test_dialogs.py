"""Test suite for UI Dialog components.

This module consolidates tests from:
- test_ui_dialogs.py: Dialog scene functionality
- test_dialogs_coverage.py: Coverage tests for dialogs module
- test_dialogs_deeper_coverage.py: Deeper coverage tests for dialogs module
- test_confirm_dialog_coverage.py: ConfirmDialog coverage tests
- test_input_dialog_coverage.py: InputDialog coverage tests

Every dialog here is real: real scenes on the real display, real sprite groups, real fonts
(through FontManager) and real pygame events. Drawing is checked by reading the pixels drawn.
The previous scene is a real Scene; only its canvas (the Bitmappy editor's, which these
dialogs hand file names to) is a small recording stand-in.
"""

import logging
import shutil
import sys
from pathlib import Path, PureWindowsPath

import pygame
import pytest

from glitchygames.events.base import HashableEvent
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.scenes import Scene
from glitchygames.ui import ConfirmDialog, InputDialog
from glitchygames.ui.dialogs import (
    DeleteAnimationDialogScene,
    DeleteFrameDialogScene,
    InputConfirmationDialogScene,
    LoadDialogScene,
    NewCanvasDialogScene,
    SaveDialogScene,
    _file_name_problem,
    _get_load_path,
    _get_save_path,
)
from glitchygames.user_files import install_user_files, installed_user_files

# Test constants from test_confirm_dialog_coverage.py
TEST_CONFIRM_DIALOG_X = 50
TEST_CONFIRM_DIALOG_Y = 50
TEST_CONFIRM_DIALOG_WIDTH = 300
TEST_CONFIRM_DIALOG_HEIGHT = 100
CONFIRM_BUTTON_WIDTH = 80
CONFIRM_BUTTON_HEIGHT = 30
BUTTON_SPACING = 20

# ConfirmDialog.render's colours
CONFIRM_BACKGROUND_COLOR = (40, 40, 40)
CONFIRM_BORDER_COLOR = (100, 100, 100)
YES_BUTTON_COLOR = (40, 100, 40)
YES_BUTTON_HOVER_COLOR = (60, 120, 60)
YES_BUTTON_BORDER_COLOR = (80, 140, 80)
NO_BUTTON_COLOR = (100, 40, 40)
NO_BUTTON_HOVER_COLOR = (120, 60, 60)
NO_BUTTON_BORDER_COLOR = (140, 80, 80)

# Test constants from test_input_dialog_coverage.py
TEST_INPUT_DIALOG_X = 100
TEST_INPUT_DIALOG_Y = 100
TEST_INPUT_DIALOG_WIDTH = 400
TEST_INPUT_DIALOG_HEIGHT = 200

# InputDialog.update's colours
INPUT_DIALOG_BACKGROUND_COLOR = (0, 0, 0)
INPUT_DIALOG_BORDER_COLOR = (128, 128, 128)

# A colour no widget draws, filled in first so a test can tell what was drawn over it
MARKER_COLOR = (1, 2, 3)

# Text pixels: every channel above this (white text, antialiased edges excluded)
TEXT_CHANNEL_THRESHOLD = 200


class _RecordingCanvas:
    """Stands in for the Bitmappy canvas: records the paths the dialogs hand it."""

    def __init__(self):
        self.loaded_paths = []
        self.saved_paths = []
        self.save_error = None

    def on_load_file_event(self, path):
        self.loaded_paths.append(path)

    def on_save_file_event(self, path):
        if self.save_error is not None:
            raise self.save_error
        self.saved_paths.append(path)


class _RecordingDebugText:
    """Stands in for the editor's debug text box: holds the message shown."""

    def __init__(self):
        self.text = ''


class _RecordingUserFiles:
    """Stands in for a browser's user files: records the files handed to the player."""

    def __init__(self):
        self.saved_files = []

    def open_file(self, *, accepted_extensions, on_opened):
        raise AssertionError((accepted_extensions, on_opened))

    def save_file(self, *, path):
        self.saved_files.append(path)


class _PreviousScene(Scene):
    """A real scene for the dialogs to return to, with a recording canvas."""

    NAME = 'PreviousScene'

    def __init__(self, options=None, groups=None):
        super().__init__(options=options, groups=groups)
        self.canvas = _RecordingCanvas()
        self.new_file_dimensions = []

    def on_new_file_event(self, dimensions):
        self.new_file_dimensions.append(dimensions)


@pytest.fixture(autouse=True)
def restore_key_repeat():
    """InputBox.on_key_up_event calls pygame.key.set_repeat; put the real setting back."""
    delay, interval = pygame.key.get_repeat()
    yield
    pygame.key.set_repeat(delay, interval)


@pytest.fixture
def previous_scene():
    """A real previous scene with one sprite in its group.

    Returns:
        _PreviousScene: The scene.
    """
    scene = _PreviousScene(groups=pygame.sprite.LayeredDirty())
    sprite = pygame.sprite.DirtySprite(scene.all_sprites)
    sprite.image = pygame.Surface((4, 4))
    sprite.rect = sprite.image.get_rect()
    sprite.dirty = 0
    return scene


def _key_down(key, unicode='', mod=0):
    """Build a real key down event.

    Returns:
        HashableEvent: The event.
    """
    return HashableEvent(pygame.KEYDOWN, key=key, unicode=unicode, mod=mod)


def _key_up(key, mod=0):
    """Build a real key up event.

    Returns:
        HashableEvent: The event.
    """
    return HashableEvent(pygame.KEYUP, key=key, mod=mod)


def _mouse_up(position):
    """Build a real left mouse button up event.

    Returns:
        HashableEvent: The event.
    """
    return HashableEvent(pygame.MOUSEBUTTONUP, pos=position, button=1)


def _type_text(scene, text):
    """Type text into a scene, one real key-down per character."""
    for character in text:
        scene.on_key_down_event(_key_down(key=ord(character.lower()), unicode=character))


def _install_mouse_position(position):
    """Make this frame's polled mouse position (current_input()) the given one."""
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(),
            modifiers=0,
            mouse_position=position,
            mouse_buttons=(False, False, False),
            mouse_focused=True,
        ),
    )


def _rgb_at(surface, position):
    """Return the RGB colour of one pixel (the alpha is not the point here).

    Returns:
        tuple: The (red, green, blue) colour.
    """
    return tuple(surface.get_at(position))[:3]


def _text_pixel_count(surface, area):
    """Count the near-white (text) pixels inside an area of a surface.

    Returns:
        int: The number of text pixels.
    """
    rgb_pixels = pygame.surfarray.array3d(surface.subsurface(area))
    return int((rgb_pixels > TEXT_CHANNEL_THRESHOLD).all(axis=2).sum())


# ============================================================================
# From test_ui_dialogs.py
# ============================================================================


class TestInputConfirmationDialogScene:
    """Test InputConfirmationDialogScene functionality."""

    def test_input_confirmation_dialog_scene_init(self, previous_scene):
        """The scene builds a real InputDialog, half the screen's size, centred on it."""
        scene = InputConfirmationDialogScene(previous_scene=previous_scene)

        screen_rect = pygame.display.get_surface().get_rect()
        assert isinstance(scene.dialog, InputDialog)
        assert scene.dialog.rect.size == (screen_rect.width // 2, screen_rect.height // 2)
        assert scene.dialog.rect.center == screen_rect.center
        assert scene.dialog.dialog_text_sprite.text_box.text == scene.DIALOG_TEXT
        assert scene.dialog.dialog_text_sprite.border_width == 0
        assert scene.dialog.cancel_button.name == scene.CANCEL_TEXT
        assert scene.dialog.confirm_button.name == scene.CONFIRMATION_TEXT
        assert scene.dialog.input_box in scene.all_sprites

    def test_input_confirmation_dialog_text_submission(self, previous_scene, caplog):
        """A text submission is logged and leaves the dialog open."""
        scene = InputConfirmationDialogScene(previous_scene=previous_scene)

        with caplog.at_level(logging.INFO):
            scene.on_text_submit_event('Submitted Text')

        assert "Text submitted: 'Submitted Text'" in caplog.text
        assert scene.next_scene is None

    def test_input_confirmation_dialog_cancellation(self, previous_scene):
        """Releasing Escape in the active input box deactivates it; the dialog stays open."""
        scene = InputConfirmationDialogScene(previous_scene=previous_scene)
        assert scene.dialog.input_box.is_active is True

        scene.on_key_up_event(_key_up(pygame.K_ESCAPE))

        assert scene.dialog.input_box.is_active is False
        assert scene.next_scene is None

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "InputBox.on_key_down_event appends a key-down's unicode for every key but Return, "
            "Backspace and Shift+;: Escape's key-down (unicode '\\x1b', as pygame delivers it) "
            'adds an invisible escape character to the typed file name'
        ),
    )
    def test_escape_key_down_types_nothing(self, previous_scene):
        """Pressing Escape in the input box must not add a character to it."""
        scene = InputConfirmationDialogScene(previous_scene=previous_scene)

        scene.on_key_down_event(_key_down(pygame.K_ESCAPE, unicode='\x1b'))

        assert not scene.dialog.input_box.text

    def test_dialog_scene_draws_its_dialog_on_the_display(self, previous_scene):
        """Drawing the scene's sprites puts the dialog's border at its rect on the display."""
        scene = InputConfirmationDialogScene(previous_scene=previous_scene)
        scene.setup()
        screen = pygame.display.get_surface()
        # LayeredDirty's first draw paints its background over the whole screen
        background = pygame.Surface(screen.get_size())
        background.fill(MARKER_COLOR)

        scene.all_sprites.update()
        scene.all_sprites.draw(screen, bgd=background)

        dialog_rect = scene.dialog.rect
        assert _rgb_at(screen, dialog_rect.topleft) == INPUT_DIALOG_BORDER_COLOR
        assert _rgb_at(screen, (dialog_rect.left + 2, dialog_rect.top + 2)) == (
            INPUT_DIALOG_BACKGROUND_COLOR
        )
        # Nothing is drawn outside the dialog
        assert _rgb_at(screen, (dialog_rect.left - 1, dialog_rect.top)) == MARKER_COLOR
        assert _rgb_at(screen, (dialog_rect.right, dialog_rect.bottom)) == MARKER_COLOR


class TestDialogScenesUseTheirGroups:
    """The New, Load and Save dialog scenes keep the sprite group they are given (BUGS.md #135)."""

    @pytest.mark.parametrize(
        'scene_class', [NewCanvasDialogScene, LoadDialogScene, SaveDialogScene]
    )
    def test_dialog_scene_uses_the_given_group(self, previous_scene, scene_class):
        """The scene's sprites go in the group passed in, not in a new one."""
        groups = pygame.sprite.LayeredDirty()

        scene = scene_class(previous_scene=previous_scene, groups=groups)

        assert scene.all_sprites is groups
        assert scene.dialog in groups


class TestLoadDialogScene:
    """Test LoadDialogScene functionality."""

    def test_load_dialog_scene_init(self, previous_scene):
        """Test LoadDialogScene initialization."""
        scene = LoadDialogScene(previous_scene=previous_scene)

        assert scene.previous_scene is previous_scene
        assert scene.dialog.dialog_text_sprite.text_box.text == 'Enter filename to load:'
        assert scene.dialog.confirm_button.name == 'Load'

    def test_load_dialog_file_selection(self, previous_scene):
        """Confirming hands the typed file name to the canvas and returns to the scene."""
        scene = LoadDialogScene(previous_scene=previous_scene)
        scene.dialog.input_box.text = 'test_file.toml'

        scene.on_confirm_event(_mouse_up((0, 0)), scene.dialog.confirm_button)

        assert previous_scene.canvas.loaded_paths == ['test_file.toml']
        assert scene.next_scene is previous_scene

    def test_load_dialog_cancellation(self, previous_scene):
        """Releasing Escape deactivates the input box without loading anything."""
        scene = LoadDialogScene(previous_scene=previous_scene)

        scene.on_key_up_event(_key_up(pygame.K_ESCAPE))

        assert scene.dialog.input_box.is_active is False
        assert previous_scene.canvas.loaded_paths == []


class TestSaveDialogScene:
    """Test SaveDialogScene functionality."""

    def test_save_dialog_scene_init(self, previous_scene):
        """Test SaveDialogScene initialization."""
        scene = SaveDialogScene(previous_scene=previous_scene)

        assert scene.previous_scene is previous_scene
        assert scene.dialog.dialog_text_sprite.text_box.text == 'Enter filename to save:'
        assert scene.dialog.confirm_button.name == 'Save'

    def test_save_dialog_filename_input(self, previous_scene):
        """A file name typed as key-downs lands in the input box."""
        scene = SaveDialogScene(previous_scene=previous_scene)

        _type_text(scene, 'new_file')

        assert scene.dialog.input_box.text == 'new_file'

    def test_save_dialog_ignores_text_input_events(self, previous_scene):
        """TEXTINPUT events type nothing (the input box takes text from key-downs)."""
        scene = SaveDialogScene(previous_scene=previous_scene)

        for character in 'new_file':
            scene.on_text_input_event(HashableEvent(pygame.TEXTINPUT, text=character))

        assert not scene.dialog.input_box.text

    def test_save_dialog_save_confirmation(self, previous_scene):
        """Confirming hands the typed file name to the canvas and returns to the scene."""
        scene = SaveDialogScene(previous_scene=previous_scene)
        scene.dialog.input_box.text = 'test_file.toml'

        scene.on_confirm_event(_mouse_up((0, 0)), scene.dialog.confirm_button)

        assert previous_scene.canvas.saved_paths == ['test_file.toml']
        assert scene.next_scene is previous_scene


class TestNewCanvasDialogScene:
    """Test NewCanvasDialogScene functionality."""

    def test_new_canvas_dialog_scene_init(self, previous_scene):
        """Test NewCanvasDialogScene initialization."""
        scene = NewCanvasDialogScene(previous_scene=previous_scene)

        assert scene.previous_scene is previous_scene
        assert scene.dialog.dialog_text_sprite.text_box.text == 'Enter canvas size (WxH):'
        assert scene.dialog.confirm_button.name == 'Create'

    def test_new_canvas_dialog_dimension_input(self, previous_scene):
        """Dimensions typed as key-downs land in the input box."""
        scene = NewCanvasDialogScene(previous_scene=previous_scene)

        _type_text(scene, '1024')

        assert scene.dialog.input_box.text == '1024'

    def test_new_canvas_dialog_creation_confirmation(self, previous_scene):
        """Confirming hands the dimensions to the previous scene and returns to it."""
        scene = NewCanvasDialogScene(previous_scene=previous_scene)
        scene.dialog.input_box.text = '1024x768'

        scene.on_confirm_event(_mouse_up((0, 0)), scene.dialog.confirm_button)

        assert previous_scene.new_file_dimensions == ['1024x768']
        assert scene.next_scene is previous_scene

    def test_new_canvas_dialog_dimension_validation(self, previous_scene):
        """The dialog passes the text through as typed; the canvas validates it."""
        scene = NewCanvasDialogScene(previous_scene=previous_scene)
        scene.dialog.input_box.text = 'invalid'

        scene.on_confirm_event(_mouse_up((0, 0)), scene.dialog.confirm_button)

        assert previous_scene.new_file_dimensions == ['invalid']


# ============================================================================
# From test_dialogs_coverage.py
# ============================================================================


class TestFileNames:
    """The dialogs use a file name as given, apart from surrounding whitespace."""

    def test_a_plain_name_is_used_as_it_is(self):
        """A plain name is the path, for a save and for a load."""
        assert _get_save_path('test.toml') == Path('test.toml')
        assert _get_load_path('test.toml') == Path('test.toml')

    def test_surrounding_whitespace_is_trimmed(self):
        """Spaces around a name are not part of the file name."""
        assert _get_save_path('  test.toml  ') == Path('test.toml')
        assert _get_load_path('  test.toml  ') == Path('test.toml')

    def test_an_examples_prefix_is_not_special_to_a_load(self):
        """'examples:' and 'example:' are ordinary characters of a name a load is given."""
        assert _get_load_path('examples:heart.toml') == Path('examples:heart.toml')
        assert _get_load_path('example:heart.toml') == Path('example:heart.toml')


class TestFileNameProblem:
    """':' in a Save name depends on the platform; the tests pass the platform explicitly."""

    @pytest.mark.parametrize(
        'filename',
        [
            'C:\\a.toml',
            'C:/a.toml',
            'C:a.toml',
            'c:\\a.toml',
            '\\\\?\\C:\\a.toml',
            '\\\\server\\share\\a.toml',
            'a.toml',
            'sprites\\a.toml',
            'C:',
            'C:\\',
            '\\\\.\\C:\\x.toml',
            '\\\\?\\UNC\\server\\share\\x.toml',
        ],
    )
    @pytest.mark.parametrize('platform', ['win32', 'cygwin'])
    def test_windows_allows_a_colon_only_in_the_drive_designator(self, filename, platform):
        """A drive (including drive-relative and extended paths) and UNC names pass."""
        assert _file_name_problem(filename, platform=platform) is None

    @pytest.mark.parametrize(
        'filename',
        [
            'foo:bar.toml',
            'examples:foo.toml',
            'C:\\a:b.toml',
            'C:a:b.toml',
            'ab:foo.toml',
            ':foo.toml',
            '\\\\server\\sh:\\a.toml',
            '\\\\?\\UNC\\server\\sh:\\a.toml',
        ],
    )
    @pytest.mark.parametrize('platform', ['win32', 'cygwin'])
    def test_windows_refuses_any_other_colon(self, filename, platform):
        """A ':' outside the drive would name an NTFS alternate data stream."""
        problem = _file_name_problem(filename, platform=platform)

        assert problem is not None
        assert "':' is only allowed after a drive letter" in problem
        assert 'alternate data stream' in problem
        assert "'examples:' prefix was removed" in problem

    def test_windows_extended_path_drive_is_pinned(self):
        """PureWindowsPath puts the extended path's drive in .drive, colon included."""
        assert PureWindowsPath('\\\\?\\C:\\a.toml').drive == '\\\\?\\C:'
        assert PureWindowsPath('C:a.toml').drive == 'C:'
        assert PureWindowsPath('C:/a.toml').drive == 'C:'

    @pytest.mark.parametrize(
        'filename', ['a:b.toml', 'examples:foo.toml', 'C:\\a.toml', 'C:/a.toml']
    )
    def test_macos_refuses_any_colon(self, filename):
        """Finder shows ':' as '/', so no ':' is accepted, not even a drive letter's."""
        problem = _file_name_problem(filename, platform='darwin')

        assert problem is not None
        assert "':' isn't allowed in a file name on macOS" in problem
        assert 'Finder shows it as' in problem
        assert "'examples:' prefix was removed" in problem

    @pytest.mark.parametrize('filename', ['a.toml', 'sprites/a.toml'])
    def test_macos_allows_a_name_without_a_colon(self, filename):
        """A plain name passes."""
        assert _file_name_problem(filename, platform='darwin') is None

    @pytest.mark.parametrize('filename', ['a:b.toml', 'examples:foo.toml', 'a.toml'])
    def test_linux_allows_a_colon(self, filename):
        """':' is a legal character on Linux."""
        assert _file_name_problem(filename, platform='linux') is None

    def test_the_browser_allows_a_colon(self):
        """Save is a download there, and the browser sanitizes the name."""
        assert _file_name_problem('a:b.toml', platform='emscripten') is None

    def test_the_default_platform_is_this_machines(self):
        """Without platform=, the helper uses sys.platform."""
        assert _file_name_problem('a:b.toml') == _file_name_problem(
            'a:b.toml', platform=sys.platform
        )


class TestDialogSceneSetupCleanupDismiss:
    """Test dialog scene lifecycle methods."""

    def test_input_confirmation_dialog_setup(self, previous_scene):
        """Test InputConfirmationDialogScene setup configures button callbacks."""
        scene = InputConfirmationDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )
        scene.setup()

        assert scene.dialog.cancel_button.callbacks == {
            'on_left_mouse_button_up_event': scene.on_cancel_event,
        }
        assert scene.dialog.confirm_button.callbacks == {
            'on_left_mouse_button_up_event': scene.on_confirm_event,
        }
        assert scene.dialog in scene.all_sprites

    def test_input_confirmation_dialog_cleanup(self, previous_scene):
        """Test InputConfirmationDialogScene cleanup sets next_scene to self."""
        scene = InputConfirmationDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )
        scene.next_scene = previous_scene

        scene.cleanup()

        assert scene.next_scene is None

    def test_input_confirmation_dialog_dismiss(self, previous_scene):
        """Dismiss returns to the previous scene and empties the dialog's sprites."""
        scene = InputConfirmationDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )
        previous_scene.next_scene = None

        scene.dismiss()

        assert scene.next_scene is previous_scene
        assert previous_scene.next_scene is None
        assert len(scene.all_sprites) == 0

    def test_input_confirmation_dialog_cancel_event(self, previous_scene):
        """Test InputConfirmationDialogScene on_cancel_event dismisses dialog."""
        scene = InputConfirmationDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )

        scene.on_cancel_event(_mouse_up((0, 0)), scene.dialog.cancel_button)

        assert scene.next_scene is previous_scene

    def test_input_confirmation_dialog_on_input_box_submit(self, previous_scene, caplog):
        """A submit from the input box is logged with the box's name and text."""
        scene = InputConfirmationDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )
        input_box = scene.dialog.input_box
        input_box.name = 'TestInput'
        input_box.text = 'test value'

        with caplog.at_level(logging.INFO, logger='game.ui.dialogs'):
            scene.on_input_box_submit_event(input_box)

        assert 'Got text input from: TestInput: test value' in caplog.text
        assert scene.next_scene is None

    def test_input_confirmation_dialog_mouse_button_up(self, previous_scene):
        """Test InputConfirmationDialogScene on_mouse_button_up_event activates input."""
        scene = InputConfirmationDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )
        scene.dialog.input_box.deactivate()

        scene.on_mouse_button_up_event(_mouse_up((0, 0)))

        assert scene.dialog.input_box.is_active is True

    def test_input_confirmation_dialog_key_up_tab_activates(self, previous_scene):
        """Test InputConfirmationDialogScene on_key_up_event with Tab activates input."""
        scene = InputConfirmationDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )
        scene.dialog.input_box.is_active = False

        scene.on_key_up_event(_key_up(pygame.K_TAB))

        assert scene.dialog.input_box.is_active is True

    def test_input_confirmation_dialog_key_up_active_input(self, previous_scene):
        """A key-up while the input box is active goes to the dialog's input box."""
        scene = InputConfirmationDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )
        scene.dialog.input_box.is_active = True

        # The input box deactivates on Escape's release: proof the key-up reached it
        scene.on_key_up_event(_key_up(pygame.K_ESCAPE))

        assert scene.dialog.input_box.is_active is False

    def test_input_confirmation_dialog_key_down_active_input(self, previous_scene):
        """A key-down while the input box is active types into the dialog's input box."""
        scene = InputConfirmationDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )
        scene.dialog.input_box.is_active = True

        scene.on_key_down_event(_key_down(pygame.K_a, unicode='a'))

        assert scene.dialog.input_box.text == 'a'

    def test_input_confirmation_dialog_key_down_inactive_input(self, previous_scene):
        """BUGS.md #41: an unhandled key-down reaches the base key-down handler, not key-up.

        The base key-down handler acts on no key (Q quits on its release, BUGS.md #203); the
        base key-up handler quits (posts QUIT) only on the release of a recorded press.
        """
        scene = InputConfirmationDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )
        scene.dialog.input_box.is_active = False
        pygame.event.clear(eventtype=pygame.QUIT)

        scene.on_key_down_event(_key_down(pygame.K_q, unicode='q'))

        assert pygame.event.get(eventtype=pygame.QUIT) == []
        assert not scene.dialog.input_box.text


class TestDeleteAnimationDialogScene:
    """Test DeleteAnimationDialogScene."""

    def test_delete_animation_dialog_initialization(self, previous_scene):
        """Test DeleteAnimationDialogScene initialization."""
        calls = []

        def confirm_callback():
            calls.append('confirm')

        def cancel_callback():
            calls.append('cancel')

        dialog = DeleteAnimationDialogScene(
            previous_scene=previous_scene,
            animation_name='idle',
            on_confirm_callback=confirm_callback,
            on_cancel_callback=cancel_callback,
            groups=pygame.sprite.LayeredDirty(),
        )
        assert dialog.animation_name == 'idle'
        assert dialog.on_confirm_callback is confirm_callback
        assert dialog.on_cancel_callback is cancel_callback
        message = "Type 'idle' to confirm deletion:"
        assert dialog.dialog.dialog_text_sprite.text_box.text == message
        assert dialog.dialog.rect.size == (500, 200)
        assert dialog.dialog.rect.center == pygame.display.get_surface().get_rect().center
        assert calls == []

    def test_delete_animation_confirm_matching_name(self, previous_scene):
        """Typing the animation's name and confirming deletes it and returns to the scene."""
        calls = []
        dialog = DeleteAnimationDialogScene(
            previous_scene=previous_scene,
            animation_name='idle',
            on_confirm_callback=lambda: calls.append('confirm'),
            groups=pygame.sprite.LayeredDirty(),
        )
        dialog.dialog.input_box.text = 'idle'

        dialog.on_confirm_event(_mouse_up((0, 0)))

        assert calls == ['confirm']
        assert dialog.scene_manager.active_scene is previous_scene

    def test_delete_animation_confirm_non_matching_name(self, previous_scene):
        """Test confirm with non-matching name clears input."""
        calls = []
        dialog = DeleteAnimationDialogScene(
            previous_scene=previous_scene,
            animation_name='idle',
            on_confirm_callback=lambda: calls.append('confirm'),
            groups=pygame.sprite.LayeredDirty(),
        )
        dialog.dialog.input_box.text = 'wrong'

        dialog.on_confirm_event(_mouse_up((0, 0)))

        assert calls == []
        assert not dialog.dialog.input_box.text
        assert dialog.scene_manager.active_scene is not previous_scene

    def test_delete_animation_cancel_with_callback(self, previous_scene):
        """Test cancel event calls cancel callback."""
        calls = []
        dialog = DeleteAnimationDialogScene(
            previous_scene=previous_scene,
            animation_name='idle',
            on_confirm_callback=lambda: calls.append('confirm'),
            on_cancel_callback=lambda: calls.append('cancel'),
            groups=pygame.sprite.LayeredDirty(),
        )

        dialog.on_cancel_event(_mouse_up((0, 0)))

        assert calls == ['cancel']
        assert dialog.scene_manager.active_scene is previous_scene

    def test_delete_animation_cancel_without_callback(self, previous_scene):
        """Cancelling without a cancel callback still returns to the previous scene."""
        calls = []
        dialog = DeleteAnimationDialogScene(
            previous_scene=previous_scene,
            animation_name='idle',
            on_confirm_callback=lambda: calls.append('confirm'),
            on_cancel_callback=None,
            groups=pygame.sprite.LayeredDirty(),
        )

        dialog.on_cancel_event(_mouse_up((0, 0)))

        assert calls == []
        assert dialog.scene_manager.active_scene is previous_scene

    def test_delete_animation_key_down_active_input(self, previous_scene):
        """A key-down while the input box is active types into it."""
        dialog = DeleteAnimationDialogScene(
            previous_scene=previous_scene,
            animation_name='idle',
            on_confirm_callback=lambda: None,
            groups=pygame.sprite.LayeredDirty(),
        )
        dialog.dialog.input_box.is_active = True

        dialog.on_key_down_event(_key_down(pygame.K_a, unicode='a'))

        assert dialog.dialog.input_box.text == 'a'

    def test_delete_animation_key_up_active_input(self, previous_scene):
        """A key-up while the input box is active reaches it (Escape deactivates it)."""
        dialog = DeleteAnimationDialogScene(
            previous_scene=previous_scene,
            animation_name='idle',
            on_confirm_callback=lambda: None,
            groups=pygame.sprite.LayeredDirty(),
        )
        dialog.dialog.input_box.is_active = True

        dialog.on_key_up_event(_key_up(pygame.K_ESCAPE))

        assert dialog.dialog.input_box.is_active is False

    def test_delete_animation_key_up_tab_activates(self, previous_scene):
        """Test DeleteAnimationDialogScene key up with Tab activates input."""
        dialog = DeleteAnimationDialogScene(
            previous_scene=previous_scene,
            animation_name='idle',
            on_confirm_callback=lambda: None,
            groups=pygame.sprite.LayeredDirty(),
        )
        dialog.dialog.input_box.is_active = False

        dialog.on_key_up_event(_key_up(pygame.K_TAB))

        assert dialog.dialog.input_box.is_active is True


def _create_delete_frame_dialog(previous_scene, *, confirm_callback, cancel_callback=None):
    """Create a DeleteFrameDialogScene for frame 0 of 'idle'.

    Returns:
        DeleteFrameDialogScene: The dialog scene.
    """
    return DeleteFrameDialogScene(
        previous_scene=previous_scene,
        animation_name='idle',
        frame_index=0,
        on_confirm_callback=confirm_callback,
        on_cancel_callback=cancel_callback,
        groups=pygame.sprite.LayeredDirty(),
    )


class TestDeleteFrameDialogScene:
    """Test DeleteFrameDialogScene."""

    def test_delete_frame_dialog_initialization(self, previous_scene):
        """The dialog asks about the frame and adds a second label below the first."""
        dialog = _create_delete_frame_dialog(previous_scene, confirm_callback=lambda: None)

        assert dialog.animation_name == 'idle'
        assert dialog.frame_index == 0
        first_label = dialog.dialog.dialog_text_sprite
        assert first_label.text_box.text == "Delete this frame from 'idle'?"
        assert dialog.second_label.text == "Type 'YES' to confirm:"
        assert dialog.second_label.rect.x == first_label.rect.x
        assert dialog.second_label.rect.y == first_label.rect.y + 30
        assert dialog.second_label.background_color == first_label.background_color
        assert dialog.second_label in dialog.all_sprites

    def test_delete_frame_second_label_draws_its_text(self, previous_scene):
        """The second label renders its prompt with the real font."""
        dialog = _create_delete_frame_dialog(previous_scene, confirm_callback=lambda: None)
        label = dialog.second_label

        label.update()

        rgb_pixels = pygame.surfarray.array3d(label.image)
        background = rgb_pixels[0, 0]
        assert (rgb_pixels != background).any(axis=2).sum() > 0

    def test_delete_frame_confirm_yes(self, previous_scene):
        """Typing YES and confirming deletes the frame and returns to the scene."""
        calls = []
        dialog = _create_delete_frame_dialog(
            previous_scene, confirm_callback=lambda: calls.append('confirm')
        )
        dialog.dialog.input_box.text = 'YES'

        dialog.on_confirm_event(_mouse_up((0, 0)))

        assert calls == ['confirm']
        assert dialog.scene_manager.active_scene is previous_scene

    def test_delete_frame_confirm_wrong_text(self, previous_scene):
        """Test confirm with wrong text clears input."""
        calls = []
        dialog = _create_delete_frame_dialog(
            previous_scene, confirm_callback=lambda: calls.append('confirm')
        )
        dialog.dialog.input_box.text = 'no'

        dialog.on_confirm_event(_mouse_up((0, 0)))

        assert calls == []
        assert not dialog.dialog.input_box.text
        assert dialog.scene_manager.active_scene is not previous_scene

    def test_delete_frame_cancel(self, previous_scene):
        """Test cancel event on delete frame dialog."""
        calls = []
        dialog = _create_delete_frame_dialog(
            previous_scene,
            confirm_callback=lambda: calls.append('confirm'),
            cancel_callback=lambda: calls.append('cancel'),
        )

        dialog.on_cancel_event(_mouse_up((0, 0)))

        assert calls == ['cancel']
        assert dialog.scene_manager.active_scene is previous_scene

    def test_delete_frame_key_down_active(self, previous_scene):
        """A key-down while the input box is active types into it."""
        dialog = _create_delete_frame_dialog(previous_scene, confirm_callback=lambda: None)
        dialog.dialog.input_box.is_active = True

        dialog.on_key_down_event(_key_down(pygame.K_y, unicode='Y', mod=pygame.KMOD_LSHIFT))

        assert dialog.dialog.input_box.text == 'Y'

    def test_delete_frame_key_up_active(self, previous_scene):
        """A key-up while the input box is active reaches it (Escape deactivates it)."""
        dialog = _create_delete_frame_dialog(previous_scene, confirm_callback=lambda: None)
        dialog.dialog.input_box.is_active = True

        dialog.on_key_up_event(_key_up(pygame.K_ESCAPE))

        assert dialog.dialog.input_box.is_active is False

    def test_delete_frame_key_up_tab_inactive(self, previous_scene):
        """Test DeleteFrameDialogScene key up with Tab when inactive."""
        dialog = _create_delete_frame_dialog(previous_scene, confirm_callback=lambda: None)
        dialog.dialog.input_box.is_active = False

        dialog.on_key_up_event(_key_up(pygame.K_TAB))

        assert dialog.dialog.input_box.is_active is True


# ============================================================================
# From test_dialogs_deeper_coverage.py
# ============================================================================


class TestNewCanvasDialogConfirm:
    """Test NewCanvasDialogScene.on_confirm_event."""

    def test_confirm_calls_on_new_file_event(self, previous_scene):
        """Test confirm event calls previous scene's on_new_file_event."""
        dialog = NewCanvasDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )
        dialog.dialog.input_box.text = '16x16'

        dialog.on_confirm_event(_mouse_up((0, 0)), dialog.dialog.confirm_button)

        assert previous_scene.new_file_dimensions == ['16x16']


class TestLoadDialogConfirm:
    """Test LoadDialogScene.on_confirm_event."""

    def test_confirm_calls_on_load_file_event(self, previous_scene):
        """Test confirm event calls canvas on_load_file_event."""
        dialog = LoadDialogScene(previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty())
        dialog.dialog.input_box.text = 'test.toml'

        dialog.on_confirm_event(_mouse_up((0, 0)), dialog.dialog.confirm_button)

        assert previous_scene.canvas.loaded_paths == ['test.toml']

    def test_confirm_loads_a_sprite_by_its_path(self, previous_scene, tmp_path):
        """Test confirm event hands the canvas the path of a sprite file."""
        sprite_path = tmp_path / 'static.toml'
        shutil.copy(
            Path(__file__).resolve().parents[1] / 'fixtures' / 'sprites' / 'static.toml',
            sprite_path,
        )
        dialog = LoadDialogScene(previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty())
        dialog.dialog.input_box.text = str(sprite_path)

        dialog.on_confirm_event(_mouse_up((0, 0)), dialog.dialog.confirm_button)

        assert previous_scene.canvas.loaded_paths == [str(sprite_path)]

    def test_an_examples_prefixed_name_is_loaded_as_an_ordinary_name(self, previous_scene):
        """'examples:heart.toml' reaches the canvas as given, which reports it missing."""
        dialog = LoadDialogScene(previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty())
        dialog.dialog.input_box.text = 'examples:heart.toml'

        dialog.on_confirm_event(_mouse_up((0, 0)), dialog.dialog.confirm_button)

        assert previous_scene.canvas.loaded_paths == ['examples:heart.toml']


class TestSaveDialogConfirm:
    """Test SaveDialogScene.on_confirm_event."""

    @pytest.fixture
    def macos_rules(self, mocker):
        """Make the dialog apply macOS's rule, wherever the tests run.

        The dialog uses this machine's platform, where a ':' may be legal (Linux), so the helper is
        patched to be called with platform='darwin' (sys.platform itself is left alone).
        """
        real_file_name_problem = _file_name_problem
        mocker.patch(
            'glitchygames.ui.dialogs._file_name_problem',
            side_effect=lambda filename: real_file_name_problem(filename, platform='darwin'),
        )

    def test_confirm_calls_on_save_file_event(self, previous_scene):
        """Test confirm event calls canvas on_save_file_event."""
        dialog = SaveDialogScene(previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty())
        dialog.dialog.input_box.text = 'output.toml'

        dialog.on_confirm_event(_mouse_up((0, 0)), dialog.dialog.confirm_button)

        assert previous_scene.canvas.saved_paths == ['output.toml']

    @pytest.mark.parametrize('filename', ['examples:star.toml', 'sprites/a:b.toml'])
    def test_a_name_with_a_colon_is_refused_and_nothing_is_saved(
        self, previous_scene, filename, macos_rules
    ):
        """A ':' name shows the reason, saves nothing, hands nothing over and closes the dialog."""
        user_files = _RecordingUserFiles()
        install_user_files(user_files=user_files)
        previous_scene.debug_text = _RecordingDebugText()
        dialog = SaveDialogScene(previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty())
        dialog.dialog.input_box.text = filename

        dialog.on_confirm_event(_mouse_up((0, 0)), dialog.dialog.confirm_button)

        assert previous_scene.canvas.saved_paths == []
        assert not user_files.saved_files
        assert "':' isn't allowed in a file name on macOS" in previous_scene.debug_text.text
        assert dialog.next_scene is previous_scene

    def test_a_refused_name_writes_no_file(
        self, previous_scene, tmp_path, monkeypatch, macos_rules
    ):
        """Nothing is created in the working directory for a refused name."""
        monkeypatch.chdir(tmp_path)
        dialog = SaveDialogScene(previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty())
        dialog.dialog.input_box.text = 'examples:star.toml'

        dialog.on_confirm_event(_mouse_up((0, 0)), dialog.dialog.confirm_button)

        assert list(tmp_path.iterdir()) == []

    def test_a_refused_name_without_a_debug_text_is_only_dismissed(
        self, previous_scene, macos_rules
    ):
        """A scene with no debug text box still closes the dialog without saving."""
        dialog = SaveDialogScene(previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty())
        dialog.dialog.input_box.text = 'examples:star.toml'

        dialog.on_confirm_event(_mouse_up((0, 0)), dialog.dialog.confirm_button)

        assert previous_scene.canvas.saved_paths == []
        assert dialog.next_scene is previous_scene

    def test_without_user_files_nothing_is_handed_over(self, previous_scene):
        """On the desktop the saved file is already the player's own."""
        dialog = SaveDialogScene(previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty())
        dialog.dialog.input_box.text = 'output.toml'

        dialog.on_confirm_event(_mouse_up((0, 0)), dialog.dialog.confirm_button)

        assert installed_user_files() is None
        assert previous_scene.canvas.saved_paths == ['output.toml']

    def test_with_user_files_the_saved_file_is_handed_to_the_player(self, previous_scene):
        """In a browser the saved file goes to the player (a download)."""
        user_files = _RecordingUserFiles()
        install_user_files(user_files=user_files)
        dialog = SaveDialogScene(previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty())
        dialog.dialog.input_box.text = 'output.toml'

        dialog.on_confirm_event(_mouse_up((0, 0)), dialog.dialog.confirm_button)

        assert user_files.saved_files == [Path('output.toml')]

    @pytest.mark.parametrize('save_error', [OSError('disk full'), ValueError('bad'), KeyError('k')])
    def test_a_failed_save_returns_to_the_editor_and_is_not_handed_over(
        self, previous_scene, save_error
    ):
        """A failed save closes the dialog with the error shown, not the editor (BUGS.md #217)."""
        user_files = _RecordingUserFiles()
        install_user_files(user_files=user_files)
        previous_scene.canvas.save_error = save_error
        dialog = SaveDialogScene(previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty())
        dialog.dialog.input_box.text = 'output.toml'

        dialog.on_confirm_event(_mouse_up((0, 0)), dialog.dialog.confirm_button)

        # Dismissed: the dialog switches back to the scene it came from
        assert dialog.next_scene is previous_scene
        assert not user_files.saved_files


class TestDeleteAnimationDialogSetup:
    """Test DeleteAnimationDialogScene.setup method."""

    def test_setup_configures_buttons_and_activates_input(self, previous_scene):
        """Test setup configures button callbacks and activates input box."""
        dialog = DeleteAnimationDialogScene(
            previous_scene=previous_scene,
            animation_name='walk',
            on_confirm_callback=lambda: None,
            groups=pygame.sprite.LayeredDirty(),
        )
        dialog.dialog.input_box.deactivate()

        dialog.setup()

        assert dialog.dialog.cancel_button.callbacks == {
            'on_left_mouse_button_up_event': dialog.on_cancel_event,
        }
        assert dialog.dialog.confirm_button.callbacks == {
            'on_left_mouse_button_up_event': dialog.on_confirm_event,
        }
        assert dialog.dialog in dialog.all_sprites
        assert dialog.dialog.input_box.is_active is True

    def test_key_down_inactive_calls_super(self, previous_scene):
        """A key-down with the input box inactive reaches the base handler (no quit on press)."""
        dialog = DeleteAnimationDialogScene(
            previous_scene=previous_scene,
            animation_name='walk',
            on_confirm_callback=lambda: None,
            groups=pygame.sprite.LayeredDirty(),
        )
        dialog.dialog.input_box.is_active = False
        pygame.event.clear(eventtype=pygame.QUIT)

        dialog.on_key_down_event(_key_down(pygame.K_q, unicode='q'))

        # Q quits on its release (BUGS.md #203: its press set a flag nothing read)
        assert pygame.event.get(eventtype=pygame.QUIT) == []
        assert not dialog.dialog.input_box.text

    def test_key_up_non_tab_inactive_calls_super(self, previous_scene):
        """A non-Tab key-up with the input box inactive reaches the base handler.

        The base handler consumes the key's recorded press and leaves the input box inactive.
        """
        dialog = DeleteAnimationDialogScene(
            previous_scene=previous_scene,
            animation_name='walk',
            on_confirm_callback=lambda: None,
            groups=pygame.sprite.LayeredDirty(),
        )
        dialog.dialog.input_box.is_active = False
        dialog.record_key_press(key=pygame.K_a)

        dialog.on_key_up_event(_key_up(pygame.K_a))

        assert pygame.K_a not in dialog._keys_pressed_in_scene
        assert dialog.dialog.input_box.is_active is False


class TestDeleteFrameDialogSetup:
    """Test DeleteFrameDialogScene.setup method."""

    def test_setup_configures_buttons_and_activates_input(self, previous_scene):
        """Test setup configures button callbacks and activates input box."""
        dialog = _create_delete_frame_dialog(previous_scene, confirm_callback=lambda: None)
        dialog.dialog.input_box.deactivate()

        dialog.setup()

        assert dialog.dialog.cancel_button.callbacks == {
            'on_left_mouse_button_up_event': dialog.on_cancel_event,
        }
        assert dialog.dialog.confirm_button.callbacks == {
            'on_left_mouse_button_up_event': dialog.on_confirm_event,
        }
        assert dialog.dialog in dialog.all_sprites
        assert dialog.dialog.input_box.is_active is True

    def test_cancel_without_callback(self, previous_scene):
        """Cancelling without a cancel callback still returns to the previous scene."""
        dialog = _create_delete_frame_dialog(previous_scene, confirm_callback=lambda: None)

        dialog.on_cancel_event(_mouse_up((0, 0)))

        assert dialog.scene_manager.active_scene is previous_scene

    def test_key_down_inactive_calls_super(self, previous_scene):
        """A key-down with the input box inactive reaches the base handler (no quit on press)."""
        dialog = _create_delete_frame_dialog(previous_scene, confirm_callback=lambda: None)
        dialog.dialog.input_box.is_active = False
        pygame.event.clear(eventtype=pygame.QUIT)

        dialog.on_key_down_event(_key_down(pygame.K_q, unicode='q'))

        # Q quits on its release (BUGS.md #203: its press set a flag nothing read)
        assert pygame.event.get(eventtype=pygame.QUIT) == []
        assert not dialog.dialog.input_box.text

    def test_key_up_non_tab_inactive_calls_super(self, previous_scene):
        """A non-Tab key-up with the input box inactive reaches the base handler."""
        dialog = _create_delete_frame_dialog(previous_scene, confirm_callback=lambda: None)
        dialog.dialog.input_box.is_active = False
        dialog.record_key_press(key=pygame.K_a)

        dialog.on_key_up_event(_key_up(pygame.K_a))

        assert pygame.K_a not in dialog._keys_pressed_in_scene
        assert dialog.dialog.input_box.is_active is False


class TestInputConfirmationDialogGroupsNone:
    """Test InputConfirmationDialogScene with groups=None (line 156)."""

    def test_groups_none_creates_default_layered_dirty(self, previous_scene):
        """Test InputConfirmationDialogScene creates LayeredDirty when groups=None."""
        dialog = InputConfirmationDialogScene(previous_scene=previous_scene, groups=None)

        assert isinstance(dialog.all_sprites, pygame.sprite.LayeredDirty)
        assert dialog.dialog.input_box in dialog.all_sprites


class TestDismissWithPreviousSceneSprites:
    """Test dismiss() iterating previous_scene.all_sprites (line 226)."""

    def test_dismiss_marks_previous_scene_sprites_dirty(self, previous_scene):
        """Test dismiss forces redraw on previous scene sprites."""
        (sprite,) = previous_scene.all_sprites.sprites()
        assert sprite.dirty == 0
        dialog = InputConfirmationDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )

        dialog.dismiss()

        assert sprite.dirty == 1


class TestBaseOnConfirmEventIsinstance:
    """Test InputConfirmationDialogScene.on_confirm_event isinstance branches (lines 242-254)."""

    def test_base_confirm_event_no_subclass_match(self, previous_scene):
        """The base dialog's confirm only dismisses: it hands nothing to the canvas."""
        dialog = InputConfirmationDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )
        dialog.dialog.input_box.text = 'test.toml'

        dialog.on_confirm_event(_mouse_up((0, 0)), dialog.dialog.confirm_button)

        assert dialog.next_scene is previous_scene
        assert previous_scene.canvas.loaded_paths == []
        assert previous_scene.canvas.saved_paths == []
        assert previous_scene.new_file_dimensions == []


class TestDialogKeyUpElseBranch:
    """Test InputConfirmationDialogScene.on_key_up_event else branch (line 289)."""

    def test_key_up_non_tab_inactive_calls_super(self, previous_scene):
        """A non-Tab key-up with the input box inactive reaches the base handler."""
        dialog = InputConfirmationDialogScene(
            previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
        )
        dialog.dialog.input_box.is_active = False
        dialog.record_key_press(key=pygame.K_a)

        dialog.on_key_up_event(_key_up(pygame.K_a))

        assert pygame.K_a not in dialog._keys_pressed_in_scene
        assert dialog.dialog.input_box.is_active is False


class TestDialogSubclassGroupsNone:
    """Test groups=None branches in dialog subclasses (lines 331, 380, 431, 482, 600)."""

    def test_new_canvas_dialog_groups_none(self, previous_scene):
        """Test NewCanvasDialogScene creates LayeredDirty when groups=None (line 331)."""
        dialog = NewCanvasDialogScene(previous_scene=previous_scene, groups=None)
        assert isinstance(dialog.all_sprites, pygame.sprite.LayeredDirty)

    def test_load_dialog_groups_none(self, previous_scene):
        """Test LoadDialogScene creates LayeredDirty when groups=None (line 380)."""
        dialog = LoadDialogScene(previous_scene=previous_scene, groups=None)
        assert isinstance(dialog.all_sprites, pygame.sprite.LayeredDirty)

    def test_save_dialog_groups_none(self, previous_scene):
        """Test SaveDialogScene creates LayeredDirty when groups=None (line 431)."""
        dialog = SaveDialogScene(previous_scene=previous_scene, groups=None)
        assert isinstance(dialog.all_sprites, pygame.sprite.LayeredDirty)

    def test_delete_animation_dialog_groups_none(self, previous_scene):
        """Test DeleteAnimationDialogScene creates LayeredDirty when groups=None (line 482)."""
        dialog = DeleteAnimationDialogScene(
            previous_scene=previous_scene,
            animation_name='walk',
            on_confirm_callback=lambda: None,
            groups=None,
        )
        assert isinstance(dialog.all_sprites, pygame.sprite.LayeredDirty)
        assert dialog.dialog.input_box in dialog.all_sprites

    def test_delete_frame_dialog_groups_none(self, previous_scene):
        """Test DeleteFrameDialogScene creates LayeredDirty when groups=None (line 600)."""
        dialog = DeleteFrameDialogScene(
            previous_scene=previous_scene,
            animation_name='idle',
            frame_index=0,
            on_confirm_callback=lambda: None,
            groups=None,
        )
        assert isinstance(dialog.all_sprites, pygame.sprite.LayeredDirty)
        assert dialog.second_label in dialog.all_sprites


# ============================================================================
# From test_confirm_dialog_coverage.py
# ============================================================================


def _create_confirm_dialog(confirm_callback=None, cancel_callback=None, groups=None):
    """Create a ConfirmDialog with standard test configuration.

    Returns:
        A ConfirmDialog instance configured for testing.
    """
    return ConfirmDialog(
        text='Are you sure?',
        confirm_callback=confirm_callback,
        cancel_callback=cancel_callback,
        x=TEST_CONFIRM_DIALOG_X,
        y=TEST_CONFIRM_DIALOG_Y,
        width=TEST_CONFIRM_DIALOG_WIDTH,
        height=TEST_CONFIRM_DIALOG_HEIGHT,
        groups=groups if groups is not None else pygame.sprite.LayeredDirty(),
    )


def _inside_corner(rect):
    """Return a point just inside a button, past its 2-pixel border and clear of its label.

    Returns:
        tuple: The (x, y) point.
    """
    return (rect.x + 4, rect.y + 4)


class TestConfirmDialogInitialization:
    """Test ConfirmDialog initialization and button positioning."""

    def test_dialog_stores_text(self):
        """Test dialog stores the confirmation text."""
        dialog = _create_confirm_dialog()
        assert dialog.text == 'Are you sure?'

    def test_dialog_stores_callbacks(self):
        """Test dialog stores confirm and cancel callbacks."""

        def confirm_callback():
            pass

        def cancel_callback():
            pass

        dialog = _create_confirm_dialog(
            confirm_callback=confirm_callback,
            cancel_callback=cancel_callback,
        )

        assert dialog.confirm_callback is confirm_callback
        assert dialog.cancel_callback is cancel_callback

    def test_yes_button_rect_is_positioned(self):
        """Test yes button rect has correct dimensions."""
        dialog = _create_confirm_dialog()

        assert dialog.yes_button_rect.width == CONFIRM_BUTTON_WIDTH
        assert dialog.yes_button_rect.height == CONFIRM_BUTTON_HEIGHT

    def test_no_button_rect_is_positioned(self):
        """Test no button rect has correct dimensions."""
        dialog = _create_confirm_dialog()

        assert dialog.no_button_rect.width == CONFIRM_BUTTON_WIDTH
        assert dialog.no_button_rect.height == CONFIRM_BUTTON_HEIGHT

    def test_buttons_are_centered(self):
        """Test buttons are horizontally centered within dialog."""
        dialog = _create_confirm_dialog()

        total_button_width = (CONFIRM_BUTTON_WIDTH * 2) + BUTTON_SPACING
        expected_start_x = (TEST_CONFIRM_DIALOG_WIDTH - total_button_width) // 2

        assert dialog.yes_button_rect.x == expected_start_x
        assert dialog.no_button_rect.x == expected_start_x + CONFIRM_BUTTON_WIDTH + BUTTON_SPACING

    def test_buttons_vertical_position(self):
        """Test buttons are positioned near the bottom of the dialog."""
        dialog = _create_confirm_dialog()

        expected_button_y = TEST_CONFIRM_DIALOG_HEIGHT - CONFIRM_BUTTON_HEIGHT - 10

        assert dialog.yes_button_rect.y == expected_button_y
        assert dialog.no_button_rect.y == expected_button_y

    def test_initial_hover_is_none(self):
        """Test hover_button is initially None."""
        dialog = _create_confirm_dialog()
        assert dialog.hover_button is None

    def test_initial_dirty_is_2(self):
        """Test dirty flag is initially 2 (continuous updates)."""
        dialog = _create_confirm_dialog()
        assert dialog.dirty == 2


class TestConfirmDialogRender:
    """Test ConfirmDialog.render() drawing, on its real image."""

    def test_render_fills_background(self):
        """Test render fills the image with dark gray."""
        dialog = _create_confirm_dialog()
        dialog.image.fill(MARKER_COLOR)

        dialog.render()

        # Between the border and the text, and between the buttons
        assert _rgb_at(dialog.image, (5, 5)) == CONFIRM_BACKGROUND_COLOR
        between_buttons = (dialog.yes_button_rect.right + 5, dialog.yes_button_rect.centery)
        assert _rgb_at(dialog.image, between_buttons) == CONFIRM_BACKGROUND_COLOR

    def test_render_draws_border(self):
        """Test render draws a 2-pixel border around the dialog, and around each button."""
        dialog = _create_confirm_dialog()
        dialog.image.fill(MARKER_COLOR)

        dialog.render()

        last_x = TEST_CONFIRM_DIALOG_WIDTH - 1
        last_y = TEST_CONFIRM_DIALOG_HEIGHT - 1
        for corner in [(0, 0), (1, 1), (last_x, 0), (0, last_y), (last_x, last_y)]:
            assert _rgb_at(dialog.image, corner) == CONFIRM_BORDER_COLOR
        assert _rgb_at(dialog.image, (2, 2)) == CONFIRM_BACKGROUND_COLOR
        assert _rgb_at(dialog.image, dialog.yes_button_rect.topleft) == YES_BUTTON_BORDER_COLOR
        assert _rgb_at(dialog.image, dialog.no_button_rect.topleft) == NO_BUTTON_BORDER_COLOR

    def test_render_draws_buttons_and_text(self):
        """Render draws both buttons in their normal colours, with the message and labels."""
        dialog = _create_confirm_dialog()

        dialog.render()

        yes_rect = dialog.yes_button_rect
        no_rect = dialog.no_button_rect
        assert _rgb_at(dialog.image, _inside_corner(yes_rect)) == YES_BUTTON_COLOR
        assert _rgb_at(dialog.image, _inside_corner(no_rect)) == NO_BUTTON_COLOR
        # The message (centred, from y=20 down) and each button's label are white text
        message_area = pygame.Rect(0, 20, TEST_CONFIRM_DIALOG_WIDTH, yes_rect.top - 20)
        assert _text_pixel_count(dialog.image, message_area) > 0
        assert _text_pixel_count(dialog.image, yes_rect.inflate(-4, -4)) > 0
        assert _text_pixel_count(dialog.image, no_rect.inflate(-4, -4)) > 0
        # The message is centred: its text pixels sit on both sides of the middle
        middle = TEST_CONFIRM_DIALOG_WIDTH // 2
        left_half = pygame.Rect(0, 20, middle, yes_rect.top - 20)
        right_half = pygame.Rect(middle, 20, middle, yes_rect.top - 20)
        assert _text_pixel_count(dialog.image, left_half) > 0
        assert _text_pixel_count(dialog.image, right_half) > 0

    def test_render_sets_dirty_to_zero(self):
        """Test render sets dirty to 0 after rendering."""
        dialog = _create_confirm_dialog()

        dialog.render()

        assert dialog.dirty == 0

    def test_render_hover_yes_changes_color(self):
        """Test render uses highlight color when yes button is hovered."""
        dialog = _create_confirm_dialog()
        dialog.hover_button = 'yes'

        dialog.render()

        assert _rgb_at(dialog.image, _inside_corner(dialog.yes_button_rect)) == (
            YES_BUTTON_HOVER_COLOR
        )
        assert _rgb_at(dialog.image, _inside_corner(dialog.no_button_rect)) == NO_BUTTON_COLOR

    def test_render_hover_no_changes_color(self):
        """Render uses the highlight colour for the No button when it is hovered."""
        dialog = _create_confirm_dialog()
        dialog.hover_button = 'no'

        dialog.render()

        assert _rgb_at(dialog.image, _inside_corner(dialog.yes_button_rect)) == YES_BUTTON_COLOR
        assert _rgb_at(dialog.image, _inside_corner(dialog.no_button_rect)) == (
            NO_BUTTON_HOVER_COLOR
        )


class TestConfirmDialogHandleMouseDown:
    """Test ConfirmDialog.handle_mouse_down()."""

    def test_click_yes_invokes_confirm_callback(self):
        """Test clicking Yes button invokes confirm_callback."""
        calls = []
        group = pygame.sprite.LayeredDirty()
        dialog = _create_confirm_dialog(confirm_callback=lambda: calls.append('yes'), groups=group)

        click_pos = (dialog.yes_button_rect.centerx, dialog.yes_button_rect.centery)
        result = dialog.handle_mouse_down(click_pos)

        assert result is True
        assert calls == ['yes']
        assert not dialog.alive()

    def test_click_no_invokes_cancel_callback(self):
        """Test clicking No button invokes cancel_callback."""
        calls = []
        group = pygame.sprite.LayeredDirty()
        dialog = _create_confirm_dialog(cancel_callback=lambda: calls.append('no'), groups=group)

        click_pos = (dialog.no_button_rect.centerx, dialog.no_button_rect.centery)
        result = dialog.handle_mouse_down(click_pos)

        assert result is True
        assert calls == ['no']
        assert not dialog.alive()

    def test_click_yes_without_callback(self):
        """Test clicking Yes without callback still kills dialog."""
        dialog = _create_confirm_dialog(confirm_callback=None)

        click_pos = (dialog.yes_button_rect.centerx, dialog.yes_button_rect.centery)
        result = dialog.handle_mouse_down(click_pos)

        assert result is True
        assert not dialog.alive()

    def test_click_no_without_callback(self):
        """Test clicking No without callback still kills dialog."""
        dialog = _create_confirm_dialog(cancel_callback=None)

        click_pos = (dialog.no_button_rect.centerx, dialog.no_button_rect.centery)
        result = dialog.handle_mouse_down(click_pos)

        assert result is True
        assert not dialog.alive()

    def test_click_outside_buttons_returns_false(self):
        """Test clicking outside both buttons returns False."""
        calls = []
        dialog = _create_confirm_dialog(
            confirm_callback=lambda: calls.append('yes'),
            cancel_callback=lambda: calls.append('no'),
        )

        # Click in the middle of the dialog, above the buttons
        click_pos = (TEST_CONFIRM_DIALOG_WIDTH // 2, 10)
        result = dialog.handle_mouse_down(click_pos)

        assert result is False
        assert calls == []
        assert dialog.alive()

    def test_click_yes_removes_dialog(self):
        """Test clicking Yes removes the dialog from its groups."""
        group = pygame.sprite.LayeredDirty()
        dialog = _create_confirm_dialog(confirm_callback=lambda: None, groups=group)
        assert dialog in group

        click_pos = (dialog.yes_button_rect.centerx, dialog.yes_button_rect.centery)
        dialog.handle_mouse_down(click_pos)

        assert dialog not in group


class TestConfirmDialogUpdate:
    """Test ConfirmDialog.update() hover tracking."""

    def test_update_detects_yes_hover(self):
        """Test update detects mouse hovering over Yes button, and redraws it highlighted."""
        dialog = _create_confirm_dialog()

        # The frame's mouse position is over the yes button (relative to dialog)
        assert dialog.rect is not None
        yes_center_x = dialog.yes_button_rect.centerx + dialog.rect.x
        yes_center_y = dialog.yes_button_rect.centery + dialog.rect.y
        _install_mouse_position((yes_center_x, yes_center_y))

        dialog.update()

        assert dialog.hover_button == 'yes'
        assert _rgb_at(dialog.image, _inside_corner(dialog.yes_button_rect)) == (
            YES_BUTTON_HOVER_COLOR
        )

    def test_update_detects_no_hover(self):
        """Test update detects mouse hovering over No button, and redraws it highlighted."""
        dialog = _create_confirm_dialog()

        assert dialog.rect is not None
        no_center_x = dialog.no_button_rect.centerx + dialog.rect.x
        no_center_y = dialog.no_button_rect.centery + dialog.rect.y
        _install_mouse_position((no_center_x, no_center_y))

        dialog.update()

        assert dialog.hover_button == 'no'
        assert _rgb_at(dialog.image, _inside_corner(dialog.no_button_rect)) == (
            NO_BUTTON_HOVER_COLOR
        )

    def test_update_clears_hover_when_outside(self):
        """Test update clears hover when mouse is outside buttons, and redraws unhighlighted."""
        dialog = _create_confirm_dialog()
        dialog.render()
        dialog.hover_button = 'yes'

        # Mouse far from both buttons
        _install_mouse_position((0, 0))

        dialog.update()

        assert dialog.hover_button is None
        assert _rgb_at(dialog.image, _inside_corner(dialog.yes_button_rect)) == YES_BUTTON_COLOR
        assert dialog.dirty == 0

    def test_update_skips_render_when_clean_and_hover_unchanged(self):
        """With no hover change and nothing dirty, update draws nothing."""
        dialog = _create_confirm_dialog()
        dialog.hover_button = None
        dialog.dirty = 0
        dialog.image.fill(MARKER_COLOR)
        _install_mouse_position((0, 0))

        dialog.update()

        assert _rgb_at(dialog.image, (5, 5)) == MARKER_COLOR
        assert _rgb_at(dialog.image, _inside_corner(dialog.yes_button_rect)) == MARKER_COLOR
        assert dialog.dirty == 0

    def test_update_calls_render_when_dirty(self):
        """Test update renders the dialog when it is dirty."""
        dialog = _create_confirm_dialog()
        dialog.dirty = 2
        dialog.image.fill(MARKER_COLOR)

        _install_mouse_position((0, 0))

        dialog.update()

        assert _rgb_at(dialog.image, (5, 5)) == CONFIRM_BACKGROUND_COLOR
        assert _rgb_at(dialog.image, _inside_corner(dialog.yes_button_rect)) == YES_BUTTON_COLOR
        assert dialog.dirty == 0


# ============================================================================
# From test_input_dialog_coverage.py
# ============================================================================


def _create_input_dialog(parent=None):
    """Create an InputDialog with standard test configuration.

    Returns:
        An InputDialog instance configured for testing.
    """
    return InputDialog(
        x=TEST_INPUT_DIALOG_X,
        y=TEST_INPUT_DIALOG_Y,
        width=TEST_INPUT_DIALOG_WIDTH,
        height=TEST_INPUT_DIALOG_HEIGHT,
        name='test_input_dialog',
        dialog_text='Enter a value:',
        confirm_text='OK',
        cancel_text='Cancel',
        parent=parent,
        groups=pygame.sprite.LayeredDirty(),
    )


def _dialog_scene_with_input_dialog(previous_scene):
    """Create a real dialog scene and an InputDialog whose parent is that scene.

    Returns:
        tuple: (the scene, the InputDialog).
    """
    scene = InputConfirmationDialogScene(
        previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty()
    )
    return scene, _create_input_dialog(parent=scene)


def _local_center(dialog, component):
    """Return a component's centre in the dialog image's coordinates.

    Returns:
        tuple: The (x, y) point.
    """
    return (component.rect.centerx - dialog.rect.x, component.rect.centery - dialog.rect.y)


class TestInputDialogUpdate:
    """Test InputDialog.update() rendering, on its real image."""

    def test_update_fills_background(self):
        """Test that update fills the image with black background."""
        dialog = _create_input_dialog()
        assert dialog.image is not None
        dialog.image.fill(MARKER_COLOR)

        dialog.update()

        # Inside the border, above the dialog text (which starts 20 px down)
        assert _rgb_at(dialog.image, (5, 5)) == INPUT_DIALOG_BACKGROUND_COLOR
        assert _rgb_at(dialog.image, (TEST_INPUT_DIALOG_WIDTH - 5, 5)) == (
            INPUT_DIALOG_BACKGROUND_COLOR
        )

    def test_update_draws_border(self):
        """Test that update draws a 1-pixel gray border rectangle."""
        dialog = _create_input_dialog()
        assert dialog.image is not None
        dialog.image.fill(MARKER_COLOR)

        dialog.update()

        last_x = TEST_INPUT_DIALOG_WIDTH - 1
        last_y = TEST_INPUT_DIALOG_HEIGHT - 1
        for corner in [(0, 0), (last_x, 0), (0, last_y), (last_x, last_y)]:
            assert _rgb_at(dialog.image, corner) == INPUT_DIALOG_BORDER_COLOR
        assert _rgb_at(dialog.image, (1, 1)) == INPUT_DIALOG_BACKGROUND_COLOR

    def test_update_blits_all_components(self):
        """Test that update draws every nested component at its place in the dialog."""
        dialog = _create_input_dialog()
        assert dialog.image is not None
        component_colors = {
            'dialog_text_sprite': (200, 10, 10),
            'cancel_button': (10, 200, 10),
            'confirm_button': (10, 10, 200),
            'input_box': (200, 200, 10),
        }
        for component_name, color in component_colors.items():
            getattr(dialog, component_name).image.fill(color)

        dialog.update()

        for component_name, color in component_colors.items():
            component = getattr(dialog, component_name)
            assert _rgb_at(dialog.image, _local_center(dialog, component)) == color, component_name

    def test_update_marks_components_dirty(self):
        """Test that update sets dirty=1 on nested components."""
        dialog = _create_input_dialog()
        dialog.dialog_text_sprite.dirty = 0
        dialog.cancel_button.dirty = 0
        dialog.confirm_button.dirty = 0

        dialog.update()

        assert dialog.dialog_text_sprite.dirty == 1
        assert dialog.cancel_button.dirty == 1
        assert dialog.confirm_button.dirty == 1


class TestInputDialogConfirmEvent:
    """Test InputDialog.on_confirm_event()."""

    def test_confirm_event_delegates_to_parent(self, previous_scene):
        """The confirm reaches the parent dialog scene, which returns to the previous scene."""
        scene, dialog = _dialog_scene_with_input_dialog(previous_scene)

        dialog.on_confirm_event(event=_mouse_up((0, 0)), trigger=dialog.confirm_button)

        assert scene.next_scene is previous_scene

    def test_confirm_event_without_parent(self, caplog):
        """With no parent, a confirm is only logged."""
        dialog = _create_input_dialog(parent=None)

        with caplog.at_level(logging.INFO, logger='game.ui'):
            dialog.on_confirm_event(event=_mouse_up((0, 0)), trigger=dialog.confirm_button)

        assert 'test_input_dialog: Got confirm event!' in caplog.text


class TestInputDialogCancelEvent:
    """Test InputDialog.on_cancel_event()."""

    def test_cancel_event_delegates_to_parent(self, previous_scene):
        """The cancel reaches the parent dialog scene, which returns to the previous scene."""
        scene, dialog = _dialog_scene_with_input_dialog(previous_scene)

        dialog.on_cancel_event(event=_mouse_up((0, 0)), trigger=dialog.cancel_button)

        assert scene.next_scene is previous_scene

    def test_cancel_event_without_parent(self, caplog):
        """With no parent, a cancel is only logged."""
        dialog = _create_input_dialog(parent=None)

        with caplog.at_level(logging.INFO, logger='game.ui'):
            dialog.on_cancel_event(event=_mouse_up((0, 0)), trigger=dialog.cancel_button)

        assert 'test_input_dialog: Got cancel event!' in caplog.text


class TestInputDialogInputBoxSubmitEvent:
    """Test InputDialog.on_input_box_submit_event()."""

    def test_input_box_submit_calls_confirm_event(self, previous_scene):
        """A submit from the input box confirms: a load dialog hands its text to the canvas."""
        scene = LoadDialogScene(previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty())
        input_box = scene.dialog.input_box
        input_box.name = 'test_input'
        input_box.text = 'hello world'

        scene.dialog.on_input_box_submit_event(event=input_box)

        assert previous_scene.canvas.loaded_paths == ['hello world']
        assert scene.next_scene is previous_scene


class TestInputDialogInputBoxCancelEvent:
    """Test InputDialog.on_input_box_cancel_event()."""

    def test_input_box_cancel_calls_cancel_event(self, previous_scene):
        """A cancel from the input box cancels: nothing is loaded, the dialog is dismissed."""
        scene = LoadDialogScene(previous_scene=previous_scene, groups=pygame.sprite.LayeredDirty())
        input_box = scene.dialog.input_box
        input_box.name = 'test_input'
        input_box.text = 'hello world'

        scene.dialog.on_input_box_cancel_event(control=input_box)

        assert previous_scene.canvas.loaded_paths == []
        assert scene.next_scene is previous_scene


class TestInputDialogMouseButtonUpEvent:
    """Test InputDialog.on_mouse_button_up_event()."""

    def test_click_within_input_box_activates(self):
        """Test clicking within input box bounds activates it."""
        dialog = _create_input_dialog()
        dialog.input_box.deactivate()

        # Position within the input box rect
        assert dialog.input_box.rect is not None
        dialog.on_mouse_button_up_event(_mouse_up(dialog.input_box.rect.center))

        assert dialog.input_box.is_active is True

    def test_click_outside_input_box_deactivates(self):
        """Test clicking outside input box bounds deactivates it."""
        dialog = _create_input_dialog()
        dialog.input_box.activate()

        # Position far outside the input box
        dialog.on_mouse_button_up_event(_mouse_up((0, 0)))

        assert dialog.input_box.is_active is False


class TestInputDialogKeyUpEvent:
    """Test InputDialog.on_key_up_event()."""

    def test_key_up_routes_to_active_input_box(self):
        """A key-up reaches the active input box (Escape's release deactivates it)."""
        dialog = _create_input_dialog()
        dialog.input_box.is_active = True

        dialog.on_key_up_event(_key_up(pygame.K_ESCAPE))

        assert dialog.input_box.is_active is False

    def test_key_up_tab_activates_input_box(self):
        """Test Tab key activates the input box when it is inactive."""
        dialog = _create_input_dialog()
        dialog.input_box.is_active = False

        dialog.on_key_up_event(_key_up(pygame.K_TAB))

        assert dialog.input_box.is_active is True

    def test_key_up_non_tab_when_inactive_calls_super(self):
        """A non-Tab key-up with the input box inactive changes nothing."""
        dialog = _create_input_dialog()
        dialog.input_box.is_active = False

        dialog.on_key_up_event(_key_up(pygame.K_ESCAPE))

        assert dialog.input_box.is_active is False
        assert not dialog.input_box.text


class TestInputDialogKeyDownEvent:
    """Test InputDialog.on_key_down_event()."""

    def test_key_down_tab_activates_input_box(self):
        """Test Tab key activates the input box (and types no tab)."""
        dialog = _create_input_dialog()
        dialog.input_box.is_active = False

        dialog.on_key_down_event(_key_down(pygame.K_TAB, unicode='\t'))

        assert dialog.input_box.is_active is True
        assert not dialog.input_box.text

    def test_key_down_routes_to_input_box(self):
        """A non-Tab key-down types into the input box, which redraws its text."""
        dialog = _create_input_dialog()
        empty_text_width = dialog.input_box.text_image.get_width()

        dialog.on_key_down_event(_key_down(pygame.K_a, unicode='a'))

        assert dialog.input_box.text == 'a'
        assert dialog.input_box.text_image.get_width() > empty_text_width


class TestInputDialogUpdateNestedSprites:
    """Test InputDialog.update_nested_sprites()."""

    def test_update_nested_sprites_syncs_dirty(self):
        """Test update_nested_sprites syncs dirty flag to buttons."""
        dialog = _create_input_dialog()
        dialog.dirty = 2

        dialog.update_nested_sprites()

        assert dialog.cancel_button.dirty == 2
        assert dialog.confirm_button.dirty == 2
