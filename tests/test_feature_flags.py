"""Feature flags: declared once, a parent wins, read where used, local to the run.

plans/2026-11-24-feature-flags-and-lucid-circuit-switch.md (Task 1). Parents, cycles and
availability are tested with throwaway declarations (``declare_flags``), passed as ``flags``.
"""

from __future__ import annotations

import argparse
import logging
import operator
from typing import Any, cast

import pytest
from pydantic import ValidationError

from glitchygames import feature_flags
from glitchygames.engine import ExitCode, GameEngine
from glitchygames.engine_context import EngineContext, current_context
from glitchygames.feature_flags import (
    FEATURE_FLAG_GROUP_TITLE,
    FEATURE_FLAGS,
    FeatureFlag,
    FeatureFlagDeclarationError,
    FlagOptionError,
    FlagState,
    UndeclaredFeatureFlagError,
    add_flag_arguments,
    declare_flags,
    flag_state,
    flag_state_lines,
    option_name,
    take_flag_options,
)
from glitchygames.replay.driver import REPLAY_LOCAL_OPTIONS, apply_recorded_options
from glitchygames.replay.tools import command
from glitchygames.replay.tools.golden_traces import GoldenTraceEngine, command_line
from glitchygames.replay.tools.registry import add_game_flags
from glitchygames.scenes import Scene
from tests import demo_runs, harness
from tests.replay.replay_helpers import replay_through_engine, rewrite_recording

LUCID_CIRCUIT = 'lucid-circuit'
BROWSER = 'emscripten'
ENGINE_ARGUMENTS = ('--headless', '--resolution', '320x240', '--log-level', 'warning')
MISSING_PART = 'the part is missing here'


def flag(
    name: str,
    *,
    default: bool = True,
    parent: str | None = None,
    unavailable: str | None = None,
    recorded: bool = False,
) -> FeatureFlag:
    """A throwaway declaration.

    Returns:
        The flag, unavailable with ``unavailable`` as the reason when given.

    """
    return FeatureFlag(
        name=name,
        summary=f'the {name} feature',
        default=default,
        parent=parent,
        availability=lambda: unavailable,
        recorded=recorded,
    )


def parsed(*arguments, flags):
    """Parse a command line holding only these flags' options.

    Returns:
        The options.

    """
    parser = argparse.ArgumentParser(prog='game')
    add_flag_arguments(parser=parser, flags=flags)
    return vars(parser.parse_args(arguments))


def state(name, *arguments, flags):
    """The state of a flag in a fresh context that was given a command line.

    Returns:
        The state.

    """
    with EngineContext(name='flags').active():
        take_flag_options(options=parsed(*arguments, flags=flags), flags=flags)
        return flag_state(name=name, flags=flags)


# --- What is declared ---


def test_lucid_circuit_is_declared_on_by_default_and_local_to_the_run():
    """The one flag today, as the owner decided it."""
    declared = FEATURE_FLAGS[LUCID_CIRCUIT]

    assert (declared.default, declared.parent, declared.recorded) == (True, None, False)


def test_the_declared_flags_are_read_only():
    """Neither the mapping nor a declaration in it can be changed."""
    with pytest.raises(TypeError):
        operator.setitem(cast('Any', FEATURE_FLAGS), 'another', flag('another'))
    with pytest.raises(ValidationError):
        FEATURE_FLAGS[LUCID_CIRCUIT].default = False


def test_lucid_circuit_is_unavailable_in_the_browser_whatever_was_asked(monkeypatch):
    """The check runs at each read: the platform is never kept from import time."""
    assert state(LUCID_CIRCUIT, flags=FEATURE_FLAGS) == FlagState(on=True)

    monkeypatch.setattr(feature_flags.sys, 'platform', BROWSER)

    for arguments in ((), ('--lucid-circuit',), ('--no-lucid-circuit',)):
        answer = state(LUCID_CIRCUIT, *arguments, flags=FEATURE_FLAGS)
        assert not answer.on
        assert 'browser' in str(answer.reason)


@pytest.mark.parametrize(
    ('declarations', 'said'),
    [
        ((flag('child', parent='nobody'),), "'child' has an undeclared parent, 'nobody'"),
        ((flag('alone', parent='alone'),), 'is its own parent: alone -> alone'),
        (
            (flag('a', parent='b'), flag('b', parent='c'), flag('c', parent='a')),
            'is its own parent: a -> b -> c -> a',
        ),
        # The cycle is reached from a flag outside it
        (
            (flag('a', parent='b'), flag('b', parent='c'), flag('c', parent='b')),
            'is its own parent: b -> c -> b',
        ),
        # Flags outside the cycle make the walk go round it more than once
        (
            (flag('a', parent='b'), flag('b', parent='a'), flag('c'), flag('d'), flag('e')),
            'is its own parent: b -> a -> b',
        ),
        ((flag('twice'), flag('twice', default=False)), "'twice' is declared twice"),
        ((flag('kept', recorded=True),), "'kept' is declared recorded"),
        *(
            ((flag(name),), 'is not kebab case')
            for name in ('', 'Lucid', 'lucid_circuit', '-lucid', 'lucid-', 'a--b', '1st', 'a b')
        ),
        ((flag('lucid\n'),), 'is not kebab case'),
        ((flag('no-sound'),), "'no-sound' starts with no-"),
    ],
)
def test_a_wrong_declaration_is_refused(declarations, said):
    """Each with an error naming the flag and what is wrong."""
    with pytest.raises(FeatureFlagDeclarationError) as refusal:
        declare_flags(*declarations)

    assert said in str(refusal.value)


def test_a_grandchild_and_names_with_digits_and_hyphens_are_accepted():
    """Parents may be declared after their children."""
    flags = declare_flags(flag('c', parent='b'), flag('b', parent='a2-x'), flag('a2-x'))

    assert list(flags) == ['c', 'b', 'a2-x']


def test_an_unknown_field_is_refused():
    """A misspelled field is an error, never ignored."""
    with pytest.raises(ValidationError):
        FeatureFlag.model_validate({
            'name': 'a',
            'summary': 'a',
            'default': True,
            'prent': 'b',
        })


# --- The state ---


@pytest.mark.parametrize('default', [True, False])
def test_the_default_answers_when_nothing_is_asked(default):
    """An empty command line leaves a flag at its declared default."""
    flags = declare_flags(flag('a', default=default))

    assert state('a', flags=flags).on is default


@pytest.mark.parametrize('default', [True, False])
def test_the_command_line_turns_a_flag_on_and_off(default):
    """Either way, whatever its default."""
    flags = declare_flags(flag('a', default=default))

    assert state('a', '--a', flags=flags) == FlagState(on=True)
    assert not state('a', '--no-a', flags=flags).on


def test_off_on_the_command_line_says_which_option_did_it():
    """The reason names the option as typed."""
    flags = declare_flags(flag('a-b'))

    assert state('a-b', '--no-a-b', flags=flags).reason == 'turned off by --no-a-b'


def test_off_by_default_says_how_to_turn_it_on():
    """The reason names the option that would turn it on."""
    flags = declare_flags(flag('a-b', default=False))

    assert state('a-b', flags=flags).reason == 'off by default; --a-b turns it on'


def test_a_default_off_flag_turned_off_on_the_command_line_says_so():
    """Only what was typed is an answer: the same value by default has another reason."""
    flags = declare_flags(flag('a-b', default=False))

    assert state('a-b', '--no-a-b', flags=flags).reason == 'turned off by --no-a-b'


def test_a_child_is_off_with_its_parent_whatever_was_asked_of_it():
    """The parent is named, with its own reason."""
    flags = declare_flags(flag('child', parent='parent'), flag('parent'))

    for asked in ((), ('--child',), ('--no-child',)):
        answer = state('child', '--no-parent', *asked, flags=flags)
        assert answer == FlagState(on=False, reason='parent is off: turned off by --no-parent')
    assert state('child', flags=flags) == FlagState(on=True)
    assert state('parent', '--no-child', flags=flags) == FlagState(on=True)
    assert state('child', '--no-child', flags=flags).reason == 'turned off by --no-child'


def test_a_grandchild_is_off_with_its_grandparent():
    """Parents win all the way up, each named."""
    flags = declare_flags(
        flag('child', parent='middle'), flag('middle', parent='top'), flag('top', default=False)
    )

    answer = state('child', flags=flags)

    assert not answer.on
    assert answer.reason is not None
    assert answer.reason.startswith('middle is off: top is off: off by default')


@pytest.mark.parametrize('arguments', [(), ('--a',), ('--no-a',), ('--no-parent',)])
def test_an_unavailable_flag_is_off_in_its_own_words_whatever_was_asked(arguments):
    """Availability comes before the parent and the option."""
    flags = declare_flags(flag('a', parent='parent', unavailable=MISSING_PART), flag('parent'))

    assert state('a', *arguments, flags=flags) == FlagState(on=False, reason=MISSING_PART)


def test_a_child_of_an_unavailable_parent_is_off():
    """The parent's own words are in the child's reason."""
    flags = declare_flags(flag('child', parent='parent'), flag('parent', unavailable=MISSING_PART))

    assert state('child', '--child', '--parent', flags=flags).reason == (
        f'parent is off: {MISSING_PART}'
    )


def test_a_flag_is_available_everywhere_unless_its_declaration_says_otherwise():
    """A declaration without an availability is never unavailable."""
    flags = declare_flags(FeatureFlag(name='a', summary='a', default=True))

    assert state('a', flags=flags) == FlagState(on=True)


def test_availability_is_asked_at_each_read():
    """A flag that stops being available is off at the next read."""
    answers = [None, MISSING_PART]
    flags = declare_flags(
        FeatureFlag(name='a', summary='a', default=True, availability=lambda: answers.pop(0))
    )

    with EngineContext(name='flags').active():
        assert flag_state(name='a', flags=flags).on
        assert not flag_state(name='a', flags=flags).on


def test_an_undeclared_name_raises():
    """A misspelled name is an error, never off."""
    with pytest.raises(UndeclaredFeatureFlagError, match='lucid-circus'):
        flag_state(name='lucid-circus')


@pytest.mark.parametrize(
    ('on', 'reason'), [(False, None), (False, ''), (True, 'turned off'), (True, '')]
)
def test_a_state_has_a_reason_exactly_when_it_is_off(on, reason):
    """Off without a reason, or on with one, cannot be made."""
    with pytest.raises(ValidationError):
        FlagState(on=on, reason=reason)


@pytest.mark.parametrize('on', [1, 0, 'yes', 'false'])
def test_a_states_on_is_a_bool_and_nothing_read_as_one(on):
    """Strict: no number or text becomes a state, with or without a reason."""
    for reason in (None, 'a reason'):
        with pytest.raises(ValidationError, match='valid boolean'):
            FlagState(on=on, reason=reason)


@pytest.mark.parametrize(
    ('field', 'value'), [('default', 1), ('default', 'off'), ('recorded', 0), ('name', b'a')]
)
def test_a_declarations_values_are_their_own_types(field, value):
    """Strict: a value of another type is refused, never converted."""
    declared: dict[str, Any] = {'name': 'a', 'summary': 'a', 'default': True}

    with pytest.raises(ValidationError, match=field):
        FeatureFlag.model_validate({**declared, field: value})


def test_a_state_is_frozen():
    """A state read is never changed."""
    answer = FlagState(on=True)

    with pytest.raises(ValidationError):
        answer.on = False


# --- What a context was asked ---


def test_before_any_engine_the_default_answers():
    """Nothing was asked in a context no engine was made in."""
    with EngineContext(name='no engine yet').active():
        assert flag_state(name=LUCID_CIRCUIT) == FlagState(on=True)


def test_options_without_the_flag_are_the_default_not_what_an_earlier_run_asked():
    """An old caller's options (or a test's) ask nothing."""
    with EngineContext(name='flags').active():
        take_flag_options(options={'lucid_circuit': False})
        assert not flag_state(name=LUCID_CIRCUIT).on

        take_flag_options(options={'log_level': 'warning'})

        assert flag_state(name=LUCID_CIRCUIT).on


def test_what_was_asked_is_kept_apart_from_the_options():
    """Local to the run: a replay writing its recorded options afterwards changes no flag."""
    options = {'lucid_circuit': False}
    with EngineContext(name='flags').active():
        take_flag_options(options=options)
        options['lucid_circuit'] = True

        assert not flag_state(name=LUCID_CIRCUIT).on


def test_only_what_was_typed_is_asked_and_every_option_ends_a_plain_bool():
    """The options are what a run logs and records: never None."""
    flags = declare_flags(flag('a'), flag('b', default=False), flag('c'), flag('d', default=False))
    options = parsed('--no-c', '--no-d', flags=flags)
    with EngineContext(name='flags').active() as context:
        take_flag_options(options=options, flags=flags)

        assert context.value(slot=feature_flags.FLAG_OPTIONS_SLOT).asked == {'c': False, 'd': False}
    assert options == {'a': True, 'b': False, 'c': False, 'd': False}


def test_options_that_hold_no_flag_are_given_none():
    """An old caller's options stay without an answer, so a feature's gate can fail closed."""
    options = {'log_level': 'warning'}
    with EngineContext(name='flags').active():
        take_flag_options(options=options)

    assert options == {'log_level': 'warning'}


@pytest.mark.parametrize('answer', ['off', 0, 1, '', [False]])
def test_an_answer_that_is_not_a_bool_is_refused_and_changes_nothing(answer):
    """Not read as on or off, and what was asked before it stays."""
    flags = declare_flags(flag('a'), flag('b'))
    options = {'a': None, 'b': answer}
    with EngineContext(name='flags').active():
        take_flag_options(options={'a': False}, flags=flags)

        with pytest.raises(FlagOptionError, match=r'--b: expected True, False or None, not '):
            take_flag_options(options=options, flags=flags)

        assert not flag_state(name='a', flags=flags).on
    assert options == {'a': None, 'b': answer}


def test_a_recording_never_sets_a_flag():
    """Every unrecorded flag's option is the run's own (REPLAY_LOCAL_OPTIONS)."""
    assert {option_name(flag_name=name) for name in FEATURE_FLAGS} <= REPLAY_LOCAL_OPTIONS

    for own, recorded in ((True, False), (False, True)):
        options = {'lucid_circuit': own}
        apply_recorded_options(options=options, recorded={'lucid_circuit': recorded})
        assert options == {'lucid_circuit': own}


@pytest.mark.parametrize('recorded', [True, False])
def test_the_removed_switch_of_an_old_recording_is_not_put_in_a_runs_options(recorded):
    """14 committed recordings hold ``ai``, which no option is now."""
    options = {'lucid_circuit': True}

    apply_recorded_options(options=options, recorded={'ai': recorded})

    assert options == {'lucid_circuit': True}


# --- The command line ---


def engine_options(*arguments):
    """The engine's options as a real game's command line gives them.

    Returns:
        The options.

    """
    with command_line(list(arguments)):
        return GameEngine.initialize_arguments(FlaggedGame)


class FlaggedGame(Scene):
    """A game with no arguments of its own."""

    NAME = 'Flagged Game'
    VERSION = '1.0'


class ClashingGame(FlaggedGame):
    """A game whose own argument is a feature flag's."""

    NAME = 'Clashing Game'

    @classmethod
    def args(cls, parser):
        """Take the flag's option."""
        parser.add_argument('--no-lucid-circuit', action='store_true')


@pytest.mark.parametrize(
    ('arguments', 'expected'),
    [((), None), (('--lucid-circuit',), True), (('--no-lucid-circuit',), False)],
)
def test_the_engine_has_an_option_for_each_flag(arguments, expected):
    """As a game's command line is parsed: None until its engine takes it, when none was typed."""
    assert engine_options(*arguments)['lucid_circuit'] is expected


@pytest.mark.parametrize('removed', ['--ai', '--no-ai', '--ai=1'])
@pytest.mark.parametrize('others', [(), ('--verify',), ('--replay-trace', 'run.jsonl.gz')])
def test_the_removed_switch_is_an_unknown_argument(capsys, removed, others):
    """Of a plain run, a tool's and a replay's: no alias, and no prefix of another option."""
    # The last keeps the run from starting, were the first to be known again
    refused = [removed, '--no-such-flag']
    with command_line([*others, *refused]), pytest.raises(SystemExit) as exit_information:
        GoldenTraceEngine(game=FlaggedGame)

    assert exit_information.value.code == ExitCode.ARGUMENT_PARSER_ERROR
    assert f'unrecognized arguments: {" ".join(refused)}' in capsys.readouterr().err


@pytest.mark.parametrize('removed', ['--ai', '--no-ai'])
def test_the_removed_switch_is_unknown_to_the_tools_command(capsys, removed):
    """``glitchygames verify --ai``."""
    with pytest.raises(SystemExit) as exit_information:
        command.main(['verify', removed])

    assert exit_information.value.code == ExitCode.ARGUMENT_PARSER_ERROR
    assert f'unrecognized arguments: {removed}' in capsys.readouterr().err


def test_the_help_lists_each_flag_in_its_group_with_its_summary_and_default():
    """Generated from the declaration."""
    parser = GameEngine.args(argparse.ArgumentParser(prog='game'))
    (group,) = [group for group in parser._action_groups if group.title == FEATURE_FLAG_GROUP_TITLE]
    (action,) = group._group_actions

    assert action.option_strings == ['--lucid-circuit', '--no-lucid-circuit']
    assert action.help == f'{FEATURE_FLAGS[LUCID_CIRCUIT].summary} (default: on)'


def test_a_summary_with_a_percent_sign_prints_as_written():
    """Argparse formats help with ``%``; the parent is named too."""
    flags = declare_flags(
        FeatureFlag(
            name='a',
            summary='50% of the frames',
            default=False,
            parent='b',
        ),
        flag('b'),
    )
    parser = argparse.ArgumentParser(prog='game')
    add_flag_arguments(parser=parser, flags=flags)

    printed = ' '.join(parser.format_help().split())

    assert '50% of the frames (default: off; off with --no-b)' in printed


def test_a_flag_named_as_a_tool_is_refused():
    """The engine's parser refuses it as the engine builds its parser."""
    flags = declare_flags(flag('verify'))
    parser = argparse.ArgumentParser(prog='game')
    add_game_flags(parser=parser)

    with pytest.raises(argparse.ArgumentError, match='conflicting option string: --verify'):
        add_flag_arguments(parser=parser, flags=flags)


def test_a_games_argument_that_clashes_with_a_flag_is_refused(capsys):
    """As any of the engine's options is (``reserved_flag_refusal``)."""
    with command_line([]), pytest.raises(SystemExit) as exit_information:
        GameEngine.initialize_arguments(ClashingGame)

    assert exit_information.value.code == ExitCode.OPTIONS_REFUSED
    assert '--no-lucid-circuit is reserved by the engine (an option of every game' in (
        capsys.readouterr().err
    )


# --- A run ---


@pytest.fixture
def engine_run_environment(mocker):
    """Let the test construct and start a real engine, leaving pygame usable for later tests.

    Yields:
        None, while the environment is in place.

    """
    yield from demo_runs.engine_run_environment(mocker)


@pytest.fixture
def quick_game():
    """A game that quits on its first frame.

    Returns:
        Its scene class.

    """

    class QuickGame(FlaggedGame):
        NAME = 'Quick Game'

        def dt_tick(self, dt):
            super().dt_tick(dt)
            self.scene_manager.quit()

    return QuickGame


@pytest.mark.usefixtures('engine_run_environment')
def test_a_games_flags_are_its_command_lines():
    """Set as the engine is built, before any scene: kept until the next engine replaces them."""
    with command_line([*ENGINE_ARGUMENTS, '--no-lucid-circuit']):
        GoldenTraceEngine(game=FlaggedGame)
    assert flag_state(name=LUCID_CIRCUIT).reason == 'turned off by --no-lucid-circuit'

    with command_line([*ENGINE_ARGUMENTS]):
        GoldenTraceEngine(game=FlaggedGame)
    assert flag_state(name=LUCID_CIRCUIT).on


@pytest.mark.usefixtures('engine_run_environment')
@pytest.mark.parametrize(('earlier', 'failed'), [('--no-', '--'), ('--', '--no-')])
def test_an_engine_that_fails_to_build_leaves_the_earlier_flags(tmp_path, earlier, failed):
    """As it leaves no half-made engine current: no run of its own ever asked anything."""
    with command_line([*ENGINE_ARGUMENTS, f'{earlier}lucid-circuit']):
        GoldenTraceEngine(game=FlaggedGame)
    before = flag_state(name=LUCID_CIRCUIT)

    missing = tmp_path / 'missing.jsonl.gz'
    with (
        command_line([
            *ENGINE_ARGUMENTS,
            f'{failed}lucid-circuit',
            '--replay-trace',
            str(missing),
        ]),
        pytest.raises(SystemExit),
    ):
        GoldenTraceEngine(game=FlaggedGame)

    assert flag_state(name=LUCID_CIRCUIT) == before
    assert before.on is (earlier == '--')


@pytest.mark.usefixtures('engine_run_environment')
def test_a_first_engine_that_fails_to_build_leaves_nothing_asked(tmp_path):
    """The context answers the default again."""
    with (
        command_line([
            *ENGINE_ARGUMENTS,
            '--no-lucid-circuit',
            '--replay-trace',
            str(tmp_path / 'missing.jsonl.gz'),
        ]),
        pytest.raises(SystemExit),
    ):
        GoldenTraceEngine(game=FlaggedGame)

    assert flag_state(name=LUCID_CIRCUIT).on


@pytest.mark.draws_frames
@pytest.mark.usefixtures('engine_run_environment')
@pytest.mark.parametrize('option', ['ai', 'lucid_circuit'])
@pytest.mark.parametrize('recorded', [True, False])
def test_a_replay_keeps_its_own_switch_whatever_the_recording_holds(
    mocker, tmp_path, quick_game, option, recorded
):
    """On or off as its own command line asked, and the recording matches either way."""
    recording = tmp_path / 'run.jsonl.gz'
    with command_line([*ENGINE_ARGUMENTS, '--record-trace', str(recording)]):
        GoldenTraceEngine(game=quick_game).start()
    rewrite_recording(
        recording_path=recording,
        change=lambda trace: trace['options'].update({option: recorded}),
    )
    started = mocker.spy(GoldenTraceEngine, 'start')

    for arguments, on in (((), True), (('--no-lucid-circuit',), False)):
        replay = replay_through_engine(
            mocker=mocker, scene_class=quick_game, path=recording, extra_arguments=arguments
        )

        engine = started.call_args.args[0]
        assert replay.exit_status == ExitCode.SUCCESS
        assert flag_state(name=LUCID_CIRCUIT).on is on
        assert engine.options['lucid_circuit'] is on
        assert 'ai' not in engine.options
        assert engine.ai_link is None


@pytest.mark.draws_frames
@pytest.mark.usefixtures('engine_run_environment')
def test_a_flag_stays_as_asked_after_the_run(quick_game):
    """A scene's clean-up, after the engine stopped being current, still sees the flag off."""
    with command_line([*ENGINE_ARGUMENTS, '--no-lucid-circuit']):
        GoldenTraceEngine(game=quick_game).start()

    assert not flag_state(name=LUCID_CIRCUIT).on


@pytest.mark.draws_frames
@pytest.mark.usefixtures('engine_run_environment')
@pytest.mark.parametrize(
    ('arguments', 'line'),
    [
        ((), 'lucid-circuit = on'),
        (('--no-lucid-circuit',), 'lucid-circuit = off: turned off by --no-lucid-circuit'),
    ],
)
def test_a_start_logs_each_flag_once_with_the_options_block(quick_game, caplog, arguments, line):
    """One record: the options, then each state and why."""
    with command_line([*ENGINE_ARGUMENTS, *arguments]):
        engine = GoldenTraceEngine(game=quick_game)
    # What its build said (ai_link's INFO line) shows at whatever level the process was left
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        engine.start()

    mentioning = [record for record in caplog.records if LUCID_CIRCUIT in record.getMessage()]
    (record,) = mentioning
    lines = [text.strip() for text in record.getMessage().splitlines()]
    assert record.levelno == logging.CRITICAL
    assert lines[0] == 'Options for Quick Game (secrets redacted):'
    assert lines[-2:] == ['Feature flags:', line]
    (option_line,) = [text for text in lines if text.startswith('lucid_circuit ')]
    assert option_line.endswith(f'= {not arguments}')


@pytest.mark.draws_frames
@pytest.mark.usefixtures('engine_run_environment')
def test_a_start_logs_its_own_engines_flags_not_a_later_ones(quick_game, caplog):
    """Two engines made in one context, the first started after the second was made."""
    with command_line([*ENGINE_ARGUMENTS, '--no-lucid-circuit']):
        first = GoldenTraceEngine(game=quick_game)
    with command_line([*ENGINE_ARGUMENTS]):
        GoldenTraceEngine(game=FlaggedGame)
    caplog.clear()
    with caplog.at_level(logging.CRITICAL):
        first.start()

    (block,) = [text for text in caplog.messages if text.startswith('Options for')]
    assert block.splitlines()[-1].strip() == (
        'lucid-circuit = off: turned off by --no-lucid-circuit'
    )


def test_the_state_lines_are_sorted_and_say_why():
    """On, off as asked and unavailable each read differently."""
    flags = declare_flags(flag('b', default=False), flag('a'), flag('c', unavailable=MISSING_PART))

    assert flag_state_lines(flags=flags) == [
        'a = on',
        'b = off: off by default; --b turns it on',
        f'c = off: {MISSING_PART}',
    ]


def test_no_flag_is_asked_in_a_context_left_alone():
    """The harness starts each test with nothing asked, as a fresh process would."""
    current_context().value(slot=feature_flags.FLAG_OPTIONS_SLOT).asked = {'lucid_circuit': False}
    assert not flag_state(name=LUCID_CIRCUIT).on

    harness._reset_all_singleton_instances()

    assert dict(current_context().value(slot=feature_flags.FLAG_OPTIONS_SLOT).asked) == {}
