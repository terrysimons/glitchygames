"""Tests for AI sprite generation functionality."""

import pytest

from glitchygames.ai.sprite_generator import (
    build_sprite_generation_messages,
    clean_ai_response,
    detect_animation_request,
    format_training_example,
    get_sprite_size_hint,
    validate_ai_response,
)


class TestSpriteGenerationMessages:
    """Tests for build_sprite_generation_messages."""

    def test_basic_message_structure(self):
        """Test basic message structure is correct."""
        messages = build_sprite_generation_messages(
            user_request="Create a red square",
            training_examples=None
        )

        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"
        assert messages[3]["role"] == "user"
        assert "Create a red square" in messages[3]["content"]

    def test_with_training_examples(self):
        """Test message building with training examples."""
        examples = [
            {
                "name": "test_sprite",
                "sprite_type": "static",
                "has_alpha": False,
                "pixels": "ABC\nDEF",
                "colors": {
                    "A": {"red": 255, "green": 0, "blue": 0}
                }
            }
        ]

        messages = build_sprite_generation_messages(
            user_request="Create a sprite",
            training_examples=examples,
            max_examples=3
        )

        # Check example is included in context
        assert "test_sprite" in messages[1]["content"]

    def test_size_hint_injection(self):
        """Test that size hints are added to request."""
        messages = build_sprite_generation_messages(
            user_request="Create a 32x32 sprite",
            training_examples=None,
            include_size_hint=True
        )

        last_message = messages[3]["content"]
        assert "32x32" in last_message
        assert "IMPORTANT" in last_message

    def test_animation_hint_injection(self):
        """Test that animation hints are added."""
        messages = build_sprite_generation_messages(
            user_request="Create an animated walking sprite",
            training_examples=None,
            include_animation_hint=True
        )

        last_message = messages[3]["content"]
        assert "ANIMATED" in last_message
        assert "[[animation]]" in last_message

    def test_max_examples_limit(self):
        """Test that example count is limited."""
        examples = [{"name": f"sprite_{i}"} for i in range(10)]

        messages = build_sprite_generation_messages(
            user_request="Create a sprite",
            training_examples=examples,
            max_examples=2
        )

        # Should only include 2 examples
        context = messages[1]["content"]
        assert context.count("sprite_0") == 1
        assert context.count("sprite_1") == 1
        assert "sprite_2" not in context


class TestTrainingExampleFormatting:
    """Tests for format_training_example."""

    def test_static_sprite_formatting(self):
        """Test formatting of static sprite example."""
        example = {
            "name": "RedSquare",
            "sprite_type": "static",
            "has_alpha": False,
            "pixels": "RR\nRR",
            "colors": {
                "R": {"red": 255, "green": 0, "blue": 0}
            }
        }

        result = format_training_example(example, include_raw=False)

        assert "RedSquare" in result
        assert "type=static" in result
        assert "[sprite]" in result
        assert "pixels" in result
        assert '[colors."R"]' in result
        assert "red = 255" in result

    def test_animated_sprite_formatting(self):
        """Test formatting of animated sprite example."""
        example = {
            "name": "WalkingHero",
            "sprite_type": "animated",
            "has_alpha": False,
            "animations": [
                {
                    "namespace": "walk",
                    "frame_interval": 0.3,
                    "loop": True,
                    "frame": [
                        {
                            "frame_index": 0,
                            "pixels": "AB\nCD"
                        }
                    ]
                }
            ],
            "colors": {
                "A": {"red": 255, "green": 0, "blue": 0}
            }
        }

        result = format_training_example(example, include_raw=False)

        assert "WalkingHero" in result
        assert "type=animated" in result
        assert "[[animation]]" in result
        assert "namespace = \"walk\"" in result
        assert "[[animation.frame]]" in result

    def test_alpha_sprite_formatting(self):
        """Test formatting includes alpha flag."""
        example = {
            "name": "TransparentSprite",
            "sprite_type": "static",
            "has_alpha": True,
            "pixels": "A",
            "colors": {
                "A": {"red": 255, "green": 0, "blue": 0, "alpha": 127}
            }
        }

        result = format_training_example(example, include_raw=False)

        assert "alpha=yes" in result
        assert "alpha = 127" in result

    def test_raw_content_preference(self):
        """Test that raw_content is used when available."""
        raw_toml = "[sprite]\nname = \"Raw\"\npixels = \"X\""
        example = {
            "name": "test",
            "raw_content": raw_toml,
            "pixels": "should_not_appear"
        }

        result = format_training_example(example, include_raw=True)

        assert raw_toml in result
        assert "should_not_appear" not in result

    def test_malformed_example_handling(self):
        """Test handling of malformed examples."""
        example = {"name": "broken"}

        result = format_training_example(example, include_raw=False)

        assert "broken" in result
        assert "(Format unavailable)" in result


class TestResponseCleaning:
    """Tests for clean_ai_response."""

    def test_remove_code_blocks(self):
        """Test removal of markdown code blocks."""
        content = "```toml\n[sprite]\nname = \"test\"\n```"

        result = clean_ai_response(content)

        assert "```" not in result
        assert "[sprite]" in result
        assert "name = \"test\"" in result

    def test_remove_backticks_only(self):
        """Test removal of code fences."""
        content = "```\n[sprite]\nname = \"test\"\n```"

        result = clean_ai_response(content)

        assert "```" not in result
        assert "[sprite]" in result

    def test_remove_leading_text(self):
        """Test removal of leading explanatory text."""
        content = "Here's your sprite:\n\nSome explanation\n\n[sprite]\nname = \"test\""

        result = clean_ai_response(content)

        assert result.startswith("[sprite]")
        assert "Here's your sprite" not in result

    def test_preserve_valid_toml(self):
        """Test that valid TOML is preserved."""
        content = '[sprite]\nname = "test"\n\n[colors."X"]\nred = 255'

        result = clean_ai_response(content)

        assert result == content.strip()

    def test_empty_content(self):
        """Test handling of empty content."""
        assert clean_ai_response("") == ""
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
        assert error == ""

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
        assert error == ""

    def test_empty_response(self):
        """Test detection of empty response."""
        is_valid, error = validate_ai_response("")

        assert not is_valid
        assert "Empty" in error

    def test_error_message_detection(self):
        """Test detection of error messages."""
        content = "I apologize, but I cannot create that sprite."

        is_valid, error = validate_ai_response(content)

        assert not is_valid
        assert "error message" in error

    def test_missing_sprite_section(self):
        """Test detection of missing [sprite] section."""
        content = '[colors."X"]\nred = 255'

        is_valid, error = validate_ai_response(content)

        assert not is_valid
        assert "[sprite]" in error

    def test_missing_colors_section(self):
        """Test detection of missing [colors] section."""
        content = '[sprite]\nname = "test"\npixels = "X"'

        is_valid, error = validate_ai_response(content)

        assert not is_valid
        assert "[colors]" in error

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
        assert "Mixed" in error

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
        assert "comma" in error

    def test_markdown_code_blocks(self):
        """Test detection of uncleaned markdown."""
        content = "```toml\n[sprite]\nname = \"test\"\n```"

        is_valid, error = validate_ai_response(content)

        assert not is_valid
        assert "markdown" in error

    def test_truncated_response(self):
        """Test detection of truncated pixel data."""
        # Simulate truncated response with unclosed triple quotes
        content = '[sprite]\nname = "test"\n\n[[animation.frame]]\nnamespace = "test"\nframe_index = 0\npixels = """\n0000000000000000\n0000000000000000\n00'
        # Note: unclosed pixel block with short last line (just "00")

        is_valid, error = validate_ai_response(content)

        assert not is_valid
        assert "truncated" in error.lower()


class TestSizeHintDetection:
    """Tests for get_sprite_size_hint."""

    def test_simple_size_pattern(self):
        """Test detection of simple size patterns."""
        assert get_sprite_size_hint("Create a 16x16 sprite") == (16, 16)
        assert get_sprite_size_hint("Make it 32x32") == (32, 32)
        assert get_sprite_size_hint("8x8 icon") == (8, 8)

    def test_size_with_spaces(self):
        """Test detection with spaces around x."""
        assert get_sprite_size_hint("16 x 16 sprite") == (16, 16)
        assert get_sprite_size_hint("32  x  32") == (32, 32)

    def test_multiplication_sign(self):
        """Test detection with × (multiplication sign)."""
        assert get_sprite_size_hint("Create 16×16 sprite") == (16, 16)

    def test_invalid_sizes(self):
        """Test rejection of invalid sizes."""
        assert get_sprite_size_hint("Create a 0x0 sprite") is None
        assert get_sprite_size_hint("Make it 100x100") is None  # Too large
        assert get_sprite_size_hint("Create sprite") is None

    def test_edge_cases(self):
        """Test edge case sizes."""
        assert get_sprite_size_hint("1x1 sprite") == (1, 1)
        assert get_sprite_size_hint("64x64 sprite") == (64, 64)
        assert get_sprite_size_hint("65x65 sprite") is None  # Out of range


class TestAnimationDetection:
    """Tests for detect_animation_request."""

    def test_animation_keywords(self):
        """Test detection of animation keywords."""
        assert detect_animation_request("Create an animated sprite")
        assert detect_animation_request("Make a walking character")
        assert detect_animation_request("2-frame animation")
        assert detect_animation_request("Create an idle loop")

    def test_static_sprite_request(self):
        """Test that static requests don't trigger animation."""
        assert not detect_animation_request("Create a red square")
        assert not detect_animation_request("Make a coin")
        assert not detect_animation_request("Simple icon")

    def test_case_insensitive(self):
        """Test that detection is case insensitive."""
        assert detect_animation_request("ANIMATED SPRITE")
        assert detect_animation_request("Walking Character")
        assert detect_animation_request("Multi-Frame")

    def test_partial_matches(self):
        """Test that partial keyword matches work."""
        assert detect_animation_request("animation")
        assert detect_animation_request("running")
        assert detect_animation_request("jumping")
