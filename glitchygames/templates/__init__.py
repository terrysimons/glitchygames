"""This module helps build a project from templates. It's a wrapper around cookiecutter."""

import os.path
from pathlib import Path

from cookiecutter.main import cookiecutter

path = Path(__file__).parent


def get_templates() -> list:
    """Returns a list of templates."""
    contents = os.listdir(path)
    return [x for x in contents if Path.is_dir(Path(path) / x) and not x.startswith('__')]


def build(template: str) -> None:
    """Builds the project from the template, using cookiecutter."""
    try:
        # The templates can be from remote repositories also.  Use a .repo file to name the repo
        with Path.open(Path(path) / template / '.repo') as fh:
            template_loc = fh.readline()
    except FileNotFoundError:
        template_loc = Path(path) / template
    cookiecutter(template_loc)
