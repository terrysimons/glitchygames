"""Tests for glitchygames.ai.sprite_generator module - AI sprite generation helpers."""

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
                }
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
                }
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
                }
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
                }
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
            'Create an animated mushroom', include_animation_hint=False
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
            '[sprite]\nname="test"\n[colors."A"]\nred = 255, green = 0'
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
