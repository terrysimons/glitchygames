# ruff: noqa: D100, D103

import nox

# Use uv as the venv backend so nox sessions get their own isolated venvs
# managed by uv, without touching the project's .venv.
nox.options.default_venv_backend = "uv"


# @nox.session(python=['3.9', '3.10', '3.11', '3.12'], reuse_venv=False)
@nox.session(python=["3.13"], reuse_venv=False)
def lint_and_test(session: nox.Session) -> None:
    session.install(".[api,dev,docs]")

    # Run tests with coverage
    # Override addopts to avoid duplicate --cov flags from pyproject.toml
    session.run(
        "pytest",
        "-o", "addopts=",
        "--cov=glitchygames",
        "--cov-report=term-missing",
        "--cov-report=html",
    )

    # Sort imports (not supported by ruff format yet)
    session.run(
        "ruff",
        "check",
        "--select",
        "I",
        "--fix",
        "noxfile.py",
    )
    session.run(
        "ruff",
        "check",
        "--select",
        "I",
        "--fix",
        "glitchygames",
    )
    session.run(
        "ruff",
        "check",
        "--select",
        "I",
        "--fix",
        "scripts",
    )
    session.run(
        "ruff",
        "check",
        "--select",
        "I",
        "--fix",
        "tests",
    )

    session.run(
        "pyright",
    )

    # Format code (ruff format is mostly black style)
    session.run(
        "ruff",
        "format",
        "noxfile.py",
    )
    session.run(
        "ruff",
        "format",
        "glitchygames",
    )
    session.run(
        "ruff",
        "format",
        "scripts",
    )
    session.run(
        "ruff",
        "format",
        "tests",
    )

    # Lint code
    session.run(
        "ruff",
        "check",
        "noxfile.py",
    )
    session.run(
        "ruff",
        "check",
        "glitchygames",
    )
    session.run(
        "ruff",
        "check",
        "scripts",
    )
    session.run(
        "ruff",
        "check",
        "tests",
    )

    # Lint docs
    session.run(
        "mkdocs",
        "build",
        "--strict",
    )


@nox.session(python=["3.13"], reuse_venv=False)
def security_scan(session: nox.Session) -> None:
    """Run security scanning tools."""
    session.install(".[dev,docs,api]")

    # Run bandit security scan
    session.run(
        "bandit",
        "-r",
        "glitchygames",
        "-f",
        "json",
        "-o",
        "bandit-report.json",
    )
    session.run(
        "bandit",
        "-r",
        "glitchygames",
    )

    # Run safety check for known vulnerabilities
    session.run(
        "safety",
        "check",
        "--json",
    )
    session.run(
        "safety",
        "check",
    )


@nox.session(python=["3.13"], reuse_venv=False)
def performance_test(session: nox.Session) -> None:
    """Run performance benchmarks."""
    session.install(".[dev,docs,api]")

    # Run performance tests with pytest-benchmark
    # Override addopts to avoid conflict with --cov flags from pyproject.toml
    session.run(
        "pytest",
        "-o", "addopts=",
        "--benchmark-only",
        "--benchmark-save=baseline",
        "tests/",
    )


@nox.session(python=["3.13"], reuse_venv=False)
def coverage_report(session: nox.Session) -> None:
    """Generate detailed coverage report."""
    session.install(".[dev,docs,api]")

    # Run tests with coverage
    # Override addopts to avoid duplicate --cov flags from pyproject.toml
    session.run(
        "pytest",
        "-o", "addopts=",
        "--cov=glitchygames",
        "--cov-report=html",
        "--cov-report=term-missing",
    )

    # Generate coverage report
    session.run(
        "coverage",
        "report",
        "--show-missing",
    )
    session.run(
        "coverage",
        "html",
    )
