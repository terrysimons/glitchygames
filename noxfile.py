# ruff: noqa: D100, D103

from nox_poetry import Session, session


# @session(python=['3.9', '3.10', '3.11', '3.12'], reuse_venv=False)
@session(python=["3.13"], reuse_venv=False)
def lint_and_test(session: Session) -> None:
    session.run("poetry", "install", external=True)

    # Run tests with coverage
    session.run(
        "pytest",
        "--cov=glitchygames",
        "--cov-report=term-missing",
        "--cov-report=html",
        external=True,
    )

    # Sort imports (not supported by ruff format yet)
    session.run("ruff", "check", "--select", "I", "--fix", "noxfile.py", external=True)
    session.run("ruff", "check", "--select", "I", "--fix", "glitchygames", external=True)
    session.run("ruff", "check", "--select", "I", "--fix", "scripts", external=True)
    session.run("ruff", "check", "--select", "I", "--fix", "tests", external=True)

    session.run("pyright", external=True)

    # Format code (ruff format is mostly black style)
    session.run("ruff", "format", "noxfile.py", external=True)
    session.run("ruff", "format", "glitchygames", external=True)
    session.run("ruff", "format", "scripts", external=True)
    session.run("ruff", "format", "tests", external=True)

    # Lint code
    session.run("ruff", "check", "noxfile.py", external=True)
    session.run("ruff", "check", "glitchygames", external=True)
    session.run("ruff", "check", "scripts", external=True)
    session.run("ruff", "check", "tests", external=True)

    # Lint docs
    session.run("mkdocs", "build", "--strict", external=True)


@session(python=["3.13"], reuse_venv=False)
def security_scan(session: Session) -> None:
    """Run security scanning tools."""
    session.run("poetry", "install", external=True)

    # Run bandit security scan
    session.run(
        "bandit",
        "-r",
        "glitchygames",
        "-f",
        "json",
        "-o",
        "bandit-report.json",
        external=True,
    )
    session.run("bandit", "-r", "glitchygames", external=True)

    # Run safety check for known vulnerabilities
    session.run("safety", "check", "--json", external=True)
    session.run("safety", "check", external=True)


@session(python=["3.13"], reuse_venv=False)
def performance_test(session: Session) -> None:
    """Run performance benchmarks."""
    session.run("poetry", "install", external=True)

    # Run performance tests with pytest-benchmark
    session.run("pytest", "--benchmark-only", "--benchmark-save=baseline", "tests/", external=True)


@session(python=["3.13"], reuse_venv=False)
def coverage_report(session: Session) -> None:
    """Generate detailed coverage report."""
    session.run("poetry", "install", external=True)

    # Run tests with coverage
    session.run(
        "pytest",
        "--cov=glitchygames",
        "--cov-report=html",
        "--cov-report=term-missing",
        external=True,
    )

    # Generate coverage report
    session.run("coverage", "report", "--show-missing", external=True)
    session.run("coverage", "html", external=True)
