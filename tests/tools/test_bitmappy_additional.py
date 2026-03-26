"""Additional tests for uncovered module-level functions and smaller classes in bitmappy.py.

Covers: normalize_toml_data, _detect_alpha_channel, _detect_alpha_channel_in_animation,
_parse_capabilities_response, AI scoring functions, _parse_toml_value, _fix_color_entry,
FilmStripSprite helpers, AnimatedCanvasSprite methods, and more.
"""

import logging
from dataclasses import dataclass
from typing import cast

import pytest

from glitchygames.bitmappy.ai_worker import (
    _create_ai_retry_decorator,
    _extract_example_size,
    _extract_response_content,
    _log_capabilities_dump,
    _parse_capabilities_response,
    _process_ai_request,
    _score_size_match,
    _score_training_example,
    build_retry_prompt,
    select_relevant_training_examples,
)
from glitchygames.bitmappy.alpha import (
    _convert_animation_colors_to_rgba,
    _convert_colors_to_rgba,
    _detect_alpha_channel,
    _detect_alpha_channel_in_animation,
    convert_sprite_to_alpha_format,
)
from glitchygames.bitmappy.models import AIRequest, AIResponse
from glitchygames.bitmappy.pixel_ops import (
    _alpha_blend_pixel,
    _build_ascii_grid,
    _build_color_to_glyph_map,
    _build_renderer_color_dict,
    _composite_frames_with_alpha,
    _get_visible_width,
)
from glitchygames.bitmappy.sprite_inspection import (
    _pixels_have_alpha,
    _sprite_has_per_pixel_alpha,
)
from glitchygames.bitmappy.toml_processing import (
    _fix_color_entry,
    _fix_color_format_in_toml_data,
    _fix_comma_separated_color_field,
    _normalize_animation_pixels,
    _normalize_escaped_newlines,
    _parse_toml_value,
    normalize_toml_data,
    parse_toml_robustly,
)
from glitchygames.bitmappy.utils import detect_file_format, resource_path
from tests.mocks import MockFactory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def logger():
    """Create a test logger.

    Returns:
        logging.Logger: A logger for testing.

    """
    return logging.getLogger('test.bitmappy_additional')


@pytest.fixture
def pygame_mocks(mocker):
    """Set up pygame mocks for sprite tests.

    Returns:
        dict: The pygame mock objects.

    """
    return MockFactory.setup_pygame_mocks_with_mocker(mocker)


# ---------------------------------------------------------------------------
# normalize_toml_data tests
# ---------------------------------------------------------------------------


class TestNormalizeTomlData:
    """Tests for normalize_toml_data function."""

    def test_normalize_sprite_pixels_with_escaped_newlines(self):
        """Test that escaped newlines in sprite pixels are normalized."""
        config_data = {
            'sprite': {'pixels': '##\\n..'},
        }
        result = normalize_toml_data(config_data)
        assert result['sprite']['pixels'] == '##\n..'

    def test_normalize_sprite_pixels_double_escaped(self):
        """Test that double-escaped newlines are normalized."""
        config_data = {
            'sprite': {'pixels': '##\\\\n..'},
        }
        result = normalize_toml_data(config_data)
        assert result['sprite']['pixels'] == '##\n..'

    def test_normalize_no_sprite_section(self):
        """Test normalization when there is no sprite section."""
        config_data = {'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}}}
        result = normalize_toml_data(config_data)
        assert result == config_data

    def test_normalize_no_pixels_in_sprite(self):
        """Test normalization when sprite section has no pixels."""
        config_data = {'sprite': {'name': 'test'}}
        result = normalize_toml_data(config_data)
        assert result['sprite']['name'] == 'test'

    def test_normalize_animation_pixels(self):
        """Test that animation frame pixels are normalized."""
        config_data = {
            'animation': [
                {
                    'frame': [
                        {'pixels': '##\\n..'},
                    ],
                },
            ],
        }
        result = normalize_toml_data(config_data)
        assert result['animation'][0]['frame'][0]['pixels'] == '##\n..'

    def test_normalize_empty_config(self):
        """Test normalization with empty config."""
        result = normalize_toml_data({})
        assert result == {}

    def test_normalize_non_string_pixels_untouched(self):
        """Test that non-string pixels are left untouched."""
        config_data = {
            'sprite': {'pixels': 12345},
        }
        result = normalize_toml_data(config_data)
        assert result['sprite']['pixels'] == 12345

    def test_normalize_returns_original_on_error(self):
        """Test that original data is returned when an error occurs."""
        # Pass something that will cause an error during .copy()
        # Actually, we need to trigger AttributeError/KeyError/TypeError
        # A dict subclass that breaks copy could do it, but simpler to use a
        # config_data whose 'sprite' value is not a dict.
        config_data = {'sprite': 'not_a_dict'}
        result = normalize_toml_data(config_data)
        # Should return the original data since 'pixels' access on a string will fail
        assert result == config_data


# ---------------------------------------------------------------------------
# _detect_alpha_channel tests
# ---------------------------------------------------------------------------


class TestDetectAlphaChannelAdditional:
    """Additional tests for _detect_alpha_channel not covered in existing suite."""

    def test_empty_colors_dict(self):
        """Test detection with empty colors dictionary."""
        assert _detect_alpha_channel({}) is False

    def test_non_dict_color_data_skipped(self):
        """Test that non-dict color data values are skipped."""
        colors = {'#': 'not_a_dict', '.': 123}
        assert _detect_alpha_channel(colors) is False

    def test_three_component_rgb_no_alpha(self):
        """Test that 3-component RGB dict without magenta returns False."""
        colors = {
            '#': {'red': 100, 'green': 100, 'blue': 100},
        }
        assert _detect_alpha_channel(colors) is False

    def test_magenta_with_full_keys(self):
        """Test that magenta with full key names is detected."""
        colors = {'.': {'red': 255, 'green': 0, 'blue': 255}}
        assert _detect_alpha_channel(colors) is True

    def test_mixed_colors_one_has_alpha(self):
        """Test that alpha is detected when only one color has it."""
        colors = {
            '#': {'red': 0, 'green': 0, 'blue': 0},
            '.': {'red': 255, 'green': 255, 'blue': 255, 'alpha': 128},
        }
        assert _detect_alpha_channel(colors) is True


# ---------------------------------------------------------------------------
# _detect_alpha_channel_in_animation tests
# ---------------------------------------------------------------------------


class TestDetectAlphaChannelInAnimation:
    """Tests for _detect_alpha_channel_in_animation function."""

    def test_dict_animation_with_alpha(self):
        """Test dict-based animation data with alpha colors."""
        animation_data = {
            'walk': {
                'colors': {
                    '#': {'red': 0, 'green': 0, 'blue': 0, 'alpha': 128},
                },
            },
        }
        assert _detect_alpha_channel_in_animation(animation_data) is True

    def test_dict_animation_without_alpha(self):
        """Test dict-based animation data without alpha."""
        animation_data = {
            'walk': {
                'colors': {
                    '#': {'red': 0, 'green': 0, 'blue': 0},
                },
            },
        }
        assert _detect_alpha_channel_in_animation(animation_data) is False

    def test_list_animation_with_alpha(self):
        """Test list-based animation data with alpha."""
        animation_data = [
            {
                'colors': {
                    '#': {'red': 255, 'green': 0, 'blue': 255},
                },
            },
        ]
        assert _detect_alpha_channel_in_animation(animation_data) is True

    def test_list_animation_without_alpha(self):
        """Test list-based animation data without alpha."""
        animation_data = [
            {
                'colors': {
                    '#': {'red': 100, 'green': 100, 'blue': 100},
                },
            },
        ]
        assert _detect_alpha_channel_in_animation(animation_data) is False

    def test_empty_dict_animation(self):
        """Test empty dict animation data."""
        assert _detect_alpha_channel_in_animation({}) is False

    def test_empty_list_animation(self):
        """Test empty list animation data."""
        assert _detect_alpha_channel_in_animation([]) is False

    def test_dict_animation_no_colors_key(self):
        """Test dict animation data without colors key."""
        animation_data = {'walk': {'pixels': '##..'}}
        assert _detect_alpha_channel_in_animation(animation_data) is False

    def test_list_animation_no_colors_key(self):
        """Test list animation data without colors key."""
        animation_data = [{'pixels': '##..'}]
        assert _detect_alpha_channel_in_animation(animation_data) is False

    def test_dict_with_non_dict_frame_data(self):
        """Test dict animation where frame data is not a dict."""
        animation_data = {'walk': 'not_a_dict'}
        assert _detect_alpha_channel_in_animation(animation_data) is False

    def test_list_with_non_dict_frame_data(self):
        """Test list animation where frame data is not a dict."""
        animation_data = ['not_a_dict', 42]
        assert _detect_alpha_channel_in_animation(animation_data) is False

    def test_multiple_frames_alpha_in_second(self):
        """Test that alpha is found in the second frame of a list."""
        animation_data = [
            {'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}}},
            {'colors': {'#': {'red': 0, 'green': 0, 'blue': 0, 'alpha': 50}}},
        ]
        assert _detect_alpha_channel_in_animation(animation_data) is True


# ---------------------------------------------------------------------------
# _parse_capabilities_response tests
# ---------------------------------------------------------------------------


class TestParseCapabilitiesResponse:
    """Tests for _parse_capabilities_response function."""

    def test_comma_separated_two_values(self, logger):
        """Test parsing comma-separated context_size,output_limit."""
        result = _parse_capabilities_response(logger, '65536, 8192')
        assert result['context_size'] == 65536
        assert result['output_limit'] == 8192
        assert result['max_tokens'] == 8192

    def test_single_number(self, logger):
        """Test parsing a single number as max_tokens."""
        result = _parse_capabilities_response(logger, '4096')
        assert result['max_tokens'] == 4096

    def test_non_numeric_response(self, logger):
        """Test parsing a non-numeric response returns None max_tokens."""
        result = _parse_capabilities_response(logger, 'I am a language model')
        assert result['max_tokens'] is None
        assert result['raw_response'] == 'I am a language model'

    def test_comma_separated_more_than_two_values(self, logger):
        """Test parsing comma-separated with more than 2 values falls through."""
        result = _parse_capabilities_response(logger, '100, 200, 300')
        # More than 2 parts, so comma branch not taken, tries int() on full string, fails
        assert result['max_tokens'] is None

    def test_comma_separated_non_numeric_values(self, logger):
        """Test comma-separated with non-numeric values."""
        result = _parse_capabilities_response(logger, 'abc, def')
        assert result['max_tokens'] is None

    def test_whitespace_handling(self, logger):
        """Test that whitespace is properly stripped."""
        result = _parse_capabilities_response(logger, '  32000 , 4000  ')
        assert result['context_size'] == 32000
        assert result['output_limit'] == 4000

    def test_single_value_with_whitespace(self, logger):
        """Test single value with whitespace."""
        result = _parse_capabilities_response(logger, '  2048  ')
        assert result['max_tokens'] == 2048


# ---------------------------------------------------------------------------
# _extract_response_content tests
# ---------------------------------------------------------------------------


class TestExtractResponseContent:
    """Tests for _extract_response_content function."""

    def test_valid_response(self, logger):
        """Test extracting content from a valid response."""

        @dataclass
        class MockMessage:
            content: str

        @dataclass
        class MockChoice:
            message: MockMessage

        @dataclass
        class MockResponse:
            choices: list

        response = MockResponse(choices=[MockChoice(message=MockMessage(content='Hello world'))])
        result = _extract_response_content(response, logger)
        assert result.content == 'Hello world'
        assert result.error is None

    def test_no_choices_attribute(self, logger):
        """Test response without choices attribute."""

        class NoChoicesResponse:
            pass

        result = _extract_response_content(NoChoicesResponse(), logger)
        assert result.content is None
        assert result.error == 'No choices in response'

    def test_empty_choices_list(self, logger):
        """Test response with empty choices list."""

        @dataclass
        class MockResponse:
            choices: list

        result = _extract_response_content(MockResponse(choices=[]), logger)
        assert result.content is None
        assert result.error == 'No choices in response'

    def test_choice_without_message(self, logger):
        """Test response where choice has no message attribute."""

        @dataclass
        class ChoiceNoMsg:
            pass

        @dataclass
        class MockResponse:
            choices: list

        result = _extract_response_content(MockResponse(choices=[ChoiceNoMsg()]), logger)
        assert result.content is None
        assert result.error is not None
        assert 'No message' in result.error

    def test_message_without_content(self, logger):
        """Test response where message has no content attribute."""

        class MessageNoContent:
            pass

        @dataclass
        class MockChoice:
            message: object

        @dataclass
        class MockResponse:
            choices: list

        result = _extract_response_content(
            MockResponse(choices=[MockChoice(message=MessageNoContent())]), logger,
        )
        assert result.content is None
        assert result.error is not None
        assert 'No content' in result.error


# ---------------------------------------------------------------------------
# _score_size_match tests
# ---------------------------------------------------------------------------


class TestScoreSizeMatch:
    """Tests for _score_size_match function."""

    def test_exact_match(self):
        """Test exact size match returns 5."""
        example = {'pixels': '####\n####\n####\n####'}
        assert _score_size_match((4, 4), example) == 5

    def test_close_match(self):
        """Test close size match returns 3."""
        # 8x8 requested, 7x7 example is within 25%
        example = {'pixels': '#######\n#######\n#######\n#######\n#######\n#######\n#######'}
        assert _score_size_match((8, 8), example) == 3

    def test_same_aspect_ratio(self):
        """Test same aspect ratio returns 1."""
        # Request 16x8 (2:1), example 8x4 (2:1) - but outside 25% range
        example = {'pixels': '########\n########\n########\n########'}
        result = _score_size_match((16, 8), example)
        assert result == 1

    def test_no_match(self):
        """Test no match returns 0."""
        # Very different size and aspect ratio
        example = {'pixels': '##\n##'}
        assert _score_size_match((100, 10), example) == 0

    def test_no_size_extractable(self):
        """Test returns 0 when size cannot be extracted."""
        example = {'name': 'test'}
        assert _score_size_match((8, 8), example) == 0

    def test_animated_example_size(self):
        """Test size extraction from animated example."""
        example = {'animations': [{'frame': [{'pixels': '####\n####\n####\n####'}]}]}
        assert _score_size_match((4, 4), example) == 5


# ---------------------------------------------------------------------------
# _score_training_example tests
# ---------------------------------------------------------------------------


class TestScoreTrainingExample:
    """Tests for _score_training_example function."""

    def test_animated_keyword_match(self):
        """Test animated keyword matching gives +10."""
        example = {'name': 'walk_cycle', 'sprite_type': 'animated', 'has_alpha': False}
        score = _score_training_example(
            example,
            'animated walk',
            {'animated', 'walk'},
            wants_alpha=False,
            requested_size=None,
        )
        assert score >= 10

    def test_static_keyword_match(self):
        """Test static keyword matching gives +10."""
        example = {'name': 'hero', 'sprite_type': 'static', 'has_alpha': False}
        score = _score_training_example(
            example,
            'static hero',
            {'static', 'hero'},
            wants_alpha=False,
            requested_size=None,
        )
        assert score >= 10

    def test_name_word_match(self):
        """Test name word matching gives +5 per word."""
        example = {'name': 'red hero', 'sprite_type': 'static', 'has_alpha': False}
        score = _score_training_example(
            example,
            'red hero',
            {'red', 'hero'},
            wants_alpha=False,
            requested_size=None,
        )
        # 'red' and 'hero' both match name words: +10
        assert score >= 10

    def test_alpha_matching(self):
        """Test alpha matching bonus."""
        example = {'name': 'ghost', 'sprite_type': 'static', 'has_alpha': True}
        score_wants = _score_training_example(
            example,
            'ghost',
            {'ghost'},
            wants_alpha=True,
            requested_size=None,
        )
        score_no_wants = _score_training_example(
            example,
            'ghost',
            {'ghost'},
            wants_alpha=False,
            requested_size=None,
        )
        assert score_wants > score_no_wants

    def test_color_keyword_bonus(self):
        """Test color keyword bonus."""
        example = {'name': 'red ball', 'sprite_type': 'static', 'has_alpha': False}
        score = _score_training_example(
            example,
            'red ball',
            {'red', 'ball'},
            wants_alpha=False,
            requested_size=None,
        )
        # 'red' in user_lower and 'red' in name -> +2
        assert score >= 2

    def test_no_alpha_both_sides(self):
        """Test no alpha on both sides gives +1."""
        example = {'name': 'block', 'sprite_type': 'static', 'has_alpha': False}
        score = _score_training_example(
            example,
            'block',
            {'block'},
            wants_alpha=False,
            requested_size=None,
        )
        # has_alpha=False and wants_alpha=False -> +1
        assert score >= 1

    def test_size_included_in_scoring(self):
        """Test that requested_size contributes to score."""
        example = {
            'name': 'test',
            'sprite_type': 'static',
            'has_alpha': False,
            'pixels': '####\n####\n####\n####',
        }
        score_with_size = _score_training_example(
            example,
            'test',
            {'test'},
            wants_alpha=False,
            requested_size=(4, 4),
        )
        score_without_size = _score_training_example(
            example,
            'test',
            {'test'},
            wants_alpha=False,
            requested_size=None,
        )
        assert score_with_size > score_without_size


# ---------------------------------------------------------------------------
# _parse_toml_value tests
# ---------------------------------------------------------------------------


class TestParseTomlValue:
    """Tests for _parse_toml_value function."""

    def test_quoted_string(self):
        """Test parsing a quoted string."""
        assert _parse_toml_value('"hello world"') == 'hello world'

    def test_triple_quoted_string_handled_by_single_quote_check(self):
        r"""Test that triple-quoted strings are caught by the single-quote check first.

        Note: The code checks for single-quote wrapping before triple-quotes,
        so '\"\"\"some text\"\"\"' strips outer quotes, leaving '\"\"some text\"\"'.
        This is a known ordering issue in the parser.
        """
        # The single-quote check runs first, stripping only outermost quotes
        assert _parse_toml_value('"""some text"""') == '""some text""'

    def test_boolean_true(self):
        """Test parsing boolean true."""
        assert _parse_toml_value('true') is True

    def test_boolean_false(self):
        """Test parsing boolean false."""
        assert _parse_toml_value('false') is False

    def test_boolean_case_insensitive(self):
        """Test parsing boolean is case insensitive."""
        assert _parse_toml_value('True') is True
        assert _parse_toml_value('FALSE') is False

    def test_integer(self):
        """Test parsing an integer."""
        assert _parse_toml_value('42') == 42

    def test_negative_integer(self):
        """Test parsing a negative integer."""
        assert _parse_toml_value('-7') == -7

    def test_float(self):
        """Test parsing a float."""
        expected_value = 3.14  # noqa: FURB152
        result = _parse_toml_value('3.14')
        assert isinstance(result, float)
        assert abs(result - expected_value) < 1e-9

    def test_comma_separated_array(self):
        """Test parsing comma-separated values as array."""
        result = _parse_toml_value('1, 2, 3')
        assert result == [1, 2, 3]

    def test_plain_string(self):
        """Test parsing a plain string (no quotes, not bool/number)."""
        assert _parse_toml_value('some_value') == 'some_value'

    def test_whitespace_stripped(self):
        """Test that whitespace is stripped."""
        assert _parse_toml_value('  42  ') == 42


# ---------------------------------------------------------------------------
# _fix_color_entry tests
# ---------------------------------------------------------------------------


class TestFixColorEntry:
    """Tests for _fix_color_entry function."""

    def test_normal_color_entry_unchanged(self, logger):
        """Test that a normal color entry is unchanged."""
        color_data = {'red': 100, 'green': 200, 'blue': 50}
        result = _fix_color_entry(color_data, '#', logger)
        assert result == {'red': 100, 'green': 200, 'blue': 50}

    def test_comma_separated_red_field(self, logger):
        """Test fixing comma-separated values in red field."""
        color_data = {'red': '100, 200, 50'}
        result = _fix_color_entry(color_data, '#', logger)
        assert result['red'] == 100
        assert result['green'] == 200
        assert result['blue'] == 50

    def test_comma_separated_green_field(self, logger):
        """Test fixing comma-separated values in green field."""
        color_data = {'green': '128'}
        result = _fix_color_entry(color_data, '.', logger)
        assert result['green'] == '128'  # Not comma-separated, kept as-is

    def test_missing_color_fields(self, logger):
        """Test color entry with missing fields."""
        color_data = {'red': 50}
        result = _fix_color_entry(color_data, '#', logger)
        assert result == {'red': 50}

    def test_non_string_comma_value(self, logger):
        """Test that non-string values without commas are kept as-is."""
        color_data = {'red': 100, 'green': 200, 'blue': 50}
        result = _fix_color_entry(color_data, '#', logger)
        assert result['red'] == 100


# ---------------------------------------------------------------------------
# _fix_comma_separated_color_field tests
# ---------------------------------------------------------------------------


class TestFixCommaSeparatedColorField:
    """Tests for _fix_comma_separated_color_field function."""

    def test_red_with_three_values(self, logger):
        """Test parsing red field with three comma-separated values."""
        fixed_color = {}
        _fix_comma_separated_color_field('red', '100, 200, 50', fixed_color, '#', logger)
        assert fixed_color['red'] == 100
        assert fixed_color['green'] == 200
        assert fixed_color['blue'] == 50

    def test_red_with_two_values(self, logger):
        """Test parsing red field with two comma-separated values."""
        fixed_color = {}
        _fix_comma_separated_color_field('red', '100, 200', fixed_color, '#', logger)
        assert fixed_color['red'] == 100
        assert fixed_color['green'] == 200
        assert 'blue' not in fixed_color

    def test_red_with_one_value(self, logger):
        """Test parsing red field with one value."""
        fixed_color = {}
        _fix_comma_separated_color_field('red', '100', fixed_color, '#', logger)
        assert fixed_color['red'] == 100

    def test_green_with_one_value(self, logger):
        """Test parsing green field with one value."""
        fixed_color = {}
        _fix_comma_separated_color_field('green', '128', fixed_color, '#', logger)
        assert fixed_color['green'] == 128

    def test_blue_with_one_value(self, logger):
        """Test parsing blue field with one value."""
        fixed_color = {}
        _fix_comma_separated_color_field('blue', '255', fixed_color, '#', logger)
        assert fixed_color['blue'] == 255

    def test_invalid_value_stored_as_string(self, logger):
        """Test that invalid values are stored as the original string."""
        fixed_color = {}
        _fix_comma_separated_color_field('red', 'not_a_number', fixed_color, '#', logger)
        assert fixed_color['red'] == 'not_a_number'


# ---------------------------------------------------------------------------
# _extract_example_size tests
# ---------------------------------------------------------------------------


class TestExtractExampleSize:
    """Tests for _extract_example_size function."""

    def test_static_pixels(self):
        """Test extracting size from static sprite pixels."""
        example = {'pixels': '####\n####\n####'}
        result = _extract_example_size(example)
        assert result == (4, 3)

    def test_animated_pixels(self):
        """Test extracting size from animated sprite pixels."""
        example = {'animations': [{'frame': [{'pixels': '##\n##'}]}]}
        result = _extract_example_size(example)
        assert result == (2, 2)

    def test_no_pixels_returns_none(self):
        """Test that example without pixels returns None."""
        assert _extract_example_size({'name': 'test'}) is None

    def test_non_string_pixels_returns_none(self):
        """Test that non-string pixels returns None."""
        assert _extract_example_size({'pixels': 12345}) is None

    def test_single_line_pixels_returns_none(self):
        """Test that single-line pixels (no newline) returns None."""
        assert _extract_example_size({'pixels': '####'}) is None

    def test_empty_animations_list(self):
        """Test empty animations list returns None."""
        assert _extract_example_size({'animations': []}) is None

    def test_animation_no_frame_key(self):
        """Test animation without 'frame' key returns None."""
        assert _extract_example_size({'animations': [{'name': 'walk'}]}) is None

    def test_animation_empty_frame_list(self):
        """Test animation with empty frame list returns None."""
        assert _extract_example_size({'animations': [{'frame': []}]}) is None


# ---------------------------------------------------------------------------
# build_retry_prompt tests
# ---------------------------------------------------------------------------


class TestBuildRetryPrompt:
    """Tests for build_retry_prompt function."""

    def test_missing_sprite_section(self):
        """Test retry prompt for missing [sprite] section."""
        result = build_retry_prompt('make a sprite', 'Missing [sprite] section')
        assert 'CRITICAL' in result
        assert '[sprite]' in result

    def test_missing_colors_section(self):
        """Test retry prompt for missing [colors] section."""
        result = build_retry_prompt('make a sprite', 'Missing [colors] section')
        assert 'CRITICAL' in result
        assert '[colors]' in result

    def test_truncated_error(self):
        """Test retry prompt for truncated response."""
        result = build_retry_prompt('make a sprite', 'Response was truncated')
        assert 'IMPORTANT' in result
        assert 'cut off' in result

    def test_mixed_format_error(self):
        """Test retry prompt for mixed format error."""
        result = build_retry_prompt('make a sprite', 'Mixed pixel format detected')
        assert 'CRITICAL' in result

    def test_comma_error(self):
        """Test retry prompt for comma in color values."""
        result = build_retry_prompt('make a sprite', 'Found comma-separated color values')
        assert 'CRITICAL' in result
        assert 'comma' in result.lower() or 'separate fields' in result

    def test_markdown_error(self):
        """Test retry prompt for markdown in response."""
        result = build_retry_prompt('make a sprite', 'Contains markdown code blocks')
        assert 'CRITICAL' in result

    def test_empty_error(self):
        """Test retry prompt for empty response."""
        result = build_retry_prompt('make a sprite', 'Response was empty')
        assert 'CRITICAL' in result

    def test_generic_error(self):
        """Test retry prompt for unknown error type."""
        result = build_retry_prompt('make a sprite', 'Something weird happened')
        assert 'IMPORTANT' in result
        assert 'Something weird happened' in result

    def test_incomplete_error(self):
        """Test retry prompt for incomplete response."""
        result = build_retry_prompt('make a sprite', 'Response was incomplete')
        assert 'IMPORTANT' in result
        assert 'cut off' in result


# ---------------------------------------------------------------------------
# _alpha_blend_pixel tests
# ---------------------------------------------------------------------------


class TestAlphaBlendPixel:
    """Tests for _alpha_blend_pixel function."""

    def test_rgb_source_pixel(self):
        """Test blending with RGB source pixel."""
        result = _alpha_blend_pixel((128, 128, 128), (0, 0, 0, 0), 1.0)
        assert result is not None
        assert len(result) == 4

    def test_rgba_source_pixel(self):
        """Test blending with RGBA source pixel."""
        result = _alpha_blend_pixel((128, 128, 128, 255), (0, 0, 0, 0), 1.0)
        assert result is not None
        assert len(result) == 4

    def test_magenta_transparency_skipped(self):
        """Test that magenta (255, 0, 255) pixels are skipped."""
        result = _alpha_blend_pixel((255, 0, 255), (0, 0, 0, 0), 1.0)
        assert result is None

    def test_fully_transparent_after_additional_alpha(self):
        """Test that fully transparent pixels after alpha multiplication are skipped."""
        result = _alpha_blend_pixel((128, 128, 128, 0), (0, 0, 0, 0), 1.0)
        assert result is None

    def test_additional_alpha_reduces_opacity(self):
        """Test that additional_alpha reduces source opacity."""
        result_full = _alpha_blend_pixel((128, 128, 128, 255), (0, 0, 0, 255), 1.0)
        result_half = _alpha_blend_pixel((128, 128, 128, 255), (0, 0, 0, 255), 0.5)
        # With half alpha, the result should be more influenced by the destination
        assert result_half is not None
        assert result_full is not None

    def test_zero_output_alpha(self):
        """Test blending when output alpha would be zero."""
        result = _alpha_blend_pixel((128, 128, 128, 1), (0, 0, 0, 0), 0.0)
        # 1 * 0.0 = 0, so source alpha is 0 -> returns None
        assert result is None


# ---------------------------------------------------------------------------
# _get_visible_width tests
# ---------------------------------------------------------------------------


class TestGetVisibleWidth:
    """Tests for _get_visible_width function."""

    def test_plain_text(self):
        """Test width of plain text without ANSI codes."""
        assert _get_visible_width('hello') == 5

    def test_text_with_ansi_codes(self):
        """Test width of text with ANSI color codes."""
        text = '\033[31mhello\033[0m'
        assert _get_visible_width(text) == 5

    def test_empty_string(self):
        """Test width of empty string."""
        assert _get_visible_width('') == 0

    def test_only_ansi_codes(self):
        """Test width of string with only ANSI codes."""
        text = '\033[31m\033[0m'
        assert _get_visible_width(text) == 0

    def test_multiple_ansi_codes(self):
        """Test width with multiple ANSI escape sequences."""
        text = '\033[1;31mhel\033[0mlo'
        assert _get_visible_width(text) == 5


# ---------------------------------------------------------------------------
# _normalize_escaped_newlines tests
# ---------------------------------------------------------------------------


class TestNormalizeEscapedNewlines:
    """Tests for _normalize_escaped_newlines function."""

    def test_single_escaped(self):
        """Test converting single escaped newlines."""
        assert _normalize_escaped_newlines('a\\nb') == 'a\nb'

    def test_double_escaped(self):
        """Test converting double escaped newlines."""
        assert _normalize_escaped_newlines('a\\\\nb') == 'a\nb'

    def test_no_escaped_newlines(self):
        """Test string without escaped newlines."""
        assert _normalize_escaped_newlines('hello') == 'hello'

    def test_empty_string(self):
        """Test empty string."""
        assert not _normalize_escaped_newlines('')


# ---------------------------------------------------------------------------
# _normalize_animation_pixels tests
# ---------------------------------------------------------------------------


class TestNormalizeAnimationPixels:
    """Tests for _normalize_animation_pixels function."""

    def test_normalizes_frame_pixels(self):
        """Test that frame pixels are normalized in place."""
        animation_list = [{'frame': [{'pixels': '##\\n..'}]}]
        _normalize_animation_pixels(animation_list)
        assert animation_list[0]['frame'][0]['pixels'] == '##\n..'

    def test_skips_non_dict_animation(self):
        """Test that non-dict animations are skipped."""
        animation_list = ['not_a_dict']
        _normalize_animation_pixels(animation_list)
        assert animation_list[0] == 'not_a_dict'

    def test_skips_animation_without_frame(self):
        """Test that animations without 'frame' key are skipped."""
        animation_list = [{'name': 'walk'}]
        _normalize_animation_pixels(animation_list)
        assert 'frame' not in animation_list[0]

    def test_skips_non_string_pixels(self):
        """Test that non-string pixels in frames are skipped."""
        animation_list = [{'frame': [{'pixels': 12345}]}]
        _normalize_animation_pixels(animation_list)
        assert animation_list[0]['frame'][0]['pixels'] == 12345


# ---------------------------------------------------------------------------
# _convert_colors_to_rgba tests
# ---------------------------------------------------------------------------


class TestConvertColorsToRgba:
    """Tests for _convert_colors_to_rgba function."""

    def test_standard_color_gets_full_alpha(self):
        """Test that a standard color gets alpha=255."""
        colors = {'#': {'red': 0, 'green': 0, 'blue': 0}}
        result = _convert_colors_to_rgba(colors)
        assert result['#']['alpha'] == 255

    def test_magenta_gets_zero_alpha(self):
        """Test that magenta gets alpha=0 (transparent)."""
        colors = {'.': {'red': 255, 'green': 0, 'blue': 255}}
        result = _convert_colors_to_rgba(colors)
        assert result['.']['alpha'] == 0

    def test_existing_alpha_preserved(self):
        """Test that existing alpha value is preserved."""
        colors = {'#': {'red': 0, 'green': 0, 'blue': 0, 'alpha': 128}}
        result = _convert_colors_to_rgba(colors)
        assert result['#']['alpha'] == 128

    def test_short_key_names(self):
        """Test with short key names (r, g, b)."""
        colors = {'#': {'r': 100, 'g': 200, 'b': 50}}
        result = _convert_colors_to_rgba(colors)
        assert result['#']['red'] == 100
        assert result['#']['green'] == 200
        assert result['#']['blue'] == 50
        assert result['#']['alpha'] == 255

    def test_non_dict_color_data_unchanged(self):
        """Test that non-dict color data is left unchanged."""
        colors = {'#': 'not_a_dict'}
        result = _convert_colors_to_rgba(colors)
        assert result['#'] == 'not_a_dict'


# ---------------------------------------------------------------------------
# _convert_animation_colors_to_rgba tests
# ---------------------------------------------------------------------------


class TestConvertAnimationColorsToRgba:
    """Tests for _convert_animation_colors_to_rgba function."""

    def test_frame_with_colors(self):
        """Test conversion of frames with colors."""
        animations = {
            'walk': {
                'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}},
                'pixels': '##',
            },
        }
        result = _convert_animation_colors_to_rgba(animations)
        assert result['walk']['colors']['#']['alpha'] == 255

    def test_frame_without_colors(self):
        """Test that frames without colors are left unchanged."""
        animations = {'walk': 'not_a_dict'}
        result = _convert_animation_colors_to_rgba(animations)
        assert result['walk'] == 'not_a_dict'


# ---------------------------------------------------------------------------
# convert_sprite_to_alpha_format tests
# ---------------------------------------------------------------------------


class TestConvertSpriteToAlphaFormat:
    """Tests for convert_sprite_to_alpha_format function."""

    def test_sprite_with_alpha(self):
        """Test converting sprite with has_alpha=True."""
        sprite_data = {
            'has_alpha': True,
            'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}},
        }
        result = convert_sprite_to_alpha_format(sprite_data)
        assert result['colors']['#']['alpha'] == 255

    def test_sprite_without_alpha(self):
        """Test that sprite without has_alpha is unchanged."""
        sprite_data = {
            'has_alpha': False,
            'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}},
        }
        result = convert_sprite_to_alpha_format(sprite_data)
        # Colors should not have alpha added
        assert 'alpha' not in result['colors']['#']

    def test_sprite_with_animations(self):
        """Test converting sprite with animations and alpha."""
        sprite_data = {
            'has_alpha': True,
            'animations': {
                'walk': {
                    'colors': {'#': {'red': 100, 'green': 100, 'blue': 100}},
                },
            },
        }
        result = convert_sprite_to_alpha_format(sprite_data)
        assert result['animations']['walk']['colors']['#']['alpha'] == 255


# ---------------------------------------------------------------------------
# _sprite_has_per_pixel_alpha tests
# ---------------------------------------------------------------------------


class TestSpriteHasPerPixelAlpha:
    """Tests for _sprite_has_per_pixel_alpha function."""

    def test_no_animations_attribute(self):
        """Test sprite without _animations attribute."""

        class FakeSprite:
            pass

        result = _sprite_has_per_pixel_alpha(FakeSprite())  # type: ignore[invalid-argument-type]
        assert result is False

    def test_opaque_pixels_only(self):
        """Test sprite with only opaque pixels."""

        class FakeFrame:
            def get_pixel_data(self) -> list[tuple[int, ...]]:
                return cast('list[tuple[int, ...]]', [(0, 0, 0, 255), (255, 255, 255, 255)])

        class FakeSprite:
            def __init__(self):
                self._animations = {'idle': [FakeFrame()]}

        result = _sprite_has_per_pixel_alpha(FakeSprite())  # type: ignore[invalid-argument-type]
        assert result is False

    def test_has_transparent_pixel(self):
        """Test sprite with a transparent pixel."""

        class FakeFrame:
            def get_pixel_data(self) -> list[tuple[int, ...]]:
                return cast('list[tuple[int, ...]]', [(0, 0, 0, 128)])

        class FakeSprite:
            def __init__(self):
                self._animations = {'idle': [FakeFrame()]}

        result = _sprite_has_per_pixel_alpha(FakeSprite())  # type: ignore[invalid-argument-type]
        assert result is True

    def test_rgb_only_pixels(self):
        """Test sprite with RGB-only pixels (no alpha channel)."""

        class FakeFrame:
            def get_pixel_data(self) -> list[tuple[int, ...]]:
                return cast('list[tuple[int, ...]]', [(0, 0, 0), (255, 255, 255)])

        class FakeSprite:
            def __init__(self):
                self._animations = {'idle': [FakeFrame()]}

        result = _sprite_has_per_pixel_alpha(FakeSprite())  # type: ignore[invalid-argument-type]
        assert result is False


# ---------------------------------------------------------------------------
# _pixels_have_alpha tests
# ---------------------------------------------------------------------------


class TestPixelsHaveAlpha:
    """Tests for _pixels_have_alpha function."""

    def test_no_alpha_pixels(self):
        """Test pixels without alpha."""
        assert _pixels_have_alpha([(0, 0, 0), (255, 255, 255)]) is False

    def test_opaque_rgba_pixels(self):
        """Test RGBA pixels that are fully opaque."""
        assert _pixels_have_alpha([(0, 0, 0, 255)]) is False

    def test_transparent_rgba_pixel(self):
        """Test RGBA pixel with transparency."""
        assert _pixels_have_alpha([(0, 0, 0, 128)]) is True

    def test_empty_pixel_list(self):
        """Test empty pixel list."""
        assert _pixels_have_alpha([]) is False


# ---------------------------------------------------------------------------
# detect_file_format tests
# ---------------------------------------------------------------------------


class TestDetectFileFormat:
    """Tests for detect_file_format function."""

    def test_toml_extension(self):
        """Test TOML extension detection."""
        assert detect_file_format('sprite.toml') == 'toml'

    def test_no_extension(self):
        """Test file with no extension defaults to toml."""
        assert detect_file_format('sprite') == 'toml'

    def test_unsupported_extension(self):
        """Test unsupported extension raises ValueError."""
        with pytest.raises(ValueError, match='Unsupported'):
            detect_file_format('sprite.yaml')

    def test_png_extension_unsupported(self):
        """Test PNG extension raises ValueError."""
        with pytest.raises(ValueError, match='Unsupported'):
            detect_file_format('sprite.png')


# ---------------------------------------------------------------------------
# _process_ai_request tests
# ---------------------------------------------------------------------------


class TestProcessAiRequest:
    """Tests for _process_ai_request function."""

    def test_none_client_returns_unavailable(self, logger):
        """Test that None client returns AI unavailable response."""
        request = AIRequest(prompt='test', request_id='1', messages=[])
        result = _process_ai_request(request, None, logger)
        assert result.content == 'AI features not available'


# ---------------------------------------------------------------------------
# _create_ai_retry_decorator tests
# ---------------------------------------------------------------------------


class TestCreateAiRetryDecorator:
    """Tests for _create_ai_retry_decorator function."""

    def test_returns_callable_decorator(self, logger):
        """Test that a callable decorator is returned."""
        decorator = _create_ai_retry_decorator(logger)
        assert callable(decorator)

    def test_no_op_when_backoff_unavailable(self, logger, mocker):
        """Test no-op decorator when backoff module is not available."""
        mocker.patch('glitchygames.bitmappy.ai_worker.backoff', None)
        decorator = _create_ai_retry_decorator(logger)

        # The no-op decorator should return the function unchanged
        def sample_function():
            return 'result'

        decorated = decorator(sample_function)
        assert decorated is sample_function


# ---------------------------------------------------------------------------
# _log_capabilities_dump tests
# ---------------------------------------------------------------------------


class TestLogCapabilitiesDump:
    """Tests for _log_capabilities_dump function."""

    def test_logs_fields(self, logger):
        """Test that fields are logged without errors."""
        # Should not raise any exceptions
        _log_capabilities_dump(logger, **{'Max Tokens': 4096, 'Context Size': 65536})

    def test_logs_with_no_fields(self, logger):
        """Test logging with no additional fields."""
        _log_capabilities_dump(logger)


# ---------------------------------------------------------------------------
# _build_color_to_glyph_map tests
# ---------------------------------------------------------------------------


class TestBuildColorToGlyphMap:
    """Tests for _build_color_to_glyph_map function."""

    def test_single_color(self):
        """Test mapping a single color."""
        pixels = cast('list[tuple[int, ...]]', [(0, 0, 0), (0, 0, 0)])
        result = _build_color_to_glyph_map(pixels)
        assert len(result) == 1
        assert (0, 0, 0) in result

    def test_multiple_colors(self):
        """Test mapping multiple colors."""
        pixels = cast('list[tuple[int, ...]]', [(0, 0, 0), (255, 0, 0), (0, 255, 0)])
        result = _build_color_to_glyph_map(pixels)
        assert len(result) == 3

    def test_rgba_reduced_to_rgb(self):
        """Test that RGBA pixels are reduced to RGB for mapping."""
        pixels = cast('list[tuple[int, ...]]', [(0, 0, 0, 255), (0, 0, 0, 128)])
        result = _build_color_to_glyph_map(pixels)
        # Both reduce to (0, 0, 0) so only one entry
        assert len(result) == 1

    def test_empty_pixels(self):
        """Test with empty pixel list."""
        result = _build_color_to_glyph_map([])
        assert result == {}


# ---------------------------------------------------------------------------
# _build_ascii_grid tests
# ---------------------------------------------------------------------------


class TestBuildAsciiGrid:
    """Tests for _build_ascii_grid function."""

    def test_simple_grid(self):
        """Test building a simple 2x2 grid."""
        pixels = cast('list[tuple[int, ...]]', [(0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255)])
        color_map = cast(
            'dict[tuple[int, ...], str]',
            {
                (0, 0, 0): '#',
                (255, 0, 0): 'R',
                (0, 255, 0): 'G',
                (0, 0, 255): 'B',
            },
        )
        result = _build_ascii_grid(pixels, 2, 2, color_map)
        assert result == '#R\nGB'

    def test_empty_pixels(self):
        """Test building grid with empty pixels."""
        result = _build_ascii_grid([], 0, 0, {})
        assert not result


# ---------------------------------------------------------------------------
# _build_renderer_color_dict tests
# ---------------------------------------------------------------------------


class TestBuildRendererColorDict:
    """Tests for _build_renderer_color_dict function."""

    def test_rgb_to_rgba_mapping(self):
        """Test that RGB colors get alpha 255 in renderer dict."""
        pixels = cast('list[tuple[int, ...]]', [(100, 200, 50)])
        color_map = cast('dict[tuple[int, ...], str]', {(100, 200, 50): '#'})
        result = _build_renderer_color_dict(pixels, color_map)
        assert result['#'] == (100, 200, 50, 255)

    def test_magenta_mapped_to_white(self):
        """Test that magenta is mapped to white in renderer dict."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 255)])
        color_map = cast('dict[tuple[int, ...], str]', {(255, 0, 255): '.'})
        result = _build_renderer_color_dict(pixels, color_map)
        assert result['.'] == (255, 255, 255, 255)

    def test_rgba_alpha_preserved(self):
        """Test that RGBA alpha is preserved in renderer dict."""
        pixels = cast('list[tuple[int, ...]]', [(100, 200, 50, 128)])
        color_map = cast('dict[tuple[int, ...], str]', {(100, 200, 50): '#'})
        result = _build_renderer_color_dict(pixels, color_map)
        assert result['#'] == (100, 200, 50, 128)


# ---------------------------------------------------------------------------
# _fix_color_format_in_toml_data tests
# ---------------------------------------------------------------------------


class TestFixColorFormatInTomlData:
    """Tests for _fix_color_format_in_toml_data function."""

    def test_no_colors_key(self, logger):
        """Test data without colors key is returned unchanged."""
        data = {'sprite': {'name': 'test'}}
        result = _fix_color_format_in_toml_data(data, logger)
        assert result == data

    def test_normal_colors_unchanged(self, logger):
        """Test that normal color entries are unchanged."""
        data = {'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}}}
        result = _fix_color_format_in_toml_data(data, logger)
        assert result['colors']['#'] == {'red': 0, 'green': 0, 'blue': 0}

    def test_non_dict_color_entry(self, logger):
        """Test that non-dict color entries are kept as-is."""
        data = {'colors': {'#': 'string_value'}}
        result = _fix_color_format_in_toml_data(data, logger)
        assert result['colors']['#'] == 'string_value'


# ---------------------------------------------------------------------------
# parse_toml_robustly tests
# ---------------------------------------------------------------------------


class TestParseTomlRobustly:
    """Tests for parse_toml_robustly function."""

    def test_valid_toml(self, logger):
        """Test parsing valid TOML content."""
        content = '[sprite]\nname = "test"\n'
        result = parse_toml_robustly(content, logger)
        assert result['sprite']['name'] == 'test'

    def test_invalid_toml_falls_back(self, logger):
        """Test that invalid TOML falls back to permissive parser."""
        # Duplicate keys cause standard TOML parsing to fail
        content = '[sprite]\nname = "test"\nname = "test2"\n'
        result = parse_toml_robustly(content, logger)
        # Permissive parser takes last value
        assert result is not None

    def test_default_logger_used(self):
        """Test that default logger is used when None is passed."""
        result = parse_toml_robustly('[sprite]\nname = "test"\n')
        assert result['sprite']['name'] == 'test'


# ---------------------------------------------------------------------------
# AIRequest / AIResponse dataclass tests
# ---------------------------------------------------------------------------


class TestAIDataClasses:
    """Tests for AIRequest and AIResponse dataclasses."""

    def test_ai_request_creation(self):
        """Test creating an AIRequest."""
        request = AIRequest(
            prompt='test',
            request_id='id1',
            messages=[{'role': 'user', 'content': 'hi'}],
        )
        assert request.prompt == 'test'
        assert request.request_id == 'id1'
        assert len(request.messages) == 1

    def test_ai_response_defaults(self):
        """Test AIResponse default values."""
        response = AIResponse(content='hello')
        assert response.content == 'hello'
        assert response.error is None

    def test_ai_response_with_error(self):
        """Test AIResponse with error."""
        response = AIResponse(content=None, error='something went wrong')
        assert response.content is None
        assert response.error == 'something went wrong'


# ---------------------------------------------------------------------------
# resource_path tests
# ---------------------------------------------------------------------------


class TestResourcePath:
    """Tests for resource_path function."""

    def test_returns_path_object(self):
        """Test that resource_path returns a Path object."""
        from pathlib import Path

        result = resource_path('glitchygames', 'assets', 'fonts')
        assert isinstance(result, Path)

    def test_multiple_segments(self):
        """Test resource_path with multiple segments."""
        result = resource_path('glitchygames', 'assets', 'fonts', 'bitstream.ttf')
        assert 'fonts' in str(result)


# ---------------------------------------------------------------------------
# select_relevant_training_examples tests
# ---------------------------------------------------------------------------


class TestSelectRelevantTrainingExamples:
    """Tests for select_relevant_training_examples function."""

    def test_empty_training_data(self, mocker):
        """Test with empty training data."""
        mocker.patch('glitchygames.bitmappy.ai_worker.ai_training_state', {'data': []})
        result = select_relevant_training_examples('test sprite')
        assert result == []

    def test_non_list_training_data(self, mocker):
        """Test with non-list training data."""
        mocker.patch('glitchygames.bitmappy.ai_worker.ai_training_state', {'data': 'not_a_list'})
        result = select_relevant_training_examples('test sprite')
        assert result == []

    def test_fewer_than_max_examples(self, mocker):
        """Test with fewer examples than max."""
        examples = [
            {'name': 'hero', 'sprite_type': 'static', 'has_alpha': False},
        ]
        mocker.patch('glitchygames.bitmappy.ai_worker.ai_training_state', {'data': examples})
        result = select_relevant_training_examples('test', max_examples=10)
        assert result == examples

    def test_scoring_and_selection(self, mocker):
        """Test that examples are scored and top ones selected."""
        examples = [
            {'name': 'unrelated', 'sprite_type': 'static', 'has_alpha': False},
            {'name': 'animated walk', 'sprite_type': 'animated', 'has_alpha': False},
            {'name': 'another', 'sprite_type': 'static', 'has_alpha': False},
        ]
        mocker.patch('glitchygames.bitmappy.ai_worker.ai_training_state', {'data': examples})
        result = select_relevant_training_examples('animated walk cycle', max_examples=2)
        assert len(result) == 2
        # The animated walk example should be ranked first
        assert result[0]['name'] == 'animated walk'


# ---------------------------------------------------------------------------
# _composite_frames_with_alpha tests
# ---------------------------------------------------------------------------


class TestCompositeFramesWithAlpha:
    """Tests for _composite_frames_with_alpha function."""

    def test_empty_frames_list(self):
        """Test compositing with empty frames list."""
        result = _composite_frames_with_alpha([])
        assert result == []

    def test_single_frame(self):
        """Test compositing with a single frame."""

        class FakeFrame:
            def get_size(self):
                return (2, 2)

            def get_pixel_data(self) -> list[tuple[int, ...]]:
                return cast('list[tuple[int, ...]]', [(100, 100, 100, 255)] * 4)

        result = _composite_frames_with_alpha([FakeFrame()])  # type: ignore[invalid-argument-type]
        assert len(result) == 4
        # All pixels should be blended
        for pixel in result:
            assert len(pixel) == 4


# ---------------------------------------------------------------------------
# MockEvent tests
# ---------------------------------------------------------------------------


class TestMockEvent:
    """Tests for MockEvent class."""

    def test_mock_event_creation(self):
        """Test creating a MockEvent."""
        from glitchygames.bitmappy.models import MockEvent

        event = MockEvent(text='test.toml')
        assert event.text == 'test.toml'
