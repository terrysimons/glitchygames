"""Template building and discovery functions. Wraps cookiecutter."""

from pathlib import Path

from cookiecutter.main import cookiecutter

path = Path(__file__).parent


def get_templates() -> list[str]:
    """Return a list of templates.

    Returns:
        list: The templates.

    """
    contents = [item.name for item in path.iterdir()]
    return [x for x in contents if Path.is_dir(Path(path) / x) and not x.startswith('__')]


def build(template: str) -> None:
    """Build the project from the template, using cookiecutter."""
    try:
        # The templates can be from remote repositories also.  Use a .repo file to name the repo
        with Path.open(Path(path) / template / '.repo') as fh:
            template_loc = fh.readline()
    except FileNotFoundError:
        template_loc = str(Path(path) / template)
    cookiecutter(template_loc)
