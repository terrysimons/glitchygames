"""Voice recognition event handling for glitchygames.

This module provides voice recognition capabilities for the glitchygames engine,
allowing users to control the application through voice commands.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from collections.abc import Callable

from glitchygames.events import ResourceManager
from glitchygames.events.voice_backends import get_microphone_backend

# Centralized logger for voice recognition
LOG: logging.Logger = logging.getLogger('glitchygames.events.voice')
LOG.addHandler(logging.NullHandler())

# Try to import speech recognition, but don't fail if it's not available
try:
    import speech_recognition as sr

    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    sr = None  # ty: ignore[invalid-assignment]
    SPEECH_RECOGNITION_AVAILABLE = False  # pyright: ignore[reportConstantRedefinition]


class VoiceEventManager(ResourceManager):
    """Manages voice recognition and command processing."""

    class VoiceEventProxy(ResourceManager):
        """Proxy for voice manager operations (consistency with other managers)."""

        log: ClassVar[logging.Logger] = LOG

        def __init__(self, game: VoiceEventManager) -> None:
            """Initialize the voice event proxy with a voice event manager."""
            super().__init__(game)
            self.game = game
            self.proxies = [self.game]

        def start_listening(self) -> None:
            """Delegate start_listening to the voice event manager."""
            self.game.start_listening()

        def stop_listening(self) -> None:
            """Delegate stop_listening to the voice event manager."""
            self.game.stop_listening()

        def register_command(self, phrase: str, callback: Callable[[], None]) -> None:
            """Delegate register_command to the voice event manager."""
            self.game.register_command(phrase, callback)

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize the voice recognition manager.

        Args:
            logger: Optional logger instance. If None, creates a default logger.

        """
        super().__init__(game=self)
        self.log = logger or logging.getLogger(__name__)  # type: ignore[misc] # ty: ignore[invalid-attribute-access]  # instance override of ClassVar is intentional
        self.is_listening = False
        self.listen_thread = None
        self.commands: dict[str, Callable[[], None]] = {}
        self.stop_listening_event = threading.Event()
        # Provide a proxy for API symmetry with other event managers
        self.proxies = [VoiceEventManager.VoiceEventProxy(game=self)]

        # Initialize speech recognition components if available
        if SPEECH_RECOGNITION_AVAILABLE:
            self.recognizer: Any = sr.Recognizer()  # type: ignore[union-attr]
            self.microphone: Any = None
            # Select a backend microphone class
            mic_cls = get_microphone_backend()
            if mic_cls is not None:
                self.microphone = self._probe_microphone_backend(mic_cls)
            if self.microphone is None:
                # Last resort: try built-in sr.Microphone init
                self._setup_microphone()
        else:
            self.recognizer = None
            self.microphone = None
            self.log.warning('Speech recognition not available - voice commands disabled')

        # Register default commands
        self._register_default_commands()

    def _probe_microphone_backend(self, mic_cls: type) -> object | None:
        """Probe a microphone backend by opening/closing once and return an instance.

        Args:
            mic_cls: The microphone backend class to probe.

        Returns:
            A microphone instance if probing succeeded, or None on failure.

        """
        backend_name = getattr(mic_cls, '__name__', str(mic_cls))
        try:
            probe = mic_cls()
            enter = getattr(probe, '__enter__', None)
            exit_cm = getattr(probe, '__exit__', None)
            if callable(enter):
                try:
                    enter()
                finally:
                    try:
                        if callable(exit_cm):
                            exit_cm(None, None, None)
                    except OSError, RuntimeError:
                        LOG.debug('Voice backend cleanup raised error during probe', exc_info=True)
            self.log.info('Voice backend selected: %s', backend_name)
            return mic_cls()
        except OSError, RuntimeError:
            self.log.exception('Voice backend probe failed for %s', backend_name)
            return None
        except Exception:
            # Catch-all to prevent unexpected backend errors from crashing initialization
            self.log.exception('Unexpected error while probing voice backend %s', backend_name)
            return None

    def _setup_microphone(self) -> None:
        """Set up the microphone for voice recognition."""
        if not SPEECH_RECOGNITION_AVAILABLE:
            self.microphone = None
            return

        try:
            self.microphone = sr.Microphone()  # type: ignore[union-attr]
            self.log.info('Microphone initialized successfully')
        except OSError, AttributeError:
            self.log.error('Failed to initialize microphone')  # noqa: TRY400
            self.microphone = None

    def _register_default_commands(self) -> None:
        """Register default voice commands."""
        # This will be populated by the scene that uses this manager

    def register_command(self, phrase: str, callback: Callable[[], None]) -> None:
        """Register a voice command.

        Args:
            phrase: The phrase to listen for (case-insensitive)
            callback: Function to call when the phrase is detected

        """
        self.commands[phrase.lower()] = callback
        self.log.info("Registered voice command: '%s'", phrase)

    def start_listening(self) -> None:
        """Start listening for voice commands in a separate thread."""
        if not SPEECH_RECOGNITION_AVAILABLE:
            self.log.warning('Cannot start listening: speech recognition not available')
            return

        if self.is_listening:
            self.log.warning('Voice recognition is already listening')
            return

        if not self.microphone:
            self.log.error('Cannot start listening: microphone not available')
            return

        self.is_listening = True
        self.stop_listening_event.clear()
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        self.log.info('Voice recognition started')

    def stop_listening(self) -> None:
        """Stop listening for voice commands."""
        if not self.is_listening:
            return

        self.is_listening = False
        self.stop_listening_event.set()

        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=2.0)  # Increased timeout
            # Force cleanup if thread is still alive
            if self.listen_thread.is_alive():
                self.log.warning('Voice recognition thread did not stop cleanly')

        self.log.info('Voice recognition stopped')

    def _listen_loop(self) -> None:
        """Run the main listening loop in a separate thread."""
        if not SPEECH_RECOGNITION_AVAILABLE:
            self.log.error('Cannot start listen loop: speech recognition not available')
            return

        if self.microphone is None:
            self.log.error('Cannot start listen loop: microphone not available')
            return

        # Open microphone once and keep it open for the duration
        with self.microphone as source:
            # Adjust for ambient noise once at the start
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            self.log.info('Microphone calibrated for ambient noise')

            while self.is_listening and not self.stop_listening_event.is_set():
                try:
                    # Listen for audio with timeout
                    self.log.debug('Listening for voice input...')
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=10)

                    # Recognize speech
                    try:
                        text = self.recognizer.recognize_google(audio).lower()
                        self.log.info("Recognized speech: '%s'", text)
                        self._process_command(text)
                    except sr.UnknownValueError:  # type: ignore[union-attr]
                        # Speech was unintelligible, continue listening
                        self.log.debug('Could not understand audio')
                    except sr.RequestError:  # type: ignore[union-attr]
                        self.log.error('Speech recognition service error')  # noqa: TRY400
                        # Wait a bit before trying again
                        time.sleep(2)

                except sr.WaitTimeoutError:  # type: ignore[union-attr]
                    # Timeout is normal, continue listening
                    continue
                except OSError:
                    self.log.error('Error in voice recognition loop')  # noqa: TRY400
                    time.sleep(1)

    def _process_command(self, text: str) -> None:
        """Process a recognized voice command.

        Args:
            text: The recognized text (already lowercased)

        """
        # Check for exact matches first
        if text in self.commands:
            self.log.info("Executing voice command: '%s'", text)
            try:
                self.commands[text]()
            except Exception:  # Arbitrary user callbacks can raise anything
                self.log.exception("Error executing voice command '%s'", text)
            return

        # Check for partial matches (commands that contain the text)
        for command_phrase, callback in self.commands.items():
            if command_phrase in text:
                self.log.info(
                    "Executing partial match voice command: '%s' from '%s'",
                    command_phrase,
                    text,
                )
                try:
                    callback()
                except Exception:  # Arbitrary user callbacks can raise anything
                    self.log.exception("Error executing voice command '%s'", command_phrase)
                return

        self.log.debug("No voice command found for: '%s'", text)

    def is_available(self) -> bool:
        """Check if voice recognition is available.

        Returns:
            True if speech_recognition and a microphone are available

        """
        return SPEECH_RECOGNITION_AVAILABLE and self.microphone is not None

    def has_microphone(self) -> bool:
        """Check if a microphone device is available/initialized.

        Returns:
            bool: True if has microphone, False otherwise.

        """
        return self.microphone is not None

    def get_available_commands(self) -> list[str]:
        """Get list of available voice commands.

        Returns:
            List of registered command phrases

        """
        return list(self.commands.keys())
