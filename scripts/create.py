#!/usr/bin/env python3
"""Create Glitchy Games template game."""

import argparse
import logging

from glitchygames import templates

LOG = logging.getLogger(__name__)


def get_args() -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        None

    Returns:
        argparse.Namespace: The parsed arguments.

    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-l', '--list', action='store_true', required=False, help='list available templates',
    )
    parser.add_argument(
        '-t', '--template', choices=templates.get_templates(), nargs='?', help='The template to use',
    )
    return parser.parse_args()


def main() -> None:
    """Run the main application."""
    args = get_args()

    if args.list:
        for template_name in templates.get_templates():
            LOG.info(template_name)
    elif args.template == 'pong':
        templates.build('pong')


if __name__ == '__main__':
    main()
