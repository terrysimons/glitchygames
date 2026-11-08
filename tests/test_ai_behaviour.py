"""The AI behaviour tests' machinery: stand-in tools, size limits, checks, and the runner's loop.

None of this needs the model: a fake server answers the runner, and small hand-made snapshots
stand in for captured ones.
"""

from __future__ import annotations

import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TYPE_CHECKING, Any, ClassVar

import pytest
from scripts.ai_behaviour.capture import FIXTURES_DIRECTORY, loggable
from scripts.ai_behaviour.paired import (
    PROJECT_ROOT,
    VERSIONS,
    WORKING_TREE,
    VersionError,
    Worker,
    exported_tree,
    first_answers,
)
from scripts.ai_behaviour.paired import main as paired_main
from scripts.ai_behaviour.questions import (
    QUESTIONS,
    Answered,
    BehaviourQuestion,
    check_winning,
    killer,
    next_pit,
    reaches_right_paddle,
)
from scripts.ai_behaviour.report import (
    CUT_OFF,
    failure_kind,
    mcnemar_exact,
    percentile,
    scored_again,
    wilson,
)
from scripts.ai_behaviour.report import main as report_main
from scripts.ai_behaviour.run import MAXIMUM_TOOL_ROUNDS, NUDGE_ROUNDS_LEFT, ask, summary
from scripts.ai_behaviour.tools import (
    GAME_PACKAGES,
    MAXIMUM_RESULT_CHARACTERS,
    TOOL_DEFINITIONS,
    SnapshotTools,
    calculate,
    compacted,
    fitted,
    source_examples,
    tool_definitions,
    tool_result_text,
    with_motion,
)
from scripts.ai_model_comparison import AskedOf

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def snapshot_with(**parts: Any) -> dict[str, Any]:
    """Build a small snapshot, with whatever a test doesn't care about filled in.

    Returns:
        The snapshot.

    """
    base: dict[str, Any] = {
        'game': 'paddleslap',
        'moment': 'test',
        'frame': 100,
        'scene': {'class': 'Game', 'rally_count': 2, 'all_sprites': ['BallSprite#0']},
        'facts': {'rally_count': 2},
        'sprites': {
            'BallSprite#0': {
                'class': 'BallSprite',
                'id': 'BallSprite#0',
                'world_x': 100.0,
                'world_y': 200.0,
                'speed': {'x': 30.0, 'y': -40.0},
                'image': {'surface': [20, 20]},
            },
            'BallSprite#1': {
                'class': 'BallSprite',
                'id': 'BallSprite#1',
                'world_x': 400.0,
                'world_y': 200.0,
            },
            'VerticalPaddle#0': {
                'class': 'VerticalPaddle',
                'id': 'VerticalPaddle#0',
                'rect': [0, 190, 20, 100],
            },
        },
        'window': [
            {
                'frame': frame,
                'scene': 'Game',
                'sprites': {'BallSprite#0': {'world_x': float(frame)}},
            }
            for frame in range(41, 101)
        ],
        'log': [{'frame': 0, 'scene': 'Game', 'rally_count': 0}, {'frame': 57, 'rally_count': 1}],
        'objects': {
            'battle': {
                'class': 'Battle',
                'soldiers': [{'id': 0, 'health': 6}, {'id': 1, 'health': 2}],
            }
        },
    }
    return {**base, **parts}


def tool_answer(tools: SnapshotTools, *, name: str, arguments: dict[str, Any]) -> Any:
    """Call a stand-in tool as the model would.

    Returns:
        Its answer as the model gets it, typed loosely: the tests index it as they expect it to
        be shaped, and a wrong shape fails the test.

    """
    return tools.call(name=name, arguments=arguments)


def test_calculate_does_arithmetic_and_nothing_else():
    """Numbers, operators and a few functions; anything else is refused by name."""
    assert calculate(expression='hypot(3, 4) + 2 ** 3 - (10 // 3) % 2') == 12.0
    assert calculate(expression='-pi') == pytest.approx(-math.pi)
    with pytest.raises(ValueError, match='not arithmetic'):
        calculate(expression='__import__("os")')
    with pytest.raises(ValueError, match='not arithmetic'):
        calculate(expression='round(2.5, ndigits=1)')


def test_every_answer_fits_and_lists_shrink_before_anything_is_cut():
    """The 8K limit was broken by single answers; now none is longer than the maximum."""
    long_list: dict[str, Any] = {
        'items': [{'value': index, 'name': 'x' * 40} for index in range(500)]
    }

    # Typed loosely, as tool_answer's are: the assertions below check the shapes
    fitted_list: Any = fitted(long_list)
    hopeless: Any = fitted({'text': 'y' * (MAXIMUM_RESULT_CHARACTERS * 2)})

    assert len(tool_result_text(fitted_list)) <= MAXIMUM_RESULT_CHARACTERS
    assert fitted_list['items'][-1].endswith('more')
    assert len(hopeless['start']) == MAXIMUM_RESULT_CHARACTERS
    assert 'ask for' in hopeless['note']


def test_pictures_go_and_long_lists_of_sprites_become_counts():
    """What's no use to the AI takes no room."""
    value: dict[str, Any] = {
        'image': {'surface': [8, 8]},
        'mask': {'surface': [8, 8]},
        'balls': [f'BallSprite#{index}' for index in range(9)],
        'pair': ['BallSprite#0', 'BallSprite#1'],
        'nested': [{'surface': [1, 1]}],
    }

    assert compacted(value) == {
        'balls': '9 sprites (list_sprites names them)',
        'pair': ['BallSprite#0', 'BallSprite#1'],
        'nested': [None],
    }


def test_motion_is_worked_out_in_a_players_words():
    """Speed combined properly (2B once added its parts) and a heading."""
    moving = with_motion({'speed': {'x': 30.0, 'y': -40.0}})
    still = with_motion({'speed': {'x': 0.0, 'y': 0.0}})

    assert moving['speed_pixels_per_second'] == 50.0
    assert moving['heading'] == 'right and up'
    assert still['heading'] == 'still'
    assert with_motion({'speed': 3}) == {'speed': 3}


def test_the_scene_is_compact_with_counts_by_class():
    """No sprite list, no pictures: the game's state and how many of each."""
    tools = SnapshotTools(snapshot=snapshot_with())

    scene = tool_answer(tools, name='get_scene', arguments={})

    assert scene['frame'] == 100
    assert scene['sprite_counts'] == {'BallSprite': 2, 'VerticalPaddle': 1}
    assert 'all_sprites' not in scene
    assert tools.calls == [{'name': 'get_scene', 'arguments': {}}]


def test_listing_sprites_counts_first_then_names_or_sorts_by_distance():
    """No class and nothing to be near gives counts; near sorts nearest first."""
    tools = SnapshotTools(snapshot=snapshot_with())

    assert tool_answer(tools, name='list_sprites', arguments={})['counts_by_class'] == {
        'BallSprite': 2,
        'VerticalPaddle': 1,
    }
    assert tool_answer(
        tools, name='list_sprites', arguments={'class_name': 'BallSprite', 'limit': 1}
    ) == [
        'BallSprite#0',
        '... 1 more',
    ]
    near = tool_answer(tools, name='list_sprites', arguments={'near': 'BallSprite#0'})
    assert [entry['id'] for entry in near] == ['VerticalPaddle#0', 'BallSprite#1']
    quoted = tool_answer(
        tools, name='list_sprites', arguments={'near': '"VerticalPaddle"', 'limit': 1}
    )
    assert [entry['id'] for entry in quoted] == ['BallSprite#0']
    # A wrong name says what is there, so the next try can be right
    assert tool_answer(tools, name='list_sprites', arguments={'near': 'Nothing#9'}) == {
        'error': 'no sprite Nothing#9 with a position now',
        'some_ids': ['BallSprite#0', 'VerticalPaddle#0'],
    }
    # "None" written as a word means no class
    assert 'counts_by_class' in tool_answer(
        tools, name='list_sprites', arguments={'class_name': 'None'}
    )
    assert tool_answer(tools, name='list_sprites', arguments={'class_name': 'Paddle'}) == {
        'error': 'no sprites of class Paddle now',
        'classes_present': ['BallSprite', 'VerticalPaddle'],
    }


def test_a_sprite_has_its_motion_and_a_gone_one_says_so():
    """The ids are never reused, so a missing one has gone or never was."""
    tools = SnapshotTools(snapshot=snapshot_with())

    ball = tool_answer(tools, name='get_sprite', arguments={'sprite_id': 'BallSprite#0'})

    assert ball['heading'] == 'right and up'
    assert 'image' not in ball
    # Quotes left on, and a class with one sprite now, both mean that sprite
    assert tool_answer(tools, name='get_sprite', arguments={'sprite_id': '"BallSprite#0"'})[
        'id'
    ] == ('BallSprite#0')
    assert tool_answer(tools, name='get_sprite', arguments={'sprite_id': 'VerticalPaddle'})[
        'id'
    ] == ('VerticalPaddle#0')
    # Two balls: which was meant can't be told
    assert 'error' in tool_answer(tools, name='get_sprite', arguments={'sprite_id': 'BallSprite'})
    gone = tool_answer(tools, name='get_sprite', arguments={'sprite_id': 'BallSprite#7'})
    assert 'gone' in gone['error']
    # Ids of the class it named, else one of each class
    assert gone['some_ids'] == ['BallSprite#0', 'BallSprite#1']
    assert tool_answer(tools, name='get_sprite', arguments={'sprite_id': 'Ghost#1'})[
        'some_ids'
    ] == [
        'BallSprite#0',
        'VerticalPaddle#0',
    ]


def test_objects_are_read_by_path():
    """The way into a game drawn without sprites."""
    tools = SnapshotTools(snapshot=snapshot_with())

    assert tool_answer(tools, name='get_object', arguments={}) == {'battle': 'dict'}
    # Naming the scene first reaches the same place
    assert tool_answer(tools, name='get_object', arguments={'path': 'scene.battle.soldiers.1'}) == (
        tool_answer(tools, name='get_object', arguments={'path': '"battle.soldiers.1"'})
    )
    assert tool_answer(tools, name='get_object', arguments={'path': 'battle.soldiers.1'}) == {
        'id': 1,
        'health': 2,
    }
    # A wrong step says where it got to and what is there
    assert tool_answer(tools, name='get_object', arguments={'path': 'battle.soldiers.9'}) == {
        'error': "nothing at '9' in 'battle.soldiers.9'",
        'reached': 'battle.soldiers',
        'list_length': 2,
    }
    assert tool_answer(tools, name='get_object', arguments={'path': 'army'}) == {
        'error': "nothing at 'army' in 'army'",
        'reached': '(the scene)',
        'fields_here': ['battle'],
    }
    assert tool_answer(tools, name='get_object', arguments={'path': 'battle.soldier'})[
        'fields_here'
    ] == ['soldiers']
    assert (
        tool_answer(tools, name='get_object', arguments={'path': 'battle.class.name'})['value_here']
        == 'Battle'
    )


def test_history_gives_changes_in_range_and_a_sprites_track_when_asked():
    """Summaries first; a track only for one sprite."""
    tools = SnapshotTools(snapshot=snapshot_with())

    plain = tool_answer(tools, name='history', arguments={'from_frame': 50})
    tracked = tool_answer(tools, name='history', arguments={'sprite_id': 'BallSprite#0'})

    assert plain['changes'] == [{'frame': 57, 'rally_count': 1}]
    assert 'track' not in plain
    assert plain['tracks_cover_frames'] == [41, 100]
    assert len(tracked['track']) <= 15
    assert tracked['track'][0]['frame'] == 41


def test_long_history_keeps_its_start_and_end():
    """The middle gives way, with a count."""
    log = [{'frame': frame, 'rally_count': frame} for frame in range(100)]
    tools = SnapshotTools(snapshot=snapshot_with(log=log))

    changes = tool_answer(tools, name='history', arguments={'to_frame': 99})['changes']

    assert changes[0] == {'frame': 0, 'rally_count': 0}
    assert changes[-1] == {'frame': 99, 'rally_count': 99}
    assert any(isinstance(change, str) and 'more changes' in change for change in changes)


def test_source_is_read_from_the_games_code():
    """A class's code with its file and line, a method alone, and a missing name refused."""
    tools = SnapshotTools(snapshot=snapshot_with())

    paddle = tool_answer(tools, name='read_source', arguments={'name': 'VerticalPaddle'})
    method = tool_answer(tools, name='read_source', arguments={'name': 'VerticalPaddle.speed_up'})

    assert 'paddle.py' in paddle['where']
    assert 'def speed_up' in method['source']
    # A guess leads to the real names: close spellings, and names holding the guess
    guessed = tool_answer(tools, name='read_source', arguments={'name': 'spawn_ball'})
    assert 'error' in guessed
    assert 'Game._spawn_new_ball' in guessed['closest_names']
    assert not any('.__eq__' in name for name in guessed['closest_names'])
    assert 'Game' in guessed['classes']
    # A property's code is its getter's; a class constant has no code, so it's a wrong guess
    clockwork = SnapshotTools(snapshot=snapshot_with(game='clockwork-keep'))
    getter = tool_answer(clockwork, name='read_source', arguments={'name': 'Tinker.world_x'})
    assert 'def world_x' in getter['source']
    constant = tool_answer(clockwork, name='read_source', arguments={'name': 'Tinker.IDLE'})
    assert 'closest_names' in constant
    # The calculator answers a wrong guess the same way: with what it accepts
    refused = tool_answer(tools, name='calculate', arguments={'expression': 'sqrt(x)'})
    assert refused['error'] == 'ValueError: not arithmetic: x'
    assert 'hypot' in refused['allowed']


def test_a_file_name_lists_the_classes_its_file_defines():
    """2B asks for files (game.py, a path, a module) about as often as for classes.

    In the two latest full runs, about 40 of 85 failed read_source calls named a file.
    """
    drawing_fire = SnapshotTools(snapshot=snapshot_with(game='drawing-fire'))

    def files(tools: SnapshotTools, name: str) -> list[dict[str, Any]]:
        return tool_answer(tools, name='read_source', arguments={'name': name})['files']

    (game_file,) = files(drawing_fire, 'game.py')
    assert game_file['file'].endswith('drawing_fire/game.py')
    # Only the classes the file defines, not the ones it imports (Battle is battle.py's)
    assert list(game_file['classes']) == ['Phase', 'DrawingFireScene']
    # A path from anywhere in the repository, a module's dotted name, or a bare module name
    for name in (
        'src/games/drawing-fire/src/drawing_fire/drivers.py',
        'drawing_fire.drivers',
        'drivers',
        'Drivers.py',
    ):
        (drivers_file,) = files(drawing_fire, name)
        assert list(drivers_file['classes']) == ['ComputerSoldier']
    # A package's own file
    paddleslap = SnapshotTools(snapshot=snapshot_with())
    (package_file,) = files(paddleslap, 'paddleslap/__init__.py')
    assert 'Game' in package_file['classes']
    # Two files of one name: both, unless the path tells them apart
    brave = SnapshotTools(snapshot=snapshot_with(game='brave-adventurer'))
    assert len(files(brave, 'levels.py')) == 2
    (core_levels,) = files(brave, 'brave_adventurer_core/levels.py')
    assert list(core_levels['classes']) == ['ScreenData', 'LevelManager']
    # A class's name still reads its code, even where a file has that name too (game.py)
    scene = tool_answer(drawing_fire, name='read_source', arguments={'name': 'DrawingFireScene'})
    assert 'files' not in scene
    assert scene['where'].startswith('src/games/drawing-fire/src/drawing_fire/game.py:')
    # Neither a class nor a file: the error lists the files too
    missing = tool_answer(drawing_fire, name='read_source', arguments={'name': 'src'})
    assert 'drawing_fire/game.py' in missing['files']


def test_drawing_is_recorded_and_copies_say_they_need_the_mirror():
    """For the checks; and nothing pretends to run."""
    tools = SnapshotTools(snapshot=snapshot_with())

    tool_answer(
        tools,
        name='draw',
        arguments={'kind': 'highlight', 'sprite_ids': ['BallSprite#0'], 'color': 'red'},
    )

    assert tools.drawings == [{'kind': 'highlight', 'sprite_ids': ['BallSprite#0'], 'color': 'red'}]
    assert 'unavailable' in tool_answer(tools, name='run_in_copy', arguments={'python': 'x = 1'})
    assert 'unavailable' in tool_answer(tools, name='screenshot', arguments={'frame': 3})
    assert 'no tool' in tool_answer(tools, name='teleport', arguments={})['error']
    assert 'error' in tool_answer(tools, name='get_sprite', arguments={})


def test_every_tool_offered_has_a_handler():
    """The definitions and the stand-ins can't drift apart."""
    for definition in TOOL_DEFINITIONS:
        assert hasattr(SnapshotTools, f'tool_{definition["function"]["name"]}')


def test_each_game_is_offered_examples_from_its_own_code():
    """2B copies examples, so another game's names in them became wrong guesses everywhere."""
    for game in GAME_PACKAGES:
        descriptions = ' '.join(
            definition['function']['description'] for definition in tool_definitions(game=game)
        )
        examples = source_examples(game=game)
        tools = SnapshotTools(snapshot=snapshot_with(game=game))

        # The literal placeholder, which tool_definitions must have replaced
        assert '{examples}' not in descriptions  # ruff: ignore[missing-f-string-syntax]
        assert all(f"'{example}'" in descriptions for example in examples)
        # Every example is a name read_source really finds
        for example in examples:
            assert 'error' not in tool_answer(
                tools, name='read_source', arguments={'name': example}
            )
    assert source_examples(game='clockwork-keep') == [
        'ClockworkKeepScene',
        'ClockworkKeepScene.dt_tick',
    ]
    assert 'ClockworkKeepScene' not in json.dumps(tool_definitions(game='mr-muncher'))


def test_logs_follow_what_changes_rarely():
    """Floats change every frame, so they stay out of the log."""
    assert loggable({'rally_count': 3, 'game_time': 1.5, 'phase': 'PLAYING'}) == {
        'rally_count': 3,
        'phase': 'PLAYING',
    }


def test_player_two_can_reach_a_ball_it_has_time_for_and_not_one_it_hasnt():
    """Worked out from positions, speeds, the paddle's 400 px/s and wall bounces."""
    paddle = {'class': 'VerticalPaddle', 'id': 'VerticalPaddle#1', 'rect': [780, 293, 20, 100]}

    def snapshot_for(world_y: float) -> dict[str, Any]:
        ball = {
            'class': 'BallSprite',
            'id': 'BallSprite#0',
            'world_x': 716.0,
            'world_y': world_y,
            'speed': {'x': 154.0, 'y': -229.0},
        }
        return snapshot_with(sprites={'BallSprite#0': ball, 'VerticalPaddle#1': paddle})

    assert reaches_right_paddle(snapshot_for(321.0)) == (True, 'BallSprite#0')
    # Far below, with no time to cover the distance
    paddle['rect'] = [780, 0, 20, 30]
    assert reaches_right_paddle(snapshot_for(470.0))[0] is False


def test_the_next_pit_is_the_next_gap_between_ground_segments():
    """From the player's front to the gap, and the gap's width."""
    sprites = {
        'Player#0': {'class': 'Player', 'id': 'Player#0', 'world_x': 300.0, 'rect': [0, 0, 24, 40]},
        'GroundSegment#0': {'class': 'GroundSegment', 'world_x': 0.0, 'rect': [0, 0, 350, 20]},
        'GroundSegment#1': {'class': 'GroundSegment', 'world_x': 450.0, 'rect': [0, 0, 350, 20]},
    }

    assert next_pit(snapshot_with(sprites=sprites)) == (26.0, 100.0)
    sprites['GroundSegment#1']['world_x'] = 350.0
    with pytest.raises(ValueError, match='no pit'):
        next_pit(snapshot_with(sprites=sprites))


def test_the_chaser_that_caught_you_is_the_nearest_at_the_moment():
    """Inferred from the window at the frame the dying began."""
    sprites = {
        'Muncher#0': {'class': 'Muncher', 'id': 'Muncher#0', 'name': 'Chomper'},
        'Muncher#1': {'class': 'Muncher', 'id': 'Muncher#1', 'name': 'Gnasher'},
    }
    window = [
        {
            'frame': 10,
            'sprites': {
                'Player#0': {'world_x': 0.0, 'world_y': 0.0},
                'Muncher#0': {'world_x': 50.0, 'world_y': 0.0},
                'Muncher#1': {'world_x': 5.0, 'world_y': 0.0},
            },
        }
    ]
    log = [{'frame': 10, 'phase': 'DYING'}]

    assert killer(snapshot_with(sprites=sprites, window=window, log=log)) == 'Gnasher'


def test_winning_breaks_a_tie_on_health_and_calls_a_dead_heat_even():
    """As many standing on each side: the healthier side leads, or it is even."""

    def answered(health: tuple[int, int], text: str) -> Answered:
        soldiers = [
            {'side': 'PLATOON', 'alive': True, 'health': health[0]},
            {'side': 'BRIGADE', 'alive': True, 'health': health[1]},
        ]
        snapshot = snapshot_with(for_checks={'battle': {'soldiers': soldiers}})
        return Answered(text=text, calls=[], drawings=[], snapshot=snapshot)

    assert check_winning(answered((4, 6), 'The Graphite Brigade, on health.'))[0] is True
    assert check_winning(answered((4, 6), 'The Pencil Platoon.'))[0] is False
    assert check_winning(answered((5, 5), "It's even."))[0] is True


def test_every_question_names_a_game_and_moment_and_has_categories():
    """And each name is used once."""
    names = [question.name for question in QUESTIONS]

    assert len(names) == len(set(names))
    for question in QUESTIONS:
        assert question.game in question.name or question.name.split('-')[0] in question.game
        assert question.categories
        assert question.moment


class FakeModel(BaseHTTPRequestHandler):
    """Answers in turns: each prepared response in order, keeping what it was sent."""

    bodies: ClassVar[list[dict[str, Any]]] = []
    queued_responses: ClassVar[list[tuple[int, dict[str, Any]]]] = []

    def do_POST(self) -> None:
        """Answer one round."""
        length = int(self.headers['Content-Length'])
        type(self).bodies.append(json.loads(self.rfile.read(length)))
        status, body = type(self).queued_responses.pop(0)
        self.send_response(status)
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, format: str, *args: Any) -> None:  # ruff: ignore[builtin-argument-shadowing] - the method's own name for it
        """Say nothing."""


@pytest.fixture
def hand_made_moment(mocker):
    """Serve the runner the hand-made snapshot instead of a captured one.

    Captured snapshots are generated (``scripts.ai_behaviour.capture``) and not committed, so
    the runner's tests mustn't need them.

    """
    mocker.patch(
        'scripts.ai_behaviour.run.load_snapshot', side_effect=lambda **_where: snapshot_with()
    )


@pytest.fixture
def model_target():
    """Run the fake model.

    Yields:
        How to reach it.

    """
    FakeModel.bodies = []
    FakeModel.queued_responses = []
    server = ThreadingHTTPServer(('127.0.0.1', 0), FakeModel)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield AskedOf(
        base_url=f'http://127.0.0.1:{server.server_address[1]}', api_key='key', alias='bonsai-2-2b'
    )
    server.shutdown()
    server.server_close()
    thread.join()


def round_with(
    *,
    content: str | None = None,
    calls: Sequence[tuple[str, dict[str, Any]]] = (),
    cache: int = 0,
    finish_reason: str | None = None,
) -> tuple[int, dict[str, Any]]:
    """Build one round of the fake model's answer.

    Returns:
        Its status and body.

    """
    tool_calls = [
        {
            'id': f'call-{index}',
            'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(arguments)},
        }
        for index, (name, arguments) in enumerate(calls)
    ]
    message: dict[str, Any] = {'role': 'assistant', 'content': content}
    if tool_calls:
        message['tool_calls'] = tool_calls
    return 200, {
        'choices': [
            {
                'message': message,
                'finish_reason': finish_reason or ('tool_calls' if tool_calls else 'stop'),
            }
        ],
        'timings': {'cache_n': cache, 'prompt_n': 100, 'predicted_n': 20},
    }


def a_question(**fields: Any) -> BehaviourQuestion:
    """Build a question on a real moment, judged by a simple check.

    Returns:
        The question.

    """
    defaults: dict[str, Any] = {
        'name': 'paddleslap-test',
        'game': 'paddleslap',
        'moment': 'two-balls-after-a-hit',
        'text': 'How many balls?',
        'categories': ('live',),
        'staleness': 'fast',
        'check': lambda answered: (answered.says('two'), 'should say two'),
    }
    return BehaviourQuestion(**{**defaults, **fields})


def test_the_runner_answers_tool_calls_then_judges_the_answer(model_target, hand_made_moment):
    """Tools run between rounds; context counts the cache too."""
    FakeModel.queued_responses = [
        round_with(calls=[('list_sprites', {'class_name': 'BallSprite'})], cache=2000),
        round_with(content='There are two balls.', cache=2100),
    ]

    result = ask(target=model_target, question=a_question())

    assert result['passed'] is True
    assert result['rounds'] == 2
    assert result['calls'] == [{'name': 'list_sprites', 'arguments': {'class_name': 'BallSprite'}}]
    assert result['context_used'] == 2220
    tool_message = FakeModel.bodies[1]['messages'][-1]
    assert tool_message['role'] == 'tool'
    assert 'BallSprite' in tool_message['content']
    assert FakeModel.bodies[0]['tools'] == tool_definitions(game='paddleslap')


def test_a_refusal_or_endless_tool_calls_fail_the_question(model_target, hand_made_moment):
    """A full context and a model that never stops calling tools are both failures."""
    FakeModel.queued_responses = [
        (400, {'error': {'message': 'request (10358 tokens) exceeds the available context size'}})
    ]
    refused = ask(target=model_target, question=a_question())
    FakeModel.bodies = []
    FakeModel.queued_responses = [
        round_with(calls=[('get_scene', {})]) for _ in range(MAXIMUM_TOOL_ROUNDS)
    ]
    endless = ask(target=model_target, question=a_question())

    assert (refused['passed'], 'request failed' in refused['why']) == (False, True)
    assert refused['overflow_tokens'] == 10358
    assert (endless['passed'], 'still calling tools' in endless['why']) == (False, True)
    # Asking the same thing again is answered with a note, not the answer again
    assert endless['repeated_calls'] == MAXIMUM_TOOL_ROUNDS - 1
    # Near the end it was told to answer with what it had
    nudged = FakeModel.bodies[MAXIMUM_TOOL_ROUNDS - NUDGE_ROUNDS_LEFT]['messages'][-1]
    assert nudged == {
        'role': 'user',
        'content': f'({NUDGE_ROUNDS_LEFT} tool rounds left: answer now with what you have.)',
    }


def test_unreadable_tool_arguments_are_treated_as_none(model_target, hand_made_moment):
    """A model's malformed JSON doesn't stop the run."""
    FakeModel.queued_responses = [
        (
            200,
            {
                'choices': [
                    {
                        'message': {
                            'role': 'assistant',
                            'content': None,
                            'tool_calls': [
                                {
                                    'id': 'x',
                                    'function': {'name': 'get_scene', 'arguments': '{not json'},
                                }
                            ],
                        }
                    }
                ]
            },
        ),
        round_with(content='two'),
    ]

    result = ask(target=model_target, question=a_question())

    assert result['calls'] == [{'name': 'get_scene', 'arguments': {}}]


def test_the_summary_gives_a_row_per_question():
    """Passes, median calls and time, the largest context, and the reasons."""
    results = [
        {
            'question': 'q',
            'passed': True,
            'why': '',
            'calls': [1, 2],
            'seconds': 2.0,
            'context_used': 3000,
        },
        {
            'question': 'q',
            'passed': False,
            'why': 'wrong',
            'calls': [1],
            'seconds': 4.0,
            'context_used': 5000,
        },
    ]

    assert '| q | 1/2 | 1.5 | 3.0 | 5000 | wrong |' in summary(results=results)


def test_an_answer_cut_off_by_a_full_context_fails_whatever_it_said(model_target, hand_made_moment):
    """Generation that ran into the end of the context never finished, so it can't pass."""
    FakeModel.queued_responses = [round_with(content='There are two balls', finish_reason='length')]

    result = ask(target=model_target, question=a_question())

    assert (result['passed'], result['why']) == (False, CUT_OFF)
    assert result['round_details'][0]['finish_reason'] == 'length'


def report_result(**fields: Any) -> dict[str, Any]:
    """Build one result as the runner writes it, with what a test doesn't care about filled in.

    Returns:
        The result.

    """
    defaults: dict[str, Any] = {
        'question': 'q',
        'categories': ['live'],
        'passed': True,
        'why': '',
        'answer': 'two',
        'calls': [],
        'rounds': 1,
        'seconds': 1.0,
        'context_used': 3000,
        'overflow_tokens': None,
        'round_details': [
            {
                'round': 1,
                'seconds': 1.0,
                'cache_tokens': 1700,
                'prompt_tokens': 100,
                'generated_tokens': 20,
                'finish_reason': 'stop',
                'tool_calls': [],
            }
        ],
        'tool_results': [],
        'repeated_calls': 0,
    }
    return {**defaults, **fields}


def test_report_names_each_kind_of_failure():
    """Refused for size, cut off, out of rounds, refused otherwise, empty, and wrong."""
    cut_off_details = [{**report_result()['round_details'][0], 'finish_reason': 'length'}]
    kinds = [
        failure_kind(scored_again(result))
        for result in (
            report_result(),
            report_result(passed=False, why='request failed: exceeds the available context'),
            # Passed by its check, but cut off: an older result, corrected on reading
            report_result(round_details=cut_off_details),
            report_result(passed=False, why='still calling tools after 16 rounds'),
            report_result(passed=False, why='request failed: connection refused'),
            report_result(passed=False, why='should say two', answer=' '),
            report_result(passed=False, why='should say two', answer='three'),
        )
    ]

    assert kinds == [
        'passed',
        'overflow: refused',
        'overflow: cut off',
        'out of rounds',
        'refused',
        'empty',
        'wrong',
    ]


def test_report_intervals_and_percentiles():
    """Wilson intervals stay inside 0-100 at the extremes; percentiles are by nearest rank."""
    assert wilson(passed=0, total=0) == (0.0, 0.0)
    assert wilson(passed=5, total=5)[1] == 100.0
    low, high = wilson(passed=25, total=50)
    assert (round(low), round(high)) == (37, 63)
    assert percentile([], 0.5) == 0.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0


def test_report_compares_two_configurations(tmp_path, capsys):
    """Every section, read from each configuration's directory, with the questions that changed."""
    refusal = 'request failed: request (8826 tokens) exceeds the available context size'
    for configuration, passed in (('2b-8192', False), ('2b-16384', True)):
        game_directory = tmp_path / configuration / 'paddleslap'
        game_directory.mkdir(parents=True)
        result = report_result(
            passed=passed,
            why='' if passed else refusal,
            overflow_tokens=None if passed else 8826,
            context_used=8912 if passed else 0,
            tool_results=[{'name': 'get_scene', 'characters': 850, 'error': False}],
            repeated_calls=1,
        )
        (game_directory / 'results.jsonl').write_text(json.dumps(result), encoding='utf-8')
        server = {'configuration': configuration, 'load_seconds': 1.0, 'footprint_mebibytes': 5243}
        (game_directory / 'server.json').write_text(json.dumps(server), encoding='utf-8')

    assert report_main([str(tmp_path / '2b-8192'), str(tmp_path / '2b-16384')]) == 0
    text = capsys.readouterr().out

    assert '| paddleslap | 0/1 0% (0-79) | 1/1 100% (21-100) |' in text
    assert '| overflow: refused | 1 | 0 |' in text
    # The 16K answer needed more than 8K; the 8K one was refused at 8826 tokens
    assert '| 2b-16384 | 8912 / 8912 / 8912 / 8912 | 0 | 1 | 1800 (1800-1800) | - |' in text
    assert '| 8826 |' in text
    assert '| get_scene | 1 calls, 0 errors, size p50 850 max 850 |' in text
    assert '1 repeated calls' in text
    assert '| 5243 |' in text
    assert '| q | 0/1 | 1/1 | +1 |' in text


def test_mcnemar_counts_only_the_pairs_that_split():
    """Even splits, or none, say nothing; six to none is unlikely by chance."""
    assert mcnemar_exact(only_first=0, only_second=0) == 1.0
    assert mcnemar_exact(only_first=3, only_second=3) == 1.0
    assert mcnemar_exact(only_first=0, only_second=6) == pytest.approx(2 / 64)
    assert mcnemar_exact(only_first=9, only_second=1) == pytest.approx(22 / 1024)


def test_the_coin_is_seeded_and_lets_each_version_answer_first():
    """The same seed gives the same order, and over many pairs neither version always leads."""
    orders = list(first_answers(seed=7, count=40))

    assert orders == list(first_answers(seed=7, count=40))
    assert {order[0] for order in orders} == set(VERSIONS)
    assert all(sorted(order) == sorted(VERSIONS) for order in orders)


def stand_in_version(
    *, root: Path, question_name: str, passes: bool, crashes: bool = False
) -> Path:
    """Lay out a version's tree with just what a worker imports, answering without a model.

    Returns:
        The tree.

    """
    package = root / 'scripts' / 'ai_behaviour'
    package.mkdir(parents=True)
    (root / 'scripts' / '__init__.py').write_text('', encoding='utf-8')
    (package / '__init__.py').write_text('', encoding='utf-8')
    (root / 'scripts' / 'ai_model_comparison.py').write_text(
        'from pydantic import BaseModel\n\n'
        'class AskedOf(BaseModel):\n'
        '    base_url: str\n'
        '    api_key: str\n'
        '    alias: str\n',
        encoding='utf-8',
    )
    (package / 'questions.py').write_text(
        f'import types\n\nQUESTIONS = [types.SimpleNamespace(name={question_name!r})]\n',
        encoding='utf-8',
    )
    result = report_result(question=question_name, passed=passes, why='' if passes else 'wrong')
    answer = 'raise SystemExit(3)' if crashes else f'return json.loads({json.dumps(result)!r})'
    (package / 'run.py').write_text(
        'import json\n\n'
        'def ask(*, target, question):\n'
        "    print('a version may print', target.alias)\n"
        f'    {answer}\n',
        encoding='utf-8',
    )
    return root


def test_a_worker_answers_from_its_own_version(tmp_path):
    """Its tree's code answers, and what it prints stays out of the answer.

    A question the version lacks, or a version that stops, is named.
    """
    target = AskedOf(base_url='http://127.0.0.1:9', api_key='key', alias='bonsai-2-2b')
    tree = stand_in_version(root=tmp_path / 'tree', question_name='q', passes=True)
    log = tmp_path / 'worker.log'
    with (
        log.open('w', encoding='utf-8') as log_file,
        Worker(tree=tree, target=target, log=log_file) as worker,
    ):
        assert worker.ask(question_name='q')['passed'] is True
        with pytest.raises(VersionError, match='has no question unknown'):
            worker.ask(question_name='unknown')
    assert 'a version may print bonsai-2-2b' in log.read_text(encoding='utf-8')

    broken = stand_in_version(
        root=tmp_path / 'broken', question_name='q', passes=True, crashes=True
    )
    with (
        (tmp_path / 'broken.log').open('w', encoding='utf-8') as log_file,
        Worker(tree=broken, target=target, log=log_file) as worker,
        pytest.raises(VersionError, match='stopped'),
    ):
        worker.ask(question_name='q')


def test_a_version_is_the_working_tree_or_a_refs_scripts(tmp_path):
    """A ref's scripts are exported, reading the working tree's snapshots; a bad ref is named."""
    assert exported_tree(ref=WORKING_TREE, directory=tmp_path) == PROJECT_ROOT

    tree = exported_tree(ref='HEAD', directory=tmp_path / 'head')
    assert (tree / 'scripts' / 'ai_behaviour' / 'run.py').is_file()
    assert (
        tree / 'scripts' / 'ai_behaviour' / 'fixtures'
    ).resolve() == FIXTURES_DIRECTORY.resolve()
    assert not (tree / 'scripts.tar').exists()

    with pytest.raises(VersionError, match='could not export no-such-ref'):
        exported_tree(ref='no-such-ref', directory=tmp_path / 'bad')


def test_a_paired_run_asks_both_versions_and_reports_the_split(tmp_path, mocker, capsys):
    """Each pair goes to both versions on one server; the report counts pairs only one passed."""
    question = next(question for question in QUESTIONS if question.game == 'paddleslap')
    trees = {
        'HEAD': stand_in_version(root=tmp_path / 'old', question_name=question.name, passes=False),
        WORKING_TREE: stand_in_version(
            root=tmp_path / 'new', question_name=question.name, passes=True
        ),
    }
    mocker.patch('scripts.ai_behaviour.paired.service_is_running', return_value=False)
    mocker.patch(
        'scripts.ai_behaviour.paired.exported_tree',
        side_effect=lambda *, ref, directory: trees[ref],
    )
    target = AskedOf(base_url='http://127.0.0.1:9', api_key='key', alias='bonsai-2-2b')
    server = mocker.patch('scripts.ai_behaviour.paired.running_server')
    server.return_value.__enter__.return_value = (target, 1.5, lambda: 900)
    output = tmp_path / 'paired'

    assert (
        paired_main([
            '--game',
            'paddleslap',
            '--output',
            str(output),
            '--repeats',
            '6',
            '--only',
            question.name,
        ])
        == 0
    )

    pairing = json.loads((output / 'pairing.json').read_text(encoding='utf-8'))
    assert pairing['old'] == 'HEAD'
    assert pairing['new'] == WORKING_TREE
    for version in VERSIONS:
        lines = (output / version / 'paddleslap' / 'results.jsonl').read_text(encoding='utf-8')
        results = [json.loads(line) for line in lines.splitlines()]
        assert [result['pair'] for result in results] == [
            f'{question.name}#{repeat}' for repeat in range(6)
        ]
        server_facts = json.loads(
            (output / version / 'paddleslap' / 'server.json').read_text(encoding='utf-8')
        )
        assert server_facts['footprint_mebibytes'] == 900
    capsys.readouterr()
    assert report_main([str(output / 'old'), str(output / 'new')]) == 0
    text = capsys.readouterr().out
    assert 'Only old passed 0, only new passed 6: McNemar exact p = 0.031.' in text
    assert f'| {question.name} | 0 | 6 |' in text


def test_runs_that_were_not_paired_get_no_paired_section(tmp_path, capsys):
    """Two ordinary runs have no pairs to match."""
    for configuration in ('first', 'second'):
        game_directory = tmp_path / configuration / 'paddleslap'
        game_directory.mkdir(parents=True)
        (game_directory / 'results.jsonl').write_text(json.dumps(report_result()), encoding='utf-8')

    assert report_main([str(tmp_path / 'first'), str(tmp_path / 'second')]) == 0

    assert 'Paired:' not in capsys.readouterr().out
