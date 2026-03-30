"""PyInstaller entry point for Bitmappy.

This thin wrapper exists because PyInstaller runs the entry script without
a parent package context, which breaks the relative imports inside
glitchygames.bitmappy.editor.  Importing through the package resolves that.
"""

from glitchygames.bitmappy import main

if __name__ == '__main__':
    main()
