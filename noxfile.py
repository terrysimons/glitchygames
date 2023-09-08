# ruff: noqa: D100, D103
from nox_poetry import session


@session(python=['3.9', '3.10', '3.11'], reuse_venv=True)
def lint_and_test(session: session.Session) -> None:

    # What's this?
    session.install('.[dev]')
    session.install('poetry', '.')
    session.install('pylama', '.')
    session.run('poetry', 'build', external=True)
    session.run('poetry', 'install', external=True)
    # session.run("pylama", "-o", "pyproject.toml", external=True)
    session.run('ruff', 'tests', external=True)
    session.run('ruff', 'noxfile.py', external=True)
    session.run('ruff', 'glitchygames', external=True)
    session.run('ruff', 'scripts', external=True)
