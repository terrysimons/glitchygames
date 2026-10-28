"""Run the text input demo as ``python -m text_input_demo``, as its console script runs it.

A package's ``__init__`` never runs as ``__main__``, so the module's old
``if __name__ == '__main__'`` (``python -m glitchygames.examples.text_input_demo``) lives here now.
"""

from text_input_demo import main

if __name__ == '__main__':
    main()
