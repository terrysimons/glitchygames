# ruff: noqa: D100, D103

from nox_poetry import Session, session


# @session(python=['3.9', '3.10', '3.11', '3.12'], reuse_venv=False)
@session(python=["3.13"], reuse_venv=False)
def lint_and_test(session: Session) -> None:
    session.run("poetry", "install", "--no-root", external=True)

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
