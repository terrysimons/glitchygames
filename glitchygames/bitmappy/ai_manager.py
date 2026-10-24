"""AI manager for the Bitmappy editor.

Manages AI sprite generation requests, response processing, and sprite loading
from AI-generated content. Extracted from BitmapEditorScene to reduce class complexity.
"""

from __future__ import annotations

import contextlib
import itertools
import logging
import multiprocessing
import os
import tempfile
import tomllib
import weakref
from pathlib import Path
from queue import Empty
from typing import TYPE_CHECKING, Any

import pygame

from glitchygames.ai import (
    build_refinement_messages,
    build_sprite_generation_messages,
    validate_ai_response,
)
from glitchygames.ai import (
    clean_ai_response as ai_clean_response,
)
from glitchygames.clock import wall_clock_epoch_seconds
from glitchygames.color import (
    RGB_COMPONENT_COUNT,
)
from glitchygames.sprites import (
    SPRITE_GLYPHS,
    SpriteFactory,
)
from glitchygames.sprites.constants import DEFAULT_FILE_FORMAT

from .ai_worker import (
    build_retry_prompt,
    run_ai_worker_process,
    select_relevant_training_examples,
)
from .constants import (
    AI_TRAINING_SINGLE_FRAME_EXAMPLE_COUNT,
    AI_VALIDATION_MAX_RETRIES,
    DEBUG_LOG_FIRST_N_PIXELS,
    MAGENTA_TRANSPARENT,
    MAX_COLORS_FOR_AI_TRAINING,
    TRANSPARENT_GLYPH,
    ai_training_state,
)
from .models import AIRequest, AIRequestState, AIResponse, MockEvent
from .toml_processing import (
    build_color_to_glyph_mapping,
    build_pixel_string_from_pixels,
    collect_unique_colors_from_pixels,
    normalize_toml_data,
    parse_toml_robustly,
    quantize_colors_if_needed,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.sprites.animated import AnimatedSprite

    from .protocols import EditorContext


# How long cleanup waits for the worker to exit on its shutdown message before terminating it
AI_WORKER_JOIN_TIMEOUT_SECONDS = 2.0

# AIManagers whose worker process is running, so shut_down_running_ai_workers can reach them
# after a signal; weak so a discarded editor's manager does not stay alive
_RUNNING_AI_MANAGERS: weakref.WeakSet[AIManager] = weakref.WeakSet()

# Appended to each AI request id: the wall clock stands still within a frame in a replay
# (glitchygames/clock.py), so two requests made in one frame would otherwise share an id
_AI_REQUEST_COUNTER = itertools.count()


def _write_temporary_toml_file(*, prefix: str, write: Callable[[str], object]) -> str:
    """Create a temporary .toml file and fill it by calling ``write`` with its path.

    The file is removed again when ``write`` fails, so a failed save leaves no empty temporary
    file behind (the frame, strip and refinement saves each used to leave one).

    Args:
        prefix: The temporary file name's prefix.
        write: Writes the file's content, given its path.

    Returns:
        The path of the written file.

    """
    temporary_file_descriptor, temporary_path = tempfile.mkstemp(suffix='.toml', prefix=prefix)
    os.close(temporary_file_descriptor)  # Close the file descriptor, we'll use the path
    try:
        write(temporary_path)
    except BaseException:
        with contextlib.suppress(OSError):
            Path(temporary_path).unlink()
        raise
    return temporary_path


def shut_down_running_ai_workers() -> None:
    """Shut down every running AI worker the way a normal quit does (AIManager.cleanup).

    Bitmappy's main() calls it when the engine stops, so a SIGINT/SIGTERM (which ends the
    engine with SystemExit and skips the scenes' cleanup) still sends each worker its shutdown
    message, joins it with a timeout and terminates it only if it does not exit. Workers
    already shut down by a normal quit are no longer registered, so this then does nothing.
    """
    for manager in list(_RUNNING_AI_MANAGERS):
        manager.cleanup()


class AIManager:
    """Manages AI sprite generation for the Bitmappy editor.

    Handles AI request/response processing, training example gathering,
    sprite loading from AI-generated content, and AI worker lifecycle.
    """

    def __init__(self, editor: EditorContext) -> None:
        """Initialize the AIManager.

        Args:
            editor: The editor context providing access to shared state.

        """
        self.editor = editor
        self.log = logging.getLogger('game.tools.bitmappy.ai_integration')
        self.log.addHandler(logging.NullHandler())

        # AI state
        self.pending_ai_requests: dict[str, Any] = {}
        self.ai_request_queue: multiprocessing.Queue[AIRequest] | None = None
        self.ai_response_queue: multiprocessing.Queue[tuple[str, AIResponse]] | None = None
        self.ai_process: multiprocessing.Process | None = None
        self.last_successful_sprite_content: str | None = None
        self.last_conversation_history: list[dict[str, str]] | None = None

    def setup(self) -> None:
        """Initialize AI processing components and start the worker process."""
        # Check if we are in the main process
        if multiprocessing.current_process().name == 'MainProcess':
            self.log.info('Initializing AI worker process...')

            try:
                self.ai_request_queue = multiprocessing.Queue()
                self.ai_response_queue = multiprocessing.Queue()

                self.ai_process = multiprocessing.Process(
                    target=run_ai_worker_process,
                    args=(self.ai_request_queue, self.ai_response_queue),
                    daemon=True,
                )

                self.ai_process.start()
            except OSError, RuntimeError:
                self.log.exception('Error initializing AI worker process')
                self.ai_request_queue = None
                self.ai_response_queue = None
                self.ai_process = None
            else:
                self.log.info('AI worker process started with PID: %s', self.ai_process.pid)
                _RUNNING_AI_MANAGERS.add(self)
        else:
            self.log.warning('Not in main process, AI processing not available')

    def check_responses(self) -> None:
        """Check for AI responses from the worker process (called from update loop)."""
        if not self.ai_response_queue:
            return

        try:
            while True:
                request_id, response = self.ai_response_queue.get_nowait()
                self.log.info('Received AI response for request %s', request_id)
                self._process_ai_response(request_id, response)
        except Empty:
            pass
        except OSError, ValueError, AttributeError, TypeError:
            self.log.exception('Error checking AI responses')

    def cleanup(self) -> None:
        """Shut down AI worker and clean up resources.

        Sends the worker its shutdown message, joins it for AI_WORKER_JOIN_TIMEOUT_SECONDS,
        terminates (then kills) it only if it is still alive, and closes the queues. Safe to
        call more than once: later calls find nothing to shut down.
        """
        _RUNNING_AI_MANAGERS.discard(self)
        self._shutdown_ai_worker()
        self._cleanup_ai_process()
        self._cleanup_queues()
        self.ai_process = None
        self.ai_request_queue = None
        self.ai_response_queue = None

    def _on_debug_text_change(self, new_text: str) -> None:
        """Handle debug text change.

        Args:
            new_text: The new text content

        """
        self._update_sprite_description(new_text)

    def _has_single_animation_canvas(self) -> bool:
        """Check if the canvas has exactly one animation.

        Returns:
            True if the canvas has a single animation.

        """
        if not (hasattr(self.editor, 'canvas') and self.editor.canvas):
            return False
        if not (
            hasattr(self.editor.canvas, 'animated_sprite') and self.editor.canvas.animated_sprite
        ):
            return False
        return len(self.editor.canvas.animated_sprite.animations) == 1

    def _gather_training_examples_from_frame(self, text: str) -> list[dict[str, Any]]:
        """Gather training examples from the current frame and strip.

        If the current frame has content, saves both the current frame and strip
        as temporary TOML files and uses them as training examples. Falls back to
        the regular training example selection if no frame content is available.

        Args:
            text: The user's prompt text for selecting relevant examples.

        Returns:
            List of training example dicts for AI context.

        """
        current_frame_has_content = self._check_current_frame_has_content()

        if not current_frame_has_content:
            relevant_examples = select_relevant_training_examples(text)
            self.log.info('Frame is empty, using %s regular examples', len(relevant_examples))
            return relevant_examples

        frame_toml_path = self._save_current_frame_to_temp_toml()
        strip_toml_path = self._save_current_strip_to_temp_toml()

        examples: list[dict[str, Any]] = []

        if frame_toml_path:
            frame_example = self._load_temp_toml_as_example(frame_toml_path)
            if frame_example:
                frame_example['name'] = 'selected_frame'
                examples.append(frame_example)
                self.log.info('Added current frame as training example')

        if strip_toml_path:
            strip_example = self._load_temp_toml_as_example(strip_toml_path)
            if strip_example:
                strip_example['name'] = 'selected_strip'
                examples.append(strip_example)
                self.log.info('Added current strip as training example')

        if not examples:
            relevant_examples = select_relevant_training_examples(text)
            self.log.info(
                'Failed to load context examples, using %s regular examples',
                len(relevant_examples),
            )
            return relevant_examples

        # Optimize: if single animation with single frame, only send the frame
        if (
            len(examples) == AI_TRAINING_SINGLE_FRAME_EXAMPLE_COUNT
            and self._has_single_animation_canvas()
        ):
            single_animation = next(iter(self.editor.canvas.animated_sprite.animations.values()))
            frame_count = len(single_animation)

            if frame_count == 1:
                self.log.info('Optimization: Single frame in single strip - using only frame data')
                return [examples[0]]

        self.log.info('Using %s context examples (frame + strip)', len(examples))
        return examples

    def _serialize_current_sprite_for_refinement(
        self,
    ) -> tuple[bool, str | None, list[dict[str, str]] | None]:
        """Serialize the current sprite for AI refinement context.

        Returns:
            Tuple of (is_refinement, last_sprite_content, conversation_history).

        """
        if not (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and hasattr(self.editor.canvas, 'animated_sprite')
            and self.editor.canvas.animated_sprite
        ):
            return (False, None, None)

        try:
            last_sprite_content = self._read_canvas_sprite_as_toml()
        except OSError, ValueError, AttributeError, TypeError:
            self.log.exception('Failed to serialize sprite')
            self.log.warning('Will use standard generation mode instead')
            return (False, None, None)

        conversation_history = self.last_conversation_history

        animation_count = last_sprite_content.count('[[animation]]')
        frame_count = last_sprite_content.count('[[animation.frame]]')
        self.log.info(
            'Sprite loaded - serialized for AI context (%s chars, %s animations, %s frames)',
            len(last_sprite_content),
            animation_count,
            frame_count,
        )
        self.log.debug('Serialized sprite preview:\n%s', last_sprite_content[:500])
        return (True, last_sprite_content, conversation_history)

    def _read_canvas_sprite_as_toml(self) -> str:
        """Save the canvas sprite to a temporary TOML file and return the file's text.

        The temporary file is removed afterwards, whether or not it could be read.

        Returns:
            The sprite's TOML text.

        """
        canvas_sprite = self.editor.canvas.animated_sprite
        temporary_path = _write_temporary_toml_file(
            prefix='bitmappy_refinement_',
            write=lambda path: canvas_sprite.save(path, DEFAULT_FILE_FORMAT),
        )
        try:
            return Path(temporary_path).read_text(encoding='utf-8')
        finally:
            with contextlib.suppress(OSError):
                Path(temporary_path).unlink()

    def _submit_ai_request(
        self,
        text: str,
        messages: list[dict[str, str]],
        relevant_examples: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None,
        last_sprite_content: str | None,
    ) -> None:
        """Submit an AI sprite generation request to the worker process.

        Args:
            text: The original user prompt.
            messages: The built message list for the AI.
            relevant_examples: Training examples for context.
            conversation_history: Prior conversation for refinement.
            last_sprite_content: Last sprite TOML content for refinement.

        """
        request_id = f'{wall_clock_epoch_seconds()}-{next(_AI_REQUEST_COUNTER)}'

        request = AIRequest(prompt=str(messages), request_id=request_id, messages=messages)
        self.log.info('Submitting AI request: %s', request)

        assert self.ai_request_queue is not None
        try:
            self.ai_request_queue.put(request)
        except AttributeError, OSError, ValueError:
            self.log.exception('Error submitting AI request')
            if hasattr(self.editor, 'debug_text'):
                self.editor.debug_text.text = 'Error: Failed to submit AI request'
            return

        self.pending_ai_requests[request_id] = AIRequestState(
            original_prompt=text,
            retry_count=0,
            training_examples=relevant_examples,
            conversation_history=conversation_history,
            last_sprite_content=last_sprite_content,
        )

        if hasattr(self.editor, 'debug_text'):
            self.editor.debug_text.text = f'Processing AI request... (ID: {request_id})'

    def on_text_submit_event(self, text: str) -> None:
        """Handle text submission from MultiLineTextBox."""
        self.log.info("AI Sprite Generation Request: '%s'", text)
        self.log.debug('Text length: %s', len(text))
        self.log.debug('Text type: %s', type(text))

        if not self.ai_request_queue:
            self.log.error('AI request queue is not available')
            if hasattr(self.editor, 'debug_text'):
                self.editor.debug_text.text = 'AI processing not available'
            return

        if hasattr(self, 'ai_process') and self.ai_process and not self.ai_process.is_alive():
            self.log.error('AI process is not alive')
            if hasattr(self.editor, 'debug_text'):
                self.editor.debug_text.text = 'AI process not available'
            return

        relevant_examples = self._gather_training_examples_from_frame(text)
        is_refinement, last_sprite_content, conversation_history = (
            self._serialize_current_sprite_for_refinement()
        )

        if is_refinement and last_sprite_content:
            messages = build_refinement_messages(
                user_request=text.strip(),
                last_sprite_content=last_sprite_content,
                conversation_history=conversation_history,
                include_size_hint=True,
                include_animation_hint=True,
            )
        else:
            messages = build_sprite_generation_messages(
                user_request=text.strip(),
                training_examples=relevant_examples,
                max_examples=3,
                include_size_hint=True,
                include_animation_hint=True,
            )

        self._submit_ai_request(
            text,
            messages,
            relevant_examples,
            conversation_history,
            last_sprite_content,
        )

    def _handle_empty_ai_response(self, request_id: str, error: str | None) -> None:
        """Report an AI response that has no content and clean up its request.

        Args:
            request_id: The AI request identifier.
            error: The worker's error description, if it reported one.

        """
        self.log.error('AI response content is None, cannot save sprite')
        if error:
            self.log.error('AI worker reported error: %s', error)
        if hasattr(self.editor, 'debug_text'):
            self.editor.debug_text.text = (
                f'AI request failed: {error}' if error else 'AI response was empty'
            )
        # Clean up
        if request_id in self.pending_ai_requests:
            del self.pending_ai_requests[request_id]

    def _process_ai_response(self, request_id: str, response: AIResponse) -> None:
        """Process an AI response with automatic validation-driven retry."""
        self.log.info('Got AI response for request %s', request_id)

        # Handle empty response
        if response.content is None:
            self._handle_empty_ai_response(request_id, response.error)
            return

        # Get request state
        if request_id not in self.pending_ai_requests:
            self.log.warning('Request %s not found in pending requests', request_id)
            self._load_ai_sprite(request_id, response.content)
            return

        request_state = self.pending_ai_requests[request_id]

        # Validate the response
        is_valid, validation_error = self._validate_ai_content(response.content)

        if not is_valid:
            self.log.warning('AI response validation failed: %s', validation_error)

            # Check if we can retry
            if request_state.retry_count < AI_VALIDATION_MAX_RETRIES:
                # Trigger retry with targeted prompt
                request_state.retry_count += 1
                request_state.last_error = validation_error

                self.log.info(
                    'Retrying request (attempt %s/%s)',
                    request_state.retry_count + 1,
                    AI_VALIDATION_MAX_RETRIES + 1,
                )

                # Build retry prompt with specific corrections
                retry_prompt = build_retry_prompt(request_state.original_prompt, validation_error)

                # Rebuild messages with retry prompt
                messages = build_sprite_generation_messages(
                    user_request=retry_prompt,
                    training_examples=request_state.training_examples,
                    max_examples=3,
                    include_size_hint=True,
                    include_animation_hint=True,
                )

                # Create new request with same ID
                retry_request = AIRequest(
                    prompt=str(messages),
                    request_id=request_id,  # Reuse same ID
                    messages=messages,
                )

                # Submit retry
                assert self.ai_request_queue is not None
                self.ai_request_queue.put(retry_request)

                # Update UI
                if hasattr(self.editor, 'debug_text'):
                    self.editor.debug_text.text = (
                        f'Retrying with corrections... (attempt'
                        f' {request_state.retry_count + 1}/{AI_VALIDATION_MAX_RETRIES + 1})\n'
                        f'Error: {validation_error}'
                    )

                # DON'T delete from pending_ai_requests - we're retrying
                return
            # Max retries reached: give up without loading. This used to say "loading sprite
            # anyway", but _load_ai_sprite validates the same content and rejects it, so nothing
            # was ever loaded
            self.log.error(
                'Max retries (%s) reached, the sprite was not loaded: %s',
                AI_VALIDATION_MAX_RETRIES,
                validation_error,
            )
            if hasattr(self.editor, 'debug_text'):
                self.editor.debug_text.text = (
                    f'Failed after {AI_VALIDATION_MAX_RETRIES} retries:\n{validation_error}\n\n'
                    f'The sprite was not loaded.'
                )
            # Show the answer (and the original prompt) below the notice, then drop the request
            self._handle_ai_error_message(request_id, response.content)
            return

        # Valid response - load the sprite
        self._load_ai_sprite(request_id, response.content)

        # Remove from pending requests
        if request_id in self.pending_ai_requests:
            del self.pending_ai_requests[request_id]

    def _log_ai_response_content(self, content: str) -> None:
        """Log AI response content for debugging."""
        # Count animations and frames in response
        anim_count = content.count('[[animation]]')
        frame_count = content.count('[[animation.frame]]')
        self.log.info(
            'AI response received, content length: %s, %s animations, %s frames',
            len(content),
            anim_count,
            frame_count,
        )

        # Debug: Dump the sprite content
        self.log.info('=== AI GENERATED SPRITE CONTENT ===')
        self.log.info('AI Generated Content:\n%s', content)
        self.log.info('=== END SPRITE CONTENT ===')

    def _prepare_ai_content(self, request_id: str, content: str) -> str:
        """Clean AI response content and add description if needed.

        Returns:
            str: The resulting string.

        """
        # Check if this is an error message BEFORE cleaning
        if self._is_ai_error_message(content):
            self.log.warning('AI returned error/apology message, skipping processing')
            return content

        # Get the original user prompt from the request
        original_prompt = ''
        if request_id in self.pending_ai_requests:
            request_state = self.pending_ai_requests[request_id]
            original_prompt = request_state.original_prompt
            self.log.debug("Using original prompt: '%s'", original_prompt)

        # Clean up any markdown formatting from AI response (an error message never gets
        # here: _is_ai_error_message above rejects content that is not valid even once cleaned)
        cleaned_content = self._clean_ai_response(content)

        # Add description to the content if we have an original prompt
        if original_prompt and ai_training_state['format'] == 'toml':
            # Parse the TOML content with robust duplicate key handling
            try:
                data = parse_toml_robustly(cleaned_content, self.log)
                # Normalize the TOML data to convert escaped newlines to actual newlines
                data = normalize_toml_data(data)
                data.setdefault('sprite', {})['description'] = original_prompt

                # Manually construct TOML to preserve formatting instead of using toml.dumps()
                cleaned_content = self._construct_toml_with_preserved_formatting(data)
            except (KeyError, ValueError) as e:
                self.log.warning('Failed to add description to TOML content: %s', e)
            else:
                self.log.debug("Added description to TOML content: '%s'", original_prompt)

        return cleaned_content

    def _format_animation_sections(self, animation_list: list[dict[str, Any]]) -> list[str]:
        """Format animation sections as TOML lines.

        Args:
            animation_list: List of animation dictionaries with frame data.

        Returns:
            List of formatted TOML lines for animation sections.

        """
        lines: list[str] = []
        for animation in animation_list:
            lines.extend([
                '[[animation]]',
                f'namespace = "{animation["namespace"]}"',
                f'frame_interval = {animation["frame_interval"]}',
                f'loop = {str(animation["loop"]).lower()}',
                '',
            ])

            for frame in animation.get('frame', []):
                lines.extend([
                    '[[animation.frame]]',
                    f'namespace = "{animation["namespace"]}"',
                    f'frame_index = {frame["frame_index"]}',
                    'pixels = """',
                    # The closing quotes go on their own line, which ends the last pixel row:
                    # keeping the parsed trailing newline too would add a blank line per
                    # rewrite (BUGS.md #110 item 7)
                    frame['pixels'].removesuffix('\n'),
                    '"""',
                    '',
                ])
        return lines

    def _construct_toml_with_preserved_formatting(self, data: dict[str, Any]) -> str:
        """Construct TOML content while preserving original formatting for pixel data.

        Args:
            data: Parsed TOML data

        Returns:
            TOML content string with preserved formatting

        """
        lines: list[str] = []

        # Add sprite section
        if 'sprite' in data:
            lines.append('[sprite]')
            sprite_data = data['sprite']
            if 'name' in sprite_data:
                lines.append(f'name = "{sprite_data["name"]}"')
            if 'description' in sprite_data:
                lines.append(f'description = """{sprite_data["description"]}"""')
            if 'pixels' in sprite_data:
                lines.extend((
                    'pixels = """',
                    # The closing quotes' line ends the last row (see _format_animation_sections)
                    sprite_data['pixels'].removesuffix('\n'),
                    '"""',
                ))
            lines.append('')

        # Add animation sections
        if 'animation' in data:
            lines.extend(self._format_animation_sections(data['animation']))

        # Add colors section
        if 'colors' in data:
            lines.append('[colors]')
            # Dict keys are unique, so each color is written once
            for color_key, color_data in data['colors'].items():
                lines.extend([
                    f'[colors."{color_key}"]',
                    f'red = {color_data["red"]}',
                    f'green = {color_data["green"]}',
                    f'blue = {color_data["blue"]}',
                    '',
                ])

        return '\n'.join(lines)

    def _create_temp_file_from_content(self, content: str) -> str:
        """Create temporary file from AI content and return the path.

        Returns:
            str: The resulting string.

        """
        # Determine file extension based on training format
        file_extension = (
            f'.{ai_training_state["format"]}' if ai_training_state['format'] else '.toml'
        )

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=file_extension,
            delete=False,
            encoding='utf-8',
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
            self.log.info('Saved AI response to temp file: %s', tmp_path)
            return tmp_path

    def _load_animated_ai_sprite(self, tmp_path: str) -> None:
        """Load animated AI sprite into canvas."""
        self.log.info('Loading animated sprite into existing animated canvas...')

        mock_event = MockEvent(text=tmp_path)
        self.editor.canvas.on_load_file_event(mock_event)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]

        # Animation will be started by on_load_file_event, no need to start here
        self.log.info('AI animated sprite loaded successfully')

    def _load_static_ai_sprite(self, tmp_path: str) -> None:
        """Load static AI sprite into canvas."""
        self.log.info('Loading static sprite into animated canvas...')

        # Load the static sprite into the current animated canvas
        mock_event = MockEvent(text=tmp_path)
        self.editor.canvas.on_load_file_event(mock_event)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]

        # Animation will be started by on_load_file_event, no need to start here
        # Just verify the state after loading
        if hasattr(self.editor.canvas, 'animated_sprite') and self.editor.canvas.animated_sprite:
            self.log.debug(
                "AI sprite loaded - animated_sprite state: current_animation='%s', is_playing=%s",
                self.editor.canvas.animated_sprite.current_animation,
                self.editor.canvas.animated_sprite.is_playing,
            )
            animations = (
                list(self.editor.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
                if hasattr(self.editor.canvas.animated_sprite, '_animations')
                else 'No _animations'
            )
            self.log.debug('AI sprite animations: %s', animations)

            # Note: Live preview functionality is now integrated into the film strip

        # Force canvas redraw to show the new sprite
        self.editor.canvas.dirty = 1
        self.editor.canvas.force_redraw()

        # Also force a scene update to ensure everything is redrawn
        if hasattr(self.editor, 'all_sprites'):
            for sprite in list(self.editor.all_sprites):
                if hasattr(sprite, 'dirty'):
                    sprite.dirty = 1

        self.log.info('AI static sprite loaded successfully into animated canvas')

    def _update_ui_after_ai_load(self, request_id: str) -> None:
        """Update UI components after AI sprite load."""
        if hasattr(self.editor, 'debug_text'):
            # Restore the original prompt text that was submitted
            if request_id in self.pending_ai_requests:
                request_state = self.pending_ai_requests[request_id]
                original_prompt = request_state.original_prompt
            else:
                original_prompt = 'Enter a description of the sprite you want to create:'

            self.editor.debug_text.text = original_prompt

    def _cleanup_ai_request(self, request_id: str) -> None:
        """Clean up pending AI request."""
        # Clean up the pending request
        if request_id in self.pending_ai_requests:
            del self.pending_ai_requests[request_id]

    def _check_current_frame_has_content(self) -> bool:
        """Check if the current frame has any non-magenta pixels.

        Returns:
            True if frame has content (non-magenta pixels), False if all magenta

        """
        if not (hasattr(self.editor, 'canvas') and hasattr(self.editor.canvas, 'pixels')):
            self.log.debug('No canvas or canvas.pixels found, returning False')
            return False

        pixels = self.editor.canvas.pixels
        try:
            self.log.debug('Checking frame content: %s pixels', len(pixels))
            if not pixels:
                self.log.debug('No pixels found, returning False')
                return False

            non_magenta_count = self._count_non_magenta_pixels(pixels)
        except AttributeError, TypeError, IndexError:
            self.log.exception('Error checking frame content')
            return False
        else:
            return non_magenta_count > 0

    def _count_non_magenta_pixels(self, pixels: list[tuple[int, ...]]) -> int:
        """Count the pixels that are not magenta (255, 0, 255).

        Args:
            pixels: The frame's pixels; a pixel that is not a sequence raises TypeError.

        Returns:
            The number of non-magenta pixels.

        """
        non_magenta_count = 0
        for pixel_index, pixel in enumerate(pixels):
            color = (
                (int(pixel[0]), int(pixel[1]), int(pixel[2]))
                if len(pixel) >= RGB_COMPONENT_COUNT
                else pixel
            )
            if color != (255, 0, 255):
                non_magenta_count += 1
                if non_magenta_count <= DEBUG_LOG_FIRST_N_PIXELS:
                    self.log.debug('Found non-magenta pixel %s: %s', pixel_index, color)

        self.log.debug(
            'Found %s non-magenta pixels out of %s total',
            non_magenta_count,
            len(pixels),
        )
        return non_magenta_count

    def _save_current_frame_to_temp_toml(self) -> str | None:
        """Save the current frame to a temporary TOML file.

        Returns:
            Path to the temporary TOML file, or None if failed

        """
        # Get current frame data
        if not hasattr(self.editor, 'canvas') or not hasattr(self.editor.canvas, 'pixels'):
            return None

        pixels = self.editor.canvas.pixels
        if not pixels:
            return None

        # Generate TOML content with single-char glyphs only
        # This ensures the AI sees only single-character glyphs in the training data
        # (it logs its own errors and returns '' rather than raising)
        toml_content = self._generate_frame_toml_content(pixels, force_single_char_glyphs=True)

        try:
            temp_path = _write_temporary_toml_file(
                prefix='bitmappy_frame_',
                write=lambda path: Path(path).write_text(toml_content, encoding='utf-8'),
            )
        except OSError, ValueError, AttributeError, TypeError:
            self.log.exception('Error saving frame to temp TOML')
            return None

        self.log.info('Saved current frame to temporary TOML: %s', temp_path)
        return temp_path

    def _save_current_strip_to_temp_toml(self) -> str | None:
        """Save the current animation strip to a temporary TOML file.

        Returns:
            Path to the temporary TOML file, or None if failed

        """
        try:
            strip_sprite = self._build_current_strip_sprite()
            if strip_sprite is None:
                return None

            # Save the sprite to TOML using the existing save method
            temp_path = _write_temporary_toml_file(
                prefix='bitmappy_strip_', write=strip_sprite.save
            )
        except OSError, ValueError, AttributeError, KeyError, TypeError:
            self.log.exception('Error saving strip to temp TOML')
            return None

        self.log.info('Saved current strip to temporary TOML: %s', temp_path)
        return temp_path

    def _build_current_strip_sprite(self) -> AnimatedSprite | None:
        """Build a sprite holding only the canvas's current animation.

        Returns:
            The new sprite, or None when the canvas has no current animation to copy.

        """
        # Get current animation data
        if not hasattr(self.editor, 'canvas') or not hasattr(
            self.editor.canvas,
            'animated_sprite',
        ):
            return None

        animated_sprite = self.editor.canvas.animated_sprite
        if not animated_sprite or not hasattr(animated_sprite, '_animations'):
            return None

        current_animation = getattr(self.editor.canvas, 'current_animation', None)
        if not current_animation or current_animation not in animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            return None

        # Create a new AnimatedSprite with just the current animation
        from glitchygames.sprites.animated import AnimatedSprite

        # Get the current animation frames
        current_frames = animated_sprite._animations[current_animation]  # type: ignore[reportPrivateUsage]

        # Create new sprite with the current animation
        new_sprite = AnimatedSprite()
        new_sprite.name = f'current_strip_{current_animation}'
        new_sprite.description = f'Current animation strip: {current_animation}'

        # Copy the animation data
        new_sprite._animations = {current_animation: current_frames}  # type: ignore[reportPrivateUsage]
        # Set the animation order to only include this animation
        new_sprite._animation_order = [current_animation]  # type: ignore[reportPrivateUsage]
        # The sprite will automatically play the first (and only) animation
        return new_sprite

    def _generate_frame_toml_content(
        self,
        pixels: list[tuple[int, ...]],
        *,
        force_single_char_glyphs: bool = False,
    ) -> str:
        """Generate TOML content for the current frame.

        Args:
            pixels: List of pixel colors
            force_single_char_glyphs: If True, limit to 64 single-character glyphs for AI training

        Returns:
            TOML content string

        """
        # Pixel and color processing can fail in many ways (a canvas without a size, malformed
        # pixels): every failure gives empty content, so the whole build is one call here
        try:
            return self._build_frame_toml_content(
                pixels,
                force_single_char_glyphs=force_single_char_glyphs,
            )
        except AttributeError, IndexError, KeyError, TypeError, ValueError:
            self.log.exception('Error generating frame TOML content')
            return ''

    def _build_frame_toml_content(
        self,
        pixels: list[tuple[int, ...]],
        *,
        force_single_char_glyphs: bool,
    ) -> str:
        """Build the TOML content for the current frame (_generate_frame_toml_content's body).

        Args:
            pixels: List of pixel colors
            force_single_char_glyphs: If True, limit to 64 single-character glyphs for AI training

        Returns:
            TOML content string

        """
        width = self.editor.canvas.pixels_across
        height = self.editor.canvas.pixels_tall

        unique_colors = collect_unique_colors_from_pixels(pixels)

        if force_single_char_glyphs and len(unique_colors) > MAX_COLORS_FOR_AI_TRAINING:
            self.log.info('Quantizing %s colors down to 64 for AI training', len(unique_colors))
            unique_colors = quantize_colors_if_needed(
                unique_colors,
                has_transparency=False,
                max_colors=64,
                log=self.log,
            )

        color_to_glyph = build_color_to_glyph_mapping(
            unique_colors,
            has_transparency=False,
            force_single_char_glyphs=force_single_char_glyphs,
            log=self.log,
        )

        sorted_colors = sorted(color_to_glyph.keys())

        pixel_string = build_pixel_string_from_pixels(
            pixels,
            width,
            height,
            color_to_glyph,
            sorted_colors,
            force_single_char_glyphs=force_single_char_glyphs,
        )

        # Generate color definitions using the consistent mapping (every color is an
        # RGB tuple: collect_unique_colors_from_pixels keeps three components)
        color_definitions = ''
        for color in sorted_colors:
            red = int(color[0])
            green = int(color[1])
            blue = int(color[2])
            glyph: str = color_to_glyph[color]
            color_definitions += (
                f'[colors."{glyph}"]\nred = {red}\ngreen = {green}\nblue = {blue}\n\n'
            )

        # Always ensure block character is mapped to magenta for transparency
        if MAGENTA_TRANSPARENT in color_to_glyph:
            color_definitions += (
                f'[colors."{TRANSPARENT_GLYPH}"]\nred = 255\ngreen = 0\nblue = 255\n\n'
            )

        # Build complete TOML
        return f"""[sprite]
name = "current_frame"
pixels = \"\"\"
{pixel_string}
\"\"\"

{color_definitions}"""

    def _get_glyph_for_color(self, color: tuple[int, int, int] | int) -> str:
        """Get a glyph for a specific color.

        Args:
            color: RGB color tuple or integer color value

        Returns:
            Single character glyph from first 64 characters of SPRITE_GLYPHS

        """
        # Use only first 64 characters for consistent, manageable palette
        available_glyphs = SPRITE_GLYPHS[:64]
        # Simple hash-based assignment to ensure consistent glyph for same color
        color_hash = hash(color) % len(available_glyphs)
        return available_glyphs[color_hash]

    def _load_temp_toml_as_example(self, temp_toml_path: str) -> dict[str, Any] | None:
        """Load a temporary TOML file as a training example.

        Args:
            temp_toml_path: Path to the temporary TOML file

        Returns:
            Training example dict, or None if failed

        """
        try:
            file_content = Path(temp_toml_path).read_text(encoding='utf-8')
            # tomllib keeps the newlines inside a multi-line pixels string; only the newline
            # before the closing quotes is extra
            config_data = tomllib.loads(file_content)
            sprite_data = self._training_example_from_toml(
                config_data=config_data,
                file_content=file_content,
            )
        except OSError, ValueError, KeyError, TypeError:
            self.log.exception('Error loading temp TOML as example')
            return None
        finally:
            # Clean up temporary file, also when it could not be read (it used to be left)
            self._remove_temporary_file(temp_toml_path)

        self.log.info('Loaded current frame as training example: %s', sprite_data['name'])
        return sprite_data

    def _remove_temporary_file(self, temporary_path: str) -> None:
        """Remove a temporary file, logging (not raising) a failure.

        Args:
            temporary_path: The file to remove; one that is already gone is fine.

        """
        try:
            Path(temporary_path).unlink(missing_ok=True)
            self.log.debug('Cleaned up temporary file: %s', temporary_path)
        except OSError as cleanup_error:
            self.log.warning('Failed to clean up temp file %s: %s', temporary_path, cleanup_error)

    @staticmethod
    def _training_example_from_toml(
        *,
        config_data: dict[str, Any],
        file_content: str,
    ) -> dict[str, Any]:
        """Build a training example from a parsed sprite TOML file.

        Args:
            config_data: The parsed TOML.
            file_content: The file's text (an animated example carries it).

        Returns:
            The training example dict.

        """
        sprite_name = config_data.get('sprite', {}).get('name', 'current_frame')
        colors = config_data.get('colors', {})

        animations = config_data.get('animation', [])
        if not animations:
            pixels_data = config_data.get('sprite', {}).get('pixels', '')
            return {
                'name': sprite_name,
                'sprite_type': 'static',
                'pixels': pixels_data.removesuffix('\n'),
                'colors': colors,
            }

        # An animation strip: every frame goes in, not only the first pixels block
        # (which was all the example held, labelled static)
        for animation in animations:
            for frame in animation.get('frame', []):
                frame['pixels'] = frame.get('pixels', '').removesuffix('\n')
        every_frame_pixels = [
            frame['pixels'] for animation in animations for frame in animation.get('frame', [])
        ]
        return {
            'name': sprite_name,
            'sprite_type': 'animated',
            # Every frame's rows, one blank line between frames
            'pixels': '\n\n'.join(every_frame_pixels),
            'animations': animations,
            'colors': colors,
            # format_training_example sends the file itself, frames and all
            'raw_content': file_content,
        }

    def _validate_ai_content(self, content: str) -> tuple[bool, str]:
        """Validate AI response content, accepting content that cleaning makes valid.

        Loading cleans markdown fences and leading explanations off an answer before parsing
        it, so an answer that is valid once cleaned is valid: validating only the raw answer
        rejected (and retried) every fenced one (BUGS.md #93).

        Args:
            content: The raw AI response content.

        Returns:
            Tuple of (is_valid, error_message); the error is the raw content's.

        """
        is_valid, error_message = validate_ai_response(content)
        if is_valid:
            return True, ''

        cleaned_is_valid, _ = validate_ai_response(self._clean_ai_response(content))
        if cleaned_is_valid:
            return True, ''
        return False, error_message

    def _is_ai_error_message(self, content: str) -> bool:
        """Check if an AI response is not valid sprite code.

        Any validation failure counts (see _validate_ai_content: the raw answer and its cleaned
        form both fail validate_ai_response), whatever the reason; it does not look for
        apologies or error wording. The failure is logged as a warning.

        Args:
            content: The AI response content to check

        Returns:
            True if the content fails validation, False if it is valid sprite code

        """
        # Use the new AI module's validation function
        is_valid, error_msg = self._validate_ai_content(content)

        if not is_valid:
            self.log.warning('AI response validation failed: %s', error_msg)
            return True

        return False

    def _get_original_prompt_for_request(self, request_id: str) -> str:
        """Get the original prompt associated with a pending AI request.

        Args:
            request_id: The AI request identifier.

        Returns:
            The original prompt string, or empty string if not found.

        """
        if request_id in self.pending_ai_requests:
            return self.pending_ai_requests[request_id].original_prompt
        return ''

    def _handle_ai_unavailable(self, request_id: str) -> None:
        """Handle AI returning an unavailable message.

        Args:
            request_id: The AI request identifier.

        """
        self.log.warning('AI returned error message, cannot load sprite')
        if hasattr(self.editor, 'debug_text'):
            self.editor.debug_text.text = (
                'AI features not available. Please check your AI configuration.'
            )
        self._cleanup_ai_request(request_id)

    def _handle_ai_error_message(self, request_id: str, content: str) -> None:
        """Handle AI returning an error/apology message instead of sprite code.

        Args:
            request_id: The AI request identifier.
            content: The AI response content.

        """
        self.log.warning('AI returned error/apology message instead of sprite code')
        self.log.debug('Detected error message, content preview: %s...', content[:100])

        original_prompt = self._get_original_prompt_for_request(request_id)

        if hasattr(self.editor, 'debug_text'):
            # Append the error message to the input box, with original prompt at the bottom
            current_text = getattr(self.editor.debug_text, 'text', '')
            error_text = current_text + '\n\n' + content if current_text else content

            # Add original prompt at the bottom if we have it
            if original_prompt:
                error_text = error_text + '\n\n--- Original Prompt ---\n' + original_prompt

            self.editor.debug_text.text = error_text
            self.log.info('Appended error message to debug_text input box')

        self._cleanup_ai_request(request_id)

    def _detect_and_load_ai_sprite(self, tmp_path: str) -> None:
        """Detect sprite type from a temp file and load it into the canvas.

        Args:
            tmp_path: Path to the temporary TOML file.

        """
        self.log.info('Detecting AI sprite type...')

        # Use SpriteFactory to detect the sprite type
        sprite = SpriteFactory.load_sprite(filename=tmp_path)
        is_animated = hasattr(sprite, '_animations') and sprite._animations  # type: ignore[reportPrivateUsage]
        self.log.info('AI sprite type: %s', 'Animated' if is_animated else 'Static')
        self.log.debug('AI sprite has _animations: %s', hasattr(sprite, '_animations'))
        # SpriteFactory.load_sprite always returns an AnimatedSprite, which has _animations
        self.log.debug('AI sprite _animations: %s', list(sprite._animations.keys()))  # type: ignore[reportPrivateUsage]
        self.log.debug('AI sprite current_animation: %s', sprite.current_animation)
        self.log.debug('AI sprite is_playing: %s', sprite.is_playing)

        if is_animated:
            self._load_animated_ai_sprite(tmp_path)
        else:
            self._load_static_ai_sprite(tmp_path)

    def _update_sprite_description(self, original_prompt: str) -> None:
        """Update the loaded sprite's description with the original AI prompt.

        Args:
            original_prompt: The original prompt used to generate the sprite.

        """
        if not (
            original_prompt
            and hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and hasattr(self.editor.canvas, 'animated_sprite')
            and self.editor.canvas.animated_sprite
        ):
            return

        self.editor.canvas.animated_sprite.description = original_prompt
        self.log.info("Updated sprite description with generation prompt: '%s'", original_prompt)

    def _update_conversation_history(
        self,
        request_id: str,
        original_prompt: str,
        cleaned_content: str,
    ) -> None:
        """Update conversation history for multi-turn AI refinement.

        Args:
            request_id: The AI request identifier.
            original_prompt: The original prompt sent to the AI.
            cleaned_content: The cleaned AI response content.

        """
        if request_id not in self.pending_ai_requests:
            return

        request_state = self.pending_ai_requests[request_id]
        # Build conversation history: previous history + new user request + assistant response
        new_history: list[dict[str, str]] = []
        if request_state.conversation_history:
            new_history.extend(request_state.conversation_history)

        # Add user's request
        new_history.extend((
            {'role': 'user', 'content': original_prompt},
            # Add assistant's response (cleaned sprite content)
            {'role': 'assistant', 'content': cleaned_content},
        ))

        # Save for next request
        self.last_conversation_history = new_history
        self.log.info('Updated conversation history (now %s messages)', len(new_history))

    def _handle_ai_sprite_load_error(
        self,
        sprite_error: Exception,
        request_id: str,
        content: str,
    ) -> None:
        """Handle errors that occur during AI sprite loading.

        Args:
            sprite_error: The exception that occurred.
            request_id: The AI request identifier.
            content: The original AI response content.

        """
        self.log.error('Failed to load AI sprite', exc_info=sprite_error)

        original_prompt = self._get_original_prompt_for_request(request_id)

        if not hasattr(self.editor, 'debug_text'):
            return

        # Show error with original prompt at the bottom
        error_text = f'Error loading AI sprite: {sprite_error}'
        if original_prompt:
            error_text = error_text + '\n\n--- Original Prompt ---\n' + original_prompt

        # Also include the AI response content for debugging
        error_text = error_text + '\n\n--- AI Response ---\n' + content

        self.editor.debug_text.text = error_text

    def _load_ai_sprite(self, request_id: str, content: str) -> None:
        """Load sprite from AI content using SpriteFactory APIs."""
        # Log AI response content for debugging
        self._log_ai_response_content(content)

        # Check if this is an error message
        if content.strip() in {'AI features not available', 'AI features not available.'}:
            self._handle_ai_unavailable(request_id)
            return

        # Check if this looks like an error/apology message
        if self._is_ai_error_message(content):
            self._handle_ai_error_message(request_id, content)
            return

        # Prepare AI content (clean and add description if needed)
        cleaned_content = self._prepare_ai_content(request_id, content)
        original_prompt = self._get_original_prompt_for_request(request_id)

        # Create temporary file from content
        tmp_path = self._create_temp_file_from_content(cleaned_content)

        # Detect sprite type and load appropriately
        try:
            self._detect_and_load_ai_sprite(tmp_path)
            self._update_sprite_description(original_prompt)
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            pygame.error,
        ) as sprite_error:
            self._handle_ai_sprite_load_error(sprite_error, request_id, content)
            return
        # Note: Temp file is kept for debugging - remove this comment when done debugging

        # Save successful sprite content for future refinements
        self.last_successful_sprite_content = cleaned_content
        self.log.info('Saved sprite content for potential refinement requests')

        self._update_conversation_history(request_id, original_prompt, cleaned_content)

        # Update UI components
        self._update_ui_after_ai_load(request_id)

        # Clean up pending request
        self._cleanup_ai_request(request_id)

    def _clean_ai_response(self, content: str) -> str:
        """Clean up markdown formatting from AI response using AI module.

        Returns:
            str: The resulting string.

        """
        # Check if this is an error message instead of valid content
        if content.strip() in {'AI features not available', 'AI features not available.'}:
            self.log.warning('AI returned error message instead of sprite content')
            return content  # Return as-is for error handling upstream

        # Use the new AI module's cleaning function
        cleaned = ai_clean_response(content)
        self.log.info('Cleaned AI response using AI module')
        return cleaned or content

    def _shutdown_ai_worker(self) -> None:
        """Signal AI worker to shut down."""
        if hasattr(self, 'ai_request_queue') and self.ai_request_queue:
            try:
                self.log.info('Sending shutdown signal to AI worker...')
                self.ai_request_queue.put(None, timeout=1.0)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]  # Sentinel for shutdown
                self.log.info('Shutdown signal sent successfully')
            except OSError, ValueError:
                self.log.exception('Error sending shutdown signal')

    def _cleanup_ai_process(self) -> None:
        """Clean up AI process."""
        if not hasattr(self, 'ai_process') or not self.ai_process:
            return

        try:
            self._stop_ai_process(self.ai_process)
        except OSError, RuntimeError, AttributeError:
            self.log.exception('Error during AI process cleanup')
        finally:
            # Ensure process is cleaned up (the check at the top made sure there is one)
            try:
                if self.ai_process.is_alive():
                    self.log.info('Force killing remaining AI process...')
                    self.ai_process.kill()
            except OSError, AttributeError, RuntimeError:
                self.log.debug('Error during final AI process cleanup (ignored)')

    def _stop_ai_process(self, ai_process: multiprocessing.Process) -> None:
        """Join the worker, terminating and then killing it only if it does not exit.

        Args:
            ai_process: The worker process (any step may raise OSError, RuntimeError or
                AttributeError; _cleanup_ai_process logs it and still kills a live worker).

        """
        self.log.info('Waiting for AI process to finish...')
        ai_process.join(timeout=AI_WORKER_JOIN_TIMEOUT_SECONDS)
        if ai_process.is_alive():
            self.log.info('AI process still alive, terminating...')
            ai_process.terminate()
            ai_process.join(timeout=1.0)  # Longer timeout for terminate
            if ai_process.is_alive():
                self.log.info('AI process still alive, force killing...')
                ai_process.kill()  # Force kill if still alive
                ai_process.join(timeout=0.5)  # Final cleanup
        self.log.info('AI process cleanup completed')

    def _cleanup_queues(self) -> None:
        """Clean up AI queues."""
        if hasattr(self, 'ai_request_queue') and self.ai_request_queue:
            try:
                self.ai_request_queue.close()
                self.log.info('AI request queue closed')
            except OSError, ValueError:
                self.log.exception('Error closing request queue')

        if hasattr(self, 'ai_response_queue') and self.ai_response_queue:
            try:
                self.ai_response_queue.close()
                self.log.info('AI response queue closed')
            except OSError, ValueError:
                self.log.exception('Error closing response queue')
