"""Controller audio device discovery, speaker output, and audio-driven haptics.

Discovers and wraps the DualSense 4-channel USB audio device for:
- Channel 0: Headphone left (unused for now)
- Channel 1: Mono speaker (TTS, sound effects)
- Channel 2: Left haptic motor (audio-driven vibration)
- Channel 3: Right haptic motor (audio-driven vibration)

Usage:
    audio = ControllerAudio.for_controller('DualSense Wireless Controller')
    if audio:
        audio.start_capture()
        data = audio.stop_capture()
        audio.play_file('/path/to/response.wav')
        audio.play_haptic('click')
"""

from __future__ import annotations

import array
import logging
import math
import threading
import time
from pathlib import Path
from typing import Any

log: logging.Logger = logging.getLogger('game.audio.controller')

try:
    import miniaudio as mi
except ImportError:  # pragma: no cover
    mi = None  # ty: ignore[invalid-assignment]

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover
    sr = None  # ty: ignore[invalid-assignment]

try:
    import hid as hidapi  # ty: ignore[unresolved-import]
except ImportError:  # pragma: no cover
    hidapi = None

# DualSense USB audio device constants
DUALSENSE_SAMPLE_RATE = 48000
DUALSENSE_CHANNELS = 4
CHANNEL_HEADPHONE_LEFT = 0
CHANNEL_SPEAKER = 1
CHANNEL_HAPTIC_LEFT = 2
CHANNEL_HAPTIC_RIGHT = 3

# DualSense HID constants
# Source: Linux kernel hid-playstation.c, dualsensectl
SONY_VENDOR_ID = 0x054C
DUALSENSE_PRODUCT_ID = 0x0CE6
DUALSENSE_EDGE_PRODUCT_ID = 0x0DF2
DS_OUTPUT_REPORT_USB = 0x02
DS_OUTPUT_REPORT_SIZE = 63

# valid_flag0 bits (USB byte 1)
_FLAG0_SPEAKER_VOLUME = 0x20  # bit 5
_FLAG0_AUDIO_CONTROL = 0x80  # bit 7

# valid_flag1 bits (USB byte 2)
_FLAG1_AUDIO_CONTROL2 = 0x80  # bit 7

# Audio output path (bits 4-5 of audio_flags, USB byte 8)
_AUDIO_PATH_SPEAKER_ONLY = 3  # HP muted, right channel → speaker
_AUDIO_PATH_SHIFT = 4

# Speaker defaults (from Linux kernel)
_SPEAKER_VOLUME_DEFAULT = 0x64  # Max effective volume
_SPEAKER_PREAMP_GAIN_6DB = 0x02  # +6dB preamp


def enable_dualsense_speaker(
    volume: int = _SPEAKER_VOLUME_DEFAULT,
    preamp_gain: int = _SPEAKER_PREAMP_GAIN_6DB,
) -> bool:
    """Enable the DualSense internal speaker via USB HID output report.

    On macOS (and Windows), the speaker is not enabled by default.
    This sends the same HID output report that the Linux kernel
    driver sends to route audio to the speaker.

    Args:
        volume: Speaker volume (effective range 0x3D-0x64).
        preamp_gain: Preamp gain for bits 0-2 of audio_flags2.

    Returns:
        True if the speaker was enabled successfully.

    """
    if hidapi is None:
        log.warning('hidapi not available — cannot enable DualSense speaker')
        return False

    # Try DualSense, then DualSense Edge
    device: Any = hidapi.device()  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
    try:
        device.open(SONY_VENDOR_ID, DUALSENSE_PRODUCT_ID)  # pyright: ignore[reportUnknownMemberType]
    except OSError:
        try:
            device.open(SONY_VENDOR_ID, DUALSENSE_EDGE_PRODUCT_ID)  # pyright: ignore[reportUnknownMemberType]
        except OSError:
            log.warning('No DualSense found via HID')
            return False

    # Build the 63-byte USB output report
    report = bytearray(DS_OUTPUT_REPORT_SIZE)
    report[0] = DS_OUTPUT_REPORT_USB

    # Byte 1: valid_flag0 — enable audio control + speaker volume
    report[1] = _FLAG0_AUDIO_CONTROL | _FLAG0_SPEAKER_VOLUME

    # Byte 2: valid_flag1 — enable audio_control2 (preamp gain)
    report[2] = _FLAG1_AUDIO_CONTROL2

    # Byte 6: speaker_volume
    report[6] = volume

    # Byte 8: audio_flags — route right channel to speaker, mute HP
    report[8] = _AUDIO_PATH_SPEAKER_ONLY << _AUDIO_PATH_SHIFT

    # Byte 38: audio_flags2 — speaker preamp gain (+6dB)
    report[38] = preamp_gain

    bytes_written: int = device.write(bytes(report))  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
    device.close()  # pyright: ignore[reportUnknownMemberType]

    if bytes_written < 0:
        log.warning('Failed to send speaker enable HID report')
        return False

    log.info(
        'DualSense speaker enabled: volume=0x%02X, gain=0x%02X',
        volume,
        preamp_gain,
    )
    return True


def find_device_by_name(
    device_list: list[dict[str, Any]],
    controller_name: str,
) -> Any | None:
    """Find a miniaudio device ID by matching controller name.

    Args:
        device_list: List of device dicts from miniaudio.
        controller_name: The controller name to match against.

    Returns:
        The native device ID (cdata pointer), or None if not found.

    """
    for device in device_list:
        if controller_name in device.get('name', ''):
            return device.get('id')
    return None


# ---------------------------------------------------------------------------
# Haptic waveform presets (generated mathematically, no files needed)
# ---------------------------------------------------------------------------


def _generate_sine(
    frequency: float,
    duration: float,
    amplitude: float = 0.8,
    sample_rate: int = DUALSENSE_SAMPLE_RATE,
) -> array.array[int]:
    """Generate a sine wave as signed 16-bit samples.

    Args:
        frequency: Frequency in Hz.
        duration: Duration in seconds.
        amplitude: Peak amplitude (0.0 to 1.0).
        sample_rate: Sample rate in Hz.

    Returns:
        Array of signed 16-bit PCM samples.

    """
    max_val = 32767
    num_samples = int(sample_rate * duration)
    return array.array(
        'h',
        [
            int(max_val * amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
            for i in range(num_samples)
        ],
    )


def _generate_click(
    sample_rate: int = DUALSENSE_SAMPLE_RATE,
) -> array.array[int]:
    """Generate a sharp click impulse (single-cycle 200Hz burst).

    Args:
        sample_rate: Sample rate in Hz.

    Returns:
        Array of signed 16-bit PCM samples.

    """
    max_val = 32767
    cycle_samples = sample_rate // 200  # One cycle at 200Hz
    return array.array(
        'h',
        [
            int(max_val * 0.9 * math.sin(2 * math.pi * i / cycle_samples))
            for i in range(cycle_samples)
        ],
    )


def _generate_noise_burst(
    duration: float,
    amplitude: float = 0.5,
    sample_rate: int = DUALSENSE_SAMPLE_RATE,
) -> array.array[int]:
    """Generate filtered noise for texture haptics (gravel, sand).

    Args:
        duration: Duration in seconds.
        amplitude: Peak amplitude (0.0 to 1.0).
        sample_rate: Sample rate in Hz.

    Returns:
        Array of signed 16-bit PCM samples.

    """
    import random

    max_val = 32767
    num_samples = int(sample_rate * duration)
    # Simple low-pass via averaging adjacent samples
    raw = [random.uniform(-1.0, 1.0) for _ in range(num_samples)]
    smoothed = [(raw[i] + raw[max(0, i - 1)]) / 2 for i in range(num_samples)]
    return array.array('h', [int(max_val * amplitude * s) for s in smoothed])


# Preset haptic effects: name → (left_samples, right_samples)
def get_haptic_preset(
    name: str,
    duration: float = 0.15,
) -> tuple[array.array[int], array.array[int]]:
    """Get a haptic preset by name.

    Args:
        name: Preset name ('click', 'buzz', 'pulse', 'rumble', 'texture').
        duration: Duration in seconds (ignored for 'click').

    Returns:
        Tuple of (left_samples, right_samples) as signed 16-bit arrays.

    """
    if name == 'click':
        click = _generate_click()
        return click, click
    if name == 'buzz':
        buzz = _generate_sine(frequency=150, duration=duration, amplitude=0.7)
        return buzz, buzz
    if name == 'pulse':
        pulse = _generate_sine(frequency=40, duration=duration, amplitude=0.9)
        return pulse, pulse
    if name == 'rumble':
        rumble = _generate_sine(frequency=25, duration=duration, amplitude=1.0)
        return rumble, rumble
    if name == 'texture':
        texture = _generate_noise_burst(duration=duration, amplitude=0.4)
        return texture, texture

    log.warning('Unknown haptic preset: %r, falling back to click', name)
    click = _generate_click()
    return click, click


# Speaker haptic mode presets: how much speech bleeds into the haptic motors
HAPTIC_MODES: dict[str, float] = {
    'speech': 0.3,  # Gentle reinforcement — feel the voice subtly
    'alert': 0.7,  # Strong — warnings, collectibles, impacts
    'quiet': 0.0,  # No haptic bleed — ambient, music, background
}


# ---------------------------------------------------------------------------
# 4-channel stream builder
# ---------------------------------------------------------------------------


def _build_4channel_stream(
    speaker_samples: array.array[int] | None = None,
    haptic_left_samples: array.array[int] | None = None,
    haptic_right_samples: array.array[int] | None = None,
    volume: float = 1.0,
    haptic_mix: float = 0.0,
) -> array.array[int]:
    """Interleave mono sources into a 4-channel DualSense audio stream.

    Args:
        speaker_samples: Audio for the mono speaker (channel 1).
        haptic_left_samples: Waveform for left grip motor (channel 2).
        haptic_right_samples: Waveform for right grip motor (channel 3).
        volume: Volume multiplier for speaker audio.
        haptic_mix: How much speaker audio bleeds into haptic channels
            (0.0 = none, 0.3 = subtle, 0.7 = strong, 1.0 = full).

    Returns:
        Interleaved 4-channel signed 16-bit array.

    """
    # Find the longest source to determine total frames
    lengths = [
        len(speaker_samples) if speaker_samples else 0,
        len(haptic_left_samples) if haptic_left_samples else 0,
        len(haptic_right_samples) if haptic_right_samples else 0,
    ]
    num_frames = max(lengths) if lengths else 0

    max_val = 32767
    output = array.array('h', [0]) * (num_frames * DUALSENSE_CHANNELS)

    for i in range(num_frames):
        base = i * DUALSENSE_CHANNELS

        # Channel 1 (Front Right): speaker — the HID report routes
        # the right channel to the mono speaker
        if speaker_samples and i < len(speaker_samples):
            amplified = int(speaker_samples[i] * volume)
            clamped = max(-max_val, min(max_val, amplified))
            output[base + CHANNEL_SPEAKER] = clamped

            # Speech haptic: feed attenuated speech to motors
            if haptic_mix > 0:
                haptic_val = max(-max_val, min(max_val, int(clamped * haptic_mix)))
                output[base + CHANNEL_HAPTIC_LEFT] = haptic_val
                output[base + CHANNEL_HAPTIC_RIGHT] = haptic_val

        # Explicit haptic waveforms override speech haptic
        if haptic_left_samples and i < len(haptic_left_samples):
            output[base + CHANNEL_HAPTIC_LEFT] = haptic_left_samples[i]
        if haptic_right_samples and i < len(haptic_right_samples):
            output[base + CHANNEL_HAPTIC_RIGHT] = haptic_right_samples[i]

    return output


class ControllerAudio:
    """Audio capture, speaker output, and haptic feedback for a game controller.

    For DualSense controllers, opens a 4-channel 48kHz USB audio device
    with speaker on channel 1 and haptic motors on channels 2-3.
    """

    def __init__(  # noqa: PLR0913
        self,
        controller_name: str,
        *,
        capture_device_id: Any = None,
        playback_device_id: Any = None,
        capture_sample_rate: int = 16000,
        capture_channels: int = 1,
        volume: float = 1.0,
    ) -> None:
        """Initialize controller audio.

        Args:
            controller_name: The controller's name string.
            capture_device_id: Override auto-discovered capture device.
            playback_device_id: Override auto-discovered playback device.
            capture_sample_rate: Mic sample rate (default 16000 for speech).
            capture_channels: Mic channels (default 1 = mono).
            volume: Speaker volume multiplier. Values above 1.0 amplify
                quiet audio (e.g. macOS TTS is ~10% of max).

        Raises:
            RuntimeError: If miniaudio is not installed.

        """
        if mi is None:
            msg = 'miniaudio is required for controller audio'
            raise RuntimeError(msg)

        self.controller_name = controller_name
        self.capture_sample_rate = capture_sample_rate
        self.capture_channels = capture_channels
        self.volume = volume

        # Auto-discover devices if not overridden
        devices = mi.Devices()
        self.capture_device_id = (
            capture_device_id
            if capture_device_id is not None
            else find_device_by_name(devices.get_captures(), controller_name)
        )
        self.playback_device_id = (
            playback_device_id
            if playback_device_id is not None
            else find_device_by_name(devices.get_playbacks(), controller_name)
        )

        log.info(
            'Controller audio for %r: capture=%s playback=%s',
            controller_name,
            self.capture_device_id,
            self.playback_device_id,
        )

        # Enable the speaker via HID if this is a DualSense
        if self.has_speaker and 'dualsense' in controller_name.lower():
            enable_dualsense_speaker()

        # Capture state
        self._capture_device: Any = None
        self._capture_buffer: bytearray = bytearray()
        self._capturing: bool = False
        self._capture_lock = threading.Lock()

    @property
    def has_microphone(self) -> bool:
        """Whether a microphone was found for this controller."""
        return self.capture_device_id is not None

    @property
    def has_speaker(self) -> bool:
        """Whether a speaker was found for this controller."""
        return self.playback_device_id is not None

    # --- Capture (Microphone) ---

    def start_capture(self) -> bool:
        """Start recording from the controller's microphone.

        Returns:
            True if capture started successfully.

        """
        if not self.has_microphone or mi is None:
            return False

        with self._capture_lock:
            self._capture_buffer = bytearray()
            self._capturing = True

        def _capture_callback() -> Any:
            """Generator that receives audio data from miniaudio.

            Yields:
                None: Yields to receive audio data from miniaudio capture.

            """
            while True:
                received = yield  # pyright: ignore[reportUnknownVariableType]
                if received and self._capturing:
                    with self._capture_lock:
                        self._capture_buffer.extend(bytes(received))  # pyright: ignore[reportUnknownArgumentType]

        self._capture_device = mi.CaptureDevice(
            input_format=mi.SampleFormat.SIGNED16,
            nchannels=self.capture_channels,
            sample_rate=self.capture_sample_rate,
            device_id=self.capture_device_id,
        )
        generator = _capture_callback()
        next(generator)  # Prime the generator
        self._capture_device.start(generator)
        log.info('Started capture from %r', self.controller_name)
        return True

    def stop_capture(self) -> bytes:
        """Stop recording and return the captured audio data.

        Returns:
            Raw PCM audio bytes (signed 16-bit, mono, capture_sample_rate Hz).

        """
        with self._capture_lock:
            self._capturing = False
            audio_data = bytes(self._capture_buffer)
            self._capture_buffer = bytearray()

        if self._capture_device is not None:
            self._capture_device.stop()
            self._capture_device = None

        log.info('Stopped capture: %d bytes', len(audio_data))
        return audio_data

    def get_speech_recognizer_audio(self, audio_data: bytes) -> Any:
        """Convert raw PCM audio to a speech_recognition AudioData object.

        Args:
            audio_data: Raw PCM bytes from stop_capture().

        Returns:
            A speech_recognition.AudioData object, or None if sr is unavailable.

        """
        if sr is None:
            return None
        sample_width = 2  # 16-bit = 2 bytes
        return sr.AudioData(
            frame_data=audio_data,
            sample_rate=self.capture_sample_rate,
            sample_width=sample_width,
        )

    # --- Playback (Speaker + Haptics) ---

    def play_file(
        self,
        file_path: str | Path,
        haptic: str | None = None,
        haptic_mode: str = 'quiet',
    ) -> bool:
        """Play an audio file through the speaker, optionally with haptics.

        Plays asynchronously in a background thread. Audio is routed to
        channel 1 (speaker) of the 4-channel DualSense device.

        Args:
            file_path: Path to a WAV audio file.
            haptic: Optional haptic preset name to play alongside
                ('click', 'buzz', 'pulse', 'rumble', 'texture').
            haptic_mode: How much speaker audio bleeds into the haptic
                motors. 'speech' (subtle), 'alert' (strong), 'quiet' (none).

        Returns:
            True if playback started.

        """
        if not self.has_speaker or mi is None:
            return False

        path = Path(file_path)
        if not path.exists():
            log.warning('Audio file not found: %s', path)
            return False

        thread = threading.Thread(
            target=self._play_file_blocking,
            args=(path, haptic, haptic_mode),
            daemon=True,
        )
        thread.start()
        return True

    def play_haptic(
        self,
        preset: str = 'click',
        duration: float = 0.15,
    ) -> bool:
        """Play a haptic effect through the controller's grip motors.

        Plays asynchronously in a background thread.

        Args:
            preset: Haptic preset name ('click', 'buzz', 'pulse',
                'rumble', 'texture').
            duration: Duration in seconds (ignored for 'click').

        Returns:
            True if haptic playback started.

        """
        if not self.has_speaker or mi is None:
            return False

        thread = threading.Thread(
            target=self._play_haptic_blocking,
            args=(preset, duration),
            daemon=True,
        )
        thread.start()
        return True

    def play_haptic_custom(
        self,
        left: array.array[int],
        right: array.array[int] | None = None,
    ) -> bool:
        """Play custom haptic waveforms through the grip motors.

        Args:
            left: Signed 16-bit samples for the left grip motor.
            right: Signed 16-bit samples for the right grip motor.
                If None, mirrors the left channel.

        Returns:
            True if haptic playback started.

        """
        if not self.has_speaker or mi is None:
            return False

        if right is None:
            right = left

        thread = threading.Thread(
            target=self._play_4channel_blocking,
            args=(None, left, right),
            daemon=True,
        )
        thread.start()
        return True

    # --- Internal playback ---

    def _play_file_blocking(
        self,
        file_path: Path,
        haptic: str | None = None,
        haptic_mode: str = 'quiet',
    ) -> None:
        """Play audio file on speaker + optional haptic (background thread).

        Decodes the file, converts to mono if needed, routes to channel 1,
        and optionally adds haptic waveforms on channels 2-3.

        Args:
            file_path: Path to the audio file.
            haptic: Optional haptic preset name.
            haptic_mode: Speaker-to-haptic bleed level.

        """
        if mi is None:
            return

        try:
            # Decode to mono at 48kHz for the DualSense
            decoded: Any = mi.decode_file(
                str(file_path),
                output_format=mi.SampleFormat.SIGNED16,
                nchannels=1,
                sample_rate=DUALSENSE_SAMPLE_RATE,
            )
            speaker_samples: array.array[int] = decoded.samples

            # Get haptic waveforms if requested
            haptic_left: array.array[int] | None = None
            haptic_right: array.array[int] | None = None
            if haptic:
                haptic_left, haptic_right = get_haptic_preset(haptic)

            haptic_mix = HAPTIC_MODES.get(haptic_mode, 0.0)
            self._play_4channel_blocking(
                speaker_samples,
                haptic_left,
                haptic_right,
                haptic_mix=haptic_mix,
            )
        except Exception:
            log.exception('Failed to play audio through controller speaker')

    def _play_haptic_blocking(self, preset: str, duration: float) -> None:
        """Play a haptic preset (background thread).

        Args:
            preset: Haptic preset name.
            duration: Duration in seconds.

        """
        try:
            haptic_left, haptic_right = get_haptic_preset(preset, duration)
            self._play_4channel_blocking(None, haptic_left, haptic_right)
        except Exception:
            log.exception('Failed to play haptic effect')

    def _play_4channel_blocking(
        self,
        speaker_samples: array.array[int] | None,
        haptic_left: array.array[int] | None,
        haptic_right: array.array[int] | None,
        *,
        haptic_mix: float = 0.0,
    ) -> None:
        """Play interleaved 4-channel audio through the DualSense (blocking).

        Args:
            speaker_samples: Mono samples for the speaker (channel 1).
            haptic_left: Samples for left grip motor (channel 2).
            haptic_right: Samples for right grip motor (channel 3).
            haptic_mix: Speaker-to-haptic bleed (0.0-1.0).

        """
        if mi is None:
            return

        try:
            # Build interleaved 4-channel stream
            stream_data = _build_4channel_stream(
                speaker_samples=speaker_samples,
                haptic_left_samples=haptic_left,
                haptic_right_samples=haptic_right,
                volume=self.volume,
                haptic_mix=haptic_mix,
            )

            num_frames = len(stream_data) // DUALSENSE_CHANNELS
            offset = 0

            def _stream_generator() -> Any:
                """Yield 4-channel interleaved frames on demand.

                Yields:
                    Interleaved sample data for the requested frames.

                """
                nonlocal offset
                num_requested = yield b''  # pyright: ignore[reportUnknownVariableType]
                while True:
                    num_samples = int(num_requested) * DUALSENSE_CHANNELS  # pyright: ignore[reportUnknownArgumentType]
                    chunk = stream_data[offset : offset + num_samples]
                    offset += num_samples
                    if not chunk:
                        break
                    num_requested = yield chunk  # pyright: ignore[reportUnknownVariableType]

            device: Any = mi.PlaybackDevice(
                output_format=mi.SampleFormat.SIGNED16,
                nchannels=DUALSENSE_CHANNELS,
                sample_rate=DUALSENSE_SAMPLE_RATE,
                device_id=self.playback_device_id,
            )
            generator = _stream_generator()
            next(generator)  # Prime the generator
            device.start(generator)

            duration = num_frames / DUALSENSE_SAMPLE_RATE
            time.sleep(duration + 0.3)
            device.stop()
            log.info(
                'Played %.2fs through %r (speaker=%s haptic=%s)',
                duration,
                self.controller_name,
                speaker_samples is not None,
                haptic_left is not None,
            )
        except Exception:
            log.exception('Failed to play 4-channel audio')

    # --- Factory ---

    @classmethod
    def for_controller(cls, controller_name: str, **kwargs: Any) -> ControllerAudio | None:
        """Create a ControllerAudio if the controller has audio devices.

        Returns None if neither microphone nor speaker is found.

        Args:
            controller_name: The controller's name string.
            **kwargs: Additional arguments passed to the constructor.

        Returns:
            A ControllerAudio instance, or None.

        """
        if mi is None:
            return None

        try:
            audio = cls(controller_name, **kwargs)
        except Exception:
            log.exception('Failed to create controller audio for %r', controller_name)
            return None

        if not audio.has_microphone and not audio.has_speaker:
            log.info('No audio devices found for controller %r', controller_name)
            return None

        return audio

    @classmethod
    def discover(cls, **kwargs: Any) -> ControllerAudio | None:
        """Auto-discover a controller with audio devices.

        Finds devices that appear in both the capture (mic) and
        playback (speaker) device lists by name matching.

        Args:
            **kwargs: Additional arguments passed to the constructor.

        Returns:
            A ControllerAudio for the first matching controller, or None.

        """
        if mi is None:
            return None

        devices = mi.Devices()
        capture_names = {dev['name'] for dev in devices.get_captures()}
        playback_names = {dev['name'] for dev in devices.get_playbacks()}

        # Devices with both mic and speaker are likely controllers
        controller_names = capture_names & playback_names
        for name in controller_names:
            audio = cls.for_controller(name, **kwargs)
            if audio is not None:
                return audio

        return None
