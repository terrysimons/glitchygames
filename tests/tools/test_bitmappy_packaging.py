"""Tests for Bitmappy's PyInstaller packaging: the frozen entry point and bitmappy.spec."""

import runpy
from pathlib import Path

ENTRY_POINT_PATH = Path('scripts/bitmappy_entry.py')


def test_entry_point_calls_freeze_support_before_starting_bitmappy(mocker):
    """freeze_support() runs before Bitmappy starts (and parses its arguments).

    In the frozen app, multiprocessing starts child processes (the AI worker, the resource
    tracker) by re-running this executable with its own arguments; freeze_support() must
    run them and exit before Bitmappy's argument parser sees those arguments.
    """
    call_order = mocker.Mock()
    mocker.patch('multiprocessing.freeze_support', call_order.freeze_support)
    mocker.patch('glitchygames.bitmappy.main', call_order.main)

    runpy.run_path(str(ENTRY_POINT_PATH), run_name='__main__')

    assert [call[0] for call in call_order.mock_calls] == ['freeze_support', 'main']
