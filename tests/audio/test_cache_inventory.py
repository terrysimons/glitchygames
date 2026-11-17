"""Tests for the sound cache's inventory and clearing (audio/cache_inventory.py).

plans/2026-11-14-sound-cache-on-first-use.md, decision 8: the cache's operations are an engine
API that GG Sound Studio's panel, the commands and the tests share.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from glitchygames.audio import cache_inventory, engine
from glitchygames.audio.cache_inventory import clear, fill, inventory, verify
from glitchygames.audio.disk_cache import DiskSoundCache, sounds_directory

RATE = 44100
# The render version these tests take as current, whatever the real one is, so two older ones
# exist (the real one is 1)
CURRENT = 5


@pytest.fixture(autouse=True)
def current_render_version(monkeypatch):
    """Make CURRENT the render version the inventory and a game's start take as current."""
    monkeypatch.setattr(cache_inventory, 'AUDIO_RENDER_VERSION', CURRENT)
    monkeypatch.setattr(engine, 'AUDIO_RENDER_VERSION', CURRENT)


def _write_sounds(root: Path, *, game: str, version: int, count: int, frames: int = 100) -> None:
    """Write ``count`` sounds into a game's folder for a render version, as a game would."""
    cache = DiskSoundCache(
        directory=sounds_directory(root=root, game=game, render_version=version),
        limit_bytes=64 * 1024 * 1024,
    )
    for index in range(count):
        cache.write(
            identity_key=f'{index:02x}' + 'a' * 30,
            samples_int16=np.zeros(frames, dtype=np.int16),
            peak=0.5,
            sample_rate=RATE,
        )


def test_an_empty_or_missing_root_holds_nothing(tmp_path):
    """No root, or an empty one: no folders, no bytes; the root may be given as text."""
    assert inventory(root=str(tmp_path / 'nowhere')).folders == ()
    assert inventory(root=tmp_path).total_bytes == 0


def test_every_games_folders_are_listed_with_their_sounds_and_bytes(tmp_path):
    """A folder per game and render version; sizes are the sound files' own."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=3)
    _write_sounds(tmp_path, game='mr_muncher', version=CURRENT, count=2, frames=1000)

    found = inventory(root=tmp_path)

    assert [(folder.game, folder.sound_count) for folder in found.folders] == [
        ('clockwork_keep', 3),
        ('mr_muncher', 2),
    ]
    sizes = {
        folder.game: sum(path.stat().st_size for path in folder.path.rglob('*.wav'))
        for folder in found.folders
    }
    assert {folder.game: folder.size_bytes for folder in found.folders} == sizes
    assert found.total_bytes == sum(sizes.values())


def test_an_older_render_version_is_stale_and_a_newer_one_is_not(tmp_path):
    """Older folders can only be an older engine's; a newer one may be another engine's."""
    for version in (CURRENT - 1, CURRENT, CURRENT + 1):
        _write_sounds(tmp_path, game='clockwork_keep', version=version, count=1)

    found = inventory(root=tmp_path)

    assert [(folder.render_version, folder.stale) for folder in found.folders] == [
        (CURRENT - 1, True),
        (CURRENT, False),
        (CURRENT + 1, False),
    ]
    assert found.stale_bytes == found.folders[0].size_bytes


def test_what_is_not_a_cache_folder_is_left_out(tmp_path):
    """Only <root>/<game>/sounds/<render version>/ counts: stray files and folders do not."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=1)
    (tmp_path / 'notes.txt').write_text('mine')
    (tmp_path / 'clockwork_keep' / 'sounds' / 'drafts').mkdir()
    (tmp_path / 'other' / 'things').mkdir(parents=True)
    (tmp_path / 'listening' / 'drafts').mkdir(parents=True)

    found = inventory(root=tmp_path)

    assert [folder.game for folder in found.folders] == ['clockwork_keep']
    assert found.listening == ()
    clear(root=tmp_path, listening=True)
    assert (tmp_path / 'listening' / 'drafts').is_dir()


def test_clearing_the_stale_versions_removes_only_older_folders_and_says_what_it_freed(tmp_path):
    """Every game's older versions go; the current and newer stay; the report adds up."""
    for version in (CURRENT - 2, CURRENT - 1, CURRENT, CURRENT + 1):
        _write_sounds(tmp_path, game='clockwork_keep', version=version, count=2)
    _write_sounds(tmp_path, game='mr_muncher', version=CURRENT - 1, count=1)
    stale_bytes = inventory(root=tmp_path).stale_bytes

    cleared = clear(root=tmp_path, stale_only=True)

    assert (cleared.removed_sounds, cleared.freed_bytes) == (5, stale_bytes)
    remaining = [
        (folder.game, folder.render_version) for folder in inventory(root=tmp_path).folders
    ]
    assert remaining == [('clockwork_keep', CURRENT), ('clockwork_keep', CURRENT + 1)]


def test_clearing_one_game_leaves_the_others(tmp_path):
    """One game's folder goes, all its versions; the other games' stay."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=2)
    _write_sounds(tmp_path, game='mr_muncher', version=CURRENT, count=1)

    cleared = clear(root=tmp_path, game='clockwork_keep')

    assert cleared.removed_sounds == 2
    assert [folder.game for folder in inventory(root=tmp_path).folders] == ['mr_muncher']
    assert not (tmp_path / 'clockwork_keep').exists()


def test_clearing_everything_leaves_the_root_and_nothing_of_the_cache(tmp_path):
    """The root may be a folder of the player's: only cache folders go, never stray files."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=2)
    _write_sounds(tmp_path, game='mr_muncher', version=CURRENT - 1, count=1)
    (tmp_path / 'notes.txt').write_text('mine')

    cleared = clear(root=tmp_path)

    assert cleared.removed_sounds == 3
    assert inventory(root=tmp_path).folders == ()
    assert (tmp_path / 'notes.txt').read_text() == 'mine'


def test_clearing_a_missing_root_removes_nothing(tmp_path):
    """Nothing there, nothing removed, no error."""
    assert clear(root=tmp_path / 'nowhere').removed_sounds == 0


def test_a_games_start_removes_its_older_render_versions(tmp_path, monkeypatch):
    """Pruning looks only at the current version's folder; a start sweeps the older ones."""
    from glitchygames.audio.disk_cache import SOUND_CACHE_ROOT_VARIABLE
    from glitchygames.audio.engine import AudioEngine
    from glitchygames.audio.library import CacheMode
    from glitchygames.audio.voices import ChannelPartition

    monkeypatch.setenv(SOUND_CACHE_ROOT_VARIABLE, str(tmp_path))
    for version in (CURRENT - 1, CURRENT, CURRENT + 1):
        _write_sounds(tmp_path, game='clockwork_keep', version=version, count=1)
    _write_sounds(tmp_path, game='mr_muncher', version=CURRENT - 1, count=1)

    AudioEngine(
        partition=ChannelPartition(live=(), library=(), legacy_count=0),
        cache=CacheMode.DISK,
        game_name='clockwork_keep',
    )

    left = [(folder.game, folder.render_version) for folder in inventory(root=tmp_path).folders]
    assert left == [
        ('clockwork_keep', CURRENT),
        ('clockwork_keep', CURRENT + 1),
        ('mr_muncher', CURRENT - 1),  # another game's: its own start sweeps it
    ]


def _a_sound_file(directory: Path) -> Path:
    """A good cache file, written as a game writes one.

    Returns:
        Its path.
    """
    _write_sounds(directory, game='clockwork_keep', version=CURRENT, count=1)
    (path,) = directory.rglob('*.wav')
    return path


def test_verifying_good_files_finds_nothing_damaged(tmp_path):
    """Every sound file is read back; lock and temporary files are not sounds."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=3)
    _write_sounds(tmp_path, game='mr_muncher', version=CURRENT - 1, count=1)
    next(tmp_path.rglob('*.wav')).with_suffix('.wav.lock').write_bytes(b'')

    report = verify(root=tmp_path)

    assert (report.checked, report.damaged) == (4, ())


def test_verifying_reports_each_damaged_file_and_why(tmp_path):
    """Damaged, not deleted: a read deletes and recompiles one, but silently; this says so."""
    import struct

    good = _a_sound_file(tmp_path)
    data = good.read_bytes()
    cut = good.with_name('cut.wav')
    cut.write_bytes(data[: len(data) - 10])
    not_a_wave = good.with_name('text.wav')
    not_a_wave.write_bytes(b'hello, not audio')
    stereo = good.with_name('stereo.wav')
    # The fmt chunk's channel count (after RIFF, WAVE, the chunk header and the format tag)
    stereo.write_bytes(data[:22] + struct.pack('<H', 2) + data[24:])
    no_peak = good.with_name('no-peak.wav')
    no_peak.write_bytes(data.replace(b'gGpk', b'xxxx'))
    no_format = good.with_name('no-format.wav')
    no_format.write_bytes(data.replace(b'fmt ', b'xxxx'))
    no_data = good.with_name('no-data.wav')
    no_data.write_bytes(data.replace(b'data', b'xxxx'))
    # A data chunk one byte short of whole samples (its size and its bytes both one less)
    data_at = data.index(b'data')
    (size,) = struct.unpack('<I', data[data_at + 4 : data_at + 8])
    half_sample = good.with_name('half-sample.wav')
    half_sample.write_bytes(
        data[: data_at + 4] + struct.pack('<I', size - 1) + data[data_at + 8 : -1]
    )

    report = verify(root=tmp_path)

    reasons = {damaged.path.name: damaged.reason for damaged in report.damaged}
    assert report.checked == 8
    assert set(reasons) == {
        'cut.wav',
        'text.wav',
        'stereo.wav',
        'no-peak.wav',
        'no-format.wav',
        'no-data.wav',
        'half-sample.wav',
    }
    assert 'past the end' in reasons['cut.wav']
    assert 'not a WAV' in reasons['text.wav']
    assert 'mono' in reasons['stereo.wav']
    assert 'peak' in reasons['no-peak.wav']
    assert reasons['no-format.wav'] == 'no format chunk'
    assert reasons['no-data.wav'] == 'no data chunk'
    assert 'whole 16-bit samples' in reasons['half-sample.wav']
    assert all(path.exists() for path in (cut, not_a_wave, stereo, no_peak))


def test_verifying_a_missing_root_checks_nothing(tmp_path):
    """Nothing there, nothing checked."""
    assert verify(root=tmp_path / 'nowhere').checked == 0


def test_verifying_reports_a_file_that_cannot_be_read(tmp_path, mocker):
    """An unreadable file is damaged too, with the system's reason."""
    from pathlib import Path

    unreadable = _a_sound_file(tmp_path)
    real_read = Path.read_bytes

    def read_bytes(path):
        if path == unreadable:
            raise PermissionError(13, 'Permission denied')
        return real_read(path)

    mocker.patch.object(Path, 'read_bytes', autospec=True, side_effect=read_bytes)

    report = verify(root=tmp_path)

    assert [(damaged.path, damaged.reason) for damaged in report.damaged] == [
        (unreadable, 'cannot be read: Permission denied')
    ]


def test_verifying_one_game_checks_only_its_folders(tmp_path):
    """``game=`` reads that game's files, every render version of them, and no other game's."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=2)
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT - 1, count=1)
    _write_sounds(tmp_path, game='paddleslap', version=CURRENT, count=3)
    (other,) = (tmp_path / 'paddleslap').rglob('00*.wav')
    other.write_bytes(b'not a sound')

    report = verify(root=tmp_path, game='clockwork_keep')

    assert (report.checked, report.damaged) == (3, ())


def _write_listening(root: Path, *, version: int, count: int) -> list[Path]:
    """Write ``count`` plain WAV files into the listening folder for a render version.

    Returns:
        Their paths.
    """
    from glitchygames.audio.offline import write_wave_file

    directory = root / 'listening' / str(version) / 'pipes'
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(count):
        path = directory / f'demo_{index}.wav'
        write_wave_file(path, np.zeros(100), sample_rate=RATE, sample_format='int16')
        paths.append(path)
    return paths


def test_the_listening_folders_are_listed_apart_from_the_games(tmp_path):
    """Each render version's listening folder, its files and bytes; an older one stale."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=1)
    current = _write_listening(tmp_path, version=CURRENT, count=2)
    _write_listening(tmp_path, version=CURRENT - 1, count=1)

    found = inventory(root=tmp_path)

    assert [folder.game for folder in found.folders] == ['clockwork_keep']
    assert [
        (folder.render_version, folder.file_count, folder.stale) for folder in found.listening
    ] == [(CURRENT - 1, 1, True), (CURRENT, 2, False)]
    assert found.listening[1].size_bytes == sum(path.stat().st_size for path in current)
    assert found.listening[1].path == tmp_path / 'listening' / str(CURRENT)


def test_clearing_the_games_leaves_the_listening_files(tmp_path):
    """Only clear(listening=True) removes them (the plan's rule)."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=1)
    _write_listening(tmp_path, version=CURRENT, count=2)

    clear(root=tmp_path)

    assert inventory(root=tmp_path).folders == ()
    assert len(inventory(root=tmp_path).listening) == 1


@pytest.mark.parametrize(('stale_only', 'left'), [(False, []), (True, [CURRENT])])
def test_clearing_the_listening_files_leaves_the_games(tmp_path, stale_only, left):
    """listening=True removes listening folders (with stale_only, only the older ones)."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=1)
    _write_listening(tmp_path, version=CURRENT, count=2)
    _write_listening(tmp_path, version=CURRENT - 1, count=1)

    report = clear(root=tmp_path, listening=True, stale_only=stale_only)

    found = inventory(root=tmp_path)
    assert [folder.render_version for folder in found.listening] == left
    assert [folder.game for folder in found.folders] == ['clockwork_keep']
    assert report.removed_sounds == (1 if stale_only else 3)


def test_clearing_one_games_listening_files_is_refused(tmp_path):
    """The listening files are no game's."""
    with pytest.raises(ValueError, match='no game'):
        clear(root=tmp_path, game='clockwork_keep', listening=True)


def test_verifying_leaves_the_listening_files_out(tmp_path):
    """They are plain WAVs, not cache files (no peak chunk): never reported as damaged."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=1)
    _write_listening(tmp_path, version=CURRENT, count=2)

    report = verify(root=tmp_path)

    assert (report.checked, report.damaged) == (1, ())


FIXTURE_SOUNDS = Path(__file__).parent / 'fixtures' / 'sounds'


def _effect(name: str, frequency: float):
    """A short one-tone effect.

    Returns:
        The effect.
    """
    from glitchygames.audio.effects import Effect, Tone
    from glitchygames.audio.synth import Envelope, Waveform

    envelope = Envelope(attack=0.001, decay=0.0, sustain_level=1.0, release=0.01)
    tone = Tone(waveform=Waveform.SINE, start_frequency=frequency, duration=0.02, envelope=envelope)
    return Effect(name=name, tones=(tone,))


def _declared_sounds():
    """A game's SOUNDS: two effects, a live instrument and a recorded file.

    Returns:
        The sources.
    """
    from glitchygames.audio.instrument import Instrument

    return (
        _effect('blip', 440.0),
        _effect('bloop', 220.0),
        Instrument(wave='sine', live=True),  # compiles nothing
        f'{FIXTURE_SOUNDS / "extras.toml"}#slap',  # a recorded file: never cached
    )


# The CRT power-on's distinct sounds: both backgrounds' schedules (click, degauss, whine, static,
# and the bars tone or the channel 3 hiss)
POWER_ON_SOUNDS = 6


def test_fill_writes_a_games_sounds_and_the_power_ons_into_its_folder(tmp_path):
    """So even a first launch reads every sound (the slow machine's first-launch stall)."""
    from glitchygames.audio.library import ENGINE_SOUND_CACHE

    ENGINE_SOUND_CACHE.clear()

    report = fill(root=tmp_path, game_name='clockwork_keep', sounds=_declared_sounds())

    folder = sounds_directory(root=tmp_path, game='clockwork_keep', render_version=CURRENT)
    assert report.folder == folder
    assert (report.written, report.already_kept, report.skipped) == (2 + POWER_ON_SOUNDS, 0, 2)
    assert len(list(folder.rglob('*.wav'))) == 2 + POWER_ON_SOUNDS


def test_a_second_fill_writes_nothing(tmp_path):
    """Idempotent: what is already kept is counted, not written again."""
    fill(root=tmp_path, game_name='clockwork_keep', sounds=_declared_sounds())

    again = fill(root=tmp_path, game_name='clockwork_keep', sounds=_declared_sounds())

    assert (again.written, again.already_kept) == (0, 2 + POWER_ON_SOUNDS)


def test_fill_writes_sounds_the_process_compiled_already(tmp_path):
    """A sound the process compiled already is written from its samples (GG Sound Studio's case).

    The process shares compiled samples, so the library never compiles such a sound again, so
    never writes it.
    """
    from glitchygames.audio.engine import AudioEngine
    from glitchygames.audio.startup import StartupSounds
    from glitchygames.audio.voices import ChannelPartition

    StartupSounds(  # compiled into the process store, on the memory cache: no file
        audio=AudioEngine(partition=ChannelPartition(live=(), library=(), legacy_count=0)),
        sources=_declared_sounds(),
    ).finish()

    report = fill(root=tmp_path, game_name='clockwork_keep', sounds=_declared_sounds())

    assert report.written == 2 + POWER_ON_SOUNDS


def test_after_a_fill_a_games_first_start_reads_every_sound(tmp_path, monkeypatch):
    """The point of fill: the start-up compile finds every declared sound on disk."""
    from glitchygames.audio.disk_cache import SOUND_CACHE_ROOT_VARIABLE
    from glitchygames.audio.engine import AudioEngine
    from glitchygames.audio.library import ENGINE_SOUND_CACHE, CacheMode
    from glitchygames.audio.startup import StartupSounds
    from glitchygames.audio.voices import ChannelPartition

    fill(root=tmp_path, game_name='clockwork_keep', sounds=_declared_sounds())
    ENGINE_SOUND_CACHE.clear()  # a new process
    monkeypatch.setenv(SOUND_CACHE_ROOT_VARIABLE, str(tmp_path))
    audio = AudioEngine(
        partition=ChannelPartition(live=(), library=(), legacy_count=0),
        cache=CacheMode.DISK,
        game_name='clockwork_keep',
    )

    StartupSounds(audio=audio, sources=_declared_sounds()).finish()

    statistics = audio.sounds.statistics()
    assert (statistics.disk_hits, statistics.disk_writes) == (2, 0)
