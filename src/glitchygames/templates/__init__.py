"""Module for building projects from templates. It's a wrapper around cookiecutter.

cookiecutter is the ``templates`` extra: ``pip install glitchygames[templates]``.
"""

from glitchygames.templates.game import (
    TemplatesUnavailableError,
    build,
    get_templates,
    path,
)

__all__ = [
    'TemplatesUnavailableError',
    'build',
    'get_templates',
    'path',
]
