"""Module for building projects from templates. It's a wrapper around cookiecutter."""

from glitchygames.templates.game import build, get_templates, path

__all__ = [
    'build',
    'get_templates',
    'path',
]
