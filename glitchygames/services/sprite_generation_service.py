"""Sprite generation service using AI providers via aisuite.

This service wraps the AI sprite generation functionality, providing a clean
interface for generating and refining sprites from text prompts.
"""

import logging
from dataclasses import dataclass
from typing import Any

from glitchygames.ai.sprite_generator import (
    build_refinement_messages,
    build_sprite_generation_messages,
    clean_ai_response,
    detect_animation_request,
    validate_ai_response,
)
from glitchygames.services.config import ServiceConfig
from glitchygames.services.exceptions import AIProviderError

LOG = logging.getLogger("glitchygames.services.sprite_generation")


@dataclass
class GenerationResult:
    """Result of a sprite generation request.

    Attributes:
        success: Whether the generation was successful
        toml_content: Generated TOML content (if successful)
        sprite_name: Extracted sprite name from TOML
        is_animated: Whether the sprite has animation
        frame_count: Number of frames (1 for static sprites)
        error: Error message (if unsuccessful)
        raw_response: Raw AI response before cleaning

    """

    success: bool
    toml_content: str | None = None
    sprite_name: str | None = None
    is_animated: bool = False
    frame_count: int = 1
    error: str | None = None
    raw_response: str | None = None


class SpriteGenerationService:
    """Service for generating sprites using AI providers.

    This service handles communication with AI providers via aisuite,
    building prompts, validating responses, and extracting sprite metadata.
    """

    def __init__(self, config: ServiceConfig | None = None):
        """Initialize the sprite generation service.

        Args:
            config: Service configuration. Uses defaults if not provided.

        """
        self.config = config or ServiceConfig.from_env()
        self._client = None
        self._ai_module = None

    def _ensure_client(self) -> Any:
        """Lazily initialize the AI client.

        Returns:
            aisuite Client instance

        Raises:
            AIProviderError: If aisuite is not available

        """
        if self._client is not None:
            return self._client

        # Import aisuite lazily
        try:
            import aisuite as ai

            self._ai_module = ai
        except ImportError as e:
            raise AIProviderError(
                "aisuite is not installed. Install with: pip install aisuite",
                provider=None,
                original_error=e,
            ) from e

        LOG.info(f"Initializing AI client for provider: {self.config.ai_provider}")

        try:
            self._client = ai.Client()
            LOG.info("AI client initialized successfully")
            return self._client
        except Exception as e:
            raise AIProviderError(
                f"Failed to initialize AI client: {e}",
                provider=self.config.ai_provider,
                original_error=e,
            ) from e

    def generate_sprite(
        self,
        prompt: str,
        width: int | None = None,
        height: int | None = None,
        frame_count: int | None = None,
        film_strip_count: int | None = None,
        animation_duration: float | None = None,
        training_examples: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> GenerationResult:
        """Generate a new sprite from a text prompt.

        Args:
            prompt: User's sprite generation request
            width: Optional sprite width (adds size hint to prompt)
            height: Optional sprite height (adds size hint to prompt)
            frame_count: Number of frames per animation
            film_strip_count: Number of film strips/animations to create
            animation_duration: Duration of animation in seconds
            training_examples: Optional training examples for context
            model: Optional model override in aisuite format (e.g., 'anthropic:claude-sonnet-4-5')

        Returns:
            GenerationResult with sprite data or error

        Raises:
            AIProviderError: If there's an issue with the AI provider

        """
        client = self._ensure_client()

        # Determine which model to use
        model_string = model or self.config.get_ai_model_string()

        # Build enhanced prompt with all hints
        enhanced_prompt = prompt
        hints = []

        if width and height:
            hints.append(f"{width}x{height} pixels")

        # Add animation hints if specified
        if frame_count or film_strip_count or animation_duration:
            animation_parts = []
            if film_strip_count and film_strip_count > 1:
                animation_parts.append(f"{film_strip_count} film strips")
            if frame_count:
                animation_parts.append(f"{frame_count} frames each")
            if animation_duration:
                animation_parts.append(f"animated across {animation_duration} seconds")

            if animation_parts:
                hints.append(", ".join(animation_parts))

        if hints:
            enhanced_prompt = f"{prompt} ({'; '.join(hints)})"

        # Build messages using the existing prompt builder
        messages = build_sprite_generation_messages(
            enhanced_prompt,
            training_examples=training_examples,
            include_size_hint=True,
            include_animation_hint=True,
        )

        # Make the API call
        try:
            LOG.info(f"Generating sprite with model: {model_string}")
            response = client.chat.completions.create(
                model=model_string,
                messages=messages,
                max_tokens=8192,
            )

            raw_content = response.choices[0].message.content
            LOG.debug(f"Raw AI response length: {len(raw_content)} chars")

        except Exception as e:
            LOG.error(f"AI API call failed: {e}")
            raise AIProviderError(
                f"AI generation failed: {e}",
                provider=self.config.ai_provider,
                original_error=e,
            ) from e

        # Clean and validate the response
        cleaned_content = clean_ai_response(raw_content)
        is_valid, error_message = validate_ai_response(cleaned_content)

        if not is_valid:
            LOG.warning(f"AI response validation failed: {error_message}")
            return GenerationResult(
                success=False,
                error=error_message,
                raw_response=raw_content,
            )

        # Extract metadata from the TOML
        sprite_name, is_animated, frame_count = self._extract_sprite_metadata(cleaned_content)

        LOG.info(
            f"Successfully generated sprite: {sprite_name} "
            f"(animated={is_animated}, frames={frame_count})"
        )

        return GenerationResult(
            success=True,
            toml_content=cleaned_content,
            sprite_name=sprite_name,
            is_animated=is_animated,
            frame_count=frame_count,
            raw_response=raw_content,
        )

    def refine_sprite(
        self,
        prompt: str,
        current_toml: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> GenerationResult:
        """Refine an existing sprite based on a text prompt.

        Args:
            prompt: User's refinement request
            current_toml: Current sprite TOML content
            conversation_history: Optional previous conversation messages

        Returns:
            GenerationResult with refined sprite data or error

        Raises:
            AIProviderError: If there's an issue with the AI provider

        """
        client = self._ensure_client()

        # Build refinement messages
        messages = build_refinement_messages(
            prompt,
            current_toml,
            conversation_history=conversation_history,
        )

        # Make the API call
        try:
            LOG.info(f"Refining sprite with model: {self.config.get_ai_model_string()}")
            response = client.chat.completions.create(
                model=self.config.get_ai_model_string(),
                messages=messages,
                max_tokens=8192,
            )

            raw_content = response.choices[0].message.content
            LOG.debug(f"Raw AI response length: {len(raw_content)} chars")

        except Exception as e:
            LOG.error(f"AI API call failed: {e}")
            raise AIProviderError(
                f"AI refinement failed: {e}",
                provider=self.config.ai_provider,
                original_error=e,
            ) from e

        # Clean and validate the response
        cleaned_content = clean_ai_response(raw_content)
        is_valid, error_message = validate_ai_response(cleaned_content)

        if not is_valid:
            LOG.warning(f"AI response validation failed: {error_message}")
            return GenerationResult(
                success=False,
                error=error_message,
                raw_response=raw_content,
            )

        # Extract metadata from the TOML
        sprite_name, is_animated, frame_count = self._extract_sprite_metadata(cleaned_content)

        LOG.info(
            f"Successfully refined sprite: {sprite_name} "
            f"(animated={is_animated}, frames={frame_count})"
        )

        return GenerationResult(
            success=True,
            toml_content=cleaned_content,
            sprite_name=sprite_name,
            is_animated=is_animated,
            frame_count=frame_count,
            raw_response=raw_content,
        )

    def _extract_sprite_metadata(self, toml_content: str) -> tuple[str, bool, int]:
        """Extract metadata from sprite TOML content.

        Args:
            toml_content: Sprite TOML content

        Returns:
            Tuple of (sprite_name, is_animated, frame_count)

        """
        import toml

        try:
            data = toml.loads(toml_content)
        except Exception as e:
            LOG.warning(f"Failed to parse TOML for metadata: {e}")
            return "unknown", False, 1

        # Get sprite name
        sprite_name = data.get("sprite", {}).get("name", "unnamed")

        # Check if animated
        is_animated = "animation" in data
        frame_count = 1

        if is_animated:
            # Count frames across all animations
            animations = data.get("animation", [])
            if isinstance(animations, list):
                for anim in animations:
                    if isinstance(anim, dict) and "frame" in anim:
                        frames = anim.get("frame", [])
                        if isinstance(frames, list):
                            frame_count = max(frame_count, len(frames))
            elif isinstance(animations, dict):
                # Single animation
                frames = animations.get("frame", [])
                if isinstance(frames, list):
                    frame_count = len(frames)

        return sprite_name, is_animated, frame_count

    def is_animation_request(self, prompt: str) -> bool:
        """Check if the prompt is requesting an animated sprite.

        Args:
            prompt: User's sprite generation request

        Returns:
            True if animation keywords detected

        """
        return detect_animation_request(prompt)
