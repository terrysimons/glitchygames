"""The AI console: a read-only conversation with the local AI, around any game.

It belongs to the AI's host layer (``glitchygames/ai_host.py``), so a game needs nothing to have
it, and a run without AI never imports this. The ` key opens and closes it, by the character or by
its US position (left of 1), so a layout without the key still has one. No game binds either.

The rules:

1. Read-only. ``/ask`` and ``/inspect`` read the scene and print text. Nothing here changes the
   game.
2. Never in a recording. These doors sit beneath the recorder, so the keys typed here are hidden
   from the recorder as they are from the game, and the console is drawn with the doors' overlay,
   which is never in a screenshot or a trace. A recording of a run that used it replays without it.
3. Typing never moves the player. While it's open every key goes here, from both the events and the
   polled snapshot. A key the game saw pressed gets its release as the console opens, and a key
   still held as it closes stays hidden until it's released, so the game never sees half a press.
   The debug overlay's keys still work. The mouse still reaches the game. A key press the game
   posts itself while the console is open (none of ours does) is hidden as typing would be.
4. It doesn't pause the game. Pausing belongs to the game, so pause it first if that matters: the
   console works over the pause screen, and inspects the paused game.
5. The frame never waits. Requests, the model's stream and the history file all live on a worker
   thread, which hands updates to the main thread through a deque. With the console closed and
   nothing to say, ``filter_events`` is one truth test and a loop over the batch's keys, and nothing
   is drawn.
"""

from __future__ import annotations

import collections
import dataclasses
import json
import logging
import threading
from collections.abc import Callable  # ruff: ignore[typing-only-standard-library-import] - pydantic reads it at runtime
from functools import partial
from typing import TYPE_CHECKING, Any

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames import clock
from glitchygames.ai_link import LinkState
from glitchygames.debug.overlay import OVERLAY_KEYS, load_debug_font
from glitchygames.debug.panels import HUD_TEXT_COLOR, blit_text
from glitchygames.fonts import FontManager

if TYPE_CHECKING:
    from pathlib import Path

    from glitchygames.ai_link import AiLink
    from glitchygames.input.state import InputSnapshot
    from glitchygames.scenes import Scene

LOG = logging.getLogger('game.ai_console')

TOGGLE_KEY = pygame.K_BACKQUOTE
TOGGLE_SCANCODE = pygame.KSCAN_GRAVE
KEYBOARD_EVENT_TYPES = frozenset({
    pygame.KEYDOWN,
    pygame.KEYUP,
    pygame.TEXTINPUT,
    pygame.TEXTEDITING,
})

BACKGROUND_COLOR = (10, 12, 24, 225)
INPUT_COLOR = (255, 255, 255)
YOU_COLOR = (120, 200, 255)
ANSWER_COLOR = HUD_TEXT_COLOR
NOTE_COLOR = (150, 160, 180)
ERROR_COLOR = (255, 120, 110)
MARGIN_PIXELS = 6
LINE_HEIGHT_PIXELS = 16
HEIGHT_FRACTION = 0.6
PAGE_LINES = 8

MAXIMUM_TRANSCRIPT_LINES = 500
MAXIMUM_RECALLED_INPUTS = 100
# Earlier questions and answers sent along, so a follow-up question makes sense
MAXIMUM_CONVERSATION_MESSAGES = 8
MAXIMUM_DESCRIBED_SPRITES = 40
MAXIMUM_HISTORY_RECORDS = 1000
MAXIMUM_HISTORY_LINES_SHOWN = 20
QUESTION_PREVIEW_CHARACTERS = 100
# Reasoning can run for minutes on the biggest model, so an interactive question asks for the least
REASONING_EFFORT = 'low'
SYSTEM_PROMPT = (
    'You are a helper inside a running video game, talking to its developer in a small console. '
    'You can see only the state given below, and you cannot change anything. Answer briefly, in '
    'plain text, without Markdown. If the state does not say, say that you do not know.'
)


@dataclasses.dataclass(eq=False)
class TranscriptLine:
    """One entry on screen. A running request changes its own."""

    text: str
    color: tuple[int, int, int]


@dataclasses.dataclass(eq=False)
class AiRequest:
    """One question, from asked to answered. Only the main thread changes its text."""

    number: int
    question: str
    started_seconds: float
    answer: str = ''
    reasoning_pieces: int = 0
    answer_pieces: int = 0
    line: TranscriptLine | None = None
    # Set by the main thread, read by the worker, which stops reading the stream when it can
    cancelled: threading.Event = dataclasses.field(default_factory=threading.Event)


class ConsoleCommand(BaseModel):
    """One slash command. The help and the completion both come from these."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str
    usage: str
    summary: str
    run: Callable[[str], None]


def describe_sprite(*, sprite: object) -> dict[str, Any]:
    """Describe one sprite from what the engine knows of every sprite.

    Args:
        sprite: The sprite, read and never changed.

    Returns:
        JSON-ready facts: its name and class, and whichever of the rest it has.

    """
    description: dict[str, Any] = {
        'name': getattr(sprite, 'name', None) or type(sprite).__name__,
        'class': type(sprite).__name__,
    }
    rect = getattr(sprite, 'rect', None)
    if rect is not None:
        description['rect'] = [rect.x, rect.y, rect.width, rect.height]
    for attribute in ('visible', 'world_x', 'world_y', 'velocity_x', 'velocity_y'):
        value = getattr(sprite, attribute, None)
        if value is not None:
            description[attribute] = round(value, 2) if isinstance(value, float) else value
    return description


def describe_scene(*, scene: Scene | None) -> dict[str, Any]:
    """Describe the scene for the player and the model, from its own state.

    Args:
        scene: The scene on screen, or None before the first frame has ended.

    Returns:
        JSON-ready facts. A pause screen describes the game it paused, as the debug overlay does.

    """
    if scene is None:
        return {'scene': None}
    subject = scene.debug_subject
    sprites = list(subject.all_sprites)
    return {
        'scene': subject.NAME,
        'class': type(subject).__name__,
        'paused': subject is not scene,
        'game_time_seconds': round(subject.game_time, 2),
        'screen': [subject.screen_width, subject.screen_height],
        'game': subject.describe_for_ai(),
        'sprite_count': len(sprites),
        'sprites': [
            describe_sprite(sprite=sprite) for sprite in sprites[:MAXIMUM_DESCRIBED_SPRITES]
        ],
    }


def wrapped_lines(*, text: str, font: pygame.font.Font, width: int) -> list[str]:
    """Wrap text to a pixel width, on spaces, breaking any word too long to fit.

    Args:
        text: The text, which may hold newlines.
        font: The font it will be drawn in.
        width: The width in pixels.

    Returns:
        The lines. A blank line of the text stays one.

    """
    lines: list[str] = []
    for paragraph in text.split('\n'):
        line = ''
        for word in paragraph.split(' '):
            candidate = f'{line} {word}' if line else word
            if font.size(candidate)[0] <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
            line = word
            while font.size(line)[0] > width and len(line) > 1:
                fitting = len(line) - 1
                while fitting > 1 and font.size(line[:fitting])[0] > width:
                    fitting -= 1
                lines.append(line[:fitting])
                line = line[fitting:]
        lines.append(line)
    return lines


class AiConsole:
    """The console's state, input, drawing and requests."""

    def __init__(
        self,
        *,
        link: AiLink,
        install_root: Path,
        service_url: str | None = None,
    ) -> None:
        """Prepare the console, closed. Nothing is loaded until it's first drawn or used.

        Args:
            link: The game's session with the service: its state, and the models it reported.
            install_root: Where the service is installed, and where history is kept.
            service_url: Where its REST API listens. None is the client's default.

        """
        self.link = link
        self.install_root = install_root
        self.service_url = service_url
        self.is_open = False
        self.hidden_scancodes: set[int] = set()
        self.input_text = ''
        self.cursor = 0
        self.running: AiRequest | None = None
        self.requests_made = 0
        self.requests_failed = 0
        self.requests_cancelled = 0
        self.last_seconds: float | None = None
        self.last_pieces = 0
        self.unread_answer = False
        self.scene: Scene | None = None
        self._held: dict[int, pygame.event.Event] = {}
        self._updates: collections.deque[Callable[[], object]] = collections.deque()
        self._transcript: collections.deque[TranscriptLine] = collections.deque(
            maxlen=MAXIMUM_TRANSCRIPT_LINES
        )
        self._recalled: collections.deque[str] = collections.deque(maxlen=MAXIMUM_RECALLED_INPUTS)
        self._recall_position: int | None = None
        self._conversation: list[dict[str, str]] = []
        self._scroll_lines = 0
        self._font: pygame.font.Font | None = None
        self._panel: pygame.Surface | None = None
        self._notice: pygame.Surface | None = None
        self.commands = {
            command.name: command
            for command in (
                ConsoleCommand(
                    name='ask',
                    usage='/ask QUESTION',
                    summary='ask the AI about what is on screen (or just type the question)',
                    run=self._ask,
                ),
                ConsoleCommand(
                    name='inspect',
                    usage='/inspect [NAME]',
                    summary='show the scene, or the sprites with NAME in their name',
                    run=self._inspect,
                ),
                ConsoleCommand(
                    name='ai',
                    usage='/ai',
                    summary='show the connection, the models and the requests so far',
                    run=self._status,
                ),
                ConsoleCommand(
                    name='cancel',
                    usage='/cancel',
                    summary='stop the request that is running',
                    run=self._cancel,
                ),
                ConsoleCommand(
                    name='history',
                    usage='/history [TEXT | clear]',
                    summary="this game's past questions, those holding TEXT, or forget them",
                    run=self._history,
                ),
                ConsoleCommand(
                    name='clear',
                    usage='/clear',
                    summary='empty this screen, and start the conversation over',
                    run=self._clear,
                ),
                ConsoleCommand(
                    name='help',
                    usage='/help [COMMAND]',
                    summary='list the commands, or show one',
                    run=self._help,
                ),
            )
        }
        self._editing_keys: dict[int, Callable[[], None]] = {
            pygame.K_ESCAPE: self._close,
            pygame.K_RETURN: self._submit,
            pygame.K_KP_ENTER: self._submit,
            pygame.K_BACKSPACE: self._delete_left,
            pygame.K_DELETE: self._delete_right,
            pygame.K_LEFT: lambda: self._move_cursor(self.cursor - 1),
            pygame.K_RIGHT: lambda: self._move_cursor(self.cursor + 1),
            pygame.K_HOME: lambda: self._move_cursor(0),
            pygame.K_END: lambda: self._move_cursor(len(self.input_text)),
            pygame.K_UP: lambda: self._recall(step=-1),
            pygame.K_DOWN: lambda: self._recall(step=1),
            pygame.K_PAGEUP: lambda: self._scroll(PAGE_LINES),
            pygame.K_PAGEDOWN: lambda: self._scroll(-PAGE_LINES),
            pygame.K_TAB: self._complete,
        }
        self._add_line(text='AI console: read-only. /help lists commands. Esc or ` closes.')

    # The doors' side: called on the main thread, every frame

    @property
    def needs_drawing(self) -> bool:
        """Whether anything is on screen: the console, or word of an answer waiting in it."""
        return self.is_open or self.unread_answer

    def filter_events(self, *, events: list[pygame.event.Event]) -> list[pygame.event.Event]:
        """Apply what the worker sent, then take this batch's keys that belong to the console.

        Args:
            events: The host's batch.

        Returns:
            What the game should see: the batch without those keys, plus a release for each key the
            game saw pressed if the console opened.

        """
        while self._updates:
            self._updates.popleft()()
        kept: list[pygame.event.Event] = []
        for event in events:
            if event.type not in KEYBOARD_EVENT_TYPES:
                kept.append(event)
            elif event.type == pygame.KEYDOWN:
                self._filter_key_down(event=event, kept=kept)
            elif event.type == pygame.KEYUP:
                self._filter_key_up(event=event, kept=kept)
            elif not self.is_open and not self.hidden_scancodes:
                # Text from a key the console took would arrive just after that key
                kept.append(event)
        return kept

    def masked_snapshot(self, *, snapshot: InputSnapshot) -> InputSnapshot:
        """Hide the console's keys from the frame's polled input.

        Args:
            snapshot: The host's snapshot.

        Returns:
            The snapshot the game should see: the same one when the console has nothing to hide.

        """
        if not self.is_open and not self.hidden_scancodes:
            return snapshot
        return dataclasses.replace(
            snapshot,
            pressed_scancodes=snapshot.pressed_scancodes - self.hidden_scancodes,
            modifiers=0 if self.is_open else snapshot.modifiers,
        )

    def draw(self, *, surface: pygame.Surface) -> None:
        """Draw the console, or the note that an answer is waiting, over the presented frame.

        Args:
            surface: The presented frame.

        """
        if self._font is None:
            self._font = load_debug_font()
        if not self.is_open:
            if self._notice is None:
                self._notice = self._rendered(text='AI replied: ` to read', color=NOTE_COLOR)
            blit_text(
                surface=surface, text_surface=self._notice, position=(MARGIN_PIXELS, MARGIN_PIXELS)
            )
            return
        if self._panel is None or self._panel.get_width() != surface.get_width():
            self._panel = self._rendered_panel(
                width=surface.get_width(), height=surface.get_height()
            )
        surface.blit(self._panel, (0, surface.get_height() - self._panel.get_height()))

    def status_lines(self) -> list[str]:
        """Describe the AI for this console's ``/ai`` and the debug overlay's AI panel.

        Returns:
            Lines of text.

        """
        lines = [f'Link: {self.link.state.value}, {self.link.round_trips} round trips']
        lines += [f'Model {model.get("id")}: {model.get("state")}' for model in self.link.models]
        lines.append(
            f'Requests: {self.requests_made} asked, {self.requests_failed} failed, '
            f'{self.requests_cancelled} cancelled'
        )
        if self.running is not None:
            lines.append(f'Running: {self._progress(request=self.running)}')
        if self.last_seconds is not None:
            lines.append(f'Last: {self.last_pieces} tokens in {self.last_seconds:.1f} s')
        return lines

    def stop(self) -> None:
        """Abandon what's running, as the run ends. Its daemon thread is never waited on."""
        if self.running is not None:
            self.running.cancelled.set()

    # Keys

    def _filter_key_down(
        self, *, event: pygame.event.Event, kept: list[pygame.event.Event]
    ) -> None:
        """Take a press that belongs to the console, or pass it to the game and remember it."""
        # A game's own posted key press may have no scancode
        scancode = getattr(event, 'scancode', None)
        if event.key == TOGGLE_KEY or scancode == TOGGLE_SCANCODE:
            self._set_open(is_open=not self.is_open, kept=kept)
            if scancode is not None:
                self.hidden_scancodes.add(scancode)
        elif not self.is_open or event.key in OVERLAY_KEYS:
            if not self.is_open and scancode is not None:
                self._held[scancode] = event
            kept.append(event)
        else:
            if scancode is not None:
                self.hidden_scancodes.add(scancode)
            self._edit(event=event)

    def _filter_key_up(self, *, event: pygame.event.Event, kept: list[pygame.event.Event]) -> None:
        """Take a release whose press was hidden from the game, or pass it on."""
        scancode: int | None = getattr(event, 'scancode', None)
        if scancode is None:
            kept.append(event)
        elif scancode in self.hidden_scancodes:
            self.hidden_scancodes.discard(scancode)
        else:
            self._held.pop(scancode, None)
            kept.append(event)

    def _set_open(self, *, is_open: bool, kept: list[pygame.event.Event]) -> None:
        """Open or close it. Opening releases, for the game, what the game saw pressed."""
        self.is_open = is_open
        self._panel = None
        if not is_open:
            return
        self.unread_answer = False
        for scancode, press in self._held.items():
            kept.append(
                pygame.event.Event(
                    pygame.KEYUP,
                    key=press.key,
                    scancode=scancode,
                    mod=0,
                    unicode='',
                    window=None,
                )
            )
            self.hidden_scancodes.add(scancode)
        self._held.clear()

    def _edit(self, *, event: pygame.event.Event) -> None:
        """Act on one key press while open."""
        self._panel = None
        action = self._editing_keys.get(event.key)
        if action is not None:
            action()
        else:
            self._type(text=getattr(event, 'unicode', ''))

    def _close(self) -> None:
        """Close it, with Esc."""
        self.is_open = False

    def _delete_left(self) -> None:
        """Delete the character before the cursor."""
        if self.cursor > 0:
            self.input_text = self.input_text[: self.cursor - 1] + self.input_text[self.cursor :]
            self.cursor -= 1

    def _delete_right(self) -> None:
        """Delete the character after the cursor."""
        self.input_text = self.input_text[: self.cursor] + self.input_text[self.cursor + 1 :]

    def _move_cursor(self, position: int) -> None:
        """Move the cursor, staying within the line."""
        self.cursor = max(0, min(len(self.input_text), position))

    def _scroll(self, lines: int) -> None:
        """Move the transcript, staying within what's there."""
        self._scroll_lines = max(0, min(len(self._transcript), self._scroll_lines + lines))

    def _type(self, *, text: str) -> None:
        """Insert printable text at the cursor."""
        if text and text.isprintable():
            self.input_text = self.input_text[: self.cursor] + text + self.input_text[self.cursor :]
            self.cursor += len(text)

    def _set_input(self, *, text: str) -> None:
        """Replace the input line, with the cursor at its end."""
        self.input_text = text
        self.cursor = len(text)

    def _recall(self, *, step: int) -> None:
        """Move through what was typed before; past the newest is an empty line."""
        if not self._recalled:
            return
        newest = len(self._recalled)
        position = newest if self._recall_position is None else self._recall_position
        position = max(0, min(newest, position + step))
        self._recall_position = position
        self._set_input(text='' if position == newest else self._recalled[position])

    def _complete(self) -> None:
        """Complete a command name, or list the choices when there are several."""
        if not self.input_text.startswith('/') or ' ' in self.input_text:
            return
        choices = [name for name in self.commands if name.startswith(self.input_text[1:])]
        if len(choices) == 1:
            self._set_input(text=f'/{choices[0]} ')
        elif choices:
            self._add_line(text=' '.join(f'/{name}' for name in choices), color=NOTE_COLOR)

    def _submit(self) -> None:
        """Run what's on the input line. Text without a slash is a question."""
        text = self.input_text.strip()
        self._set_input(text='')
        self._recall_position = None
        self._scroll_lines = 0
        if not text:
            return
        if not self._recalled or self._recalled[-1] != text:
            self._recalled.append(text)
        self._add_line(text=f'> {text}', color=YOU_COLOR)
        if not text.startswith('/'):
            self._ask(text)
            return
        name, _, argument = text[1:].partition(' ')
        command = self.commands.get(name)
        if command is None:
            self._add_line(text=f'No command /{name}: try /help', color=ERROR_COLOR)
        else:
            command.run(argument.strip())

    # Commands

    def _help(self, argument: str) -> None:
        """List the commands, or show one."""
        command = self.commands.get(argument.removeprefix('/'))
        if command is not None:
            self._add_line(text=f'{command.usage}: {command.summary}', color=NOTE_COLOR)
        elif argument:
            self._add_line(text=f'No command {argument}: try /help', color=ERROR_COLOR)
        else:
            for command in self.commands.values():
                self._add_line(text=f'{command.usage}: {command.summary}', color=NOTE_COLOR)

    def _clear(self, _argument: str) -> None:
        """Empty the screen, and forget the conversation so far."""
        self._transcript.clear()
        self._conversation.clear()

    def _status(self, _argument: str) -> None:
        """Print the AI's state."""
        for line in self.status_lines():
            self._add_line(text=line, color=NOTE_COLOR)

    def _inspect(self, argument: str) -> None:
        """Print the scene, or the sprites whose name holds the argument."""
        description = describe_scene(scene=self.scene)
        if description['scene'] is None:
            self._add_line(text='No scene yet', color=ERROR_COLOR)
            return
        sprites: list[dict[str, Any]] = description.pop('sprites')
        if argument:
            matches = [
                sprite for sprite in sprites if argument.casefold() in sprite['name'].casefold()
            ]
            for sprite in matches:
                self._add_line(text=json.dumps(sprite), color=ANSWER_COLOR)
            if not matches:
                self._add_line(text=f'No sprite named like {argument}', color=ERROR_COLOR)
            return
        self._add_line(text=json.dumps(description), color=ANSWER_COLOR)
        for sprite in sprites:
            self._add_line(text=json.dumps(sprite), color=ANSWER_COLOR)

    def _cancel(self, _argument: str) -> None:
        """Stop the running request. Closing its stream is what stops the model's work."""
        if self.running is None:
            self._add_line(text='Nothing is running', color=NOTE_COLOR)
            return
        self.running.cancelled.set()
        self.requests_cancelled += 1
        self._add_line(text=f'#{self.running.number} cancelled', color=NOTE_COLOR)
        self.running = None

    def _ask(self, question: str) -> None:
        """Start a question on the worker, with the scene as it is right now."""
        if not question:
            self._add_line(text='/ask QUESTION', color=NOTE_COLOR)
        elif self.running is not None:
            self._add_line(
                text=f'#{self.running.number} is still running: /cancel to stop it',
                color=ERROR_COLOR,
            )
        elif self.link.state in {
            LinkState.NOT_ENOUGH_MEMORY,
            LinkState.UNAVAILABLE,
            LinkState.REFUSED,
        }:
            self._add_line(text=f'No AI this run: {self.link.state.value}', color=ERROR_COLOR)
        else:
            self.requests_made += 1
            request = AiRequest(
                number=self.requests_made,
                question=question,
                started_seconds=clock.raw_counter_seconds(),
            )
            self.running = request
            request.line = self._add_line(text=f'#{request.number} thinking...', color=NOTE_COLOR)
            game_state = json.dumps(describe_scene(scene=self.scene))
            messages = [
                {
                    'role': 'system',
                    'content': f'{SYSTEM_PROMPT}\n\nThe game right now: {game_state}',
                },
                *self._conversation[-MAXIMUM_CONVERSATION_MESSAGES:],
                {'role': 'user', 'content': question},
            ]
            self._on_worker(work=partial(self._run_request, request, messages))

    def _history(self, argument: str) -> None:
        """Print or forget this game's past questions, reading the file on the worker."""
        path = self._history_path()
        if argument == 'clear':
            self._on_worker(work=partial(self._forget_history, path))
        else:
            self._on_worker(work=partial(self._read_history, path, argument))

    # The worker's side: these never touch console state directly, except through self._updates

    def _on_worker(self, *, work: Callable[[], None]) -> None:
        """Run work on a thread of its own, reporting anything it raises as text."""

        def guarded() -> None:
            try:
                work()
            except Exception as error:
                LOG.exception('The AI console failed')
                self._updates.append(partial(self._add_line, text=str(error), color=ERROR_COLOR))

        threading.Thread(target=guarded, name='ai-console', daemon=True).start()

    def _run_request(self, request: AiRequest, messages: list[dict[str, str]]) -> None:
        """Stream one answer to the main thread, then keep a record of it."""
        # Imported here, on this thread: a run that asks nothing never loads it
        from glitchygames.ai.local_service import LocalAIServiceError

        outcome = 'answered'
        answer = ''
        try:
            answer = self._read_stream(request=request, messages=messages)
        # ValueError: a stream line that wasn't JSON. Either way the request must end
        except (LocalAIServiceError, ValueError) as error:
            outcome = 'failed'
            self._updates.append(partial(self._failed, request, str(error)))
        if request.cancelled.is_set():
            outcome = 'cancelled'
        elif outcome == 'answered':
            self._updates.append(partial(self._finished, request))
        self._write_history(request=request, outcome=outcome, answer=answer, messages=messages)

    def _read_stream(self, *, request: AiRequest, messages: list[dict[str, str]]) -> str:
        """Pass each piece of the answer to the main thread, until it ends or is cancelled.

        Returns:
            The answer so far.

        """
        from glitchygames.ai.local_service import (
            DEFAULT_BASE_URL,
            REASONING_MODEL,
            LocalAIClient,
        )

        client = LocalAIClient(
            install_root=self.install_root, base_url=self.service_url or DEFAULT_BASE_URL
        )
        answer = ''
        for piece in client.stream(
            model=REASONING_MODEL, messages=messages, reasoning_effort=REASONING_EFFORT
        ):
            if request.cancelled.is_set():
                break
            if piece.is_answer:
                answer += piece.text
            self._updates.append(
                partial(self._received, request, text=piece.text, is_answer=piece.is_answer)
            )
        return answer

    def _write_history(
        self, *, request: AiRequest, outcome: str, answer: str, messages: list[dict[str, str]]
    ) -> None:
        """Append a record, with the game state the model saw, trimming the oldest."""
        path = self._history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            'at': clock.raw_wall_clock_time().isoformat(),
            'request': request.number,
            'outcome': outcome,
            'question': request.question,
            'seconds': round(clock.raw_counter_seconds() - request.started_seconds, 1),
            'answer': answer,
            'prompt': messages[0]['content'],
        }
        lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
        lines.append(json.dumps(record))
        path.write_text('\n'.join(lines[-MAXIMUM_HISTORY_RECORDS:]) + '\n', encoding='utf-8')

    def _read_history(self, path: Path, text: str) -> None:
        """Send the newest records holding the text to the transcript."""
        lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
        records: list[dict[str, Any]] = [json.loads(line) for line in lines]
        matching = [
            record for record in records if text.casefold() in record['question'].casefold()
        ]
        for record in matching[-MAXIMUM_HISTORY_LINES_SHOWN:]:
            question = record['question'][:QUESTION_PREVIEW_CHARACTERS]
            line = f'{record["at"][:19]} {record["outcome"]} {record["seconds"]} s: {question}'
            self._updates.append(partial(self._add_line, text=line, color=NOTE_COLOR))
        if not matching:
            self._updates.append(partial(self._add_line, text='No history', color=NOTE_COLOR))

    def _forget_history(self, path: Path) -> None:
        """Delete this game's history file."""
        path.unlink(missing_ok=True)
        self._updates.append(partial(self._add_line, text='History forgotten', color=NOTE_COLOR))

    def _history_path(self) -> Path:
        """Return this game's history file, named for its package, so its scenes share it."""
        subject = None if self.scene is None else self.scene.debug_subject
        package = 'unknown' if subject is None else type(subject).__module__.partition('.')[0]
        return self.install_root / 'history' / f'{package}.jsonl'

    # Applied on the main thread, from self._updates

    def _received(self, request: AiRequest, *, text: str, is_answer: bool) -> None:
        """Take one piece of a running request's stream."""
        if request is not self.running:
            return
        if is_answer:
            request.answer += text
            request.answer_pieces += 1
            self._show_answer_so_far(request=request)
        else:
            request.reasoning_pieces += 1
            if request.reasoning_pieces % 8 == 1:
                self._set_request_line(
                    request=request, text=self._progress(request=request), color=NOTE_COLOR
                )

    def _show_answer_so_far(self, *, request: AiRequest) -> None:
        """Show the answer as it grows, replacing the line that said it was thinking."""
        self._set_request_line(request=request, text=request.answer, color=ANSWER_COLOR)

    def _finished(self, request: AiRequest) -> None:
        """Finish a request that wasn't cancelled."""
        if request is not self.running:
            return
        self.running = None
        self.last_seconds = clock.raw_counter_seconds() - request.started_seconds
        self.last_pieces = request.answer_pieces + request.reasoning_pieces
        if not request.answer:
            self._set_request_line(
                request=request, text='The model gave no answer', color=ERROR_COLOR
            )
            self.requests_failed += 1
            return
        self._conversation += [
            {'role': 'user', 'content': request.question},
            {'role': 'assistant', 'content': request.answer},
        ]
        self._add_line(
            text=f'#{request.number}: {self.last_pieces} tokens in {self.last_seconds:.1f} s',
            color=NOTE_COLOR,
        )
        if not self.is_open:
            self.unread_answer = True

    def _failed(self, request: AiRequest, reason: str) -> None:
        """Report a request that failed."""
        if request is not self.running:
            return
        self.running = None
        self.requests_failed += 1
        self._set_request_line(
            request=request, text=f'#{request.number} failed: {reason}', color=ERROR_COLOR
        )
        if not self.is_open:
            self.unread_answer = True

    # Text and drawing

    def _progress(self, *, request: AiRequest) -> str:
        """Describe a running request.

        Returns:
            A line of text.

        """
        seconds = clock.raw_counter_seconds() - request.started_seconds
        pieces = request.reasoning_pieces + request.answer_pieces
        return f'#{request.number} thinking: {pieces} tokens, {seconds:.0f} s'

    def _add_line(self, *, text: str, color: tuple[int, int, int] = NOTE_COLOR) -> TranscriptLine:
        """Add an entry to the transcript.

        Returns:
            The entry.

        """
        line = TranscriptLine(text=text, color=color)
        self._transcript.append(line)
        self._panel = None
        return line

    def _set_request_line(
        self, *, request: AiRequest, text: str, color: tuple[int, int, int]
    ) -> None:
        """Change a request's own line, wherever it is now: other commands may have run since."""
        assert request.line is not None  # _ask gives every request its line
        request.line.text = text
        request.line.color = color
        self._panel = None

    def _rendered(self, *, text: str, color: tuple[int, int, int]) -> pygame.Surface:
        """Render a line of text.

        Returns:
            The rendered text.

        """
        assert self._font is not None  # draw() loads it first
        return self._font.render(text, antialias=FontManager.antialias(), color=color)

    def _rendered_panel(self, *, width: int, height: int) -> pygame.Surface:
        """Render the whole console. Kept until something in it changes.

        Returns:
            The panel: the newest lines that fit, above the input line.

        """
        assert self._font is not None  # draw() loads it first
        panel_height = round(height * HEIGHT_FRACTION)
        panel = pygame.Surface((width, panel_height), pygame.SRCALPHA)
        panel.fill(BACKGROUND_COLOR)
        text_width = width - 2 * MARGIN_PIXELS
        lines = [
            (wrapped, line.color)
            for line in self._transcript
            for wrapped in wrapped_lines(text=line.text, font=self._font, width=text_width)
        ]
        input_top = panel_height - LINE_HEIGHT_PIXELS - MARGIN_PIXELS
        fitting = max(1, input_top // LINE_HEIGHT_PIXELS)
        end = max(fitting, len(lines) - self._scroll_lines)
        top = input_top - LINE_HEIGHT_PIXELS * min(fitting, len(lines))
        for line, color in lines[max(0, end - fitting) : end]:
            if line:
                panel.blit(self._rendered(text=line, color=color), (MARGIN_PIXELS, top))
            top += LINE_HEIGHT_PIXELS
        prompt = f'> {self.input_text[: self.cursor]}'
        panel.blit(self._rendered(text=prompt, color=INPUT_COLOR), (MARGIN_PIXELS, input_top))
        cursor_left = MARGIN_PIXELS + self._font.size(prompt)[0]
        pygame.draw.line(
            panel,
            INPUT_COLOR,
            (cursor_left, input_top),
            (cursor_left, input_top + LINE_HEIGHT_PIXELS - 2),
        )
        rest = self.input_text[self.cursor :]
        if rest:
            panel.blit(self._rendered(text=rest, color=INPUT_COLOR), (cursor_left + 1, input_top))
        return panel
