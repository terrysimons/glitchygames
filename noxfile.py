"""Nox session definitions for linting, testing, security scanning, and benchmarks."""

import os
import shutil
from pathlib import Path

import nox

# Use uv as the venv backend so nox sessions get their own isolated venvs
# managed by uv, without touching the project's .venv.
nox.options.default_venv_backend = 'uv'

# Common install target — all extras so every tool can resolve imports.
# Update this if new [project.optional-dependencies] sections are added.
_ALL_EXTRAS = '.[api,dev,docs]'

_CODE_DIRS = ['noxfile.py', 'glitchygames', 'scripts', 'tests']


# ---------------------------------------------------------------------------
# Helper functions (reusable logic, not sessions themselves)
# ---------------------------------------------------------------------------


def _format_code(session: nox.Session) -> None:
    """Format Python code with ruff (import sorting + black-style formatting)."""
    for target in _CODE_DIRS:
        session.run('ruff', 'check', '--select', 'I', '--fix', target)
    for target in _CODE_DIRS:
        session.run('ruff', 'format', target)


def _format_toml(session: nox.Session) -> None:
    """Format TOML files with taplo."""
    session.run('taplo', 'format', external=True)


def _lint_code(session: nox.Session) -> None:
    """Lint Python code with ruff."""
    session.run('ruff', 'check', *_CODE_DIRS)


def _lint_docs(session: nox.Session) -> None:
    """Lint documentation with mkdocs strict build."""
    session.run('mkdocs', 'build', '--strict')


def _lint_yaml(session: nox.Session) -> None:
    """Lint YAML files with yamllint."""
    session.run('yamllint', '--strict', '.', external=True)


def _lint_circleci(session: nox.Session) -> None:
    """Validate CircleCI configuration."""
    if os.environ.get('CIRCLECI') == 'true':
        session.log(
            'Running inside CircleCI; skipping config validation'
            ' (agent binary does not support it).'
        )
        return
    if not shutil.which('circleci'):
        session.log('circleci CLI not found on PATH; skipping config validation.')
        return
    session.run('circleci', 'config', 'validate', external=True)


def _lint_github_actions(session: nox.Session) -> None:
    """Lint GitHub Actions workflows with actionlint."""
    if not Path('.github/workflows').is_dir():
        session.log('No .github/workflows/ directory found; skipping actionlint.')
        return
    if not shutil.which('actionlint'):
        session.log('actionlint not found on PATH; skipping.')
        return
    session.run('actionlint', external=True)


def _lint_toml(session: nox.Session) -> None:
    """Lint TOML files with taplo."""
    session.run('taplo', 'lint', external=True)


def _lint_dependencies(session: nox.Session) -> None:
    """Check for dependency issues with deptry."""
    session.run('deptry', '.')


def _lint_dead_code(session: nox.Session) -> None:
    """Detect dead code with vulture."""
    session.run('vulture', 'glitchygames', 'vulture_whitelist.py', '--min-confidence=80')


def _lint_cves(session: nox.Session) -> None:
    """Audit dependencies for known CVEs with pip-audit."""
    import tempfile

    # Export requirements to a temp file (cross-platform; /dev/stdin doesn't exist on Windows)
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.txt',
        delete=False,
        encoding='utf-8',
    ) as tmp:
        tmp_path = tmp.name
    try:
        session.run(
            'uv',
            'export',
            '--quiet',
            '--no-emit-project',
            '--output-file',
            tmp_path,
            external=True,
        )
        session.run(
            'pip-audit',
            '--requirement',
            tmp_path,
            '--require-hashes',
            '--disable-pip',
            '--ignore-vuln',
            'CVE-2026-2473',
            '--ignore-vuln',
            'CVE-2026-4539',
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Aggregate sessions
# ---------------------------------------------------------------------------


@nox.session(python=['3.14'], reuse_venv=False, name='format')
def format_all(session: nox.Session) -> None:
    """Run all formatters (code + TOML)."""
    session.install(_ALL_EXTRAS)
    _format_code(session)
    _format_toml(session)


@nox.session(python=['3.14'], reuse_venv=False, name='lint')
def lint_all(session: nox.Session) -> None:
    """Run all linters (code, docs, YAML, TOML, deps, dead code, CVEs)."""
    session.install(_ALL_EXTRAS)
    _lint_code(session)
    _lint_docs(session)
    _lint_yaml(session)
    _lint_circleci(session)
    _lint_github_actions(session)
    _lint_toml(session)
    _lint_dependencies(session)
    _lint_dead_code(session)
    _lint_cves(session)


# ---------------------------------------------------------------------------
# Individual format sessions
# ---------------------------------------------------------------------------


@nox.session(python=['3.14'], reuse_venv=False, name='format-code', default=False)
def format_code(session: nox.Session) -> None:
    """Format Python code with ruff (import sorting + black-style formatting)."""
    session.install(_ALL_EXTRAS)
    _format_code(session)


@nox.session(venv_backend='none', name='format-toml', default=False)
def format_toml(session: nox.Session) -> None:
    """Format TOML files with taplo."""
    _format_toml(session)


# ---------------------------------------------------------------------------
# Individual lint sessions
# ---------------------------------------------------------------------------


@nox.session(python=['3.14'], reuse_venv=False, name='lint-code', default=False)
def lint_code(session: nox.Session) -> None:
    """Lint Python code with ruff."""
    session.install(_ALL_EXTRAS)
    _lint_code(session)


@nox.session(python=['3.14'], reuse_venv=False, name='lint-docs', default=False)
def lint_docs(session: nox.Session) -> None:
    """Lint documentation with mkdocs strict build."""
    session.install(_ALL_EXTRAS)
    _lint_docs(session)


@nox.session(venv_backend='none', name='lint-yaml', default=False)
def lint_yaml(session: nox.Session) -> None:
    """Lint YAML files with yamllint."""
    _lint_yaml(session)


@nox.session(venv_backend='none', name='lint-circleci', default=False)
def lint_circleci(session: nox.Session) -> None:
    """Validate CircleCI configuration."""
    _lint_circleci(session)


@nox.session(venv_backend='none', name='lint-github-actions', default=False)
def lint_github_actions(session: nox.Session) -> None:
    """Lint GitHub Actions workflows with actionlint."""
    _lint_github_actions(session)


@nox.session(venv_backend='none', name='lint-ci-config', default=False)
def lint_ci_config(session: nox.Session) -> None:
    """Validate all CI configurations (CircleCI + GitHub Actions)."""
    _lint_circleci(session)
    _lint_github_actions(session)


@nox.session(venv_backend='none', name='lint-toml', default=False)
def lint_toml(session: nox.Session) -> None:
    """Lint TOML files with taplo."""
    _lint_toml(session)


@nox.session(python=['3.14'], reuse_venv=False, name='lint-dependencies', default=False)
def lint_dependencies(session: nox.Session) -> None:
    """Check for dependency issues with deptry."""
    session.install(_ALL_EXTRAS)
    _lint_dependencies(session)


@nox.session(python=['3.14'], reuse_venv=False, name='lint-dead-code', default=False)
def lint_dead_code(session: nox.Session) -> None:
    """Detect dead code with vulture."""
    session.install(_ALL_EXTRAS)
    _lint_dead_code(session)


@nox.session(python=['3.14'], reuse_venv=False, name='lint-cves', default=False)
def lint_cves(session: nox.Session) -> None:
    """Audit dependencies for known CVEs with pip-audit."""
    session.install(_ALL_EXTRAS)
    _lint_cves(session)


# ---------------------------------------------------------------------------
# Static type analysis
# ---------------------------------------------------------------------------


def _static_analysis_basedpyright(session: nox.Session) -> None:
    """Run static type analysis with basedpyright."""
    session.run('basedpyright')


def _static_analysis_ty(session: nox.Session) -> None:
    """Run static type analysis with ty (Astral's type checker)."""
    session.run('ty', 'check')


@nox.session(python=['3.14'], reuse_venv=False, name='static-analysis-basedpyright', default=False)
def static_analysis_basedpyright(session: nox.Session) -> None:
    """Run static type analysis with basedpyright."""
    session.install(_ALL_EXTRAS)
    _static_analysis_basedpyright(session)


@nox.session(python=['3.14'], reuse_venv=False, name='static-analysis-ty', default=False)
def static_analysis_ty(session: nox.Session) -> None:
    """Run static type analysis with ty (Astral's type checker)."""
    session.install(_ALL_EXTRAS)
    _static_analysis_ty(session)


@nox.session(python=['3.14'], reuse_venv=False, name='static-analysis')
def static_analysis(session: nox.Session) -> None:
    """Run all static type analysis (basedpyright + ty)."""
    session.install(_ALL_EXTRAS)
    _static_analysis_basedpyright(session)
    _static_analysis_ty(session)


# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------


@nox.session(python=['3.14'], reuse_venv=False)
def test(session: nox.Session) -> None:
    """Run tests."""
    session.install(_ALL_EXTRAS)

    # Use dummy SDL video driver in CI/headless environments to prevent segfaults.
    # This is set here so it applies before pygame is imported by any test worker.
    env = {}
    if os.environ.get('CI') == 'true' or os.environ.get('SDL_VIDEODRIVER') == 'dummy':
        env['SDL_VIDEODRIVER'] = 'dummy'

    # In CI, limit xdist workers to half the CPU count to avoid resource exhaustion.
    # Locally, -n auto (from pyproject.toml addopts) uses all cores.
    args: list[str] = []
    if os.environ.get('CI') == 'true':
        import multiprocessing

        half_cpus = max(1, multiprocessing.cpu_count() // 2)
        args.extend(['-n', str(half_cpus)])

    # Run tests with coverage — all coverage reports (term, html, xml, json, lcov)
    # are generated by pytest-cov via pyproject.toml addopts.
    # JUnit XML output is stored for CI test result ingestion.
    session.run('pytest', *args, env=env)


@nox.session(python=['3.14'], reuse_venv=False, name='performance-test', default=False)
def performance_test(session: nox.Session) -> None:
    """Run performance benchmarks."""
    session.install(_ALL_EXTRAS)

    # Run performance tests with pytest-benchmark
    # Override addopts to avoid conflict with --cov flags from pyproject.toml
    session.run(
        'pytest',
        '-o',
        'addopts=',
        '-p',
        'no:xdist',
        '--benchmark-only',
        '--benchmark-save=baseline',
        'tests/',
    )


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


def _bandit_scan(session: nox.Session) -> None:
    """Run bandit security scan (exclude_dirs configured in pyproject.toml)."""
    session.run(
        'bandit',
        '-c',
        'pyproject.toml',
        '-ll',  # Medium+ severity
        '-ii',  # Medium+ confidence
        '-r',
        'glitchygames',
        '-f',
        'json',
        '-o',
        'bandit-report.json',
    )


def _safety_scan(session: nox.Session) -> None:
    """Run safety check for known vulnerabilities."""
    if not os.getenv('SAFETY_API_KEY'):
        session.log('SAFETY_API_KEY not set; skipping Safety scan.')
        return

    session.run(
        'safety',
        'scan',
        '--exclude',
        '.venv',
        '--exclude',
        '.nox',
        '--output',
        'screen',
        '--save-as',
        'json',
        'safety-report.json',
    )


@nox.session(python=['3.14'], reuse_venv=False, name='bandit-scan', default=False)
def bandit_scan(session: nox.Session) -> None:
    """Run bandit security scan."""
    session.install(_ALL_EXTRAS)
    _bandit_scan(session)


@nox.session(python=['3.14'], reuse_venv=False, name='safety-scan', default=False)
def safety_scan(session: nox.Session) -> None:
    """Run safety vulnerability scan."""
    session.install(_ALL_EXTRAS)
    _safety_scan(session)


@nox.session(python=['3.14'], reuse_venv=False, name='security-scan', default=False)
def security_scan(session: nox.Session) -> None:
    """Run all security scanning tools (bandit + safety)."""
    session.install(_ALL_EXTRAS)
    _bandit_scan(session)
    _safety_scan(session)


# ---------------------------------------------------------------------------
# Code Complexity
# ---------------------------------------------------------------------------


@nox.session(python=['3.14'], reuse_venv=False, name='code-complexity', default=False)
def code_complexity(session: nox.Session) -> None:
    """Analyze code complexity with wily and generate optional HTML graphs.

    Tools: wily (complexity analysis), generate_complexity_graphs.py (HTML graph generation)

    Usage:
        nox -s code-complexity              # Build cache + show diff vs previous revision
        nox -s code-complexity -- --graphs  # Also generate HTML graphs for docs
        nox -s code-complexity -- --rank    # Show files ranked by complexity
    """
    session.install(_ALL_EXTRAS)

    # Build the wily cache from git history
    session.run('wily', 'build')

    # Show complexity diff against previous revision for all source directories
    session.run('wily', 'diff', 'glitchygames/', 'scripts/', '--changes-only', success_codes=[0, 1])

    # Optional: generate graphs for documentation
    if '--graphs' in session.posargs:
        session.run('python', 'scripts/generate_complexity_graphs.py')

    # Optional: show file rankings
    if '--rank' in session.posargs:
        session.run('wily', 'rank', '--limit', '20', 'glitchygames/', 'cyclomatic.complexity')
