"""Run PaddleSlap as ``python -m paddleslap``, as the ``paddleslap`` console script runs it.

A package's ``__init__`` never runs as ``__main__``, so the module's old
``if __name__ == '__main__'`` (``python -m glitchygames.examples.paddleslap``) lives here now.
"""

from paddleslap import main

if __name__ == '__main__':
    main()
