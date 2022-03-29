#!/usr/bin/env python
from glitchygames import templates
import sys


if len(sys.argv) > 1 and sys.argv[-1].lower() == 'pong':
    templates.build('pong')
