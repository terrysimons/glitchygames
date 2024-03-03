# ruff: noqa: D100, D103
from nox_poetry import session


# @session(python=['3.9', '3.10', '3.11', '3.12'], reuse_venv=True)
@session(python=['3.12'], reuse_venv=False)
def lint_and_test(session: object) -> None:
    # What's this?
    session.install('.[dev]')
    # session.install('poetry', '.')
    # session.install('pylama', '.')
    session.run('poetry', 'build', external=True)
    session.run('poetry', 'install', external=True)
    # session.run('ruff', 'tests', external=True)
    session.run('ruff', 'format', 'noxfile.py', external=True)
    session.run('ruff', 'format', 'glitchygames', external=True)
    session.run('ruff', 'format', 'scripts', external=True)
    session.run('ruff', 'check', 'noxfile.py', external=True)
    session.run('ruff', 'check', 'glitchygames', external=True)
    session.run('ruff', 'check', 'scripts', external=True)
    session.run('mkdocs', 'build', '--strict', external=True)
    # griffe check -a <branch> glitchygames
    # or without the -a flag if tags exist
