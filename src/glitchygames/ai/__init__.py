"""AI-powered features for GlitchyGames.

This module provides AI-based sprite generation and related functionality.
"""

from glitchygames.ai.sprite_generator import (
    SpriteGenerationPrompt,
    build_refinement_messages,
    build_sprite_generation_messages,
    clean_ai_response,
    detect_animation_request,
    format_training_example,
    get_sprite_size_hint,
    validate_ai_response,
)

__all__ = [
    'SpriteGenerationPrompt',
    'build_refinement_messages',
    'build_sprite_generation_messages',
    'clean_ai_response',
    'detect_animation_request',
    'format_training_example',
    'get_sprite_size_hint',
    'validate_ai_response',
]
