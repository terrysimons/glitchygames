"""Template building and discovery functions. Wraps cookiecutter.

cookiecutter is the ``templates`` extra (``pip install glitchygames[templates]``), not a core
dependency: without it the templates are still listed (``get_templates``), and ``build`` raises
``TemplatesUnavailableError`` naming the extra.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

cookiecutter: Callable[..., Any] | None
try:
    from cookiecutter.main import cookiecutter
except ImportError:  # the templates extra is not installed
    cookiecutter = None

path = Path(__file__).parent

TEMPLATES_EXTRA_MISSING_MESSAGE = (
    'Building a project from a template needs cookiecutter, which the templates extra '
    'installs: pip install glitchygames[templates]'
)


class TemplatesUnavailableError(ImportError):
    """cookiecutter, the ``templates`` extra, is not installed."""


def get_templates() -> list[str]:
    """Return a list of templates.

    Returns:
        list: The templates.

    """
    contents = [item.name for item in path.iterdir()]
    return [x for x in contents if Path.is_dir(Path(path) / x) and not x.startswith('__')]


def build(template: str) -> None:
    """Build the project from the template, using cookiecutter.

    Raises:
        TemplatesUnavailableError: cookiecutter (the ``templates`` extra) is not installed.

    """
    if cookiecutter is None:
        raise TemplatesUnavailableError(TEMPLATES_EXTRA_MISSING_MESSAGE)
    try:
        # The templates can be from remote repositories also.  Use a .repo file to name the repo
        with Path.open(Path(path) / template / '.repo') as fh:
            # Without the line's newline, which cookiecutter would take as part of the
            # location (BUGS.md #107)
            template_loc = fh.readline().strip()
    except FileNotFoundError:
        template_loc = str(Path(path) / template)
    cookiecutter(template_loc)
