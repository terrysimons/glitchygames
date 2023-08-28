import os.path
from pathlib import Path

from cookiecutter.main import cookiecutter

path = os.path.dirname(__file__)


def get_templates():
    """Returns a list of templates"""
    contents = os.listdir(path)
    return [x for x in contents if Path.is_dir(os.path.join(path, x)) and not x.startswith('__')]


def build(template):
    """Builds the project from the template"""

    try:
        # The templates can be from remote repositories also.  Use a .repo file to name the repo
        with open(os.path.join(path, template, '.repo')) as fh:
            template_loc = fh.readline()
    except FileNotFoundError:
        template_loc = os.path.join(path, template)
    cookiecutter(template_loc)
