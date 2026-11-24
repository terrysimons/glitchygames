"""The browser frame measurement's own parts (scripts/measure_browser_frames.py).

The measurement itself needs Chrome and the pygame-ce WebAssembly wheel, so it runs by hand
(``uv run python -m scripts.measure_browser_frames <game>``); these test what it parses and
writes.
"""

from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING

import pytest
from scripts import measure_browser_frames
from scripts.build_browser_bundle import pyscript_config
from scripts.frame_phase_probe import REPORT_MARKER
from scripts.measure_browser_frames import (
    READY_TEXT,
    add_probe_to_pyscript_files,
    chrome_command,
    console_text,
    devtools_port_from_line,
    find_chrome,
    read_devtools_port,
    report_from_console,
    summary_lines,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestDevToolsPort:
    """Where Chrome's DevTools listen, from its standard error."""

    def test_the_listening_line_gives_the_port(self):
        line = 'DevTools listening on ws://127.0.0.1:53817/devtools/browser/0b7c-uuid\n'

        assert devtools_port_from_line(line=line) == 53817

    def test_other_lines_give_none(self):
        assert devtools_port_from_line(line='[1120/0912:ERROR:gpu_init.cc] something\n') is None

    def test_reading_standard_error_skips_to_the_listening_line(self):
        errors = io.StringIO(
            'warning one\nDevTools listening on ws://127.0.0.1:9222/devtools/browser/x\nlater\n'
        )

        assert read_devtools_port(chrome_errors=errors) == 9222

    def test_chrome_ending_before_listening_is_an_error(self):
        with pytest.raises(RuntimeError, match='exited before'):
            read_devtools_port(chrome_errors=io.StringIO('crash\n'))


class TestConsole:
    """The page's console lines: their text, the report line and the ready line."""

    def test_console_text_joins_values_and_descriptions(self):
        parameters = {'args': [{'type': 'string', 'value': 'a'}, {'description': 'Object'}]}

        assert console_text(event_parameters=parameters) == 'a Object'

    def test_the_report_line_parses(self):
        assert report_from_console(text=REPORT_MARKER + '{"summary": {"frames": 3}}') == {
            'summary': {'frames': 3}
        }

    def test_any_other_line_is_not_a_report(self):
        assert report_from_console(text='game.browser - INFO - Loading') is None

    def test_the_ready_text_is_what_boot_py_says_before_the_click(self):
        """boot.py's status: f'{config["title"]}: click to play' (browser/boot.py, main)."""
        boot_source = (
            measure_browser_frames.REPOSITORY_DIRECTORY / 'browser' / 'boot.py'
        ).read_text(encoding='utf-8')

        assert f'set_status(f\'{{config["title"]}}{READY_TEXT}\')' in boot_source


class TestBundle:
    """The measurement bundle's additions to the browser bundle."""

    def test_the_probe_joins_pyscripts_files(self, tmp_path: Path):
        pyscript_path = tmp_path / 'pyscript.toml'
        pyscript_path.write_text(pyscript_config(wheel_name='pygame.whl'), encoding='utf-8')

        add_probe_to_pyscript_files(pyscript_path=pyscript_path)

        text = pyscript_path.read_text(encoding='utf-8')
        assert '"./frame_phase_probe.py" = "./frame_phase_probe.py"' in text
        assert text.count('[files]') == 1

    def test_a_pyscript_toml_without_files_is_refused(self, tmp_path: Path):
        pyscript_path = tmp_path / 'pyscript.toml'
        pyscript_path.write_text('packages = []\n', encoding='utf-8')

        with pytest.raises(RuntimeError, match=r'no \[files\] table'):
            add_probe_to_pyscript_files(pyscript_path=pyscript_path)


class TestChrome:
    """Finding and starting Chrome."""

    def test_headless_unless_headed(self, tmp_path: Path):
        headless = chrome_command(chrome='chrome', profile_directory=tmp_path, headed=False)
        headed = chrome_command(chrome='chrome', profile_directory=tmp_path, headed=True)

        assert '--headless=new' in headless
        assert '--headless=new' not in headed
        assert f'--user-data-dir={tmp_path}' in headed
        assert '--remote-debugging-port=0' in headed

    def test_find_chrome_takes_the_first_existing_path(self, tmp_path: Path):
        chrome = tmp_path / 'chrome'
        chrome.write_text('', encoding='utf-8')

        assert find_chrome(candidates=(str(tmp_path / 'missing'), str(chrome))) == str(chrome)

    def test_find_chrome_gives_none_when_nothing_is_installed(self, tmp_path: Path):
        assert find_chrome(candidates=(str(tmp_path / 'missing'),)) is None


def test_summary_lines_name_every_sprite_and_hitch():
    """The printed summary names each audited sprite and each hitch."""
    report_data = json.loads(
        json.dumps({
            'environment': {'platform': 'emscripten'},
            'surface_audit': {
                'display': {'bitsize': 32},
                'sprites': [
                    {
                        'name': 'Slot P1',
                        'dirty': 2,
                        'visible': 1,
                        'format': {'size': [164, 56], 'bitsize': 32, 'per_pixel_alpha': True},
                        'matches_display': True,
                    }
                ],
            },
            'summary': {
                'frames': 2,
                'frame_seconds': {'median': 0.001, 'p95': 0.001, 'p99': 0.001, 'max': 0.001},
                'interval_seconds': {'median': 0.016, 'p95': 0.025, 'p99': 0.025, 'max': 0.025},
                'phase_seconds': {},
                'gc_pause_seconds': {'median': 0.0, 'p95': 0.0, 'p99': 0.0, 'max': 0.0},
                'rects': {'count': {'median': 5}, 'area': {'median': 66616}},
                'sprites_blitted': {'median': 5},
                'hitches': [
                    {
                        'game_time': 1.5,
                        'interval': 0.025,
                        'frame': 0.001,
                        'slowest_phase': 'sprites_draw',
                        'slowest_phase_seconds': 0.0005,
                        'gc_seconds': 0.0,
                    }
                ],
            },
        })
    )

    text = '\n'.join(summary_lines(report_data=report_data))

    assert 'sprite Slot P1: dirty=2' in text
    assert 'Hitches (interval > 1.5x median): 1' in text
    assert 'game_time=1.500 interval=25.000' in text
