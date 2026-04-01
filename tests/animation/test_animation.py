"""Tests for expression parser, coroutine scheduler, and animation state machine."""

from dataclasses import dataclass, field

import pytest

from glitchygames.animation.expressions import (
    parse,
)
from glitchygames.animation.scheduler import BehaviorScheduler
from glitchygames.animation.state_machine import AnimationStateMachine

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
