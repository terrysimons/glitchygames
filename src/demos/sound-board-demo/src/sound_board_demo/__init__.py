"""Sound Board Demo: hear every built-in wave and noise, and compare notes, hertz and steps.

Run it with the ``sound-board-demo`` console script or ``python -m sound_board_demo``.

One row per built-in wave and noise, each row showing the eight notes of C major. The keys:

* 1-8 play the current row's notes.
* Up and Down pick the row (the current row is lit).
* L cycles the labels between note names, hertz and scale steps. Only the labels change: the
  same pitches play.
* C plays a C major chord on the current row.

The Audio debug panel is on by default (``--sound-diagnostics``): it shows the voices playing
and the compile log. Every sound is requested in ``setup()``, so the log shows only setup
compiles and playing a key never compiles anything.
"""

from __future__ import annotations

import dataclasses
import sys
from typing import TYPE_CHECKING, Final, Self, cast, override

if TYPE_CHECKING:
    import argparse

    from glitchygames.audio import Hz, Note, Sound
    from glitchygames.events.base import KeyEvent

import pygame

from glitchygames.audio import Instrument, Noise, Scale
from glitchygames.engine import GameEngine
from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import DEFAULT_FONT_NAME
from glitchygames.input.action_map import ActionMap
from glitchygames.scenes import Scene

# The physical keys that play the current row's eight notes: 1 to 8 (a scancode is the same place
# on every keyboard layout)
STEP_SCANCODES: Final[tuple[int, ...]] = (
    pygame.KSCAN_1,
    pygame.KSCAN_2,
    pygame.KSCAN_3,
    pygame.KSCAN_4,
    pygame.KSCAN_5,
    pygame.KSCAN_6,
    pygame.KSCAN_7,
    pygame.KSCAN_8,
)
STEPS_PER_ROW: Final = len(STEP_SCANCODES)
# The chord C plays, on the current row
CHORD_NOTE_NAMES: Final[tuple[str, ...]] = ('C4', 'E4', 'G4')
SCALE: Final = Scale('C', 'major')
# How loud every key plays (the built-in waves and noise are full scale)
PLAY_VOLUME: Final = 0.5

# The labels L cycles through
LABEL_NOTE_NAMES: Final = 'note names'
LABEL_HERTZ: Final = 'hertz'
LABEL_SCALE_STEPS: Final = 'scale steps'
LABEL_MODES: Final[tuple[str, ...]] = (LABEL_NOTE_NAMES, LABEL_HERTZ, LABEL_SCALE_STEPS)

# Layout, in pixels
TITLE_HEIGHT: Final = 36
ROW_HEIGHT: Final = 40
ROW_NAME_WIDTH: Final = 150
CELL_WIDTH: Final = 56
CELL_HEIGHT: Final = 32
CELL_GAP: Final = 4
MARGIN: Final = 8
FONT_SIZE: Final = 16

BACKGROUND_RGB: Final = (16, 16, 32)
ROW_RGB: Final = (48, 48, 80)
SELECTED_ROW_RGB: Final = (200, 120, 40)
TEXT_RGB: Final = (255, 255, 255)

# The actions the keys are bound to
ACTION_ROW_UP: Final = 'row_up'
ACTION_ROW_DOWN: Final = 'row_down'
ACTION_CYCLE_LABELS: Final = 'cycle_labels'
ACTION_CHORD: Final = 'chord'
STEP_ACTIONS: Final[tuple[str, ...]] = tuple(f'step_{index}' for index in range(STEPS_PER_ROW))

HELP_TEXT: Final = '1-8 play   Up/Down row   L labels   C chord   Esc quit'


@dataclasses.dataclass(frozen=True, slots=True)
class SoundRow:
    """One row of the board: a built-in wave or noise.

    Attributes:
        name: The name drawn at the row's left.
        instrument: The instrument every note and the chord of the row play.
    """

    name: str
    instrument: Instrument


def built_in_rows() -> tuple[SoundRow, ...]:
    """Make one row for each built-in wave and noise (feature spec 3.1, 3.2 and W1).

    Returns:
        The rows, waves first, then the noises.
    """
    # normalize=True: a chord sums three full-scale notes and would clip (and log a warning)
    waves = ('sine', 'triangle', 'saw', 'square', 'pulse_12', 'pulse_25', 'pulse_75')
    return (
        *(SoundRow(name=wave, instrument=Instrument(wave=wave, normalize=True)) for wave in waves),
        SoundRow(name='white noise', instrument=Instrument(noise=Noise('white'), normalize=True)),
        SoundRow(
            name='lfsr 15-bit', instrument=Instrument(noise=Noise('lfsr', bits=15), normalize=True)
        ),
        SoundRow(
            name='lfsr 7-bit', instrument=Instrument(noise=Noise('lfsr', bits=7), normalize=True)
        ),
    )


class Game(Scene):
    """The Sound Board scene."""

    NAME = 'Sound Board Demo'
    VERSION = '1.0'

    def __init__(
        self: Self,
        options: dict[str, object],
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize the board: its rows, its keys and its font.

        Args:
            options (dict[str, object]): The options passed to the game.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()  # type: ignore[type-arg]

        super().__init__(options=options, groups=groups)  # type: ignore[arg-type]
        self.rows = built_in_rows()
        self.selected_row_index = 0
        self.label_mode_index = 0
        # Filled by setup(): every sound the board can play, by (row index, step index) and by
        # row index (the chords)
        self.note_sounds: dict[tuple[int, int], Sound] = {}
        self.chord_sounds: dict[int, Sound] = {}
        self.action_map = self._create_action_map(options=options)
        # The bundled default font, loaded from its file through FontManager (as the other demos)
        self.font = cast(
            'pygame.font.Font',
            FontManager.pygame_font(
                font_config={'font_name': DEFAULT_FONT_NAME, 'font_size': FONT_SIZE}
            ),
        )

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> None:
        """Add game-specific arguments to the global parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        """
        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'{cls.NAME} {cls.VERSION}',
            help='print the game version and exit',
        )

    @staticmethod
    def _create_action_map(*, options: dict[str, object]) -> ActionMap:
        """Bind the board's keys by physical key position (scancode).

        Args:
            options: The engine's options: the map follows its input mode and axis deadzone.

        Returns:
            The map.

        """
        action_map = ActionMap.from_engine_options(options)
        for action, scancode in zip(STEP_ACTIONS, STEP_SCANCODES, strict=True):
            action_map.bind(action, scancode=scancode)
        action_map.bind(ACTION_ROW_UP, scancode=pygame.KSCAN_UP)
        action_map.bind(ACTION_ROW_DOWN, scancode=pygame.KSCAN_DOWN)
        action_map.bind(ACTION_CYCLE_LABELS, scancode=pygame.KSCAN_L)
        action_map.bind(ACTION_CHORD, scancode=pygame.KSCAN_C)
        return action_map

    @override
    def setup(self: Self) -> None:
        """Request every sound the board can play, so playing a key never compiles one.

        The scene manager marks these compiles as setup's (the Audio panel's compile log shows
        only them).
        """
        audio = self.scene_manager.audio
        chord_pitches = list(CHORD_NOTE_NAMES)
        for row_index, row in enumerate(self.rows):
            for step_index in range(STEPS_PER_ROW):
                self.note_sounds[row_index, step_index] = audio.sound(
                    row.instrument, pitch=self.step_pitch(step_index=step_index)
                )
            self.chord_sounds[row_index] = audio.sound(row.instrument, chord=chord_pitches)

    def step_pitch(self: Self, *, step_index: int) -> Note:
        """Return the note of one of the row's eight steps.

        Args:
            step_index: The step, 0 to 7.

        Returns:
            The note of the current scale at that step.

        """
        return SCALE.step(step_index)

    def step_label(self: Self, *, step_index: int) -> str:
        """Return the label drawn on one step with the current label mode.

        Args:
            step_index: The step, 0 to 7.

        Returns:
            The note name, the hertz or the scale step number.

        """
        mode = LABEL_MODES[self.label_mode_index]
        if mode == LABEL_NOTE_NAMES:
            return self.step_pitch(step_index=step_index).name
        if mode == LABEL_HERTZ:
            hertz: Hz = self.step_pitch(step_index=step_index).to_hz()
            return f'{hertz:.2f} Hz'
        return str(step_index)

    def cell_rect(self: Self, *, row_index: int, step_index: int) -> pygame.Rect:
        """Return where one step of one row is drawn.

        Args:
            row_index: The row.
            step_index: The step, 0 to 7.

        Returns:
            The cell's rectangle on the screen.

        """
        return pygame.Rect(
            MARGIN + ROW_NAME_WIDTH + step_index * (CELL_WIDTH + CELL_GAP),
            TITLE_HEIGHT + row_index * ROW_HEIGHT,
            CELL_WIDTH,
            CELL_HEIGHT,
        )

    @override
    def render(self: Self, screen: pygame.Surface) -> None:
        """Draw the board: the title, every row's name and cells, and the keys.

        Drawn after the scene's own render: its first render clears the whole screen to the
        scene's background, which would wipe a picture drawn in ``update()``.

        Args:
            screen (pygame.Surface): The screen to render to.

        """
        super().render(screen)
        screen.fill(BACKGROUND_RGB)
        self._draw_text(
            screen,
            f'Labels: {LABEL_MODES[self.label_mode_index]}  (scale: C major)',
            (MARGIN, MARGIN),
        )
        for row_index, row in enumerate(self.rows):
            selected = row_index == self.selected_row_index
            cell_color = SELECTED_ROW_RGB if selected else ROW_RGB
            first_cell = self.cell_rect(row_index=row_index, step_index=0)
            self._draw_text(screen, row.name, (MARGIN, first_cell.y + 8))
            for step_index in range(STEPS_PER_ROW):
                cell = self.cell_rect(row_index=row_index, step_index=step_index)
                screen.fill(cell_color, cell)
                self._draw_text(
                    screen, self.step_label(step_index=step_index), (cell.x + 3, cell.y + 8)
                )
        self._draw_text(screen, HELP_TEXT, (MARGIN, TITLE_HEIGHT + len(self.rows) * ROW_HEIGHT + 4))

    def _draw_text(
        self: Self, screen: pygame.Surface, text: str, position: tuple[int, int]
    ) -> None:
        """Draw one line of text.

        Args:
            screen: The screen to draw on.
            text: The text.
            position: The top left of the text.

        """
        screen.blit(self.font.render(text, FontManager.antialias(), TEXT_RGB), position)

    @override
    def on_key_down_event(self: Self, event: KeyEvent) -> None:
        """Play, pick a row or change the labels for a bound key; hand any other key on.

        Args:
            event (KeyEvent): The event to handle.

        """
        actions = self.action_map.get_actions(event)
        if not actions:
            # Not ours (Escape quits, for one)
            super().on_key_down_event(event)
            return
        for action in actions:
            self._do_action(action)

    def _do_action(self: Self, action: str) -> None:
        """Carry out one of the board's actions.

        Args:
            action: The action's name.

        """
        row_count = len(self.rows)
        if action in STEP_ACTIONS:
            self.note_sounds[self.selected_row_index, STEP_ACTIONS.index(action)].play(
                volume=PLAY_VOLUME
            )
        elif action == ACTION_CHORD:
            self.chord_sounds[self.selected_row_index].play(volume=PLAY_VOLUME)
        elif action == ACTION_ROW_UP:
            self.selected_row_index = (self.selected_row_index - 1) % row_count
        elif action == ACTION_ROW_DOWN:
            self.selected_row_index = (self.selected_row_index + 1) % row_count
        else:
            self.label_mode_index = (self.label_mode_index + 1) % len(LABEL_MODES)


def main() -> None:
    """Run the main entry point for the demo, with the Audio debug panel on.

    The panel is on unless the user passes flags of their own (``--sound-diagnostics`` is the
    engine's option for it).
    """
    if len(sys.argv) == 1:
        sys.argv = [*sys.argv, '--sound-diagnostics']
    GameEngine(game=Game).start()
