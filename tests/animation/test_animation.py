"""Tests for expression parser, coroutine scheduler, and animation state machine."""

from dataclasses import dataclass, field
from itertools import product
from typing import Any

import pytest

from glitchygames.animation.expressions import (
    Expression,
    parse,
    tokenize,
)
from glitchygames.animation.scheduler import BehaviorScheduler
from glitchygames.animation.state_machine import AnimationStateMachine
from glitchygames.examples.brave_adventurer.constants import (
    FALLING_VELOCITY_THRESHOLD as BRAVE_ADVENTURER_FALLING_VELOCITY_THRESHOLD,
)
from glitchygames.examples.clockwork_keep.constants import (
    FALLING_VELOCITY_THRESHOLD as CLOCKWORK_KEEP_FALLING_VELOCITY_THRESHOLD,
)

# --- Test helpers ---


@dataclass
class FakeSprite:
    """Minimal sprite for testing state machine integration."""

    current_animation: str = 'idle'
    is_looping: bool = True
    _loop_flags: dict = field(
        default_factory=lambda: {
            'idle': True,
            'running': True,
            'jumping': False,
            'falling': False,
        }
    )

    def play(self, animation_name: str) -> None:
        """Switch animation."""
        self.current_animation = animation_name


# --- Expression Parser ---


class TestExpressionParser:
    """Phase 1 expression parsing and evaluation."""

    def test_bare_variable_true(self):
        """Bare variable evaluates to its bool value."""
        expr = parse('on_ground')
        assert expr.evaluate({'on_ground': True}) is True

    def test_bare_variable_false(self):
        """Bare variable that's False evaluates to False."""
        expr = parse('on_ground')
        assert expr.evaluate({'on_ground': False}) is False

    def test_unknown_variable_is_false(self):
        """Unknown variables default to False."""
        expr = parse('nonexistent')
        assert expr.evaluate({}) is False

    def test_comparison_greater_than(self):
        """Greater-than comparison works."""
        expr = parse('velocity_y > 10.0')
        assert expr.evaluate({'velocity_y': 15.0}) is True
        assert expr.evaluate({'velocity_y': 5.0}) is False

    def test_comparison_less_than(self):
        """Less-than comparison with negative number."""
        expr = parse('velocity_y < -10.0')
        assert expr.evaluate({'velocity_y': -15.0}) is True
        assert expr.evaluate({'velocity_y': 0.0}) is False

    def test_comparison_greater_equal(self):
        """Greater-or-equal comparison."""
        expr = parse('velocity_x >= 0.0')
        assert expr.evaluate({'velocity_x': 0.0}) is True
        assert expr.evaluate({'velocity_x': -1.0}) is False

    def test_comparison_less_equal(self):
        """Less-or-equal comparison."""
        expr = parse('timer <= 2.0')
        assert expr.evaluate({'timer': 2.0}) is True
        assert expr.evaluate({'timer': 3.0}) is False

    def test_abs_comparison(self):
        """abs() function with comparison."""
        expr = parse('abs(velocity_x) > 0.1')
        assert expr.evaluate({'velocity_x': 0.5}) is True
        assert expr.evaluate({'velocity_x': -0.5}) is True
        assert expr.evaluate({'velocity_x': 0.05}) is False

    def test_boolean_literal_true(self):
        """Boolean literal 'true'."""
        expr = parse('true')
        assert expr.evaluate({}) is True

    def test_boolean_literal_false(self):
        """Boolean literal 'false'."""
        expr = parse('false')
        assert expr.evaluate({}) is not True

    def test_empty_expression_raises(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError, match='Empty expression'):
            parse('')

    def test_invalid_characters_raise(self):
        """Invalid characters raise ValueError."""
        with pytest.raises(ValueError, match='Invalid characters'):
            parse('velocity_x & 5')


class RecordingExpression(Expression):
    """Probe expression that records whether it was evaluated."""

    def __init__(self, *, result: bool, raises: bool = False) -> None:
        """Initialize with the result to return and whether evaluating is an error."""
        self.result = result
        self.raises = raises
        self.evaluation_count = 0

    def evaluate(self, context: dict[str, Any]) -> bool:
        self.evaluation_count += 1
        if self.raises:
            msg = 'right side should not have been evaluated'
            raise AssertionError(msg)
        return self.result


class TestBooleanOperators:
    """Phase 2: and / or / not / parentheses."""

    @pytest.mark.parametrize(('first', 'second', 'third'), list(product([True, False], repeat=3)))
    def test_or_binds_looser_than_and(self, first, second, third):
        context = {'a': first, 'b': second, 'c': third}
        assert parse('a or b and c').evaluate(context) is (first or (second and third))
        assert parse('a or b and c').evaluate(context) is parse('a or (b and c)').evaluate(context)

    @pytest.mark.parametrize(('first', 'second'), list(product([True, False], repeat=2)))
    def test_not_binds_tighter_than_and_and_or(self, first, second):
        context = {'a': first, 'b': second}
        assert parse('not a and b').evaluate(context) is ((not first) and second)
        assert parse('not a or b').evaluate(context) is ((not first) or second)

    def test_not_groups_override_precedence(self):
        context = {'a': True, 'b': False}
        assert parse('not (a and b)').evaluate(context) is True
        assert parse('not a and b').evaluate(context) is False

    @pytest.mark.parametrize('values', list(product([True, False], repeat=4)))
    def test_and_or_chains_are_left_associative(self, values):
        context = dict(zip('abcd', values, strict=True))
        first, second, third, fourth = values
        assert parse('a and b and c and d').evaluate(context) is (
            first and second and third and fourth
        )
        assert parse('a or b or c or d').evaluate(context) is bool(
            first or second or third or fourth
        )
        assert parse('a or b and c or d').evaluate(context) is bool(
            first or (second and third) or fourth
        )

    def test_left_associativity_shape(self):
        expression = parse('a and b and c')
        assert expression.left.__class__.__name__ == 'AndExpr'  # type: ignore[attr-defined]
        assert expression.right.__class__.__name__ == 'VariableExpr'  # type: ignore[attr-defined]

    def test_nested_parentheses(self):
        expression = parse('((a or b) and (c or (d and e)))')
        assert expression.evaluate({'a': True, 'c': False, 'd': True, 'e': True}) is True
        assert expression.evaluate({'a': True, 'c': False, 'd': True, 'e': False}) is False
        assert expression.evaluate({'b': True, 'c': True}) is True

    def test_double_negation(self):
        assert parse('not not x').evaluate({'x': True}) is True
        assert parse('not not x').evaluate({'x': False}) is False
        assert parse('not not not x').evaluate({'x': False}) is True

    def test_results_are_booleans_for_numeric_operands(self):
        assert parse('speed and flag').evaluate({'speed': 3.0, 'flag': 2.0}) is True
        assert parse('speed or flag').evaluate({'speed': 0.0, 'flag': 0.0}) is False
        assert parse('not speed').evaluate({'speed': 0.0}) is True
        assert parse('not speed').evaluate({'speed': 5.0}) is False

    def test_and_short_circuits_when_left_is_false(self):
        from glitchygames.animation.expressions import AndExpr

        right = RecordingExpression(result=True, raises=True)
        expression = AndExpr(left=RecordingExpression(result=False), right=right)
        assert expression.evaluate({}) is False
        assert right.evaluation_count == 0

    def test_or_short_circuits_when_left_is_true(self):
        from glitchygames.animation.expressions import OrExpr

        right = RecordingExpression(result=False, raises=True)
        expression = OrExpr(left=RecordingExpression(result=True), right=right)
        assert expression.evaluate({}) is True
        assert right.evaluation_count == 0

    def test_and_or_evaluate_right_when_left_does_not_decide(self):
        from glitchygames.animation.expressions import AndExpr, OrExpr

        right_for_and = RecordingExpression(result=True)
        assert AndExpr(left=RecordingExpression(result=True), right=right_for_and).evaluate({})
        assert right_for_and.evaluation_count == 1
        right_for_or = RecordingExpression(result=True)
        assert OrExpr(left=RecordingExpression(result=False), right=right_for_or).evaluate({})
        assert right_for_or.evaluation_count == 1

    def test_not_expr_negates(self):
        from glitchygames.animation.expressions import NotExpr

        assert NotExpr(operand=RecordingExpression(result=False)).evaluate({}) is True

    def test_comparison_inside_group(self):
        expression = parse('(velocity_y > 50) and not on_ground')
        assert expression.evaluate({'velocity_y': 60.0, 'on_ground': False}) is True
        assert expression.evaluate({'velocity_y': 60.0, 'on_ground': True}) is False
        assert expression.evaluate({'velocity_y': 40.0, 'on_ground': False}) is False

    def test_abs_inside_or(self):
        expression = parse('abs(velocity_x) > 0.1 or in_air')
        assert expression.evaluate({'velocity_x': -0.5}) is True
        assert expression.evaluate({'velocity_x': 0.0, 'in_air': True}) is True
        assert expression.evaluate({'velocity_x': 0.0}) is False

    def test_abs_inside_group(self):
        expression = parse('(abs(velocity_x) > 0.1) and not (timer > 2)')
        assert expression.evaluate({'velocity_x': -1.0, 'timer': 1.0}) is True
        assert expression.evaluate({'velocity_x': -1.0, 'timer': 3.0}) is False

    def test_boolean_literals_combine(self):
        assert parse('true and not false').evaluate({}) is True
        assert parse('false or false').evaluate({}) is False


class TestExpressionErrors:
    """Malformed Phase 2 expressions raise clear ValueErrors."""

    @pytest.mark.parametrize(
        ('expression_string', 'message'),
        [
            ('(a and b', 'Unbalanced parentheses'),
            ('a and b)', 'Unbalanced parentheses'),
            ('((a)', 'Unbalanced parentheses'),
            ('on_ground and', 'Unexpected end of expression'),
            ('on_ground or', 'Unexpected end of expression'),
            ('not', 'Unexpected end of expression'),
            ('()', 'Empty parentheses'),
            ('a and ()', 'Empty parentheses'),
            ('a < b < c', 'Chained comparison'),
            ('a < b > c', 'Chained comparison'),
            ('and on_ground', "Unexpected operator 'and'"),
            ('or on_ground', "Unexpected operator 'or'"),
            ('a and and b', "Unexpected operator 'and'"),
            ('a b', 'Unexpected tokens after expression'),
        ],
    )
    def test_malformed_expressions(self, expression_string, message):
        with pytest.raises(ValueError, match=message):
            parse(expression_string)

    @pytest.mark.parametrize('reserved_word', ['and', 'or', 'not', 'abs'])
    def test_reserved_word_as_variable(self, reserved_word):
        with pytest.raises(ValueError, match=f"'{reserved_word}'"):
            parse(f'{reserved_word} > 1')

    def test_reserved_word_on_right_side_of_comparison(self):
        with pytest.raises(ValueError, match="Reserved word 'not'"):
            parse('velocity_y > not')

    def test_keywords_are_lowercase_only(self):
        assert parse('AND').evaluate({'AND': True}) is True
        assert parse('Not').evaluate({'Not': True}) is True


class TestKeywordTokenization:
    """Keywords match as whole words only."""

    def test_variable_starting_with_abs_tokenizes_whole(self):
        assert tokenize('absolute_speed > 1') == ['absolute_speed', '>', '1']

    def test_variables_starting_with_keywords(self):
        assert tokenize('android or order and nothing') == [
            'android',
            'or',
            'order',
            'and',
            'nothing',
        ]

    def test_absolute_speed_parses_and_evaluates(self):
        expression = parse('absolute_speed > 1')
        assert expression.evaluate({'absolute_speed': 2.0}) is True
        assert expression.evaluate({'absolute_speed': 0.5}) is False

    def test_abs_of_variable_starting_with_abs(self):
        expression = parse('abs(absolute_speed) > 1')
        assert expression.evaluate({'absolute_speed': -2.0}) is True
        assert expression.evaluate({'absolute_speed': -0.5}) is False

    def test_variables_with_keyword_prefixes_evaluate(self):
        assert parse('android and order').evaluate({'android': True, 'order': True}) is True
        assert parse('nothing').evaluate({'nothing': True}) is True


class TestFallingConditionEquivalence:
    """The falling `when` string matches the old hand-written _FallingCondition."""

    @staticmethod
    def _old_falling_condition(threshold: float, context: dict[str, Any]) -> bool:
        return context.get('velocity_y', 0.0) > threshold and not context.get('on_ground', True)

    @pytest.mark.parametrize(
        'threshold',
        [BRAVE_ADVENTURER_FALLING_VELOCITY_THRESHOLD, CLOCKWORK_KEEP_FALLING_VELOCITY_THRESHOLD],
    )
    def test_matches_old_logic_around_threshold(self, threshold):
        expression = parse(f'velocity_y > {threshold} and not on_ground')
        velocities = [
            -threshold,
            0.0,
            threshold - 1.0,
            threshold,
            threshold + 0.001,
            threshold + 1.0,
        ]
        for velocity_y, on_ground in product(velocities, [True, False]):
            context = {'velocity_y': velocity_y, 'on_ground': on_ground}
            assert expression.evaluate(context) is self._old_falling_condition(threshold, context)


# --- Coroutine Scheduler ---


class TestBehaviorScheduler:
    """Coroutine behavior execution."""

    def test_start_and_step(self):
        """Behavior runs entry code, then yields per frame."""
        entered = [False]
        stepped = [0]

        def my_behavior(sprite, ctx):
            entered[0] = True
            yield  # frame 1
            stepped[0] += 1
            yield  # frame 2
            stepped[0] += 1

        scheduler = BehaviorScheduler()
        scheduler.start(my_behavior, sprite=None)
        assert entered[0] is True
        assert scheduler.is_running is True

        scheduler.step(variables={}, dt=0.016)
        assert stepped[0] == 1

        scheduler.step(variables={}, dt=0.016)
        assert stepped[0] == 2
        assert scheduler.is_running is False  # generator exhausted

    def test_cancel_stops_behavior(self):
        """Cancelling stops the coroutine."""
        cancelled = [False]

        def my_behavior(sprite, ctx):
            try:
                yield
                yield  # should not reach here after cancel
            except GeneratorExit:
                cancelled[0] = True

        scheduler = BehaviorScheduler()
        scheduler.start(my_behavior, sprite=None)
        scheduler.cancel()
        assert cancelled[0] is True
        assert scheduler.is_running is False

    def test_context_updates_each_step(self):
        """Context variables are updated each frame."""
        seen_values = []

        def my_behavior(sprite, ctx):
            while True:
                seen_values.append(ctx.get('velocity_x', 0.0))
                yield

        scheduler = BehaviorScheduler()
        scheduler.start(my_behavior, sprite=None)

        scheduler.step(variables={'velocity_x': 100.0}, dt=0.016)
        scheduler.step(variables={'velocity_x': 200.0}, dt=0.016)

        # First value is 0.0 from priming (start), then 100.0, 200.0 from steps
        assert seen_values == [0.0, 100.0, 200.0]

    def test_immediate_return_behavior(self):
        """Behavior that never yields completes immediately."""
        ran = [False]

        def instant_behavior(sprite, ctx):
            ran[0] = True
            return
            yield  # make it a generator

        scheduler = BehaviorScheduler()
        scheduler.start(instant_behavior, sprite=None)
        assert ran[0] is True
        assert scheduler.is_running is False


# --- Animation State Machine ---


class TestAnimationStateMachine:
    """State machine transitions and integration."""

    def test_load_from_toml(self):
        """Load transitions from TOML-style data."""
        sprite = FakeSprite()
        state_machine = AnimationStateMachine(sprite)
        state_machine.load_from_toml([
            {'from': 'idle', 'to': 'running', 'when': 'abs(velocity_x) > 0.1'},
            {'from': 'running', 'to': 'idle', 'when': 'abs(velocity_x) <= 0.1'},
        ])
        state_machine.set_state('idle')
        assert state_machine.current_state == 'idle'

    def test_transition_fires(self):
        """Transition fires when condition is met."""
        sprite = FakeSprite()
        state_machine = AnimationStateMachine(sprite)
        state_machine.load_from_toml([
            {'from': 'idle', 'to': 'running', 'when': 'abs(velocity_x) > 0.1'},
        ])
        state_machine.set_state('idle')

        state_machine.evaluate({'velocity_x': 200.0}, dt=0.016)
        assert state_machine.current_state == 'running'
        assert sprite.current_animation == 'running'

    def test_transition_does_not_fire(self):
        """Transition doesn't fire when condition is not met."""
        sprite = FakeSprite()
        state_machine = AnimationStateMachine(sprite)
        state_machine.load_from_toml([
            {'from': 'idle', 'to': 'running', 'when': 'abs(velocity_x) > 0.1'},
        ])
        state_machine.set_state('idle')

        state_machine.evaluate({'velocity_x': 0.0}, dt=0.016)
        assert state_machine.current_state == 'idle'

    def test_code_transition(self):
        """Add transition via code API."""
        sprite = FakeSprite()
        state_machine = AnimationStateMachine(sprite)
        state_machine.add_transition(
            from_state='idle',
            to_state='jumping',
            when='velocity_y < -10.0',
        )
        state_machine.set_state('idle')

        state_machine.evaluate({'velocity_y': -50.0}, dt=0.016)
        assert state_machine.current_state == 'jumping'

    def test_timer_variable(self):
        """Timer accumulates time in current state."""
        sprite = FakeSprite()
        state_machine = AnimationStateMachine(sprite)
        state_machine.add_transition(
            from_state='idle',
            to_state='running',
            when='timer > 2.0',
        )
        state_machine.set_state('idle')

        # 120 frames at 60fps = 2.0 seconds
        for _ in range(120):
            state_machine.evaluate({}, dt=1.0 / 60.0)

        assert state_machine.current_state == 'idle'  # just at 2.0, not over

        state_machine.evaluate({}, dt=1.0 / 60.0)  # one more frame
        assert state_machine.current_state == 'running'

    def test_loop_flags_auto_set(self):
        """State machine auto-sets is_looping from _loop_flags."""
        sprite = FakeSprite()
        state_machine = AnimationStateMachine(sprite)
        state_machine.add_transition(
            from_state='idle',
            to_state='jumping',
            when='velocity_y < -10.0',
        )
        state_machine.set_state('idle')
        assert sprite.is_looping is True  # idle loops

        state_machine.evaluate({'velocity_y': -50.0}, dt=0.016)
        assert sprite.current_animation == 'jumping'
        assert sprite.is_looping is False  # jumping doesn't loop

    def test_on_enter_callback(self):
        """on_enter callback fires when entering a state."""
        sprite = FakeSprite()
        state_machine = AnimationStateMachine(sprite)
        entered = []

        def mark_entered():
            entered.append('entered')

        state_machine.on_enter('running', callback=mark_entered)
        state_machine.add_transition(
            from_state='idle',
            to_state='running',
            when='abs(velocity_x) > 0.1',
        )
        state_machine.set_state('idle')

        state_machine.evaluate({'velocity_x': 200.0}, dt=0.016)
        assert len(entered) == 1

    def test_on_exit_callback(self):
        """on_exit callback fires when leaving a state."""
        sprite = FakeSprite()
        state_machine = AnimationStateMachine(sprite)
        exited = []

        def mark_exited():
            exited.append('exited')

        state_machine.on_exit('idle', callback=mark_exited)
        state_machine.add_transition(
            from_state='idle',
            to_state='running',
            when='abs(velocity_x) > 0.1',
        )
        state_machine.set_state('idle')

        state_machine.evaluate({'velocity_x': 200.0}, dt=0.016)
        assert len(exited) == 1

    def test_behavior_coroutine(self):
        """Behavior coroutine runs entry, per-frame, and exit logic."""
        sprite = FakeSprite()
        state_machine = AnimationStateMachine(sprite)
        events_log: list[str] = []

        @state_machine.behavior('attack')
        def attack_behavior(behavior_sprite, ctx):
            events_log.append('enter')
            yield
            events_log.append('frame')
            yield
            events_log.append('frame')

        state_machine.set_state('attack')

        # Step through the behavior
        state_machine.evaluate({}, dt=0.016)
        state_machine.evaluate({}, dt=0.016)

        assert events_log == ['enter', 'frame', 'frame']


# --- PhysicsBody Context ---


class TestPhysicsBodyContext:
    """PhysicsBody.get_animation_context() integration."""

    def test_base_context(self):
        """PhysicsBody generates base context variables."""
        from glitchygames.physics import PhysicsBody

        body = PhysicsBody()
        body.velocity_x = 100.0
        body.velocity_y = -50.0
        body.on_ground = False

        context = body.get_animation_context()

        assert context['velocity_x'] == 100.0
        assert context['velocity_y'] == -50.0
        assert context['on_ground'] is False
        assert context['in_air'] is True
        assert context['is_moving'] is True
        assert context['is_rising'] is True
        assert context['is_falling'] is False

    def test_stationary_context(self):
        """Stationary body has correct derived booleans."""
        from glitchygames.physics import PhysicsBody

        body = PhysicsBody()
        body.on_ground = True

        context = body.get_animation_context()

        assert context['is_moving'] is False
        assert context['is_falling'] is False
        assert context['is_rising'] is False
        assert context['in_air'] is False
