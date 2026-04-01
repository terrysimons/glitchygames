"""Push-to-talk AI voice assistant using controller mic and speaker.

Provides a complete voice assistant pipeline:
mic button press → record → speech-to-text → AI → text-to-speech → controller speaker

Usage:
    assistant = VoiceAssistant.for_controller('DualSense Wireless Controller')

    # In event handler (mic button pressed):
    assistant.start_listening()

    # In event handler (mic button released):
    assistant.stop_listening_and_respond()

    # In dt_tick:
    assistant.update()  # Checks for completed responses
"""

from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING, Any

from glitchygames.audio.controller_audio import ControllerAudio
from glitchygames.audio.tts import get_tts_backend

log: logging.Logger = logging.getLogger('game.audio.voice_assistant')

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover
    sr = None  # ty: ignore[invalid-assignment]

try:
    import aisuite as ai
except ImportError, AttributeError:  # pragma: no cover
    ai = None  # ty: ignore[invalid-assignment]
    log.warning(
        '*** aisuite not available — voice assistant AI features disabled. '
        'Install aisuite or check Python 3.14 compatibility (ast.NameConstant removed). ***',
    )

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.audio.tts import TTSBackend


# Default AI configuration
_DEFAULT_PROVIDER = 'anthropic'
_DEFAULT_MODEL = 'claude-sonnet-4-5'

_SYSTEM_PROMPT = (
    'You are a helpful game assistant. The player is speaking to you through '
    'their controller microphone during gameplay. Keep responses concise '
    '(1-2 sentences) and helpful. If they ask about game controls, guide them. '
    'If they ask for general help, be friendly and brief.'
)


class VoiceAssistant:
    """Push-to-talk AI voice assistant for game controllers.

    Manages the full pipeline from controller mic recording through
    AI processing to speaker playback. All heavy processing (speech
    recognition, AI API calls, TTS) runs in a background thread to
    avoid blocking the game loop.

    Args:
        controller_audio: The controller's audio devices.
        ai_provider: AI provider name for aisuite (default: from env or 'anthropic').
        ai_model: AI model identifier (default: from env or 'claude-sonnet-4-5').
        system_prompt: System prompt for the AI assistant.
        on_transcription: Callback when speech is transcribed. Receives the text.
        on_response: Callback when AI responds. Receives the response text.
        on_error: Callback on any error. Receives the error message.

    """

    def __init__(  # noqa: PLR0913
        self,
        controller_audio: ControllerAudio,
        *,
        ai_provider: str | None = None,
        ai_model: str | None = None,
        system_prompt: str = _SYSTEM_PROMPT,
        on_transcription: Callable[[str], None] | None = None,
        on_response: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the voice assistant."""
        self._audio = controller_audio
        self._tts: TTSBackend | None = get_tts_backend()
        self._system_prompt = system_prompt

        # AI configuration (env vars override defaults)
        self._ai_provider = ai_provider or os.environ.get('SPRITE_AI_PROVIDER', _DEFAULT_PROVIDER)
        self._ai_model = ai_model or os.environ.get('SPRITE_AI_MODEL', _DEFAULT_MODEL)

        # Callbacks for game integration
        self._on_transcription = on_transcription
        self._on_response = on_response
        self._on_error = on_error

        # Conversation history for context
        self._conversation: list[dict[str, str]] = []
        self._max_conversation_turns = 10

        # State
        self._listening = False
        self._processing = False
        self._pending_response: str | None = None
        self._pending_error: str | None = None
        self._lock = threading.Lock()

    @property
    def is_listening(self) -> bool:
        """Whether the assistant is currently recording."""
        return self._listening

    @property
    def is_processing(self) -> bool:
        """Whether the assistant is processing a request (STT + AI + TTS)."""
        return self._processing

    def start_listening(self) -> bool:
        """Start recording from the controller mic.

        Returns:
            True if recording started successfully.

        """
        if self._listening or self._processing:
            return False

        if not self._audio.has_microphone:
            self._fire_error('No microphone found on controller')
            return False

        # Haptic feedback: short buzz to confirm mic is active
        self._audio.play_haptic('buzz', duration=0.08)

        self._listening = self._audio.start_capture()
        if self._listening:
            log.info('Voice assistant: listening...')
        return self._listening

    def stop_listening_and_respond(self) -> None:
        """Stop recording and process the audio in the background.

        The pipeline runs in a background thread:
        audio → speech-to-text → AI → TTS → play through speaker.

        Results are delivered via callbacks and the update() method.
        """
        if not self._listening:
            return

        audio_data = self._audio.stop_capture()
        self._listening = False
        self._processing = True

        log.info('Voice assistant: processing %d bytes of audio...', len(audio_data))

        # Run the heavy pipeline in a background thread
        thread = threading.Thread(
            target=self._process_pipeline,
            args=(audio_data,),
            daemon=True,
        )
        thread.start()

    def update(self) -> None:
        """Check for completed responses (call from dt_tick).

        Delivers pending responses and errors via callbacks on
        the main thread.
        """
        with self._lock:
            response = self._pending_response
            error = self._pending_error
            self._pending_response = None
            self._pending_error = None

        if response is not None and self._on_response is not None:
            self._on_response(response)

        if error is not None and self._on_error is not None:
            self._on_error(error)

    def clear_conversation(self) -> None:
        """Reset the conversation history."""
        self._conversation.clear()

    # --- Background pipeline ---

    def _process_pipeline(self, audio_data: bytes) -> None:
        """Run the full STT → AI → TTS → playback pipeline.

        Runs in a background thread. Sets _pending_response or
        _pending_error for the main thread to pick up.

        Args:
            audio_data: Raw PCM audio from the controller mic.

        """
        try:
            # 1. Speech-to-text
            text = self._transcribe(audio_data)
            if not text:
                self._fire_error('Could not understand speech')
                return

            log.info('Voice assistant heard: %r', text)
            if self._on_transcription is not None:
                self._on_transcription(text)

            # 2. AI response
            response = self._ask_ai(text)
            if not response:
                self._fire_error('No response from AI')
                return

            log.info('Voice assistant says: %r', response)

            # 3. Deliver response text
            with self._lock:
                self._pending_response = response

            # 4. TTS → speaker
            self._speak_response(response)

        except Exception:
            log.exception('Voice assistant pipeline error')
            self._fire_error('Voice assistant error — check logs')
        finally:
            self._processing = False

    def _transcribe(self, audio_data: bytes) -> str | None:
        """Convert raw audio to text via speech_recognition.

        Args:
            audio_data: Raw PCM audio bytes.

        Returns:
            The transcribed text, or None.

        """
        if sr is None:
            log.warning('speech_recognition not available')
            return None

        audio = self._audio.get_speech_recognizer_audio(audio_data)
        if audio is None:
            return None

        recognizer = sr.Recognizer()
        try:
            # Use Google's free speech recognition
            # Could swap to Whisper, etc.
            return recognizer.recognize_google(audio)  # type: ignore[no-any-return] # ty: ignore[unresolved-attribute]
        except sr.UnknownValueError:
            log.warning('Speech not understood')
            return None
        except sr.RequestError:
            log.exception('Speech recognition service error')
            return None

    def _ask_ai(self, user_text: str) -> str | None:
        """Send text to the AI and get a response.

        Args:
            user_text: The player's transcribed speech.

        Returns:
            The AI's response text, or None.

        """
        if ai is None:
            log.warning('aisuite not available')
            return None

        # Build messages with conversation context
        self._conversation.append({'role': 'user', 'content': user_text})

        # Trim conversation to max turns
        if len(self._conversation) > self._max_conversation_turns * 2:
            self._conversation = self._conversation[-self._max_conversation_turns * 2 :]

        messages: list[dict[str, str]] = [
            {'role': 'system', 'content': self._system_prompt},
            *self._conversation,
        ]

        try:
            client: Any = ai.Client()
            model_string = f'{self._ai_provider}:{self._ai_model}'
            response = client.chat.completions.create(
                model=model_string,
                messages=messages,
            )
            response_text: str = response.choices[0].message.content
        except Exception:
            log.exception('AI request failed')
            return None
        else:
            self._conversation.append({'role': 'assistant', 'content': response_text})
            return response_text

    def _speak_response(self, text: str) -> None:
        """Convert response to speech and play through controller speaker.

        Args:
            text: The response text to speak.

        """
        if self._tts is None:
            log.info('No TTS backend — response is text-only')
            return

        if not self._audio.has_speaker:
            log.info('No speaker on controller — response is text-only')
            return

        # Play a click haptic when the response starts, then speak
        self._audio.play_haptic('click')

        audio_file = self._tts.speak_to_file(text)
        if audio_file is not None:
            self._audio.play_file(audio_file, haptic_mode='speech')

    def _fire_error(self, message: str) -> None:
        """Set a pending error for the main thread.

        Args:
            message: Error description.

        """
        log.warning('Voice assistant: %s', message)
        with self._lock:
            self._pending_error = message
        self._processing = False

    # --- Factory ---

    @classmethod
    def for_controller(
        cls,
        controller_name: str,
        **kwargs: Any,
    ) -> VoiceAssistant | None:
        """Create a VoiceAssistant for a named controller.

        Returns None if the controller has no audio devices or
        required libraries are missing.

        Args:
            controller_name: The controller's name string.
            **kwargs: Additional arguments passed to the constructor.

        Returns:
            A VoiceAssistant instance, or None.

        """
        audio = ControllerAudio.for_controller(controller_name)
        if audio is None:
            return None

        try:
            return cls(controller_audio=audio, **kwargs)
        except Exception:
            log.exception('Failed to create voice assistant for %r', controller_name)
            return None

    @classmethod
    def discover(cls, **kwargs: Any) -> VoiceAssistant | None:
        """Auto-discover a controller with audio and create a VoiceAssistant.

        Scans miniaudio devices for a controller with both microphone
        and speaker. No engine access needed.

        Args:
            **kwargs: Additional arguments passed to the constructor.

        Returns:
            A VoiceAssistant for the first matching controller, or None.

        """
        # Volume 5.0 compensates for quiet macOS TTS output (~10% of max)
        audio = ControllerAudio.discover(volume=5.0)
        if audio is None:
            log.info('No controller with audio devices found')
            return None

        try:
            return cls(controller_audio=audio, **kwargs)
        except Exception:
            log.exception('Failed to create voice assistant')
            return None
