#!/usr/bin/env python3
"""AI Query Inspector Scene - A GlitchyGames scene for showing Bitmappy AI queries.

This scene demonstrates the complete message structure that would be sent to the AI,
including system prompts, training examples, and user requests.
"""

from __future__ import annotations

import sys
import typing
from pathlib import Path
from typing import Any, cast, override

import pygame

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from glitchygames.bitmappy import (  # noqa: E402
    AI_MAX_CONTEXT_SIZE,
    AI_MAX_INPUT_TOKENS,
    AI_MODEL,
    load_ai_training_data,
)
from glitchygames.bitmappy.constants import ai_training_state  # noqa: E402
from glitchygames.engine import GameEngine  # noqa: E402
from glitchygames.scenes import Scene  # noqa: E402
from glitchygames.sprites import SPRITE_GLYPHS  # noqa: E402
from glitchygames.ui import MultiLineTextBox  # noqa: E402

if typing.TYPE_CHECKING:
    from glitchygames import events

# --- Magic value constants ---
CONTENT_PREVIEW_LENGTH: int = 200
CHARACTERS_PER_TOKEN_ESTIMATE: int = 4
TOKEN_PERCENTAGE_MULTIPLIER: float = 100.0
FONT_SIZE_LARGE: int = 24
FONT_SIZE_SMALL: int = 16
BUTTON_WIDTH: int = 120
BUTTON_HEIGHT: int = 40
BUTTON_MARGIN_FROM_BOTTOM: int = 100
BUTTON_X_SEND: int = 20
BUTTON_X_TOGGLE: int = 160
BUTTON_X_BACK: int = 300
UI_MARGIN: int = 20
PROMPT_INPUT_Y: int = 50
PROMPT_INPUT_HEIGHT: int = 100
QUERY_DISPLAY_Y: int = 170
QUERY_DISPLAY_BOTTOM_MARGIN: int = 300
SEPARATOR_WIDTH: int = 80
SUB_SEPARATOR_WIDTH: int = 40
BACKGROUND_COLOR: tuple[int, int, int] = (20, 20, 20)
TEXT_COLOR_WHITE: tuple[int, int, int] = (255, 255, 255)
TEXT_COLOR_GRAY: tuple[int, int, int] = (200, 200, 200)
BUTTON_COLOR_GREEN: tuple[int, int, int] = (0, 100, 0)
BUTTON_COLOR_BLUE: tuple[int, int, int] = (0, 0, 100)
BUTTON_COLOR_RED: tuple[int, int, int] = (100, 0, 0)
INSTRUCTION_LINE_HEIGHT: int = 20
INSTRUCTION_Y_OFFSET: int = 10
SPRITE_GLYPHS_SLICE_SIZE: int = 512


class _ButtonSprite(pygame.sprite.Sprite):
    """A simple button sprite with a name attribute for identification."""

    def __init__(self, name: str) -> None:
        """Initialize a button sprite.

        Args:
            name: The name identifier for the button.

        """
        super().__init__()
        self.name: str = name
        self.image: pygame.Surface = pygame.Surface((0, 0))
        self.rect: pygame.Rect = self.image.get_rect()


class AIQueryInspectorScene(Scene):
    """Scene that demonstrates AI query construction."""

    NAME = 'AI Query Inspector'
    VERSION = '1.0'

    def __init__(
        self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize the AI Query Inspector scene.

        Args:
            options: Configuration options for the scene.
            groups: Sprite groups for rendering.

        """
        if options is None:
            options = {}
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(options=options, groups=groups)

        self.user_prompt: str = ''
        self.messages: list[dict[str, str]] = []
        self.show_full_content: bool = False

        # UI elements
        self.prompt_input: MultiLineTextBox | None = None
        self.query_display: MultiLineTextBox | None = None
        self.send_button: _ButtonSprite | None = None
        self.full_content_button: _ButtonSprite | None = None
        self.back_button: _ButtonSprite | None = None

        # Load training data
        self.training_data_loaded: bool = False
        self.load_training_data()

    def load_training_data(self) -> None:
        """Load AI training data."""
        try:
            load_ai_training_data()
            self.training_data_loaded = True
            training_data = cast('list[Any]', ai_training_state['data'])
            print(f'Loaded {len(training_data)} training examples')  # noqa: T201
        except (TypeError, OSError, ValueError) as exception:
            print(f'Warning: Could not load training data: {exception}')  # noqa: T201
            self.training_data_loaded = False

    @override
    def setup(self) -> None:
        """Set up the scene."""
        self.log.info('Setting up AI Query Inspector Scene')

        # Create UI elements
        self.create_ui()

        # Set initial state
        self.update_query_display()

    def create_ui(self) -> None:
        """Create UI elements."""
        screen_width: int = self.screen_width
        screen_height: int = self.screen_height

        # Prompt input
        self.prompt_input = MultiLineTextBox(
            x=UI_MARGIN,
            y=PROMPT_INPUT_Y,
            width=screen_width - UI_MARGIN * 2,
            height=PROMPT_INPUT_HEIGHT,
            name='Prompt Input',
            text='a red hat',
            groups=self.all_sprites,
        )

        # Query display
        self.query_display = MultiLineTextBox(
            x=UI_MARGIN,
            y=QUERY_DISPLAY_Y,
            width=screen_width - UI_MARGIN * 2,
            height=screen_height - QUERY_DISPLAY_BOTTOM_MARGIN,
            name='Query Display',
            text='Enter a prompt above to see the AI query structure',
            groups=self.all_sprites,
        )

        # Create simple button sprites for interaction
        button_y: int = screen_height - BUTTON_MARGIN_FROM_BOTTOM

        # Send Query button
        self.send_button = _ButtonSprite(name='Send Query')
        self.send_button.image = pygame.Surface((BUTTON_WIDTH, BUTTON_HEIGHT))
        assert self.send_button.image is not None
        self.send_button.image.fill(BUTTON_COLOR_GREEN)
        self.send_button.rect = self.send_button.image.get_rect()
        assert self.send_button.rect is not None
        self.send_button.rect.x = BUTTON_X_SEND
        self.send_button.rect.y = button_y

        # Toggle Full Content button
        self.full_content_button = _ButtonSprite(name='Toggle Full')
        self.full_content_button.image = pygame.Surface((BUTTON_WIDTH, BUTTON_HEIGHT))
        assert self.full_content_button.image is not None
        self.full_content_button.image.fill(BUTTON_COLOR_BLUE)
        self.full_content_button.rect = self.full_content_button.image.get_rect()
        assert self.full_content_button.rect is not None
        self.full_content_button.rect.x = BUTTON_X_TOGGLE
        self.full_content_button.rect.y = button_y

        # Back button
        self.back_button = _ButtonSprite(name='Back')
        self.back_button.image = pygame.Surface((BUTTON_WIDTH, BUTTON_HEIGHT))
        assert self.back_button.image is not None
        self.back_button.image.fill(BUTTON_COLOR_RED)
        self.back_button.rect = self.back_button.image.get_rect()
        assert self.back_button.rect is not None
        self.back_button.rect.x = BUTTON_X_BACK
        self.back_button.rect.y = button_y

        # Add text to buttons
        self.add_button_text()

        # Add buttons to sprite group
        self.all_sprites.add(self.send_button)
        self.all_sprites.add(self.full_content_button)
        self.all_sprites.add(self.back_button)

    def add_button_text(self) -> None:
        """Add text labels to buttons."""
        font: pygame.font.Font = pygame.font.Font(None, FONT_SIZE_LARGE)

        # Send Query button text
        if self.send_button is not None:
            assert self.send_button.rect is not None
            assert self.send_button.image is not None
            send_text: pygame.Surface = font.render(
                'Send Query',
                True,  # noqa: FBT003
                TEXT_COLOR_WHITE,
            )
            send_text_rect: pygame.Rect = send_text.get_rect(center=self.send_button.rect.center)
            self.send_button.image.blit(send_text, send_text_rect)

        # Toggle Full Content button text
        if self.full_content_button is not None:
            assert self.full_content_button.rect is not None
            assert self.full_content_button.image is not None
            toggle_text: pygame.Surface = font.render(
                'Toggle Full',
                True,  # noqa: FBT003
                TEXT_COLOR_WHITE,
            )
            toggle_text_rect: pygame.Rect = toggle_text.get_rect(
                center=self.full_content_button.rect.center
            )
            self.full_content_button.image.blit(toggle_text, toggle_text_rect)

        # Back button text
        if self.back_button is not None:
            assert self.back_button.rect is not None
            assert self.back_button.image is not None
            back_text: pygame.Surface = font.render(
                'Back',
                True,  # noqa: FBT003
                TEXT_COLOR_WHITE,
            )
            back_text_rect: pygame.Rect = back_text.get_rect(center=self.back_button.rect.center)
            self.back_button.image.blit(back_text, back_text_rect)

    @override
    def on_mouse_button_up_event(self, event: events.HashableEvent) -> None:
        """Handle mouse button up events for button clicks."""
        # Check if any button was clicked
        if self.send_button is not None:
            assert self.send_button.rect is not None
            if self.send_button.rect.collidepoint(event.pos):
                self.on_send_query()
                return

        if self.full_content_button is not None:
            assert self.full_content_button.rect is not None
            if self.full_content_button.rect.collidepoint(event.pos):
                self.on_toggle_full_content()
                return

        if self.back_button is not None:
            assert self.back_button.rect is not None
            if self.back_button.rect.collidepoint(event.pos):
                self.on_back()
                return

        # Pass to other sprites
        for sprite in self.all_sprites:
            if hasattr(sprite, 'on_mouse_button_up_event') and sprite.rect.collidepoint(event.pos):
                sprite.on_mouse_button_up_event(event)

    def on_prompt_submit(self, text: str) -> None:
        """Handle prompt submission."""
        self.user_prompt = text.strip()
        self.update_query_display()

    def on_toggle_full_content(self) -> None:
        """Toggle full content display."""
        self.show_full_content = not self.show_full_content
        self.update_query_display()

    def on_send_query(self) -> None:
        """Send the actual query to AI."""
        if not self.messages:
            return

        try:
            import logging

            import aisuite as ai

            log: logging.Logger = logging.getLogger('ai_query_inspector')
            log.setLevel(logging.INFO)

            # Create API call parameters
            api_kwargs: dict[str, Any] = {
                'model': AI_MODEL,
                'messages': self.messages,
                'max_tokens': AI_MAX_INPUT_TOKENS,
            }

            # Send request
            client: Any = ai.Client()
            response: Any = client.chat.completions.create(**api_kwargs)

            if response.choices:
                ai_response: str = str(response.choices[0].message.content)
                if self.query_display is not None:
                    self.query_display.text = (
                        f'AI Response ({len(ai_response)} characters):\n\n{ai_response}'
                    )
            elif self.query_display is not None:
                self.query_display.text = 'No response received from AI'

        except (ImportError, OSError, ValueError, RuntimeError) as exception:
            if self.query_display is not None:
                self.query_display.text = f'Error sending request: {exception}'

    def on_back(self) -> None:
        """Go back to previous scene."""
        self.scene_manager.quit_requested = True

    def update_query_display(self) -> None:
        """Update the query display with current messages."""
        if self.query_display is None:
            return

        if not self.user_prompt:
            self.query_display.text = 'Enter a prompt above to see the AI query structure'
            return

        try:
            self.messages = self.construct_ai_query(self.user_prompt)
            display_text: str = self.format_messages_for_display(self.messages)
            self.query_display.text = display_text
        except (TypeError, ValueError, KeyError) as exception:
            self.query_display.text = f'Error constructing query: {exception}'

    def construct_ai_query(self, user_prompt: str) -> list[dict[str, str]]:
        """Construct the AI query that Bitmappy would send.

        Args:
            user_prompt: The user's prompt text.

        Returns:
            A list of message dicts with 'role' and 'content' keys.

        """
        # Training format defaults to 'toml' after load_ai_training_data() runs
        training_format: str = (
            str(ai_training_state['format']) if ai_training_state['format'] else 'toml'
        )

        # Use loaded training examples or fall back to mock data
        relevant_examples: list[Any]
        if self.training_data_loaded:
            relevant_examples = cast('list[Any]', ai_training_state['data'])
        else:
            # Use mock examples if training data couldn't be loaded
            relevant_examples = [
                {
                    'name': 'example_static_sprite',
                    'sprite_type': 'static',
                    'pixels': '.#.\n#.#\n.#.',
                    'colors': {
                        '.': {'red': 0, 'green': 0, 'blue': 0},
                        '#': {'red': 255, 'green': 255, 'blue': 255},
                    },
                }
            ]

        available_glyphs = SPRITE_GLYPHS[:SPRITE_GLYPHS_SLICE_SIZE]
        glyph_count = len(available_glyphs)

        # Determine format instruction
        format_instruction: str = (
            'I understand. I will provide ONLY raw TOML content'
            ' without any markdown formatting, code blocks, or'
            ' explanations. The TOML format will include:\n'
            '- [sprite] section containing name and pixels'
            ' (using triple-quoted block strings)\n'
            '- [colors."X"] sections ONLY for colors that are'
            ' actually used in the pixel data\n'
            '- RGB values from 0-255 for each color\n'
            '- Pixels using the SPRITE_GLYPHS character set\n'
            '- For animated sprites: [[animation]] and'
            ' [[animation.frame]] sections\n'
            '- When "frame", "animation", "animated", "2-frame",'
            ' or "multi-frame" is mentioned, I will create an'
            ' ANIMATED sprite with multiple frames\n'
            '- IMPORTANT: Use triple-quoted block strings for'
            ' multi-line pixel data\n'
            '- EFFICIENCY: Only define colors that appear in the'
            ' pixels (e.g., if pixels="0", only define'
            ' [colors."0"])'
        )

        examples_text = '\n'.join([str(data) for data in relevant_examples])

        # Construct the complete message array
        messages: list[dict[str, str]] = [
            {
                'role': 'system',
                'content': (
                    'You are a helpful assistant in a bitmap editor'
                    ' that can create game content for game'
                    ' developers. You can create both static'
                    ' single-frame sprites and animated multi-frame'
                    f' sprites.\n\nAvailable character set for'
                    f' sprite pixels: {glyph_count}'
                    f' colors: {available_glyphs}'
                ),
            },
            {
                'role': 'user',
                'content': (
                    'Here is the context for your sprite'
                    f' generation:\n\n{examples_text}\n\n'
                    f'Available character set: {glyph_count}'
                    f' colors: {available_glyphs}\n\n'
                    'IMPORTANT: The examples above include both'
                    ' the selected frame and the selected strip'
                    ' from the current sprite. Use this context to'
                    ' understand what the user is asking for and'
                    ' determine the appropriate response based on'
                    ' their request.'
                ),
            },
            {
                'role': 'assistant',
                'content': (
                    'Thank you for providing those sprite examples.'
                    ' I understand that each sprite consists'
                    ' of:\n\n'
                    '1. A name\n'
                    '2. A pixel layout using characters from:'
                    f' {glyph_count}'
                    f' colors: {available_glyphs}\n'
                    '3. A color palette mapping characters to RGB'
                    ' values\n'
                    '4. For animated sprites: multiple frames with'
                    ' timing information\n\n'
                    f"I'll use the {training_format.upper()} format"
                    ' when suggesting new sprites.'
                ),
            },
            {
                'role': 'user',
                'content': (
                    'Great! When I ask you to create a sprite,'
                    ' please provide ONLY the'
                    f' {training_format.upper()} content without'
                    ' any markdown formatting, code blocks, or'
                    ' explanations. Just the raw'
                    f' {training_format.upper()} file content.\n\n'
                    'Use the standard TOML sprite format with'
                    ' [sprite], [[animation]],'
                    ' [[animation.frame]], and [colors]'
                    ' sections.\n\n'
                    'IMPORTANT: Return ONLY the'
                    f' {training_format.upper()} content, no'
                    ' markdown code blocks, no explanations, no'
                    ' ```toml or ``` markers.'
                ),
            },
            {
                'role': 'assistant',
                'content': format_instruction,
            },
            {
                'role': 'user',
                'content': user_prompt.strip(),
            },
        ]

        return messages

    def format_messages_for_display(self, messages: list[dict[str, str]]) -> str:
        """Format messages for display in the text box.

        Args:
            messages: List of message dicts to format.

        Returns:
            A formatted string representation of all messages.

        """
        lines: list[str] = []

        # Header
        lines.extend([
            '=' * SEPARATOR_WIDTH,
            'BITMAPPY AI QUERY CONSTRUCTION',
            '=' * SEPARATOR_WIDTH,
            '',
        ])

        # Configuration
        lines.extend([
            f'AI Model: {AI_MODEL}',
            f'Max input tokens: {AI_MAX_INPUT_TOKENS}',
            f'Max context size: {AI_MAX_CONTEXT_SIZE}',
            f'Training format: {ai_training_state["format"]}',
            f'Training data loaded: {self.training_data_loaded}',
            '',
        ])

        # Message structure
        total_chars: int = sum(len(msg['content']) for msg in messages)
        estimated_tokens: int = total_chars // CHARACTERS_PER_TOKEN_ESTIMATE
        token_percentage: float = (
            estimated_tokens / AI_MAX_INPUT_TOKENS * TOKEN_PERCENTAGE_MULTIPLIER
        )
        lines.extend([
            'MESSAGE STRUCTURE:',
            f'Total messages: {len(messages)}',
            f'Total characters: {total_chars:,}',
            f'Estimated tokens: {estimated_tokens:,}',
            f'Token usage: {token_percentage:.1f}%',
            '',
        ])

        # API parameters
        lines.extend([
            'API CALL PARAMETERS:',
            f'  model: {AI_MODEL}',
            f'  messages: {len(messages)} messages',
            f'  max_tokens: {AI_MAX_INPUT_TOKENS}',
            '',
        ])

        # Detailed messages
        lines.extend(['DETAILED MESSAGE BREAKDOWN:', ''])

        for message_index, message in enumerate(messages):
            message_header = f'--- Message {message_index + 1} ({message["role"].upper()}) ---'
            content_length_line = f'Content Length: {len(message["content"])} characters'
            lines.extend([
                message_header,
                f'Role: {message["role"]}',
                content_length_line,
            ])

            if self.show_full_content:
                lines.extend([
                    'Full content:',
                    '-' * SUB_SEPARATOR_WIDTH,
                    message['content'],
                    '-' * SUB_SEPARATOR_WIDTH,
                ])
            else:
                preview: str = message['content'][:CONTENT_PREVIEW_LENGTH]
                lines.append(f'Content Preview: {preview}...')
                remaining = len(message['content']) - CONTENT_PREVIEW_LENGTH
                if remaining > 0:
                    lines.append(f'[... {remaining} more characters ...]')

            lines.append('')

        return '\n'.join(lines)

    @override
    def on_key_down_event(self, event: events.HashableEvent) -> None:
        """Handle key down events."""
        if event.key == pygame.K_ESCAPE:
            self.on_back()
        elif event.key == pygame.K_F5:
            # Refresh query display
            self.update_query_display()
        elif event.key == pygame.K_F6:
            # Toggle full content
            self.on_toggle_full_content()
        elif event.key == pygame.K_RETURN and pygame.key.get_pressed()[pygame.K_LCTRL]:
            # Send query with Ctrl+Enter
            self.on_send_query()

    @override
    def render(self, screen: pygame.Surface) -> None:
        """Render the scene."""
        # Clear background
        screen.fill(BACKGROUND_COLOR)

        # Render title
        font: pygame.font.Font = pygame.font.Font(None, FONT_SIZE_LARGE)
        title_text: pygame.Surface = font.render(
            'AI Query Inspector',
            True,  # noqa: FBT003
            TEXT_COLOR_WHITE,
        )
        screen.blit(title_text, (UI_MARGIN, UI_MARGIN))

        # Render instructions
        font_small: pygame.font.Font = pygame.font.Font(None, FONT_SIZE_SMALL)
        instructions: list[str] = [
            'Enter a prompt above to see the AI query structure',
            ('F5: Refresh query | F6: Toggle full content | Ctrl+Enter: Send query | Esc: Back'),
        ]

        for instruction_index, instruction in enumerate(instructions):
            text: pygame.Surface = font_small.render(
                instruction,
                True,  # noqa: FBT003
                TEXT_COLOR_GRAY,
            )
            screen.blit(
                text,
                (
                    UI_MARGIN,
                    INSTRUCTION_Y_OFFSET + instruction_index * INSTRUCTION_LINE_HEIGHT,
                ),
            )

        # Render UI elements
        super().render(screen)


def main() -> None:
    """Main function to run the AI Query Inspector scene."""
    # Create game engine with the scene class
    GameEngine(game=AIQueryInspectorScene).start()


if __name__ == '__main__':
    main()
