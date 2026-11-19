"""Run Zombies Ain't My Neighbors as ``python -m zombies_aint_my_neighbors``.

A package's ``__init__`` never runs as ``__main__``, so the run-as-a-script entry lives here.
"""

from zombies_aint_my_neighbors import main

if __name__ == '__main__':
    main()
