from cookiecutter.main import cookiecutter
import os.path

path = os.path.dirname(__file__)


def get_templates():
    """Returns a list of templates"""
    contents = os.listdir(path)
    return [x for x in contents if os.path.isdir(os.path.join(path, x)) and not x.startswith('__')]


def build(template):
    """Builds the project from the template"""
    cookiecutter(os.path.join(path, template))
