"""Tests for AI sprite generation functionality."""

from glitchygames.ai.sprite_generator import (
    SpriteGenerationPrompt,
    _check_mixed_format,
    _check_truncated_pixel_data,
    _reconstruct_animated_sprite,
    _reconstruct_static_sprite,
    build_refinement_messages,
    build_sprite_generation_messages,
    clean_ai_response,
    detect_animation_request,
    detect_refinement_request,
    format_training_example,
    get_sprite_size_hint,
    validate_ai_response,
)


class TestSpriteGenerationMessages:
    """Tests for build_sprite_generation_messages."""

    def test_basic_message_structure(self):
        """Test basic message structure is correct."""
        messages = build_sprite_generation_messages(
            user_request='Create a red square', training_examples=None,
        )

        assert len(messages) == 4
        assert messages[0]['role'] == 'system'
        assert messages[1]['role'] == 'user'
        assert messages[2]['role'] == 'assistant'
        assert messages[3]['role'] == 'user'
        assert 'Create a red square' in messages[3]['content']

    def test_with_training_examples(self):
        """Test message building with training examples."""
        examples = [
            {
                'name': 'test_sprite',
                'sprite_type': 'static',
                'has_alpha': False,
                'pixels': 'ABC\nDEF',
                'colors': {'A': {'red': 255, 'green': 0, 'blue': 0}},
            },
        ]

        messages = build_sprite_generation_messages(
            user_request='Create a sprite', training_examples=examples, max_examples=3,
        )

        # Check example is included in context
        assert 'test_sprite' in messages[1]['content']

    def test_size_hint_injection(self):
        """Test that size hints are added to request."""
        messages = build_sprite_generation_messages(
            user_request='Create a 32x32 sprite', training_examples=None, include_size_hint=True,
        )

        last_message = messages[3]['content']
        assert '32x32' in last_message
        assert 'IMPORTANT' in last_message

    def test_animation_hint_injection(self):
        """Test that animation hints are added."""
        messages = build_sprite_generation_messages(
            user_request='Create an animated walking sprite',
            training_examples=None,
            include_animation_hint=True,
        )

        last_message = messages[3]['content']
        assert 'ANIMATED' in last_message
        assert '[[animation]]' in last_message

    def test_max_examples_limit(self):
        """Test that example count is limited."""
        examples = [{'name': f'sprite_{i}'} for i in range(10)]

        messages = build_sprite_generation_messages(
            user_request='Create a sprite', training_examples=examples, max_examples=2,
        )

        # Should only include 2 examples
        context = messages[1]['content']
        assert context.count('sprite_0') == 1
        assert context.count('sprite_1') == 1
        assert 'sprite_2' not in context


class TestTrainingExampleFormatting:
    """Tests for format_training_example."""

    def test_static_sprite_formatting(self):
        """Test formatting of static sprite example."""
        example = {
            'name': 'RedSquare',
            'sprite_type': 'static',
            'has_alpha': False,
            'pixels': 'RR\nRR',
            'colors': {'R': {'red': 255, 'green': 0, 'blue': 0}},
        }

        result = format_training_example(example, include_raw=False)

        assert 'RedSquare' in result
        assert 'type=static' in result
        assert '[sprite]' in result
        assert 'pixels' in result
        assert '[colors."R"]' in result
        assert 'red = 255' in result

    def test_animated_sprite_formatting(self):
        """Test formatting of animated sprite example."""
        example = {
            'name': 'WalkingHero',
            'sprite_type': 'animated',
            'has_alpha': False,
            'animations': [
                {
                    'namespace': 'walk',
                    'frame_interval': 0.3,
                    'loop': True,
                    'frame': [{'frame_index': 0, 'pixels': 'AB\nCD'}],
                },
            ],
            'colors': {'A': {'red': 255, 'green': 0, 'blue': 0}},
        }

        result = format_training_example(example, include_raw=False)

        assert 'WalkingHero' in result
        assert 'type=animated' in result
        assert '[[animation]]' in result
        assert 'namespace = "walk"' in result
        assert '[[animation.frame]]' in result

    def test_alpha_sprite_formatting(self):
        """Test formatting includes alpha flag."""
        example = {
            'name': 'TransparentSprite',
            'sprite_type': 'static',
            'has_alpha': True,
            'pixels': 'A',
            'colors': {'A': {'red': 255, 'green': 0, 'blue': 0, 'alpha': 127}},
        }

        result = format_training_example(example, include_raw=False)

        assert 'alpha=yes' in result
        assert 'alpha = 127' in result

    def test_raw_content_preference(self):
        """Test that raw_content is used when available."""
        raw_toml = '[sprite]\nname = "Raw"\npixels = "X"'
        example = {'name': 'test', 'raw_content': raw_toml, 'pixels': 'should_not_appear'}

        result = format_training_example(example, include_raw=True)

        assert raw_toml in result
        assert 'should_not_appear' not in result

    def test_malformed_example_handling(self):
        """Test handling of malformed examples."""
        example = {'name': 'broken'}

        result = format_training_example(example, include_raw=False)

        assert 'broken' in result
        assert '(Format unavailable)' in result


class TestResponseCleaning:
    """Tests for clean_ai_response."""

    def test_remove_code_blocks(self):
        """Test removal of markdown code blocks."""
        content = '```toml\n[sprite]\nname = "test"\n```'

        result = clean_ai_response(content)

        assert '```' not in result  # type: ignore[unsupported-operator]
        assert '[sprite]' in result  # type: ignore[unsupported-operator]
        assert 'name = "test"' in result  # type: ignore[unsupported-operator]

    def test_remove_backticks_only(self):
        """Test removal of code fences."""
        content = '```\n[sprite]\nname = "test"\n```'

        result = clean_ai_response(content)

        assert '```' not in result  # type: ignore[unsupported-operator]
        assert '[sprite]' in result  # type: ignore[unsupported-operator]

    def test_remove_leading_text(self):
        """Test removal of leading explanatory text."""
        content = 'Here\'s your sprite:\n\nSome explanation\n\n[sprite]\nname = "test"'

        result = clean_ai_response(content)

        assert result is not None
        assert result.startswith('[sprite]')
        assert "Here's your sprite" not in result  # type: ignore[unsupported-operator]

    def test_preserve_valid_toml(self):
        """Test that valid TOML is preserved."""
        content = '[sprite]\nname = "test"\n\n[colors."X"]\nred = 255'

        result = clean_ai_response(content)

        assert result == content.strip()

    def test_empty_content(self):
        """Test handling of empty content."""
        assert not clean_ai_response('')
        assert clean_ai_response(None) is None


class TestResponseValidation:
    """Tests for validate_ai_response."""

    def test_valid_static_sprite(self):
        """Test validation of valid static sprite."""
        content = """
[sprite]
name = "test"
pixels = "X"

[colors."X"]
red = 255
green = 0
blue = 0
"""

        is_valid, error = validate_ai_response(content)

        assert is_valid
        assert not error

    def test_valid_animated_sprite(self):
        """Test validation of valid animated sprite."""
        content = """
[sprite]
name = "test"

[[animation]]
namespace = "idle"

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = "X"

[colors."X"]
red = 255
"""

        is_valid, error = validate_ai_response(content)

        assert is_valid
        assert not error

    def test_empty_response(self):
        """Test detection of empty response."""
        is_valid, error = validate_ai_response('')

        assert not is_valid
        assert 'Empty' in error

    def test_error_message_detection(self):
        """Test detection of error messages."""
        content = 'I apologize, but I cannot create that sprite.'

        is_valid, error = validate_ai_response(content)

        assert not is_valid
        assert 'error message' in error

    def test_missing_sprite_section(self):
        """Test detection of missing [sprite] section."""
        content = '[colors."X"]\nred = 255'

        is_valid, error = validate_ai_response(content)

        assert not is_valid
        assert '[sprite]' in error

    def test_missing_colors_section(self):
        """Test detection of missing [colors] section."""
        content = '[sprite]\nname = "test"\npixels = "X"'

        is_valid, error = validate_ai_response(content)

        assert not is_valid
        assert '[colors]' in error

    def test_mixed_format_detection(self):
        """Test detection of mixed static/animated format."""
        content = """
[sprite]
name = "test"
pixels = "X"

[[animation]]
namespace = "idle"

[colors."X"]
red = 255
"""

        is_valid, error = validate_ai_response(content)

        assert not is_valid
        assert 'Mixed' in error

    def test_comma_separated_colors(self):
        """Test detection of comma-separated color values."""
        content = """
[sprite]
name = "test"
pixels = "X"

[colors."X"]
red = 255, 0, 0
"""

        is_valid, error = validate_ai_response(content)

        assert not is_valid
        assert 'comma' in error

    def test_markdown_code_blocks(self):
        """Test detection of uncleaned markdown."""
        content = '```toml\n[sprite]\nname = "test"\n```'

        is_valid, error = validate_ai_response(content)

        assert not is_valid
        assert 'markdown' in error

    def test_truncated_response(self):
        """Test detection of truncated pixel data."""
        # Simulate truncated response with unclosed triple quotes
        content = (
            '[sprite]\nname = "test"\n\n'
            '[[animation.frame]]\nnamespace = "test"\n'
            'frame_index = 0\npixels = """\n'
            '0000000000000000\n0000000000000000\n00'
        )
        # Note: unclosed pixel block with short last line (just "00")

        is_valid, error = validate_ai_response(content)

        assert not is_valid
        assert 'truncated' in error.lower()


class TestSizeHintDetection:
    """Tests for get_sprite_size_hint."""

    def test_simple_size_pattern(self):
        """Test detection of simple size patterns."""
        assert get_sprite_size_hint('Create a 16x16 sprite') == (16, 16)
        assert get_sprite_size_hint('Make it 32x32') == (32, 32)
        assert get_sprite_size_hint('8x8 icon') == (8, 8)

    def test_size_with_spaces(self):
        """Test detection with spaces around x."""
        assert get_sprite_size_hint('16 x 16 sprite') == (16, 16)
        assert get_sprite_size_hint('32  x  32') == (32, 32)

    def test_multiplication_sign(self):
        """Test detection with × (multiplication sign)."""  # noqa: RUF002
        assert get_sprite_size_hint('Create 16×16 sprite') == (16, 16)  # noqa: RUF001

    def test_invalid_sizes(self):
        """Test rejection of invalid sizes."""
        assert get_sprite_size_hint('Create a 0x0 sprite') is None
        assert get_sprite_size_hint('Make it 100x100') is None  # Too large
        assert get_sprite_size_hint('Create sprite') is None

    def test_edge_cases(self):
        """Test edge case sizes."""
        assert get_sprite_size_hint('1x1 sprite') == (1, 1)
        assert get_sprite_size_hint('64x64 sprite') == (64, 64)
        assert get_sprite_size_hint('65x65 sprite') is None  # Out of range


class TestAnimationDetection:
    """Tests for detect_animation_request."""

    def test_animation_keywords(self):
        """Test detection of animation keywords."""
        assert detect_animation_request('Create an animated sprite')
        assert detect_animation_request('Make a walking character')
        assert detect_animation_request('2-frame animation')
        assert detect_animation_request('Create an idle loop')

    def test_static_sprite_request(self):
        """Test that static requests don't trigger animation."""
        assert not detect_animation_request('Create a red square')
        assert not detect_animation_request('Make a coin')
        assert not detect_animation_request('Simple icon')

    def test_case_insensitive(self):
        """Test that detection is case insensitive."""
        assert detect_animation_request('ANIMATED SPRITE')
        assert detect_animation_request('Walking Character')
        assert detect_animation_request('Multi-Frame')

    def test_partial_matches(self):
        """Test that partial keyword matches work."""
        assert detect_animation_request('animation')
        assert detect_animation_request('running')
        assert detect_animation_request('jumping')


class TestRefinementDetection:
    """Tests for detect_refinement_request."""

    def test_refinement_keywords(self):
        """Test detection of refinement keywords."""
        assert detect_refinement_request('Make it bigger')
        assert detect_refinement_request('Change the color to blue')
        assert detect_refinement_request('Add more details')
        assert detect_refinement_request('Use less red')
        assert detect_refinement_request('Make it brighter')

    def test_non_refinement_request(self):
        """Test that non-refinement requests don't trigger detection."""
        assert not detect_refinement_request('Create a red square')
        assert not detect_refinement_request('Generate a dragon')
        assert not detect_refinement_request('32x32 sprite')

    def test_case_insensitive(self):
        """Test that detection is case insensitive."""
        assert detect_refinement_request('MAKE IT BIGGER')
        assert detect_refinement_request('Change Color')
        assert detect_refinement_request('more Details')


class TestRefinementMessages:
    """Tests for build_refinement_messages."""

    def test_basic_refinement_message(self):
        """Test basic refinement message structure."""
        last_sprite = '[sprite]\nname = "test"\npixels = "X"'
        messages = build_refinement_messages(
            user_request='Make it bigger', last_sprite_content=last_sprite,
        )

        assert len(messages) == 4
        assert messages[0]['role'] == 'system'
        assert messages[1]['role'] == 'user'
        assert messages[2]['role'] == 'assistant'
        assert messages[3]['role'] == 'user'

        # Check that last sprite is included in context
        assert last_sprite in messages[3]['content']
        assert 'Make it bigger' in messages[3]['content']

    def test_with_conversation_history(self):
        """Test refinement with existing conversation history."""
        last_sprite = '[sprite]\nname = "test"\npixels = "X"'
        history = [
            {'role': 'user', 'content': 'Create a red square'},
            {'role': 'assistant', 'content': last_sprite},
        ]

        messages = build_refinement_messages(
            user_request='Make it blue',
            last_sprite_content=last_sprite,
            conversation_history=history,
        )

        # Should have system, format, confirmation, history (2), and new request
        assert len(messages) == 6
        assert messages[3]['role'] == 'user'
        assert messages[3]['content'] == 'Create a red square'
        assert messages[4]['role'] == 'assistant'
        assert messages[4]['content'] == last_sprite

    def test_size_hint_in_refinement(self):
        """Test that refinement requests include the user's size request."""
        last_sprite = '[sprite]\nname = "test"\npixels = "X"'
        messages = build_refinement_messages(
            user_request='Make it 32x32', last_sprite_content=last_sprite, include_size_hint=True,
        )

        last_message = messages[-1]['content']
        # Should include user's request (which mentions size)
        assert '32x32' in last_message
        assert last_sprite in last_message

    def test_animation_hint_in_refinement(self):
        """Test that refinement requests include the user's animation request."""
        last_sprite = '[sprite]\nname = "test"\npixels = "X"'
        messages = build_refinement_messages(
            user_request='Make it animated with 2 frames',
            last_sprite_content=last_sprite,
            include_animation_hint=True,
        )

        last_message = messages[-1]['content']
        # Should include user's request (which mentions animation)
        assert 'animated with 2 frames' in last_message
        assert last_sprite in last_message

    def test_preserves_all_frames_in_animated_refinement(self):
        """Test that animated sprite refinements include the full sprite content."""
        # Create a multi-frame animated sprite
        last_sprite = """[sprite]
name = "test"

[[animation]]
namespace = "jump"

[[animation.frame]]
namespace = "jump"
frame_index = 0
pixels = "A"

[[animation.frame]]
namespace = "jump"
frame_index = 1
pixels = "B"

[[animation.frame]]
namespace = "jump"
frame_index = 2
pixels = "C"

[colors."A"]
red = 255
"""
        messages = build_refinement_messages(
            user_request='Make it red', last_sprite_content=last_sprite,
        )

        last_message = messages[-1]['content']
        # Should include the full sprite content (with all frames)
        assert '[[animation.frame]]' in last_message
        assert 'frame_index = 0' in last_message
        assert 'frame_index = 1' in last_message
        assert 'frame_index = 2' in last_message
        # Should include user's request
        assert 'Make it red' in last_message

    def test_static_to_animated_conversion_hint(self):
        """Test that refinement requests include sprite content and user request."""
        last_sprite = '[sprite]\nname = "test"\npixels = "X"\n\n[colors."X"]\nred = 255'
        messages = build_refinement_messages(
            user_request='Make it animated with 2 frames',
            last_sprite_content=last_sprite,
            include_animation_hint=True,
        )

        last_message = messages[-1]['content']
        # Should include the full sprite content
        assert last_sprite in last_message
        # Should include user's request
        assert 'Make it animated with 2 frames' in last_message


class TestSpriteGenerationPrompt:
    """Test SpriteGenerationPrompt constants."""

    def test_format_spec_exists(self):
        assert len(SpriteGenerationPrompt.FORMAT_SPEC) > 0

    def test_system_message_exists(self):
        assert 'sprite' in SpriteGenerationPrompt.SYSTEM_MESSAGE.lower()

    def test_assistant_confirmation_exists(self):
        assert 'TOML' in SpriteGenerationPrompt.ASSISTANT_CONFIRMATION


class TestFormatTrainingExample:
    """Test format_training_example."""

    def test_with_raw_content(self):
        example = {
            'name': 'test_sprite',
            'sprite_type': 'static',
            'has_alpha': False,
            'raw_content': '[sprite]\nname = "test"',
        }
        result = format_training_example(example)
        assert 'test_sprite' in result
        assert '[sprite]' in result

    def test_with_alpha(self):
        example = {
            'name': 'alpha_sprite',
            'sprite_type': 'static',
            'has_alpha': True,
            'raw_content': '[sprite]\nname = "alpha"',
        }
        result = format_training_example(example)
        assert 'alpha=yes' in result

    def test_without_raw_content_static(self):
        example = {
            'name': 'test',
            'sprite_type': 'static',
            'pixels': 'AB\nCD',
            'colors': {
                'A': {'red': 255, 'green': 0, 'blue': 0},
                'B': {'red': 0, 'green': 255, 'blue': 0},
            },
        }
        result = format_training_example(example, include_raw=False)
        assert '[sprite]' in result
        assert 'red = 255' in result

    def test_without_raw_content_animated(self):
        example = {
            'name': 'test',
            'sprite_type': 'animated',
            'animations': [
                {
                    'namespace': 'idle',
                    'frame_interval': 0.5,
                    'loop': True,
                    'frame': [{'frame_index': 0, 'pixels': 'AB'}],
                },
            ],
            'colors': {'A': {'red': 255, 'green': 0, 'blue': 0}},
        }
        result = format_training_example(example, include_raw=False)
        assert '[[animation]]' in result

    def test_fallback_no_data(self):
        example = {'name': 'empty'}
        result = format_training_example(example, include_raw=False)
        assert 'Format unavailable' in result

    def test_error_handling(self):
        # Pass a dict that will trigger KeyError
        example = {'name': 'test'}
        result = format_training_example(example, include_raw=False)
        assert 'test' in result


class TestReconstructStaticSprite:
    """Test _reconstruct_static_sprite."""

    def test_basic(self):
        example = {
            'name': 'test',
            'pixels': 'A',
            'colors': {'A': {'red': 255, 'green': 0, 'blue': 0}},
        }
        result = _reconstruct_static_sprite(example)
        assert '[sprite]' in result
        assert '[colors."A"]' in result

    def test_multiline_pixels(self):
        example = {
            'name': 'test',
            'pixels': 'AB\nCD',
            'colors': {'A': {'red': 0, 'green': 0, 'blue': 0}},
        }
        result = _reconstruct_static_sprite(example)
        assert '"""' in result

    def test_with_alpha(self):
        example = {
            'name': 'test',
            'pixels': 'A',
            'colors': {'A': {'red': 255, 'green': 0, 'blue': 0, 'alpha': 128}},
        }
        result = _reconstruct_static_sprite(example)
        assert 'alpha = 128' in result


class TestReconstructAnimatedSprite:
    """Test _reconstruct_animated_sprite."""

    def test_basic(self):
        example = {
            'name': 'test',
            'animations': [
                {
                    'namespace': 'idle',
                    'frame_interval': 0.5,
                    'loop': True,
                    'frame': [{'frame_index': 0, 'pixels': 'AB'}],
                },
            ],
            'colors': {'A': {'red': 255, 'green': 0, 'blue': 0}},
        }
        result = _reconstruct_animated_sprite(example)
        assert '[[animation]]' in result
        assert '[[animation.frame]]' in result

    def test_with_frame_interval_override(self):
        example = {
            'name': 'test',
            'animations': [
                {
                    'namespace': 'idle',
                    'frame': [{'frame_index': 0, 'pixels': 'A', 'frame_interval': 1.0}],
                },
            ],
            'colors': {},
        }
        result = _reconstruct_animated_sprite(example)
        assert 'frame_interval = 1.0' in result

    def test_skips_non_dict_animations(self):
        example = {
            'name': 'test',
            'animations': ['not_a_dict'],
            'colors': {},
        }
        result = _reconstruct_animated_sprite(example)
        assert '[[animation]]' not in result

    def test_skips_non_dict_frames(self):
        example = {
            'name': 'test',
            'animations': [
                {
                    'namespace': 'idle',
                    'frame': ['not_a_dict'],
                },
            ],
            'colors': {},
        }
        result = _reconstruct_animated_sprite(example)
        assert '[[animation.frame]]' not in result


class TestBuildSpriteGenerationMessages:
    """Test build_sprite_generation_messages."""

    def test_basic(self):
        messages = build_sprite_generation_messages('Create a mushroom sprite')
        assert len(messages) == 4
        assert messages[0]['role'] == 'system'
        assert messages[-1]['role'] == 'user'

    def test_with_size_hint(self):
        messages = build_sprite_generation_messages('Create a 16x16 mushroom')
        assert '16x16' in messages[-1]['content']

    def test_with_animation_hint(self):
        messages = build_sprite_generation_messages('Create an animated walking sprite')
        assert 'ANIMATED' in messages[-1]['content']

    def test_with_training_examples(self):
        examples = [{'name': 'test', 'raw_content': '[sprite]\nname = "test"'}]
        messages = build_sprite_generation_messages('Create a sprite', training_examples=examples)
        # System + format + confirmation + user
        assert len(messages) == 4
        assert 'Example sprites' in messages[1]['content']

    def test_no_size_hint(self):
        messages = build_sprite_generation_messages('Create a mushroom', include_size_hint=False)
        assert len(messages) == 4

    def test_no_animation_hint(self):
        messages = build_sprite_generation_messages(
            'Create an animated mushroom', include_animation_hint=False,
        )
        assert 'ANIMATED' not in messages[-1]['content']


class TestCheckTruncatedPixelData:
    """Test _check_truncated_pixel_data."""

    def test_no_pixel_data(self):
        is_valid, _msg = _check_truncated_pixel_data('[sprite]\nname = "test"')
        assert is_valid is True

    def test_valid_pixel_data(self):
        content = '[sprite]\npixels = """\nABCDEFGHIJKLMNOP\nABCDEFGHIJKLMNOP\n"""'
        is_valid, _msg = _check_truncated_pixel_data(content)
        assert is_valid is True

    def test_truncated_pixel_data(self):
        # Last line much shorter than previous
        content = 'pixels = """ABCDEFGHIJKLMNOPQRSTUVWX\nABCDEFGHIJKLMNOPQRSTUVWX\nA'
        is_valid, msg = _check_truncated_pixel_data(content)
        assert is_valid is False
        assert 'truncated' in msg.lower()


class TestCheckMixedFormat:
    """Test _check_mixed_format."""

    def test_static_only(self):
        content = '[sprite]\nname = "test"\npixels = "AB"'
        is_valid, _msg = _check_mixed_format(content)
        assert is_valid is True

    def test_animated_only(self):
        content = '[sprite]\nname = "test"\n[[animation]]\nnamespace = "idle"'
        is_valid, _msg = _check_mixed_format(content)
        assert is_valid is True

    def test_mixed_format_invalid(self):
        content = '[sprite]\npixels = "AB"\n[[animation]]\nnamespace = "idle"'
        is_valid, msg = _check_mixed_format(content)
        assert is_valid is False
        assert 'Mixed' in msg


class TestValidateAiResponse:
    """Test validate_ai_response."""

    def test_empty_response(self):
        is_valid, _msg = validate_ai_response('')
        assert is_valid is False

    def test_error_message(self):
        is_valid, _msg = validate_ai_response('I apologize, I cannot generate that sprite.')
        assert is_valid is False

    def test_markdown_code_blocks(self):
        is_valid, _msg = validate_ai_response('```toml\n[sprite]\n```')
        assert is_valid is False

    def test_missing_sprite_section(self):
        is_valid, _msg = validate_ai_response('[colors."A"]\nred = 255')
        assert is_valid is False

    def test_missing_colors_section(self):
        is_valid, _msg = validate_ai_response('[sprite]\nname = "test"\npixels = "A"')
        assert is_valid is False

    def test_comma_separated_colors(self):
        is_valid, _msg = validate_ai_response(
            '[sprite]\nname="test"\n[colors."A"]\nred = 255, green = 0',
        )
        assert is_valid is False

    def test_valid_response(self):
        content = (
            '[sprite]\nname = "test"\npixels = "A"\n[colors."A"]\nred = 255\ngreen = 0\nblue = 0'
        )
        is_valid, _msg = validate_ai_response(content)
        assert is_valid is True

    def test_error_phrase_with_toml_structure(self):
        # Has error phrase but also has TOML structure - should pass
        content = '[sprite]\nname = "I apologize sprite"\n[colors."A"]\nred = 255'
        is_valid, _msg = validate_ai_response(content)
        assert is_valid is True


class TestCleanAiResponse:
    """Test clean_ai_response."""

    def test_empty(self):
        assert not clean_ai_response('')

    def test_none(self):
        assert clean_ai_response(None) is None

    def test_remove_code_fences(self):
        content = '```toml\n[sprite]\nname = "test"\n```'
        result = clean_ai_response(content)
        assert '```' not in result  # type: ignore[unsupported-operator]
        assert '[sprite]' in result  # type: ignore[unsupported-operator]

    def test_remove_leading_text(self):
        content = 'Here is your sprite:\n[sprite]\nname = "test"'
        result = clean_ai_response(content)
        assert result is not None
        assert result.startswith('[sprite]')

    def test_clean_content(self):
        content = '[sprite]\nname = "test"'
        result = clean_ai_response(content)
        assert result == content


class TestGetSpriteSizeHint:
    """Test get_sprite_size_hint."""

    def test_basic_16x16(self):
        result = get_sprite_size_hint('Create a 16x16 mushroom')
        assert result == (16, 16)

    def test_32x32(self):
        result = get_sprite_size_hint('Make a 32x32 sprite')
        assert result == (32, 32)

    def test_no_size(self):
        result = get_sprite_size_hint('Create a mushroom sprite')
        assert result is None

    def test_too_large(self):
        result = get_sprite_size_hint('Create a 256x256 sprite')
        assert result is None

    def test_with_unicode_x(self):
        result = get_sprite_size_hint('Create a 8\u00d78 sprite')
        assert result == (8, 8)


class TestDetectAnimationRequest:
    """Test detect_animation_request."""

    def test_animated_keyword(self):
        assert detect_animation_request('Create an animated sprite') is True

    def test_walking_keyword(self):
        assert detect_animation_request('Create a walking character') is True

    def test_idle_keyword(self):
        assert detect_animation_request('Create an idle animation') is True

    def test_no_animation(self):
        assert detect_animation_request('Create a static mushroom') is False

    def test_multi_frame(self):
        assert detect_animation_request('Create a multi-frame explosion') is True


class TestDetectRefinementRequest:
    """Test detect_refinement_request."""

    def test_make_it(self):
        assert detect_refinement_request('Make it bigger') is True

    def test_change(self):
        assert detect_refinement_request('Change the color to red') is True

    def test_brighter(self):
        assert detect_refinement_request('Make it brighter') is True

    def test_add(self):
        assert detect_refinement_request('Add a hat') is True

    def test_not_refinement(self):
        assert detect_refinement_request('Create a mushroom sprite') is False

    def test_give_him(self):
        assert detect_refinement_request('Give him a sword') is True


class TestBuildRefinementMessages:
    """Test build_refinement_messages."""

    def test_basic(self):
        messages = build_refinement_messages(
            'Make it red',
            '[sprite]\nname = "test"\npixels = "A"\n[colors."A"]\nred = 0\ngreen = 0\nblue = 255',
        )
        assert len(messages) >= 4
        assert messages[0]['role'] == 'system'

    def test_with_conversation_history(self):
        history = [
            {'role': 'user', 'content': 'Create a mushroom'},
            {'role': 'assistant', 'content': '[sprite]...'},
        ]
        messages = build_refinement_messages(
            'Make it bigger',
            '[sprite]\nname = "test"',
            conversation_history=history,
        )
        assert len(messages) >= 6

    def test_with_size_hint(self):
        messages = build_refinement_messages(
            'Make it 32x32',
            '[sprite]\nname = "test"',
        )
        last_content = messages[-1]['content']
        assert '32x32' in last_content

    def test_with_animation_hint(self):
        messages = build_refinement_messages(
            'Make it animated with walking frames',
            '[sprite]\nname = "test"',
        )
        last_content = messages[-1]['content']
        assert 'ANIMATED' in last_content
