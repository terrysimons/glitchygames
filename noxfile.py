"""Nox session definitions for linting, testing, security scanning, and benchmarks."""

import nox

# Use uv as the venv backend so nox sessions get their own isolated venvs
# managed by uv, without touching the project's .venv.
nox.options.default_venv_backend = 'uv'


# @nox.session(python=['3.9', '3.10', '3.11', '3.12'], reuse_venv=False)
@nox.session(python=['3.13'], reuse_venv=False)
def lint_and_test(session: nox.Session) -> None:
    """Run linting and tests with coverage."""
    # Install with all extras into the nox session venv.
    # Update this if new [project.optional-dependencies] sections are added.
    session.install('.[api,dev,docs]')

    # Run tests with coverage
    # Override addopts to avoid duplicate --cov flags from pyproject.toml
    session.run(
        'pytest'
    )

    # Sort imports (not supported by ruff format yet)
    session.run(
        'ruff',
        'check',
        '--select',
        'I',
        '--fix',
        'noxfile.py',
    )
    session.run(
        'ruff',
        'check',
        '--select',
        'I',
        '--fix',
        'glitchygames',
    )
    session.run(
        'ruff',
        'check',
        '--select',
        'I',
        '--fix',
        'scripts',
    )
    session.run(
        'ruff',
        'check',
        '--select',
        'I',
        '--fix',
        'tests',
    )

    session.run(
        'pyright',
    )

    # Format code (ruff format is mostly black style)
    session.run(
        'ruff',
        'format',
        'noxfile.py',
    )
    session.run(
        'ruff',
        'format',
        'glitchygames',
    )
    session.run(
        'ruff',
        'format',
        'scripts',
    )
    session.run(
        'ruff',
        'format',
        'tests',
    )

    # Lint code
    session.run(
        'ruff',
        'check',
        'noxfile.py',
    )
    session.run(
        'ruff',
        'check',
        'glitchygames',
    )
    session.run(
        'ruff',
        'check',
        'scripts',
    )
    session.run(
        'ruff',
        'check',
        'tests',
    )

    # Lint docs
    session.run(
        'mkdocs',
        'build',
        '--strict',
    )


@nox.session(python=['3.13'], reuse_venv=False)
def security_scan(session: nox.Session) -> None:
    """Run security scanning tools."""
    # Install with all extras into the nox session venv.
    # Update this if new [project.optional-dependencies] sections are added.
    session.install('.[api,dev,docs]')

    # Run bandit security scan
    # Exclude test dirs (B101 assert false positives) and skip B104 (0.0.0.0 bind is intentional)
    session.run(
        'bandit',
        '-r',
        'glitchygames',
        '--exclude', 'glitchygames/tests',
        '-s', 'B104',
        '-f', 'json',
        '-o', '/dev/stdout',
    )

    # Run safety check for known vulnerabilities
    # Exclude .venv and .nox to avoid scanning third-party packages
    session.run(
        'safety',
        'scan',
        '--exclude', '.venv',
        '--exclude', '.nox',
        '--json',
        '--output', '/dev/stdout',
    )


@nox.session(python=['3.13'], reuse_venv=False)
def performance_test(session: nox.Session) -> None:
    """Run performance benchmarks."""
    # Install with all extras into the nox session venv.
    # Update this if new [project.optional-dependencies] sections are added.
    session.install('.[api,dev,docs]')

    # Run performance tests with pytest-benchmark
    # Override addopts to avoid conflict with --cov flags from pyproject.toml
    session.run(
        'pytest',
        '-o', 'addopts=',
        '-p', 'no:xdist',
        '--benchmark-only',
        '--benchmark-save=baseline',
        'tests/',
    )


@nox.session(python=['3.13'], reuse_venv=False)
def coverage_report(session: nox.Session) -> None:
    """Generate detailed coverage report."""
    # Install with all extras into the nox session venv.
    # Update this if new [project.optional-dependencies] sections are added.
    session.install('.[api,dev,docs]')

    # Run tests with coverage
    # Override addopts to avoid duplicate --cov flags from pyproject.toml
    session.run(
        'pytest',
    )
