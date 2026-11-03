"""The suite runs git where each test says, never in the repository a git hook was started for.

Git exports the variables that locate a repository (``GIT_DIR``, ``GIT_WORK_TREE``, ...) to every
hook it runs (githooks(5)), so the pre-push hooks' test runs inherit them, and so does every git
command a test runs, wherever it points git. In the main checkout ``GIT_DIR`` is the relative
``.git``, which finds nothing from a test's temporary directory; in a worktree it is an absolute
path, so a test that runs git outside any repository found the worktree's instead (three tests
failed only when pushing from a worktree: ``test_code_tree.py``'s and two in
``test_generate_complexity_graphs.py``). The harness clears them before any test, xdist worker
or native run starts.
"""

from __future__ import annotations

import os

# The variables by which git finds a repository instead of searching from the working directory:
# see the git manual page, section The Git Repository
GIT_REPOSITORY_VARIABLES = (
    'GIT_DIR',
    'GIT_WORK_TREE',
    'GIT_INDEX_FILE',
    'GIT_COMMON_DIR',
    'GIT_OBJECT_DIRECTORY',
    'GIT_ALTERNATE_OBJECT_DIRECTORIES',
    'GIT_PREFIX',
)


def clear_git_repository_variables() -> tuple[str, ...]:
    """Remove git's repository-locating variables from this process's environment.

    Returns:
        The names that were set (and are now cleared).

    """
    cleared = tuple(name for name in GIT_REPOSITORY_VARIABLES if name in os.environ)
    for name in cleared:
        del os.environ[name]
    return cleared
