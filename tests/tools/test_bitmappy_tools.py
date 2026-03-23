"""Tests for bitmappy tool operations: alpha blending, color calculations, scoring."""

import logging
from typing import cast

import pytest

from glitchygames.bitmappy.ai_worker import (
    _extract_response_content,
    _parse_capabilities_response,
    _score_size_match,
    _score_training_example,
    build_retry_prompt,
)
from glitchygames.bitmappy.models import AIResponse
from glitchygames.bitmappy.pixel_ops import _alpha_blend_pixel, _get_visible_width
from glitchygames.bitmappy.sprite_inspection import (
    _calculate_animation_duration,
    _format_duration_string,
    _get_sprite_alpha_type,
    _get_sprite_color_count,
    _pixels_have_alpha,
    _sprite_has_per_pixel_alpha,
)


class TestAlphaBlendPixel:
    """Test the _alpha_blend_pixel function."""

    def test_opaque_rgb_source_over_transparent(self):
        """Test blending an opaque RGB pixel over a transparent destination."""
        result = _alpha_blend_pixel((255, 0, 0), (0, 0, 0, 0), 1.0)
        assert result is not None
        assert result[0] == 255  # Red channel
        assert result[1] == 0
        assert result[2] == 0
        assert result[3] == 255  # Full alpha

    def test_opaque_rgba_source(self):
        """Test blending an opaque RGBA pixel."""
        result = _alpha_blend_pixel((0, 255, 0, 255), (0, 0, 0, 0), 1.0)
        assert result is not None
        assert result[1] == 255  # Green channel

    def test_magenta_returns_none(self):
        """Test that magenta (255, 0, 255) is treated as transparent."""
        result = _alpha_blend_pixel((255, 0, 255), (100, 100, 100, 255), 1.0)
        assert result is None

    def test_magenta_rgba_returns_none(self):
        """Test that magenta RGBA pixel is also transparent."""
        result = _alpha_blend_pixel((255, 0, 255, 255), (100, 100, 100, 255), 1.0)
        assert result is None

    def test_zero_additional_alpha_returns_none(self):
        """Test that zero additional alpha makes all pixels transparent."""
        result = _alpha_blend_pixel((255, 0, 0, 255), (0, 0, 0, 255), 0.0)
        assert result is None

    def test_half_alpha_blending(self):
        """Test blending with 50% additional alpha."""
        result = _alpha_blend_pixel((255, 0, 0), (0, 0, 0, 255), 0.5)
        assert result is not None
        # With 50% alpha on red over opaque black, we get a reddish dark color
        assert result[0] > 0  # Some red
        assert result[3] == 255  # Full output alpha

    def test_fully_transparent_source_returns_none(self):
        """Test that fully transparent source pixel returns None."""
        result = _alpha_blend_pixel((100, 200, 50, 0), (0, 0, 0, 255), 1.0)
        assert result is None

    def test_semi_transparent_over_opaque(self):
        """Test semi-transparent source over opaque destination."""
        result = _alpha_blend_pixel((255, 0, 0, 128), (0, 0, 255, 255), 1.0)
        assert result is not None
        # Result should be a blend of red and blue
        assert result[0] > 0  # Some red
        assert result[2] > 0  # Some blue

    def test_both_transparent_returns_transparent(self):
        """Test blending two nearly transparent pixels."""
        result = _alpha_blend_pixel((255, 0, 0, 1), (0, 0, 255, 0), 1.0)
        assert result is not None
        assert result[3] > 0  # Very small alpha

    def test_opaque_source_replaces_destination(self):
        """Test that opaque source effectively replaces destination."""
        result = _alpha_blend_pixel((255, 0, 0, 255), (0, 0, 255, 255), 1.0)
        assert result is not None
        assert result[0] == 255  # Full red
        assert result[2] == 0  # No blue
        assert result[3] == 255


class TestGetVisibleWidth:
    """Test _get_visible_width function."""

    def test_plain_text(self):
        """Test width of plain text without ANSI codes."""
        assert _get_visible_width('hello') == 5

    def test_text_with_ansi_color(self):
        """Test that ANSI color codes are excluded from width."""
        # ANSI red text: \x1b[31mhello\x1b[0m
        text = '\x1b[31mhello\x1b[0m'
        assert _get_visible_width(text) == 5

    def test_empty_string(self):
        """Test width of empty string."""
        assert _get_visible_width('') == 0

    def test_multiple_ansi_codes(self):
        """Test text with multiple ANSI escape sequences."""
        text = '\x1b[1m\x1b[31mbold red\x1b[0m'
        assert _get_visible_width(text) == 8

    def test_string_without_ansi(self):
        """Test regular string is measured correctly."""
        assert _get_visible_width('##..@@') == 6


class TestPixelsHaveAlpha:
    """Test _pixels_have_alpha function."""

    def test_rgb_pixels_no_alpha(self):
        """Test that RGB-only pixels report no alpha."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0), (0, 255, 0), (0, 0, 255)])
        assert _pixels_have_alpha(pixels) is False

    def test_rgba_opaque_pixels_no_alpha(self):
        """Test that fully opaque RGBA pixels report no alpha."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0, 255), (0, 255, 0, 255)])
        assert _pixels_have_alpha(pixels) is False

    def test_rgba_with_transparency(self):
        """Test that RGBA pixels with transparency are detected."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0, 128), (0, 255, 0, 255)])
        assert _pixels_have_alpha(pixels) is True

    def test_fully_transparent_pixel(self):
        """Test detection of fully transparent pixel."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0, 0)])
        assert _pixels_have_alpha(pixels) is True

    def test_empty_pixel_list(self):
        """Test with empty pixel list."""
        assert _pixels_have_alpha([]) is False

    def test_mixed_rgb_and_rgba(self):
        """Test with mix of RGB and RGBA pixels."""
        pixels: list[tuple[int, ...]] = [(255, 0, 0), (0, 255, 0, 100)]
        assert _pixels_have_alpha(pixels) is True


class TestSpriteHasPerPixelAlpha:
    """Test _sprite_has_per_pixel_alpha function."""

    def test_sprite_without_animations_attribute(self):
        """Test sprite without _animations returns False."""

        class DummySprite:
            pass

        assert _sprite_has_per_pixel_alpha(DummySprite()) is False  # type: ignore[invalid-argument-type]

    def test_sprite_with_opaque_frames(self, mocker):
        """Test sprite with only opaque pixels returns False."""
        sprite = mocker.Mock()
        frame = mocker.Mock()
        frame.get_pixel_data.return_value = [(255, 0, 0, 255), (0, 255, 0, 255)]
        sprite._animations = {'idle': [frame]}
        assert _sprite_has_per_pixel_alpha(sprite) is False

    def test_sprite_with_transparent_frames(self, mocker):
        """Test sprite with transparent pixels returns True."""
        sprite = mocker.Mock()
        frame = mocker.Mock()
        frame.get_pixel_data.return_value = [(255, 0, 0, 128), (0, 255, 0, 255)]
        sprite._animations = {'idle': [frame]}
        assert _sprite_has_per_pixel_alpha(sprite) is True

    def test_sprite_with_rgb_only_frames(self, mocker):
        """Test sprite with RGB-only pixels (no alpha) returns False."""
        sprite = mocker.Mock()
        frame = mocker.Mock()
        frame.get_pixel_data.return_value = [(255, 0, 0), (0, 255, 0)]
        sprite._animations = {'idle': [frame]}
        assert _sprite_has_per_pixel_alpha(sprite) is False

    def test_sprite_with_empty_animations(self, mocker):
        """Test sprite with empty animations dict returns False."""
        sprite = mocker.Mock()
        sprite._animations = {}
        assert _sprite_has_per_pixel_alpha(sprite) is False


class TestGetSpriteColorCount:
    """Test _get_sprite_color_count function."""

    def test_sprite_with_color_map(self, mocker):
        """Test getting color count from color_map attribute."""
        sprite = mocker.Mock(spec=[])
        sprite.color_map = {'#': (0, 0, 0), '.': (255, 255, 255), '@': (255, 0, 0)}
        assert _get_sprite_color_count(sprite) == 3

    def test_sprite_with_private_color_map(self, mocker):
        """Test getting color count from _color_map attribute."""
        sprite = mocker.Mock(spec=[])
        sprite._color_map = {'#': (0, 0, 0), '.': (255, 255, 255)}
        assert _get_sprite_color_count(sprite) == 2

    def test_sprite_without_color_map(self, mocker):
        """Test sprite without any color map returns 0."""
        sprite = mocker.Mock(spec=[])
        assert _get_sprite_color_count(sprite) == 0

    def test_sprite_with_empty_color_map(self, mocker):
        """Test sprite with empty color map returns 0."""
        sprite = mocker.Mock(spec=[])
        sprite.color_map = {}
        assert _get_sprite_color_count(sprite) == 0


class TestGetSpriteAlphaType:
    """Test _get_sprite_alpha_type function."""

    def test_sprite_without_color_map(self, mocker):
        """Test sprite without color_map returns 'indexed'."""
        sprite = mocker.Mock(spec=[])
        assert _get_sprite_alpha_type(sprite) == 'indexed'

    def test_sprite_with_rgb_colors(self, mocker):
        """Test sprite with RGB colors returns 'indexed'."""
        sprite = mocker.Mock(spec=[])
        sprite.color_map = {'#': (0, 0, 0), '.': (255, 255, 255)}
        assert _get_sprite_alpha_type(sprite) == 'indexed'

    def test_sprite_with_per_pixel_alpha(self, mocker):
        """Test sprite with RGBA colors with valid alpha returns 'per-pixel'."""
        sprite = mocker.Mock(spec=[])
        sprite.color_map = {'#': (0, 0, 0, 128)}
        assert _get_sprite_alpha_type(sprite) == 'per-pixel'

    def test_sprite_with_full_opacity_rgba(self, mocker):
        """Test sprite with RGBA colors at alpha=255 returns 'indexed'."""
        # MAX_PER_PIXEL_ALPHA is 254, so alpha=255 is not per-pixel
        sprite = mocker.Mock(spec=[])
        sprite.color_map = {'#': (0, 0, 0, 255)}
        assert _get_sprite_alpha_type(sprite) == 'indexed'

    def test_sprite_with_alpha_zero(self, mocker):
        """Test sprite with alpha=0 returns 'per-pixel'."""
        sprite = mocker.Mock(spec=[])
        sprite.color_map = {'@': (255, 0, 255, 0)}
        assert _get_sprite_alpha_type(sprite) == 'per-pixel'


class TestCalculateAnimationDuration:
    """Test _calculate_animation_duration function."""

    def test_static_sprite(self):
        """Test that static sprites return zero duration."""
        total_duration, is_looped = _calculate_animation_duration(object(), 'static')  # type: ignore[invalid-argument-type]
        assert total_duration == pytest.approx(0.0)
        assert is_looped is False

    def test_animated_sprite_without_animations_attr(self, mocker):
        """Test animated sprite without _animations attribute."""
        sprite = mocker.Mock(spec=[])
        total_duration, is_looped = _calculate_animation_duration(sprite, 'animated')
        assert total_duration == pytest.approx(0.0)
        assert is_looped is False

    def test_animated_sprite_with_frames(self, mocker):
        """Test animated sprite with frames that have durations."""
        sprite = mocker.Mock()
        frame1 = mocker.Mock()
        frame1.duration = 0.5
        frame2 = mocker.Mock()
        frame2.duration = 1.0
        sprite._animations = {'walk': [frame1, frame2]}
        sprite.is_looping = False

        total_duration, is_looped = _calculate_animation_duration(sprite, 'animated')
        assert total_duration == pytest.approx(1.5)
        assert is_looped is False

    def test_animated_sprite_looping(self, mocker):
        """Test animated sprite with looping enabled."""
        sprite = mocker.Mock()
        frame = mocker.Mock()
        frame.duration = 0.5
        sprite._animations = {'idle': [frame]}
        sprite.is_looping = True

        total_duration, is_looped = _calculate_animation_duration(sprite, 'animated')
        assert total_duration == pytest.approx(0.5)
        assert is_looped is True

    def test_frames_without_duration_default_to_half_second(self, mocker):
        """Test that frames without duration attribute default to 0.5s."""
        sprite = mocker.Mock()
        frame = mocker.Mock(spec=[])  # spec=[] means no attributes
        sprite._animations = {'walk': [frame]}
        sprite.is_looping = False

        total_duration, _is_looped = _calculate_animation_duration(sprite, 'animated')
        assert total_duration == pytest.approx(0.5)


class TestFormatDurationString:
    """Test _format_duration_string function."""

    def test_static_sprite_returns_infinity(self):
        """Test static sprite returns infinity symbol."""
        assert _format_duration_string('static', 0.0, is_looped=False) == '\u221e'

    def test_looped_animation(self):
        """Test looped animation shows duration with infinity."""
        result = _format_duration_string('animated', 2.5, is_looped=True)
        assert result == '2.5s (\u221e)'

    def test_single_play_animation(self):
        """Test single-play animation shows duration with "1 time"."""
        result = _format_duration_string('animated', 3.0, is_looped=False)
        assert result == '3.0s (1 time)'

    def test_zero_duration_non_looped(self):
        """Test zero duration non-looped returns infinity."""
        result = _format_duration_string('animated', 0.0, is_looped=False)
        assert result == '\u221e'


class TestScoreSizeMatch:
    """Test _score_size_match function."""

    def test_exact_match_returns_5(self):
        """Test exact size match returns highest score."""
        example = {'pixels': '####\n####\n####\n####'}
        assert _score_size_match((4, 4), example) == 5

    def test_close_match_returns_3(self):
        """Test close size match returns 3."""
        # 8x8 vs 7x7 - within 25% tolerance
        example = {'pixels': '#######\n' * 6 + '#######'}
        result = _score_size_match((8, 8), example)
        assert result == 3

    def test_no_size_info_returns_0(self):
        """Test example without size info returns 0."""
        example = {'name': 'test'}
        assert _score_size_match((8, 8), example) == 0


class TestScoreTrainingExample:
    """Test _score_training_example function."""

    def test_animated_keyword_match(self):
        """Test scoring bonus for animated keyword match."""
        example = {'name': 'test', 'sprite_type': 'animated', 'has_alpha': False}
        score = _score_training_example(
            example,
            'create an animated slime',
            {'create', 'an', 'animated', 'slime'},
            wants_alpha=False,
            requested_size=None,
        )
        assert score >= 10

    def test_static_keyword_match(self):
        """Test scoring bonus for static keyword match."""
        example = {'name': 'test', 'sprite_type': 'static', 'has_alpha': False}
        score = _score_training_example(
            example,
            'create a static sprite',
            {'create', 'a', 'static', 'sprite'},
            wants_alpha=False,
            requested_size=None,
        )
        assert score >= 10

    def test_name_keyword_match(self):
        """Test scoring bonus for name keyword matches."""
        example = {'name': 'slime monster', 'sprite_type': 'static', 'has_alpha': False}
        score = _score_training_example(
            example,
            'create a slime',
            {'create', 'a', 'slime'},
            wants_alpha=False,
            requested_size=None,
        )
        assert score >= 5

    def test_alpha_match_bonus(self):
        """Test scoring bonus when alpha preference matches."""
        example_with_alpha = {'name': 'test', 'sprite_type': 'static', 'has_alpha': True}
        score_with = _score_training_example(
            example_with_alpha,
            'transparent sprite',
            {'transparent', 'sprite'},
            wants_alpha=True,
            requested_size=None,
        )

        example_without_alpha = {'name': 'test', 'sprite_type': 'static', 'has_alpha': False}
        score_without = _score_training_example(
            example_without_alpha,
            'transparent sprite',
            {'transparent', 'sprite'},
            wants_alpha=True,
            requested_size=None,
        )
        assert score_with > score_without

    def test_color_keyword_bonus(self):
        """Test scoring bonus for color keyword matches."""
        example = {'name': 'red dragon', 'sprite_type': 'static', 'has_alpha': False}
        score = _score_training_example(
            example,
            'create a red dragon',
            {'create', 'a', 'red', 'dragon'},
            wants_alpha=False,
            requested_size=None,
        )
        # Should get +2 for color match, +5 for name match on 'dragon' or 'red'
        assert score >= 2

    def test_zero_score_for_no_matches(self):
        """Test zero score when nothing matches."""
        example = {'name': 'mushroom', 'sprite_type': 'animated', 'has_alpha': True}
        score = _score_training_example(
            example,
            'create a static tree',
            {'create', 'a', 'static', 'tree'},
            wants_alpha=False,
            requested_size=None,
        )
        # No type match, no name match, alpha mismatch
        assert score >= 0  # Score is always non-negative


class TestBuildRetryPrompt:
    """Test build_retry_prompt function."""

    def test_missing_sprite_section(self):
        """Test retry prompt for missing [sprite] section."""
        result = build_retry_prompt('Create a slime', 'Missing [sprite] section')
        assert 'CRITICAL' in result
        assert '[sprite]' in result
        assert 'Create a slime' in result

    def test_missing_colors_section(self):
        """Test retry prompt for missing [colors] section."""
        result = build_retry_prompt('Create a cat', 'Missing [colors] section')
        assert 'CRITICAL' in result
        assert '[colors]' in result

    def test_truncated_response(self):
        """Test retry prompt for truncated response."""
        result = build_retry_prompt('Create a sprite', 'Response appears truncated')
        assert 'IMPORTANT' in result
        assert 'cut off' in result

    def test_mixed_format_error(self):
        """Test retry prompt for mixed format error."""
        result = build_retry_prompt('Create animation', 'Mixed static and animated format')
        assert 'CRITICAL' in result
        assert 'animated' in result.lower()

    def test_comma_format_error(self):
        """Test retry prompt for comma-separated color error."""
        result = build_retry_prompt('Create sprite', 'Found comma-separated color values')
        assert 'CRITICAL' in result
        assert 'comma' in result.lower() or 'separate fields' in result

    def test_markdown_format_error(self):
        """Test retry prompt for markdown wrapping error."""
        result = build_retry_prompt('Create sprite', 'Response contains markdown code blocks')
        assert 'CRITICAL' in result
        assert 'TOML' in result

    def test_empty_response_error(self):
        """Test retry prompt for empty response."""
        result = build_retry_prompt('Create sprite', 'Empty response received')
        assert 'CRITICAL' in result

    def test_generic_error(self):
        """Test retry prompt for unrecognized error."""
        result = build_retry_prompt('Create sprite', 'Some unknown error')
        assert 'IMPORTANT' in result
        assert 'Some unknown error' in result

    def test_original_prompt_preserved(self):
        """Test that the original prompt is preserved in the retry."""
        result = build_retry_prompt('Make a cool mushroom sprite', 'Missing [colors] section')
        assert 'Make a cool mushroom sprite' in result


class TestParseCapabilitiesResponse:
    """Test _parse_capabilities_response function."""

    def test_parse_comma_separated_values(self):
        """Test parsing comma-separated context size and output limit."""
        log = logging.getLogger('test')
        result = _parse_capabilities_response(log, '65536,8192')
        assert result['context_size'] == 65536
        assert result['output_limit'] == 8192
        assert result['max_tokens'] == 8192

    def test_parse_single_number(self):
        """Test parsing a single number response."""
        log = logging.getLogger('test')
        result = _parse_capabilities_response(log, '4096')
        assert result['max_tokens'] == 4096

    def test_parse_non_numeric_response(self):
        """Test parsing a non-numeric response."""
        log = logging.getLogger('test')
        result = _parse_capabilities_response(log, 'I can handle up to 8192 tokens')
        assert result['max_tokens'] is None
        assert 'raw_response' in result

    def test_parse_with_whitespace(self):
        """Test parsing response with whitespace."""
        log = logging.getLogger('test')
        result = _parse_capabilities_response(log, '  65536 , 8192  ')
        assert result['context_size'] == 65536
        assert result['output_limit'] == 8192


class TestExtractResponseContent:
    """Test _extract_response_content function."""

    def test_valid_response(self, mocker):
        """Test extracting content from a valid response."""
        log = logging.getLogger('test')
        message = mocker.Mock()
        message.content = '[sprite]\nname = "test"'
        choice = mocker.Mock()
        choice.message = message
        response = mocker.Mock()
        response.choices = [choice]

        result = _extract_response_content(response, log)
        assert isinstance(result, AIResponse)
        assert result.content == '[sprite]\nname = "test"'
        assert result.error is None

    def test_empty_choices(self, mocker):
        """Test response with empty choices list."""
        log = logging.getLogger('test')
        response = mocker.Mock()
        response.choices = []

        result = _extract_response_content(response, log)
        assert result.content is None
        assert result.error is not None

    def test_no_choices_attribute(self, mocker):
        """Test response without choices attribute."""
        log = logging.getLogger('test')
        response = mocker.Mock(spec=[])  # No attributes

        result = _extract_response_content(response, log)
        assert result.content is None
        assert result.error is not None

    def test_no_message_attribute(self, mocker):
        """Test choice without message attribute."""
        log = logging.getLogger('test')
        choice = mocker.Mock(spec=[])  # No attributes
        response = mocker.Mock()
        response.choices = [choice]

        result = _extract_response_content(response, log)
        assert result.content is None
        assert result.error is not None

    def test_no_content_attribute(self, mocker):
        """Test message without content attribute."""
        log = logging.getLogger('test')
        message = mocker.Mock(spec=[])  # No attributes
        choice = mocker.Mock()
        choice.message = message
        response = mocker.Mock()
        response.choices = [choice]

        result = _extract_response_content(response, log)
        assert result.content is None
        assert result.error is not None


class TestColorDistanceStaticMethod:
    """Test the color_distance function from toml_processing."""

    def test_same_color_distance_is_zero(self):
        """Test that distance between identical colors is zero."""
        from glitchygames.bitmappy.toml_processing import color_distance

        assert color_distance((0, 0, 0), (0, 0, 0)) == 0

    def test_black_to_white_distance(self):
        """Test distance from black to white."""
        from glitchygames.bitmappy.toml_processing import color_distance

        distance = color_distance((0, 0, 0), (255, 255, 255))
        assert distance == 255**2 + 255**2 + 255**2

    def test_single_channel_difference(self):
        """Test distance with only one channel different."""
        from glitchygames.bitmappy.toml_processing import color_distance

        distance = color_distance((100, 0, 0), (200, 0, 0))
        assert distance == 100**2

    def test_symmetry(self):
        """Test that distance is symmetric."""
        from glitchygames.bitmappy.toml_processing import color_distance

        distance_ab = color_distance((10, 20, 30), (40, 50, 60))
        distance_ba = color_distance((40, 50, 60), (10, 20, 30))
        assert distance_ab == distance_ba
