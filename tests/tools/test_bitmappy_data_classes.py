"""Tests for bitmappy data classes, enums, constants, and simple utility classes."""

import pytest

from glitchygames.bitmappy.constants import (
    AI_BASE_DELAY,
    AI_MAX_CONTEXT_SIZE,
    AI_MAX_DELAY,
    AI_MAX_INPUT_TOKENS,
    AI_MAX_OUTPUT_TOKENS,
    AI_MAX_RETRIES,
    AI_MODEL,
    AI_QUEUE_SIZE,
    AI_TIMEOUT,
    AI_TRAINING_SINGLE_FRAME_EXAMPLE_COUNT,
    AI_VALIDATION_MAX_RETRIES,
    COLOR_QUANTIZATION_GROUP_DISTANCE_THRESHOLD,
    CONTROLLER_ACCEL_JUMP_LEVEL1,
    CONTROLLER_ACCEL_JUMP_LEVEL2,
    CONTROLLER_ACCEL_JUMP_LEVEL3,
    CONTROLLER_ACCEL_LEVEL1_TIME,
    CONTROLLER_ACCEL_LEVEL2_TIME,
    CONTROLLER_ACCEL_LEVEL3_TIME,
    DEBUG_LOG_FIRST_N_PIXELS,
    HAT_INPUT_MAGNITUDE_THRESHOLD,
    LARGE_SPRITE_DIMENSION,
    MAGENTA_TRANSPARENT,
    MAX_COLOR_VALUE,
    MAX_COLORS_FOR_AI_TRAINING,
    MAX_PIXELS_ACROSS,
    MAX_PIXELS_TALL,
    MIN_COLOR_VALUE,
    MIN_FILM_STRIPS_FOR_PANEL_POSITIONING,
    MIN_PIXEL_DISPLAY_SIZE,
    MIN_PIXELS_ACROSS,
    MIN_PIXELS_TALL,
    MODEL_DOWNLOAD_TIME_THRESHOLD_SECONDS,
    PIXEL_CHANGE_DEBOUNCE_SECONDS,
    PROGRESS_LOG_MIN_HEIGHT,
    SPRITE_ASPECT_RATIO_TOLERANCE,
    TRANSPARENT_GLYPH,
)
from glitchygames.bitmappy.models import (
    AIRequest,
    AIRequestState,
    AIResponse,
    GGUnhandledMenuItemError,
    MockEvent,
)


class TestConstants:
    """Test that all bitmappy constants have expected values."""

    def test_magenta_transparent_value(self):
        """Test magenta transparency color constant."""
        assert MAGENTA_TRANSPARENT == (255, 0, 255)

    def test_transparent_glyph_is_block_character(self):
        """Test transparent glyph is the block character."""
        assert TRANSPARENT_GLYPH == '\u2588'

    def test_pixel_dimension_bounds(self):
        """Test pixel dimension constants have valid ranges."""
        assert MAX_PIXELS_ACROSS == 64
        assert MIN_PIXELS_ACROSS == 1
        assert MAX_PIXELS_TALL == 64
        assert MIN_PIXELS_TALL == 1
        assert MIN_PIXELS_ACROSS <= MAX_PIXELS_ACROSS
        assert MIN_PIXELS_TALL <= MAX_PIXELS_TALL

    def test_color_value_bounds(self):
        """Test color value constants have valid ranges."""
        assert MIN_COLOR_VALUE == 0
        assert MAX_COLOR_VALUE == 255
        assert MIN_COLOR_VALUE < MAX_COLOR_VALUE

    def test_large_sprite_dimension(self):
        """Test large sprite threshold is reasonable."""
        assert LARGE_SPRITE_DIMENSION == 128
        assert LARGE_SPRITE_DIMENSION > MAX_PIXELS_ACROSS

    def test_min_pixel_display_size(self):
        """Test minimum pixel display size for large sprites."""
        assert MIN_PIXEL_DISPLAY_SIZE == 2

    def test_ai_constants(self):
        """Test AI-related constants have expected values."""
        assert AI_TIMEOUT == 600
        assert AI_QUEUE_SIZE == 10
        assert AI_MAX_CONTEXT_SIZE == 65536
        assert AI_MAX_INPUT_TOKENS == 8192
        assert AI_MAX_OUTPUT_TOKENS == 64000
        assert AI_MAX_RETRIES == 5
        assert pytest.approx(1.0) == AI_BASE_DELAY
        assert pytest.approx(60.0) == AI_MAX_DELAY
        assert AI_VALIDATION_MAX_RETRIES == 2
        assert AI_TRAINING_SINGLE_FRAME_EXAMPLE_COUNT == 2
        assert MAX_COLORS_FOR_AI_TRAINING == 64

    def test_ai_model_is_string(self):
        """Test AI model identifier is a non-empty string."""
        assert isinstance(AI_MODEL, str)
        assert len(AI_MODEL) > 0

    def test_controller_acceleration_constants(self):
        """Test controller acceleration timing thresholds are ordered."""
        assert pytest.approx(0.8) == CONTROLLER_ACCEL_LEVEL1_TIME
        assert pytest.approx(1.5) == CONTROLLER_ACCEL_LEVEL2_TIME
        assert pytest.approx(2.5) == CONTROLLER_ACCEL_LEVEL3_TIME
        assert CONTROLLER_ACCEL_LEVEL1_TIME < CONTROLLER_ACCEL_LEVEL2_TIME
        assert CONTROLLER_ACCEL_LEVEL2_TIME < CONTROLLER_ACCEL_LEVEL3_TIME

    def test_controller_acceleration_jumps_are_ordered(self):
        """Test controller acceleration jump sizes increase with levels."""
        assert CONTROLLER_ACCEL_JUMP_LEVEL1 == 2
        assert CONTROLLER_ACCEL_JUMP_LEVEL2 == 4
        assert CONTROLLER_ACCEL_JUMP_LEVEL3 == 8
        assert CONTROLLER_ACCEL_JUMP_LEVEL1 < CONTROLLER_ACCEL_JUMP_LEVEL2
        assert CONTROLLER_ACCEL_JUMP_LEVEL2 < CONTROLLER_ACCEL_JUMP_LEVEL3

    def test_hat_input_magnitude_threshold(self):
        """Test joystick hat dead zone threshold."""
        assert pytest.approx(0.5) == HAT_INPUT_MAGNITUDE_THRESHOLD

    def test_debug_constants(self):
        """Test debugging constants."""
        assert DEBUG_LOG_FIRST_N_PIXELS == 5
        assert PROGRESS_LOG_MIN_HEIGHT == 32

    def test_pixel_change_debounce(self):
        """Test debounce timing for auto-submit."""
        assert pytest.approx(0.1) == PIXEL_CHANGE_DEBOUNCE_SECONDS

    def test_model_download_time_threshold(self):
        """Test AI model download time threshold."""
        assert MODEL_DOWNLOAD_TIME_THRESHOLD_SECONDS == 60

    def test_sprite_aspect_ratio_tolerance(self):
        """Test aspect ratio tolerance for AI training matching."""
        assert pytest.approx(0.2) == SPRITE_ASPECT_RATIO_TOLERANCE

    def test_color_quantization_threshold(self):
        """Test color quantization group distance threshold."""
        assert COLOR_QUANTIZATION_GROUP_DISTANCE_THRESHOLD == 1000

    def test_min_film_strips_for_panel_positioning(self):
        """Test minimum film strips before AI panel positioning."""
        assert MIN_FILM_STRIPS_FOR_PANEL_POSITIONING == 2


class TestMockEvent:
    """Test the MockEvent Pydantic model."""

    def test_mock_event_creation(self):
        """Test creating a MockEvent with text."""
        event = MockEvent(text='test.toml')
        assert event.text == 'test.toml'

    def test_mock_event_with_empty_text(self):
        """Test MockEvent with empty text string."""
        event = MockEvent(text='')
        assert not event.text

    def test_mock_event_with_path(self):
        """Test MockEvent with a file path as text."""
        event = MockEvent(text='/path/to/sprite.toml')
        assert event.text == '/path/to/sprite.toml'

    def test_mock_event_requires_text(self):
        """Test MockEvent raises error without text field."""
        with pytest.raises(ValueError, match='validation error'):
            MockEvent()  # type: ignore[missing-argument]


class TestAIRequest:
    """Test the AIRequest dataclass."""

    def test_ai_request_creation(self):
        """Test creating an AIRequest with all fields."""
        messages = [{'role': 'user', 'content': 'Create a 8x8 slime'}]
        request = AIRequest(prompt='Create a slime', request_id='req_001', messages=messages)
        assert request.prompt == 'Create a slime'
        assert request.request_id == 'req_001'
        assert len(request.messages) == 1
        assert request.messages[0]['role'] == 'user'

    def test_ai_request_with_multiple_messages(self):
        """Test AIRequest with a multi-message conversation."""
        messages = [
            {'role': 'system', 'content': 'You are a sprite generator.'},
            {'role': 'user', 'content': 'Create a mushroom sprite'},
        ]
        request = AIRequest(prompt='Create a mushroom', request_id='req_002', messages=messages)
        assert len(request.messages) == 2

    def test_ai_request_with_empty_messages(self):
        """Test AIRequest with empty messages list."""
        request = AIRequest(prompt='test', request_id='req_003', messages=[])
        assert request.messages == []


class TestAIResponse:
    """Test the AIResponse dataclass."""

    def test_ai_response_with_content(self):
        """Test AIResponse with valid content."""
        response = AIResponse(content='[sprite]\nname = "test"')
        assert response.content == '[sprite]\nname = "test"'
        assert response.error is None

    def test_ai_response_with_error(self):
        """Test AIResponse with an error."""
        response = AIResponse(content=None, error='API timeout')
        assert response.content is None
        assert response.error == 'API timeout'

    def test_ai_response_default_error_is_none(self):
        """Test AIResponse defaults error to None."""
        response = AIResponse(content='some content')
        assert response.error is None

    def test_ai_response_with_both_content_and_error(self):
        """Test AIResponse can hold both content and error."""
        response = AIResponse(content='partial data', error='truncated response')
        assert response.content == 'partial data'
        assert response.error == 'truncated response'


class TestAIRequestState:
    """Test the AIRequestState dataclass."""

    def test_ai_request_state_creation(self):
        """Test creating an AIRequestState with all defaults."""
        state = AIRequestState(original_prompt='Create a cat sprite')
        assert state.original_prompt == 'Create a cat sprite'
        assert state.retry_count == 0
        assert state.last_error is None
        assert state.training_examples is None
        assert state.conversation_history is None
        assert state.last_sprite_content is None

    def test_ai_request_state_with_retry(self):
        """Test AIRequestState tracking retry state."""
        state = AIRequestState(
            original_prompt='Create a sprite',
            retry_count=3,
            last_error='Missing [sprite] section',
        )
        assert state.retry_count == 3
        assert state.last_error == 'Missing [sprite] section'

    def test_ai_request_state_with_conversation_history(self):
        """Test AIRequestState with multi-turn conversation history."""
        history = [
            {'role': 'user', 'content': 'Create a cat'},
            {'role': 'assistant', 'content': '[sprite]\nname = "cat"'},
            {'role': 'user', 'content': 'Make it bigger'},
        ]
        state = AIRequestState(
            original_prompt='Create a cat',
            conversation_history=history,
            last_sprite_content='[sprite]\nname = "cat"',
        )
        assert state.conversation_history is not None
        assert len(state.conversation_history) == 3
        assert state.last_sprite_content is not None

    def test_ai_request_state_with_training_examples(self):
        """Test AIRequestState with training examples."""
        examples = [{'name': 'slime', 'pixels': '##\n##'}]
        state = AIRequestState(
            original_prompt='Create a slime',
            training_examples=examples,
        )
        assert state.training_examples is not None
        assert len(state.training_examples) == 1


class TestGGUnhandledMenuItemError:
    """Test the GGUnhandledMenuItemError exception class."""

    def test_exception_is_exception_subclass(self):
        """Test GGUnhandledMenuItemError inherits from Exception."""
        assert issubclass(GGUnhandledMenuItemError, Exception)

    def test_exception_can_be_raised(self):
        """Test GGUnhandledMenuItemError can be raised and caught.

        Raises:
            GGUnhandledMenuItemError: Raised intentionally to test the exception class.

        """
        with pytest.raises(GGUnhandledMenuItemError, match='Unknown menu item'):
            raise GGUnhandledMenuItemError('Unknown menu item')

    def test_exception_message_preserved(self):
        """Test exception message is preserved."""
        error = GGUnhandledMenuItemError('File menu not handled')
        assert str(error) == 'File menu not handled'

    def test_exception_with_empty_message(self):
        """Test exception with empty message."""
        error = GGUnhandledMenuItemError('')
        assert not str(error)
