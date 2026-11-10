"""Run the Sound Board demo as ``python -m sound_board_demo``, as its console script runs it.

A package's ``__init__`` never runs as ``__main__``, so the run-as-a-script entry lives here.
"""

from sound_board_demo import main

if __name__ == '__main__':
    main()
