"""Run the joystick demo as ``python -m joystick_demo``, as its console script runs it.

A package's ``__init__`` never runs as ``__main__``, so the module's old
``if __name__ == '__main__'`` (``python -m glitchygames.examples.joystick_demo``) lives here now.
"""

from joystick_demo import main

if __name__ == '__main__':
    main()
