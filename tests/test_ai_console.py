"""The AI console: real events, real drawing, a real local HTTP server, and real history files."""

from __future__ import annotations

import itertools
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from typing import Any, ClassVar

import pygame
import pytest

from glitchygames import ai_console, clock
from glitchygames.ai_console import (
    MAXIMUM_DESCRIBED_SPRITES,
    MAXIMUM_HISTORY_RECORDS,
    MAXIMUM_PASTED_CHARACTERS,
    MAXIMUM_REPEATS_PER_BATCH,
    PAGE_LINES,
    REPEAT_ACCELERATION,
    REPEAT_DELAY_SECONDS,
    REPEAT_FIRST_INTERVAL_SECONDS,
    REPEAT_SHORTEST_INTERVAL_SECONDS,
    AiConsole,
    describe_scene,
    fitting_tail,
    wrapped_lines,
)
from glitchygames.ai_host import AiHostSources
from glitchygames.ai_link import AiLink, LinkState
from glitchygames.clipboard import ClipboardUnavailableError
from glitchygames.debug.overlay import load_debug_font
from glitchygames.input.state import InputSnapshot
from glitchygames.scenes import Scene
from glitchygames.testing.keys import qwerty_scancode
from tests.ai_service_stand_in import install
from tests.test_ai_link import FakeInnerSources

# Every install here can run its control script, on Windows too (tests/ai_service_stand_in.py)
pytestmark = pytest.mark.usefixtures('stand_in_ai_control_scripts')

WAIT_SECONDS = 10.0
GRAVE = pygame.K_BACKQUOTE


def key_event(
    event_type: int, key: int, unicode: str = '', scancode: int | None = None, mod: int = 0
) -> Any:
    """Build a key event as SDL would, its scancode from the keymap unless given.

    Returns:
        The event.

    """
    code = qwerty_scancode(key=key) if scancode is None else scancode
    return pygame.event.Event(event_type, key=key, scancode=code, mod=mod, unicode=unicode)


def press(console: AiConsole, key: int, unicode: str = '', mod: int = 0) -> list[Any]:
    """Press and release a key.

    Returns:
        What the game saw.

    """
    down = key_event(pygame.KEYDOWN, key, unicode, mod=mod)
    up = key_event(pygame.KEYUP, key)
    return console.filter_events(events=[down, up])


def type_text(console: AiConsole, text: str) -> None:
    """Type printable text, one key per character."""
    for character in text:
        press(console, pygame.K_F15, character)


def enter(console: AiConsole, text: str) -> None:
    """Type a line and press Enter."""
    type_text(console, text)
    press(console, pygame.K_RETURN)


def transcript(console: AiConsole) -> str:
    """Return everything on screen, as text, after applying what the worker sent.

    Returns:
        The lines, joined.

    """
    console.filter_events(events=[])
    return '\n'.join(line.text for line in console._transcript)


def wait_for(console: AiConsole, text: str) -> str:
    """Wait for text to reach the transcript from the worker.

    Returns:
        The transcript.

    """
    deadline = clock.raw_counter_seconds() + WAIT_SECONDS
    while clock.raw_counter_seconds() < deadline:
        if text in transcript(console):
            return transcript(console)
        clock.raw_sleep(0.01)
    pytest.fail(f'{text!r} never appeared in: {transcript(console)}')


def wait_until_the_request_reached(fake: ChatService) -> None:
    """Wait for the worker's request to reach the fake service, before abandoning it.

    A request abandoned sooner can find the service gone once its test ends: its readiness
    check then fails, the installed control script "starts" the service, and the worker polls
    for readiness through ``clock.raw_sleep`` for two minutes, landing in later tests' patches
    of it (BUGS.md #262).
    """
    deadline = clock.raw_counter_seconds() + WAIT_SECONDS
    while not fake.bodies and clock.raw_counter_seconds() < deadline:
        clock.raw_sleep(0.01)
    assert fake.bodies, 'the request never reached the service'


def stream_line(**delta: str) -> bytes:
    """Build one line of a llama.cpp event stream.

    Returns:
        Its bytes.

    """
    return f'data: {json.dumps({"choices": [{"delta": delta}]})}\n\n'.encode()


class ChatService:
    """A real HTTP server speaking the service's chat stream."""

    def __init__(self) -> None:
        """Answer with reasoning, then two pieces of text."""
        self.lines = [
            stream_line(reasoning_content='hmm'),
            stream_line(content='Two '),
            stream_line(content='balls.'),
            b'data: [DONE]\n\n',
        ]
        self.status = 200
        self.bodies: list[dict[str, Any]] = []
        self.hold = Event()
        self.hold.set()


@pytest.fixture
def chat_service():
    """Run the server on a real local port.

    Yields:
        The fake and its URL.

    """
    fake = ChatService()

    class Handler(BaseHTTPRequestHandler):
        fake_service: ClassVar[ChatService] = fake

        def do_GET(self) -> None:
            self.send_response(200)
            self.end_headers()

        def do_POST(self) -> None:
            length = int(self.headers['Content-Length'])
            self.fake_service.bodies.append(json.loads(self.rfile.read(length)))
            self.send_response(self.fake_service.status)
            self.end_headers()
            self.fake_service.hold.wait(WAIT_SECONDS)
            for line in self.fake_service.lines:
                self.wfile.write(line)
                self.wfile.flush()

        def log_message(self, format: str, *args: object) -> None:  # ruff: ignore[builtin-argument-shadowing]
            """Say nothing."""

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield fake, f'http://127.0.0.1:{server.server_address[1]}'
    fake.hold.set()
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def console(tmp_path):
    """Build a console over a real install, connected, and open.

    Returns:
        The console.

    """
    install(root=tmp_path)
    link = AiLink(install_root=tmp_path)
    link.state = LinkState.CONNECTED
    built = AiConsole(link=link, install_root=tmp_path)
    press(built, GRAVE)
    return built


class Watched(pygame.sprite.DirtySprite):
    """A sprite with what the console reads."""

    def __init__(self, name: str) -> None:
        """Place it."""
        super().__init__()
        self.name = name
        self.rect = pygame.Rect(1, 2, 3, 4)
        self.world_x = 1.2345


@pytest.fixture
def scene():
    """Build a real scene with two sprites.

    Returns:
        The scene.

    """
    built = Scene(options={})
    built.all_sprites.add(Watched('Ball'), Watched('Paddle'))
    return built


def test_the_grave_key_opens_and_closes_it(tmp_path):
    """` opens and ` closes, and the game sees neither."""
    built = AiConsole(link=AiLink(install_root=tmp_path), install_root=tmp_path)

    assert press(built, GRAVE) == []
    assert built.is_open is True
    assert press(built, GRAVE) == []
    assert built.is_open is False


def test_the_character_opens_it_wherever_a_layout_puts_it(tmp_path):
    """The ` character from another position counts."""
    built = AiConsole(link=AiLink(install_root=tmp_path), install_root=tmp_path)

    down = key_event(pygame.KEYDOWN, GRAVE, '`', scancode=pygame.KSCAN_A)
    up = key_event(pygame.KEYUP, GRAVE, scancode=pygame.KSCAN_A)

    assert built.filter_events(events=[down, up]) == []
    assert built.is_open is True


def test_the_us_position_opens_it_when_a_layout_gives_another_character(tmp_path):
    """The key left of 1 counts, whatever it types."""
    built = AiConsole(link=AiLink(install_root=tmp_path), install_root=tmp_path)

    down = key_event(pygame.KEYDOWN, pygame.K_F15, '²', scancode=pygame.KSCAN_GRAVE)

    assert built.filter_events(events=[down]) == []
    assert built.is_open is True


def test_a_key_press_without_a_scancode_is_the_games(tmp_path):
    """A game's own posted press may have none, and passes through."""
    built = AiConsole(link=AiLink(install_root=tmp_path), install_root=tmp_path)
    posted = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode='a')
    released = pygame.event.Event(pygame.KEYUP, key=pygame.K_a)

    assert built.filter_events(events=[posted, released]) == [posted, released]

    press(built, GRAVE)
    assert built.filter_events(events=[posted]) == []
    assert built.input_text == 'a'


def test_a_grave_without_a_scancode_still_toggles(tmp_path):
    """The character alone is enough, with nothing to hide afterwards."""
    built = AiConsole(link=AiLink(install_root=tmp_path), install_root=tmp_path)

    built.filter_events(events=[pygame.event.Event(pygame.KEYDOWN, key=GRAVE)])

    assert built.is_open is True
    assert built.hidden_scancodes == set()


def test_closed_the_game_gets_everything_unchanged(tmp_path):
    """No AI use, no difference: the same events reach the game."""
    built = AiConsole(link=AiLink(install_root=tmp_path), install_root=tmp_path)
    events = [
        key_event(pygame.KEYDOWN, pygame.K_w, 'w'),
        pygame.event.Event(pygame.TEXTINPUT, text='w'),
        key_event(pygame.KEYUP, pygame.K_w),
        pygame.event.Event(pygame.MOUSEMOTION, pos=(1, 1), rel=(0, 0), buttons=(0, 0, 0)),
    ]

    assert built.filter_events(events=list(events)) == events


def test_open_it_takes_every_key_but_not_the_mouse(console):
    """Typing never moves the player, and text input never reaches a game's text field."""
    motion = pygame.event.Event(pygame.MOUSEMOTION, pos=(1, 1), rel=(0, 0), buttons=(0, 0, 0))
    events = [
        key_event(pygame.KEYDOWN, pygame.K_w, 'w'),
        pygame.event.Event(pygame.TEXTINPUT, text='w'),
        key_event(pygame.KEYUP, pygame.K_w),
        motion,
    ]

    assert console.filter_events(events=events) == [motion]
    assert console.input_text == 'w'


def test_the_debug_overlays_keys_still_work_while_open(console):
    """F3 and F4 reach the overlay, to show the AI panel beside the console."""
    down = key_event(pygame.KEYDOWN, pygame.K_F3)
    up = key_event(pygame.KEYUP, pygame.K_F3)

    assert console.filter_events(events=[down, up]) == [down, up]


def test_opening_releases_what_the_game_saw_pressed(tmp_path):
    """A held key doesn't stay stuck in the game while the console is open."""
    built = AiConsole(link=AiLink(install_root=tmp_path), install_root=tmp_path)
    assert len(built.filter_events(events=[key_event(pygame.KEYDOWN, pygame.K_w, 'w')])) == 1

    seen = built.filter_events(events=[key_event(pygame.KEYDOWN, GRAVE, '`')])

    assert [(event.type, event.key) for event in seen] == [(pygame.KEYUP, pygame.K_w)]
    # ...and its real release later isn't a second one
    assert built.filter_events(events=[key_event(pygame.KEYUP, pygame.K_w)]) == []


def test_a_key_released_before_opening_gets_no_second_release(tmp_path):
    """Only what's still held is released."""
    built = AiConsole(link=AiLink(install_root=tmp_path), install_root=tmp_path)
    press(built, pygame.K_w, 'w')

    assert built.filter_events(events=[key_event(pygame.KEYDOWN, GRAVE)]) == []


def test_a_key_held_as_it_closes_stays_hidden_until_released(console):
    """Closing with Esc held must not quit the game: its release is the console's too."""
    console.filter_events(events=[key_event(pygame.KEYDOWN, pygame.K_ESCAPE)])
    assert console.is_open is False

    text = pygame.event.Event(pygame.TEXTINPUT, text='x')
    assert console.filter_events(events=[text]) == []
    assert console.filter_events(events=[key_event(pygame.KEYUP, pygame.K_ESCAPE)]) == []
    assert console.filter_events(events=[text]) == [text]


def snapshot(*scancodes: int) -> InputSnapshot:
    """Build a polled snapshot holding these keys, with a modifier down.

    Returns:
        The snapshot.

    """
    return InputSnapshot(
        pressed_scancodes=frozenset(scancodes),
        modifiers=pygame.KMOD_LSHIFT,
        mouse_position=(0, 0),
        mouse_buttons=(False, False, False),
        mouse_focused=True,
    )


def test_a_game_that_polls_sees_no_typing(tmp_path):
    """The snapshot is masked too: Drawing Fire reads its controls from it."""
    built = AiConsole(link=AiLink(install_root=tmp_path), install_root=tmp_path)
    closed = snapshot(pygame.KSCAN_W)
    assert built.masked_snapshot(snapshot=closed) is closed

    built.filter_events(events=[key_event(pygame.KEYDOWN, pygame.K_w, 'w')])
    built.filter_events(events=[key_event(pygame.KEYDOWN, GRAVE)])
    masked = built.masked_snapshot(snapshot=snapshot(pygame.KSCAN_W, pygame.KSCAN_D))

    assert masked.pressed_scancodes == {pygame.KSCAN_D} - built.hidden_scancodes
    assert pygame.KSCAN_W not in masked.pressed_scancodes
    assert masked.modifiers == 0


def test_modifiers_return_while_a_closing_key_is_still_held(console):
    """Only the keys are hidden once it's closed."""
    console.filter_events(events=[key_event(pygame.KEYDOWN, pygame.K_ESCAPE)])

    masked = console.masked_snapshot(snapshot=snapshot(pygame.KSCAN_ESCAPE))

    assert masked.pressed_scancodes == frozenset()
    assert masked.modifiers == pygame.KMOD_LSHIFT


def test_editing_the_input_line(console):
    """The keys of an input line."""
    type_text(console, 'abcd')
    press(console, pygame.K_LEFT)
    press(console, pygame.K_BACKSPACE)
    assert (console.input_text, console.cursor) == ('abd', 2)
    press(console, pygame.K_DELETE)
    assert console.input_text == 'ab'
    press(console, pygame.K_HOME)
    press(console, pygame.K_BACKSPACE)
    press(console, pygame.K_LEFT)
    assert console.cursor == 0
    type_text(console, 'x')
    press(console, pygame.K_END)
    press(console, pygame.K_RIGHT)
    assert (console.input_text, console.cursor) == ('xab', 3)


def test_keys_that_type_nothing_change_nothing(console):
    """A shift or arrow-less control key has no printable text."""
    press(console, pygame.K_LSHIFT, '')
    press(console, pygame.K_F15, '\x01')

    assert not console.input_text


def test_control_keys_move_to_the_ends_of_the_line(console):
    """Ctrl-A and Ctrl-E, by the key's name, typing nothing."""
    type_text(console, 'abc')

    press(console, pygame.K_a, '\x01', mod=pygame.KMOD_LCTRL)
    assert (console.input_text, console.cursor) == ('abc', 0)
    press(console, pygame.K_e, '\x05', mod=pygame.KMOD_RCTRL)
    assert (console.input_text, console.cursor) == ('abc', 3)


def test_cutting_to_the_end_and_pasting_back(console, in_process_clipboard):
    """Ctrl-K cuts from the cursor, Ctrl-Y inserts it at the cursor, as often as asked."""
    in_process_clipboard.copy('the clipboard')
    type_text(console, 'hello world')
    for _ in range(5):
        press(console, pygame.K_LEFT)

    press(console, pygame.K_k, '\x0b', mod=pygame.KMOD_LCTRL)
    assert (console.input_text, console.cursor) == ('hello ', 6)
    assert console.cut_text == 'world'

    press(console, pygame.K_y, '\x19', mod=pygame.KMOD_LCTRL)
    press(console, pygame.K_HOME)
    press(console, pygame.K_y, '\x19', mod=pygame.KMOD_LCTRL)
    assert (console.input_text, console.cursor) == ('worldhello world', 5)
    assert in_process_clipboard.paste() == 'the clipboard'


def test_cutting_nothing_keeps_what_was_cut(console):
    """Ctrl-K at the end of the line keeps the buffer, and pasting nothing does nothing."""
    press(console, pygame.K_y, '\x19', mod=pygame.KMOD_LCTRL)
    assert not console.input_text

    type_text(console, 'keep')
    press(console, pygame.K_HOME)
    press(console, pygame.K_k, '\x0b', mod=pygame.KMOD_LCTRL)
    press(console, pygame.K_k, '\x0b', mod=pygame.KMOD_LCTRL)

    assert not console.input_text
    assert console.cut_text == 'keep'


def test_altgr_still_types(console):
    """Windows reports AltGr as Ctrl+Alt, and AltGr+E is a character on many layouts."""
    press(console, pygame.K_e, '€', mod=pygame.KMOD_LCTRL | pygame.KMOD_RALT)

    assert console.input_text == '€'


def test_modifiers_with_no_action_of_their_own(console):
    """Shift still types capitals, and a modified editing key still edits."""
    press(console, pygame.K_a, 'A', mod=pygame.KMOD_LSHIFT)
    press(console, pygame.K_b, '\x02', mod=pygame.KMOD_LCTRL)
    assert console.input_text == 'A'

    press(console, pygame.K_BACKSPACE, mod=pygame.KMOD_LCTRL)
    assert not console.input_text


@pytest.fixture
def held_backspace(console, mocker):
    """Hold Backspace over a long line, on a clock the test moves.

    Returns:
        A function moving the clock on by that many seconds, then polling the console.

    """
    now = [100.0]
    mocker.patch('glitchygames.clock.raw_counter_seconds', side_effect=lambda: now[0])
    type_text(console, 'x' * 200)
    console.filter_events(events=[key_event(pygame.KEYDOWN, pygame.K_BACKSPACE)])

    def advance(seconds: float) -> None:
        now[0] += seconds
        console.filter_events(events=[])

    return advance


def test_a_held_backspace_repeats_faster_and_faster(console, held_backspace):
    """One at once, nothing until the delay, then each gap shorter down to the shortest."""
    assert len(console.input_text) == 199
    held_backspace(REPEAT_DELAY_SECONDS - 0.01)
    assert len(console.input_text) == 199

    gaps = []
    since_last = 0.0
    held_backspace(0.011)
    assert len(console.input_text) == 198
    previous_length = 198
    while len(console.input_text) > 50:
        held_backspace(0.001)
        since_last += 0.001
        if len(console.input_text) < previous_length:
            gaps.append(since_last)
            since_last = 0.0
            previous_length = len(console.input_text)

    assert all(later <= earlier + 0.002 for earlier, later in itertools.pairwise(gaps))
    assert gaps[0] == pytest.approx(REPEAT_FIRST_INTERVAL_SECONDS * REPEAT_ACCELERATION, abs=0.002)
    assert gaps[-1] == pytest.approx(REPEAT_SHORTEST_INTERVAL_SECONDS, abs=0.002)


def test_releasing_backspace_stops_it(console, held_backspace):
    """Only its own release: another key's leaves it repeating."""
    held_backspace(REPEAT_DELAY_SECONDS)
    length = len(console.input_text)

    console.filter_events(events=[key_event(pygame.KEYUP, pygame.K_F15)])
    held_backspace(REPEAT_FIRST_INTERVAL_SECONDS)
    assert len(console.input_text) < length

    length = len(console.input_text)
    console.filter_events(events=[key_event(pygame.KEYUP, pygame.K_BACKSPACE)])
    held_backspace(10.0)
    assert len(console.input_text) == length


def test_another_key_takes_over_from_a_held_backspace(console, held_backspace):
    """Typing while it's held stops it, and types."""
    press(console, pygame.K_F15, 'y')
    length = len(console.input_text)

    held_backspace(10.0)

    assert len(console.input_text) == length
    assert console.input_text.endswith('y')


@pytest.mark.parametrize('closing_key', [pygame.K_ESCAPE, GRAVE])
def test_closing_stops_a_held_backspace(console, held_backspace, closing_key):
    """Whichever key closes it."""
    length = len(console.input_text)
    console.filter_events(events=[key_event(pygame.KEYDOWN, closing_key)])

    held_backspace(10.0)

    assert len(console.input_text) == length


def test_a_stalled_frame_cant_eat_the_line(console, held_backspace):
    """A few repeats at most, then it carries on from now rather than catching up."""
    length = len(console.input_text)

    held_backspace(60.0)
    assert len(console.input_text) == length - MAXIMUM_REPEATS_PER_BATCH

    held_backspace(0.0)
    assert len(console.input_text) == length - MAXIMUM_REPEATS_PER_BATCH


def test_sdls_own_repeat_is_ignored(console):
    """A game may turn key repeat on: a key pressed again with no release is that, not typing."""
    letter = key_event(pygame.KEYDOWN, pygame.K_a, 'a')
    console.filter_events(events=[letter, letter, letter])
    assert console.input_text == 'a'

    console.filter_events(events=[key_event(pygame.KEYUP, pygame.K_a), letter])
    assert console.input_text == 'aa'

    backspace = key_event(pygame.KEYDOWN, pygame.K_BACKSPACE)
    console.filter_events(events=[backspace, backspace])
    assert console.input_text == 'a'


def test_holding_the_toggle_key_with_sdls_repeat_on_toggles_once(tmp_path):
    """It would flicker open and closed at the repeat rate."""
    built = AiConsole(link=AiLink(install_root=tmp_path), install_root=tmp_path)
    grave = key_event(pygame.KEYDOWN, GRAVE, '`')

    built.filter_events(events=[grave, grave, grave])

    assert built.is_open


def test_a_key_held_as_it_opens_types_nothing_when_sdl_repeats_it(tmp_path):
    """The game saw the press, so its repeats are not typing."""
    built = AiConsole(link=AiLink(install_root=tmp_path), install_root=tmp_path)
    letter = key_event(pygame.KEYDOWN, pygame.K_a, 'a')
    built.filter_events(events=[letter, key_event(pygame.KEYDOWN, GRAVE, '`')])

    built.filter_events(events=[letter])

    assert not built.input_text


def test_help_lists_the_keys(console):
    """They can't be found any other way."""
    enter(console, '/help')

    assert 'Ctrl-K' in transcript(console)
    assert 'Shift+Up/Down' in transcript(console)


def test_recalling_earlier_input(console):
    """Up and Down walk what was typed, and the newest is repeated only once."""
    press(console, pygame.K_UP)
    assert not console.input_text
    enter(console, '/help')
    enter(console, '/help')
    enter(console, '/clear')

    press(console, pygame.K_UP)
    assert console.input_text == '/clear'
    press(console, pygame.K_UP)
    assert console.input_text == '/help'
    press(console, pygame.K_UP)
    assert console.input_text == '/help'
    press(console, pygame.K_DOWN)
    press(console, pygame.K_DOWN)
    assert not console.input_text


def test_tab_completes_a_command(console):
    """One match completes, several are listed, and anything else is left alone."""
    type_text(console, '/in')
    press(console, pygame.K_TAB)
    assert console.input_text == '/inspect '
    press(console, pygame.K_TAB)
    assert console.input_text == '/inspect '

    console._set_input(text='/c')
    press(console, pygame.K_TAB)
    assert '/cancel /copy /clear' in transcript(console)

    console._set_input(text='/zzz')
    press(console, pygame.K_TAB)
    assert console.input_text == '/zzz'


def test_an_empty_line_does_nothing(console):
    """Enter on nothing adds nothing."""
    before = transcript(console)

    press(console, pygame.K_RETURN)

    assert transcript(console) == before


def test_help_comes_from_the_commands(console):
    """Every command is listed, and one can be asked about."""
    enter(console, '/help')
    listed = transcript(console)
    for name in console.commands:
        assert f'/{name}' in listed

    enter(console, '/help /ask')
    assert transcript(console).endswith(
        '/ask QUESTION: ask the AI about what is on screen (or just type the question)'
    )
    enter(console, '/help nothing')
    assert transcript(console).endswith('No command nothing: try /help')


def test_an_unknown_command_is_named(console):
    """A typo says so."""
    enter(console, '/nope')

    assert 'No command /nope' in transcript(console)


def test_clear_empties_the_screen(console):
    """Everything goes, and so does the conversation."""
    console._conversation.append({'role': 'user', 'content': 'x'})

    enter(console, '/clear')

    assert not transcript(console)
    assert console._conversation == []


def test_inspect_before_the_first_frame(console):
    """Nothing to read yet."""
    enter(console, '/inspect')

    assert 'No scene yet' in transcript(console)


def test_inspect_lists_the_scene_and_filters_by_name(console, scene):
    """It reads the real scene's real sprites."""
    console.scene = scene

    enter(console, '/inspect')
    assert '"scene": ' in transcript(console)
    assert '"name": "Ball"' in transcript(console)
    assert '"name": "Paddle"' in transcript(console)

    enter(console, '/clear')
    enter(console, '/inspect ball')
    assert '"rect": [1, 2, 3, 4]' in transcript(console)
    assert '"world_x": 1.23' in transcript(console)
    assert 'Paddle' not in transcript(console)

    enter(console, '/inspect nothing')
    assert 'No sprite named like nothing' in transcript(console)


def test_describing_a_scene_changes_nothing_and_is_bounded(scene):
    """Read-only, and a huge scene stays a small prompt."""
    scene.all_sprites.add(*[Watched(f's{number}') for number in range(MAXIMUM_DESCRIBED_SPRITES)])
    rects = [sprite.rect.copy() for sprite in scene.all_sprites]

    description = describe_scene(scene=scene)

    assert description['sprite_count'] == MAXIMUM_DESCRIBED_SPRITES + 2
    assert len(description['sprites']) == MAXIMUM_DESCRIBED_SPRITES
    assert description['paused'] is False
    assert description['game'] == {}
    assert [sprite.rect for sprite in scene.all_sprites] == rects


def test_a_sprite_with_no_name_or_rect_is_still_described(scene):
    """Whatever's in the group can be read."""
    scene.all_sprites.add(pygame.sprite.DirtySprite())

    names = [sprite['name'] for sprite in describe_scene(scene=scene)['sprites']]

    assert 'DirtySprite' in names


def test_a_paused_game_is_described_not_its_pause_screen(scene, mocker):
    """As the debug overlay inspects it."""
    pause_screen = Scene(options={})
    mocker.patch.object(
        type(pause_screen), 'debug_subject', new_callable=mocker.PropertyMock, return_value=scene
    )

    assert describe_scene(scene=pause_screen)['paused'] is True


def test_a_question_streams_the_answer_and_says_what_it_cost(console, chat_service, scene):
    """A typed question goes to the service with the game's state, and comes back in pieces."""
    fake, url = chat_service
    console.service_url = url
    console.scene = scene

    enter(console, 'how many balls?')
    text = wait_for(console, 'tokens in')

    assert 'Two balls.' in text
    assert console.running is None
    assert console.last_pieces == 3
    body = fake.bodies[0]
    assert body['stream'] is True
    assert body['reasoning_effort'] == 'low'
    assert body['messages'][-1] == {'role': 'user', 'content': 'how many balls?'}
    assert '"name": "Ball"' in body['messages'][0]['content']


def test_a_follow_up_carries_the_conversation(console, chat_service):
    """So 'and now?' makes sense."""
    fake, url = chat_service
    console.service_url = url

    enter(console, '/ask first')
    wait_for(console, 'tokens in')
    enter(console, '/ask second')
    deadline = clock.raw_counter_seconds() + WAIT_SECONDS
    while console.running is not None and clock.raw_counter_seconds() < deadline:
        transcript(console)
        clock.raw_sleep(0.01)

    roles = [message['role'] for message in fake.bodies[1]['messages']]
    assert roles == ['system', 'user', 'assistant', 'user']


def test_only_one_question_at_a_time(console, chat_service):
    """A second waits to be asked again, naming how to stop the first."""
    fake, url = chat_service
    console.service_url = url
    fake.hold.clear()

    enter(console, '/ask first')
    enter(console, '/ask second')

    assert '#1 is still running: /cancel to stop it' in transcript(console)
    assert 'Running: #1' in '\n'.join(console.status_lines())
    fake.hold.set()
    wait_for(console, 'tokens in')


def test_a_command_run_while_thinking_keeps_its_lines(console, chat_service):
    """Progress and the answer go on the request's own line, never over what came after."""
    fake, url = chat_service
    console.service_url = url
    fake.hold.clear()
    fake.lines = [
        stream_line(reasoning_content='one'),
        stream_line(reasoning_content='two'),
        stream_line(content='The answer.'),
        b'data: [DONE]\n\n',
    ]
    enter(console, '/ask something')
    enter(console, '/ai')
    status_line = console._transcript[-1].text

    fake.hold.set()
    wait_for(console, 'tokens in')

    lines = [line.text for line in console._transcript]
    assert status_line in lines
    assert lines.index('The answer.') < lines.index(status_line)


def test_ask_needs_a_question(console):
    """Bare /ask says how."""
    enter(console, '/ask')

    assert transcript(console).endswith('/ask QUESTION')


@pytest.mark.parametrize(
    'state', [LinkState.NOT_ENOUGH_MEMORY, LinkState.UNAVAILABLE, LinkState.REFUSED]
)
def test_no_ai_this_run_says_why_without_trying(console, state):
    """Not enough memory isn't retried just because someone asked."""
    console.link.state = state

    enter(console, 'anything')

    assert f'No AI this run: {state.value}' in transcript(console)
    assert console.running is None


def test_cancelling_stops_listening_at_once(console, chat_service):
    """The console is free straight away, and a late answer doesn't appear."""
    fake, url = chat_service
    console.service_url = url
    fake.hold.clear()
    enter(console, '/cancel')
    assert 'Nothing is running' in transcript(console)

    enter(console, '/ask something')
    enter(console, '/cancel')
    assert '#1 cancelled' in transcript(console)
    assert console.running is None
    assert console.requests_cancelled == 1

    fake.hold.set()
    deadline = clock.raw_counter_seconds() + WAIT_SECONDS
    history = console.install_root / 'history' / 'unknown.jsonl'
    while not history.exists() and clock.raw_counter_seconds() < deadline:
        clock.raw_sleep(0.01)
    assert 'Two' not in transcript(console)
    assert json.loads(history.read_text(encoding='utf-8'))['outcome'] == 'cancelled'


def test_updates_for_a_cancelled_request_are_ignored(console):
    """A worker that had already queued them can't write over what's on screen."""
    from glitchygames.ai_console import AiRequest

    stale = AiRequest(number=9, question='q', started_seconds=0.0)
    before = transcript(console)

    console._received(stale, text='late', is_answer=True)
    console._finished(stale)
    console._failed(stale, 'late')

    assert transcript(console) == before


def test_a_refusal_is_reported_and_ends_the_request(console, chat_service):
    """The service's answer reaches the screen."""
    fake, url = chat_service
    console.service_url = url
    fake.status = 503
    fake.lines = [b'busy']

    enter(console, 'anything')
    text = wait_for(console, 'failed')

    assert '503' in text
    assert console.running is None
    assert console.requests_failed == 1


def test_a_stream_that_is_not_json_ends_the_request(console, chat_service):
    """Nothing can leave a request running forever."""
    fake, url = chat_service
    console.service_url = url
    fake.lines = [b'data: {not json\n\n']

    enter(console, 'anything')
    wait_for(console, 'failed')

    assert console.running is None


def test_a_missing_service_is_reported(console):
    """An install that's gone by the time of asking."""
    (console.install_root / 'bin' / 'ai-service.sh').unlink()

    enter(console, 'anything')

    assert 'not installed' in wait_for(console, 'failed')


def test_only_reasoning_is_reported_as_no_answer(console, chat_service):
    """A model that reasons and never answers says so."""
    fake, url = chat_service
    console.service_url = url
    fake.lines = [stream_line(reasoning_content='hmm'), b'data: [DONE]\n\n']

    enter(console, 'anything')

    wait_for(console, 'The model gave no answer')
    assert console.requests_failed == 1


def test_an_answer_arriving_while_closed_leaves_word(console, chat_service):
    """It's drawn only then, and opening reads it."""
    fake, url = chat_service
    console.service_url = url
    fake.hold.clear()
    enter(console, 'anything')
    press(console, GRAVE)
    assert console.needs_drawing is False

    fake.hold.set()
    wait_for(console, 'tokens in')
    assert console.needs_drawing is True
    surface = pygame.Surface((320, 240))
    surface.fill((0, 0, 0))
    console.draw(surface=surface)
    console.draw(surface=surface)
    assert surface.get_bounding_rect().width > 0

    press(console, GRAVE)
    assert console.unread_answer is False


def test_a_failure_arriving_while_closed_leaves_word(console, chat_service):
    """Not only good news."""
    fake, url = chat_service
    console.service_url = url
    fake.status = 503
    fake.hold.clear()
    enter(console, 'anything')
    press(console, GRAVE)

    fake.hold.set()
    wait_for(console, 'failed')

    assert console.unread_answer is True


def test_history_is_kept_searched_bounded_and_forgotten(console, chat_service, mocker):
    """One file per game, with what was asked and answered."""
    _fake, url = chat_service
    console.service_url = url
    enter(console, '/history')
    wait_for(console, 'No history')

    enter(console, '/ask where is it')
    wait_for(console, 'tokens in')
    path = console.install_root / 'history' / 'unknown.jsonl'
    deadline = clock.raw_counter_seconds() + WAIT_SECONDS
    while not path.exists() and clock.raw_counter_seconds() < deadline:
        clock.raw_sleep(0.01)
    record = json.loads(path.read_text(encoding='utf-8'))
    assert (record['question'], record['answer'], record['outcome']) == (
        'where is it',
        'Two balls.',
        'answered',
    )

    enter(console, '/history where')
    wait_for(console, 'answered')
    enter(console, '/clear')
    enter(console, '/history nothing like it')
    wait_for(console, 'No history')

    mocker.patch.object(ai_console, 'MAXIMUM_HISTORY_RECORDS', 2)
    for number in range(3):
        console._write_history(
            request=ai_console.AiRequest(number=number, question='q', started_seconds=0.0),
            outcome='answered',
            answer='a',
            messages=[{'role': 'system', 'content': 's'}],
        )
    assert len(path.read_text(encoding='utf-8').splitlines()) == 2
    assert MAXIMUM_HISTORY_RECORDS > 2

    enter(console, '/history clear')
    wait_for(console, 'History forgotten')
    assert not path.exists()


def test_history_is_named_for_the_games_package(console, scene):
    """All of a game's scenes share one file."""
    console.scene = scene

    assert console._history_path().name == 'glitchygames.jsonl'


def test_a_worker_failure_reaches_the_screen(console):
    """A disk error is text, not a dead thread."""

    def fail() -> None:
        message = 'no disk'
        raise OSError(message)

    console._on_worker(work=fail)

    wait_for(console, 'no disk')


def test_ai_status_reports_the_link_and_requests(console):
    """What /ai and the debug panel show."""
    console.link.models = [{'id': 'bonsai-2-27b', 'state': 'ready'}]
    console.link.round_trips = 3
    console.last_seconds = 2.5
    console.last_pieces = 10

    enter(console, '/ai')

    text = transcript(console)
    assert 'Link: connected, 3 round trips' in text
    assert 'Model bonsai-2-27b: ready' in text
    assert 'Requests: 0 asked, 0 failed, 0 cancelled' in text
    assert 'Last: 10 tokens in 2.5 s' in text


def test_stop_abandons_what_is_running(console, chat_service):
    """As the run ends, and harmless with nothing running."""
    fake, url = chat_service
    console.service_url = url
    console.stop()
    fake.hold.clear()
    enter(console, 'anything')
    running = console.running
    wait_until_the_request_reached(fake)

    console.stop()

    assert running.cancelled.is_set()


def test_drawing_paints_the_console_and_is_cached(console):
    """It covers the lower part of the frame, and stays until something changes."""
    surface = pygame.Surface((320, 240))
    surface.fill((200, 0, 0))

    console.draw(surface=surface)

    assert surface.get_at((5, 10))[:3] == (200, 0, 0)
    assert surface.get_at((315, 235))[:3] != (200, 0, 0)
    panel = console._panel
    console.draw(surface=surface)
    assert console._panel is panel

    press(console, pygame.K_F15, 'a')
    assert console._panel is None


def test_a_new_window_size_redraws_it(console):
    """The panel is as wide as the frame."""
    console.draw(surface=pygame.Surface((320, 240)))

    console.draw(surface=pygame.Surface((640, 480)))

    assert console._panel.get_width() == 640


def test_scrolling_shows_older_lines(console):
    """Page Up goes back, within what's there, and Enter comes back to the newest."""
    surface = pygame.Surface((320, 240))
    for number in range(40):
        console._add_line(text=f'line {number}')
    console.draw(surface=surface)
    newest = pygame.image.tobytes(console._panel, 'RGBA')

    press(console, pygame.K_PAGEUP)
    console.draw(surface=surface)
    assert pygame.image.tobytes(console._panel, 'RGBA') != newest
    for _ in range(10):
        press(console, pygame.K_PAGEUP)
    console.draw(surface=surface)

    for _ in range(10):
        press(console, pygame.K_PAGEDOWN)
    console.draw(surface=surface)
    assert pygame.image.tobytes(console._panel, 'RGBA') == newest


def test_shift_and_arrows_scroll_one_line_at_a_time(console):
    """A page is that many lines, plain arrows still recall, and Shift+Down comes back."""
    surface = pygame.Surface((320, 240))
    for number in range(40):
        console._add_line(text=f'line {number}')
    console.draw(surface=surface)
    newest = pygame.image.tobytes(console._panel, 'RGBA')

    press(console, pygame.K_UP, mod=pygame.KMOD_LSHIFT)
    console.draw(surface=surface)
    one_line = pygame.image.tobytes(console._panel, 'RGBA')
    assert one_line != newest
    assert not console.input_text

    for _ in range(PAGE_LINES - 1):
        press(console, pygame.K_UP, mod=pygame.KMOD_RSHIFT)
    console.draw(surface=surface)
    by_lines = pygame.image.tobytes(console._panel, 'RGBA')
    for _ in range(PAGE_LINES):
        press(console, pygame.K_DOWN, mod=pygame.KMOD_LSHIFT)
    console.draw(surface=surface)
    assert pygame.image.tobytes(console._panel, 'RGBA') == newest

    press(console, pygame.K_PAGEUP)
    console.draw(surface=surface)
    assert pygame.image.tobytes(console._panel, 'RGBA') == by_lines


def test_scrolling_reaches_the_top_of_one_long_answer(console):
    """The limit counts lines as wrapped: one long answer is one entry but many lines."""
    surface = pygame.Surface((320, 240))
    enter(console, '/clear')
    console._add_line(text='\n'.join(f'line {number}' for number in range(40)))
    console.draw(surface=surface)
    newest = pygame.image.tobytes(console._panel, 'RGBA')

    for _ in range(10):
        press(console, pygame.K_PAGEUP)
    console.draw(surface=surface)
    # Panel 144 high, its input line from 122: seven lines fit
    assert console._scroll_lines == 33

    # Clamped, so no dead presses on the way back
    for _ in range(33):
        press(console, pygame.K_DOWN, mod=pygame.KMOD_LSHIFT)
    console.draw(surface=surface)
    assert pygame.image.tobytes(console._panel, 'RGBA') == newest


def test_the_input_line_draws_text_either_side_of_the_cursor(console):
    """The cursor's in the middle of what's typed."""
    surface = pygame.Surface((320, 240))
    type_text(console, 'abc')
    console.draw(surface=surface)
    at_end = pygame.image.tobytes(console._panel, 'RGBA')

    press(console, pygame.K_LEFT)
    console.draw(surface=surface)

    assert pygame.image.tobytes(console._panel, 'RGBA') != at_end


def test_a_blank_line_in_an_answer_takes_up_room(console):
    """Paragraphs stay paragraphs."""
    surface = pygame.Surface((320, 240))
    console._add_line(text='one\n\ntwo')

    console.draw(surface=surface)

    assert console._panel is not None


def test_wrapping_fits_the_width():
    """On spaces, and through a word too long for a line."""
    font = load_debug_font()
    width = 100

    lines = wrapped_lines(text=f'short words here\n\n{"x" * 60} end', font=font, width=width)

    assert all(font.size(line)[0] <= width for line in lines)
    assert '' in lines
    assert lines[-1].endswith('end')
    assert ''.join(lines).count('x') == 60


def test_a_width_too_small_for_one_character_still_ends():
    """A tiny window mustn't hang the frame."""
    assert wrapped_lines(text='abc', font=load_debug_font(), width=1) == ['a', 'b', 'c']


def control(console: AiConsole, key: int) -> None:
    """Press a key with Ctrl held."""
    press(console, key, mod=pygame.KMOD_LCTRL)


@pytest.mark.parametrize(
    'key',
    [
        pygame.K_DELETE,
        pygame.K_LEFT,
        pygame.K_RIGHT,
        pygame.K_UP,
        pygame.K_DOWN,
        pygame.K_PAGEUP,
        pygame.K_PAGEDOWN,
    ],
)
def test_the_other_moving_keys_repeat_too(console, mocker, key):
    """Held, each does again what it did, and a key that only types doesn't."""
    now = [100.0]
    mocker.patch('glitchygames.clock.raw_counter_seconds', side_effect=lambda: now[0])
    action = mocker.Mock()
    console._editing_keys[key] = action

    console.filter_events(events=[key_event(pygame.KEYDOWN, key)])
    assert action.call_count == 1
    now[0] += REPEAT_DELAY_SECONDS
    console.filter_events(events=[])

    assert action.call_count == 2


def test_a_held_arrow_really_moves_the_cursor(console, mocker):
    """The whole path, not only the table."""
    now = [100.0]
    mocker.patch('glitchygames.clock.raw_counter_seconds', side_effect=lambda: now[0])
    type_text(console, 'abcd')

    console.filter_events(events=[key_event(pygame.KEYDOWN, pygame.K_LEFT)])
    now[0] += REPEAT_DELAY_SECONDS
    console.filter_events(events=[])

    assert console.cursor == 2


def test_alt_arrows_move_by_word(console):
    """To a word's start going left and its end going right, past any spaces."""
    type_text(console, 'one  two three')

    press(console, pygame.K_LEFT, mod=pygame.KMOD_LALT)
    assert console.cursor == len('one  two ')
    press(console, pygame.K_LEFT, mod=pygame.KMOD_LALT)
    assert console.cursor == len('one  ')
    press(console, pygame.K_LEFT, mod=pygame.KMOD_LALT)
    assert console.cursor == 0
    press(console, pygame.K_LEFT, mod=pygame.KMOD_LALT)
    assert console.cursor == 0

    press(console, pygame.K_RIGHT, mod=pygame.KMOD_LALT)
    assert console.cursor == len('one')
    press(console, pygame.K_RIGHT, mod=pygame.KMOD_LALT)
    assert console.cursor == len('one  two')
    press(console, pygame.K_RIGHT, mod=pygame.KMOD_LALT)
    assert console.cursor == len('one  two three')
    press(console, pygame.K_RIGHT, mod=pygame.KMOD_LALT)
    assert console.cursor == len('one  two three')


def test_alt_with_a_letter_still_types(console):
    """Option+letter types a character on a Mac."""
    press(console, pygame.K_e, 'é', mod=pygame.KMOD_LALT)

    assert console.input_text == 'é'


def test_ctrl_w_and_ctrl_u_cut_for_ctrl_y(console):
    """A word back, then all the way back, each pasted again by Ctrl-Y."""
    type_text(console, 'one two  ')

    control(console, pygame.K_w)
    assert (console.input_text, console.cut_text) == ('one ', 'two  ')

    press(console, pygame.K_F15, 'x')
    press(console, pygame.K_LEFT)
    control(console, pygame.K_u)
    assert (console.input_text, console.cut_text, console.cursor) == ('x', 'one ', 0)

    control(console, pygame.K_y)
    assert (console.input_text, console.cursor) == ('one x', 4)


def test_ctrl_c_empties_the_line_when_nothing_is_running(console):
    """And restarts recall from the newest."""
    enter(console, '/help')
    press(console, pygame.K_UP)
    assert console.input_text == '/help'

    control(console, pygame.K_c)

    assert not console.input_text
    press(console, pygame.K_UP)
    assert console.input_text == '/help'


def test_ctrl_c_cancels_what_is_running_and_keeps_the_line(console, chat_service):
    """The request goes first: a half-typed next question stays."""
    fake, url = chat_service
    console.service_url = url
    fake.hold.clear()
    enter(console, 'something')
    running = console.running
    wait_until_the_request_reached(fake)
    type_text(console, 'next')

    control(console, pygame.K_c)
    fake.hold.set()

    assert console.running is None
    assert running.cancelled.is_set()
    assert console.input_text == 'next'
    assert f'#{running.number} cancelled' in transcript(console)


def test_a_new_line_below_leaves_a_scrolled_view_where_it_is(console):
    """And says how far back it is, until Enter comes back to the newest."""
    surface = pygame.Surface((320, 240))
    for number in range(40):
        console._add_line(text=f'line {number}')
    console.draw(surface=surface)
    newest = pygame.image.tobytes(console._panel, 'RGBA')
    press(console, pygame.K_UP, mod=pygame.KMOD_LSHIFT)
    console.draw(surface=surface)
    assert pygame.image.tobytes(console._panel, 'RGBA') != newest
    back = console._scroll_lines

    console._add_line(text='new one')
    console._add_line(text='new two')
    console.draw(surface=surface)
    assert console._scroll_lines == back + 2

    press(console, pygame.K_RETURN)
    console.draw(surface=surface)
    assert console._scroll_lines == 0


def test_the_view_at_the_newest_follows_new_lines(console):
    """Not scrolled back, it stays on the newest."""
    surface = pygame.Surface((320, 240))
    console.draw(surface=surface)

    console._add_line(text='new')
    console.draw(surface=surface)

    assert console._scroll_lines == 0


def test_a_long_input_line_keeps_the_cursor_on_screen(console):
    """What's before the cursor is cut to fit, and a line of any length still draws."""
    surface = pygame.Surface((320, 240))
    font = load_debug_font()
    long_text = 'word ' * 800
    console._set_input(text=long_text)
    console.draw(surface=surface)
    at_end = pygame.image.tobytes(console._panel, 'RGBA')

    press(console, pygame.K_HOME)
    console.draw(surface=surface)
    assert pygame.image.tobytes(console._panel, 'RGBA') != at_end

    tail = fitting_tail(text=long_text, font=font, width=100)
    assert long_text.endswith(tail)
    assert 0 < font.size(tail)[0] <= 100
    assert font.size(f'd{tail}')[0] > 100 or tail[0] != 'd'


def test_fitting_a_tail_of_short_or_nothing():
    """All of what fits, and nothing of what can't."""
    font = load_debug_font()

    assert fitting_tail(text='abc', font=font, width=1000) == 'abc'
    assert not fitting_tail(text='', font=font, width=10)
    assert not fitting_tail(text='W', font=font, width=1)


def test_copy_puts_the_last_answer_on_the_clipboard(console, chat_service, in_process_clipboard):
    """The answer alone, and saying so."""
    fake, url = chat_service
    console.service_url = url
    fake.lines = [stream_line(content='The answer.'), b'data: [DONE]\n\n']
    enter(console, 'something')
    wait_for(console, 'tokens in')

    enter(console, '/copy')
    wait_for(console, 'Copied the last answer')

    assert in_process_clipboard.paste() == 'The answer.'


def test_copy_with_no_answer_says_so(console, in_process_clipboard):
    """The clipboard stays as it was."""
    in_process_clipboard.copy('mine')

    enter(console, '/copy')

    assert 'No answer to copy yet' in transcript(console)
    assert in_process_clipboard.paste() == 'mine'


def wait_for_input(console: AiConsole) -> None:
    """Wait for text to reach the input line from the worker."""
    deadline = clock.raw_counter_seconds() + WAIT_SECONDS
    while not console.input_text and clock.raw_counter_seconds() < deadline:
        console.filter_events(events=[])
        clock.raw_sleep(0.01)


def test_paste_puts_the_clipboard_on_the_line_to_edit(console, in_process_clipboard):
    """As one line, at the cursor, not run: it waits for Enter."""
    in_process_clipboard.copy('one\r\ntwo\tthree')
    before = transcript(console)

    enter(console, '/paste')
    wait_for_input(console)

    assert console.input_text == 'one two three'
    assert console.cursor == len('one two three')
    assert transcript(console) == f'{before}\n> /paste'


def test_paste_of_nothing_says_so(console):
    """The harness's clipboard starts empty."""
    enter(console, '/paste')

    assert 'The clipboard holds no text' in wait_for(console, 'holds no text')
    assert not console.input_text


def test_paste_is_bounded(console, in_process_clipboard):
    """A clipboard can hold a whole file."""
    in_process_clipboard.copy('x' * (MAXIMUM_PASTED_CHARACTERS + 1))

    enter(console, '/paste')
    wait_for(console, 'Pasted only the first')

    assert len(console.input_text) == MAXIMUM_PASTED_CHARACTERS
    console.draw(surface=pygame.Surface((320, 240)))


@pytest.mark.parametrize(
    ('command', 'method'), [('/paste', 'paste'), ('/copy', 'copy')], ids=['paste', 'copy']
)
def test_no_clipboard_on_this_machine_is_reported(
    console, in_process_clipboard, mocker, command, method
):
    """As one line: headless Linux can have no clipboard program."""
    mocker.patch.object(
        in_process_clipboard, method, side_effect=ClipboardUnavailableError('no clipboard')
    )
    console.last_answer = 'An answer'

    enter(console, command)

    assert 'no clipboard' in wait_for(console, 'no clipboard')


def search(console: AiConsole, text: str = '') -> None:
    """Press Ctrl-R, and type what's given."""
    control(console, pygame.K_r)
    type_text(console, text)


def test_searching_finds_the_newest_match_then_older_ones(console):
    """As it's typed, ignoring case, skipping a repeat of the match, and saying when it runs out."""
    for line in ('/help ask', '/inspect Ball', '/help inspect', '/help ask'):
        enter(console, line)

    search(console, 'HELP')
    assert console.input_text == '/help ask'
    assert console._input_prompt() == '(search: HELP) '

    control(console, pygame.K_r)
    assert console.input_text == '/help inspect'
    control(console, pygame.K_r)
    assert console.input_text == '/help ask'
    assert console._input_prompt() == '(search: HELP) '
    control(console, pygame.K_r)
    assert console.input_text == '/help ask'
    assert console._input_prompt() == '(no match: HELP) '


def test_narrowing_and_widening_a_search(console):
    """Typing narrows it, Backspace widens it, and emptied it shows what was there before."""
    enter(console, '/help')
    enter(console, '/inspect')
    type_text(console, 'draft')

    search(console, 'i')
    assert console.input_text == '/inspect'
    type_text(console, 'zz')
    assert console._input_prompt() == '(no match: izz) '

    press(console, pygame.K_BACKSPACE)
    press(console, pygame.K_BACKSPACE)
    assert console.input_text == '/inspect'
    assert console._input_prompt() == '(search: i) '
    press(console, pygame.K_BACKSPACE)
    assert console.input_text == 'draft'
    press(console, pygame.K_BACKSPACE)
    assert console._input_prompt() == '(search: ) '


def test_ctrl_r_again_with_nothing_typed_stays_on_the_line(console):
    """No search text, nothing matches yet."""
    enter(console, '/help')
    type_text(console, 'draft')

    search(console)
    control(console, pygame.K_r)

    assert console.input_text == 'draft'


def test_esc_leaves_a_search_rather_than_the_console(console):
    """And puts back what was on the line."""
    enter(console, '/help')
    type_text(console, 'draft')
    search(console, 'help')
    assert console.input_text == '/help'

    press(console, pygame.K_ESCAPE)

    assert console.is_open
    assert console.input_text == 'draft'
    assert console._input_prompt() == '> '


def test_enter_runs_a_match(console):
    """Any key that does something ends the search and then does it."""
    enter(console, '/ai')
    before = transcript(console).count('> /ai')
    search(console, 'ai')

    press(console, pygame.K_RETURN)

    assert console._input_prompt() == '> '
    assert transcript(console).count('> /ai') == before + 1


def test_an_arrow_starts_editing_a_match(console):
    """The match stays, and the arrow moves in it."""
    enter(console, '/help')
    search(console, 'help')

    press(console, pygame.K_LEFT)

    assert console._input_prompt() == '> '
    assert (console.input_text, console.cursor) == ('/help', 4)


def test_a_key_that_types_nothing_leaves_the_search_alone(console):
    """Shift on its way to a capital mustn't end it."""
    enter(console, '/help')
    search(console, 'help')

    press(console, pygame.K_LSHIFT)

    assert console._input_prompt() == '(search: help) '


def test_closing_ends_a_search(console):
    """Reopening starts on the plain prompt."""
    search(console, 'x')

    press(console, GRAVE)
    press(console, GRAVE)

    assert console._input_prompt() == '> '


def test_the_input_line_shows_a_search(console):
    """It's drawn, not only held."""
    surface = pygame.Surface((320, 240))
    console.draw(surface=surface)
    plain = pygame.image.tobytes(console._panel, 'RGBA')

    search(console)
    console.draw(surface=surface)

    assert pygame.image.tobytes(console._panel, 'RGBA') != plain


def wait_for_past_questions(console: AiConsole) -> None:
    """Wait for the worker to bring past runs' questions."""
    deadline = clock.raw_counter_seconds() + WAIT_SECONDS
    while not console._past_questions and clock.raw_counter_seconds() < deadline:
        console.filter_events(events=[])
        clock.raw_sleep(0.01)


def test_searching_reaches_past_runs_questions(console, tmp_path):
    """From the history file, older than this run's, found even if they arrive after the typing."""
    path = console._history_path()
    path.parent.mkdir(parents=True)
    record = {'question': 'an old question'}
    path.write_text(json.dumps(record) + '\n', encoding='utf-8')
    enter(console, '/help')

    search(console, 'old')
    wait_for_past_questions(console)

    assert console.input_text == 'an old question'

    press(console, pygame.K_ESCAPE)
    search(console, 'help')
    assert console.input_text == '/help'
    control(console, pygame.K_r)
    assert console._input_prompt() == '(no match: help) '


def test_past_questions_arriving_with_no_search_typed_change_nothing(console):
    """Only searching looks at them, and the file is read once."""
    path = console._history_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'question': 'an old question'}) + '\n', encoding='utf-8')
    type_text(console, 'draft')

    search(console)
    wait_for_past_questions(console)
    assert console.input_text == 'draft'

    press(console, pygame.K_ESCAPE)
    path.unlink()
    search(console)
    console.filter_events(events=[])
    assert console._past_questions == ['an old question']


class TestTheDoors:
    """The console through AiHostSources, as the engine calls it."""

    def build(self, *, tmp_path: Any, events: list[Any], polled: InputSnapshot) -> AiHostSources:
        """Build the doors over stand-in inner doors.

        Returns:
            The doors.

        """
        inner = FakeInnerSources(events=events)
        inner.input_snapshot = lambda: polled
        inner.draws_overlay = False
        inner.draw_overlay = lambda *, surface: None
        inner.end_frame = lambda **_arguments: None
        return AiHostSources(inner=inner, link=AiLink(install_root=tmp_path))

    def test_they_hide_the_keys_and_draw_only_when_open(self, tmp_path):
        """Closed they add nothing to a frame."""
        polled = snapshot(pygame.KSCAN_W)
        doors = self.build(tmp_path=tmp_path, events=[], polled=polled)
        surface = pygame.Surface((320, 240))
        surface.fill((200, 0, 0))

        assert doors.draws_overlay is False
        assert doors.input_snapshot() is polled
        doors.draw_overlay(surface=surface)
        assert surface.get_at((315, 235))[:3] == (200, 0, 0)

        doors.inner.events = [key_event(pygame.KEYDOWN, GRAVE)]
        assert doors.pump_events() == []
        doors.inner.events = []

        assert doors.draws_overlay is True
        doors.draw_overlay(surface=surface)
        assert surface.get_at((315, 235))[:3] != (200, 0, 0)

    def test_ending_a_frame_notes_the_scene(self, tmp_path, scene):
        """That's how /inspect reads it, with no reach into the scene manager."""
        doors = self.build(tmp_path=tmp_path, events=[], polled=snapshot())

        doors.end_frame(frame_number=0, dt=0.0, scene=scene, control_events=[])

        assert doors.console.scene is scene
        assert doors.frames_ended == 1
