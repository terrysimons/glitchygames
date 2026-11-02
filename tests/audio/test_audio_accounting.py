"""Tests for per-frame audio accounting: measured pieces, the entry cap and the compile log."""

import pytest

from glitchygames.audio.accounting import AudioAccountant, AudioFrameAccount, CompileRecord


def _counter_reading(mocker, readings):
    return mocker.patch('glitchygames.clock.raw_counter_ns', side_effect=list(readings))


def test_measure_reads_the_raw_counter_twice_and_records_microseconds(mocker):
    """Measure reads the raw counter twice and records microseconds."""
    counter = _counter_reading(mocker, [1_000_000, 3_500_000])
    accountant = AudioAccountant()

    with accountant.measure('decode', 'slap'):
        pass

    assert counter.call_count == 2
    account = accountant.take_frame()
    assert account.audio_work == (('decode', 'slap', 2500),)
    assert account.audio_seconds == pytest.approx(0.0025)


def test_take_frame_returns_and_resets():
    """Take frame returns the frame's account and resets it."""
    accountant = AudioAccountant()
    with accountant.measure('cache_read', 'coin'):
        pass

    first = accountant.take_frame()
    second = accountant.take_frame()

    assert len(first.audio_work) == 1
    assert second == AudioFrameAccount(audio_seconds=0.0, audio_work=())


def test_frame_account_caps_entries_and_sums_the_rest(mocker):
    """Forty measured pieces give 32 entries; the last sums the rest into other."""
    _counter_reading(mocker, [value for index in range(40) for value in (0, (index + 1) * 1000)])
    accountant = AudioAccountant()
    for index in range(40):
        with accountant.measure('live_chunk', f'piece-{index}'):
            pass

    account = accountant.take_frame()

    assert len(account.audio_work) == 32
    assert account.audio_work[0] == ('live_chunk', 'piece-0', 1)
    assert account.audio_work[30] == ('live_chunk', 'piece-30', 31)
    # Pieces 31 to 39 lasted 32 to 40 microseconds each
    assert account.audio_work[-1] == ('other', '', sum(range(32, 41)))
    assert account.audio_seconds == pytest.approx(sum(range(1, 41)) / 1_000_000)


def test_exactly_thirty_two_pieces_are_all_kept(mocker):
    """Thirty-two pieces fit without an other entry."""
    _counter_reading(mocker, [value for _ in range(32) for value in (0, 1000)])
    accountant = AudioAccountant()
    for index in range(32):
        with accountant.measure('compile', f'piece-{index}'):
            pass

    account = accountant.take_frame()

    assert len(account.audio_work) == 32
    assert account.audio_work[-1] == ('compile', 'piece-31', 1)


def test_a_piece_that_raises_is_still_recorded():
    """A piece of work that raises is still measured."""
    accountant = AudioAccountant()

    def fail_inside_the_measure() -> None:
        with accountant.measure('decode', 'broken'):
            message = 'boom'
            raise RuntimeError(message)

    with pytest.raises(RuntimeError):
        fail_inside_the_measure()

    assert accountant.take_frame().audio_work[0][:2] == ('decode', 'broken')


def test_compiles_are_logged_with_their_frame_and_setup_flag(mocker):
    """A compile record carries the frame number, milliseconds and whether it was setup."""
    _counter_reading(mocker, [0, 2_000_000, 0, 1_500_000])
    accountant = AudioAccountant()
    assert accountant.frame_number is None
    assert accountant.setup_mode is True  # compiles before the first logic frame are setup

    with accountant.measure('compile', 'coin'):
        pass
    accountant.setup_mode = False
    accountant.frame_number = 30
    with accountant.measure('decode', 'slap'):
        pass

    assert accountant.compile_log == (
        CompileRecord(frame_number=None, name='coin', milliseconds=2.0, during_setup=True),
        CompileRecord(frame_number=30, name='slap', milliseconds=1.5, during_setup=False),
    )


def test_other_kinds_are_not_compile_records():
    """Live chunks and cache reads are accounted but are not compiles."""
    accountant = AudioAccountant()
    with accountant.measure('live_chunk', 'engine'), accountant.measure('cache_read', 'coin'):
        pass

    assert accountant.compile_log == ()
    assert len(accountant.take_frame().audio_work) == 2


def test_the_compile_log_keeps_the_last_eight():
    """The compile log is bounded to the last eight records."""
    accountant = AudioAccountant()
    for index in range(12):
        with accountant.measure('compile', f'sound-{index}'):
            pass

    assert [record.name for record in accountant.compile_log] == [
        f'sound-{index}' for index in range(4, 12)
    ]
    accountant.take_frame()
    assert len(accountant.compile_log) == 8  # taking a frame does not clear the log


def _compile_lasting(accountant, mocker, *, name, milliseconds, kind='compile'):
    _counter_reading(mocker, [0, round(milliseconds * 1_000_000)])
    with accountant.measure(kind, name):
        pass


def test_compiles_are_counted_apart_for_setup_and_gameplay(mocker):
    """Setup and gameplay compiles (and decodes) each get their count and milliseconds."""
    accountant = AudioAccountant()
    _compile_lasting(accountant, mocker, name='coin', milliseconds=2.0)
    _compile_lasting(accountant, mocker, name='slap', milliseconds=1.0, kind='decode')
    accountant.setup_mode = False
    accountant.frame_number = 12
    _compile_lasting(accountant, mocker, name='blip', milliseconds=4.0)
    _compile_lasting(accountant, mocker, name='coin', milliseconds=0.5, kind='cache_read')

    assert accountant.setup_compile_count == 2
    assert accountant.setup_compile_milliseconds == pytest.approx(3.0)
    assert accountant.gameplay_compile_count == 1
    assert accountant.gameplay_compile_milliseconds == pytest.approx(4.0)
    assert accountant.compile_count == 3
    assert accountant.gameplay_compiles == (
        CompileRecord(frame_number=12, name='blip', milliseconds=4.0, during_setup=False),
    )


def test_the_gameplay_compile_list_keeps_the_last_thirty_two(mocker):
    """Only the most recent 32 gameplay compiles are kept by name; the counts go on."""
    accountant = AudioAccountant()
    accountant.setup_mode = False
    for index in range(40):
        _compile_lasting(accountant, mocker, name=f'sound-{index}', milliseconds=1.0)

    assert accountant.gameplay_compile_count == 40
    assert len(accountant.gameplay_compiles) == 32
    assert accountant.gameplay_compiles[0].name == 'sound-8'


def test_a_setup_tally_gives_its_total_and_slowest_sounds_once(mocker):
    """take_setup_compiles returns the setup's total and its three slowest, then starts afresh."""
    accountant = AudioAccountant()
    for name, milliseconds in (('a', 5.0), ('b', 30.0), ('c', 1.0), ('d', 20.0), ('e', 10.0)):
        _compile_lasting(accountant, mocker, name=name, milliseconds=milliseconds)

    total_milliseconds, slowest = accountant.take_setup_compiles()

    assert total_milliseconds == pytest.approx(66.0)
    assert [record.name for record in slowest] == ['b', 'd', 'e']
    assert accountant.take_setup_compiles() == (0.0, ())
