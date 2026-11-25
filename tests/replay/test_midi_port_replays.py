"""A replay opens the MIDI ports its recording named, never the replaying command's.

``--midi-input`` and ``--midi-output`` are recorded options (``glitchygames/events/midi.py``);
a replay takes the recording's, and a recording made before they existed names none, so a replay
of it opens none whatever its command line or the game's defaults say. These run the
departure/arrival session of tests/world/test_gameplay_recording.py in this process.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.input.devices import MidiPortInfo, ReplayDeviceRegistry
from tests.replay.playback_fixtures import MALFORMED_PORT_NAMES, use_stand_in_midi_ports
from tests.replay.replay_helpers import rewrite_recording
from tests.world.test_gameplay_recording import (
    RUN_ENGINE_ARGUMENTS,
    DepartureRecordedScene,
    Script,
    build_engine,
    engine_run_environment,
)
from tests.world.test_gameplay_replay import record_session, replay_session

if TYPE_CHECKING:
    from pathlib import Path

KEYS = MidiPortInfo(interface='CoreMIDI', name='Keys', is_input=True, is_output=False)
PADS = MidiPortInfo(interface='CoreMIDI', name='Pads', is_input=True, is_output=False)


def replay_with_arguments(*, recording_path: Path, mocker, arguments: tuple[str, ...]):
    """Replay headless with extra arguments; return the engine and its exit code."""
    with engine_run_environment(mocker):
        Script.action, Script.action_frame = None, 1
        engine = build_engine(
            scene_class=DepartureRecordedScene,
            arguments=(
                *RUN_ENGINE_ARGUMENTS,
                '--replay-trace',
                str(recording_path),
                '--headless',
                *arguments,
            ),
        )
        with pytest.raises(SystemExit) as exit_info:
            engine.start()
    return engine, exit_info.value.code


@pytest.mark.draws_frames
def test_a_replay_opens_the_recorded_port_whatever_its_command_names(mocker, tmp_path, caplog):
    """Recorded with --midi-input Keys, replayed with --midi-input Pads: Keys opens, no warning."""
    use_stand_in_midi_ports(mocker=mocker, midi_ports=[PADS, KEYS])
    recording_path = record_session(
        tmp_path=tmp_path, mocker=mocker, extra_arguments=('--midi-input', 'Keys')
    )
    caplog.clear()

    with caplog.at_level('WARNING', logger='game.midi'):
        engine, _exit_code = replay_with_arguments(
            recording_path=recording_path, mocker=mocker, arguments=('--midi-input', 'Pads')
        )

    assert list(engine.options['midi_input']) == ['Keys']
    assert list(engine.midi_manager.ports) == [('midi_input', 1)]
    assert [record for record in caplog.records if record.name == 'game.midi'] == []


@pytest.mark.draws_frames
def test_a_recording_that_predates_the_options_replays_with_no_midi_names(mocker, tmp_path, caplog):
    """An old header has no midi_input: --midi-input Keys on the replay asks the door nothing."""
    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)

    def forget_the_options(trace):
        trace['options'].pop('midi_input')
        trace['options'].pop('midi_output')

    rewrite_recording(recording_path=recording_path, change=forget_the_options)
    port_count = mocker.spy(ReplayDeviceRegistry, 'midi_port_count')
    caplog.clear()

    with caplog.at_level('WARNING'):
        engine, _exit_code = replay_with_arguments(
            recording_path=recording_path, mocker=mocker, arguments=('--midi-input', 'Keys')
        )

    assert engine.options['midi_input'] == []
    assert engine.midi_manager.ports == {}
    port_count.assert_not_called()
    assert [
        record.getMessage()
        for record in caplog.records
        if record.name in {'game.midi', 'game.input.devices'}
    ] == []


@pytest.mark.draws_frames
@pytest.mark.parametrize('option', ['midi_input', 'midi_output'])
@pytest.mark.parametrize('malformed', MALFORMED_PORT_NAMES)
def test_a_recording_with_malformed_port_names_is_refused(
    mocker, tmp_path, caplog, option, malformed
):
    """Like a malformed screen size: UNUSABLE_INPUT, named in one line, never a TypeError."""
    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    rewrite_recording(
        recording_path=recording_path,
        change=lambda trace: trace['options'].update({option: malformed}),
    )
    caplog.clear()

    with pytest.raises(SystemExit) as exit_info:
        replay_session(recording_path=recording_path, mocker=mocker)

    assert exit_info.value.code == ExitCode.UNUSABLE_INPUT
    (refusal,) = [record for record in caplog.records if 'Cannot replay' in record.getMessage()]
    assert refusal.exc_info is None


@pytest.mark.draws_frames
def test_a_recording_with_no_options_mapping_is_refused(mocker, tmp_path):
    """Refused like its malformed values, never an AttributeError."""
    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    rewrite_recording(recording_path=recording_path, change=lambda trace: trace.update(options=5))

    with pytest.raises(SystemExit) as exit_info:
        replay_session(recording_path=recording_path, mocker=mocker)

    assert exit_info.value.code == ExitCode.UNUSABLE_INPUT


@pytest.mark.draws_frames
def test_a_recorded_null_names_no_port(mocker, tmp_path):
    """A game may default its option to None: no ports, as live play takes it."""
    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    rewrite_recording(
        recording_path=recording_path,
        change=lambda trace: trace['options'].update(midi_input=None),
    )

    engine, exit_code = replay_with_arguments(
        recording_path=recording_path, mocker=mocker, arguments=('--midi-input', 'Keys')
    )

    assert exit_code == ExitCode.SUCCESS
    assert engine.options['midi_input'] == []
    assert engine.midi_manager.ports == {}
