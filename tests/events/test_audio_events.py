"""Tests for audio event functionality.

This module tests audio event interfaces, stubs, event handling,
AudioEventProxy delegation, and AudioEventManager initialization, with real pygame
events, the real mixer and real scenes.
"""

import argparse

import pygame
import pytest
from scripts.record_golden_traces import GoldenTraceEngine, GoldenTraceSceneManager, command_line

from glitchygames.events import (
    AudioEvents,
    AudioEventStubs,
    HashableEvent,
    UnhandledEventError,
)
from glitchygames.events.audio import AudioEventManager
from glitchygames.live_sources import LiveSources
from glitchygames.scenes import Scene
from glitchygames.sources import install_sources

EVENT_TEST_OPTIONS = {'debug_events': False, 'no_unhandled_events': True}


class AudioRecordingScene(Scene):
    """A real scene that records the audio events it receives, in order."""

    def __init__(self, options=None, groups=None):
        """Create the scene with no audio events received yet."""
        super().__init__(
            options=options if options is not None else dict(EVENT_TEST_OPTIONS),
            groups=groups,
        )
        self.audio_events_received: list[tuple[str, HashableEvent]] = []

    def on_audio_device_added_event(self, event):
        """Record an audio device added event."""
        self.audio_events_received.append(('added', event))

    def on_audio_device_removed_event(self, event):
        """Record an audio device removed event."""
        self.audio_events_received.append(('removed', event))


class ScriptedBatchSources(LiveSources):
    """Live doors whose first pump returns a scripted batch (the real queue is drained)."""

    def __init__(self, *, batch):
        """Create the doors with one scripted batch to serve."""
        super().__init__(random_seed=1)
        self.batches = [batch]

    def pump_events(self):
        """Drain SDL's queue and return the scripted batch once, then nothing.

        Returns:
            The scripted batch on the first pump, an empty list afterwards.

        """
        pygame.event.get()
        return self.batches.pop(0) if self.batches else []


def stub_with_strict_options():
    """Create audio stubs whose options make unhandled events raise.

    Returns:
        AudioEventStubs: Stubs with ``no_unhandled_events`` enabled.

    """
    stub = AudioEventStubs()
    stub.options = dict(EVENT_TEST_OPTIONS)
    return stub


class TestAudioEventProxy:
    """Test AudioEventProxy event delegation."""

    def test_proxy_init(self):
        game = AudioRecordingScene()
        proxy = AudioEventManager.AudioEventProxy(game=game)
        assert proxy.game is game
        assert proxy.proxies == [game, pygame.mixer]

    def test_on_audio_device_added_event(self):
        game = AudioRecordingScene()
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1, iscapture=False)
        proxy = AudioEventManager.AudioEventProxy(game=game)
        proxy.on_audio_device_added_event(event)
        assert game.audio_events_received == [('added', event)]

    def test_on_audio_device_removed_event(self):
        game = AudioRecordingScene()
        event = HashableEvent(pygame.AUDIODEVICEREMOVED, which=1, iscapture=False)
        proxy = AudioEventManager.AudioEventProxy(game=game)
        proxy.on_audio_device_removed_event(event)
        assert game.audio_events_received == [('removed', event)]


class TestAudioEventManager:
    """Test AudioEventManager initialization."""

    def test_init(self):
        game = AudioRecordingScene()
        manager = AudioEventManager(game=game)
        assert len(manager.proxies) == 1
        assert manager.proxies[0].game is game

    def test_init_does_not_call_pre_init(self, mocker):
        """pre_init after pygame.init() never took effect, so it is not called (BUGS.md #22)."""
        pre_init = mocker.spy(pygame.mixer, 'pre_init')
        AudioEventManager(game=AudioRecordingScene())
        pre_init.assert_not_called()

    def test_init_keeps_the_running_mixer(self):
        """The mixer pygame.init() started keeps its settings after the manager is made."""
        mixer_settings_before = pygame.mixer.get_init()
        AudioEventManager(game=AudioRecordingScene())
        assert pygame.mixer.get_init() == mixer_settings_before

    def test_init_survives_missing_audio_device(self, mocker, caplog):
        """No audio device logs a warning and continues silently (BUGS.md #23)."""
        # No audio device cannot be produced for real: simulate the mixer failing to start
        mocker.patch('pygame.mixer.init', side_effect=pygame.error('no audio device'))
        mocker.patch('pygame.mixer.get_init', return_value=None)
        with caplog.at_level('WARNING', logger='game.audio'):
            manager = AudioEventManager(game=AudioRecordingScene())
        assert len(manager.proxies) == 1
        assert 'Audio unavailable, running silently: no audio device' in caplog.text
        assert 'Mixer is not initialized; audio may be unavailable' in caplog.text

    def test_args(self):
        parser = argparse.ArgumentParser()
        result = AudioEventManager.args(parser)
        assert result is parser
        assert any(group.title == 'Sound Mixer Options' for group in parser._action_groups)


class TestAudioEvents:
    """Test AudioEvents interface functionality."""

    def test_audio_events_interface(self):
        """Test AudioEvents interface methods."""
        # Test that AudioEvents has required abstract methods
        assert hasattr(AudioEvents, 'on_audio_device_added_event')
        assert hasattr(AudioEvents, 'on_audio_device_removed_event')

    def test_audio_event_stubs_implementation(self, mocker):
        """Test AudioEventStubs implementation."""
        stub = stub_with_strict_options()

        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1)
        # Silence the "Unhandled Event" log during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_audio_device_added_event(event)
        with pytest.raises(UnhandledEventError):
            stub.on_audio_device_removed_event(
                HashableEvent(pygame.AUDIODEVICEREMOVED, which=1),
            )

    def test_audio_device_added_event(self):
        """The manager delivers an audio device added event to the scene."""
        scene = AudioRecordingScene()
        manager = AudioEventManager(game=scene)

        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1)
        manager.on_audio_device_added_event(event)

        assert scene.audio_events_received == [('added', event)]
        assert scene.audio_events_received[0][1].which == 1

    def test_audio_device_removed_event(self):
        """The manager delivers an audio device removed event to the scene."""
        scene = AudioRecordingScene()
        manager = AudioEventManager(game=scene)

        event = HashableEvent(pygame.AUDIODEVICEREMOVED, which=1)
        manager.on_audio_device_removed_event(event)

        assert scene.audio_events_received == [('removed', event)]
        assert scene.audio_events_received[0][1].which == 1

    def test_multiple_audio_devices(self):
        """Test multiple audio device events."""
        scene = AudioRecordingScene()
        manager = AudioEventManager(game=scene)

        for device_id in range(5):
            manager.on_audio_device_added_event(
                HashableEvent(pygame.AUDIODEVICEADDED, which=device_id),
            )
            manager.on_audio_device_removed_event(
                HashableEvent(pygame.AUDIODEVICEREMOVED, which=device_id),
            )

        assert len(scene.audio_events_received) == 10  # 5 added + 5 removed
        assert [(kind, event.which) for kind, event in scene.audio_events_received] == [
            (kind, device_id) for device_id in range(5) for kind in ('added', 'removed')
        ]

    def test_audio_device_events_with_iscapture(self):
        """Test audio device events with iscapture parameter."""
        scene = AudioRecordingScene()
        manager = AudioEventManager(game=scene)

        manager.on_audio_device_added_event(
            HashableEvent(pygame.AUDIODEVICEADDED, which=1, iscapture=True),
        )
        manager.on_audio_device_added_event(
            HashableEvent(pygame.AUDIODEVICEADDED, which=1, iscapture=False),
        )
        manager.on_audio_device_removed_event(
            HashableEvent(pygame.AUDIODEVICEREMOVED, which=1, iscapture=True),
        )
        manager.on_audio_device_removed_event(
            HashableEvent(pygame.AUDIODEVICEREMOVED, which=1, iscapture=False),
        )

        assert [(kind, event.iscapture) for kind, event in scene.audio_events_received] == [
            ('added', True),
            ('added', False),
            ('removed', True),
            ('removed', False),
        ]


class TestAudioEventFlow:
    """Test audio events through the proper engine flow."""

    def test_audio_event_through_engine(self):
        """A pumped AUDIODEVICEADDED reaches the active scene through the engine's managers."""
        scene_manager = GoldenTraceSceneManager.install()
        with command_line([
            '--windowed',
            '--resolution',
            '800x600',
            '--log-level',
            'warning',
            '--no-unhandled-events',
        ]):
            engine = GoldenTraceEngine(game=AudioRecordingScene)
        engine.install_game(scene_class=AudioRecordingScene)
        scene = scene_manager.active_scene
        install_sources(
            sources=ScriptedBatchSources(
                batch=[pygame.event.Event(pygame.AUDIODEVICEADDED, which=1, iscapture=0)],
            ),
        )

        assert engine.process_events() is True

        assert [(kind, event.type, event.which) for kind, event in scene.audio_events_received] == [
            ('added', pygame.AUDIODEVICEADDED, 1),
        ]

    def test_audio_event_falls_back_to_stubs(self, mocker):
        """Test that unhandled audio events fall back to stubs and cause UnhandledEventError."""
        stub = stub_with_strict_options()

        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1)

        # Silence the "Unhandled Event" log during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_audio_device_added_event(event)

    def test_audio_manager_initialization(self):
        """Test AudioEventManager initializes correctly with the real mixer."""
        game = AudioRecordingScene()
        manager = AudioEventManager(game=game)

        assert manager.game is game
        assert hasattr(manager, 'on_audio_device_added_event')
        assert hasattr(manager, 'on_audio_device_removed_event')

    def test_audio_manager_directly(self):
        """A real Scene's own audio handlers handle both events (no UnhandledEventError)."""
        scene = Scene(options=dict(EVENT_TEST_OPTIONS))
        manager = AudioEventManager(game=scene)

        manager.on_audio_device_added_event(
            HashableEvent(pygame.AUDIODEVICEADDED, which=1, iscapture=True),
        )
        manager.on_audio_device_removed_event(
            HashableEvent(pygame.AUDIODEVICEREMOVED, which=1, iscapture=False),
        )


class TestAudioEventManagerWithoutVideo:
    """Constructing the manager before pygame's video system is up."""

    def test_unallowed_events_are_logged_and_the_manager_still_works(self, mocker, caplog):
        """set_allowed raises 'video system not initialized' before pygame.display.init()."""
        # The video system is up in every test: simulate set_allowed failing before it is
        mocker.patch(
            'pygame.event.set_allowed',
            side_effect=pygame.error('video system not initialized'),
        )
        game = AudioRecordingScene()

        with caplog.at_level('DEBUG', logger='game.audio'):
            manager = AudioEventManager(game=game)

        assert len(manager.proxies) == 1
        assert 'Failed to set allowed audio events: pygame not fully initialized' in caplog.text
