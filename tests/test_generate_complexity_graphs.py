"""scripts/generate_complexity_graphs.py generates the docs' complexity graphs from git history.

The end-to-end tests run the real git, radon and wily on a small repository made in tmp_path
(two commits of a two-module ``glitchygames`` package), never on this repository.
"""

from __future__ import annotations

import functools
import gc
import importlib
import logging
import os
import sys
import types
import weakref
from typing import TYPE_CHECKING

import pytest
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from scripts import generate_complexity_graphs, mkdocs_hooks
from scripts.generate_complexity_graphs import (
    GENERATED_FROM_NAME,
    GRAPHS_SNIPPET_NAME,
    METRICS,
    ComplexityGraphError,
    ComplexityGraphs,
    RadonReport,
    detached_checkout,
    generate_if_stale,
    graph_file_name,
    graphs_snippet,
    load_plotly_from_jsdelivr,
    main,
    rank_modules,
    run_tool,
    space_commits_evenly,
    wily_command,
)

from glitchygames.exit_codes import ExitCode
from glitchygames.process import run_command

if TYPE_CHECKING:
    from pathlib import Path

# The fixture repository's wily configuration: this repository's operators, its one package
FIXTURE_WILY_CONFIGURATION = """[wily]
path = glitchygames
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


def git(*, repository: Path, arguments: list[str]) -> str:
    """Run git in the fixture repository (no signing, a fixed author).

    Returns:
        git's standard output.

    """
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
        environment=os.environ,
        timeout_seconds=60.0,
        capture_output=True,
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
    package = repository / 'glitchygames'
    package.mkdir(parents=True)
    git(repository=repository, arguments=['init', '--quiet'])
    (repository / 'wily.cfg').write_text(FIXTURE_WILY_CONFIGURATION, encoding='utf-8')
    (package / '__init__.py').write_text('', encoding='utf-8')
    (package / 'simple.py').write_text(SIMPLE_MODULE, encoding='utf-8')
    (package / 'branchy.py').write_text(SIMPLE_MODULE, encoding='utf-8')
    git(repository=repository, arguments=['add', '.'])
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'First'])
    (package / 'branchy.py').write_text(BRANCHY_MODULE, encoding='utf-8')
    git(repository=repository, arguments=['commit', '--quiet', '-am', 'Branchier'])
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


def test_load_plotly_from_jsdelivr_keeps_plotlys_version():
    """cdn.plot.ly's plotly.js becomes the same version on jsDelivr."""
    html = '<script charset="utf-8" src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>'

    rewritten = load_plotly_from_jsdelivr(html=html)

    assert rewritten == (
        '<script charset="utf-8" '
        'src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script>'
    )


def test_load_plotly_from_jsdelivr_refuses_a_page_without_plotlys_cdn_script():
    """A page without the cdn.plot.ly script means plotly changed its output: refused."""
    with pytest.raises(ComplexityGraphError, match=r'no plotly\.js from cdn\.plot\.ly'):
        load_plotly_from_jsdelivr(html='<script>/* plotly.js inlined */</script>')


def test_space_commits_evenly_makes_the_x_axis_one_slot_per_commit():
    """Commits plotted by date get one evenly spaced slot each once the page loads."""
    html = (
        '<html><body><div class="plotly-graph-div"></div><script>/* plot */</script></body></html>'
    )

    spaced = space_commits_evenly(html=html)

    script_start = spaced.index('<script>window.addEventListener')
    assert spaced.endswith('</script></body></html>')
    assert spaced[:script_start] == html.removesuffix('</body></html>')
    script = spaced[script_start:]
    assert "'xaxis.type': 'category'" in script
    assert "'xaxis.categoryorder': 'category ascending'" in script
    assert 'Plotly.relayout' in script


def test_space_commits_evenly_refuses_a_page_without_a_body_end():
    """A page with no </body> means wily changed its output: refused."""
    with pytest.raises(ComplexityGraphError, match=r'no </body>'):
        space_commits_evenly(html='<div class="plotly-graph-div"></div>')


def test_graph_file_name_replaces_the_metric_dots():
    """A metric's graph page is named after it, dots made underscores."""
    assert graph_file_name(metric='maintainability.mi') == 'maintainability_mi.html'


def test_wily_command_runs_this_interpreters_wily_with_the_given_cache(tmp_path):
    """The wily command runs wily as this interpreter's module, with its cache where it is told."""
    command = wily_command(cache_directory=tmp_path, arguments=['index'])

    assert command == [sys.executable, '-m', 'wily', '--cache', str(tmp_path), 'index']


def test_graphs_snippet_names_the_commit_and_modules_and_embeds_each_graph():
    """The snippet names what was measured and embeds every metric's graph."""
    graphs = ComplexityGraphs(
        commit='abc1234',
        commit_date='2026-10-23',
        commit_count=12,
        modules=('glitchygames/a.py', 'glitchygames/b.py'),
        graph_files={metric: graph_file_name(metric=metric) for metric, _label in METRICS},
    )

    snippet = graphs_snippet(graphs=graphs)

    assert snippet.startswith(
        'Generated at commit `abc1234` (2026-10-23) from all 12 commits. The modules, highest '
        'total cyclomatic complexity first: `glitchygames/a.py`, `glitchygames/b.py`.'
    )
    for metric, metric_label in METRICS:
        assert f'## {metric_label}' in snippet
        assert f'<iframe src="../graphs/{graph_file_name(metric=metric)}"' in snippet


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
                (checkout / 'glitchygames' / 'branchy.py').read_text(encoding='utf-8')
            )
            message = 'measuring failed'
            raise ComplexityGraphError(message)

    with pytest.raises(ComplexityGraphError, match='measuring failed'):
        measure_then_fail()

    assert checked_out_modules == [BRANCHY_MODULE]

    assert not checkout_directory.exists()
    assert len(git(repository=fixture_repository, arguments=['worktree', 'list']).splitlines()) == 1


def test_main_graphs_the_fixture_repositorys_history(fixture_repository, tmp_path, mocker):
    """Running main graphs every metric for the ranked modules, loading plotly.js from jsDelivr."""
    graphs_directory = tmp_path / 'graphs'
    graphs_directory.mkdir()
    stale_graph = graphs_directory / 'glitchygames_old_module_py_raw_loc.html'
    stale_graph.write_text('a graph of a module that left the ranking', encoding='utf-8')
    mocker.patch.object(generate_complexity_graphs, 'PROJECT_ROOT', fixture_repository)
    mocker.patch.object(generate_complexity_graphs, 'GRAPHS_DIR', graphs_directory)
    head_commit = git(repository=fixture_repository, arguments=['log', '-1', '--format=%h'])

    main()

    assert not stale_graph.exists()
    for metric, _label in METRICS:
        html = (graphs_directory / graph_file_name(metric=metric)).read_text(encoding='utf-8')
        assert 'src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@' in html
        assert 'cdn.plot.ly' not in html
        # Both modules are graphed (simple.py's line too)
        # (plotly escapes the trace names' slashes in its JSON)
        assert '"name":"glitchygames\\u002fsimple.py"' in html
        assert '"name":"glitchygames\\u002fbranchy.py"' in html
    snippet = (graphs_directory / GRAPHS_SNIPPET_NAME).read_text(encoding='utf-8')
    # branchy.py (complexity 3) ranks before simple.py (1); radon reports nothing for the empty
    # __init__.py, so it is not ranked
    assert f'Generated at commit `{head_commit.strip()}` ' in snippet
    assert (
        'from all 2 commits. The modules, highest total cyclomatic complexity first: '
        '`glitchygames/branchy.py`, `glitchygames/simple.py`.'
    ) in snippet
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
    assert 'git worktree add --detach' in capsys.readouterr().err


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


def test_the_mkdocs_hook_generates_the_graphs_before_a_build(fixture_repository, tmp_path, mocker):
    """Mkdocs's on_pre_build generates the graphs through the script it loads by path."""
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

    assert (graphs_directory / GRAPHS_SNIPPET_NAME).is_file()
    assert (graphs_directory / GENERATED_FROM_NAME).is_file()
    assert (tmp_path / 'metrics' / performance_script.SNIPPET_NAME).is_file()


def test_the_mkdocs_hook_stops_the_build_when_the_generation_fails(tmp_path, mocker):
    """A failed tool becomes mkdocs's PluginError, which stops the build with the tool's output."""
    graph_script = mkdocs_hooks.load_graph_script()
    not_a_repository = tmp_path / 'not-a-repository'
    not_a_repository.mkdir()
    mocker.patch.object(graph_script, 'PROJECT_ROOT', not_a_repository)
    mocker.patch.object(graph_script, 'GRAPHS_DIR', tmp_path / 'graphs')

    with pytest.raises(
        PluginError, match='Could not generate the complexity graphs: git rev-parse'
    ):
        mkdocs_hooks.on_pre_build(config=MkDocsConfig())


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

    module.cached_lookup = cached_lookup
    sys.modules[name] = module
    argument = CachedArgument()
    cached_lookup(argument)
    return module, weakref.ref(argument)


def test_the_mkdocs_hook_frees_the_documentation_caches_after_a_build(mocker, tmp_path):
    """After a build, griffe's and mkdocstrings' module caches are emptied, freeing their keys."""
    mocker.patch.dict(sys.modules)
    # No browser games built: the hook copies none into the (relative) default site_dir
    mocker.patch.object(mkdocs_hooks, 'BROWSER_GAMES_DIRECTORY', tmp_path / 'no games')
    module, key = module_with_a_filled_cache(name='griffe._fake_extension')

    mkdocs_hooks.on_post_build(config=MkDocsConfig())
    gc.collect()

    assert module.cached_lookup.cache_info().currsize == 0
    assert key() is None


def test_the_mkdocs_hook_leaves_other_modules_caches_alone(mocker, tmp_path):
    """Only griffe's and mkdocstrings' caches are emptied."""
    mocker.patch.dict(sys.modules)
    # No browser games built: the hook copies none into the (relative) default site_dir
    mocker.patch.object(mkdocs_hooks, 'BROWSER_GAMES_DIRECTORY', tmp_path / 'no games')
    module, key = module_with_a_filled_cache(name='unrelated_package.lookups')

    mkdocs_hooks.on_post_build(config=MkDocsConfig())

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
