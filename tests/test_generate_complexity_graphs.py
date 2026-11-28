"""scripts/generate_complexity_graphs.py generates the docs' complexity graphs from git history.

The end-to-end tests run the real git, radon and wily on a small repository made in tmp_path
(two commits of a two-module ``glitchygames`` package), never on this repository.
"""

from __future__ import annotations

import functools
import gc
import importlib
import json
import logging
import os
import re
import sys
import threading
import types
import weakref
from typing import TYPE_CHECKING

import pytest
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from scripts import generate_complexity_graphs, mkdocs_hooks
from scripts.generate_complexity_graphs import (
    EXPLORER_DATA_NAME,
    GENERATED_FROM_NAME,
    GENERATION_LOCK_NAME,
    GRAPHS_SNIPPET_NAME,
    METRICS,
    STAGING_DIRECTORY_PREFIX,
    TOP_MODULE_COUNT,
    ComplexityGraphError,
    ComplexityGraphs,
    RadonReport,
    complexity_history,
    detached_checkout,
    generate_if_stale,
    graphs_snippet,
    join_moved_paths,
    joined_operator_data,
    main,
    measure_ranked_modules,
    measurement,
    packages_at_head,
    rank_modules,
    run_tool,
    wily_command,
    wily_revisions,
)

from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command
from glitchygames.replay.tools.performance_pages import PLOTLY_JS_URL
from tests.explorer_site import make_explorer_site

if TYPE_CHECKING:
    from pathlib import Path

# The fixture repository's wily configuration: this repository's operators, its one package
FIXTURE_WILY_CONFIGURATION = """[wily]
path = src/glitchygames
operators = cyclomatic,maintainability,raw,halstead
"""

# The fixture package's modules: simple.py is the least complex, branchy.py the most
SIMPLE_MODULE = """def simple():
    return 1
"""
BRANCHY_MODULE = """def branchy(value):
    if value > 1:
        return 1
    if value > 2:
        return 2
    return 3
"""


def git(*, repository: Path, arguments: list[str], committed_at_second: int | None = None) -> str:
    """Run git in the fixture repository (no signing, a fixed author).

    Args:
        repository: The fixture repository.
        arguments: git's arguments.
        committed_at_second: For a commit, its author and committer time in seconds after
            2026-01-01 00:00 UTC. wily orders a graph's points by commit time, and commits made
            within one second would tie and come out in any order (the moved-module graph test
            then failed intermittently, its first point not the first commit).

    Returns:
        git's standard output.

    """
    environment = dict(os.environ)
    if committed_at_second is not None:
        commit_time = f'2026-01-01T00:00:{committed_at_second:02d}+00:00'
        environment['GIT_AUTHOR_DATE'] = commit_time
        environment['GIT_COMMITTER_DATE'] = commit_time
    completed = run_command(
        command=[
            'git',
            '-c',
            'user.name=Complexity Test',
            '-c',
            'user.email=complexity@example.com',
            '-c',
            'commit.gpgsign=false',
            *arguments,
        ],
        environment=environment,
        timeout_seconds=60.0,
        capture_output=OutputCapture.TOGETHER,
        working_directory=repository,
    )
    assert completed.returncode == 0, completed.stdout
    return completed.stdout


@pytest.fixture
def fixture_repository(tmp_path: Path) -> Path:
    """Return a git repository of two commits: the package, then a branchier module.

    Returns:
        The repository's directory.

    """
    repository = tmp_path / 'repository'
    package = repository / 'src' / 'glitchygames'
    package.mkdir(parents=True)
    git(repository=repository, arguments=['init', '--quiet'])
    (repository / 'wily.cfg').write_text(FIXTURE_WILY_CONFIGURATION, encoding='utf-8')
    (package / '__init__.py').write_text('', encoding='utf-8')
    (package / 'simple.py').write_text(SIMPLE_MODULE, encoding='utf-8')
    (package / 'branchy.py').write_text(SIMPLE_MODULE, encoding='utf-8')
    git(repository=repository, arguments=['add', '.'])
    git(
        repository=repository, arguments=['commit', '--quiet', '-m', 'First'], committed_at_second=1
    )
    (package / 'branchy.py').write_text(BRANCHY_MODULE, encoding='utf-8')
    git(
        repository=repository,
        arguments=['commit', '--quiet', '-am', 'Branchier'],
        committed_at_second=2,
    )
    return repository


def test_rank_modules_sums_functions_and_methods_highest_first():
    """A module ranks by its functions' and methods' complexity; its class blocks repeat them."""
    radon_report: RadonReport = {
        'glitchygames/small.py': [{'type': 'function', 'complexity': 2}],
        'glitchygames/large.py': [
            {'type': 'class', 'complexity': 50},
            {'type': 'method', 'complexity': 4},
            {'type': 'function', 'complexity': 3},
        ],
        'glitchygames/medium.py': [{'type': 'method', 'complexity': 5}],
    }

    ranked = rank_modules(radon_report=radon_report, module_count=2)

    # large.py's class block is not counted: 4 + 3 = 7 beats medium.py's 5
    assert ranked == ['glitchygames/large.py', 'glitchygames/medium.py']


def test_rank_modules_keeps_path_order_for_equal_totals():
    """Modules with equal totals rank in path order, so the ranking is stable."""
    radon_report: RadonReport = {
        'glitchygames/b.py': [{'type': 'function', 'complexity': 1}],
        'glitchygames/a.py': [{'type': 'function', 'complexity': 1}],
    }

    assert rank_modules(radon_report=radon_report, module_count=5) == [
        'glitchygames/a.py',
        'glitchygames/b.py',
    ]


def test_rank_modules_leaves_out_a_module_radon_could_not_parse(caplog):
    """A module radon reports an error for is left out, with a warning."""
    radon_report: RadonReport = {
        'glitchygames/broken.py': {'error': 'invalid syntax'},
        'glitchygames/fine.py': [{'type': 'function', 'complexity': 1}],
    }

    with caplog.at_level(logging.WARNING):
        ranked = rank_modules(radon_report=radon_report, module_count=5)

    assert ranked == ['glitchygames/fine.py']
    assert 'radon could not measure glitchygames/broken.py' in caplog.text


@pytest.fixture
def moved_fixture_repository(tmp_path: Path) -> Path:
    """Return a git repository whose package moves to src/ in its second of three commits.

    Returns:
        The repository's directory.

    """
    repository = tmp_path / 'moved-repository'
    former_package = repository / 'glitchygames'
    former_package.mkdir(parents=True)
    git(repository=repository, arguments=['init', '--quiet'])
    (repository / 'wily.cfg').write_text(FIXTURE_WILY_CONFIGURATION, encoding='utf-8')
    (former_package / '__init__.py').write_text('', encoding='utf-8')
    (former_package / 'branchy.py').write_text(SIMPLE_MODULE, encoding='utf-8')
    git(repository=repository, arguments=['add', '.'])
    git(
        repository=repository,
        arguments=['commit', '--quiet', '-m', 'Before the move'],
        committed_at_second=1,
    )
    (repository / 'src').mkdir()
    git(repository=repository, arguments=['mv', 'glitchygames', 'src/glitchygames'])
    # wily graph plots only points whose value changed from the previous one, so each commit
    # gives the module a different line count (2, 4, then BRANCHY_MODULE's 6): a pure rename
    # would drop the point before the move
    (repository / 'src' / 'glitchygames' / 'branchy.py').write_text(
        SIMPLE_MODULE + 'def moved():\n    return 2\n', encoding='utf-8'
    )
    git(repository=repository, arguments=['add', '.'])
    git(
        repository=repository,
        arguments=['commit', '--quiet', '-m', 'The move'],
        committed_at_second=2,
    )
    (repository / 'src' / 'glitchygames' / 'branchy.py').write_text(
        BRANCHY_MODULE, encoding='utf-8'
    )
    git(
        repository=repository,
        arguments=['commit', '--quiet', '-am', 'After the move'],
        committed_at_second=3,
    )
    return repository


def explorer_data(*, graphs_directory: Path) -> dict:
    """Return the explorer's data a generation published.

    Returns:
        The data.

    """
    return json.loads((graphs_directory / EXPLORER_DATA_NAME).read_text(encoding='utf-8'))


def series_messages(*, data: dict, path: str, metric: str) -> list[str]:
    """Return the commit messages of a path's points of one metric, oldest first.

    Returns:
        The messages.

    """
    return [
        data['commits'][commit_index]['message'] for commit_index, _ in data['series'][path][metric]
    ]


def test_joined_operator_data_renames_former_paths_to_current_ones():
    """A revision from before the move measures glitchygames/: its data joins src/glitchygames/."""
    operator_data: dict[str, dict[str, object]] = {
        'raw': {
            'glitchygames/scene.py': {'total': {'loc': 10}},
            'tests/test_scene.py': {'total': {'loc': 3}},
        }
    }

    assert joined_operator_data(operator_data=operator_data) == {
        'raw': {
            'src/glitchygames/scene.py': {'total': {'loc': 10}},
            'tests/test_scene.py': {'total': {'loc': 3}},
        }
    }


def test_joined_operator_data_renames_the_moved_directory_itself():
    """The package's own measurement joins too; a name that only starts the same does not."""
    operator_data: dict[str, dict[str, object]] = {
        'raw': {
            'glitchygames': {'total': {'loc': 10}},
            'glitchygames_tools': {'total': {'loc': 2}},
        }
    }

    assert joined_operator_data(operator_data=operator_data) == {
        'raw': {
            'src/glitchygames': {'total': {'loc': 10}},
            'glitchygames_tools': {'total': {'loc': 2}},
        }
    }


def test_joined_operator_data_keeps_the_current_paths_own_measurement():
    """A revision measuring a file under both paths keeps the current path's measurement."""
    operator_data: dict[str, dict[str, object]] = {
        'raw': {
            'glitchygames/scene.py': {'total': {'loc': 10}},
            'src/glitchygames/scene.py': {'total': {'loc': 12}},
        }
    }

    assert joined_operator_data(operator_data=operator_data) == {
        'raw': {'src/glitchygames/scene.py': {'total': {'loc': 12}}}
    }


def test_joined_operator_data_renames_windows_paths_too():
    """Wily on Windows names files with backslashes; the moved prefix matches them, kept so."""
    operator_data: dict[str, dict[str, object]] = {
        'raw': {'glitchygames\\scenes\\scene.py': {'total': {'loc': 10}}}
    }

    assert joined_operator_data(operator_data=operator_data) == {
        'raw': {'src\\glitchygames\\scenes\\scene.py': {'total': {'loc': 10}}}
    }


def test_join_moved_paths_rewrites_a_caches_revisions_and_index(tmp_path):
    """A small fake wily cache: the old revision's measurements and tracked files are renamed."""
    archiver_directory = tmp_path / 'git'
    archiver_directory.mkdir()
    old_revision = {'operator_data': {'raw': {'glitchygames/scene.py': {'total': {'loc': 10}}}}}
    new_revision = {'operator_data': {'raw': {'src/glitchygames/scene.py': {'total': {'loc': 12}}}}}
    (archiver_directory / 'old.json').write_text(json.dumps(old_revision), encoding='utf-8')
    (archiver_directory / 'new.json').write_text(json.dumps(new_revision), encoding='utf-8')
    index = [
        {'key': 'new', 'tracked_files': ['src/glitchygames/scene.py']},
        {'key': 'old', 'tracked_files': ['glitchygames/scene.py', 'README.md']},
    ]
    (archiver_directory / 'index.json').write_text(json.dumps(index), encoding='utf-8')

    assert join_moved_paths(cache_directory=tmp_path) == 1

    joined_old = json.loads((archiver_directory / 'old.json').read_text(encoding='utf-8'))
    assert joined_old == {
        'operator_data': {'raw': {'src/glitchygames/scene.py': {'total': {'loc': 10}}}}
    }
    assert json.loads((archiver_directory / 'new.json').read_text(encoding='utf-8')) == (
        new_revision
    )
    joined_index = json.loads((archiver_directory / 'index.json').read_text(encoding='utf-8'))
    assert [entry['tracked_files'] for entry in joined_index] == [
        ['src/glitchygames/scene.py'],
        ['README.md', 'src/glitchygames/scene.py'],
    ]


def test_a_moved_modules_graph_is_one_series_through_its_whole_history(
    moved_fixture_repository, tmp_path, mocker
):
    """The module's series holds its points from before the move, under its current path."""
    graphs_directory = tmp_path / 'graphs'
    mocker.patch.object(generate_complexity_graphs, 'PROJECT_ROOT', moved_fixture_repository)
    mocker.patch.object(generate_complexity_graphs, 'GRAPHS_DIR', graphs_directory)

    main()

    data = explorer_data(graphs_directory=graphs_directory)
    assert data['modules'] == ['src/glitchygames/branchy.py']
    # One point per commit (each changed its line count), the one before the move included
    assert series_messages(data=data, path='src/glitchygames/branchy.py', metric='raw.loc') == [
        'Before the move',
        'The move',
        'After the move',
    ]
    # The package's own series runs through the move too
    assert data['packages'] == ['src/glitchygames']
    assert series_messages(data=data, path='src/glitchygames', metric='raw.loc')[0] == (
        'Before the move'
    )


def revision(*, key: str, date: int, message: str, loc: dict[str, object]) -> dict[str, object]:
    """Return a revision as ``wily_revisions`` gives it, measuring only line counts.

    Returns:
        The revision.

    """
    return {
        'key': key,
        'date': date,
        'message': message,
        'operator_data': {'raw': {path: {'total': {'loc': value}} for path, value in loc.items()}},
    }


def test_wily_revisions_are_oldest_first_and_skip_a_revision_without_measurements(tmp_path):
    """Oldest first (wily's index lists the newest first); one without its file is skipped."""
    archiver_directory = tmp_path / 'git'
    archiver_directory.mkdir()
    index = [
        {'key': 'newest', 'date': 30, 'message': 'Newest'},
        {'key': 'missing', 'date': 20, 'message': 'Never measured'},
        {'key': 'oldest', 'date': 10, 'message': 'Oldest'},
    ]
    (archiver_directory / 'index.json').write_text(json.dumps(index), encoding='utf-8')
    for key in ('newest', 'oldest'):
        (archiver_directory / f'{key}.json').write_text(
            json.dumps({'operator_data': {'raw': {}}}), encoding='utf-8'
        )

    revisions = wily_revisions(cache_directory=tmp_path)

    assert [entry['key'] for entry in revisions] == ['oldest', 'newest']
    assert revisions[0]['operator_data'] == {'raw': {}}


def test_wily_revisions_name_windows_paths_with_slashes(tmp_path):
    """On Windows wily names paths with backslashes; the modules are looked up /-separated."""
    archiver_directory = tmp_path / 'git'
    archiver_directory.mkdir()
    index = [{'key': 'only', 'date': 10, 'message': 'Only'}]
    (archiver_directory / 'index.json').write_text(json.dumps(index), encoding='utf-8')
    measured = {
        'operator_data': {
            'raw': {
                'src\\glitchygames': {'total': {'loc': 5}},
                'src\\glitchygames\\scene.py': {'total': {'loc': 3}},
            }
        }
    }
    (archiver_directory / 'only.json').write_text(json.dumps(measured), encoding='utf-8')

    revisions = wily_revisions(cache_directory=tmp_path)

    assert set(revisions[0]['operator_data']['raw']) == {
        'src/glitchygames',
        'src/glitchygames/scene.py',
    }
    assert packages_at_head(revisions=revisions) == ['src/glitchygames']


def test_wily_revisions_keep_only_what_the_explorer_draws(tmp_path):
    """Each revision keeps only the metrics' totals for RANKED_PACKAGE's paths, nothing else.

    wily's revision files hold every function's measurements for every file in the repository
    (435 files, 4.57 GB on 2026-11-28); keeping them whole took the docs deploy past CircleCI's
    8 GB and the kernel killed it, so only what the explorer draws is kept.
    """
    archiver_directory = tmp_path / 'git'
    archiver_directory.mkdir()
    index = [{'key': 'only', 'date': 10, 'message': 'Only'}]
    (archiver_directory / 'index.json').write_text(json.dumps(index), encoding='utf-8')
    measured = {
        'operator_data': {
            'raw': {
                'src/glitchygames/scene.py': {
                    'total': {'loc': 30, 'comments': 4},
                    'detailed': {'Scene.update': {'loc': 12}},
                },
                'src/glitchygames': {'total': {'loc': 30}},
                'src/games/paddleslap/game.py': {'total': {'loc': 99}},
            },
            'cyclomatic': {
                'src/glitchygames/scene.py': {
                    'total': {'complexity': 7},
                    'detailed': {'Scene.update': {'complexity': 3}},
                },
            },
            'unlisted': {'src/glitchygames/scene.py': {'total': {'thing': 1}}},
        }
    }
    (archiver_directory / 'only.json').write_text(json.dumps(measured), encoding='utf-8')

    revisions = wily_revisions(cache_directory=tmp_path)

    assert revisions[0]['operator_data'] == {
        'raw': {
            'src/glitchygames/scene.py': {'total': {'loc': 30}},
            'src/glitchygames': {'total': {'loc': 30}},
        },
        'cyclomatic': {'src/glitchygames/scene.py': {'total': {'complexity': 7}}},
    }


def test_measurement_reads_a_paths_total_rounded_or_none():
    """A path's total, rounded; None for an unmeasured path, operator or non-number."""
    operator_data = {
        'raw': {'a.py': {'total': {'loc': 10}}, 'b.py': {'total': {'loc': True}}},
        'halstead': {'a.py': {'total': {'effort': 12.3456}}},
    }

    assert measurement(operator_data=operator_data, path='a.py', metric='raw.loc') == 10.0
    assert measurement(operator_data=operator_data, path='a.py', metric='halstead.effort') == 12.35
    assert measurement(operator_data=operator_data, path='b.py', metric='raw.loc') is None
    assert measurement(operator_data=operator_data, path='c.py', metric='raw.loc') is None
    assert measurement(operator_data=operator_data, path='a.py', metric='cyclomatic.x') is None


def test_packages_at_head_are_the_ranked_packages_directories_at_the_newest_revision():
    """The package and its directories as the newest revision measured them; files left out."""
    revisions = [
        revision(key='a', date=1, message='Old', loc={'src/glitchygames/gone': 1}),
        revision(
            key='b',
            date=2,
            message='New',
            loc={
                '': 9,
                'src/glitchygames': 5,
                'src/glitchygames/scenes': 3,
                'src/glitchygames/scenes/scene.py': 3,
                'src/glitchygames_other': 1,
                'tests': 2,
            },
        ),
    ]

    assert packages_at_head(revisions=revisions) == ['src/glitchygames', 'src/glitchygames/scenes']
    assert packages_at_head(revisions=[]) == []


def test_complexity_history_keeps_only_the_commits_that_changed_a_value():
    """Each series holds its first measurement and every change, as [commit index, value]."""
    revisions = [
        revision(key='1' * 40, date=0, message='First\n\nbody', loc={'m.py': 2}),
        revision(key='2' * 40, date=86400, message='Same', loc={'m.py': 2, 'p': 4}),
        revision(key='3' * 40, date=172800, message='Longer', loc={'m.py': 6, 'p': 4}),
    ]

    data = complexity_history(revisions=revisions, modules=['m.py'], packages=['p'])

    assert data['commits'] == [
        {'commit': '1111111', 'date': '1970-01-01', 'message': 'First'},
        {'commit': '2222222', 'date': '1970-01-02', 'message': 'Same'},
        {'commit': '3333333', 'date': '1970-01-03', 'message': 'Longer'},
    ]
    assert data['series']['m.py']['raw.loc'] == [[0, 2.0], [2, 6.0]]
    # A package measured from the second commit on starts there
    assert data['series']['p']['raw.loc'] == [[1, 4.0]]
    # Metrics the revisions never measured have no points
    assert data['series']['m.py']['cyclomatic.complexity'] == []
    assert data['metrics'] == [{'key': metric, 'label': label} for metric, label in METRICS]
    assert (data['modules'], data['packages']) == (['m.py'], ['p'])
    assert (data['default_count'], data['plotly']) == (TOP_MODULE_COUNT, PLOTLY_JS_URL)


def test_wily_command_runs_this_interpreters_wily_with_the_given_cache(tmp_path):
    """The wily command runs wily as this interpreter's module, with its cache where it is told."""
    command = wily_command(cache_directory=tmp_path, arguments=['index'])

    assert command == [sys.executable, '-m', 'wily', '--cache', str(tmp_path), 'index']


def test_graphs_snippet_names_what_was_measured_and_holds_the_explorer():
    """The snippet names the commit and counts, then the explorer reading the published data."""
    graphs = ComplexityGraphs(
        commit='abc1234',
        commit_date='2026-10-23',
        commit_count=12,
        modules=('src/glitchygames/a.py', 'src/glitchygames/b.py'),
        packages=('src/glitchygames',),
    )

    snippet = graphs_snippet(graphs=graphs)

    assert snippet.startswith(
        'Generated at commit `abc1234` (2026-10-23) from all 12 commits: 2 modules and 1 '
        'packages of `src/glitchygames`.'
    )
    assert (
        '<div class="complexity-explorer" data-source="../graphs/complexity-explorer.json"></div>'
    ) in snippet
    assert '<iframe' not in snippet


def test_run_tool_returns_the_output(tmp_path):
    """A tool that succeeds returns its output."""
    output = run_tool(
        command=[sys.executable, '-c', 'print("measured")'],
        working_directory=tmp_path,
        timeout_seconds=60.0,
    )

    assert output == 'measured\n'


def test_run_tool_raises_with_the_output_of_a_failed_tool(tmp_path):
    """A tool that fails raises with its exit status and output."""
    with pytest.raises(ComplexityGraphError, match=r'failed with exit status 3:\nbroken'):
        run_tool(
            command=[sys.executable, '-c', 'import sys; print("broken"); sys.exit(3)'],
            working_directory=tmp_path,
            timeout_seconds=60.0,
        )


def test_a_checkout_without_the_ranked_package_is_refused_by_name(tmp_path):
    """HEAD without src/glitchygames/ says so, not a raw FileNotFoundError from radon's report."""
    with pytest.raises(ComplexityGraphError, match=r'no src/glitchygames/ to rank'):
        measure_ranked_modules(checkout=tmp_path, report_path=tmp_path / 'radon.json')


def test_run_tool_raises_for_a_tool_that_outlives_its_timeout(tmp_path):
    """A tool that outlives its timeout raises."""
    with pytest.raises(ComplexityGraphError, match='did not finish within 0 seconds'):
        run_tool(
            command=[sys.executable, '-c', 'import time; time.sleep(30)'],
            working_directory=tmp_path,
            timeout_seconds=0.2,
        )


def test_detached_checkout_removes_its_worktree_after_an_error(fixture_repository, tmp_path):
    """The worktree holds HEAD and is removed even when the work in it fails."""
    checkout_directory = tmp_path / 'checkout'

    checked_out_modules: list[str] = []

    def measure_then_fail() -> None:
        with detached_checkout(
            project_root=fixture_repository, checkout_directory=checkout_directory
        ) as checkout:
            checked_out_modules.append(
                (checkout / 'src' / 'glitchygames' / 'branchy.py').read_text(encoding='utf-8')
            )
            message = 'measuring failed'
            raise ComplexityGraphError(message)

    with pytest.raises(ComplexityGraphError, match='measuring failed'):
        measure_then_fail()

    assert checked_out_modules == [BRANCHY_MODULE]

    assert not checkout_directory.exists()
    assert len(git(repository=fixture_repository, arguments=['worktree', 'list']).splitlines()) == 1


def test_main_measures_the_fixture_repositorys_history(fixture_repository, tmp_path, mocker):
    """Running main writes every metric of the ranked modules and the package, and the snippet."""
    graphs_directory = tmp_path / 'graphs'
    graphs_directory.mkdir()
    # A graph page an earlier generation wrote, before the explorer
    stale_graph = graphs_directory / 'raw_loc.html'
    stale_graph.write_text('a wily graph page', encoding='utf-8')
    mocker.patch.object(generate_complexity_graphs, 'PROJECT_ROOT', fixture_repository)
    mocker.patch.object(generate_complexity_graphs, 'GRAPHS_DIR', graphs_directory)
    head_commit = git(repository=fixture_repository, arguments=['log', '-1', '--format=%h'])

    main()

    assert not stale_graph.exists()
    data = explorer_data(graphs_directory=graphs_directory)
    # branchy.py (complexity 3) ranks before simple.py (1); radon reports nothing for the empty
    # __init__.py, so it is not ranked
    assert data['modules'] == ['src/glitchygames/branchy.py', 'src/glitchygames/simple.py']
    assert data['packages'] == ['src/glitchygames']
    assert [commit['message'] for commit in data['commits']] == ['First', 'Branchier']
    for path in (*data['modules'], *data['packages']):
        assert set(data['series'][path]) == {metric for metric, _label in METRICS}
    # branchy.py grew in the second commit; simple.py never changed (one point)
    assert series_messages(data=data, path='src/glitchygames/branchy.py', metric='raw.loc') == [
        'First',
        'Branchier',
    ]
    assert series_messages(data=data, path='src/glitchygames/simple.py', metric='raw.loc') == [
        'First'
    ]
    snippet = (graphs_directory / GRAPHS_SNIPPET_NAME).read_text(encoding='utf-8')
    assert f'Generated at commit `{head_commit.strip()}` ' in snippet
    # Marked with HEAD, so a later local docs build keeps them instead of the placeholder
    full_head = git(repository=fixture_repository, arguments=['rev-parse', 'HEAD']).strip()
    assert (graphs_directory / GENERATED_FROM_NAME).read_text(encoding='utf-8') == f'{full_head}\n'
    assert 'from all 2 commits: 2 modules and 1 packages of `src/glitchygames`.' in snippet
    # The worktree is gone and the repository's own checkout untouched
    assert len(git(repository=fixture_repository, arguments=['worktree', 'list']).splitlines()) == 1
    assert not git(repository=fixture_repository, arguments=['status', '--porcelain'])


def test_main_exits_internal_error_when_a_tool_fails(tmp_path, mocker, capsys):
    """A failed tool (git outside a repository) exits INTERNAL_ERROR with its output."""
    not_a_repository = tmp_path / 'not-a-repository'
    not_a_repository.mkdir()
    mocker.patch.object(generate_complexity_graphs, 'PROJECT_ROOT', not_a_repository)
    mocker.patch.object(generate_complexity_graphs, 'GRAPHS_DIR', tmp_path / 'graphs')

    with pytest.raises(SystemExit) as exit_information:
        main()

    assert exit_information.value.code == ExitCode.INTERNAL_ERROR
    # The first tool main runs: reading the commit the generated graphs are marked with
    assert 'git rev-parse HEAD' in capsys.readouterr().err


def test_generate_if_stale_generates_once_per_commit(fixture_repository, tmp_path, mocker):
    """The graphs are generated when missing, skipped for the same HEAD, redone for a new one."""
    graphs_directory = tmp_path / 'graphs'
    generation = mocker.spy(generate_complexity_graphs, 'generate_complexity_graphs')

    first = generate_if_stale(project_root=fixture_repository, graphs_directory=graphs_directory)
    second = generate_if_stale(project_root=fixture_repository, graphs_directory=graphs_directory)
    git(
        repository=fixture_repository,
        arguments=['commit', '--allow-empty', '--quiet', '-m', 'A third commit'],
    )
    third = generate_if_stale(project_root=fixture_repository, graphs_directory=graphs_directory)

    assert (first, second, third) == (True, False, True)
    assert generation.call_count == 2
    head = git(repository=fixture_repository, arguments=['rev-parse', 'HEAD']).strip()
    assert (graphs_directory / GENERATED_FROM_NAME).read_text(encoding='utf-8') == f'{head}\n'
    assert (graphs_directory / GRAPHS_SNIPPET_NAME).is_file()


def test_two_generations_at_once_both_succeed_and_only_one_generates(fixture_repository, tmp_path):
    """Two builds generating into one directory at once (BUGS.md #214): one waits, then skips.

    A running ``mkdocs serve`` and the pre-push hook's ``mkdocs build`` both saw a new HEAD;
    each rewrote the other's pages in place and one failed ("plotly changed its output").
    """
    graphs_directory = tmp_path / 'graphs'
    outcomes: list[bool] = []
    errors: list[Exception] = []

    def generate() -> None:
        try:
            outcomes.append(
                generate_if_stale(
                    project_root=fixture_repository, graphs_directory=graphs_directory
                )
            )
        # The race's failures: a page rewritten by the other build, or removed under it
        except (ComplexityGraphError, OSError) as error:
            errors.append(error)

    builds = [threading.Thread(target=generate) for _ in range(2)]
    for build in builds:
        build.start()
    for build in builds:
        build.join(timeout=600)

    assert errors == []
    assert sorted(outcomes) == [False, True]
    assert explorer_data(graphs_directory=graphs_directory)['modules']


def test_the_published_data_stays_whole_while_new_data_is_made(
    fixture_repository, tmp_path, mocker
):
    """The data is made in staging: the published file is replaced only once the new one is done."""
    graphs_directory = tmp_path / 'graphs'
    graphs_directory.mkdir()
    published_data = graphs_directory / EXPLORER_DATA_NAME
    published_data.write_text("the previous generation's data", encoding='utf-8')
    real_complexity_history = generate_complexity_graphs.complexity_history
    seen_while_measuring: list[str] = []

    def complexity_history_watching(**arguments) -> dict:
        seen_while_measuring.append(published_data.read_text(encoding='utf-8'))
        return real_complexity_history(**arguments)

    mocker.patch.object(
        generate_complexity_graphs, 'complexity_history', complexity_history_watching
    )

    generate_if_stale(project_root=fixture_repository, graphs_directory=graphs_directory)

    assert seen_while_measuring == ["the previous generation's data"]
    assert explorer_data(graphs_directory=graphs_directory)['modules']


def test_a_generation_cleans_up_after_one_that_crashed(fixture_repository, tmp_path):
    """A crashed generation's staging directory is removed by the next one, nothing else left."""
    graphs_directory = tmp_path / 'graphs'
    leftover = graphs_directory / f'{STAGING_DIRECTORY_PREFIX}crashed'
    leftover.mkdir(parents=True)
    (leftover / 'half_a_graph.html').write_text('<html>', encoding='utf-8')

    generate_if_stale(project_root=fixture_repository, graphs_directory=graphs_directory)

    assert not leftover.exists()
    published = {path.name for path in graphs_directory.iterdir()}
    assert published - {GENERATION_LOCK_NAME} == {
        EXPLORER_DATA_NAME,
        GRAPHS_SNIPPET_NAME,
        GENERATED_FROM_NAME,
    }


def test_the_mkdocs_hook_generates_the_graphs_before_a_deploy(fixture_repository, tmp_path, mocker):
    """A deploy's on_pre_build generates the graphs through the script it loads by path."""
    mocker.patch.object(mkdocs_hooks.BUILD_STATE, 'command', 'gh-deploy')
    mocker.patch.dict(os.environ, {mkdocs_hooks.COMPLEXITY_GRAPHS_VARIABLE: ''})
    graph_script = mkdocs_hooks.load_graph_script()
    graphs_directory = tmp_path / 'graphs'
    mocker.patch.object(graph_script, 'PROJECT_ROOT', fixture_repository)
    mocker.patch.object(graph_script, 'GRAPHS_DIR', graphs_directory)
    # The performance graphs follow (tests/test_generate_performance_graphs.py): kept out of
    # this repository's docs tree
    performance_script = mkdocs_hooks.load_performance_script()
    mocker.patch.object(performance_script, 'PROJECT_ROOT', fixture_repository)
    mocker.patch.object(performance_script, 'METRICS_DIR', tmp_path / 'metrics')
    mocker.patch.object(performance_script, 'PENDING_LEDGER_PATH', tmp_path / 'pending.jsonl')

    mkdocs_hooks.on_pre_build(config=MkDocsConfig())

    assert explorer_data(graphs_directory=graphs_directory)['modules'] == [
        'src/glitchygames/branchy.py',
        'src/glitchygames/simple.py',
    ]
    assert 'placeholder' not in explorer_data(graphs_directory=graphs_directory)
    head = git(repository=fixture_repository, arguments=['rev-parse', 'HEAD']).strip()
    assert (graphs_directory / GENERATED_FROM_NAME).read_text(encoding='utf-8') == f'{head}\n'
    assert (tmp_path / 'metrics' / performance_script.SNIPPET_NAME).is_file()


# A stage's lines from the hook's logger (INFO, which mkdocs prints): its start, and its end with
# the seconds it took and the process's peak memory (unknown only on Windows: no resource module)
PEAK_MEMORY = r'peak memory unknown' if sys.platform == 'win32' else r'peak memory \d+\.\d\d GB'
STAGE_STARTED = r'^{stage}: started$'
STAGE_DONE = rf'^{{stage}}: done in \d+\.\d s, {PEAK_MEMORY}$'
STAGE_FAILED = rf'^{{stage}}: failed after \d+\.\d s, {PEAK_MEMORY}$'


def hook_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return what the hook logged at INFO, in order.

    Returns:
        The messages.

    """
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == mkdocs_hooks.LOG.name and record.levelno == logging.INFO
    ]


def test_the_mkdocs_hook_logs_each_graph_stages_start_and_end(mocker, caplog):
    """The build is never silent while the graphs generate, and the log says how long each took.

    CircleCI's checks-linux job (#285 moved the strict docs build to Linux) was killed after 10
    minutes with no output while the hook generated the graphs silently (job 5089, #261).
    """
    mocker.patch.object(mkdocs_hooks.BUILD_STATE, 'command', 'gh-deploy')
    graph_script = mkdocs_hooks.load_graph_script()
    mocker.patch.object(graph_script, 'generate_if_stale')
    mocker.patch.object(
        mkdocs_hooks, 'load_performance_script'
    ).return_value.generate_performance_page = mocker.Mock()
    caplog.set_level(logging.INFO, logger=mkdocs_hooks.LOG.name)

    mkdocs_hooks.on_pre_build(config=MkDocsConfig())

    messages = hook_messages(caplog)
    patterns = [
        STAGE_STARTED.format(stage='Complexity graphs'),
        STAGE_DONE.format(stage='Complexity graphs'),
        STAGE_STARTED.format(stage='Performance graphs'),
        STAGE_DONE.format(stage='Performance graphs'),
    ]
    assert len(messages) == len(patterns), messages
    for message, pattern in zip(messages, patterns, strict=True):
        assert re.fullmatch(pattern, message), (message, pattern)


def test_a_failed_graph_stage_logs_how_long_it_ran(tmp_path, mocker, caplog):
    """A stage that stops the build still ends its lines: failed, after how long."""
    mocker.patch.object(mkdocs_hooks.BUILD_STATE, 'command', 'gh-deploy')
    graph_script = mkdocs_hooks.load_graph_script()
    not_a_repository = tmp_path / 'not-a-repository'
    not_a_repository.mkdir()
    mocker.patch.object(graph_script, 'PROJECT_ROOT', not_a_repository)
    mocker.patch.object(graph_script, 'GRAPHS_DIR', tmp_path / 'graphs')
    caplog.set_level(logging.INFO, logger=mkdocs_hooks.LOG.name)

    with pytest.raises(PluginError):
        mkdocs_hooks.on_pre_build(config=MkDocsConfig())

    messages = hook_messages(caplog)
    assert re.fullmatch(STAGE_STARTED.format(stage='Complexity graphs'), messages[0])
    assert re.fullmatch(STAGE_FAILED.format(stage='Complexity graphs'), messages[-1]), messages


@pytest.mark.skipif(sys.platform == 'win32', reason='Windows has no resource module')
def test_a_stages_peak_memory_reads_the_process_peak_in_each_platforms_unit(mocker):
    """ru_maxrss is bytes on macOS and kibibytes on Linux; both read as gigabytes."""
    usage = mocker.Mock(ru_maxrss=9_437_184)
    mocker.patch.object(mkdocs_hooks.resource, 'getrusage', return_value=usage)

    assert mkdocs_hooks.peak_memory_text(platform='linux') == 'peak memory 9.66 GB'
    assert mkdocs_hooks.peak_memory_text(platform='darwin') == 'peak memory 0.01 GB'


def test_a_stages_peak_memory_is_unknown_without_a_resource_module(mocker):
    """Windows has no resource module: the line says so instead of a number."""
    mocker.patch.object(mkdocs_hooks, 'resource', None)

    assert mkdocs_hooks.peak_memory_text() == 'peak memory unknown'


def test_the_mkdocs_hook_stops_the_build_when_the_generation_fails(tmp_path, mocker):
    """A failed tool becomes mkdocs's PluginError, which stops the build with the tool's output."""
    mocker.patch.object(mkdocs_hooks.BUILD_STATE, 'command', 'gh-deploy')
    graph_script = mkdocs_hooks.load_graph_script()
    not_a_repository = tmp_path / 'not-a-repository'
    not_a_repository.mkdir()
    mocker.patch.object(graph_script, 'PROJECT_ROOT', not_a_repository)
    mocker.patch.object(graph_script, 'GRAPHS_DIR', tmp_path / 'graphs')

    with pytest.raises(
        PluginError, match='Could not generate the complexity graphs: git rev-parse'
    ):
        mkdocs_hooks.on_pre_build(config=MkDocsConfig())


def local_build_hook(*, mocker, tmp_path: Path, project_root: Path, command: str | None) -> Path:
    """Point the hook's scripts at ``tmp_path`` for a build run as ``command``.

    The complexity script's ``PROJECT_ROOT`` is ``project_root``; its graphs and the performance
    script's output go under ``tmp_path``, never this repository's docs tree, and
    ``COMPLEXITY_GRAPHS_VARIABLE`` is unset.

    Returns:
        The complexity graphs' directory.

    """
    mocker.patch.object(mkdocs_hooks.BUILD_STATE, 'command', command)
    mocker.patch.dict(os.environ)
    os.environ.pop(mkdocs_hooks.COMPLEXITY_GRAPHS_VARIABLE, None)
    graph_script = mkdocs_hooks.load_graph_script()
    graphs_directory = tmp_path / 'graphs'
    mocker.patch.object(graph_script, 'PROJECT_ROOT', project_root)
    mocker.patch.object(graph_script, 'GRAPHS_DIR', graphs_directory)
    performance_script = mkdocs_hooks.load_performance_script()
    mocker.patch.object(performance_script, 'PROJECT_ROOT', project_root)
    mocker.patch.object(performance_script, 'METRICS_DIR', tmp_path / 'metrics')
    mocker.patch.object(performance_script, 'PENDING_LEDGER_PATH', tmp_path / 'pending.jsonl')
    return graphs_directory


@pytest.mark.parametrize('command', ['build', 'serve', None])
def test_a_local_build_writes_the_placeholder_and_measures_nothing(
    fixture_repository, tmp_path, mocker, caplog, command
):
    """``mkdocs build`` and ``serve`` (and an unknown command) skip the minutes-long generation.

    The owner, 2026-11-23: only a deploy generates the graphs; the strict build in nox -s lint
    spent about 490 s of its 830 on them.
    """
    graphs_directory = local_build_hook(
        mocker=mocker, tmp_path=tmp_path, project_root=fixture_repository, command=command
    )
    generation = mocker.spy(mkdocs_hooks.load_graph_script(), 'generate_complexity_graphs')
    caplog.set_level(logging.INFO, logger=mkdocs_hooks.LOG.name)

    mkdocs_hooks.on_pre_build(config=MkDocsConfig())

    assert generation.call_count == 0
    # The build's log says why the page has no graphs, and how to get them
    assert (
        'Complexity graphs: a placeholder (only a deploy generates them; '
        'GLITCHYGAMES_DOCS_COMPLEXITY_GRAPHS=1 generates them here)'
    ) in hook_messages(caplog)
    data = explorer_data(graphs_directory=graphs_directory)
    assert data['placeholder'] == generate_complexity_graphs.PLACEHOLDER_NOTICE
    assert (data['commits'], data['modules'], data['packages'], data['series']) == ([], [], [], {})
    snippet = (graphs_directory / GRAPHS_SNIPPET_NAME).read_text(encoding='utf-8')
    assert snippet.startswith(f'**{generate_complexity_graphs.PLACEHOLDER_HEADING}**')
    assert (
        '<div class="complexity-explorer" data-source="../graphs/complexity-explorer.json"></div>'
    ) in snippet
    # Never taken for current graphs: a later deploy generates
    assert not (graphs_directory / GENERATED_FROM_NAME).exists()


def test_the_placeholder_holds_every_key_the_explorer_reads():
    """The placeholder is the generated data's format (docs/js/complexity.js reads it alike)."""
    generated = complexity_history(revisions=[], modules=[], packages=[])

    placeholder = generate_complexity_graphs.placeholder_history()

    assert set(placeholder) == {*generated, 'placeholder'}
    assert placeholder['metrics'] == generated['metrics']
    assert placeholder['plotly'] == PLOTLY_JS_URL


def test_a_local_build_keeps_graphs_generated_from_this_commit(
    fixture_repository, tmp_path, mocker, caplog
):
    """Graphs already generated from HEAD (main, or a deploy build) are kept, not replaced."""
    graphs_directory = local_build_hook(
        mocker=mocker, tmp_path=tmp_path, project_root=fixture_repository, command='build'
    )
    generate_if_stale(project_root=fixture_repository, graphs_directory=graphs_directory)
    generated = explorer_data(graphs_directory=graphs_directory)
    caplog.set_level(logging.INFO, logger=mkdocs_hooks.LOG.name)

    mkdocs_hooks.on_pre_build(config=MkDocsConfig())

    assert explorer_data(graphs_directory=graphs_directory) == generated
    assert 'placeholder' not in generated
    assert 'Complexity graphs: kept, generated from this commit' in hook_messages(caplog)


def test_a_local_build_replaces_another_commits_graphs_with_the_placeholder(
    fixture_repository, tmp_path, mocker
):
    """Graphs from an older commit are not shown as this one's: the placeholder replaces them."""
    graphs_directory = local_build_hook(
        mocker=mocker, tmp_path=tmp_path, project_root=fixture_repository, command='serve'
    )
    generate_if_stale(project_root=fixture_repository, graphs_directory=graphs_directory)
    git(
        repository=fixture_repository,
        arguments=['commit', '--allow-empty', '--quiet', '-m', 'A third commit'],
    )

    mkdocs_hooks.on_pre_build(config=MkDocsConfig())

    assert 'placeholder' in explorer_data(graphs_directory=graphs_directory)
    published = {path.name for path in graphs_directory.iterdir()}
    assert published - {GENERATION_LOCK_NAME} == {EXPLORER_DATA_NAME, GRAPHS_SNIPPET_NAME}


def test_the_placeholder_needs_no_repository(tmp_path, mocker):
    """Without graphs to keep, git is never asked: a placeholder build needs no repository."""
    not_a_repository = tmp_path / 'not-a-repository'
    not_a_repository.mkdir()
    graphs_directory = local_build_hook(
        mocker=mocker, tmp_path=tmp_path, project_root=not_a_repository, command='build'
    )
    performance = mocker.patch.object(mkdocs_hooks, 'generate_performance_graphs')

    mkdocs_hooks.on_pre_build(config=MkDocsConfig())

    assert 'placeholder' in explorer_data(graphs_directory=graphs_directory)
    performance.assert_called_once_with()


def test_a_placeholder_builds_an_explorer_page_the_hook_accepts(
    fixture_repository, tmp_path, mocker
):
    """The skipped build's complexity page names only files the site has (missing_explorer_files).

    The page holds the placeholder snippet's explorer element (mkdocs passes its HTML through)
    and the site the placeholder data beside it, as mkdocs copies docs/quality/graphs/.
    """
    graphs_directory = local_build_hook(
        mocker=mocker, tmp_path=tmp_path, project_root=fixture_repository, command='build'
    )
    mkdocs_hooks.on_pre_build(config=MkDocsConfig())
    site = make_explorer_site(tmp_path / 'site')
    snippet = (graphs_directory / GRAPHS_SNIPPET_NAME).read_text(encoding='utf-8')
    (site / 'quality' / 'complexity' / 'index.html').write_text(
        f'<div class="md-content">{snippet}</div>', encoding='utf-8'
    )
    (site / 'quality' / 'graphs' / EXPLORER_DATA_NAME).write_bytes(
        (graphs_directory / EXPLORER_DATA_NAME).read_bytes()
    )

    assert mkdocs_hooks.missing_explorer_files(site_directory=site) == []


@pytest.mark.parametrize(
    ('command', 'setting', 'wanted'),
    [
        ('gh-deploy', None, True),
        ('gh-deploy', '', True),
        ('gh-deploy', '0', True),
        ('gh-deploy', '1', True),
        ('build', None, False),
        ('build', '0', False),
        ('build', '1', True),
        ('serve', '', False),
        ('serve', '1', True),
        (None, None, False),
        (None, '1', True),
    ],
)
def test_only_a_deploy_or_the_setting_generates_the_graphs(mocker, command, setting, wanted):
    """A deploy always generates; a local build only with GLITCHYGAMES_DOCS_COMPLEXITY_GRAPHS=1."""
    mocker.patch.object(mkdocs_hooks.BUILD_STATE, 'command', command)
    mocker.patch.dict(os.environ)
    os.environ.pop(mkdocs_hooks.COMPLEXITY_GRAPHS_VARIABLE, None)
    if setting is not None:
        os.environ[mkdocs_hooks.COMPLEXITY_GRAPHS_VARIABLE] = setting

    assert mkdocs_hooks.complexity_graphs_wanted() is wanted


def test_the_setting_makes_a_local_build_generate(fixture_repository, tmp_path, mocker):
    """GLITCHYGAMES_DOCS_COMPLEXITY_GRAPHS=1 on ``mkdocs build`` generates the real graphs."""
    graphs_directory = local_build_hook(
        mocker=mocker, tmp_path=tmp_path, project_root=fixture_repository, command='build'
    )
    os.environ[mkdocs_hooks.COMPLEXITY_GRAPHS_VARIABLE] = mkdocs_hooks.COMPLEXITY_GRAPHS_ON

    mkdocs_hooks.on_pre_build(config=MkDocsConfig())

    data = explorer_data(graphs_directory=graphs_directory)
    assert 'placeholder' not in data
    assert data['modules']
    assert (graphs_directory / GENERATED_FROM_NAME).is_file()


@pytest.mark.parametrize('setting', ['yes', 'true', '2', ' 1'])
def test_an_unknown_setting_stops_the_build(mocker, setting):
    """A misspelt setting is refused by name, never read as on or off."""
    mocker.patch.object(mkdocs_hooks.BUILD_STATE, 'command', 'build')
    mocker.patch.dict(os.environ, {mkdocs_hooks.COMPLEXITY_GRAPHS_VARIABLE: setting})

    with pytest.raises(PluginError, match=mkdocs_hooks.COMPLEXITY_GRAPHS_VARIABLE):
        mkdocs_hooks.complexity_graphs_wanted()


def test_the_mkdocs_hook_loads_the_graph_script_once(mocker):
    """The script is loaded from its file the first time and reused after (as mkdocs reloads)."""
    mocker.patch.dict(sys.modules)
    sys.modules.pop(mkdocs_hooks.GRAPH_SCRIPT_MODULE_NAME, None)

    first = mkdocs_hooks.load_graph_script()
    second = mkdocs_hooks.load_graph_script()

    assert first is second
    assert first.__file__ == str(mkdocs_hooks.GRAPH_SCRIPT_PATH)


class CachedArgument:
    """An object a module cache is keyed by, as griffe's caches are keyed by a build's classes."""


def module_with_a_filled_cache(*, name: str) -> tuple[types.ModuleType, weakref.ref]:
    """Return a module named ``name`` with one cache entry, and a weak reference to its key.

    Returns:
        The module (already in sys.modules) and the weak reference.

    """
    module = types.ModuleType(name)

    @functools.cache
    def cached_lookup(argument: CachedArgument) -> int:
        return id(argument)

    module.__dict__['cached_lookup'] = cached_lookup
    sys.modules[name] = module
    argument = CachedArgument()
    cached_lookup(argument)
    return module, weakref.ref(argument)


def test_the_mkdocs_hook_frees_the_documentation_caches_after_a_build(mocker, tmp_path):
    """After a build, griffe's and mkdocstrings' module caches are emptied, freeing their keys."""
    mocker.patch.dict(sys.modules)
    # No browser games built: the hook copies none. The hook also checks the built explorer
    # pages, so the site is one holding them, never the checkout's (a fresh CI checkout has none)
    mocker.patch.object(mkdocs_hooks, 'BROWSER_GAMES_DIRECTORY', tmp_path / 'no games')
    config = MkDocsConfig()
    config['site_dir'] = str(make_explorer_site(tmp_path / 'site'))
    module, key = module_with_a_filled_cache(name='griffe._fake_extension')

    mkdocs_hooks.on_post_build(config=config)
    gc.collect()

    assert module.cached_lookup.cache_info().currsize == 0
    assert key() is None


def test_the_mkdocs_hook_leaves_other_modules_caches_alone(mocker, tmp_path):
    """Only griffe's and mkdocstrings' caches are emptied."""
    mocker.patch.dict(sys.modules)
    # No browser games built: the hook copies none. The hook also checks the built explorer
    # pages, so the site is one holding them, never the checkout's (a fresh CI checkout has none)
    mocker.patch.object(mkdocs_hooks, 'BROWSER_GAMES_DIRECTORY', tmp_path / 'no games')
    config = MkDocsConfig()
    config['site_dir'] = str(make_explorer_site(tmp_path / 'site'))
    module, key = module_with_a_filled_cache(name='unrelated_package.lookups')

    mkdocs_hooks.on_post_build(config=config)

    assert module.cached_lookup.cache_info().currsize == 1
    assert key() is not None


@pytest.mark.parametrize(
    ('module_name', 'function_name'),
    [
        # Keyed by a build's griffe classes: kept every build's API tree (about 430 MB each)
        ('griffe._internal.extensions.dataclasses', '_dataclass_parameters'),
        # Keyed by a build's Jinja environment: kept every build's Python handler
        ('mkdocstrings_handlers.python._internal.rendering', '_test_existing_template'),
    ],
)
def test_the_mkdocs_hook_finds_the_caches_that_kept_old_builds(module_name, function_name):
    """The caches that kept every mkdocs serve rebuild alive are among those it empties."""
    cache = getattr(importlib.import_module(module_name), function_name)

    assert cache in mkdocs_hooks.documentation_caches()
