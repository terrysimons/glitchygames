"""Tests for bitmappy.editor_setup: placement of the AI panel, undo and voice setup."""

import logging
from types import SimpleNamespace

import pygame

from bitmappy import editor_setup
from bitmappy.editor_setup import EditorSetup

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
DEBUG_TEXT_HEIGHT = 186
AI_LABEL_HEIGHT = 20


def make_editor_stand_in(**attributes) -> SimpleNamespace:
    """Build the smallest editor the setup delegate's debug text box needs.

    Args:
        **attributes: Extra attributes to set on the editor.

    Returns:
        The editor stand-in.

    """
    editor = SimpleNamespace(
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
        all_sprites=pygame.sprite.LayeredDirty(),
        color_well=None,
        film_strips={},
    )
    for name, value in attributes.items():
        setattr(editor, name, value)
    return editor


class TestSetupDebugTextBox:
    """Test EditorSetup.setup_debug_text_box placement."""

    def test_without_color_well_the_panel_takes_the_rightmost_200_pixels(self):
        """With no color well, the panel starts 200 pixels from the right edge."""
        editor = make_editor_stand_in()

        EditorSetup(editor=editor).setup_debug_text_box()  # type: ignore[arg-type]

        assert editor.debug_text.rect.x == SCREEN_WIDTH - 200
        assert editor.debug_text.rect.width == 200
        assert editor.debug_text.rect.y == SCREEN_HEIGHT - DEBUG_TEXT_HEIGHT
        assert editor.ai_label.rect.y == SCREEN_HEIGHT - DEBUG_TEXT_HEIGHT - AI_LABEL_HEIGHT

    def test_panel_sits_30_pixels_below_the_second_film_strip(self):
        """With two film strips, the panel is placed 30 pixels below the second one."""
        color_well = SimpleNamespace(rect=pygame.Rect(0, 0, 500, 50))
        film_strips = {
            'idle': SimpleNamespace(rect=pygame.Rect(501, 0, 299, 100)),
            'walk': SimpleNamespace(rect=pygame.Rect(501, 100, 299, 100)),
        }
        editor = make_editor_stand_in(color_well=color_well, film_strips=film_strips)

        EditorSetup(editor=editor).setup_debug_text_box()  # type: ignore[arg-type]

        assert editor.debug_text.rect.x == 501
        assert editor.debug_text.rect.width == SCREEN_WIDTH - 501
        assert editor.debug_text.rect.y == 200 + 30
        assert editor.ai_label.rect.y == 200 + 30 - AI_LABEL_HEIGHT

    def test_panel_below_a_low_second_strip_is_clamped_to_the_screen(self):
        """A second strip near the bottom cannot push the panel off the screen."""
        film_strips = {
            'idle': SimpleNamespace(rect=pygame.Rect(600, 0, 200, 100)),
            'walk': SimpleNamespace(rect=pygame.Rect(600, 500, 200, 90)),
        }
        editor = make_editor_stand_in(film_strips=film_strips)

        EditorSetup(editor=editor).setup_debug_text_box()  # type: ignore[arg-type]

        assert editor.debug_text.rect.y == SCREEN_HEIGHT - DEBUG_TEXT_HEIGHT

    def test_second_strip_without_rect_places_the_panel_at_the_top(self):
        """A second strip that has no rect yet counts as ending at y=0."""
        film_strips = {
            'idle': SimpleNamespace(rect=pygame.Rect(600, 0, 200, 100)),
            'walk': SimpleNamespace(),
        }
        editor = make_editor_stand_in(film_strips=film_strips)

        EditorSetup(editor=editor).setup_debug_text_box()  # type: ignore[arg-type]

        assert editor.debug_text.rect.y == 30

    def test_film_strips_changing_mid_read_place_the_panel_at_the_top(self, mocker):
        """A film strip mapping that fails while being read counts as ending at y=0."""
        film_strips = mocker.MagicMock()
        film_strips.__bool__.return_value = True
        film_strips.__len__.return_value = 2
        film_strips.values.side_effect = KeyError('strip removed')
        editor = make_editor_stand_in(film_strips=film_strips)

        EditorSetup(editor=editor).setup_debug_text_box()  # type: ignore[arg-type]

        assert editor.debug_text.rect.y == 30


class TestInitUndoRedoSystem:
    """Test EditorSetup.init_undo_redo_system."""

    def test_already_initialized_editor_keeps_its_font(self):
        """An editor the engine already initialized keeps its font option."""
        editor = SimpleNamespace(
            options={'font_name': 'courier'},
            _initialized=True,
        )

        EditorSetup(editor=editor).init_undo_redo_system()  # type: ignore[arg-type]

        assert editor.options['font_name'] == 'courier'
        assert editor.undo_redo_manager.max_history == 50
        assert editor.current_pixel_changes == []
        assert editor.pixel_change_timer is None


class FakeVoiceEventManager:
    """A stand-in VoiceEventManager that records commands instead of opening a microphone."""

    def __init__(self, logger=None) -> None:
        """Record the logger and start with no commands, not listening."""
        self.logger = logger
        self.commands = {}
        self.listening = False

    def is_available(self) -> bool:
        """Report a microphone as available.

        Returns:
            bool: Always True.

        """
        return True

    def register_command(self, phrase, callback) -> None:
        """Remember the callback for the phrase."""
        self.commands[phrase] = callback

    def start_listening(self) -> None:
        """Mark the manager as listening."""
        self.listening = True


class UnavailableVoiceEventManager(FakeVoiceEventManager):
    """A stand-in VoiceEventManager that finds no microphone."""

    def is_available(self) -> bool:
        """Report no microphone.

        Returns:
            bool: Always False.

        """
        return False


class TestSetupVoiceRecognition:
    """Test EditorSetup.setup_voice_recognition with a voice manager present."""

    def test_available_voice_manager_registers_commands_and_listens(self, mocker):
        """An available voice manager gets every clear command and starts listening."""
        mocker.patch.object(editor_setup, 'VoiceEventManager', FakeVoiceEventManager)
        cleared = []
        editor = SimpleNamespace(
            log=logging.getLogger('test.editor_setup'),
            clear_ai_sprite_box=lambda: cleared.append(True),
        )

        EditorSetup(editor=editor).setup_voice_recognition()  # type: ignore[arg-type]

        voice_manager = editor.voice_manager
        assert isinstance(voice_manager, FakeVoiceEventManager)
        assert voice_manager.listening is True
        assert set(voice_manager.commands) == {
            'clear the ai sprite box',
            'clear ai sprite box',
            'clear ai box',
            'clear the ai sprite',
            'clear ai sprite',
            'clear the ai sprite window',
            'clear ai sprite window',
        }
        voice_manager.commands['clear ai box']()
        assert cleared == [True]

    def test_voice_manager_without_microphone_is_dropped(self, mocker):
        """A voice manager that reports no microphone is discarded and never listens."""
        mocker.patch.object(editor_setup, 'VoiceEventManager', UnavailableVoiceEventManager)
        editor = SimpleNamespace(log=logging.getLogger('test.editor_setup'))

        EditorSetup(editor=editor).setup_voice_recognition()  # type: ignore[arg-type]

        assert editor.voice_manager is None
