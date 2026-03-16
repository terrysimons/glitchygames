"""Additional coverage tests for sprite generation service.

Tests cover: generate_sprite, refine_sprite, _extract_sprite_metadata edge cases,
_ensure_client, and prompt enhancement logic.
"""

import pytest

from glitchygames.services.config import ServiceConfig
from glitchygames.services.exceptions import AIProviderError
from glitchygames.services.sprite_generation_service import (
    GenerationResult,
    SpriteGenerationService,
)


class TestSpriteGenerationServiceCoverage:
    """Coverage tests for SpriteGenerationService methods."""

    def _make_service(self):
        config = ServiceConfig(ai_provider='anthropic', ai_model='claude-sonnet-4-5')
        return SpriteGenerationService(config)

    # ------------------------------------------------------------------
    # _ensure_client
    # ------------------------------------------------------------------

    def test_ensure_client_returns_cached_client(self, mocker):
        """Test that _ensure_client returns the cached client on second call."""
        service = self._make_service()
        sentinel = object()
        service._client = sentinel

        result = service._ensure_client()

        assert result is sentinel

    def test_ensure_client_init_failure_raises_ai_provider_error(self, mocker):
        """Test AIProviderError when ai.Client() itself raises."""
        service = self._make_service()

        fake_ai = mocker.MagicMock()
        fake_ai.Client.side_effect = RuntimeError('connection refused')
        mocker.patch.dict('sys.modules', {'aisuite': fake_ai})

        with pytest.raises(AIProviderError, match='Failed to initialize AI client'):
            service._ensure_client()

    def test_ensure_client_success(self, mocker):
        """Test _ensure_client succeeds when aisuite is available."""
        service = self._make_service()

        fake_client = mocker.MagicMock()
        fake_ai = mocker.MagicMock()
        fake_ai.Client.return_value = fake_client
        mocker.patch.dict('sys.modules', {'aisuite': fake_ai})

        result = service._ensure_client()

        assert result is fake_client
        assert service._client is fake_client

    # ------------------------------------------------------------------
    # generate_sprite
    # ------------------------------------------------------------------

    def test_generate_sprite_success_toml_only(self, mocker):
        """Test successful sprite generation with valid TOML response."""
        service = self._make_service()

        toml_content = (
            '[sprite]\nname = "star"\npixels = "##"\n\n'
            '[colors."#"]\nred = 255\ngreen = 255\nblue = 0\n'
        )

        fake_message = mocker.MagicMock()
        fake_message.content = toml_content

        fake_choice = mocker.MagicMock()
        fake_choice.message = fake_message

        fake_response = mocker.MagicMock()
        fake_response.choices = [fake_choice]

        fake_client = mocker.MagicMock()
        fake_client.chat.completions.create.return_value = fake_response

        service._client = fake_client

        mocker.patch(
            'glitchygames.services.sprite_generation_service.build_sprite_generation_messages',
            return_value=[{'role': 'user', 'content': 'test'}],
        )
        mocker.patch(
            'glitchygames.services.sprite_generation_service.clean_ai_response',
            return_value=toml_content,
        )
        mocker.patch(
            'glitchygames.services.sprite_generation_service.validate_ai_response',
            return_value=(True, None),
        )

        result = service.generate_sprite(prompt='a yellow star', width=16, height=16)

        assert result.success is True
        assert result.sprite_name == 'star'
        assert result.is_animated is False
        assert result.frame_count == 1
        assert result.toml_content == toml_content

    def test_generate_sprite_validation_failure(self, mocker):
        """Test generate_sprite when AI response fails validation."""
        service = self._make_service()

        fake_message = mocker.MagicMock()
        fake_message.content = 'not valid toml'

        fake_choice = mocker.MagicMock()
        fake_choice.message = fake_message

        fake_response = mocker.MagicMock()
        fake_response.choices = [fake_choice]

        fake_client = mocker.MagicMock()
        fake_client.chat.completions.create.return_value = fake_response

        service._client = fake_client

        mocker.patch(
            'glitchygames.services.sprite_generation_service.build_sprite_generation_messages',
            return_value=[],
        )
        mocker.patch(
            'glitchygames.services.sprite_generation_service.clean_ai_response',
            return_value='cleaned',
        )
        mocker.patch(
            'glitchygames.services.sprite_generation_service.validate_ai_response',
            return_value=(False, 'Missing [sprite] section'),
        )

        result = service.generate_sprite(prompt='bad prompt')

        assert result.success is False
        assert result.error == 'Missing [sprite] section'
        assert result.raw_response == 'not valid toml'

    def test_generate_sprite_api_call_failure(self, mocker):
        """Test generate_sprite raises AIProviderError on API failure."""
        service = self._make_service()

        fake_client = mocker.MagicMock()
        fake_client.chat.completions.create.side_effect = ConnectionError('timeout')

        service._client = fake_client

        mocker.patch(
            'glitchygames.services.sprite_generation_service.build_sprite_generation_messages',
            return_value=[],
        )

        with pytest.raises(AIProviderError, match='AI generation failed'):
            service.generate_sprite(prompt='test')

    def test_generate_sprite_with_model_override(self, mocker):
        """Test generate_sprite uses model override when provided."""
        service = self._make_service()

        toml_content = (
            '[sprite]\nname = "dot"\npixels = "#"\n\n[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n'
        )

        fake_message = mocker.MagicMock()
        fake_message.content = toml_content

        fake_choice = mocker.MagicMock()
        fake_choice.message = fake_message

        fake_response = mocker.MagicMock()
        fake_response.choices = [fake_choice]

        fake_client = mocker.MagicMock()
        fake_client.chat.completions.create.return_value = fake_response

        service._client = fake_client

        mocker.patch(
            'glitchygames.services.sprite_generation_service.build_sprite_generation_messages',
            return_value=[],
        )
        mocker.patch(
            'glitchygames.services.sprite_generation_service.clean_ai_response',
            return_value=toml_content,
        )
        mocker.patch(
            'glitchygames.services.sprite_generation_service.validate_ai_response',
            return_value=(True, None),
        )

        service.generate_sprite(prompt='dot', model='openai:gpt-4o')

        call_kwargs = fake_client.chat.completions.create.call_args.kwargs
        assert call_kwargs['model'] == 'openai:gpt-4o'

    def test_generate_sprite_prompt_enhancement_with_animation_hints(self, mocker):
        """Test that animation parameters are added to the enhanced prompt."""
        service = self._make_service()

        toml_content = (
            '[sprite]\nname = "walk"\npixels = "#"\n\n[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n'
        )

        fake_message = mocker.MagicMock()
        fake_message.content = toml_content

        fake_choice = mocker.MagicMock()
        fake_choice.message = fake_message

        fake_response = mocker.MagicMock()
        fake_response.choices = [fake_choice]

        fake_client = mocker.MagicMock()
        fake_client.chat.completions.create.return_value = fake_response

        service._client = fake_client

        mock_build = mocker.patch(
            'glitchygames.services.sprite_generation_service.build_sprite_generation_messages',
            return_value=[],
        )
        mocker.patch(
            'glitchygames.services.sprite_generation_service.clean_ai_response',
            return_value=toml_content,
        )
        mocker.patch(
            'glitchygames.services.sprite_generation_service.validate_ai_response',
            return_value=(True, None),
        )

        service.generate_sprite(
            prompt='walking character',
            width=16,
            height=16,
            frame_count=4,
            film_strip_count=2,
            animation_duration=1.5,
        )

        # Verify the enhanced prompt was passed to the message builder
        enhanced_prompt = mock_build.call_args.args[0]
        assert '16x16 pixels' in enhanced_prompt
        assert '2 film strips' in enhanced_prompt
        assert '4 frames each' in enhanced_prompt
        assert '1.5 seconds' in enhanced_prompt

    # ------------------------------------------------------------------
    # refine_sprite
    # ------------------------------------------------------------------

    def test_refine_sprite_success(self, mocker):
        """Test successful sprite refinement."""
        service = self._make_service()

        toml_content = (
            '[sprite]\nname = "blue_star"\npixels = "##"\n\n'
            '[colors."#"]\nred = 0\ngreen = 0\nblue = 255\n'
        )

        fake_message = mocker.MagicMock()
        fake_message.content = toml_content

        fake_choice = mocker.MagicMock()
        fake_choice.message = fake_message

        fake_response = mocker.MagicMock()
        fake_response.choices = [fake_choice]

        fake_client = mocker.MagicMock()
        fake_client.chat.completions.create.return_value = fake_response

        service._client = fake_client

        mocker.patch(
            'glitchygames.services.sprite_generation_service.build_refinement_messages',
            return_value=[],
        )
        mocker.patch(
            'glitchygames.services.sprite_generation_service.clean_ai_response',
            return_value=toml_content,
        )
        mocker.patch(
            'glitchygames.services.sprite_generation_service.validate_ai_response',
            return_value=(True, None),
        )

        result = service.refine_sprite(
            prompt='make it blue',
            current_toml='[sprite]\nname = "star"',
        )

        assert result.success is True
        assert result.sprite_name == 'blue_star'

    def test_refine_sprite_validation_failure(self, mocker):
        """Test refine_sprite when validation fails."""
        service = self._make_service()

        fake_message = mocker.MagicMock()
        fake_message.content = 'garbage response'

        fake_choice = mocker.MagicMock()
        fake_choice.message = fake_message

        fake_response = mocker.MagicMock()
        fake_response.choices = [fake_choice]

        fake_client = mocker.MagicMock()
        fake_client.chat.completions.create.return_value = fake_response

        service._client = fake_client

        mocker.patch(
            'glitchygames.services.sprite_generation_service.build_refinement_messages',
            return_value=[],
        )
        mocker.patch(
            'glitchygames.services.sprite_generation_service.clean_ai_response',
            return_value='cleaned',
        )
        mocker.patch(
            'glitchygames.services.sprite_generation_service.validate_ai_response',
            return_value=(False, 'bad TOML'),
        )

        result = service.refine_sprite(
            prompt='make it red',
            current_toml='[sprite]\nname = "star"',
        )

        assert result.success is False
        assert result.error == 'bad TOML'

    def test_refine_sprite_api_call_failure(self, mocker):
        """Test refine_sprite raises AIProviderError on API failure."""
        service = self._make_service()

        fake_client = mocker.MagicMock()
        fake_client.chat.completions.create.side_effect = RuntimeError('API down')

        service._client = fake_client

        mocker.patch(
            'glitchygames.services.sprite_generation_service.build_refinement_messages',
            return_value=[],
        )

        with pytest.raises(AIProviderError, match='AI refinement failed'):
            service.refine_sprite(
                prompt='change color',
                current_toml='[sprite]\nname = "star"',
            )

    # ------------------------------------------------------------------
    # _extract_sprite_metadata edge cases
    # ------------------------------------------------------------------

    def test_extract_metadata_no_sprite_section(self):
        """Test metadata extraction when [sprite] section is missing."""
        service = self._make_service()

        toml_content = '[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n'

        name, is_animated, frame_count = service._extract_sprite_metadata(toml_content)

        assert name == 'unnamed'
        assert is_animated is False
        assert frame_count == 1

    def test_extract_metadata_single_animation_dict(self):
        """Test metadata extraction when animation is a single dict (not a list)."""
        service = self._make_service()

        # This tests the isinstance(animations, dict) branch
        toml_content = (
            '[sprite]\nname = "blink"\n\n[animation]\nnamespace = "idle"\n\n'
            '[[animation.frame]]\nframe_index = 0\npixels = "##"\n\n'
            '[[animation.frame]]\nframe_index = 1\npixels = ".."\n'
        )

        name, is_animated, frame_count = service._extract_sprite_metadata(toml_content)

        assert name == 'blink'
        assert is_animated is True
        assert frame_count == 2

    def test_extract_metadata_animation_without_frames(self):
        """Test metadata extraction when animation section exists but has no frames."""
        service = self._make_service()

        toml_content = '[sprite]\nname = "empty_anim"\n\n[[animation]]\nnamespace = "idle"\n'

        name, is_animated, frame_count = service._extract_sprite_metadata(toml_content)

        assert name == 'empty_anim'
        assert is_animated is True
        assert frame_count == 1  # Stays at default

    def test_extract_metadata_animation_frame_not_list(self):
        """Test metadata extraction when frame is not a list."""
        service = self._make_service()

        # frame is a dict rather than a list of dicts
        toml_content = (
            '[sprite]\nname = "odd"\n\n[[animation]]\nnamespace = "idle"\n\n'
            '[animation.frame]\nframe_index = 0\npixels = "##"\n'
        )

        name, is_animated, frame_count = service._extract_sprite_metadata(toml_content)

        assert name == 'odd'
        assert is_animated is True
        # frame is a dict, not a list, so the len(frames) branch is not reached
        assert frame_count == 1

    # ------------------------------------------------------------------
    # is_animation_request
    # ------------------------------------------------------------------

    def test_is_animation_request_delegates_to_detect(self, mocker):
        """Test that is_animation_request delegates to detect_animation_request."""
        service = self._make_service()

        mock_detect = mocker.patch(
            'glitchygames.services.sprite_generation_service.detect_animation_request',
            return_value=True,
        )

        result = service.is_animation_request('make a walking animation')

        assert result is True
        mock_detect.assert_called_once_with('make a walking animation')

    # ------------------------------------------------------------------
    # GenerationResult dataclass coverage
    # ------------------------------------------------------------------

    def test_generation_result_default_values(self):
        """Test GenerationResult defaults."""
        result = GenerationResult(success=True)

        assert result.toml_content is None
        assert result.sprite_name is None
        assert result.is_animated is False
        assert result.frame_count == 1
        assert result.error is None
        assert result.raw_response is None

    def test_generation_result_all_fields(self):
        """Test GenerationResult with all fields populated."""
        result = GenerationResult(
            success=True,
            toml_content='content',
            sprite_name='hero',
            is_animated=True,
            frame_count=8,
            error=None,
            raw_response='raw',
        )

        assert result.sprite_name == 'hero'
        assert result.is_animated is True
        assert result.frame_count == 8
        assert result.raw_response == 'raw'
