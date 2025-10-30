"""Voice recognition event handling for glitchygames.

This module provides voice recognition capabilities for the glitchygames engine,
allowing users to control the application through voice commands.
"""

import logging
import threading
import time
from collections.abc import Callable

from glitchygames.events import ResourceManager
try:
    from .voice_backends import get_microphone_backend
except Exception:
    get_microphone_backend = lambda: None  # type: ignore

# Centralized logger for voice recognition
LOG: logging.Logger = logging.getLogger("glitchygames.events.voice")
LOG.addHandler(logging.NullHandler())

# Try to import speech recognition, but don't fail if it's not available
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    sr = None
    SPEECH_RECOGNITION_AVAILABLE = False


class VoiceEventManager(ResourceManager):
    """Manages voice recognition and command processing."""

    class VoiceEventProxy(ResourceManager):
        """Proxy for voice manager operations (consistency with other managers)."""

        log: logging.Logger = LOG

        def __init__(self, game: "VoiceEventManager") -> None:
            super().__init__(game)
            self.game = game
            self.proxies = [self.game]

        def start_listening(self) -> None:
            self.game.start_listening()

        def stop_listening(self) -> None:
            self.game.stop_listening()

        def register_command(self, phrase: str, callback: Callable[[], None]) -> None:
            self.game.register_command(phrase, callback)

    def __init__(self, logger: logging.Logger | None = None):
        """Initialize the voice recognition manager.

        Args:
            logger: Optional logger instance. If None, creates a default logger.

        """
        super().__init__(game=self)
        self.log = logger or logging.getLogger(__name__)
        self.is_listening = False
        self.listen_thread = None
        self.commands: dict[str, Callable[[], None]] = {}
        self.stop_listening_event = threading.Event()
        # Provide a proxy for API symmetry with other event managers
        self.proxies = [VoiceEventManager.VoiceEventProxy(game=self)]

        # Initialize speech recognition components if available
        if SPEECH_RECOGNITION_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.microphone = None
            # Select a backend microphone class
            mic_cls = get_microphone_backend()
            if mic_cls is not None:
                backend_name = getattr(mic_cls, "__name__", str(mic_cls))
                # Probe the backend by opening/closing once to surface errors early
                try:
                    _probe = mic_cls()  # type: ignore[call-arg]
                    try:
                        _enter = _probe.__enter__
                    except AttributeError:
                        _enter = None
                    if callable(_enter):  # type: ignore[truthy-bool]
                        try:
                            _probe.__enter__()
                        finally:
                            try:
                                _probe.__exit__(None, None, None)
                            except Exception:
                                pass
                    self.log.info(f"Voice backend selected: {backend_name}")
                    self.microphone = mic_cls()  # type: ignore[call-arg]
                except Exception as e:
                    self.log.error(f"Voice backend probe failed for {backend_name}: {e}")
                    self.microphone = None
            if self.microphone is None:
                # Last resort: try built-in sr.Microphone init
                self._setup_microphone()
        else:
            self.recognizer = None
            self.microphone = None
            self.log.warning("Speech recognition not available - voice commands disabled")

        # Register default commands
        self._register_default_commands()

    def _setup_microphone(self) -> None:
        """Set up the microphone for voice recognition."""
        if not SPEECH_RECOGNITION_AVAILABLE:
            self.microphone = None
            return

        try:
            self.microphone = sr.Microphone()
            self.log.info("Microphone initialized successfully")
        except Exception:
            self.log.error("Failed to initialize microphone")
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
        self.log.info(f"Registered voice command: '{phrase}'")

    def start_listening(self) -> None:
        """Start listening for voice commands in a separate thread."""
        if not SPEECH_RECOGNITION_AVAILABLE:
            self.log.warning("Cannot start listening: speech recognition not available")
            return

        if self.is_listening:
            self.log.warning("Voice recognition is already listening")
            return

        if not self.microphone:
            self.log.error("Cannot start listening: microphone not available")
            return

        self.is_listening = True
        self.stop_listening_event.clear()
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        self.log.info("Voice recognition started")

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
                self.log.warning("Voice recognition thread did not stop cleanly")

        self.log.info("Voice recognition stopped")

    def _listen_loop(self) -> None:
        """Run the main listening loop in a separate thread."""
        if not SPEECH_RECOGNITION_AVAILABLE:
            self.log.error("Cannot start listen loop: speech recognition not available")
            return

        # Open microphone once and keep it open for the duration
        with self.microphone as source:
            # Adjust for ambient noise once at the start
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            self.log.info("Microphone calibrated for ambient noise")

            while self.is_listening and not self.stop_listening_event.is_set():
                try:
                    # Listen for audio with timeout
                    self.log.debug("Listening for voice input...")
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=10)

                    # Recognize speech
                    try:
                        text = self.recognizer.recognize_google(audio).lower()
                        self.log.info(f"Recognized speech: '{text}'")
                        self._process_command(text)
                    except sr.UnknownValueError:
                        # Speech was unintelligible, continue listening
                        self.log.debug("Could not understand audio")
                    except sr.RequestError:
                        self.log.error("Speech recognition service error")
                        # Wait a bit before trying again
                        time.sleep(2)

                except sr.WaitTimeoutError:
                    # Timeout is normal, continue listening
                    continue
                except Exception:
                    self.log.error("Error in voice recognition loop")
                    time.sleep(1)

    def _process_command(self, text: str) -> None:
        """Process a recognized voice command.

        Args:
            text: The recognized text (already lowercased)

        """
        # Check for exact matches first
        if text in self.commands:
            self.log.info(f"Executing voice command: '{text}'")
            try:
                self.commands[text]()
            except Exception:
                self.log.error(f"Error executing voice command '{text}'")
            return

        # Check for partial matches (commands that contain the text)
        for command_phrase, callback in self.commands.items():
            if command_phrase in text:
                self.log.info(
                    f"Executing partial match voice command: '{command_phrase}' from '{text}'"
                )
                try:
                    callback()
                except Exception:
                    self.log.error(f"Error executing voice command '{command_phrase}'")
                return

        self.log.debug(f"No voice command found for: '{text}'")

    def is_available(self) -> bool:
        """Check if voice recognition is available.

        Returns:
            True if speech_recognition and a microphone are available

        """
        return SPEECH_RECOGNITION_AVAILABLE and self.microphone is not None

    def has_microphone(self) -> bool:
        """Check if a microphone device is available/initialized."""
        return self.microphone is not None

    def get_available_commands(self) -> list[str]:
        """Get list of available voice commands.

        Returns:
            List of registered command phrases

        """
        return list(self.commands.keys())
