"""The startup options block: a run's options, pretty printed, paths shown, nothing secret.

The engine logs it at CRITICAL once per start (``GameEngine._log_the_startup_options``; its
engine tests are tests/engine/test_engine_lifecycle.py's ``TestStartupOptions``). These test how
the block reads: sorted names, ``name = value`` aligned, nested values indented, paths relative
to the project root inside it and absolute outside it, and any option whose name suggests a key,
token, secret, password or credential shown as ``<redacted>`` (the owner and the coordinator,
2026-10-28).
"""

from __future__ import annotations

import pytest

from glitchygames.engine import game_engine as game_engine_module
from glitchygames.engine.game_engine import (
    OPTIONS_BLOCK_INDENT,
    REDACTED_OPTION_VALUE,
    displayed_options,
    displayed_path,
    is_secret_option_name,
    options_block_lines,
    startup_options_block,
)

# A stand-in for a secret value: never shown
VALUE_NEVER_SHOWN = 'sk-not-a-real-value'
# A pyproject.toml that makes its directory a project root
PROJECT_PYPROJECT = '[project]\nname = "a-project"\n\n[tool.glitchygames]\n'


@pytest.mark.parametrize(
    'name',
    ['api_key', 'OPENAI_API_KEY', 'auth_token', 'client_secret', 'Password', 'credentials_file'],
)
def test_a_name_that_suggests_a_secret_is_one(name):
    """key, token, secret, password and credential, in any case, anywhere in the name."""
    assert is_secret_option_name(name=name)


@pytest.mark.parametrize('name', ['log_level', 'replay_trace', 'font_name', 'random_seed'])
def test_an_ordinary_name_is_no_secret(name):
    """An option named for what it sets, with none of the parts, is shown."""
    assert not is_secret_option_name(name=name)


def test_the_lines_are_sorted_and_aligned():
    """One ``name = value`` per line, sorted by name, the ``=`` in one column, values by repr."""
    lines = options_block_lines(
        options={'windowed': True, 'a': None, 'font_name': 'Vera'}, indent=''
    )

    assert lines == ['a         = None', "font_name = 'Vera'", 'windowed  = True']


def test_a_nested_mapping_is_indented_below_its_name():
    """A mapping's name stands alone; its own lines, sorted and aligned, go one level deeper."""
    lines = options_block_lines(options={'outer': {'b': 2, 'a': 1}, 'z': 0}, indent='')

    assert lines == [
        'outer =',
        f'{OPTIONS_BLOCK_INDENT}a = 1',
        f'{OPTIONS_BLOCK_INDENT}b = 2',
        'z     = 0',
    ]


def test_an_empty_mapping_stays_on_its_line():
    """An empty mapping has no lines of its own: it is shown as ``{}``."""
    assert options_block_lines(options={'nothing': {}}, indent='') == ['nothing = {}']


def test_a_long_value_continues_under_its_first_line():
    """A value too long for one line (pprint's) goes on below, under where it started."""
    long_list = [f'item-number-{index}' for index in range(20)]

    lines = options_block_lines(options={'many': long_list}, indent='')

    assert len(lines) > 1
    assert lines[0].startswith("many = ['item-number-0',")
    assert all(line.startswith(' ' * len('many = ')) for line in lines[1:])


@pytest.mark.parametrize(
    'value', [VALUE_NEVER_SHOWN, None, {'nested': VALUE_NEVER_SHOWN}], ids=['text', 'none', 'map']
)
def test_a_secret_option_is_redacted_whatever_its_value(value):
    """Never part of the value, and not even whether it was given (None)."""
    lines = options_block_lines(options={'api_key': value}, indent='')

    assert lines == [f'api_key = {REDACTED_OPTION_VALUE}']


def test_a_secret_option_nested_in_another_is_redacted():
    """Redaction looks at every depth's names."""
    lines = options_block_lines(options={'service': {'token': VALUE_NEVER_SHOWN}}, indent='')

    assert lines == ['service =', f'{OPTIONS_BLOCK_INDENT}token = {REDACTED_OPTION_VALUE}']


def test_a_path_inside_the_project_is_shown_from_its_root(tmp_path):
    """The stored-path rule: relative to the project root, POSIX-style."""
    project_root = tmp_path / 'project'
    (project_root / 'recordings').mkdir(parents=True)
    (project_root / 'pyproject.toml').write_text(PROJECT_PYPROJECT, encoding='utf-8')

    shown = displayed_path(
        path=project_root / 'recordings' / 'run.jsonl.gz', project_root=project_root
    )

    assert shown == 'recordings/run.jsonl.gz'


def test_a_path_outside_the_project_is_shown_absolute(tmp_path):
    """Not the stored path's file name only: the whole path, resolved."""
    project_root = tmp_path / 'project'
    project_root.mkdir()
    (project_root / 'pyproject.toml').write_text(PROJECT_PYPROJECT, encoding='utf-8')
    elsewhere = tmp_path / 'scratch' / 'run.jsonl.gz'

    shown = displayed_path(path=elsewhere, project_root=project_root)

    assert shown == str(elsewhere.resolve())


def test_a_path_with_no_project_is_shown_absolute(tmp_path):
    """With no project root, every path is shown absolute."""
    path = tmp_path / 'run.jsonl.gz'

    assert displayed_path(path=path, project_root=None) == str(path.resolve())


def test_the_path_options_are_displayed_and_the_others_kept(tmp_path, monkeypatch):
    """Only path options (the tools' and the engine's) change; a list of paths shows each."""
    project_root = tmp_path / 'project'
    project_root.mkdir()
    (project_root / 'pyproject.toml').write_text(PROJECT_PYPROJECT, encoding='utf-8')
    monkeypatch.chdir(project_root)
    monkeypatch.setattr(
        game_engine_module,
        'path_option_destinations',
        lambda: frozenset({'replay_trace', 'verify'}),
    )

    shown = displayed_options(
        options={
            'replay_trace': 'a/run.jsonl.gz',
            'verify': ['a/one.jsonl.gz', str(tmp_path / 'two.jsonl.gz')],
            'replay_restart_handoff': None,
            'resolution': 'a/not-a-path',
        }
    )

    assert shown == {
        'replay_trace': 'a/run.jsonl.gz',
        'verify': ['a/one.jsonl.gz', str((tmp_path / 'two.jsonl.gz').resolve())],
        'replay_restart_handoff': None,
        'resolution': 'a/not-a-path',
    }


def test_the_block_has_a_heading_then_every_option_indented(tmp_path, monkeypatch):
    """The heading names the game; each option follows, one indent in, secrets redacted."""
    monkeypatch.chdir(tmp_path)

    block = startup_options_block(
        game_name='Paddle Slap', options={'log_level': 'warning', 'api_key': VALUE_NEVER_SHOWN}
    )

    assert block.splitlines() == [
        'Options for Paddle Slap (secrets redacted):',
        f'{OPTIONS_BLOCK_INDENT}api_key   = {REDACTED_OPTION_VALUE}',
        f"{OPTIONS_BLOCK_INDENT}log_level = 'warning'",
    ]
    assert VALUE_NEVER_SHOWN not in block


def test_the_block_reads_no_environment_variable(tmp_path, monkeypatch):
    """An environment variable that looks like an option never reaches the block."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('API_KEY', VALUE_NEVER_SHOWN)

    block = startup_options_block(game_name='A Game', options={'log_level': 'warning'})

    assert VALUE_NEVER_SHOWN not in block
