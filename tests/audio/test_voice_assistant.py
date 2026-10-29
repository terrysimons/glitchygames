"""Tests for the push-to-talk voice assistant (glitchygames/audio/voice_assistant.py).

The controller's audio, speech_recognition, aisuite and the TTS backend are the boundaries
and are replaced with fakes; the background pipeline is run synchronously.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import types
from pathlib import Path
from typing import ClassVar

import pytest

import glitchygames.audio
from glitchygames.audio import voice_assistant
from glitchygames.audio.voice_assistant import VoiceAssistant
from glitchygames.process import OutputCapture, run_command

HEARD_TEXT = 'how do I jump'
AI_ANSWER = 'Press the cross button to jump.'
SPEECH_FILE = Path('generated-speech.wav')
# Run in a fresh interpreter: whether the engine and its live voices import aisuite, whether
# asking the package for the voice assistant does, and whether that is the class its module defines
LAZY_IMPORT_PROBE = """\
import json, sys
import glitchygames.engine, glitchygames.audio.live
before = 'aisuite' in sys.modules
from glitchygames.audio import VoiceAssistant
from glitchygames.audio.voice_assistant import VoiceAssistant as Defined
print(json.dumps([before, 'aisuite' in sys.modules, VoiceAssistant is Defined]))
"""


class FakeUnknownValueError(Exception):
    """Stands in for speech_recognition.UnknownValueError."""


class FakeRequestError(Exception):
    """Stands in for speech_recognition.RequestError."""


class RecordedThread:
    """Stands in for threading.Thread: records the target so a test can run it synchronously."""

    created: ClassVar[list[RecordedThread]] = []

    def __init__(self, *, target, args, daemon):
        """Keep the thread's target, arguments and daemon flag."""
        self.target = target
        self.args = args
        self.daemon = daemon
        self.started = False
        RecordedThread.created.append(self)

    def start(self):
        """Record the start; the test runs the target itself."""
        self.started = True

    def run_now(self):
        """Run the thread's target on the calling thread."""
        self.target(*self.args)


class FakeAIClient:
    """Stands in for aisuite.Client: answers scripted replies and records the requests.

    A reply may be a string, an exception to raise, or a callable run during the request (to act
    while the request is in flight) whose result is used as the reply.
    """

    def __init__(self, *, replies, requests):
        """Answer from `replies` (consumed in order) and append each request to `requests`."""
        self._replies = replies
        self._requests = requests
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self._create),
        )

    def _create(self, *, model, messages):
        self._requests.append({'model': model, 'messages': [dict(item) for item in messages]})
        reply = self._replies.pop(0)
        if callable(reply):
            reply = reply()
        if isinstance(reply, Exception):
            raise reply
        message = types.SimpleNamespace(content=reply)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


@pytest.fixture
def controller(mocker):
    """A ControllerAudio stand-in with a microphone and a speaker.

    Returns:
        The mock controller audio.

    """
    controller_audio = mocker.Mock(name='ControllerAudio')
    controller_audio.has_microphone = True
    controller_audio.has_speaker = True
    controller_audio.start_capture.return_value = True
    controller_audio.stop_capture.return_value = b'\x01\x02\x03\x04'
    controller_audio.get_speech_recognizer_audio.return_value = 'audio-data'
    return controller_audio


@pytest.fixture
def tts_backend(mocker):
    """Install a TTS backend stand-in that writes SPEECH_FILE.

    Returns:
        The mock TTS backend.

    """
    backend = mocker.Mock(name='TTSBackend')
    backend.speak_to_file.return_value = SPEECH_FILE
    mocker.patch.object(voice_assistant, 'get_tts_backend', return_value=backend)
    return backend


@pytest.fixture
def recognizer(mocker):
    """Install a speech_recognition stand-in whose recognizer hears HEARD_TEXT.

    Returns:
        The mock recognizer instance.

    """
    recognizer_instance = mocker.Mock(name='Recognizer')
    recognizer_instance.recognize_google.return_value = HEARD_TEXT
    fake_speech_recognition = types.SimpleNamespace(
        Recognizer=lambda: recognizer_instance,
        UnknownValueError=FakeUnknownValueError,
        RequestError=FakeRequestError,
    )
    mocker.patch.object(voice_assistant, 'sr', fake_speech_recognition)
    return recognizer_instance


@pytest.fixture
def ai_replies(mocker):
    """Install an aisuite stand-in; the test fills the replies list it answers from.

    Returns:
        A namespace with the `replies` to answer and the `requests` received.

    """
    exchange = types.SimpleNamespace(replies=[], requests=[])
    mocker.patch.object(
        voice_assistant,
        'ai',
        types.SimpleNamespace(
            Client=lambda: FakeAIClient(replies=exchange.replies, requests=exchange.requests)
        ),
    )
    return exchange


@pytest.fixture
def recorded_threads(mocker):
    """Replace threading in voice_assistant with RecordedThread (Lock stays real).

    Returns:
        The list of threads created during the test.

    """
    RecordedThread.created = []
    mocker.patch.object(
        voice_assistant,
        'threading',
        types.SimpleNamespace(Thread=RecordedThread, Lock=threading.Lock),
    )
    return RecordedThread.created


@pytest.fixture
def delivered():
    """Callbacks recording what the assistant delivers.

    Returns:
        A namespace of transcriptions, responses and errors lists.

    """
    return types.SimpleNamespace(transcriptions=[], responses=[], errors=[])


@pytest.fixture
def assistant(controller, tts_backend, delivered):
    """A VoiceAssistant wired to the recording callbacks.

    Returns:
        The assistant.

    """
    return VoiceAssistant(
        controller,
        ai_provider='test-provider',
        ai_model='test-model',
        system_prompt='Be brief.',
        on_transcription=delivered.transcriptions.append,
        on_response=delivered.responses.append,
        on_error=delivered.errors.append,
    )


class TestConfiguration:
    """The AI provider and model come from arguments, then the environment, then defaults."""

    def test_arguments_win(self, assistant):
        """Explicit provider and model are used."""
        assert assistant._ai_provider == 'test-provider'
        assert assistant._ai_model == 'test-model'

    def test_environment_then_defaults(self, controller, tts_backend, monkeypatch):
        """SPRITE_AI_PROVIDER / SPRITE_AI_MODEL apply when set, else the defaults."""
        monkeypatch.setenv('SPRITE_AI_PROVIDER', 'env-provider')
        monkeypatch.delenv('SPRITE_AI_MODEL', raising=False)

        configured = VoiceAssistant(controller)

        assert configured._ai_provider == 'env-provider'
        assert configured._ai_model == 'claude-sonnet-4-5'
        assert configured.is_listening is False
        assert configured.is_processing is False


class TestListening:
    """start_listening and stop_listening_and_respond drive the capture and the pipeline."""

    def test_start_buzzes_and_captures(self, assistant, controller):
        """A haptic buzz confirms the mic, then capture starts."""
        assert assistant.start_listening() is True

        controller.play_haptic.assert_called_once_with('buzz', duration=0.08)
        controller.start_capture.assert_called_once_with()
        assert assistant.is_listening is True

    def test_start_while_listening_or_processing_is_refused(self, assistant, controller):
        """A second press while busy does nothing."""
        assistant.start_listening()
        assert assistant.start_listening() is False

        assistant._listening = False
        assistant._processing = True
        assert assistant.start_listening() is False
        assert controller.start_capture.call_count == 1

    def test_start_without_microphone_reports_an_error(self, assistant, controller, delivered):
        """No microphone: an error is delivered on the next update."""
        controller.has_microphone = False

        assert assistant.start_listening() is False
        assistant.update()

        assert delivered.errors == ['No microphone found on controller']
        controller.start_capture.assert_not_called()

    def test_start_when_capture_fails(self, assistant, controller):
        """A capture that does not start leaves the assistant idle."""
        controller.start_capture.return_value = False

        assert assistant.start_listening() is False
        assert assistant.is_listening is False

    def test_stop_without_listening_does_nothing(self, assistant, controller, recorded_threads):
        """A release without a press starts nothing."""
        assistant.stop_listening_and_respond()

        controller.stop_capture.assert_not_called()
        assert recorded_threads == []

    def test_stop_hands_the_audio_to_a_daemon_thread(self, assistant, controller, recorded_threads):
        """The captured audio goes to the pipeline thread; the assistant is processing."""
        assistant.start_listening()
        assistant.stop_listening_and_respond()

        (thread,) = recorded_threads
        assert thread.started is True
        assert thread.daemon is True
        assert thread.target == assistant._process_pipeline
        assert thread.args == (b'\x01\x02\x03\x04',)
        assert assistant.is_listening is False
        assert assistant.is_processing is True


class TestPipeline:
    """The pipeline transcribes, asks the AI, delivers the text and speaks it."""

    @pytest.mark.usefixtures('recognizer')
    def test_full_round_trip(self, assistant, controller, ai_replies, recorded_threads, delivered):
        """Heard text, the AI's answer and the spoken file all reach their destinations."""
        recognizer = voice_assistant.sr.Recognizer()
        tts_backend = assistant._tts
        ai_replies.replies.append(AI_ANSWER)
        assistant.start_listening()
        assistant.stop_listening_and_respond()

        recorded_threads[0].run_now()

        controller.get_speech_recognizer_audio.assert_called_once_with(b'\x01\x02\x03\x04')
        recognizer.recognize_google.assert_called_once_with('audio-data')
        assert delivered.transcriptions == [HEARD_TEXT]
        (request,) = ai_replies.requests
        assert request == {
            'model': 'test-provider:test-model',
            'messages': [
                {'role': 'system', 'content': 'Be brief.'},
                {'role': 'user', 'content': HEARD_TEXT},
            ],
        }
        controller.play_haptic.assert_called_with('click')
        tts_backend.speak_to_file.assert_called_once_with(AI_ANSWER)
        controller.play_file.assert_called_once_with(SPEECH_FILE, haptic_mode='speech')
        assert assistant.is_processing is False

        # The response waits for the main thread's update
        assert delivered.responses == []
        assistant.update()
        assert delivered.responses == [AI_ANSWER]
        assert delivered.errors == []
        assistant.update()
        assert delivered.responses == [AI_ANSWER]

    def test_conversation_history_is_sent_and_can_be_cleared(
        self, assistant, recognizer, ai_replies
    ):
        """A second question carries the first exchange; clear_conversation forgets it."""
        ai_replies.replies.extend([AI_ANSWER, 'Hold it to jump higher.', 'Hello again.'])
        assistant._run_pipeline(b'')
        assistant._run_pipeline(b'')

        second_messages = ai_replies.requests[1]['messages']
        assert second_messages[1:] == [
            {'role': 'user', 'content': HEARD_TEXT},
            {'role': 'assistant', 'content': AI_ANSWER},
            {'role': 'user', 'content': HEARD_TEXT},
        ]

        assistant.clear_conversation()
        assistant._run_pipeline(b'')
        assert ai_replies.requests[2]['messages'][1:] == [{'role': 'user', 'content': HEARD_TEXT}]

    def test_history_is_trimmed_to_the_last_ten_turns(self, assistant, ai_replies):
        """Whole user/assistant pairs are dropped: the history sent starts with a user message.

        BUGS.md #105: keeping the last 20 of 21 entries started it with an assistant message.
        """
        assistant._conversation = [
            {'role': 'user' if index % 2 == 0 else 'assistant', 'content': f'turn {index}'}
            for index in range(20)
        ]
        ai_replies.replies.append(AI_ANSWER)

        assert assistant._ask_ai('turn 20') == AI_ANSWER

        sent_history = ai_replies.requests[0]['messages'][1:]
        assert len(sent_history) == 19
        assert sent_history[0] == {'role': 'user', 'content': 'turn 2'}
        assert sent_history[-1] == {'role': 'user', 'content': 'turn 20'}
        assert len(assistant._conversation) == 20
        assert assistant._conversation[0] == {'role': 'user', 'content': 'turn 2'}
        assert assistant._conversation[-1] == {'role': 'assistant', 'content': AI_ANSWER}

    def test_history_alternates_from_a_user_message_after_many_questions(
        self, assistant, recognizer, ai_replies
    ):
        """Past ten questions every request still starts with the user and alternates."""
        question_count = 15
        ai_replies.replies.extend([f'answer {index}' for index in range(question_count)])

        for _ in range(question_count):
            assistant._run_pipeline(b'')

        for request in ai_replies.requests:
            roles = [message['role'] for message in request['messages'][1:]]
            assert roles == ['user', 'assistant'] * (len(roles) // 2) + ['user']
            assert len(roles) <= 19

    def test_failed_repeated_question_keeps_the_earlier_exchange(
        self, assistant, recognizer, ai_replies
    ):
        """A failed repeat of an earlier question removes only the repeat."""
        ai_replies.replies.extend([AI_ANSWER, RuntimeError('rate limited')])

        assistant._run_pipeline(b'')
        assistant._run_pipeline(b'')

        assert assistant._conversation == [
            {'role': 'user', 'content': HEARD_TEXT},
            {'role': 'assistant', 'content': AI_ANSWER},
        ]

    def test_failed_request_removes_its_question(self, assistant, recognizer, ai_replies):
        """A failed request leaves no unanswered question, so roles keep alternating."""
        ai_replies.replies.extend([RuntimeError('rate limited'), AI_ANSWER])

        assistant._run_pipeline(b'')
        assistant._run_pipeline(b'')

        assert ai_replies.requests[1]['messages'][1:] == [{'role': 'user', 'content': HEARD_TEXT}]
        assert assistant._conversation == [
            {'role': 'user', 'content': HEARD_TEXT},
            {'role': 'assistant', 'content': AI_ANSWER},
        ]

    @pytest.mark.parametrize('reply', [AI_ANSWER, RuntimeError('rate limited')])
    def test_clearing_mid_request_leaves_no_answer_without_its_question(
        self, assistant, recognizer, ai_replies, reply
    ):
        """BUGS.md #114: a clear during a request never leaves a history starting with an answer.

        The answer (or failure) arrives after clear_conversation() emptied the history, so the
        next request must carry only its own question.
        """

        def clear_then_reply():
            assistant.clear_conversation()
            if isinstance(reply, Exception):
                raise reply
            return reply

        ai_replies.replies.extend([AI_ANSWER, clear_then_reply, 'Hello again.'])

        assistant._run_pipeline(b'')
        assistant._run_pipeline(b'')

        assert assistant._conversation == []
        assistant._run_pipeline(b'')
        assert ai_replies.requests[2]['messages'][1:] == [{'role': 'user', 'content': HEARD_TEXT}]

    def test_unheard_speech_reports_an_error(
        self, assistant, controller, recognizer, delivered, caplog
    ):
        """Speech the recognizer cannot understand gives 'Could not understand speech'."""
        recognizer.recognize_google.side_effect = FakeUnknownValueError()

        with caplog.at_level(logging.WARNING, logger='game.audio.voice_assistant'):
            assistant._process_pipeline(b'')
        assistant.update()

        assert delivered.errors == ['Could not understand speech']
        assert delivered.transcriptions == []
        assert 'Speech not understood' in caplog.text

    def test_recognition_service_error_reports_an_error(
        self, assistant, recognizer, delivered, caplog
    ):
        """A recognition service failure is logged and reported as not understood."""
        recognizer.recognize_google.side_effect = FakeRequestError('offline')

        with caplog.at_level(logging.ERROR, logger='game.audio.voice_assistant'):
            assistant._process_pipeline(b'')
        assistant.update()

        assert delivered.errors == ['Could not understand speech']
        assert 'Speech recognition service error' in caplog.text

    def test_no_recognizer_audio_reports_an_error(
        self, assistant, controller, recognizer, delivered
    ):
        """When the controller cannot wrap the audio nothing is recognized."""
        controller.get_speech_recognizer_audio.return_value = None

        assistant._process_pipeline(b'')
        assistant.update()

        recognizer.recognize_google.assert_not_called()
        assert delivered.errors == ['Could not understand speech']

    def test_without_speech_recognition(self, assistant, mocker, delivered, caplog):
        """No speech_recognition module: a warning and an error delivery."""
        mocker.patch.object(voice_assistant, 'sr', None)

        with caplog.at_level(logging.WARNING, logger='game.audio.voice_assistant'):
            assistant._process_pipeline(b'')
        assistant.update()

        assert delivered.errors == ['Could not understand speech']
        assert 'speech_recognition not available' in caplog.text

    def test_ai_failure_reports_no_response(
        self, assistant, recognizer, ai_replies, delivered, caplog
    ):
        """An AI request that raises is logged and reported as no response."""
        ai_replies.replies.append(RuntimeError('rate limited'))

        with caplog.at_level(logging.ERROR, logger='game.audio.voice_assistant'):
            assistant._process_pipeline(b'')
        assistant.update()

        assert delivered.transcriptions == [HEARD_TEXT]
        assert delivered.errors == ['No response from AI']
        assert delivered.responses == []
        assert 'AI request failed' in caplog.text
        # The unanswered question is dropped from the history (BUGS.md #105)
        assert assistant._conversation == []

    def test_without_aisuite(self, assistant, recognizer, mocker, delivered, caplog):
        """No aisuite module: a warning and 'No response from AI'."""
        mocker.patch.object(voice_assistant, 'ai', None)

        with caplog.at_level(logging.WARNING, logger='game.audio.voice_assistant'):
            assistant._process_pipeline(b'')
        assistant.update()

        assert delivered.errors == ['No response from AI']
        assert 'aisuite not available' in caplog.text

    @pytest.mark.usefixtures('recognizer')
    def test_unexpected_failure_is_reported_at_the_thread_boundary(
        self, assistant, ai_replies, controller, delivered, caplog
    ):
        """An exception escaping the pipeline is logged, reported, and ends processing."""
        ai_replies.replies.append(AI_ANSWER)
        controller.play_file.side_effect = RuntimeError('speaker unplugged')
        assistant._processing = True

        with caplog.at_level(logging.ERROR, logger='game.audio.voice_assistant'):
            assistant._process_pipeline(b'')
        assistant.update()

        assert delivered.responses == [AI_ANSWER]
        assert delivered.errors == ['Voice assistant error — check logs']
        assert assistant.is_processing is False
        assert 'Voice assistant pipeline error' in caplog.text

    def test_without_callbacks_update_just_clears(self, controller, tts_backend):
        """With no callbacks set, pending results are dropped silently."""
        silent_assistant = VoiceAssistant(controller)
        silent_assistant._pending_response = AI_ANSWER
        silent_assistant._pending_error = 'oops'

        silent_assistant.update()

        assert silent_assistant._pending_response is None
        assert silent_assistant._pending_error is None

    def test_transcription_without_callback_still_answers(
        self, controller, tts_backend, recognizer, ai_replies
    ):
        """No transcription callback: the pipeline continues to the AI."""
        ai_replies.replies.append(AI_ANSWER)
        silent_assistant = VoiceAssistant(controller)

        silent_assistant._run_pipeline(b'')

        assert silent_assistant._pending_response == AI_ANSWER


class TestSpeaking:
    """_speak_response speaks through the controller only when it can."""

    def test_without_tts_backend_is_text_only(self, controller, mocker, caplog):
        """No TTS backend: nothing is played."""
        mocker.patch.object(voice_assistant, 'get_tts_backend', return_value=None)
        text_only_assistant = VoiceAssistant(controller)

        with caplog.at_level(logging.INFO, logger='game.audio.voice_assistant'):
            text_only_assistant._speak_response(AI_ANSWER)

        controller.play_haptic.assert_not_called()
        controller.play_file.assert_not_called()
        assert 'No TTS backend' in caplog.text

    def test_without_speaker_is_text_only(self, assistant, controller, tts_backend, caplog):
        """No speaker: no speech is generated."""
        controller.has_speaker = False

        with caplog.at_level(logging.INFO, logger='game.audio.voice_assistant'):
            assistant._speak_response(AI_ANSWER)

        tts_backend.speak_to_file.assert_not_called()
        assert 'No speaker on controller' in caplog.text

    def test_failed_speech_generation_plays_only_the_click(
        self, assistant, controller, tts_backend
    ):
        """When TTS returns no file the click still plays but no file does."""
        tts_backend.speak_to_file.return_value = None

        assistant._speak_response(AI_ANSWER)

        controller.play_haptic.assert_called_once_with('click')
        controller.play_file.assert_not_called()


class TestFactories:
    """for_controller and discover build an assistant only when the controller has audio."""

    def test_for_controller_without_audio(self, mocker):
        """No controller audio: None."""
        mocker.patch.object(voice_assistant.ControllerAudio, 'for_controller', return_value=None)

        assert VoiceAssistant.for_controller('Pad') is None

    def test_for_controller_builds_an_assistant(self, mocker, controller, tts_backend):
        """The controller's audio and the kwargs reach the assistant."""
        for_controller = mocker.patch.object(
            voice_assistant.ControllerAudio, 'for_controller', return_value=controller
        )

        built = VoiceAssistant.for_controller('Pad', ai_model='other-model')

        assert built is not None
        assert built._audio is controller
        assert built._ai_model == 'other-model'
        for_controller.assert_called_once_with('Pad')

    def test_for_controller_logs_a_constructor_failure(self, mocker, controller, caplog):
        """A failing constructor is logged and gives None."""
        mocker.patch.object(
            voice_assistant.ControllerAudio, 'for_controller', return_value=controller
        )
        mocker.patch.object(
            voice_assistant, 'get_tts_backend', side_effect=RuntimeError('tts broke')
        )

        with caplog.at_level(logging.ERROR, logger='game.audio.voice_assistant'):
            assert VoiceAssistant.for_controller('Pad') is None
        assert "Failed to create voice assistant for 'Pad'" in caplog.text

    def test_discover_without_audio(self, mocker, caplog):
        """No controller with audio: None and an info log."""
        discover = mocker.patch.object(
            voice_assistant.ControllerAudio, 'discover', return_value=None
        )

        with caplog.at_level(logging.INFO, logger='game.audio.voice_assistant'):
            assert VoiceAssistant.discover() is None
        discover.assert_called_once_with(volume=5.0)
        assert 'No controller with audio devices found' in caplog.text

    def test_discover_builds_an_assistant(self, mocker, controller, tts_backend):
        """A discovered controller gets an assistant with the kwargs."""
        mocker.patch.object(voice_assistant.ControllerAudio, 'discover', return_value=controller)

        built = VoiceAssistant.discover(system_prompt='Short answers.')

        assert built is not None
        assert built._audio is controller
        assert built._system_prompt == 'Short answers.'

    def test_discover_logs_a_constructor_failure(self, mocker, controller, caplog):
        """A failing constructor is logged and gives None."""
        mocker.patch.object(voice_assistant.ControllerAudio, 'discover', return_value=controller)
        mocker.patch.object(
            voice_assistant, 'get_tts_backend', side_effect=RuntimeError('tts broke')
        )

        with caplog.at_level(logging.ERROR, logger='game.audio.voice_assistant'):
            assert VoiceAssistant.discover() is None
        assert 'Failed to create voice assistant' in caplog.text


class TestThePackagesLazyImport:
    """``glitchygames.audio`` imports the voice assistant (and aisuite) only when asked for it."""

    def test_the_engine_imports_no_aisuite_until_the_voice_assistant_is_asked_for(self):
        """In a fresh interpreter: the engine and the live voices first, then the assistant."""
        completed = run_command(
            command=[sys.executable, '-c', LAZY_IMPORT_PROBE],
            environment=dict(os.environ),
            timeout_seconds=120,
            capture_output=OutputCapture.TOGETHER,
        )

        assert completed.returncode == 0, completed.stdout
        assert json.loads(completed.stdout.strip().splitlines()[-1]) == [False, True, True]

    def test_the_package_gives_the_voice_assistant_class(self):
        """The name the package exports is the class its module defines."""
        assert glitchygames.audio.VoiceAssistant is VoiceAssistant
        assert 'VoiceAssistant' in glitchygames.audio.__all__

    def test_any_other_missing_name_is_an_attribute_error(self):
        """As for any module: the error names the module and the attribute."""
        with pytest.raises(
            AttributeError,
            match=re.escape("module 'glitchygames.audio' has no attribute 'NoSuchName'"),
        ):
            _ = glitchygames.audio.NoSuchName
