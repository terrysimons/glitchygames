#!/usr/bin/env python
"""
Create Glitchy Games template game.
"""
import argparse
from glitchygames import templates


def get_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--list', action='store_true',  required=False, help='list available templates')
    parser.add_argument('template', choices=templates.get_templates(), nargs='?', help='The template to use')
    return parser.parse_args()


def main():
    args = get_args()

    if args.list:
        [print(x) for x in templates.get_templates()]
    elif args.template == 'pong':
        templates.build('pong')


if __name__ == '__main__':
    main()