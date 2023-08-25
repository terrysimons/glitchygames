import os.path

from cookiecutter.main import cookiecutter

path = os.path.dirname(__file__)


def get_templates():
    """Returns a list of templates"""
    contents = os.listdir(path)
    return [x for x in contents if os.path.isdir(os.path.join(path, x)) and not x.startswith('__')]


def build(template):
    """Builds the project from the template"""

    try:
        # The templates can be from remote repositories also.  Use a .repo file to name the repo
        template_loc = open(os.path.join(path, template, '.repo')).readline()
    except FileNotFoundError:
        template_loc = os.path.join(path, template)
    cookiecutter(template_loc)
