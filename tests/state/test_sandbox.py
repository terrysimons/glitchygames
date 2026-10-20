"""The saves door (glitchygames/state/sandbox.py)."""

from __future__ import annotations

import pytest

from glitchygames.live_sources import LiveSources
from glitchygames.sources import install_sources
from glitchygames.state import SaveManager, SaveNotFoundError
from glitchygames.state.sandbox import SandboxSaves, open_saves, save_namespace_snapshot


def test_live_open_saves_is_a_save_manager(tmp_path, mocker):
    """Live play opens a real SaveManager for the app name."""
    mocker.patch('glitchygames.state.manager.get_save_directory', return_value=tmp_path)
    saves = open_saves(app_name='demo')
    assert isinstance(saves, SaveManager)
    assert saves.app_name == 'demo'


def test_snapshot_holds_every_slot_envelope(tmp_path):
    """A snapshot of a real store holds each slot's full envelope."""
    saves = SaveManager(app_name='demo', save_dir=tmp_path)
    saves.save('high_scores', {'scores': [{'score': 900}]})
    snapshot = save_namespace_snapshot(saves=saves)
    assert snapshot['high_scores']['data'] == {'scores': [{'score': 900}]}


def test_sandbox_reads_the_snapshot_and_discards_writes(tmp_path):
    """A sandbox reads its snapshot; its writes never reach the disk."""
    saves = SaveManager(app_name='demo', save_dir=tmp_path)
    saves.save('high_scores', {'scores': [{'score': 900}]})
    sandbox = SandboxSaves(app_name='demo', envelopes=save_namespace_snapshot(saves=saves))
    assert sandbox.load('high_scores') == {'scores': [{'score': 900}]}
    sandbox.save('high_scores', {'scores': [{'score': 800}]})
    assert sandbox.load('high_scores') == {'scores': [{'score': 800}]}
    assert saves.load('high_scores') == {'scores': [{'score': 900}]}  # the disk is untouched


def test_snapshot_of_a_sandbox_is_a_copy_of_its_envelopes():
    """Changing a snapshot of a sandbox does not change the sandbox."""
    sandbox = SandboxSaves(app_name='demo', envelopes={'slot': {'data': {'value': 1}}})
    snapshot = save_namespace_snapshot(saves=sandbox)
    snapshot['slot']['data']['value'] = 2
    assert sandbox.load('slot') == {'value': 1}


def test_sandbox_missing_slot_raises_like_the_real_store():
    """Loading a missing slot raises SaveNotFoundError, as SaveManager does."""
    sandbox = SandboxSaves(app_name='demo', envelopes={})
    with pytest.raises(SaveNotFoundError):
        sandbox.load('high_scores')
    assert not sandbox.exists('high_scores')


def test_sandbox_delete_of_a_missing_slot_raises_like_the_real_store(tmp_path):
    """Deleting a missing slot raises SaveNotFoundError in both stores."""
    saves = SaveManager(app_name='demo', save_dir=tmp_path)
    with pytest.raises(SaveNotFoundError):
        saves.delete('high_scores')
    sandbox = SandboxSaves(app_name='demo', envelopes={})
    with pytest.raises(SaveNotFoundError):
        sandbox.delete('high_scores')


def test_sandbox_delete_removes_the_slot():
    """Deleting a slot removes it from the sandbox."""
    sandbox = SandboxSaves(app_name='demo', envelopes={'slot': {'data': {'value': 1}}})
    assert sandbox.exists('slot')
    sandbox.delete('slot')
    assert not sandbox.exists('slot')


def test_live_sources_remember_opened_namespaces(tmp_path, mocker):
    """LiveSources remembers each opened store by namespace (for recording)."""
    mocker.patch('glitchygames.state.manager.get_save_directory', return_value=tmp_path)
    sources = LiveSources(random_seed=1)
    install_sources(sources=sources)
    open_saves(app_name='demo')
    assert list(sources.opened_save_namespaces) == ['demo']


def test_live_sources_return_the_already_opened_store(tmp_path, mocker):
    """Opening a namespace twice returns the same store."""
    mocker.patch('glitchygames.state.manager.get_save_directory', return_value=tmp_path)
    sources = LiveSources(random_seed=1)
    install_sources(sources=sources)
    assert open_saves(app_name='demo') is open_saves(app_name='demo')
