"""Tests for controller audio (glitchygames/audio/controller_audio.py).

miniaudio, hidapi, speech_recognition and threads are replaced with fakes: no real device
is opened, and thread entry points are run synchronously.
"""

from __future__ import annotations

import array
import logging
import math
import threading
import types
from typing import ClassVar

import pytest

from glitchygames.audio import controller_audio
from glitchygames.randomness import reset_streams

NOISE_STREAM_TEST_SEED = 79
TEXTURE_DURATION_SECONDS = 0.01


def _texture_samples() -> list[int]:
    left_samples, right_samples = controller_audio.get_haptic_preset(
        'texture', duration=TEXTURE_DURATION_SECONDS
    )
    assert list(left_samples) == list(right_samples)
    return list(left_samples)


def test_texture_noise_comes_from_the_controller_noise_stream(mocker):
    """Texture haptics draw from random_stream('audio.controller_noise'): a seed repeats them."""
    stream_lookup = mocker.patch.object(
        controller_audio, 'random_stream', wraps=controller_audio.random_stream
    )
    reset_streams(seed=NOISE_STREAM_TEST_SEED)
    first_run = _texture_samples()
    reset_streams(seed=NOISE_STREAM_TEST_SEED)

    assert _texture_samples() == first_run
    assert any(sample != 0 for sample in first_run)
    stream_lookup.assert_called_with('audio.controller_noise')


def test_different_seeds_give_different_texture_noise():
    """The noise depends on the run's seed."""
    reset_streams(seed=NOISE_STREAM_TEST_SEED)
    first_run = _texture_samples()
    reset_streams(seed=NOISE_STREAM_TEST_SEED + 1)

    assert _texture_samples() != first_run


# ---------------------------------------------------------------------------
# Boundary fakes: miniaudio, hidapi and speech_recognition are never touched
# ---------------------------------------------------------------------------

DUALSENSE_NAME = 'DualSense Wireless Controller'
CAPTURE_DEVICE_ID = 'capture-device-id'
PLAYBACK_DEVICE_ID = 'playback-device-id'
FRAMES_PER_REQUEST = 100


class FakePlaybackDevice:
    """Stands in for miniaudio.PlaybackDevice: drains the generator it is started with."""

    def __init__(self, **device_options):
        """Keep the options the device was opened with."""
        self.device_options = device_options
        self.played_samples = array.array('h')
        self.request_count = 0
        self.stopped = False

    def start(self, generator):
        """Pull FRAMES_PER_REQUEST frames at a time until the generator ends."""
        try:
            while True:
                chunk = generator.send(FRAMES_PER_REQUEST)
                self.request_count += 1
                self.played_samples.extend(chunk)
        except StopIteration:
            pass

    def stop(self):
        """Record that the device was stopped."""
        self.stopped = True


class FakeCaptureDevice:
    """Stands in for miniaudio.CaptureDevice: keeps the generator so a test can feed it."""

    def __init__(self, **device_options):
        """Keep the options the device was opened with."""
        self.device_options = device_options
        self.generator = None
        self.stopped = False

    def start(self, generator):
        """Keep the primed generator for the test to send microphone data to."""
        self.generator = generator

    def stop(self):
        """Record that the device was stopped."""
        self.stopped = True


class FakeMiniaudio:
    """A miniaudio module with fake devices and a scripted device list."""

    def __init__(self, *, captures=(), playbacks=()):
        """List the given capture and playback devices."""
        self.captures = list(captures)
        self.playbacks = list(playbacks)
        self.SampleFormat = types.SimpleNamespace(SIGNED16='signed16')
        self.playback_devices: list[FakePlaybackDevice] = []
        self.capture_devices: list[FakeCaptureDevice] = []
        self.decoded_samples = array.array('h')
        self.decode_calls: list[tuple[str, dict]] = []

    def Devices(self):  # ruff: ignore[invalid-function-name] - mirrors miniaudio's class name
        """Return a device list object answering the scripted captures and playbacks."""
        return types.SimpleNamespace(
            get_captures=lambda: self.captures,
            get_playbacks=lambda: self.playbacks,
        )

    def PlaybackDevice(self, **device_options):  # ruff: ignore[invalid-function-name] - mirrors miniaudio's class name
        """Create and remember a fake playback device."""
        device = FakePlaybackDevice(**device_options)
        self.playback_devices.append(device)
        return device

    def CaptureDevice(self, **device_options):  # ruff: ignore[invalid-function-name] - mirrors miniaudio's class name
        """Create and remember a fake capture device."""
        device = FakeCaptureDevice(**device_options)
        self.capture_devices.append(device)
        return device

    def decode_file(self, filename, **decode_options):
        """Return the scripted decoded samples."""
        self.decode_calls.append((filename, decode_options))
        return types.SimpleNamespace(samples=self.decoded_samples)


class FakeHidDevice:
    """Stands in for hid.device: open succeeds only for the listed product ids."""

    def __init__(
        self,
        *,
        openable_product_ids,
        write_result=controller_audio.DS_OUTPUT_REPORT_SIZE,
        write_error=None,
    ):
        """Open only `openable_product_ids`; writes answer `write_result` or raise `write_error`."""
        self.openable_product_ids = openable_product_ids
        self.write_result = write_result
        self.write_error = write_error
        self.opened_product_ids: list[int] = []
        self.written_reports: list[bytes] = []
        self.closed = False

    def open(self, vendor_id, product_id):
        """Open the device, as hidapi does.

        Raises:
            OSError: When the product id is not openable.

        """
        assert vendor_id == controller_audio.SONY_VENDOR_ID
        if product_id not in self.openable_product_ids:
            message = 'open failed'
            raise OSError(message)
        self.opened_product_ids.append(product_id)

    def write(self, report):
        """Record the report, then raise `write_error` or answer the scripted byte count."""
        self.written_reports.append(report)
        if self.write_error is not None:
            raise self.write_error
        return self.write_result

    def close(self):
        """Record that the device was closed."""
        self.closed = True


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


@pytest.fixture
def fake_miniaudio(mocker):
    """Install a FakeMiniaudio listing a DualSense microphone and speaker.

    Returns:
        The installed fake.

    """
    fake = FakeMiniaudio(
        captures=[{'name': f'{DUALSENSE_NAME} Mic', 'id': CAPTURE_DEVICE_ID}],
        playbacks=[{'name': f'{DUALSENSE_NAME} Speaker', 'id': PLAYBACK_DEVICE_ID}],
    )
    mocker.patch.object(controller_audio, 'mi', fake)
    return fake


@pytest.fixture
def enable_speaker(mocker):
    """Replace the HID speaker enable so no HID device is opened.

    Returns:
        The mock standing in for enable_dualsense_speaker.

    """
    return mocker.patch.object(controller_audio, 'enable_dualsense_speaker', return_value=True)


@pytest.fixture
def recorded_threads(mocker):
    """Replace threading in controller_audio with RecordedThread (Lock stays real).

    Returns:
        The list of threads created during the test.

    """
    RecordedThread.created = []
    mocker.patch.object(
        controller_audio,
        'threading',
        types.SimpleNamespace(Thread=RecordedThread, Lock=threading.Lock),
    )
    return RecordedThread.created


@pytest.fixture
def no_sleep(mocker):
    """Replace controller_audio's raw sleep (glitchygames/clock.py's) so playback never sleeps.

    Returns:
        The mock standing in for the sleep.

    """
    return mocker.patch.object(controller_audio, 'raw_sleep')


@pytest.fixture
def dualsense_audio(fake_miniaudio, enable_speaker):
    """A ControllerAudio for the fake DualSense, with both devices found.

    Returns:
        The ControllerAudio.

    """
    return controller_audio.ControllerAudio(DUALSENSE_NAME)


def _channel(samples, channel_index):
    """Return one channel of an interleaved 4-channel stream."""
    return list(samples[channel_index :: controller_audio.DUALSENSE_CHANNELS])


class TestEnableDualSenseSpeaker:
    """enable_dualsense_speaker builds the Linux driver's speaker report and sends it over HID."""

    def test_without_hidapi_returns_false(self, mocker, caplog):
        """No hidapi module, no speaker."""
        mocker.patch.object(controller_audio, 'hidapi', None)

        with caplog.at_level(logging.WARNING, logger='game.audio.controller'):
            assert controller_audio.enable_dualsense_speaker() is False
        assert 'hidapi not available' in caplog.text

    def test_sends_the_speaker_report_to_a_dualsense(self, mocker):
        """The report enables audio control, volume, the speaker-only path and preamp gain."""
        hid_device = FakeHidDevice(openable_product_ids={controller_audio.DUALSENSE_PRODUCT_ID})
        mocker.patch.object(
            controller_audio, 'hidapi', types.SimpleNamespace(device=lambda: hid_device)
        )

        assert controller_audio.enable_dualsense_speaker(volume=0x50, preamp_gain=0x01) is True

        assert hid_device.opened_product_ids == [controller_audio.DUALSENSE_PRODUCT_ID]
        assert hid_device.closed is True
        (report,) = hid_device.written_reports
        assert len(report) == controller_audio.DS_OUTPUT_REPORT_SIZE
        assert report[0] == controller_audio.DS_OUTPUT_REPORT_USB
        assert report[1] == 0x80 | 0x20
        assert report[2] == 0x80
        assert report[6] == 0x50
        assert report[8] == 3 << 4
        assert report[38] == 0x01
        untouched_bytes = set(range(len(report))) - {0, 1, 2, 6, 8, 38}
        assert all(report[index] == 0 for index in untouched_bytes)

    def test_falls_back_to_the_dualsense_edge(self, mocker):
        """When the plain DualSense does not open, the Edge's product id is tried."""
        hid_device = FakeHidDevice(
            openable_product_ids={controller_audio.DUALSENSE_EDGE_PRODUCT_ID}
        )
        mocker.patch.object(
            controller_audio, 'hidapi', types.SimpleNamespace(device=lambda: hid_device)
        )

        assert controller_audio.enable_dualsense_speaker() is True
        assert hid_device.opened_product_ids == [controller_audio.DUALSENSE_EDGE_PRODUCT_ID]
        assert hid_device.written_reports[0][6] == 0x64

    def test_no_dualsense_found_returns_false(self, mocker, caplog):
        """Neither product id opens: nothing is written."""
        hid_device = FakeHidDevice(openable_product_ids=set())
        mocker.patch.object(
            controller_audio, 'hidapi', types.SimpleNamespace(device=lambda: hid_device)
        )

        with caplog.at_level(logging.WARNING, logger='game.audio.controller'):
            assert controller_audio.enable_dualsense_speaker() is False
        assert hid_device.written_reports == []
        assert 'No DualSense found via HID' in caplog.text

    def test_failed_write_returns_false(self, mocker, caplog):
        """The hidapi write answers -1 for a failed write; the device is still closed."""
        hid_device = FakeHidDevice(
            openable_product_ids={controller_audio.DUALSENSE_PRODUCT_ID}, write_result=-1
        )
        mocker.patch.object(
            controller_audio, 'hidapi', types.SimpleNamespace(device=lambda: hid_device)
        )

        with caplog.at_level(logging.WARNING, logger='game.audio.controller'):
            assert controller_audio.enable_dualsense_speaker() is False
        assert hid_device.closed is True
        assert 'Failed to send speaker enable HID report' in caplog.text

    @pytest.mark.parametrize(
        'write_error', [OSError('device disconnected'), ValueError('not open')]
    )
    def test_write_that_raises_returns_false_and_closes(self, mocker, caplog, write_error):
        """A write that raises closes the device and only fails the enable (BUGS.md #108)."""
        hid_device = FakeHidDevice(
            openable_product_ids={controller_audio.DUALSENSE_PRODUCT_ID}, write_error=write_error
        )
        mocker.patch.object(
            controller_audio, 'hidapi', types.SimpleNamespace(device=lambda: hid_device)
        )

        with caplog.at_level(logging.WARNING, logger='game.audio.controller'):
            assert controller_audio.enable_dualsense_speaker() is False
        assert hid_device.closed is True
        assert 'Failed to send speaker enable HID report' in caplog.text


class TestFindDeviceByName:
    """find_device_by_name returns the first device whose name contains the controller's."""

    def test_returns_the_first_matching_id(self):
        """Substring match, first match wins."""
        device_list = [
            {'name': 'Built-in Microphone', 'id': 'built-in'},
            {'name': 'DualSense Wireless Controller', 'id': 'first'},
            {'name': 'DualSense Wireless Controller (2)', 'id': 'second'},
        ]

        assert controller_audio.find_device_by_name(device_list, 'DualSense') == 'first'

    def test_no_match_or_nameless_device_returns_none(self):
        """A device without a name never matches."""
        assert controller_audio.find_device_by_name([{'id': 'nameless'}], 'DualSense') is None


class TestHapticPresets:
    """get_haptic_preset generates each named waveform for both motors."""

    def test_click_is_one_200hz_cycle(self):
        """The click is a single 200 Hz cycle at 90% amplitude, the same on both motors."""
        left_samples, right_samples = controller_audio.get_haptic_preset('click')

        assert left_samples is right_samples
        assert len(left_samples) == controller_audio.DUALSENSE_SAMPLE_RATE // 200
        assert left_samples[0] == 0
        assert max(left_samples) == int(32767 * 0.9)
        assert min(left_samples) == -int(32767 * 0.9)

    @pytest.mark.parametrize(
        ('name', 'frequency', 'amplitude'),
        [('buzz', 150, 0.7), ('pulse', 40, 0.9), ('rumble', 25, 1.0)],
    )
    def test_sine_presets(self, name, frequency, amplitude):
        """Buzz, pulse and rumble are sines of their frequency, amplitude and duration."""
        duration = 0.05
        left_samples, right_samples = controller_audio.get_haptic_preset(name, duration=duration)

        assert left_samples is right_samples
        sample_rate = controller_audio.DUALSENSE_SAMPLE_RATE
        assert len(left_samples) == int(sample_rate * duration)
        quarter_period = sample_rate // (4 * frequency)
        expected_quarter = int(
            32767 * amplitude * math.sin(2 * math.pi * frequency * quarter_period / sample_rate)
        )
        assert left_samples[quarter_period] == expected_quarter

    def test_texture_stays_within_its_amplitude(self):
        """Texture noise is scaled to 40% of full scale."""
        reset_streams(seed=NOISE_STREAM_TEST_SEED)
        samples = _texture_samples()

        assert len(samples) == int(controller_audio.DUALSENSE_SAMPLE_RATE * 0.01)
        assert max(abs(sample) for sample in samples) <= int(32767 * 0.4)

    def test_unknown_preset_falls_back_to_click(self, caplog):
        """An unknown name logs a warning and gives the click."""
        with caplog.at_level(logging.WARNING, logger='game.audio.controller'):
            left_samples, right_samples = controller_audio.get_haptic_preset('wobble')

        assert list(left_samples) == list(controller_audio.get_haptic_preset('click')[0])
        assert left_samples is right_samples
        assert "Unknown haptic preset: 'wobble'" in caplog.text


class TestBuild4ChannelStream:
    """_build_4channel_stream interleaves speaker and motor sources into DualSense channels."""

    def test_empty_sources_give_an_empty_stream(self):
        """No sources, no frames."""
        assert len(controller_audio._build_4channel_stream()) == 0

    def test_speaker_goes_to_channel_one_amplified_and_clamped(self):
        """The speaker is scaled by volume and clamped to +/-32767 on channel 1 only."""
        speaker_samples = array.array('h', [100, -100, 20000, -20000])

        stream = controller_audio._build_4channel_stream(
            speaker_samples=speaker_samples, volume=2.0
        )

        assert _channel(stream, controller_audio.CHANNEL_SPEAKER) == [200, -200, 32767, -32767]
        assert _channel(stream, controller_audio.CHANNEL_HEADPHONE_LEFT) == [0, 0, 0, 0]
        assert _channel(stream, controller_audio.CHANNEL_HAPTIC_LEFT) == [0, 0, 0, 0]
        assert _channel(stream, controller_audio.CHANNEL_HAPTIC_RIGHT) == [0, 0, 0, 0]

    def test_haptic_mix_bleeds_the_speaker_into_both_motors(self):
        """With a haptic mix the clamped speaker value, scaled by the mix, drives both motors."""
        speaker_samples = array.array('h', [1000, -30000])

        stream = controller_audio._build_4channel_stream(
            speaker_samples=speaker_samples, volume=2.0, haptic_mix=0.5
        )

        assert _channel(stream, controller_audio.CHANNEL_HAPTIC_LEFT) == [1000, -16383]
        assert _channel(stream, controller_audio.CHANNEL_HAPTIC_RIGHT) == [1000, -16383]

    def test_explicit_haptics_override_the_speech_bleed_and_set_the_length(self):
        """Motor waveforms replace the bleed where they have samples; the longest source wins."""
        speaker_samples = array.array('h', [1000, 1000])
        left_samples = array.array('h', [7, 8, 9])
        right_samples = array.array('h', [-5])

        stream = controller_audio._build_4channel_stream(
            speaker_samples=speaker_samples,
            haptic_left_samples=left_samples,
            haptic_right_samples=right_samples,
            haptic_mix=0.3,
        )

        assert len(stream) == 3 * controller_audio.DUALSENSE_CHANNELS
        assert _channel(stream, controller_audio.CHANNEL_SPEAKER) == [1000, 1000, 0]
        assert _channel(stream, controller_audio.CHANNEL_HAPTIC_LEFT) == [7, 8, 9]
        assert _channel(stream, controller_audio.CHANNEL_HAPTIC_RIGHT) == [-5, 300, 0]


class TestControllerAudioConstruction:
    """ControllerAudio finds its devices by name and enables a DualSense speaker."""

    def test_requires_miniaudio(self, mocker):
        """Without miniaudio construction raises RuntimeError."""
        mocker.patch.object(controller_audio, 'mi', None)

        with pytest.raises(RuntimeError, match='miniaudio is required'):
            controller_audio.ControllerAudio(DUALSENSE_NAME)

    def test_discovers_devices_and_enables_the_dualsense_speaker(
        self, fake_miniaudio, enable_speaker
    ):
        """Both device ids are found by name and the HID speaker enable is sent."""
        audio = controller_audio.ControllerAudio(DUALSENSE_NAME, volume=3.0)

        assert audio.capture_device_id == CAPTURE_DEVICE_ID
        assert audio.playback_device_id == PLAYBACK_DEVICE_ID
        assert audio.has_microphone is True
        assert audio.has_speaker is True
        assert audio.volume == 3.0
        enable_speaker.assert_called_once_with()

    def test_overrides_win_and_other_controllers_skip_the_hid_enable(
        self, fake_miniaudio, enable_speaker
    ):
        """Given device ids are used as-is; a non-DualSense never gets the HID report."""
        audio = controller_audio.ControllerAudio(
            'Xbox Controller', capture_device_id='mic', playback_device_id='speaker'
        )

        assert audio.capture_device_id == 'mic'
        assert audio.playback_device_id == 'speaker'
        enable_speaker.assert_not_called()

    def test_failed_hid_write_keeps_the_controller_audio(self, fake_miniaudio, mocker):
        """A HID write that raises loses only the speaker enable, not the controller's audio."""
        hid_device = FakeHidDevice(
            openable_product_ids={controller_audio.DUALSENSE_PRODUCT_ID},
            write_error=OSError('device disconnected'),
        )
        mocker.patch.object(
            controller_audio, 'hidapi', types.SimpleNamespace(device=lambda: hid_device)
        )

        audio = controller_audio.ControllerAudio.for_controller(DUALSENSE_NAME)

        assert audio is not None
        assert audio.has_microphone is True
        assert hid_device.closed is True

    def test_dualsense_without_a_speaker_skips_the_hid_enable(self, mocker, enable_speaker):
        """No playback device: no speaker to enable."""
        mocker.patch.object(
            controller_audio,
            'mi',
            FakeMiniaudio(captures=[{'name': DUALSENSE_NAME, 'id': CAPTURE_DEVICE_ID}]),
        )

        audio = controller_audio.ControllerAudio(DUALSENSE_NAME)

        assert audio.has_microphone is True
        assert audio.has_speaker is False
        enable_speaker.assert_not_called()


class TestCapture:
    """The microphone capture collects what miniaudio sends while capturing."""

    def test_start_without_microphone_returns_false(self, mocker, enable_speaker):
        """No capture device found: capture does not start."""
        fake = FakeMiniaudio(playbacks=[{'name': DUALSENSE_NAME, 'id': PLAYBACK_DEVICE_ID}])
        mocker.patch.object(controller_audio, 'mi', fake)
        audio = controller_audio.ControllerAudio(DUALSENSE_NAME)

        assert audio.start_capture() is False
        assert fake.capture_devices == []

    def test_start_without_miniaudio_returns_false(self, dualsense_audio, mocker):
        """With miniaudio gone after construction: capture does not start."""
        mocker.patch.object(controller_audio, 'mi', None)

        assert dualsense_audio.start_capture() is False

    def test_captured_bytes_come_back_from_stop(self, dualsense_audio, fake_miniaudio):
        """Data sent to the capture generator is returned by stop_capture, then cleared."""
        assert dualsense_audio.start_capture() is True
        (capture_device,) = fake_miniaudio.capture_devices
        assert capture_device.device_options == {
            'input_format': 'signed16',
            'nchannels': 1,
            'sample_rate': 16000,
            'device_id': CAPTURE_DEVICE_ID,
        }

        capture_device.generator.send(b'\x01\x02')
        capture_device.generator.send(None)  # An empty callback adds nothing
        capture_device.generator.send(bytearray(b'\x03\x04'))

        assert dualsense_audio.stop_capture() == b'\x01\x02\x03\x04'
        assert capture_device.stopped is True
        assert dualsense_audio.stop_capture() == b''

    def test_data_after_stop_is_ignored(self, dualsense_audio, fake_miniaudio):
        """A late callback after stop_capture does not refill the buffer."""
        dualsense_audio.start_capture()
        generator = fake_miniaudio.capture_devices[0].generator
        dualsense_audio.stop_capture()

        generator.send(b'\x09\x09')

        assert dualsense_audio.stop_capture() == b''

    def test_speech_recognizer_audio_wraps_the_pcm(self, dualsense_audio, mocker):
        """The PCM is wrapped as 16-bit audio at the capture sample rate."""
        audio_data_class = mocker.Mock(name='AudioData')
        mocker.patch.object(
            controller_audio, 'sr', types.SimpleNamespace(AudioData=audio_data_class)
        )

        result = dualsense_audio.get_speech_recognizer_audio(b'\x00\x01')

        assert result is audio_data_class.return_value
        audio_data_class.assert_called_once_with(
            frame_data=b'\x00\x01', sample_rate=16000, sample_width=2
        )

    def test_speech_recognizer_audio_without_speech_recognition(self, dualsense_audio, mocker):
        """No speech_recognition module: None."""
        mocker.patch.object(controller_audio, 'sr', None)

        assert dualsense_audio.get_speech_recognizer_audio(b'\x00') is None


class TestPlaybackStarters:
    """play_file, play_haptic and play_haptic_custom start a daemon thread with their work."""

    def test_nothing_starts_without_a_speaker(
        self, mocker, enable_speaker, recorded_threads, tmp_path
    ):
        """No playback device: every player returns False and starts no thread."""
        mocker.patch.object(
            controller_audio,
            'mi',
            FakeMiniaudio(captures=[{'name': DUALSENSE_NAME, 'id': CAPTURE_DEVICE_ID}]),
        )
        audio = controller_audio.ControllerAudio(DUALSENSE_NAME)
        sound_file = tmp_path / 'sound.wav'
        sound_file.write_bytes(b'RIFF')

        assert audio.play_file(sound_file) is False
        assert audio.play_haptic('buzz') is False
        assert audio.play_haptic_custom(array.array('h', [1])) is False
        assert recorded_threads == []

    def test_nothing_starts_without_miniaudio(self, dualsense_audio, mocker, recorded_threads):
        """With miniaudio gone after construction: no player starts."""
        mocker.patch.object(controller_audio, 'mi', None)

        assert dualsense_audio.play_file('/any/file.wav') is False
        assert dualsense_audio.play_haptic() is False
        assert dualsense_audio.play_haptic_custom(array.array('h', [1])) is False
        assert recorded_threads == []

    def test_play_file_refuses_a_missing_file(
        self, dualsense_audio, recorded_threads, tmp_path, caplog
    ):
        """A file that does not exist is logged and not played."""
        missing_file = tmp_path / 'missing.wav'

        with caplog.at_level(logging.WARNING, logger='game.audio.controller'):
            assert dualsense_audio.play_file(missing_file) is False
        assert recorded_threads == []
        assert 'Audio file not found' in caplog.text

    def test_play_file_starts_a_daemon_thread(self, dualsense_audio, recorded_threads, tmp_path):
        """The thread gets the path, haptic preset and mode."""
        sound_file = tmp_path / 'sound.wav'
        sound_file.write_bytes(b'RIFF')

        assert dualsense_audio.play_file(str(sound_file), haptic='click', haptic_mode='alert')

        (thread,) = recorded_threads
        assert thread.started is True
        assert thread.daemon is True
        assert thread.target == dualsense_audio._play_file_blocking
        assert thread.args == (sound_file, 'click', 'alert')

    def test_play_haptic_starts_a_daemon_thread(self, dualsense_audio, recorded_threads):
        """The thread gets the preset and duration."""
        assert dualsense_audio.play_haptic('pulse', duration=0.2) is True

        (thread,) = recorded_threads
        assert thread.started is True
        assert thread.target == dualsense_audio._play_haptic_blocking
        assert thread.args == ('pulse', 0.2)

    def test_play_haptic_custom_mirrors_left_when_right_is_missing(
        self, dualsense_audio, recorded_threads
    ):
        """Without a right waveform the left one drives both motors."""
        left_samples = array.array('h', [1, 2])

        assert dualsense_audio.play_haptic_custom(left_samples) is True

        (thread,) = recorded_threads
        assert thread.target == dualsense_audio._play_4channel_blocking
        assert thread.args == (None, left_samples, left_samples)

    def test_play_haptic_custom_keeps_a_given_right(self, dualsense_audio, recorded_threads):
        """A given right waveform is passed through."""
        left_samples = array.array('h', [1])
        right_samples = array.array('h', [2])

        dualsense_audio.play_haptic_custom(left_samples, right_samples)

        assert recorded_threads[0].args == (None, left_samples, right_samples)


class TestPlaybackThreads:
    """The playback threads' entry points, run synchronously against the fake device."""

    def test_haptic_thread_streams_the_preset_to_the_motors(
        self, dualsense_audio, fake_miniaudio, recorded_threads, no_sleep
    ):
        """A click plays on both motor channels; the speaker channel stays silent."""
        dualsense_audio.play_haptic('click')
        recorded_threads[0].run_now()

        (device,) = fake_miniaudio.playback_devices
        assert device.device_options == {
            'output_format': 'signed16',
            'nchannels': controller_audio.DUALSENSE_CHANNELS,
            'sample_rate': controller_audio.DUALSENSE_SAMPLE_RATE,
            'device_id': PLAYBACK_DEVICE_ID,
        }
        click = list(controller_audio.get_haptic_preset('click')[0])
        assert _channel(device.played_samples, controller_audio.CHANNEL_HAPTIC_LEFT) == click
        assert _channel(device.played_samples, controller_audio.CHANNEL_HAPTIC_RIGHT) == click
        assert set(_channel(device.played_samples, controller_audio.CHANNEL_SPEAKER)) == {0}
        # 240 frames in requests of 100: three chunks, the fourth request ends the stream
        assert device.request_count == 3
        assert device.stopped is True
        no_sleep.assert_called_once_with(len(click) / controller_audio.DUALSENSE_SAMPLE_RATE + 0.3)

    def test_file_thread_decodes_and_plays_speech_with_haptic_bleed(
        self, fake_miniaudio, enable_speaker, recorded_threads, no_sleep, tmp_path
    ):
        """The file is decoded to 48 kHz mono, amplified, and bled into the motors (speech mode)."""
        audio = controller_audio.ControllerAudio(DUALSENSE_NAME, volume=2.0)
        fake_miniaudio.decoded_samples = array.array('h', [1000, -2000, 3000])
        sound_file = tmp_path / 'speech.wav'
        sound_file.write_bytes(b'RIFF')

        audio.play_file(sound_file, haptic_mode='speech')
        recorded_threads[0].run_now()

        assert fake_miniaudio.decode_calls == [
            (
                str(sound_file),
                {
                    'output_format': 'signed16',
                    'nchannels': 1,
                    'sample_rate': controller_audio.DUALSENSE_SAMPLE_RATE,
                },
            )
        ]
        played_samples = fake_miniaudio.playback_devices[0].played_samples
        assert _channel(played_samples, controller_audio.CHANNEL_SPEAKER) == [2000, -4000, 6000]
        assert _channel(played_samples, controller_audio.CHANNEL_HAPTIC_LEFT) == [600, -1200, 1800]

    def test_file_thread_with_a_haptic_preset_and_unknown_mode(
        self, dualsense_audio, fake_miniaudio, recorded_threads, no_sleep, tmp_path
    ):
        """A preset overrides the motors; an unknown mode means no bleed."""
        fake_miniaudio.decoded_samples = array.array('h', [5] * 300)
        sound_file = tmp_path / 'effect.wav'
        sound_file.write_bytes(b'RIFF')

        dualsense_audio.play_file(sound_file, haptic='click', haptic_mode='no-such-mode')
        recorded_threads[0].run_now()

        played_samples = fake_miniaudio.playback_devices[0].played_samples
        click = list(controller_audio.get_haptic_preset('click')[0])
        left_channel = _channel(played_samples, controller_audio.CHANNEL_HAPTIC_LEFT)
        assert left_channel == click + [0] * (300 - len(click))
        assert _channel(played_samples, controller_audio.CHANNEL_SPEAKER) == [5] * 300

    def test_file_thread_logs_a_decode_failure(
        self, dualsense_audio, fake_miniaudio, mocker, caplog, tmp_path
    ):
        """A decode error is logged at the thread boundary, not raised."""
        mocker.patch.object(fake_miniaudio, 'decode_file', side_effect=ValueError('bad wav'))

        with caplog.at_level(logging.ERROR, logger='game.audio.controller'):
            dualsense_audio._play_file_blocking(tmp_path / 'bad.wav')

        assert 'Failed to play audio through controller speaker' in caplog.text
        assert fake_miniaudio.playback_devices == []

    def test_file_thread_without_miniaudio_does_nothing(self, dualsense_audio, mocker, tmp_path):
        """With miniaudio gone the thread returns at once."""
        play_file = mocker.patch.object(dualsense_audio, '_play_file')
        mocker.patch.object(controller_audio, 'mi', None)

        dualsense_audio._play_file_blocking(tmp_path / 'x.wav')

        play_file.assert_not_called()

    def test_haptic_thread_logs_a_preset_failure(self, dualsense_audio, mocker, caplog):
        """A failure building the preset is logged at the thread boundary."""
        mocker.patch.object(
            controller_audio, 'get_haptic_preset', side_effect=RuntimeError('preset broke')
        )

        with caplog.at_level(logging.ERROR, logger='game.audio.controller'):
            dualsense_audio._play_haptic_blocking('click', 0.1)

        assert 'Failed to play haptic effect' in caplog.text

    def test_4channel_thread_logs_a_device_failure(
        self, dualsense_audio, fake_miniaudio, mocker, caplog
    ):
        """A playback device that cannot open is logged at the thread boundary."""
        mocker.patch.object(
            fake_miniaudio, 'PlaybackDevice', side_effect=RuntimeError('device busy')
        )

        with caplog.at_level(logging.ERROR, logger='game.audio.controller'):
            dualsense_audio._play_4channel_blocking(None, array.array('h', [1]), None)

        assert 'Failed to play 4-channel audio' in caplog.text

    def test_4channel_thread_without_miniaudio_does_nothing(self, dualsense_audio, mocker):
        """With miniaudio gone the thread returns at once."""
        stream = mocker.patch.object(dualsense_audio, '_stream_4channel')
        mocker.patch.object(controller_audio, 'mi', None)

        dualsense_audio._play_4channel_blocking(None, array.array('h', [1]), None)

        stream.assert_not_called()


class TestFactories:
    """for_controller and discover build a ControllerAudio only when a device exists."""

    def test_for_controller_without_miniaudio(self, mocker):
        """No miniaudio: None."""
        mocker.patch.object(controller_audio, 'mi', None)

        assert controller_audio.ControllerAudio.for_controller(DUALSENSE_NAME) is None

    def test_for_controller_returns_audio_with_devices(self, fake_miniaudio, enable_speaker):
        """A controller with devices gets a ControllerAudio; kwargs reach the constructor."""
        audio = controller_audio.ControllerAudio.for_controller(DUALSENSE_NAME, volume=4.0)

        assert audio is not None
        assert audio.playback_device_id == PLAYBACK_DEVICE_ID
        assert audio.volume == 4.0

    def test_for_controller_without_devices_returns_none(
        self, fake_miniaudio, enable_speaker, caplog
    ):
        """A controller with neither microphone nor speaker gets None."""
        with caplog.at_level(logging.INFO, logger='game.audio.controller'):
            audio = controller_audio.ControllerAudio.for_controller('Joy-Con (L)')

        assert audio is None
        assert "No audio devices found for controller 'Joy-Con (L)'" in caplog.text

    def test_for_controller_logs_a_constructor_failure(self, fake_miniaudio, mocker, caplog):
        """A device list that fails is logged and gives None."""
        mocker.patch.object(fake_miniaudio, 'Devices', side_effect=RuntimeError('no backend'))

        with caplog.at_level(logging.ERROR, logger='game.audio.controller'):
            audio = controller_audio.ControllerAudio.for_controller(DUALSENSE_NAME)

        assert audio is None
        assert 'Failed to create controller audio' in caplog.text

    def test_discover_without_miniaudio(self, mocker):
        """No miniaudio: None."""
        mocker.patch.object(controller_audio, 'mi', None)

        assert controller_audio.ControllerAudio.discover() is None

    def test_discover_picks_a_device_with_both_microphone_and_speaker(self, mocker, enable_speaker):
        """Only names in both lists are tried; kwargs reach the constructor."""
        fake = FakeMiniaudio(
            captures=[
                {'name': 'Built-in Microphone', 'id': 'built-in-mic'},
                {'name': DUALSENSE_NAME, 'id': CAPTURE_DEVICE_ID},
            ],
            playbacks=[
                {'name': 'Built-in Speakers', 'id': 'built-in-speaker'},
                {'name': DUALSENSE_NAME, 'id': PLAYBACK_DEVICE_ID},
            ],
        )
        mocker.patch.object(controller_audio, 'mi', fake)

        audio = controller_audio.ControllerAudio.discover(volume=5.0)

        assert audio is not None
        assert audio.controller_name == DUALSENSE_NAME
        assert audio.capture_device_id == CAPTURE_DEVICE_ID
        assert audio.volume == 5.0

    def test_discover_returns_none_when_no_candidate_works(self, mocker):
        """Every shared name is tried; when none gives audio the result is None."""
        fake = FakeMiniaudio(
            captures=[{'name': 'Headset A', 'id': 1}, {'name': 'Headset B', 'id': 2}],
            playbacks=[{'name': 'Headset A', 'id': 3}, {'name': 'Headset B', 'id': 4}],
        )
        mocker.patch.object(controller_audio, 'mi', fake)
        for_controller = mocker.patch.object(
            controller_audio.ControllerAudio, 'for_controller', return_value=None
        )

        assert controller_audio.ControllerAudio.discover() is None
        tried_names = {call.args[0] for call in for_controller.call_args_list}
        assert tried_names == {'Headset A', 'Headset B'}
