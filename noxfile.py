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
    session.run(
        'bash',
        '-c',
        'uv export --quiet --no-emit-project'
        ' | pip-audit --requirement /dev/stdin'
        ' --require-hashes --disable-pip'
        ' --ignore-vuln CVE-2026-2473',
        external=True,
    )


# ---------------------------------------------------------------------------
# Aggregate sessions
# ---------------------------------------------------------------------------


@nox.session(python=['3.13'], reuse_venv=False, name='format')
def format_all(session: nox.Session) -> None:
    """Run all formatters (code + TOML)."""
    session.install(_ALL_EXTRAS)
    _format_code(session)
    _format_toml(session)


@nox.session(python=['3.13'], reuse_venv=False, name='lint')
def lint_all(session: nox.Session) -> None:
    """Run all linters (code, docs, YAML, TOML, CI configs, deps, dead code, CVEs)."""
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


@nox.session(python=['3.13'], reuse_venv=False, name='format-code')
def format_code(session: nox.Session) -> None:
    """Format Python code with ruff (import sorting + black-style formatting)."""
    session.install(_ALL_EXTRAS)
    _format_code(session)


@nox.session(venv_backend='none', name='format-toml')
def format_toml(session: nox.Session) -> None:
    """Format TOML files with taplo."""
    _format_toml(session)


# ---------------------------------------------------------------------------
# Individual lint sessions
# ---------------------------------------------------------------------------


@nox.session(python=['3.13'], reuse_venv=False, name='lint-code')
def lint_code(session: nox.Session) -> None:
    """Lint Python code with ruff."""
    session.install(_ALL_EXTRAS)
    _lint_code(session)


@nox.session(python=['3.13'], reuse_venv=False, name='lint-docs')
def lint_docs(session: nox.Session) -> None:
    """Lint documentation with mkdocs strict build."""
    session.install(_ALL_EXTRAS)
    _lint_docs(session)


@nox.session(venv_backend='none', name='lint-yaml')
def lint_yaml(session: nox.Session) -> None:
    """Lint YAML files with yamllint."""
    _lint_yaml(session)


@nox.session(venv_backend='none', name='lint-circleci')
def lint_circleci(session: nox.Session) -> None:
    """Validate CircleCI configuration."""
    _lint_circleci(session)


@nox.session(venv_backend='none', name='lint-github-actions')
def lint_github_actions(session: nox.Session) -> None:
    """Lint GitHub Actions workflows with actionlint."""
    _lint_github_actions(session)


@nox.session(venv_backend='none', name='lint-ci-config')
def lint_ci_config(session: nox.Session) -> None:
    """Validate all CI configurations (CircleCI + GitHub Actions)."""
    _lint_circleci(session)
    _lint_github_actions(session)


@nox.session(venv_backend='none', name='lint-toml')
def lint_toml(session: nox.Session) -> None:
    """Lint TOML files with taplo."""
    _lint_toml(session)


@nox.session(python=['3.13'], reuse_venv=False, name='lint-dependencies')
def lint_dependencies(session: nox.Session) -> None:
    """Check for dependency issues with deptry."""
    session.install(_ALL_EXTRAS)
    _lint_dependencies(session)


@nox.session(python=['3.13'], reuse_venv=False, name='lint-dead-code')
def lint_dead_code(session: nox.Session) -> None:
    """Detect dead code with vulture."""
    session.install(_ALL_EXTRAS)
    _lint_dead_code(session)


@nox.session(python=['3.13'], reuse_venv=False, name='lint-cves')
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


@nox.session(python=['3.13'], reuse_venv=False, name='static-analysis-basedpyright')
def static_analysis_basedpyright(session: nox.Session) -> None:
    """Run static type analysis with basedpyright."""
    session.install(_ALL_EXTRAS)
    _static_analysis_basedpyright(session)


@nox.session(python=['3.13'], reuse_venv=False, name='static-analysis-ty')
def static_analysis_ty(session: nox.Session) -> None:
    """Run static type analysis with ty (Astral's type checker)."""
    session.install(_ALL_EXTRAS)
    _static_analysis_ty(session)


@nox.session(python=['3.13'], reuse_venv=False, name='static-analysis')
def static_analysis(session: nox.Session) -> None:
    """Run all static type analysis (basedpyright + ty)."""
    session.install(_ALL_EXTRAS)
    _static_analysis_basedpyright(session)
    _static_analysis_ty(session)


# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------


@nox.session(python=['3.13'], reuse_venv=False)
def test(session: nox.Session) -> None:
    """Run tests."""
    session.install(_ALL_EXTRAS)

    # Use dummy SDL video driver in CI/headless environments to prevent segfaults.
    # This is set here so it applies before pygame is imported by any test worker.
    env = {}
    if os.environ.get('CI') == 'true' or os.environ.get('SDL_VIDEODRIVER') == 'dummy':
        env['SDL_VIDEODRIVER'] = 'dummy'

    # Run tests with coverage — all coverage reports (term, html, xml, json, lcov)
    # are generated by pytest-cov via pyproject.toml addopts.
    # JUnit XML output is stored for CI test result ingestion.
    session.run('pytest', env=env)


@nox.session(python=['3.13'], reuse_venv=False, name='performance-test')
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


@nox.session(python=['3.13'], reuse_venv=False, name='bandit-scan')
def bandit_scan(session: nox.Session) -> None:
    """Run bandit security scan."""
    session.install(_ALL_EXTRAS)
    _bandit_scan(session)


@nox.session(python=['3.13'], reuse_venv=False, name='safety-scan')
def safety_scan(session: nox.Session) -> None:
    """Run safety vulnerability scan."""
    session.install(_ALL_EXTRAS)
    _safety_scan(session)


@nox.session(python=['3.13'], reuse_venv=False, name='security-scan')
def security_scan(session: nox.Session) -> None:
    """Run all security scanning tools (bandit + safety)."""
    session.install(_ALL_EXTRAS)
    _bandit_scan(session)
    _safety_scan(session)
