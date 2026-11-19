"""Which cores run the game, its mirror and the AI, and the game's pinning of itself to its own.

The owner's placement (plans/lucid-circuit-linux.md, section 6.2): the game on the fastest core,
the mirror (the AI's headless copy of the game, Stage 4b) on the next, every AI unit on the rest.
The service's per-user setup (``setup.sh``) decides it and writes it to
``<user root>/config/cpu-placement.json`` (``ServiceLocations.cpu_placement_file``), shaped
``{"game": [0], "mirror": [1], "ai": [2, 3]}``; a one-core machine gets no file. The engine never
works the rule out for itself: a second copy of it would drift.

A game isn't a systemd unit, so it pins itself: on Linux only, and only for a live run with AI
(the run ``create_link`` gives a link) that isn't an inner context, which shares the process with
other games. ``pin_the_game_to_its_cores`` is that step, called by the engine once the link is made.
By then ``pygame.init()`` has started SDL's audio thread, so every thread listed in
``/proc/self/task`` is moved; a thread started later inherits the affinity of the thread that
starts it. A placement naming a core this process may not run on (one the machine lacks, or one
outside its cgroup's allowed cores), or a placement that can't be read, is a warning and an
unpinned game, never a crash.
"""

from __future__ import annotations

import functools
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from glitchygames.render_target import is_inner_context

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.ai_link import AiLink

LOG = logging.getLogger(__name__)

# Linux lists each of this process's threads here, one folder named by its thread id
THIS_PROCESS_TASK_DIRECTORY = Path('/proc/self/task')

# A core's number, as the kernel numbers them
CoreNumber = Annotated[int, Field(ge=0)]
# A part's cores: at least one
CoreNumbers = Annotated[frozenset[CoreNumber], Field(min_length=1)]


class CpuPlacement(BaseModel):
    """The cores each part runs on, as ``setup.sh`` wrote them.

    Strict, so a core written as a string or ``true`` is refused rather than read as a number.
    """

    model_config = ConfigDict(frozen=True, extra='forbid', strict=True)

    game: CoreNumbers
    mirror: CoreNumbers
    ai: CoreNumbers


def read_cpu_placement(*, path: Path) -> CpuPlacement | None:
    """Read the placement ``setup.sh`` wrote.

    Args:
        path: The placement file (``ServiceLocations.cpu_placement_file``).

    Returns:
        The placement; None when there is no file (nothing is pinned on this machine), and None
        with a warning when the file can't be read or isn't a valid placement (bytes that aren't
        UTF-8 or aren't JSON included: pydantic reports both as a ``ValidationError``).

    """
    try:
        contents = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as error:
        LOG.warning('Could not read the CPU placement %s (%s): the game is not pinned', path, error)
        return None
    try:
        return CpuPlacement.model_validate_json(contents)
    except ValidationError as error:
        LOG.warning('The CPU placement %s is not valid, so the game is not pinned: %s', path, error)
        return None


def pin_this_process(
    *,
    cores: frozenset[int],
    task_directory: Path = THIS_PROCESS_TASK_DIRECTORY,
    set_affinity: Callable[[int, set[int]], None] | None = None,
    read_allowed_cores: Callable[[], set[int]] | None = None,
) -> bool:
    """Move every thread of this process onto these cores.

    First the cores are checked against the ones this process may run on: the kernel pins a
    mask to whichever of its cores are online and allowed, and refuses (``EINVAL``) only a mask
    with none, so ``{0, 7}`` on a four-core machine would quietly become ``{0}``. Any core outside
    them is a warning naming it, and no thread moves.

    Then each thread is moved in turn, by thread id. A thread that ends between the listing and
    its turn is passed over. Any other refusal is a warning and stops there, without rollback:
    the threads before it stay on the new cores, the rest where they were. Never raises.

    Args:
        cores: The cores to run on.
        task_directory: The folder listing the process's threads by id.
        set_affinity: Sets one thread's cores; None for ``os.sched_setaffinity`` (Linux only),
            resolved at call time.
        read_allowed_cores: Returns the cores this process may run on; None for
            ``os.sched_getaffinity(0)`` (Linux only), resolved at call time.

    Returns:
        Whether every thread still running was moved.

    """
    if set_affinity is None or read_allowed_cores is None:
        if sys.platform != 'linux':
            LOG.warning('Pinning threads to cores needs Linux; this is %s', sys.platform)
            return False
        set_affinity = set_affinity or os.sched_setaffinity
        read_allowed_cores = read_allowed_cores or functools.partial(os.sched_getaffinity, 0)
    try:
        allowed_cores = read_allowed_cores()
    except OSError as error:
        LOG.warning(
            'Could not read the cores this process may use (%s): the game is not pinned', error
        )
        return False
    if unavailable_cores := cores - allowed_cores:
        LOG.warning(
            'This process may not run on cores %s (it may use %s): the game is not pinned',
            sorted(unavailable_cores),
            sorted(allowed_cores),
        )
        return False
    try:
        thread_ids = sorted(
            int(entry.name) for entry in task_directory.iterdir() if entry.name.isdigit()
        )
    except OSError as error:
        LOG.warning(
            'Could not list the threads in %s (%s): the game is not pinned', task_directory, error
        )
        return False
    for thread_id in thread_ids:
        try:
            set_affinity(thread_id, set(cores))
        except ProcessLookupError:
            continue
        except OSError as error:
            LOG.warning(
                'Could not pin the game to cores %s (%s): it runs where the system puts it',
                sorted(cores),
                error,
            )
            return False
    return True


def pin_the_game_to_its_cores(*, link: AiLink | None) -> bool:
    """Pin a live run with AI to the placement's game cores, on Linux.

    The engine calls it once ``create_link`` has run, with what it gave.

    Args:
        link: The run's link to the AI service; None for a run without AI.

    Returns:
        Whether the game was pinned: False without a link, in an inner context, off Linux,
        without a placement, or on a refusal.

    """
    if link is None or is_inner_context() or sys.platform != 'linux':
        return False
    placement = read_cpu_placement(path=link.locations.cpu_placement_file)
    if placement is None:
        return False
    return pin_this_process(cores=placement.game)
