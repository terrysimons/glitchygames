#!/usr/bin/env python3
"""Create Glitchy Games template game.

Building needs cookiecutter, the engine's ``templates`` extra: without it the command says so
(``pip install glitchygames[templates]``) and exits 1, never with a traceback. ``--list`` needs
nothing extra.

Usage:
    python -m scripts.create --list
    python -m scripts.create --template pong
"""

import argparse
import sys
from collections.abc import Sequence

from glitchygames import templates


def get_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        arguments: The command line (None: ``sys.argv[1:]``).

    Returns:
        argparse.Namespace: The parsed arguments.

    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-l',
        '--list',
        action='store_true',
        required=False,
        help='list available templates',
    )
    parser.add_argument(
        '-t',
        '--template',
        choices=templates.get_templates(),
        nargs='?',
        help='The template to use',
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the main application.

    Args:
        arguments: The command line (None: ``sys.argv[1:]``).

    Returns:
        The exit status: 0, or 1 when the templates extra is not installed.

    """
    args = get_args(arguments)

    if args.list:
        # Printed, not logged: nothing configured logging, so an INFO record showed nothing
        for template_name in templates.get_templates():
            sys.stdout.write(f'{template_name}\n')
    elif args.template == 'pong':
        try:
            templates.build('pong')
        except templates.TemplatesUnavailableError as error:
            sys.stderr.write(f'{error}\n')
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
