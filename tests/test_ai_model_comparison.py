"""The Bonsai comparison: its scoring, its question file, and a run against a fake server."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any, ClassVar

import pytest
from scripts.ai_model_comparison import (
    FACT_KINDS,
    STRUCTURED_KIND,
    Answer,
    AskedOf,
    Configuration,
    Question,
    QuestionResult,
    ServerFacts,
    answers_page,
    ask,
    ask_question,
    asked_result,
    load_questions,
    load_state,
    parse_configuration,
    score,
    summary_markdown,
    summary_rows,
    write_settings,
)

from glitchygames.ai_console import SYSTEM_PROMPT


def question_with(**fields: Any) -> Question:
    """Build a question, with whatever a test doesn't care about filled in.

    Returns:
        The question.

    """
    defaults = {'name': 'q', 'state': 's', 'kind': 'fact', 'turns': ('?',), 'example_answer': 'x'}
    return Question(**{**defaults, **fields})


def result_with(
    *, kind: str = 'fact', question: str = 'q', passed: bool = True, seconds: float = 2.0
) -> QuestionResult:
    """Build a result.

    Returns:
        The result.

    """
    return QuestionResult(
        configuration='2b-100',
        question=question,
        kind=kind,
        repeat=0,
        passed=passed,
        why='' if passed else 'wrong',
        answer=Answer(
            text='an <answer>',
            pieces=10,
            seconds=seconds,
            first_piece_seconds=0.5,
            first_answer_seconds=1.0,
            stopped=False,
        ),
    )


@pytest.mark.parametrize('question', load_questions(), ids=lambda question: question.name)
def test_every_question_accepts_its_example_answer(question):
    """The scoring has to pass a right answer, or it measures nothing."""
    assert score(question=question, answer=question.example_answer) == (True, '')


@pytest.mark.parametrize('question', load_questions(), ids=lambda question: question.name)
def test_every_question_refuses_no_answer_and_nonsense(question):
    """A question anything passes measures nothing either."""
    assert score(question=question, answer='  ')[0] is False
    assert score(question=question, answer='Purple elephants.')[0] is False


@pytest.mark.parametrize('question', load_questions(), ids=lambda question: question.name)
def test_every_question_is_well_formed(question):
    """It has a saved state, a known kind, a turn, and a way to be judged."""
    assert load_state(name=question.state)
    assert question.kind in {*FACT_KINDS, STRUCTURED_KIND}
    assert question.turns
    assert question.required or question.does_not_know or question.expected_json


def test_saying_it_does_not_know_fails_a_question_with_an_answer():
    """Refusing isn't right when the state does say."""
    for question in load_questions():
        if not question.does_not_know:
            assert score(question=question, answer='I do not know.')[0] is False


def test_the_file_has_every_kind_several_times():
    """Enough of each to compare the sizes on it."""
    questions = load_questions()
    for kind in (*FACT_KINDS, STRUCTURED_KIND):
        assert sum(question.kind == kind for question in questions) >= 2


def test_the_hard_questions_answers_follow_from_the_states():
    """Worked out from the states, as a wrong expectation would mark right answers down."""
    paddleslap = json.loads(load_state(name='paddleslap'))
    ball_lefts = sorted(
        sprite['rect'][0] for sprite in paddleslap['sprites'] if sprite['name'] == 'BallSprite'
    )
    assert ball_lefts == [49, 717]
    assert ball_lefts[1] - ball_lefts[0] == 668
    # Their world positions are apart by this, which is right too: the question is open to both
    ball_worlds = sorted(
        sprite['world_x'] for sprite in paddleslap['sprites'] if sprite['name'] == 'BallSprite'
    )
    assert round(ball_worlds[1] - ball_worlds[0], 2) == 665.28

    sprites = json.loads(load_state(name='clockwork_keep'))['sprites']
    platforms = [sprite for sprite in sprites if sprite['name'] == 'Platform']
    cogs = [sprite for sprite in sprites if sprite['name'] == 'Cog']
    tinker = next(sprite for sprite in sprites if sprite['name'] == 'Tinker')
    assert sum(1 for platform in platforms if platform['visible']) == 12
    assert sum(1 for sprite in sprites if sprite['visible']) == 19
    widest = max(platforms, key=lambda platform: platform['rect'][2])
    assert (widest['rect'][2], widest['world_y']) == (600, 936.0)
    nearest = min(
        cogs,
        key=lambda cog: (
            (cog['world_x'] - tinker['world_x']) ** 2 + (cog['world_y'] - tinker['world_y']) ** 2
        ),
    )
    assert nearest['world_y'] == 858.35
    assert [cog['world_y'] for cog in cogs if cog['visible']] == [
        858.35,
        778.35,
        778.35,
        688.35,
        508.35,
    ]


def test_the_states_hold_the_answers_the_questions_expect():
    """Spot checks that the saved states and the file agree."""
    paddleslap = json.loads(load_state(name='paddleslap'))
    assert paddleslap['game'] == {'rally_count': 1, 'balls_in_play': 2}
    clockwork = json.loads(load_state(name='clockwork_keep'))
    names = [sprite['name'] for sprite in clockwork['sprites']]
    assert names.count('Cog') == 6
    assert names.count('Platform') == 14
    hidden = [
        sprite
        for sprite in clockwork['sprites']
        if sprite['name'] == 'Cog' and not sprite['visible']
    ]
    assert [sprite['world_y'] for sprite in hidden] == [328.35]
    muncher = json.loads(load_state(name='mr_muncher'))
    assert muncher['sprite_count'] == 267
    assert {sprite['name'] for sprite in muncher['sprites']} == {'Sprocket'}


@pytest.mark.parametrize(
    'answer', ['800x480', '800 x 480', '800X480', '800\u00d7480', '800 by 480']
)
def test_dimensions_written_together_still_count_as_both_numbers(answer):
    """An x is a word character, so 800x480 once failed a question wanting 800."""
    question = question_with(required=(r'\b800\b', r'\b480\b'))

    assert score(question=question, answer=answer) == (True, '')


def test_required_and_forbidden_ignore_case():
    """Each required pattern must be there, and no forbidden one."""
    question = question_with(required=('player 1', '42'), forbidden=('nope',))

    assert score(question=question, answer='PLAYER 1 has 42')[0] is True
    assert score(question=question, answer='player 1 only') == (False, 'missing 42')
    assert score(question=question, answer='player 1 has 42, nope') == (False, 'holds nope')


@pytest.mark.parametrize(
    'answer',
    [
        'I do not know.',
        "I don't know the score.",
        'The state does not show a score.',
        'The score is not stated.',
        "It isn't listed.",
        'Unknown.',
    ],
)
def test_ways_of_saying_it_does_not_know(answer):
    """However it's put."""
    assert score(question=question_with(does_not_know=True), answer=answer)[0] is True


def test_inventing_an_answer_fails_a_question_with_none():
    """The state doesn't say, so a number is wrong."""
    assert score(question=question_with(does_not_know=True), answer='The score is 12.')[0] is False


@pytest.mark.parametrize(
    ('answer', 'passed'),
    [
        ('{"balls": 2, "rally": 1}', True),
        ('{"rally": 1, "balls": 2, "extra": true}', True),
        ('{"balls": 3, "rally": 1}', False),
        ('```json\n{"balls": 2, "rally": 1}\n```', False),
        ('[2, 1]', False),
        ('Two balls.', False),
    ],
)
def test_structured_answers_must_be_only_json_with_the_values(answer, passed):
    """A fence around it fails: an agent would have to clean it up first."""
    question = question_with(kind=STRUCTURED_KIND, expected_json={'balls': 2, 'rally': 1})

    assert score(question=question, answer=answer)[0] is passed


class FakeChatServer(BaseHTTPRequestHandler):
    """Streams the next prepared answer, keeping what it was asked."""

    bodies: ClassVar[list[dict[str, Any]]] = []
    answers: ClassVar[list[list[dict[str, str]]]] = []
    status: ClassVar[int] = 200

    def do_POST(self) -> None:
        """Answer one chat request."""
        length = int(self.headers['Content-Length'])
        type(self).bodies.append(json.loads(self.rfile.read(length)))
        self.send_response(type(self).status)
        self.end_headers()
        if type(self).status != 200:
            self.wfile.write(b'refused')
            return
        for delta in type(self).answers.pop(0):
            line = json.dumps({'choices': [{'delta': delta}]})
            self.wfile.write(f'data: {line}\n\n'.encode())
        self.wfile.write(b'data: [DONE]\n\n')

    def log_message(self, format: str, *args: Any) -> None:  # ruff: ignore[builtin-argument-shadowing] - the method's own name for it
        """Say nothing."""


@pytest.fixture
def chat_target():
    """Run a fake server.

    Yields:
        How to ask it.

    """
    FakeChatServer.bodies = []
    FakeChatServer.answers = []
    FakeChatServer.status = 200
    server = ThreadingHTTPServer(('127.0.0.1', 0), FakeChatServer)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield AskedOf(
        base_url=f'http://127.0.0.1:{server.server_address[1]}',
        api_key='secret',
        alias='bonsai-2-4b',
    )
    server.shutdown()
    server.server_close()
    thread.join()


def test_asking_sends_what_the_console_sends_and_times_the_answer(chat_target):
    """Low effort, no cache flattering the first token, and reasoning kept out of the answer."""
    FakeChatServer.answers = [
        [{'reasoning_content': 'hmm'}, {'content': 'Two'}, {'content': ' balls'}]
    ]

    answer = ask(target=chat_target, messages=[{'role': 'user', 'content': 'How many?'}])

    assert answer.text == 'Two balls'
    assert answer.pieces == 3
    assert answer.first_piece_seconds is not None
    assert answer.first_answer_seconds is not None
    assert answer.stopped is False
    body = FakeChatServer.bodies[0]
    assert body['model'] == 'bonsai-2-4b'
    assert body['stream'] is True
    assert body['cache_prompt'] is False
    # The service and console set no limit, and one would end hard questions mid-reasoning
    assert 'max_tokens' not in body
    assert body['chat_template_kwargs'] == {'reasoning_effort': 'low'}


def test_an_answer_past_the_time_limit_is_stopped_and_fails(chat_target, mocker):
    """A runaway answer can't stall the comparison."""
    FakeChatServer.answers = [[{'content': 'never'}]]
    readings = iter([0.0, *[1000.0] * 5])
    mocker.patch('glitchygames.clock.raw_counter_seconds', side_effect=lambda: next(readings))

    answer = ask(target=chat_target, messages=[], time_limit_seconds=1.0)

    assert answer.stopped is True
    assert not answer.text


def test_a_follow_up_is_scored_on_its_last_turn_with_the_first_in_its_history(chat_target):
    """Each turn sees the answers before it."""
    FakeChatServer.answers = [[{'content': 'At 717.'}], [{'content': 'At 49.'}]]
    question = question_with(turns=('Where is it?', 'and the other?'))

    answer = ask_question(target=chat_target, question=question, state='{"a": 1}')

    assert answer.text == 'At 49.'
    last = FakeChatServer.bodies[1]['messages']
    assert [message['role'] for message in last] == ['system', 'user', 'assistant', 'user']
    # The console's prompt, or this would measure something players never see
    assert last[0]['content'] == f'{SYSTEM_PROMPT}\n\nThe game right now: {{"a": 1}}'
    assert last[2]['content'] == 'At 717.'


def test_a_refusal_counts_against_the_size_and_the_run_goes_on(chat_target):
    """Reported in the result, with nothing raised."""
    FakeChatServer.status = 500

    result = asked_result(
        target=chat_target,
        configuration=Configuration(size='4b', context=100),
        question=question_with(required=('x',)),
        repeat=1,
        state='{}',
    )

    assert result.passed is False
    assert 'request failed' in result.why
    assert result.configuration == '4b-100'
    assert result.repeat == 1


def test_a_stopped_answer_fails_even_if_it_was_right(chat_target, mocker):
    """It didn't finish in time."""
    FakeChatServer.answers = [[{'content': 'x'}]]
    mocker.patch(
        'scripts.ai_model_comparison.ask_question',
        return_value=Answer(
            text='x',
            pieces=1,
            seconds=999.0,
            first_piece_seconds=1.0,
            first_answer_seconds=1.0,
            stopped=True,
        ),
    )

    result = asked_result(
        target=chat_target,
        configuration=Configuration(size='4b', context=100),
        question=question_with(required=('x',)),
        repeat=0,
        state='{}',
    )

    assert (result.passed, result.why) == (False, 'hit the time limit')


def test_settings_change_only_the_port_and_context(tmp_path):
    """The rest are the installed ones, so a run uses what the service uses."""
    root = tmp_path / 'install'
    (root / 'config').mkdir(parents=True)
    installed = 'AI_ROLE=reasoning\nAI_CONTEXT_SIZE=262144\nAI_PORT=23233\n'
    label = 'ai.glitchygames.bonsai-2-4b.llama-cpp'
    (root / 'config' / f'{label}.env').write_text(installed, encoding='utf-8')
    directory = tmp_path / 'copy'
    directory.mkdir()

    write_settings(
        root=root,
        configuration=Configuration(size='4b', context=32768),
        port=23239,
        directory=directory,
    )

    assert (directory / f'{label}.env').read_text(encoding='utf-8') == installed
    assert (directory / f'{label}.env.runtime').read_text(encoding='utf-8') == (
        'AI_PORT=23239\nAI_CONTEXT_SIZE=32768\n'
    )
    assert (root / 'config' / f'{label}.env').read_text(encoding='utf-8') == installed


def test_a_configuration_is_read_and_named():
    """SIZE:CONTEXT."""
    configuration = parse_configuration('9b:32768')

    assert (configuration.size, configuration.context) == ('9b', 32768)
    assert configuration.name == '9b-32768'


def test_the_summary_separates_facts_from_json():
    """So the owner can weigh them, and each column is what it says."""
    results = [
        result_with(kind='fact'),
        result_with(kind='absent', passed=False),
        result_with(kind=STRUCTURED_KIND),
        result_with(kind=STRUCTURED_KIND, question='hard-one', passed=False),
    ]
    servers = [ServerFacts(configuration='2b-100', load_seconds=3.0, footprint_mebibytes=512.0)]

    [row] = summary_rows(results=results, servers=servers)

    assert row['facts_percent'] == 50.0
    assert row['structured_percent'] == 50.0
    assert row['hard_percent'] == 0.0
    assert row['median_first_answer_seconds'] == 1.0
    # 10 pieces in the 1.5 s after the first one: the prompt's time doesn't count
    assert row['median_pieces_per_second'] == 6.67
    assert '| 2b-100 | 50.0 | 50.0 | 0.0 |' in summary_markdown(rows=[row])


def test_a_summary_of_a_size_with_no_results_says_nothing_rather_than_failing():
    """A filtered run may ask none of a kind."""
    servers = [ServerFacts(configuration='2b-100', load_seconds=3.0, footprint_mebibytes=None)]

    [row] = summary_rows(results=[], servers=servers)

    assert row['facts_percent'] is None
    assert row['median_total_seconds'] is None


def test_the_page_shows_every_answer_escaped_with_why_it_failed():
    """Side by side, and safe to open: a model can write anything."""
    question = question_with(name='q', turns=('How <many>?',))

    page = answers_page(questions=[question], results=[result_with(), result_with(passed=False)])

    assert 'How &lt;many&gt;?' in page
    assert 'an &lt;answer&gt;' in page
    assert '<answer>' not in page
    assert '1/2' in page
    assert '<small>wrong</small>' in page
