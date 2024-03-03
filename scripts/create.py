#!/usr/bin/env python3
"""Create Glitchy Games template game."""

import argparse

from glitchygames import templates


def get_args() -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        None

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-l', '--list', action='store_true', required=False, help='list available templates'
    )
    parser.add_argument(
        '-t', 'template', choices=templates.get_templates(), nargs='?', help='The template to use'
    )
    return parser.parse_args()


def main() -> None:
    """Run the main application."""
    args = get_args()

    if args.list:
        [print(x) for x in templates.get_templates()]  # noqa: T201
    elif args.template == 'pong':
        templates.build('pong')


if __name__ == '__main__':
    main()
