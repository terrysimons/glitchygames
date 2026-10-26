"""PyInstaller entry point for Bitmappy.

This thin wrapper exists because PyInstaller runs the entry script without
a parent package context, which breaks the relative imports inside
bitmappy.editor.  Importing through the package resolves that.
"""

import multiprocessing

if __name__ == '__main__':
    # Must come first. In the frozen app, multiprocessing starts child processes (Bitmappy's
    # AI worker, the resource tracker) by re-running this executable with its own arguments
    # (--multiprocessing-fork ..., -B -S -I -c ...). freeze_support() runs the child's task and
    # exits; without it the child would import Bitmappy and its argument parser would reject
    # those arguments. It does nothing when not frozen. (BUGS.md #47)
    multiprocessing.freeze_support()

    # Imported only after freeze_support(), so child processes never import Bitmappy
    from bitmappy import main

    main()
