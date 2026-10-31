"""Tests for bitmappy.ai_manager.AIManager.

The worker process and its queues are local fakes (the process boundary): no test starts a
process or sends a real AI request. Sprites are real AnimatedSprites loaded from TOML, and every
temporary file the manager writes goes to the test's tmp_path.
"""

import logging
import os
import queue
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs this interpreter on a fixed program
import sys
import tempfile
import textwrap
import tomllib
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pytest

from bitmappy import ai_manager as ai_manager_module
from bitmappy import constants as constants_module
from bitmappy.ai_manager import (
    AI_WORKER_JOIN_TIMEOUT_SECONDS,
    AIManager,
    shut_down_running_ai_workers,
)
from bitmappy.ai_worker import run_ai_worker_process
from bitmappy.constants import (
    AI_VALIDATION_MAX_RETRIES,
    MAGENTA_TRANSPARENT,
    TRANSPARENT_GLYPH,
    ai_training_state,
)
from bitmappy.models import AIRequest, AIRequestState, AIResponse
from glitchygames.ai import build_refinement_messages, build_sprite_generation_messages
from glitchygames.sprites import SPRITE_GLYPHS, SpriteFactory
from glitchygames.sprites.animated import AnimatedSprite

STATIC_SPRITE_TOML = (
    '[sprite]\nname = "ball"\npixels = """\n#.\n.#\n"""\n\n'
    '[colors."#"]\nred = 255\ngreen = 0\nblue = 0\n\n'
    '[colors."."]\nred = 255\ngreen = 0\nblue = 255\n'
)

ANIMATED_SPRITE_TOML = (
    '[sprite]\nname = "blinker"\n\n'
    '[[animation]]\nnamespace = "blink"\nframe_interval = 0.5\nloop = true\n\n'
    '[[animation.frame]]\nnamespace = "blink"\nframe_index = 0\npixels = """\n#.\n.#\n"""\n\n'
    '[[animation.frame]]\nnamespace = "blink"\nframe_index = 1\npixels = """\n.#\n#.\n"""\n\n'
    '[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n\n'
    '[colors."."]\nred = 255\ngreen = 255\nblue = 255\n'
)

# A static sprite whose second row is short: valid TOML that needs a pixel-row repair
RAGGED_SPRITE_TOML = (
    '[sprite]\nname = "ball"\npixels = """\n##\n#\n"""\n\n'
    '[colors."#"]\nred = 255\ngreen = 0\nblue = 0\n'
)

DEFAULT_PROMPT_TEXT = 'Enter a description of the sprite you want to create:'


class FakeQueue:
    """A queue standing in for a multiprocessing.Queue between editor and worker."""

    def __init__(self) -> None:
        """Start empty and open."""
        self.items: deque = deque()
        self.closed = False
        self.put_error: BaseException | None = None
        self.get_error: BaseException | None = None
        self.close_error: BaseException | None = None

    def put(self, item: object, timeout: float | None = None) -> None:
        """Queue an item, or raise the configured error."""
        if self.put_error is not None:
            raise self.put_error
        self.items.append(item)

    def get_nowait(self) -> object:
        """Take the oldest item.

        Returns:
            The oldest item.

        Raises:
            queue.Empty: When nothing is queued.

        """
        if self.get_error is not None:
            raise self.get_error
        if not self.items:
            raise queue.Empty
        return self.items.popleft()

    def close(self) -> None:
        """Close the queue, or raise the configured error."""
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


class FakeProcess:
    """A worker process that answers is_alive() from a script and records lifecycle calls."""

    start_error: BaseException | None = None

    def __init__(
        self,
        *,
        target: object = None,
        args: tuple = (),
        daemon: bool = False,
    ) -> None:
        """Remember how the process was created."""
        self.target = target
        self.args = args
        self.daemon = daemon
        self.pid = 4242
        self.started = False
        self.alive_answers: deque[bool] = deque()
        self.calls: list[str] = []
        self.join_error: BaseException | None = None
        self.is_alive_error: BaseException | None = None

    def start(self) -> None:
        """Start the process, or raise the class's configured error."""
        if self.start_error is not None:
            raise self.start_error
        self.started = True

    def is_alive(self) -> bool:
        """Answer from the script; False once it runs out.

        Returns:
            Whether the process is alive.

        """
        if self.is_alive_error is not None:
            raise self.is_alive_error
        return self.alive_answers.popleft() if self.alive_answers else False

    def join(self, timeout: float | None = None) -> None:
        """Record a join."""
        self.calls.append(f'join({timeout})')
        if self.join_error is not None:
            raise self.join_error

    def terminate(self) -> None:
        """Record a terminate."""
        self.calls.append('terminate')

    def kill(self) -> None:
        """Record a kill."""
        self.calls.append('kill')


class FakeCanvas:
    """A canvas that loads sprite files into a real AnimatedSprite."""

    def __init__(
        self,
        *,
        pixels: list[tuple[int, ...]] | None = None,
        pixels_across: int = 2,
        pixels_tall: int = 2,
    ) -> None:
        """Start with the given pixels and no sprite."""
        self.pixels = pixels if pixels is not None else []
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall
        self.animated_sprite = None
        self.current_animation = None
        self.loaded_paths: list[str] = []
        self.dirty = 0
        self.redraw_count = 0

    def on_load_file_event(self, event: object) -> None:
        """Load the event's file as the canvas sprite."""
        self.loaded_paths.append(event.text)  # type: ignore[attr-defined]
        self.animated_sprite = SpriteFactory.load_sprite(filename=event.text)  # type: ignore[attr-defined]

    def force_redraw(self) -> None:
        """Count redraws."""
        self.redraw_count += 1


def _write_sprite(*, tmp_path: Path, name: str, content: str) -> str:
    """Write a sprite TOML file.

    Returns:
        Its path as a string.

    """
    sprite_path = tmp_path / name
    sprite_path.write_text(content, encoding='utf-8')
    return str(sprite_path)


def _canvas_with_sprite(*, tmp_path: Path, content: str) -> FakeCanvas:
    """Build a canvas holding a real sprite loaded from ``content``.

    Returns:
        The canvas, its pixels taken from the sprite's first frame.

    """
    canvas = FakeCanvas()
    canvas.on_load_file_event(
        SimpleNamespace(text=_write_sprite(tmp_path=tmp_path, name='canvas.toml', content=content)),
    )
    canvas.current_animation = next(iter(canvas.animated_sprite.animations))
    first_frame = next(iter(canvas.animated_sprite.animations.values()))[0]
    width, height = first_frame.image.get_size()
    canvas.pixels = [
        tuple(first_frame.image.get_at((x, y))) for y in range(height) for x in range(width)
    ]
    canvas.loaded_paths.clear()
    return canvas


def _editor(*, canvas: object = None, with_debug_text: bool = True) -> SimpleNamespace:
    """Build an editor context with an optional canvas and a debug text box.

    Returns:
        The editor.

    """
    editor = SimpleNamespace(all_sprites=[])
    if canvas is not None:
        editor.canvas = canvas
    if with_debug_text:
        editor.debug_text = SimpleNamespace(text='')
    return editor


def _manager_with_queues(editor: SimpleNamespace) -> AIManager:
    """Build a manager whose request and response queues are fakes.

    Returns:
        The manager.

    """
    manager = AIManager(editor)  # type: ignore[arg-type]
    manager.ai_request_queue = FakeQueue()  # type: ignore[assignment]
    manager.ai_response_queue = FakeQueue()  # type: ignore[assignment]
    return manager


@pytest.fixture(autouse=True)
def temporary_files_in_tmp_path(mocker, tmp_path):
    """Make every tempfile the manager creates land in a temp subdirectory of tmp_path.

    Returns:
        The directory temporary files are written to.

    """
    temporary_directory = tmp_path / 'temporary'
    temporary_directory.mkdir()
    mocker.patch.object(tempfile, 'tempdir', str(temporary_directory))
    return temporary_directory


@pytest.fixture(autouse=True)
def toml_training_state(mocker):
    """Use the TOML training format with no training examples."""
    mocker.patch.dict(ai_training_state, {'format': 'toml', 'data': []})


@pytest.fixture
def fake_process_class(mocker):
    """Replace multiprocessing.Process and Queue in the manager with fakes.

    Yields:
        The FakeProcess class.

    """
    mocker.patch.object(ai_manager_module.multiprocessing, 'Process', FakeProcess)
    mocker.patch.object(ai_manager_module.multiprocessing, 'Queue', FakeQueue)
    FakeProcess.start_error = None
    yield FakeProcess
    FakeProcess.start_error = None


# ---------------------------------------------------------------------------
# Worker lifecycle
# ---------------------------------------------------------------------------


class TestSetup:
    """Test AIManager.setup."""

    def test_starts_the_worker_process_with_both_queues(self, fake_process_class):
        """In the main process the worker is started as a daemon on the two queues."""
        manager = AIManager(_editor())  # type: ignore[arg-type]

        manager.setup()

        assert isinstance(manager.ai_process, FakeProcess)
        assert manager.ai_process.started is True
        assert manager.ai_process.daemon is True
        assert manager.ai_process.target is run_ai_worker_process
        assert manager.ai_process.args == (manager.ai_request_queue, manager.ai_response_queue)
        assert manager in ai_manager_module._RUNNING_AI_MANAGERS
        manager.cleanup()

    def test_start_failure_leaves_ai_unavailable(self, fake_process_class):
        """A worker that cannot start leaves no queues or process behind."""
        fake_process_class.start_error = OSError('no fork')
        manager = AIManager(_editor())  # type: ignore[arg-type]

        manager.setup()

        assert (manager.ai_request_queue, manager.ai_response_queue, manager.ai_process) == (
            None,
            None,
            None,
        )
        assert manager not in ai_manager_module._RUNNING_AI_MANAGERS

    def test_outside_the_main_process_nothing_starts(self, mocker, fake_process_class):
        """A manager created in a child process does not start a worker."""
        mocker.patch.object(
            ai_manager_module.multiprocessing,
            'current_process',
            return_value=SimpleNamespace(name='Process-1'),
        )
        manager = AIManager(_editor())  # type: ignore[arg-type]

        manager.setup()

        assert manager.ai_process is None
        assert manager.ai_request_queue is None


class TestCleanup:
    """Test AIManager.cleanup and shut_down_running_ai_workers."""

    def test_worker_that_exits_is_only_joined(self):
        """A worker that exits on the shutdown message is joined, not terminated."""
        manager = _manager_with_queues(_editor())
        request_queue = manager.ai_request_queue
        response_queue = manager.ai_response_queue
        process = FakeProcess()
        manager.ai_process = process  # type: ignore[assignment]

        manager.cleanup()

        assert list(request_queue.items) == [None]  # type: ignore[union-attr]
        assert process.calls == [f'join({AI_WORKER_JOIN_TIMEOUT_SECONDS})']
        assert request_queue.closed is True  # type: ignore[union-attr]
        assert response_queue.closed is True  # type: ignore[union-attr]
        assert (manager.ai_process, manager.ai_request_queue, manager.ai_response_queue) == (
            None,
            None,
            None,
        )

    def test_worker_still_alive_after_join_is_terminated(self):
        """A worker that ignores the shutdown message is terminated."""
        manager = _manager_with_queues(_editor())
        process = FakeProcess()
        process.alive_answers.extend([True, False, False])
        manager.ai_process = process  # type: ignore[assignment]

        manager.cleanup()

        assert process.calls == [
            f'join({AI_WORKER_JOIN_TIMEOUT_SECONDS})',
            'terminate',
            'join(1.0)',
        ]

    def test_worker_surviving_terminate_is_killed(self):
        """A worker still alive after terminate is killed."""
        manager = _manager_with_queues(_editor())
        process = FakeProcess()
        process.alive_answers.extend([True, True, False])
        manager.ai_process = process  # type: ignore[assignment]

        manager.cleanup()

        assert process.calls == [
            f'join({AI_WORKER_JOIN_TIMEOUT_SECONDS})',
            'terminate',
            'join(1.0)',
            'kill',
            'join(0.5)',
        ]

    def test_join_error_still_kills_a_live_worker(self):
        """When joining fails, a worker that is still alive is killed in the final step."""
        manager = _manager_with_queues(_editor())
        process = FakeProcess()
        process.join_error = OSError('join failed')
        process.alive_answers.append(True)
        manager.ai_process = process  # type: ignore[assignment]

        manager.cleanup()

        assert process.calls == [f'join({AI_WORKER_JOIN_TIMEOUT_SECONDS})', 'kill']
        assert manager.ai_process is None

    def test_error_in_the_final_liveness_check_is_ignored(self):
        """A process whose is_alive fails is still released."""
        manager = _manager_with_queues(_editor())
        process = FakeProcess()
        process.is_alive_error = RuntimeError('gone')
        manager.ai_process = process  # type: ignore[assignment]

        manager.cleanup()

        assert manager.ai_process is None

    def test_queue_errors_do_not_stop_cleanup(self):
        """Failing to send the shutdown message or close the queues is logged, not raised."""
        manager = _manager_with_queues(_editor())
        manager.ai_request_queue.put_error = ValueError('closed')  # type: ignore[union-attr]
        manager.ai_request_queue.close_error = OSError('broken')  # type: ignore[union-attr]
        manager.ai_response_queue.close_error = ValueError('broken')  # type: ignore[union-attr]

        manager.cleanup()

        assert (manager.ai_request_queue, manager.ai_response_queue) == (None, None)

    def test_shut_down_running_ai_workers_cleans_up_each_registered_manager(self):
        """Every registered manager is cleaned up and unregistered."""
        manager = _manager_with_queues(_editor())
        request_queue = manager.ai_request_queue
        ai_manager_module._RUNNING_AI_MANAGERS.add(manager)

        shut_down_running_ai_workers()

        assert manager not in ai_manager_module._RUNNING_AI_MANAGERS
        assert list(request_queue.items) == [None]  # type: ignore[union-attr]
        assert manager.ai_request_queue is None


# ---------------------------------------------------------------------------
# Response checking
# ---------------------------------------------------------------------------


class TestCheckResponses:
    """Test AIManager.check_responses."""

    def test_without_a_response_queue_nothing_happens(self):
        """A manager with no worker has nothing to check."""
        AIManager(_editor()).check_responses()  # type: ignore[arg-type]

    def test_queued_responses_are_processed(self):
        """Each queued response is processed; an empty one reports the worker's error."""
        editor = _editor()
        manager = _manager_with_queues(editor)
        manager.pending_ai_requests['request-1'] = AIRequestState(original_prompt='ball')
        manager.ai_response_queue.put(  # type: ignore[union-attr]
            ('request-1', AIResponse(content=None, error='BadRequestError: no credit')),
        )

        manager.check_responses()

        assert editor.debug_text.text == 'AI request failed: BadRequestError: no credit'
        assert manager.pending_ai_requests == {}

    def test_queue_error_is_logged_not_raised(self, caplog):
        """A broken response queue is reported in the log."""
        manager = _manager_with_queues(_editor())
        manager.ai_response_queue.get_error = OSError('broken pipe')  # type: ignore[union-attr]

        with caplog.at_level(logging.ERROR, logger='game.tools.bitmappy.ai_integration'):
            manager.check_responses()

        assert 'Error checking AI responses' in caplog.messages


# ---------------------------------------------------------------------------
# Request submission
# ---------------------------------------------------------------------------


class TestOnTextSubmitEvent:
    """Test AIManager.on_text_submit_event."""

    def test_without_a_queue_reports_ai_unavailable(self):
        """With no worker, the debug text says AI processing is unavailable."""
        editor = _editor()

        AIManager(editor).on_text_submit_event('a ball')  # type: ignore[arg-type]

        assert editor.debug_text.text == 'AI processing not available'

    def test_dead_worker_reports_the_process_unavailable(self):
        """With a dead worker, nothing is submitted."""
        editor = _editor()
        manager = _manager_with_queues(editor)
        manager.ai_process = FakeProcess()  # type: ignore[assignment]

        manager.on_text_submit_event('a ball')

        assert editor.debug_text.text == 'AI process not available'
        assert not manager.ai_request_queue.items  # type: ignore[union-attr]

    def test_new_sprite_request_uses_the_generation_messages(self, mocker):
        """Without a sprite on the canvas, a generation request with the examples is sent."""
        training_examples = [{'name': 'ball', 'sprite_type': 'static'}]
        mocker.patch.dict(ai_training_state, {'data': training_examples})
        editor = _editor(canvas=FakeCanvas())
        manager = _manager_with_queues(editor)
        manager.ai_process = FakeProcess()  # type: ignore[assignment]
        manager.ai_process.alive_answers.append(True)

        manager.on_text_submit_event('  a red ball  ')

        request = manager.ai_request_queue.items[0]  # type: ignore[union-attr]
        assert isinstance(request, AIRequest)
        assert request.messages == build_sprite_generation_messages(
            user_request='a red ball',
            training_examples=training_examples,
            max_examples=3,
            include_size_hint=True,
            include_animation_hint=True,
        )
        assert request.prompt == str(request.messages)
        assert manager.pending_ai_requests == {
            request.request_id: AIRequestState(
                original_prompt='  a red ball  ',
                training_examples=training_examples,
            ),
        }
        assert editor.debug_text.text == f'Processing AI request... (ID: {request.request_id})'

    def test_two_requests_in_one_frame_get_different_ids(self):
        """Request ids stay unique when the wall clock stands still."""
        manager = _manager_with_queues(_editor())

        manager.on_text_submit_event('one')
        manager.on_text_submit_event('two')

        first_request, second_request = manager.ai_request_queue.items  # type: ignore[union-attr]
        assert first_request.request_id != second_request.request_id

    def test_sprite_on_the_canvas_makes_a_refinement_request(self, tmp_path):
        """With a sprite loaded, the request refines its serialized TOML."""
        canvas = _canvas_with_sprite(tmp_path=tmp_path, content=ANIMATED_SPRITE_TOML)
        manager = _manager_with_queues(_editor(canvas=canvas))
        history = [{'role': 'user', 'content': 'earlier'}]
        manager.last_conversation_history = history

        manager.on_text_submit_event('make it blink faster')

        request = manager.ai_request_queue.items[0]  # type: ignore[union-attr]
        request_state = manager.pending_ai_requests[request.request_id]
        assert '[[animation]]' in request_state.last_sprite_content
        assert request_state.conversation_history == history
        assert request.messages == build_refinement_messages(
            user_request='make it blink faster',
            last_sprite_content=request_state.last_sprite_content,
            conversation_history=history,
            include_size_hint=True,
            include_animation_hint=True,
        )

    def test_failed_submission_is_reported(self):
        """A request that cannot be queued leaves no pending request."""
        editor = _editor()
        manager = _manager_with_queues(editor)
        manager.ai_request_queue.put_error = OSError('queue full')  # type: ignore[union-attr]

        manager.on_text_submit_event('a ball')

        assert editor.debug_text.text == 'Error: Failed to submit AI request'
        assert manager.pending_ai_requests == {}


class TestGatherTrainingExamplesFromFrame:
    """Test AIManager._gather_training_examples_from_frame."""

    def test_empty_frame_uses_the_regular_examples(self, mocker):
        """An all-magenta frame falls back to the training examples."""
        training_examples = [{'name': 'tree'}]
        mocker.patch.dict(ai_training_state, {'data': training_examples})
        canvas = FakeCanvas(pixels=[MAGENTA_TRANSPARENT] * 4)

        examples = AIManager(_editor(canvas=canvas))._gather_training_examples_from_frame('tree')  # type: ignore[arg-type]

        assert examples == training_examples

    def test_single_frame_sprite_sends_only_the_frame(self, tmp_path, temporary_files_in_tmp_path):
        """A single animation with one frame needs only the frame as context."""
        canvas = _canvas_with_sprite(tmp_path=tmp_path, content=STATIC_SPRITE_TOML)

        examples = AIManager(_editor(canvas=canvas))._gather_training_examples_from_frame('x')  # type: ignore[arg-type]

        assert len(examples) == 1
        assert examples[0]['name'] == 'selected_frame'
        assert examples[0]['sprite_type'] == 'static'
        assert len(examples[0]['pixels'].split('\n')) == 2
        assert list(temporary_files_in_tmp_path.iterdir()) == []

    def test_multi_frame_sprite_sends_the_frame_and_the_strip(self, tmp_path):
        """With several frames, both the current frame and the strip are examples."""
        canvas = _canvas_with_sprite(tmp_path=tmp_path, content=ANIMATED_SPRITE_TOML)

        examples = AIManager(_editor(canvas=canvas))._gather_training_examples_from_frame('x')  # type: ignore[arg-type]

        assert [example['name'] for example in examples] == ['selected_frame', 'selected_strip']

    def test_frame_without_a_strip_sends_only_the_frame(self):
        """A canvas with pixels but no sprite sends its frame alone."""
        canvas = FakeCanvas(pixels=[(0, 0, 0)] * 4)

        examples = AIManager(_editor(canvas=canvas))._gather_training_examples_from_frame('x')  # type: ignore[arg-type]

        assert [example['name'] for example in examples] == ['selected_frame']
        assert examples[0]['pixels'] == '..\n..'

    def test_unloadable_context_falls_back_to_regular_examples(self, mocker):
        """When neither the frame nor the strip can be saved, the training examples are used."""
        training_examples = [{'name': 'rock'}]
        mocker.patch.dict(ai_training_state, {'data': training_examples})
        canvas = FakeCanvas(pixels=[(0, 0, 0)] * 4)
        manager = AIManager(_editor(canvas=canvas))  # type: ignore[arg-type]
        mocker.patch.object(manager, '_save_current_frame_to_temp_toml', return_value=None)

        assert manager._gather_training_examples_from_frame('rock') == training_examples

    def test_unreadable_frame_file_falls_back_to_regular_examples(self, mocker):
        """A saved frame that cannot be read back falls back to the training examples."""
        training_examples = [{'name': 'rock'}]
        mocker.patch.dict(ai_training_state, {'data': training_examples})
        manager = AIManager(_editor(canvas=FakeCanvas(pixels=[(0, 0, 0)] * 4)))  # type: ignore[arg-type]
        mocker.patch.object(
            manager,
            '_save_current_frame_to_temp_toml',
            return_value='/nonexistent/frame.toml',
        )

        assert manager._gather_training_examples_from_frame('rock') == training_examples


class TestHasSingleAnimationCanvas:
    """Test AIManager._has_single_animation_canvas."""

    def test_no_canvas_is_not_single_animation(self):
        """Without a canvas there is no animation."""
        assert AIManager(_editor())._has_single_animation_canvas() is False  # type: ignore[arg-type]

    def test_canvas_without_a_sprite_is_not_single_animation(self):
        """A canvas with no sprite has no animation."""
        manager = AIManager(_editor(canvas=FakeCanvas()))  # type: ignore[arg-type]

        assert manager._has_single_animation_canvas() is False

    def test_one_animation_is_single_animation(self, tmp_path):
        """A sprite with one animation is a single-animation canvas."""
        canvas = _canvas_with_sprite(tmp_path=tmp_path, content=ANIMATED_SPRITE_TOML)

        assert AIManager(_editor(canvas=canvas))._has_single_animation_canvas() is True  # type: ignore[arg-type]


class TestSerializeCurrentSpriteForRefinement:
    """Test AIManager._serialize_current_sprite_for_refinement."""

    def test_without_a_sprite_is_not_a_refinement(self):
        """An empty canvas is not refined."""
        manager = AIManager(_editor(canvas=FakeCanvas()))  # type: ignore[arg-type]

        assert manager._serialize_current_sprite_for_refinement() == (False, None, None)

    def test_sprite_is_serialized_and_its_temp_file_removed(
        self,
        tmp_path,
        temporary_files_in_tmp_path,
    ):
        """The sprite's TOML is returned with the conversation so far."""
        canvas = _canvas_with_sprite(tmp_path=tmp_path, content=ANIMATED_SPRITE_TOML)
        manager = AIManager(_editor(canvas=canvas))  # type: ignore[arg-type]

        is_refinement, content, history = manager._serialize_current_sprite_for_refinement()

        assert is_refinement is True
        assert tomllib.loads(content)['animation'][0]['namespace'] == 'blink'
        assert history is None
        assert list(temporary_files_in_tmp_path.iterdir()) == []

    def test_save_failure_falls_back_to_generation(self):
        """A sprite that cannot be saved is not refined."""

        class UnsavableSprite:
            """A sprite whose save fails."""

            def save(self, filename: str, file_format: str) -> None:
                msg = 'disk full'
                raise OSError(msg)

        canvas = FakeCanvas()
        canvas.animated_sprite = UnsavableSprite()  # type: ignore[assignment]

        manager = AIManager(_editor(canvas=canvas))  # type: ignore[arg-type]

        assert manager._serialize_current_sprite_for_refinement() == (False, None, None)

    def test_save_failure_leaves_no_temporary_file(self, temporary_files_in_tmp_path):
        """The temporary file a failed save was meant to fill is removed (it used to stay)."""

        class UnsavableSprite:
            """A sprite whose save fails."""

            def save(self, filename: str, file_format: str) -> None:
                msg = 'disk full'
                raise OSError(msg)

        canvas = FakeCanvas()
        canvas.animated_sprite = UnsavableSprite()  # type: ignore[assignment]

        AIManager(_editor(canvas=canvas))._serialize_current_sprite_for_refinement()  # type: ignore[arg-type]

        assert list(temporary_files_in_tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# Response processing
# ---------------------------------------------------------------------------


class TestProcessAiResponse:
    """Test AIManager._process_ai_response."""

    def test_empty_response_without_an_error_says_so(self):
        """An empty response with no error reports an empty answer."""
        editor = _editor()
        manager = _manager_with_queues(editor)
        manager.pending_ai_requests['request-1'] = AIRequestState(original_prompt='ball')

        manager._process_ai_response('request-1', AIResponse(content=None))

        assert editor.debug_text.text == 'AI response was empty'
        assert manager.pending_ai_requests == {}

    def test_empty_response_for_an_unknown_request_is_reported(self):
        """An empty response for a request no longer pending still updates the UI."""
        editor = _editor()

        _manager_with_queues(editor)._process_ai_response('gone', AIResponse(content=None))

        assert editor.debug_text.text == 'AI response was empty'

    def test_valid_response_loads_the_sprite_and_records_the_turn(self):
        """A valid answer is loaded, described, remembered and its request finished."""
        canvas = FakeCanvas()
        editor = _editor(canvas=canvas)
        manager = _manager_with_queues(editor)
        history = [{'role': 'user', 'content': 'before'}, {'role': 'assistant', 'content': 'x'}]
        manager.pending_ai_requests['request-1'] = AIRequestState(
            original_prompt='a red ball',
            conversation_history=history,
        )

        manager._process_ai_response('request-1', AIResponse(content=STATIC_SPRITE_TOML))

        assert len(canvas.loaded_paths) == 1
        assert canvas.animated_sprite.description == 'a red ball'
        loaded_data = tomllib.loads(Path(canvas.loaded_paths[0]).read_text(encoding='utf-8'))
        assert loaded_data['sprite']['description'] == 'a red ball'
        # The rewrite keeps the pixel block exactly as the answer had it (BUGS.md #110 item 7)
        assert loaded_data['sprite']['pixels'] == '#.\n.#\n'
        assert canvas.animated_sprite.animations[canvas.animated_sprite.current_animation][
            0
        ].image.get_size() == (2, 2)
        assert manager.last_successful_sprite_content == Path(canvas.loaded_paths[0]).read_text(
            encoding='utf-8',
        )
        assert manager.last_conversation_history == [
            *history,
            {'role': 'user', 'content': 'a red ball'},
            {'role': 'assistant', 'content': manager.last_successful_sprite_content},
        ]
        assert editor.debug_text.text == 'a red ball'
        assert manager.pending_ai_requests == {}

    def test_fenced_valid_response_loads_without_a_retry(self):
        """An answer wrapped in markdown fences is cleaned, not retried (BUGS.md #93)."""
        canvas = FakeCanvas()
        editor = _editor(canvas=canvas)
        manager = _manager_with_queues(editor)
        manager.pending_ai_requests['request-1'] = AIRequestState(original_prompt='a red ball')

        manager._process_ai_response(
            'request-1',
            AIResponse(content=f'```toml\n{STATIC_SPRITE_TOML}```'),
        )

        assert not manager.ai_request_queue.items  # type: ignore[union-attr]
        assert len(canvas.loaded_paths) == 1
        loaded_data = tomllib.loads(Path(canvas.loaded_paths[0]).read_text(encoding='utf-8'))
        assert loaded_data['sprite']['pixels'] == '#.\n.#\n'
        assert manager.pending_ai_requests == {}

    def test_response_for_an_unknown_request_is_loaded_anyway(self):
        """A valid answer whose request is not pending is still loaded."""
        canvas = FakeCanvas()
        editor = _editor(canvas=canvas)
        manager = _manager_with_queues(editor)

        manager._process_ai_response('gone', AIResponse(content=ANIMATED_SPRITE_TOML))

        assert list(canvas.animated_sprite.animations) == ['blink']
        assert editor.debug_text.text == DEFAULT_PROMPT_TEXT
        assert manager.last_conversation_history is None

    def test_invalid_response_is_retried_with_a_corrective_prompt(self):
        """An answer missing [colors] is retried under the same id with a correction."""
        editor = _editor()
        manager = _manager_with_queues(editor)
        manager.pending_ai_requests['request-1'] = AIRequestState(original_prompt='a red ball')

        manager._process_ai_response(
            'request-1',
            AIResponse(content='[sprite]\nname = "x"\npixels = """\n#\n"""\n'),
        )

        retry_request = manager.ai_request_queue.items[0]  # type: ignore[union-attr]
        assert retry_request.request_id == 'request-1'
        assert 'You must include [colors] sections' in str(retry_request.messages)
        request_state = manager.pending_ai_requests['request-1']
        assert request_state.retry_count == 1
        assert request_state.last_error == 'Missing [colors] section'
        assert editor.debug_text.text.startswith(
            f'Retrying with corrections... (attempt 2/{AI_VALIDATION_MAX_RETRIES + 1})',
        )

    def test_invalid_response_after_the_last_retry_shows_the_error(self):
        """Out of retries, an apology is shown with the original prompt and not loaded."""
        canvas = FakeCanvas()
        editor = _editor(canvas=canvas)
        editor.debug_text.text = ''
        manager = _manager_with_queues(editor)
        manager.pending_ai_requests['request-1'] = AIRequestState(
            original_prompt='a red ball',
            retry_count=AI_VALIDATION_MAX_RETRIES,
        )
        apology = "I'm sorry, I cannot draw that."

        manager._process_ai_response('request-1', AIResponse(content=apology))

        assert canvas.loaded_paths == []
        assert not manager.ai_request_queue.items  # type: ignore[union-attr]
        # The failure notice is shown first, then the apology is appended below it
        assert editor.debug_text.text.startswith(
            f'Failed after {AI_VALIDATION_MAX_RETRIES} retries:',
        )
        assert editor.debug_text.text.endswith(
            f'\n\n{apology}\n\n--- Original Prompt ---\na red ball',
        )
        assert manager.pending_ai_requests == {}

    def test_invalid_response_after_the_last_retry_says_it_was_not_loaded(self, caplog):
        """Out of retries, the log and the text box say the sprite was not loaded.

        They said "loading sprite anyway", but loading validates the same content and
        rejects it, so nothing was ever loaded.
        """
        canvas = FakeCanvas()
        editor = _editor(canvas=canvas)
        editor.debug_text.text = ''
        manager = _manager_with_queues(editor)
        manager.pending_ai_requests['request-1'] = AIRequestState(
            original_prompt='a red ball',
            retry_count=AI_VALIDATION_MAX_RETRIES,
        )

        manager._process_ai_response(
            'request-1',
            AIResponse(content='[sprite]\nname = "x"\npixels = """\n#\n"""\n'),
        )

        assert canvas.loaded_paths == []
        assert 'Missing [colors] section' in editor.debug_text.text
        assert 'The sprite was not loaded.' in editor.debug_text.text
        assert 'anyway' not in editor.debug_text.text
        assert 'the sprite was not loaded' in caplog.text
        assert 'anyway' not in caplog.text
        assert manager.pending_ai_requests == {}

    def test_bitmappy_retries_ragged_rows(self):
        """Rows that need repair are retried with the equal-widths correction."""
        editor = _editor()
        manager = _manager_with_queues(editor)
        manager.pending_ai_requests['request-1'] = AIRequestState(original_prompt='a red ball')

        manager._process_ai_response('request-1', AIResponse(content=RAGGED_SPRITE_TOML))

        retry_request = manager.ai_request_queue.items[0]  # type: ignore[union-attr]
        assert 'every row of a frame must have the same number of characters' in str(
            retry_request.messages
        )
        assert manager.pending_ai_requests['request-1'].retry_count == 1

    def test_bitmappy_loads_ragged_rows_after_last_retry(self):
        """Out of retries, rows that need repair load repaired instead of being thrown away."""
        canvas = FakeCanvas()
        editor = _editor(canvas=canvas)
        manager = _manager_with_queues(editor)
        manager.pending_ai_requests['request-1'] = AIRequestState(
            original_prompt='a red ball',
            retry_count=AI_VALIDATION_MAX_RETRIES,
        )

        manager._process_ai_response('request-1', AIResponse(content=RAGGED_SPRITE_TOML))

        assert not manager.ai_request_queue.items  # type: ignore[union-attr]
        assert len(canvas.loaded_paths) == 1
        frame = canvas.animated_sprite.get_current_frame()
        assert frame.image.get_size() == (2, 2)
        assert canvas.animated_sprite.pixel_row_repairs
        assert manager.pending_ai_requests == {}

    def test_ai_load_with_repairs_shows_the_notice(self):
        """After the AI manager puts the prompt back, the repair notice is still below it."""
        canvas = FakeCanvas()
        editor = _editor(canvas=canvas)
        manager = _manager_with_queues(editor)
        manager.pending_ai_requests['request-1'] = AIRequestState(
            original_prompt='a red ball',
            retry_count=AI_VALIDATION_MAX_RETRIES,
        )

        manager._process_ai_response('request-1', AIResponse(content=RAGGED_SPRITE_TOML))

        assert editor.debug_text.text == (
            'a red ball\nRepaired the pixel rows of 1 block(s) while loading (details in the '
            'log). Saving writes the repaired rows.'
        )

    def test_row_check_skips_a_response_that_is_not_toml(self):
        """Content that isn't TOML has no rows to check; loading reports what's wrong with it."""
        manager = _manager_with_queues(_editor())

        assert not manager._ai_pixel_row_problems('request-1', '[sprite]\nname = = "x"\n')

    def test_bitmappy_still_discards_other_failures(self):
        """Out of retries, any other failure is still not loaded."""
        canvas = FakeCanvas()
        editor = _editor(canvas=canvas)
        manager = _manager_with_queues(editor)
        manager.pending_ai_requests['request-1'] = AIRequestState(
            original_prompt='a red ball',
            retry_count=AI_VALIDATION_MAX_RETRIES,
        )

        manager._process_ai_response(
            'request-1',
            AIResponse(content='[sprite]\nname = "x"\npixels = """\n#\n#.\n"""\n'),
        )

        assert canvas.loaded_paths == []
        assert 'The sprite was not loaded.' in editor.debug_text.text


class TestLoadAiSprite:
    """Test AIManager._load_ai_sprite error handling."""

    def test_ai_unavailable_message_asks_to_check_the_configuration(self):
        """The worker's 'AI features not available' answer is explained to the user."""
        editor = _editor()
        manager = _manager_with_queues(editor)
        manager.pending_ai_requests['request-1'] = AIRequestState(original_prompt='x')

        manager._load_ai_sprite('request-1', 'AI features not available')

        assert editor.debug_text.text == (
            'AI features not available. Please check your AI configuration.'
        )
        assert manager.pending_ai_requests == {}

    def test_error_message_replaces_an_empty_debug_text(self):
        """An apology with no prior text and no pending prompt is shown alone."""
        editor = _editor()

        _manager_with_queues(editor)._load_ai_sprite('gone', 'I apologize, unable to help.')

        assert editor.debug_text.text == 'I apologize, unable to help.'

    def test_error_message_without_a_debug_text_is_only_logged(self):
        """With no debug text box, an apology only finishes the request."""
        manager = _manager_with_queues(_editor(with_debug_text=False))
        manager.pending_ai_requests['request-1'] = AIRequestState(original_prompt='x')

        manager._load_ai_sprite('request-1', 'I apologize, unable to help.')

        assert manager.pending_ai_requests == {}

    def test_load_failure_shows_the_error_prompt_and_response(self):
        """A sprite the canvas cannot load shows the error, the prompt and the AI answer."""

        class FailingCanvas(FakeCanvas):
            def on_load_file_event(self, event: object) -> None:
                msg = 'bad sprite'
                raise ValueError(msg)

        editor = _editor(canvas=FailingCanvas())
        manager = _manager_with_queues(editor)
        manager.pending_ai_requests['request-1'] = AIRequestState(original_prompt='a red ball')

        manager._load_ai_sprite('request-1', ANIMATED_SPRITE_TOML)

        assert editor.debug_text.text == (
            'Error loading AI sprite: bad sprite\n\n--- Original Prompt ---\na red ball'
            f'\n\n--- AI Response ---\n{ANIMATED_SPRITE_TOML}'
        )
        assert 'request-1' in manager.pending_ai_requests

    def test_load_failure_without_a_prompt_or_debug_text(self):
        """Without a pending prompt the error omits it; without a text box nothing is shown."""

        class FailingCanvas(FakeCanvas):
            def on_load_file_event(self, event: object) -> None:
                msg = 'bad sprite'
                raise ValueError(msg)

        editor = _editor(canvas=FailingCanvas())
        _manager_with_queues(editor)._load_ai_sprite('gone', ANIMATED_SPRITE_TOML)
        assert editor.debug_text.text == (
            f'Error loading AI sprite: bad sprite\n\n--- AI Response ---\n{ANIMATED_SPRITE_TOML}'
        )

        silent_editor = _editor(canvas=FailingCanvas(), with_debug_text=False)
        _manager_with_queues(silent_editor)._load_ai_sprite('gone', ANIMATED_SPRITE_TOML)
        assert not hasattr(silent_editor, 'debug_text')


class TestPrepareAiContent:
    """Test AIManager._prepare_ai_content."""

    def test_error_message_is_returned_unchanged(self):
        """An apology is not cleaned or rewritten."""
        manager = AIManager(_editor())  # type: ignore[arg-type]

        assert manager._prepare_ai_content('id', 'I apologize.') == 'I apologize.'

    def test_leading_explanation_is_removed_and_description_added(self):
        """Text before the first section is dropped and the prompt becomes the description."""
        manager = AIManager(_editor())  # type: ignore[arg-type]
        manager.pending_ai_requests['id'] = AIRequestState(original_prompt='a red ball')

        prepared = manager._prepare_ai_content('id', f'Here is your sprite:\n{STATIC_SPRITE_TOML}')

        data = tomllib.loads(prepared)
        assert data['sprite']['name'] == 'ball'
        assert data['sprite']['description'] == 'a red ball'
        assert data['sprite']['pixels'].rstrip('\n') == '#.\n.#'
        assert data['colors']['#'] == {'red': 255, 'green': 0, 'blue': 0}

    def test_without_a_pending_prompt_only_cleans(self):
        """Without an original prompt, no description is added."""
        manager = AIManager(_editor())  # type: ignore[arg-type]

        prepared = manager._prepare_ai_content('id', f'Here you go:\n{STATIC_SPRITE_TOML}')

        assert prepared == STATIC_SPRITE_TOML.strip()

    def test_non_toml_training_format_adds_no_description(self, mocker):
        """The description is only added for the TOML format."""
        mocker.patch.dict(ai_training_state, {'format': None})
        manager = AIManager(_editor())  # type: ignore[arg-type]
        manager.pending_ai_requests['id'] = AIRequestState(original_prompt='a red ball')

        assert manager._prepare_ai_content('id', STATIC_SPRITE_TOML) == STATIC_SPRITE_TOML.strip()

    def test_color_without_all_components_keeps_the_cleaned_content(self):
        """A color missing a component cannot be rewritten, so the cleaned answer is kept."""
        content = '[sprite]\nname = "x"\npixels = """\n#\n"""\n\n[colors."#"]\nred = 1\ngreen = 2\n'
        manager = AIManager(_editor())  # type: ignore[arg-type]
        manager.pending_ai_requests['id'] = AIRequestState(original_prompt='x')

        assert manager._prepare_ai_content('id', content) == content.strip()

    def test_sprite_without_a_sprite_table_gets_one_for_the_description(self):
        """Content whose sections parse without [sprite] still gets a described sprite table."""
        content = '# [sprite]\n[colors."#"]\nred = 1\ngreen = 2\nblue = 3\n'
        manager = AIManager(_editor())  # type: ignore[arg-type]
        manager.pending_ai_requests['id'] = AIRequestState(original_prompt='dot')

        prepared = manager._prepare_ai_content('id', content)

        assert tomllib.loads(prepared) == {
            'sprite': {'description': 'dot'},
            'colors': {'#': {'red': 1, 'green': 2, 'blue': 3}},
        }


class TestConstructTomlWithPreservedFormatting:
    """Test AIManager._construct_toml_with_preserved_formatting."""

    def test_animated_sprite_round_trips(self):
        """Animation sections are written back so the TOML parses to the same data."""
        data = tomllib.loads(ANIMATED_SPRITE_TOML)

        content = AIManager(_editor())._construct_toml_with_preserved_formatting(data)  # type: ignore[arg-type]

        reparsed = tomllib.loads(content)
        assert reparsed['animation'][0]['loop'] is True
        assert reparsed['animation'][0]['frame_interval'] == pytest.approx(0.5)
        assert [frame['pixels'] for frame in reparsed['animation'][0]['frame']] == [
            '#.\n.#\n',
            '.#\n#.\n',
        ]
        assert reparsed['colors'] == data['colors']

    def test_rewriting_twice_adds_no_blank_lines_to_pixel_blocks(self):
        """A rewrite of a rewrite keeps every pixel block unchanged (BUGS.md #110 item 7)."""
        manager = AIManager(_editor())  # type: ignore[arg-type]
        static_data = tomllib.loads(STATIC_SPRITE_TOML)
        animated_data = tomllib.loads(ANIMATED_SPRITE_TOML)

        static_once = manager._construct_toml_with_preserved_formatting(static_data)
        static_twice = manager._construct_toml_with_preserved_formatting(
            tomllib.loads(static_once),
        )
        animated_once = manager._construct_toml_with_preserved_formatting(animated_data)
        animated_twice = manager._construct_toml_with_preserved_formatting(
            tomllib.loads(animated_once),
        )

        assert static_twice == static_once
        assert tomllib.loads(static_twice)['sprite']['pixels'] == '#.\n.#\n'
        assert animated_twice == animated_once

    def test_sprite_without_name_or_pixels_writes_only_what_it_has(self):
        """Only the sprite fields present are written."""
        content = AIManager(_editor())._construct_toml_with_preserved_formatting(  # type: ignore[arg-type]
            {'sprite': {}},
        )

        assert content == '[sprite]\n'

    def test_ai_rewrite_accepts_a_non_string_name(self):
        """An AI that writes name = 5 still gets a rewrite, as it did before escaping."""
        content = AIManager(_editor())._construct_toml_with_preserved_formatting(  # type: ignore[arg-type]
            {'sprite': {'name': 5}},
        )

        assert tomllib.loads(content)['sprite']['name'] == '5'

    def test_ai_rewrite_keeps_alpha(self):
        """A color's alpha is written back, so a see-through color stays see-through."""
        data = tomllib.loads(STATIC_SPRITE_TOML)
        first_glyph = next(iter(data['colors']))
        data['colors'][first_glyph]['alpha'] = 128

        content = AIManager(_editor())._construct_toml_with_preserved_formatting(data)  # type: ignore[arg-type]

        assert tomllib.loads(content)['colors'][first_glyph]['alpha'] == 128

    def test_ai_rewrite_escapes_name_description_and_rows(self):
        """Text and rows with TOML's own characters parse back to the same values."""
        data = {
            'sprite': {
                'name': 'a "quoted" \\ name',
                'description': 'draw """ a \\ thing',
                'pixels': 'b\\\nbb\n',
            },
            'animation': [
                {
                    'namespace': 'walk',
                    'frame_interval': 0.5,
                    'loop': True,
                    'frame': [{'frame_index': 0, 'pixels': '"b\nb\\\n'}],
                }
            ],
            'colors': {
                '\\': {'red': 1, 'green': 2, 'blue': 3},
                '"': {'red': 4, 'green': 5, 'blue': 6},
                'b': {'red': 7, 'green': 8, 'blue': 9},
            },
        }

        content = AIManager(_editor())._construct_toml_with_preserved_formatting(data)  # type: ignore[arg-type]

        reparsed = tomllib.loads(content)
        assert reparsed['sprite'] == data['sprite']
        assert reparsed['animation'][0]['frame'][0]['pixels'] == '"b\nb\\\n'
        assert reparsed['colors'] == data['colors']


class TestTemporaryFilesAndStaticLoad:
    """Test temp file creation and the static sprite load path."""

    def test_temp_file_uses_the_training_format_extension(self, temporary_files_in_tmp_path):
        """The temp file is named after the training format and holds the content."""
        temp_path = Path(AIManager(_editor())._create_temp_file_from_content('abc'))  # type: ignore[arg-type]

        assert temp_path.parent == temporary_files_in_tmp_path
        assert temp_path.suffix == '.toml'
        assert temp_path.read_text(encoding='utf-8') == 'abc'

    def test_temp_file_defaults_to_toml_without_a_format(self, mocker):
        """With no detected training format the extension is .toml."""
        mocker.patch.dict(ai_training_state, {'format': None})

        temp_path = AIManager(_editor())._create_temp_file_from_content('abc')  # type: ignore[arg-type]

        assert temp_path.endswith('.toml')

    def test_static_load_redraws_the_canvas_and_marks_sprites_dirty(self, tmp_path):
        """Loading a static sprite redraws the canvas and dirties every scene sprite."""
        canvas = FakeCanvas()
        other_sprite = SimpleNamespace(dirty=0)
        editor = _editor(canvas=canvas)
        editor.all_sprites = [other_sprite, object()]
        sprite_path = _write_sprite(tmp_path=tmp_path, name='s.toml', content=STATIC_SPRITE_TOML)

        AIManager(editor)._load_static_ai_sprite(sprite_path)  # type: ignore[arg-type]

        assert canvas.loaded_paths == [sprite_path]
        assert canvas.dirty == 1
        assert canvas.redraw_count == 1
        assert other_sprite.dirty == 1

    def test_static_load_without_a_resulting_sprite_still_redraws(self, tmp_path):
        """A canvas whose load leaves no sprite is still redrawn."""

        class NoSpriteCanvas(FakeCanvas):
            def on_load_file_event(self, event: object) -> None:
                self.loaded_paths.append(event.text)  # type: ignore[attr-defined]

        canvas = NoSpriteCanvas()
        editor = _editor(canvas=canvas)
        del editor.all_sprites

        AIManager(editor)._load_static_ai_sprite('x.toml')  # type: ignore[arg-type]

        assert canvas.redraw_count == 1

    def test_detected_static_file_loads_through_the_canvas(self, tmp_path):
        """SpriteFactory turns a static file into a one-animation sprite, loaded as animated."""
        canvas = FakeCanvas()
        sprite_path = _write_sprite(tmp_path=tmp_path, name='s.toml', content=STATIC_SPRITE_TOML)

        AIManager(_editor(canvas=canvas))._detect_and_load_ai_sprite(sprite_path)  # type: ignore[arg-type]

        assert canvas.loaded_paths == [sprite_path]
        assert canvas.redraw_count == 0

    def test_detected_file_without_frames_loads_as_static(self, tmp_path):
        """An animation with no frames leaves no animations, so it takes the static load path."""
        canvas = FakeCanvas()
        sprite_path = _write_sprite(
            tmp_path=tmp_path,
            name='frameless.toml',
            content='[sprite]\nname = "frameless"\n\n[[animation]]\nnamespace = "idle"\n',
        )

        AIManager(_editor(canvas=canvas))._detect_and_load_ai_sprite(sprite_path)  # type: ignore[arg-type]

        assert canvas.loaded_paths == [sprite_path]
        assert canvas.redraw_count == 1


# ---------------------------------------------------------------------------
# Current frame and strip context
# ---------------------------------------------------------------------------


class TestCheckCurrentFrameHasContent:
    """Test AIManager._check_current_frame_has_content."""

    @pytest.mark.parametrize(
        ('pixels', 'has_content'),
        [
            ([], False),
            ([MAGENTA_TRANSPARENT, (255, 0, 255, 255)], False),
            ([MAGENTA_TRANSPARENT, (0, 0, 0)], True),
            ([(1, 2, 3)] * 8, True),
            ([(5,)], True),
        ],
    )
    def test_any_non_magenta_pixel_is_content(self, pixels, has_content):
        """A frame has content when any pixel is not magenta."""
        manager = AIManager(_editor(canvas=FakeCanvas(pixels=pixels)))  # type: ignore[arg-type]

        assert manager._check_current_frame_has_content() is has_content

    def test_without_a_canvas_there_is_no_content(self):
        """No canvas means no content."""
        assert AIManager(_editor())._check_current_frame_has_content() is False  # type: ignore[arg-type]

    def test_malformed_pixels_have_no_content(self):
        """Pixels that are not sequences are treated as an empty frame."""
        manager = AIManager(_editor(canvas=FakeCanvas(pixels=[7])))  # type: ignore[arg-type]

        assert manager._check_current_frame_has_content() is False


class TestSaveCurrentFrameToTempToml:
    """Test AIManager._save_current_frame_to_temp_toml."""

    def test_frame_is_written_as_a_sprite(self, temporary_files_in_tmp_path):
        """The frame becomes a static sprite TOML in the temp directory."""
        canvas = FakeCanvas(pixels=[(0, 0, 0), (9, 9, 9), (9, 9, 9), (0, 0, 0)])

        temp_path = AIManager(_editor(canvas=canvas))._save_current_frame_to_temp_toml()  # type: ignore[arg-type]

        assert temp_path is not None
        assert Path(temp_path).parent == temporary_files_in_tmp_path
        data = tomllib.loads(Path(temp_path).read_text(encoding='utf-8'))
        assert data['sprite'] == {'name': 'current_frame', 'pixels': '.a\na.\n'}

    def test_without_a_canvas_nothing_is_saved(self):
        """No canvas, no file."""
        assert AIManager(_editor())._save_current_frame_to_temp_toml() is None  # type: ignore[arg-type]

    def test_empty_frame_is_not_saved(self):
        """A canvas without pixels saves nothing."""
        manager = AIManager(_editor(canvas=FakeCanvas()))  # type: ignore[arg-type]

        assert manager._save_current_frame_to_temp_toml() is None

    def test_unwritable_temp_directory_saves_nothing(self, mocker, tmp_path):
        """A temp directory that does not exist makes the save fail quietly."""
        mocker.patch.object(tempfile, 'tempdir', str(tmp_path / 'missing'))
        manager = AIManager(_editor(canvas=FakeCanvas(pixels=[(0, 0, 0)] * 4)))  # type: ignore[arg-type]

        assert manager._save_current_frame_to_temp_toml() is None


class TestSaveCurrentStripToTempToml:
    """Test AIManager._save_current_strip_to_temp_toml."""

    def test_current_animation_is_saved_alone(self, tmp_path):
        """The strip file holds only the canvas's current animation."""
        canvas = _canvas_with_sprite(tmp_path=tmp_path, content=ANIMATED_SPRITE_TOML)

        temp_path = AIManager(_editor(canvas=canvas))._save_current_strip_to_temp_toml()  # type: ignore[arg-type]

        assert temp_path is not None
        data = tomllib.loads(Path(temp_path).read_text(encoding='utf-8'))
        assert data['sprite']['name'] == 'current_strip_blink'
        assert [animation['namespace'] for animation in data['animation']] == ['blink']
        assert len(data['animation'][0]['frame']) == 2

    def test_without_a_canvas_nothing_is_saved(self):
        """No canvas, no strip."""
        assert AIManager(_editor())._save_current_strip_to_temp_toml() is None  # type: ignore[arg-type]

    def test_without_a_sprite_nothing_is_saved(self):
        """A canvas with no sprite has no strip."""
        manager = AIManager(_editor(canvas=FakeCanvas()))  # type: ignore[arg-type]

        assert manager._save_current_strip_to_temp_toml() is None

    def test_unknown_current_animation_is_not_saved(self, tmp_path):
        """A current animation the sprite does not have saves nothing."""
        canvas = _canvas_with_sprite(tmp_path=tmp_path, content=ANIMATED_SPRITE_TOML)
        canvas.current_animation = 'missing'

        assert AIManager(_editor(canvas=canvas))._save_current_strip_to_temp_toml() is None  # type: ignore[arg-type]

    def test_unwritable_temp_directory_saves_nothing(self, mocker, tmp_path):
        """A temp directory that does not exist makes the save fail quietly."""
        canvas = _canvas_with_sprite(tmp_path=tmp_path, content=ANIMATED_SPRITE_TOML)
        mocker.patch.object(tempfile, 'tempdir', str(tmp_path / 'missing'))

        assert AIManager(_editor(canvas=canvas))._save_current_strip_to_temp_toml() is None  # type: ignore[arg-type]

    def test_save_failure_leaves_no_temporary_file(
        self,
        mocker,
        tmp_path,
        temporary_files_in_tmp_path,
    ):
        """A strip that cannot be saved gives no path and leaves no temporary file behind."""
        canvas = _canvas_with_sprite(tmp_path=tmp_path, content=ANIMATED_SPRITE_TOML)
        mocker.patch.object(AnimatedSprite, 'save', side_effect=OSError('disk full'))

        assert AIManager(_editor(canvas=canvas))._save_current_strip_to_temp_toml() is None  # type: ignore[arg-type]
        assert list(temporary_files_in_tmp_path.iterdir()) == []


class TestGenerateFrameTomlContent:
    """Test AIManager._generate_frame_toml_content."""

    def test_many_colors_are_quantized_to_single_char_glyphs(self):
        """More than 64 colors are reduced so every glyph is one of the first 64."""
        pixels = [(index * 3, 0, 0) for index in range(80)]
        canvas = FakeCanvas(pixels=pixels, pixels_across=80, pixels_tall=1)

        content = AIManager(_editor(canvas=canvas))._generate_frame_toml_content(  # type: ignore[arg-type]
            pixels,
            force_single_char_glyphs=True,
        )

        data = tomllib.loads(content)
        assert len(data['colors']) <= 64
        assert set(data['sprite']['pixels'].strip()) <= set(SPRITE_GLYPHS[:64])

    def test_magenta_also_defines_the_transparent_glyph(self):
        """A frame with magenta defines the transparency glyph as magenta too."""
        pixels = [MAGENTA_TRANSPARENT, (0, 0, 0)]
        canvas = FakeCanvas(pixels=pixels, pixels_across=2, pixels_tall=1)

        content = AIManager(_editor(canvas=canvas))._generate_frame_toml_content(pixels)  # type: ignore[arg-type]

        colors = tomllib.loads(content)['colors']
        assert colors[TRANSPARENT_GLYPH] == {'red': 255, 'green': 0, 'blue': 255}

    def test_canvas_without_a_size_gives_empty_content(self):
        """Without the canvas dimensions no TOML can be generated."""
        manager = AIManager(_editor(canvas=SimpleNamespace()))  # type: ignore[arg-type]

        assert not manager._generate_frame_toml_content([(0, 0, 0)])


class TestLoadTempTomlAsExample:
    """Test AIManager._load_temp_toml_as_example."""

    def test_example_keeps_pixel_newlines_and_removes_the_file(self, tmp_path):
        """The example has the sprite's name, raw pixel rows and colors; the file is deleted."""
        sprite_path = _write_sprite(tmp_path=tmp_path, name='e.toml', content=STATIC_SPRITE_TOML)

        example = AIManager(_editor())._load_temp_toml_as_example(sprite_path)  # type: ignore[arg-type]

        assert example == {
            'name': 'ball',
            'sprite_type': 'static',
            'pixels': '#.\n.#',
            'colors': {
                '#': {'red': 255, 'green': 0, 'blue': 0},
                '.': {'red': 255, 'green': 0, 'blue': 255},
            },
        }
        assert not Path(sprite_path).exists()

    def test_animated_example_carries_every_frame(self, tmp_path):
        """An animated strip's example holds every frame, not only the first one.

        It used to extract only the first pixels block and label the strip static.
        """
        sprite_path = _write_sprite(
            tmp_path=tmp_path, name='strip.toml', content=ANIMATED_SPRITE_TOML
        )

        example = AIManager(_editor())._load_temp_toml_as_example(sprite_path)  # type: ignore[arg-type]

        assert example is not None
        assert example['name'] == 'blinker'
        assert example['sprite_type'] == 'animated'
        assert example['raw_content'] == ANIMATED_SPRITE_TOML
        [animation] = example['animations']
        assert animation['namespace'] == 'blink'
        assert [frame['pixels'] for frame in animation['frame']] == ['#.\n.#', '.#\n#.']
        assert example['pixels'] == '#.\n.#\n\n.#\n#.'
        assert set(example['colors']) == {'#', '.'}
        assert not Path(sprite_path).exists()

    def test_file_that_cannot_be_removed_still_gives_an_example(self, mocker, tmp_path):
        """Failing to delete the temp file does not lose the example."""
        sprite_path = _write_sprite(tmp_path=tmp_path, name='e.toml', content=STATIC_SPRITE_TOML)
        mocker.patch.object(Path, 'unlink', side_effect=OSError('busy'))

        example = AIManager(_editor())._load_temp_toml_as_example(sprite_path)  # type: ignore[arg-type]

        assert example is not None
        assert example['name'] == 'ball'

    def test_invalid_toml_gives_no_example(self, tmp_path):
        """A file that is not TOML yields no example."""
        sprite_path = _write_sprite(tmp_path=tmp_path, name='bad.toml', content='[sprite\n')

        assert AIManager(_editor())._load_temp_toml_as_example(sprite_path) is None  # type: ignore[arg-type]

    def test_unreadable_example_file_is_still_removed(self, tmp_path):
        """A temporary file that is not TOML is removed too (it used to be left behind)."""
        sprite_path = _write_sprite(tmp_path=tmp_path, name='bad.toml', content='[sprite\n')

        AIManager(_editor())._load_temp_toml_as_example(sprite_path)  # type: ignore[arg-type]

        assert not Path(sprite_path).exists()

    def test_missing_example_file_gives_no_example(self, tmp_path):
        """A file that is already gone yields no example and no cleanup error."""
        missing_path = str(tmp_path / 'missing.toml')

        assert AIManager(_editor())._load_temp_toml_as_example(missing_path) is None  # type: ignore[arg-type]


class TestSmallHelpers:
    """Tests for the manager's small helpers."""

    def test_glyph_for_color_is_stable_and_single_char(self):
        """A color always gets the same glyph from the first 64."""
        manager = AIManager(_editor())  # type: ignore[arg-type]

        glyph = manager._get_glyph_for_color((1, 2, 3))

        assert glyph == manager._get_glyph_for_color((1, 2, 3))
        assert glyph in SPRITE_GLYPHS[:64]

    def test_debug_text_change_becomes_the_sprite_description(self, tmp_path):
        """Editing the prompt text updates the loaded sprite's description."""
        canvas = _canvas_with_sprite(tmp_path=tmp_path, content=STATIC_SPRITE_TOML)

        AIManager(_editor(canvas=canvas))._on_debug_text_change('a shiny ball')  # type: ignore[arg-type]

        assert canvas.animated_sprite.description == 'a shiny ball'

    def test_clean_ai_response_keeps_the_unavailable_message(self):
        """The unavailable message is passed through for upstream handling."""
        manager = AIManager(_editor())  # type: ignore[arg-type]

        assert manager._clean_ai_response('AI features not available.') == (
            'AI features not available.'
        )

    def test_clean_ai_response_strips_markdown_fences(self):
        """A fenced answer is reduced to its TOML."""
        manager = AIManager(_editor())  # type: ignore[arg-type]

        assert manager._clean_ai_response(f'```toml\n{STATIC_SPRITE_TOML}```') == (
            STATIC_SPRITE_TOML.strip()
        )

    def test_clean_ai_response_that_cleans_to_nothing_keeps_the_original(self):
        """When cleaning leaves nothing, the original answer is kept."""
        manager = AIManager(_editor())  # type: ignore[arg-type]

        assert manager._clean_ai_response('```\n```') == '```\n```'


class TestWithoutDebugText:
    """Every path works on an editor that has no debug text box."""

    def test_submission_and_its_failure_need_no_debug_text(self):
        """Requests are queued, and failures handled, without a debug text box."""
        editor = _editor(with_debug_text=False)
        manager = _manager_with_queues(editor)

        manager.on_text_submit_event('a ball')
        manager.ai_request_queue.put_error = OSError('queue full')  # type: ignore[union-attr]
        manager.on_text_submit_event('a tree')

        assert len(manager.ai_request_queue.items) == 1  # type: ignore[union-attr]
        assert len(manager.pending_ai_requests) == 1
        assert not hasattr(editor, 'debug_text')

    def test_unavailable_worker_needs_no_debug_text(self):
        """No queue or a dead worker is only logged."""
        editor = _editor(with_debug_text=False)
        AIManager(editor).on_text_submit_event('a ball')  # type: ignore[arg-type]
        manager = _manager_with_queues(editor)
        manager.ai_process = FakeProcess()  # type: ignore[assignment]

        manager.on_text_submit_event('a ball')

        assert not manager.ai_request_queue.items  # type: ignore[union-attr]
        assert not hasattr(editor, 'debug_text')

    def test_empty_and_unavailable_responses_need_no_debug_text(self):
        """Empty and 'not available' answers finish their requests silently."""
        manager = _manager_with_queues(_editor(with_debug_text=False))
        manager.pending_ai_requests['empty'] = AIRequestState(original_prompt='x')
        manager.pending_ai_requests['unavailable'] = AIRequestState(original_prompt='y')

        manager._process_ai_response('empty', AIResponse(content=None))
        manager._load_ai_sprite('unavailable', 'AI features not available')

        assert manager.pending_ai_requests == {}

    def test_retries_need_no_debug_text(self):
        """An invalid answer is retried, and finally given up on, without a text box."""
        manager = _manager_with_queues(_editor(with_debug_text=False))
        manager.pending_ai_requests['request-1'] = AIRequestState(original_prompt='x')

        for _ in range(AI_VALIDATION_MAX_RETRIES + 1):
            manager._process_ai_response('request-1', AIResponse(content='I apologize.'))

        assert len(manager.ai_request_queue.items) == AI_VALIDATION_MAX_RETRIES  # type: ignore[union-attr]
        assert manager.pending_ai_requests == {}

    def test_successful_load_needs_no_debug_text(self):
        """A valid answer loads into the canvas without a text box."""
        canvas = FakeCanvas()
        manager = _manager_with_queues(_editor(canvas=canvas, with_debug_text=False))
        manager.pending_ai_requests['request-1'] = AIRequestState(original_prompt='ball')

        manager._process_ai_response('request-1', AIResponse(content=STATIC_SPRITE_TOML))

        assert len(canvas.loaded_paths) == 1
        assert manager.pending_ai_requests == {}


class TestRemainingBranches:
    """Smaller branches of the response and cleanup paths."""

    def test_valid_response_that_fails_to_load_finishes_the_request(self):
        """A valid answer the canvas rejects is still removed from the pending requests."""

        class FailingCanvas(FakeCanvas):
            def on_load_file_event(self, event: object) -> None:
                msg = 'cannot read'
                raise OSError(msg)

        editor = _editor(canvas=FailingCanvas())
        manager = _manager_with_queues(editor)
        manager.pending_ai_requests['request-1'] = AIRequestState(original_prompt='ball')

        manager._process_ai_response('request-1', AIResponse(content=STATIC_SPRITE_TOML))

        assert editor.debug_text.text.startswith('Error loading AI sprite: cannot read')
        assert manager.pending_ai_requests == {}

    def test_first_turn_starts_the_conversation_history(self):
        """A request with no earlier history starts one with its own turn."""
        manager = AIManager(_editor())  # type: ignore[arg-type]
        manager.pending_ai_requests['request-1'] = AIRequestState(original_prompt='ball')

        manager._update_conversation_history('request-1', 'ball', '[sprite]')

        assert manager.last_conversation_history == [
            {'role': 'user', 'content': 'ball'},
            {'role': 'assistant', 'content': '[sprite]'},
        ]

    def test_conversation_history_ignores_unknown_requests(self):
        """A request that is not pending leaves the history alone."""
        manager = AIManager(_editor())  # type: ignore[arg-type]

        manager._update_conversation_history('gone', 'ball', '[sprite]')

        assert manager.last_conversation_history is None

    def test_strip_that_cannot_be_read_sends_only_the_frame(self, mocker):
        """When the strip file cannot be read back, the frame is the only example."""
        manager = AIManager(_editor(canvas=FakeCanvas(pixels=[(0, 0, 0)] * 4)))  # type: ignore[arg-type]
        mocker.patch.object(
            manager,
            '_save_current_strip_to_temp_toml',
            return_value='/nonexistent/strip.toml',
        )

        examples = manager._gather_training_examples_from_frame('x')

        assert [example['name'] for example in examples] == ['selected_frame']

    def test_colors_only_data_writes_only_colors(self):
        """Data with no sprite or animation writes just the color tables."""
        content = AIManager(_editor())._construct_toml_with_preserved_formatting(  # type: ignore[arg-type]
            {'colors': {'#': {'red': 1, 'green': 2, 'blue': 3}}},
        )

        assert tomllib.loads(content) == {'colors': {'#': {'red': 1, 'green': 2, 'blue': 3}}}

    def test_cleanup_without_a_worker_does_nothing(self):
        """Cleaning up a manager that never started is safe."""
        manager = AIManager(_editor())  # type: ignore[arg-type]

        manager.cleanup()
        manager.cleanup()

        assert (manager.ai_process, manager.ai_request_queue, manager.ai_response_queue) == (
            None,
            None,
            None,
        )


class TestAiFeatureFlag:
    """constants.AI_FEATURES_ENABLED: off in WebAssembly builds, where no worker can start."""

    def test_the_flag_is_on_where_processes_can_start(self):
        """This (desktop) interpreter is not emscripten: AI features are on."""
        assert sys.platform != 'emscripten'
        assert constants_module.AI_FEATURES_ENABLED is True

    def test_the_flag_is_off_on_emscripten(self):
        """Imported on emscripten (a browser build), the flag is off.

        In a fresh interpreter: importing the constants again in this one would rebind the
        package's attribute for later tests.
        """
        program = textwrap.dedent("""
            import importlib
            import sys

            # Imported as on desktop first (pygame's own import checks the platform too), then
            # the constants are evaluated again as a browser build would
            from bitmappy import constants

            sys.platform = 'emscripten'
            print(importlib.reload(constants).AI_FEATURES_ENABLED)
        """)
        completed = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - this interpreter, a fixed program
            [sys.executable, '-c', program],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, 'PYGAME_HIDE_SUPPORT_PROMPT': '1'},
        )

        assert completed.returncode == 0, completed.stderr[-2000:]
        assert completed.stdout.strip() == 'False'

    def test_setup_starts_no_worker_with_the_flag_off(self, mocker, fake_process_class):
        mocker.patch.object(ai_manager_module, 'AI_FEATURES_ENABLED', new=False)
        manager = AIManager(_editor())  # type: ignore[arg-type]

        manager.setup()

        assert manager.ai_process is None
        assert manager.ai_request_queue is None
        assert manager not in ai_manager_module._RUNNING_AI_MANAGERS
        manager.cleanup()

    def test_a_request_with_the_flag_off_says_ai_is_off(self, mocker):
        mocker.patch.object(ai_manager_module, 'AI_FEATURES_ENABLED', new=False)
        editor = _editor()

        AIManager(editor).on_text_submit_event('a ball')  # type: ignore[arg-type]

        assert editor.debug_text.text == 'AI features are off in this build'

    def test_a_request_with_the_flag_off_and_no_debug_text_is_ignored(self, mocker):
        mocker.patch.object(ai_manager_module, 'AI_FEATURES_ENABLED', new=False)
        editor = _editor(with_debug_text=False)

        AIManager(editor).on_text_submit_event('a ball')  # type: ignore[arg-type]

        assert not hasattr(editor, 'debug_text')
