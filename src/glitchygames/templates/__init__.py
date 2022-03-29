from cookiecutter.main import cookiecutter
import os.path

path = os.path.dirname(__file__)


def build(template):
    cookiecutter(os.path.join(path, template))
