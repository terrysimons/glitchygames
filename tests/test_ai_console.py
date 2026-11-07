"""The AI console: real events, real drawing, a real local HTTP server, and real history files."""

from __future__ import annotations

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
    AiConsole,
    describe_scene,
    wrapped_lines,
)
from glitchygames.ai_host import AiHostSources
from glitchygames.ai_link import AiLink, LinkState
from glitchygames.debug.overlay import load_debug_font
from glitchygames.input.state import InputSnapshot
from glitchygames.scenes import Scene
from glitchygames.testing.keys import qwerty_scancode
from tests.test_ai_link import FakeInnerSources, install

WAIT_SECONDS = 10.0
GRAVE = pygame.K_BACKQUOTE


def key_event(event_type: int, key: int, unicode: str = '', scancode: int | None = None) -> Any:
    """Build a key event as SDL would, its scancode from the keymap unless given.

    Returns:
        The event.

    """
    code = qwerty_scancode(key=key) if scancode is None else scancode
    return pygame.event.Event(event_type, key=key, scancode=code, mod=0, unicode=unicode)


def press(console: AiConsole, key: int, unicode: str = '') -> list[Any]:
    """Press and release a key.

    Returns:
        What the game saw.

    """
    down = key_event(pygame.KEYDOWN, key, unicode)
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
    assert '/cancel /clear' in transcript(console)

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
    # Reached the server, so the worker isn't left polling for a service gone after this test
    deadline = clock.raw_counter_seconds() + WAIT_SECONDS
    while not fake.bodies and clock.raw_counter_seconds() < deadline:
        clock.raw_sleep(0.01)

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
