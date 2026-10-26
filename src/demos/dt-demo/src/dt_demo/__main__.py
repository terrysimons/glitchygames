"""Run the dt demo as ``python -m dt_demo``, as the ``dt-demo`` console script runs it.

A package's ``__init__`` never runs as ``__main__``, so the module's old
``if __name__ == '__main__'`` (``python -m glitchygames.examples.dt_demo``) lives here now.
"""

from dt_demo import main

if __name__ == '__main__':
    main()
