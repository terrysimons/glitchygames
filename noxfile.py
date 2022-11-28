from nox_poetry import session


@session(python=["3.8", "3.9", "3.10"], reuse_venv=True)
def lint_and_test(session):
    session.install(".[dev]")
    session.install("poetry", ".")
    session.install("pylama", ".")
    session.run("poetry", "build")
    session.run("poetry", "install")
    session.run("pylama", "-o", "pyproject.toml")
