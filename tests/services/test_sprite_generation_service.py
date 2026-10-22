"""Tests for sprite generation service.

The AI client (aisuite) is the boundary and is replaced with a fake.
"""

import types

import pytest

from glitchygames.services.config import ServiceConfig
from glitchygames.services.exceptions import AIProviderError
from glitchygames.services.sprite_generation_service import (
    GenerationResult,
    SpriteGenerationService,
)


class TestGenerationResult:
    """Test suite for GenerationResult dataclass."""

    def test_successful_result(self):
        """Test successful generation result."""
        result = GenerationResult(
            success=True,
            toml_content="[sprite]\nname = 'test'",
            sprite_name='test',
            is_animated=False,
            frame_count=1,
        )

        assert result.success is True
        assert result.sprite_name == 'test'
        assert result.error is None

    def test_failed_result(self):
        """Test failed generation result."""
        result = GenerationResult(
            success=False,
            error='AI response invalid',
        )

        assert result.success is False
        assert result.toml_content is None
        assert result.error == 'AI response invalid'


class TestSpriteGenerationService:
    """Test suite for SpriteGenerationService."""

    def test_initialization_with_config(self):
        """Test service initialization with custom config."""
        config = ServiceConfig(ai_provider='openai', ai_model='gpt-4')
        service = SpriteGenerationService(config)

        assert service.config.ai_provider == 'openai'
        assert service.config.ai_model == 'gpt-4'

    def test_initialization_default_config(self):
        """Test service initialization with default config."""
        service = SpriteGenerationService()

        assert service.config is not None
        assert service._client is None  # Lazy initialization

    def test_ensure_client_no_aisuite(self, mocker):
        """Test that AIProviderError is raised when aisuite is not available."""
        service = SpriteGenerationService()

        mocker.patch.dict('sys.modules', {'aisuite': None})
        # Mock import to fail
        mocker.patch('builtins.__import__', side_effect=ImportError("No module named 'aisuite'"))
        # This should raise an error on import attempt
        with pytest.raises(AIProviderError):
            service._ensure_client()

    def test_is_animation_request_true(self):
        """Test animation detection for animation keywords."""
        service = SpriteGenerationService()

        assert service.is_animation_request('create a walking animation') is True
        assert service.is_animation_request('make a 2-frame idle sprite') is True
        assert service.is_animation_request('bouncing ball') is True

    def test_is_animation_request_false(self):
        """Test animation detection for static requests."""
        service = SpriteGenerationService()

        assert service.is_animation_request('16x16 red heart') is False
        assert service.is_animation_request('simple sword sprite') is False

    def test_extract_sprite_metadata_static(self):
        """Test metadata extraction from static sprite."""
        service = SpriteGenerationService()

        toml_content = """
[sprite]
name = "heart"
pixels = \"\"\"
##
##
\"\"\"

[colors."#"]
red = 255
green = 0
blue = 0
"""
        name, is_animated, frame_count = service._extract_sprite_metadata(toml_content)

        assert name == 'heart'
        assert is_animated is False
        assert frame_count == 1

    def test_extract_sprite_metadata_animated(self):
        """Test metadata extraction from animated sprite."""
        service = SpriteGenerationService()

        toml_content = """
[sprite]
name = "blink"

[[animation]]
namespace = "idle"
frame_interval = 0.5

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = "##"

[[animation.frame]]
namespace = "idle"
frame_index = 1
pixels = ".."

[colors."#"]
red = 255
green = 255
blue = 255

[colors."."]
red = 0
green = 0
blue = 0
"""
        name, is_animated, frame_count = service._extract_sprite_metadata(toml_content)

        assert name == 'blink'
        assert is_animated is True
        assert frame_count == 2

    def test_extract_sprite_metadata_invalid_toml(self):
        """Test metadata extraction with invalid TOML."""
        service = SpriteGenerationService()

        toml_content = 'this is not valid toml {'

        name, is_animated, frame_count = service._extract_sprite_metadata(toml_content)

        assert name == 'unknown'
        assert is_animated is False
        assert frame_count == 1


VALID_STATIC_TOML = """[sprite]
name = "heart"
pixels = \"\"\"
##
##
\"\"\"

[colors."#"]
red = 255
green = 0
blue = 0"""

VALID_ANIMATED_TOML = """[sprite]
name = "spinner"

[[animation]]
namespace = "spin"

[[animation.frame]]
pixels = "#"

[[animation.frame]]
pixels = "#"

[[animation.frame]]
pixels = "#"

[[animation]]
namespace = "rest"

[[animation.frame]]
pixels = "#"

[colors."#"]
red = 1
green = 2
blue = 3"""


class FakeAIClient:
    """Stands in for aisuite.Client: answers a scripted reply and records the requests."""

    def __init__(self, *, reply):
        """Answer `reply` to every request."""
        self.reply = reply
        self.requests: list[dict] = []
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self._create),
        )

    def _create(self, **request):
        self.requests.append(request)
        if isinstance(self.reply, Exception):
            raise self.reply
        message = types.SimpleNamespace(content=self.reply)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


def _service_answering(reply):
    """Build a service whose AI client answers `reply` (a string, None or an exception).

    Returns:
        The service and its fake client.

    """
    service = SpriteGenerationService(ServiceConfig(ai_provider='anthropic', ai_model='model-x'))
    client = FakeAIClient(reply=reply)
    service._client = client
    return service, client


class TestEnsureClient:
    """_ensure_client imports aisuite lazily, builds one client and reuses it."""

    def test_builds_the_client_once(self, mocker):
        """The client comes from aisuite.Client and is cached for later calls."""
        client = object()
        fake_aisuite = types.SimpleNamespace(Client=mocker.Mock(return_value=client))
        mocker.patch.dict('sys.modules', {'aisuite': fake_aisuite})
        service = SpriteGenerationService(ServiceConfig(ai_provider='openai', ai_model='m'))

        assert service._ensure_client() is client
        assert service._ensure_client() is client
        fake_aisuite.Client.assert_called_once_with()
        assert service._ai_module is fake_aisuite

    def test_missing_aisuite_names_the_install(self, mocker):
        """With aisuite not importable: an AIProviderError with no provider and the ImportError."""
        mocker.patch.dict('sys.modules', {'aisuite': None})
        service = SpriteGenerationService(ServiceConfig(ai_provider='openai', ai_model='m'))

        with pytest.raises(AIProviderError, match='aisuite is not installed') as raised:
            service._ensure_client()

        assert raised.value.provider is None
        assert isinstance(raised.value.original_error, ImportError)

    def test_client_construction_failure(self, mocker):
        """A client that cannot be built gives an AIProviderError naming the provider."""
        failure = RuntimeError('missing API key')
        fake_aisuite = types.SimpleNamespace(Client=mocker.Mock(side_effect=failure))
        mocker.patch.dict('sys.modules', {'aisuite': fake_aisuite})
        service = SpriteGenerationService(ServiceConfig(ai_provider='openai', ai_model='m'))

        with pytest.raises(AIProviderError, match='Failed to initialize AI client') as raised:
            service._ensure_client()

        assert raised.value.provider == 'openai'
        assert raised.value.original_error is failure
        assert service._client is None


class TestBuildEnhancedPrompt:
    """_build_enhanced_prompt appends size and animation hints in parentheses."""

    def test_no_hints_keeps_the_prompt(self):
        """Without hints the prompt is unchanged."""
        service = SpriteGenerationService(ServiceConfig())

        assert service._build_enhanced_prompt('a sword') == 'a sword'

    def test_size_needs_both_dimensions(self):
        """A width alone adds no size hint."""
        service = SpriteGenerationService(ServiceConfig())

        assert service._build_enhanced_prompt('a sword', width=16) == 'a sword'

    def test_all_hints(self):
        """Size, film strips, frames and duration are joined in order."""
        service = SpriteGenerationService(ServiceConfig())

        enhanced = service._build_enhanced_prompt(
            'a slime',
            width=32,
            height=24,
            frame_count=4,
            film_strip_count=2,
            animation_duration=1.5,
        )

        assert enhanced == (
            'a slime (32x24 pixels; 2 film strips, 4 frames each, animated across 1.5 seconds)'
        )

    def test_a_single_film_strip_is_not_mentioned(self):
        """film_strip_count of 1 adds nothing, and alone it leaves the prompt unchanged."""
        service = SpriteGenerationService(ServiceConfig())

        assert service._build_enhanced_prompt('a coin', film_strip_count=1) == 'a coin'
        assert (
            service._build_enhanced_prompt('a coin', film_strip_count=1, frame_count=3)
            == 'a coin (3 frames each)'
        )


class TestGenerateSprite:
    """generate_sprite sends the built messages and validates the reply."""

    def test_successful_generation(self):
        """A valid reply gives a successful result with the sprite's metadata."""
        service, client = _service_answering(VALID_STATIC_TOML)

        result = service.generate_sprite('a heart', width=8, height=8)

        assert result.success is True
        assert result.toml_content == VALID_STATIC_TOML
        assert result.sprite_name == 'heart'
        assert result.is_animated is False
        assert result.frame_count == 1
        assert result.raw_response == VALID_STATIC_TOML
        (request,) = client.requests
        assert request['model'] == 'anthropic:model-x'
        assert request['max_tokens'] == 8192
        assert 'a heart (8x8 pixels)' in request['messages'][-1]['content']

    def test_model_override_and_training_examples(self):
        """A model override is used; training examples reach the prompt."""
        service, client = _service_answering(VALID_STATIC_TOML)
        example = {'name': 'example', 'raw_content': '[sprite]\nname = "example_marker"'}

        service.generate_sprite('a heart', model='openai:gpt-x', training_examples=[example])

        request = client.requests[0]
        assert request['model'] == 'openai:gpt-x'
        assert any('example_marker' in message['content'] for message in request['messages'])

    def test_markdown_wrapped_reply_is_cleaned(self):
        """A reply in a ```toml fence is cleaned before validation; raw_response keeps it."""
        raw_reply = f'Here you go:\n```toml\n{VALID_STATIC_TOML}\n```'
        service, _ = _service_answering(raw_reply)

        result = service.generate_sprite('a heart')

        assert result.success is True
        assert result.toml_content == VALID_STATIC_TOML
        assert result.raw_response == raw_reply

    def test_animated_reply_counts_the_longest_animation(self):
        """frame_count is the longest animation's frame count."""
        service, _ = _service_answering(VALID_ANIMATED_TOML)

        result = service.generate_sprite('a spinning thing')

        assert result.success is True
        assert result.is_animated is True
        assert result.frame_count == 3

    def test_empty_reply(self):
        """A None reply gives 'AI returned empty response'."""
        service, _ = _service_answering(None)

        result = service.generate_sprite('a heart')

        assert result.success is False
        assert result.error == 'AI returned empty response'
        assert result.raw_response is None

    def test_invalid_reply(self):
        """A reply missing the colors section fails validation with that error."""
        raw_reply = '[sprite]\nname = "x"'
        service, _ = _service_answering(raw_reply)

        result = service.generate_sprite('a heart')

        assert result.success is False
        assert result.error == 'Missing [colors] section'
        assert result.raw_response == raw_reply

    def test_blank_reply_fails_validation(self):
        """An empty-string reply is cleaned to '' and fails as an empty response."""
        service, _ = _service_answering('')

        result = service.generate_sprite('a heart')

        assert result.success is False
        assert result.error == 'Empty response'

    def test_api_failure_raises_provider_error(self):
        """An exception from the API becomes an AIProviderError naming the provider."""
        failure = ConnectionError('timed out')
        service, _ = _service_answering(failure)

        with pytest.raises(AIProviderError, match='AI generation failed: timed out') as raised:
            service.generate_sprite('a heart')

        assert raised.value.provider == 'anthropic'
        assert raised.value.original_error is failure


class TestRefineSprite:
    """refine_sprite sends the current sprite and history and validates the reply."""

    def test_successful_refinement(self):
        """The current TOML and the history reach the request; the reply is validated."""
        service, client = _service_answering(VALID_STATIC_TOML)
        history = [
            {'role': 'user', 'content': 'earlier request'},
            {'role': 'assistant', 'content': 'earlier sprite'},
        ]

        result = service.refine_sprite(
            'make it red', '[sprite]\nname = "old"', conversation_history=history
        )

        assert result.success is True
        assert result.sprite_name == 'heart'
        request = client.requests[0]
        assert request['model'] == 'anthropic:model-x'
        assert request['max_tokens'] == 8192
        assert request['messages'][3:5] == history
        assert 'name = "old"' in request['messages'][-1]['content']
        assert 'make it red' in request['messages'][-1]['content']

    def test_api_failure_raises_provider_error(self):
        """An exception from the API becomes an AIProviderError."""
        failure = RuntimeError('overloaded')
        service, _ = _service_answering(failure)

        with pytest.raises(AIProviderError, match='AI refinement failed: overloaded') as raised:
            service.refine_sprite('make it red', VALID_STATIC_TOML)

        assert raised.value.original_error is failure

    def test_empty_reply(self):
        """A None reply gives an unsuccessful result."""
        service, _ = _service_answering(None)

        result = service.refine_sprite('make it red', VALID_STATIC_TOML)

        assert result.success is False
        assert result.error == 'AI returned empty response'


class TestExtractSpriteMetadataShapes:
    """_extract_sprite_metadata handles every shape the animation key can take."""

    def test_single_animation_table(self):
        """A single [animation] table counts its frames."""
        service = SpriteGenerationService(ServiceConfig())
        toml_content = """
[sprite]
name = "single"

[animation]
namespace = "idle"

[[animation.frame]]
pixels = "#"

[[animation.frame]]
pixels = "#"
"""
        assert service._extract_sprite_metadata(toml_content) == ('single', True, 2)

    def test_animations_without_frames_and_unnamed_sprite(self):
        """Animations with no frames leave the count at 1; a missing name is 'unnamed'."""
        service = SpriteGenerationService(ServiceConfig())
        toml_content = """
[[animation]]
namespace = "empty"
"""
        assert service._extract_sprite_metadata(toml_content) == ('unnamed', True, 1)

    def test_animation_of_another_type(self):
        """A scalar animation value is animated with the default count."""
        service = SpriteGenerationService(ServiceConfig())

        assert service._extract_sprite_metadata('animation = "yes"') == ('unnamed', True, 1)
