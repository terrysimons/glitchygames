"""Property-based tests using Hypothesis.

Tests mathematical invariants and properties of the engine's pure logic:
Speed arithmetic, movement scaling, palette roundtrips, and adaptive clamping.
"""

import math
from itertools import starmap

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from pygame import Color

from glitchygames.color.palette import ColorPalette, PaletteUtility
from glitchygames.movement.horizontal import Horizontal
from glitchygames.movement.speed import Speed
from glitchygames.movement.vertical import Vertical
from glitchygames.performance.adaptive_clamping import AdaptiveClamping

# ---------------------------------------------------------------------------
# Reusable strategies
# ---------------------------------------------------------------------------

# Finite floats that won't overflow when multiplied together
reasonable_floats = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
positive_floats = st.floats(min_value=1e-6, max_value=1e6, allow_nan=False, allow_infinity=False)
nonzero_floats = st.floats(
    min_value=-1e6,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
).filter(lambda x: abs(x) > 1e-9)
rgb_values = st.integers(min_value=0, max_value=255)
alpha_values = st.integers(min_value=0, max_value=255)
dt_values = st.floats(min_value=0.001, max_value=0.1, allow_nan=False, allow_infinity=False)


# ===================================================================
# Speed arithmetic properties
# ===================================================================


class TestSpeedAddition:
    """Properties of Speed addition."""

    @given(
        x1=reasonable_floats,
        y1=reasonable_floats,
        x2=reasonable_floats,
        y2=reasonable_floats,
    )
    def test_addition_is_commutative(self, x1, y1, x2, y2):
        """A + b == b + a for Speed objects."""
        speed_a = Speed(x1, y1)
        speed_b = Speed(x2, y2)
        result_ab = speed_a + speed_b
        result_ba = speed_b + speed_a
        assert math.isclose(result_ab.x, result_ba.x, rel_tol=1e-9, abs_tol=1e-12)
        assert math.isclose(result_ab.y, result_ba.y, rel_tol=1e-9, abs_tol=1e-12)

    @given(x=reasonable_floats, y=reasonable_floats)
    def test_adding_zero_is_identity(self, x, y):
        """A + Speed(0, 0) == a."""
        speed = Speed(x, y)
        result = speed + Speed(0, 0)
        assert math.isclose(result.x, x, rel_tol=1e-9, abs_tol=1e-12)
        assert math.isclose(result.y, y, rel_tol=1e-9, abs_tol=1e-12)

    @given(
        speed_a=st.builds(Speed, x=reasonable_floats, y=reasonable_floats),
        speed_b=st.builds(Speed, x=reasonable_floats, y=reasonable_floats),
        speed_c=st.builds(Speed, x=reasonable_floats, y=reasonable_floats),
    )
    def test_addition_is_associative(self, speed_a, speed_b, speed_c):
        """(a + b) + c == a + (b + c)."""
        left = (speed_a + speed_b) + speed_c
        right = speed_a + (speed_b + speed_c)
        assert math.isclose(left.x, right.x, rel_tol=1e-9, abs_tol=1e-12)
        assert math.isclose(left.y, right.y, rel_tol=1e-9, abs_tol=1e-12)


class TestSpeedSubtraction:
    """Properties of Speed subtraction."""

    @given(x=reasonable_floats, y=reasonable_floats)
    def test_subtracting_self_gives_zero(self, x, y):
        """A - a == Speed(0, 0)."""
        speed = Speed(x, y)
        result = speed - Speed(x, y)
        assert math.isclose(result.x, 0.0, abs_tol=1e-12)
        assert math.isclose(result.y, 0.0, abs_tol=1e-12)

    @given(
        x1=reasonable_floats,
        y1=reasonable_floats,
        x2=reasonable_floats,
        y2=reasonable_floats,
    )
    def test_addition_then_subtraction_roundtrips(self, x1, y1, x2, y2):
        """(a + b) - b == a."""
        speed_a = Speed(x1, y1)
        speed_b = Speed(x2, y2)
        result = (speed_a + speed_b) - speed_b
        assert math.isclose(result.x, x1, rel_tol=1e-9, abs_tol=1e-9)
        assert math.isclose(result.y, y1, rel_tol=1e-9, abs_tol=1e-9)


class TestSpeedMultiplication:
    """Properties of Speed multiplication."""

    @given(x=reasonable_floats, y=reasonable_floats)
    def test_multiplying_by_one_is_identity(self, x, y):
        """A * 1 == a."""
        speed = Speed(x, y)
        result = speed * 1.0
        assert math.isclose(result.x, x, rel_tol=1e-9, abs_tol=1e-12)
        assert math.isclose(result.y, y, rel_tol=1e-9, abs_tol=1e-12)

    @given(x=reasonable_floats, y=reasonable_floats)
    def test_multiplying_by_zero_gives_zero(self, x, y):
        """A * 0 == Speed(0, 0)."""
        speed = Speed(x, y)
        result = speed * 0.0
        assert result.x == 0.0
        assert result.y == 0.0

    @given(
        x=st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
        y=st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
        scalar1=st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
        scalar2=st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
    )
    def test_multiplication_is_associative(self, x, y, scalar1, scalar2):
        """(a * s1) * s2 == a * (s1 * s2)."""
        speed = Speed(x, y)
        left = (speed * scalar1) * scalar2
        right = speed * (scalar1 * scalar2)
        assert math.isclose(left.x, right.x, rel_tol=1e-6, abs_tol=1e-9)
        assert math.isclose(left.y, right.y, rel_tol=1e-6, abs_tol=1e-9)


class TestSpeedDivision:
    """Properties of Speed division."""

    @given(x=reasonable_floats, y=reasonable_floats, scalar=nonzero_floats)
    def test_division_inverts_multiplication(self, x, y, scalar):
        """(a * s) / s == a for nonzero s."""
        speed = Speed(x, y)
        result = (speed * scalar) / scalar
        assert math.isclose(result.x, x, rel_tol=1e-6, abs_tol=1e-9)
        assert math.isclose(result.y, y, rel_tol=1e-6, abs_tol=1e-9)

    @given(x=reasonable_floats, y=reasonable_floats)
    def test_division_by_zero_raises(self, x, y):
        """Dividing by zero raises ZeroDivisionError."""
        speed = Speed(x, y)
        with pytest.raises(ZeroDivisionError):
            _ = speed / 0

    @given(x=reasonable_floats, y=reasonable_floats)
    def test_modulo_by_zero_raises(self, x, y):
        """Modulo by zero raises ZeroDivisionError."""
        speed = Speed(x, y)
        with pytest.raises(ZeroDivisionError):
            _ = speed % 0


class TestSpeedNegation:
    """Properties of Speed negation."""

    @given(x=reasonable_floats, y=reasonable_floats)
    def test_double_negation_is_identity(self, x, y):
        """-(-a) == a."""
        speed = Speed(x, y)
        result = -(-speed)
        assert math.isclose(result.x, x, rel_tol=1e-9, abs_tol=1e-12)
        assert math.isclose(result.y, y, rel_tol=1e-9, abs_tol=1e-12)

    @given(x=reasonable_floats, y=reasonable_floats)
    def test_negation_plus_original_is_zero(self, x, y):
        """A + (-a) == Speed(0, 0)."""
        speed = Speed(x, y)
        result = speed + (-speed)
        assert math.isclose(result.x, 0.0, abs_tol=1e-12)
        assert math.isclose(result.y, 0.0, abs_tol=1e-12)

    @given(x=reasonable_floats, y=reasonable_floats)
    def test_negation_preserves_increment(self, x, y):
        """Negation should preserve the increment value."""
        increment = 0.5
        speed = Speed(x, y, increment=increment)
        negated = -speed
        assert negated.increment == increment


class TestSpeedApplyDt:
    """Properties of delta time application."""

    @given(x=reasonable_floats, y=reasonable_floats, dt=dt_values)
    def test_apply_dt_scales_linearly(self, x, y, dt):
        """apply_dt(dt) == Speed(x*dt, y*dt)."""
        speed = Speed(x, y)
        result = speed.apply_dt(dt)
        assert math.isclose(result.x, x * dt, rel_tol=1e-9, abs_tol=1e-12)
        assert math.isclose(result.y, y * dt, rel_tol=1e-9, abs_tol=1e-12)

    @given(
        x=reasonable_floats,
        y=reasonable_floats,
        dt1=dt_values,
        dt2=dt_values,
    )
    def test_apply_dt_distributes_over_addition(self, x, y, dt1, dt2):
        """apply_dt(dt1 + dt2) == apply_dt(dt1) + apply_dt(dt2) (approximately)."""
        speed = Speed(x, y)
        combined = speed.apply_dt(dt1 + dt2)
        separate = speed.apply_dt(dt1) + speed.apply_dt(dt2)
        assert math.isclose(combined.x, separate.x, rel_tol=1e-9, abs_tol=1e-9)
        assert math.isclose(combined.y, separate.y, rel_tol=1e-9, abs_tol=1e-9)

    @given(x=reasonable_floats, y=reasonable_floats)
    def test_apply_dt_preserves_increment(self, x, y):
        """apply_dt should preserve the increment value."""
        increment = 0.3
        speed = Speed(x, y, increment=increment)
        result = speed.apply_dt(0.016)
        assert result.increment == increment


class TestSpeedUpPreservesSign:
    """speed_up_horizontal/vertical preserve the sign of the speed component."""

    @given(
        x=st.floats(min_value=0.1, max_value=1e6, allow_nan=False, allow_infinity=False),
        y=st.floats(min_value=0.1, max_value=1e6, allow_nan=False, allow_infinity=False),
        increment=positive_floats,
    )
    def test_speed_up_increases_positive_components(self, x, y, increment):
        """Speeding up positive components makes them larger."""
        speed = Speed(x, y, increment=increment)
        old_x, old_y = speed.x, speed.y
        speed.speed_up()
        assert speed.x > old_x
        assert speed.y > old_y

    @given(
        x=st.floats(min_value=-1e6, max_value=-0.1, allow_nan=False, allow_infinity=False),
        y=st.floats(min_value=-1e6, max_value=-0.1, allow_nan=False, allow_infinity=False),
        increment=positive_floats,
    )
    def test_speed_up_increases_magnitude_of_negative_components(self, x, y, increment):
        """Speeding up negative components makes their absolute value larger."""
        speed = Speed(x, y, increment=increment)
        old_abs_x, old_abs_y = abs(speed.x), abs(speed.y)
        speed.speed_up()
        assert abs(speed.x) > old_abs_x
        assert abs(speed.y) > old_abs_y

    @given(
        x=reasonable_floats,
        y=reasonable_floats,
        increment=positive_floats,
    )
    def test_speed_up_preserves_sign(self, x, y, increment):
        """speed_up never flips the sign of a component (unless it was zero)."""
        assume(x != 0.0)
        assume(y != 0.0)
        speed = Speed(x, y, increment=increment)
        original_x_sign = math.copysign(1, speed.x)
        original_y_sign = math.copysign(1, speed.y)
        speed.speed_up()
        assert math.copysign(1, speed.x) == original_x_sign
        assert math.copysign(1, speed.y) == original_y_sign


# ===================================================================
# Movement properties
# ===================================================================


class TestHorizontalMovement:
    """Properties of horizontal movement with delta time."""

    @given(
        speed_x=positive_floats,
        dt=dt_values,
    )
    def test_movement_scales_linearly_with_dt(self, speed_x, dt):
        """Double the dt, double the movement."""
        speed = Speed(speed_x, 0)
        horizontal = Horizontal(speed)
        movement_1 = horizontal.get_movement_with_dt(dt)
        movement_2 = horizontal.get_movement_with_dt(dt * 2)
        assert math.isclose(movement_2, movement_1 * 2, rel_tol=1e-9, abs_tol=1e-12)

    @given(speed_x=positive_floats)
    def test_zero_dt_means_no_movement(self, speed_x):
        """Zero delta time means zero movement."""
        speed = Speed(speed_x, 0)
        horizontal = Horizontal(speed)
        assert horizontal.get_movement_with_dt(0.0) == 0.0

    @given(speed_x=positive_floats, dt=dt_values)
    def test_left_reverses_direction(self, speed_x, dt):
        """After calling left(), movement should be negative."""
        speed = Speed(speed_x, 0)
        horizontal = Horizontal(speed)
        horizontal.left()
        movement = horizontal.get_movement_with_dt(dt)
        assert movement < 0

    @given(speed_x=positive_floats, dt=dt_values)
    def test_stop_means_no_movement(self, speed_x, dt):
        """After calling stop(), movement should be zero."""
        speed = Speed(speed_x, 0)
        horizontal = Horizontal(speed)
        horizontal.stop()
        assert horizontal.get_movement_with_dt(dt) == 0.0


class TestVerticalMovement:
    """Properties of vertical movement with delta time."""

    @given(
        speed_y=positive_floats,
        dt=dt_values,
    )
    def test_movement_scales_linearly_with_dt(self, speed_y, dt):
        """Double the dt, double the movement."""
        speed = Speed(0, speed_y)
        vertical = Vertical(speed)
        movement_1 = vertical.get_movement_with_dt(dt)
        movement_2 = vertical.get_movement_with_dt(dt * 2)
        assert math.isclose(movement_2, movement_1 * 2, rel_tol=1e-9, abs_tol=1e-12)

    @given(speed_y=positive_floats, dt=dt_values)
    def test_up_reverses_direction(self, speed_y, dt):
        """After calling up(), movement should be negative."""
        speed = Speed(0, speed_y)
        vertical = Vertical(speed)
        vertical.up()
        movement = vertical.get_movement_with_dt(dt)
        assert movement < 0

    @given(speed_y=positive_floats, dt=dt_values)
    def test_stop_means_no_movement(self, speed_y, dt):
        """After calling stop(), movement should be zero."""
        speed = Speed(0, speed_y)
        vertical = Vertical(speed)
        vertical.stop()
        assert vertical.get_movement_with_dt(dt) == 0.0


# ===================================================================
# Color palette roundtrip properties
# ===================================================================


class TestPaletteRoundtrip:
    """Palette serialization/deserialization should be lossless."""

    @given(
        colors=st.lists(
            st.tuples(rgb_values, rgb_values, rgb_values, alpha_values),
            min_size=1,
            max_size=50,
        ),
    )
    def test_create_then_load_roundtrips(self, colors):
        """create_palette_data -> load_palette_from_config preserves colors."""
        pygame_colors = list(starmap(Color, colors))
        config = PaletteUtility.create_palette_data(pygame_colors)
        loaded_colors = PaletteUtility.load_palette_from_config(config)
        assert len(loaded_colors) == len(pygame_colors)
        for original, loaded in zip(pygame_colors, loaded_colors):
            assert original.r == loaded.r
            assert original.g == loaded.g
            assert original.b == loaded.b
            assert original.a == loaded.a

    @given(
        colors=st.lists(
            st.tuples(rgb_values, rgb_values, rgb_values, alpha_values),
            min_size=1,
            max_size=50,
        ),
    )
    def test_double_roundtrip_is_stable(self, colors):
        """Two roundtrips should give the same result as one."""
        pygame_colors = list(starmap(Color, colors))
        config1 = PaletteUtility.create_palette_data(pygame_colors)
        loaded1 = PaletteUtility.load_palette_from_config(config1)
        config2 = PaletteUtility.create_palette_data(loaded1)
        loaded2 = PaletteUtility.load_palette_from_config(config2)
        for color1, color2 in zip(loaded1, loaded2):
            assert color1.r == color2.r
            assert color1.g == color2.g
            assert color1.b == color2.b
            assert color1.a == color2.a


class TestColorPaletteGetSet:
    """ColorPalette get/set roundtrip properties."""

    @given(
        index=st.integers(min_value=0, max_value=49),
        r=rgb_values,
        g=rgb_values,
        b=rgb_values,
    )
    def test_set_then_get_roundtrips(self, index, r, g, b):
        """Setting a color at an index and getting it back should match."""
        # Start with enough colors so the index is valid
        initial_colors = [(0, 0, 0)] * (index + 2)
        palette = ColorPalette(colors=initial_colors)
        new_color = (r, g, b)
        palette.set_color(index, new_color)
        assert palette.get_color(index) == new_color

    @given(
        colors=st.lists(
            st.tuples(rgb_values, rgb_values, rgb_values),
            min_size=1,
            max_size=20,
        ),
    )
    def test_palette_size_matches_color_count(self, colors):
        """The palette's internal size should reflect the number of colors."""
        palette = ColorPalette(colors=list(colors))
        # _size is len(colors) - 1 per the implementation
        assert palette._size == len(colors) - 1

    def test_empty_palette_returns_magenta(self):
        """An empty palette should return magenta as fallback."""
        palette = ColorPalette(colors=[])
        assert palette.get_color(0) == (255, 0, 255)


# ===================================================================
# Adaptive clamping properties
# ===================================================================


class TestAdaptiveClampingProperties:
    """Properties of the AdaptiveClamping dt adjustment."""

    @pytest.fixture(autouse=True)
    def fresh_clamping(self):
        """Reset the singleton for each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.clamping = AdaptiveClamping()
        yield
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False

    @given(dt=dt_values)
    def test_get_adaptive_dt_returns_positive(self, dt):
        """Adjusted dt should always be positive for positive input."""
        # Need a fresh instance each hypothesis example since state accumulates
        self.clamping._dt_history = []
        result = self.clamping.get_adaptive_dt(dt)
        assert result > 0

    @given(
        dt=st.floats(min_value=0.001, max_value=0.1, allow_nan=False, allow_infinity=False),
    )
    def test_with_insufficient_history_returns_raw_dt(self, dt):
        """With < 10 history samples, raw dt is returned unchanged."""
        self.clamping._dt_history = []
        result = self.clamping.get_adaptive_dt(dt)
        # First call should return raw dt (only 1 sample in history)
        assert result == dt

    @given(
        dts=st.lists(
            st.floats(min_value=0.001, max_value=0.1, allow_nan=False, allow_infinity=False),
            min_size=15,
            max_size=30,
        ),
    )
    def test_adjusted_dt_blends_toward_target(self, dts):
        """After enough history, adjusted dt should be between raw dt and 1/60."""
        self.clamping._dt_history = []
        target_dt = 1.0 / 60.0
        # Feed in all but the last dt to build history
        for dt in dts[:-1]:
            self.clamping.get_adaptive_dt(dt)
        # The last dt should be blended toward the target
        last_dt = dts[-1]
        result = self.clamping.get_adaptive_dt(last_dt)
        # Result should be between the raw dt and target (or at least close)
        lower = min(last_dt, target_dt)
        upper = max(last_dt, target_dt)
        # Allow a small tolerance for floating point
        assert lower - 0.001 <= result <= upper + 0.001

    @given(dt=dt_values)
    @settings(max_examples=20)
    def test_dt_history_never_exceeds_window(self, dt):
        """History should never exceed DT_HISTORY_WINDOW (60)."""
        self.clamping._dt_history = []
        for _ in range(100):
            self.clamping.get_adaptive_dt(dt)
        assert len(self.clamping._dt_history) <= 60


class TestTrimPercentValidation:
    """Properties of set_trim_percent validation."""

    @pytest.fixture(autouse=True)
    def fresh_clamping(self):
        """Reset the singleton for each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.clamping = AdaptiveClamping()
        yield
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False

    @given(
        percent=st.floats(min_value=0.0, max_value=49.9, allow_nan=False, allow_infinity=False),
    )
    def test_valid_trim_percent_is_stored(self, percent):
        """Valid trim percentages in [0, 49.9] should be stored as-is."""
        self.clamping.set_trim_percent(percent)
        assert math.isclose(self.clamping._trim_percent, percent, rel_tol=1e-9)

    @given(
        percent=st.floats(min_value=50.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    def test_trim_percent_at_or_above_50_is_clamped(self, percent):
        """Trim percent >= 50 should be clamped to 49.9."""
        self.clamping.set_trim_percent(percent)
        assert self.clamping._trim_percent == 49.9

    @given(
        percent=st.floats(min_value=-1e6, max_value=-0.001, allow_nan=False, allow_infinity=False),
    )
    def test_negative_trim_percent_is_clamped_to_zero(self, percent):
        """Negative trim percent should be clamped to 0."""
        self.clamping.set_trim_percent(percent)
        assert self.clamping._trim_percent == 0.0


class TestPerformanceGrading:
    """Properties of performance grade calculations."""

    @pytest.fixture(autouse=True)
    def fresh_clamping(self):
        """Reset the singleton for each test."""
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False
        self.clamping = AdaptiveClamping()
        yield
        AdaptiveClamping._instance = None
        AdaptiveClamping._initialized = False

    @given(
        fps=st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False),
    )
    def test_grade_is_always_a_valid_string(self, fps):
        """Performance grade should always return a non-empty string."""
        grade = self.clamping._calculate_performance_grade([fps])
        assert isinstance(grade, str)
        assert len(grade) > 0

    def test_empty_fps_list_gives_na(self):
        """Empty FPS list should return N/A."""
        grade = self.clamping._calculate_performance_grade([])
        assert grade == 'N/A'

    @given(
        fps=st.floats(min_value=120.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    )
    def test_high_fps_gets_excellent_grade(self, fps):
        """FPS >= 120 should get A+ grade (unlimited target)."""
        self.clamping._target_fps = 0.0
        grade = self.clamping._calculate_performance_grade([fps])
        assert 'A+' in grade

    @given(
        target=st.floats(min_value=30.0, max_value=240.0, allow_nan=False, allow_infinity=False),
    )
    def test_meeting_target_gets_excellent(self, target):
        """FPS at or above target should get A+ grade."""
        self.clamping._target_fps = target
        # Use exactly target FPS
        grade = self.clamping._calculate_performance_grade([target])
        assert 'A+' in grade

    @given(
        fps=st.floats(min_value=0.1, max_value=19.9, allow_nan=False, allow_infinity=False),
    )
    def test_very_low_fps_gets_poor_grade(self, fps):
        """FPS < 20 should get F grade (unlimited target)."""
        self.clamping._target_fps = 0.0
        grade = self.clamping._calculate_performance_grade([fps])
        assert 'F' in grade


# ===================================================================
# Speed modulo properties
# ===================================================================


class TestSpeedModulo:
    """Properties of Speed modulo operation."""

    @given(
        x=reasonable_floats,
        y=reasonable_floats,
        modulus=st.floats(min_value=0.1, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    def test_modulo_result_is_bounded(self, x, y, modulus):
        """Result of modulo should be in [0, modulus)."""
        speed = Speed(x, y)
        result = speed % modulus
        # Python modulo always returns non-negative for positive modulus
        assert 0 <= result.x < modulus + 1e-9
        assert 0 <= result.y < modulus + 1e-9


# ===================================================================
# Speed in-place multiplication
# ===================================================================


class TestSpeedInPlaceMultiplication:
    """Properties of Speed *= operator."""

    @given(x=reasonable_floats, y=reasonable_floats, scalar=reasonable_floats)
    def test_imul_matches_mul(self, x, y, scalar):
        """A *= s should give the same result as a * s."""
        speed_mul = Speed(x, y) * scalar
        speed_imul = Speed(x, y)
        speed_imul *= scalar
        assert math.isclose(speed_mul.x, speed_imul.x, rel_tol=1e-9, abs_tol=1e-12)
        assert math.isclose(speed_mul.y, speed_imul.y, rel_tol=1e-9, abs_tol=1e-12)

    @given(x=reasonable_floats, y=reasonable_floats, scalar=reasonable_floats)
    def test_imul_returns_same_object(self, x, y, scalar):
        """In-place multiplication should return the same object (not a copy)."""
        speed = Speed(x, y)
        original_id = id(speed)
        speed *= scalar
        assert id(speed) == original_id
