# Upstream Issues

Problems found in the tools this project depends on, worked around here, to be reported to
their projects. Each entry holds the evidence an upstream report needs: the versions, the
measurements, how the cause was found, a reproduction, and the issue text drafted for posting.
None has been posted yet.

When a release fixes one, upgrade, check the reproduction no longer shows it, remove the
workaround and move the entry to the Fixed section.

## Open

### pygame-ce's mixer frees a queued Sound while it is still referenced (re-entrant `endsound_callback`)

Found 2026-11-24. The golden-traces test (`tests/world/test_golden_traces.py`, Mr. Muncher)
segfaulted in about half the group runs once main's #269 changed the timing between its two
games: heap corruption, detected later in `pymalloc` (the next `pygame.Rect` allocation; a Sound
and a Rect share a size class).

**Versions**: pygame-ce 2.5.8, SDL 2.32.10, SDL_mixer 2.8.2, CPython 3.15.1, macOS arm64;
`SDL_AUDIODRIVER=dummy` is enough.

**Cause**: `Channel.play(C)` on a channel still playing Sound A, with Sound B queued, when
pygame's channel table holds the only reference to A. `Mix_PlayChannelTimed` ends A and calls
`endsound_callback`, which runs `Py_XSETREF(channeldata[channel].sound,
channeldata[channel].queue)` and only then clears `queue`. Releasing A runs `sound_dealloc` →
`Mix_FreeChunk(A)`, and SDL_mixer halts every channel still playing A, calling
`endsound_callback` again, nested, for the same channel. The nested call finds `sound == queue ==
B` with one reference between them and releases B; the outer call and `chan_play` then release it
again. All on the main thread (a C stack at the second free shows the nesting): re-entrancy, not
a data race.

**Measurements**: the code before #269, 0 of 15 single-test runs crashed; at #269, 11 of 20; the
lighting branch's timing hid it (0 of 10). A probe caught the bad free in exactly the runs that
crashed.

**Reproduction** (deterministic, 5 of 5 runs; no glitchygames code):

```python
import weakref

import numpy as np
import pygame

pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)


def one_second_sound():
    return pygame.sndarray.make_sound(np.full((44100, 2), 500, dtype=np.int16))


channel = pygame.mixer.Channel(0)
channel.play(one_second_sound())  # A: referenced only by pygame's channel table
sound_b = one_second_sound()  # B: this script keeps a reference for the whole run
channel.queue(sound_b)
freed = []
watch = weakref.ref(sound_b, lambda _reference: freed.append(True))
channel.play(one_second_sound())  # C, while A still plays
print('BUG: Sound B was freed while still referenced' if freed else 'ok: Sound B is alive')
```

**Workaround here**: `LiveStream` (`src/glitchygames/audio/live.py`), the only engine code that
queues Sounds, keeps its own reference to every chunk it plays or queues (`held_chunks`) and lets
go of one only once its channel no longer names it, or after stopping the channel. A stream
dropped unstopped stops its channel first (a `weakref.finalize`). So pygame's table never holds
the last reference and `endsound_callback` never deallocates inside itself. `SceneManager.terminate`
releases the live voices at every game end. A stream collected unreleased is reported by its
finalizer, which never raises, to its engine context's registry of live streams and to the log.
After every test, the harness asks that registry and fails a channel queue naming a Sound no live
stream holds, and any stream still holding chunks or reported. The tests are
`TestLiveStreamKeepsItsChunks` in `tests/audio/test_live.py`: the reproduction's pattern through
two live voices on one channel (it segfaulted 5 of 5 runs before the fix), and the invariant that
every Sound on a voice's channel is held by the voice, at most two. Complementing it, the
golden-trace harness's `golden_game` releases the game's live voices and halts the mixer at
teardown (`test_a_golden_games_teardown_leaves_no_mixer_channel_busy`). Bug record:
`bugs/2026-11-24-pygame-mixer-frees-a-queued-sound-twice.md`. Remove the guard only after a fixed
pygame-ce release ships.

**Fix to propose upstream**: update both slots, then release the old Sound:

```c
PyObject *old_sound = channeldata[channel].sound;
channeldata[channel].sound = channeldata[channel].queue;
channeldata[channel].queue = NULL;
Py_XDECREF(old_sound);
```

Three related defects in the same file. `chan_get_sound` and `chan_get_queue` index `channeldata`
with no `MIXER_INIT_CHECK` and no bounds check. `chan_play` indexes `channeldata[channelnum]`
without checking for `-1` (`Mix_PlayChannelTimed`'s failure value, for a channel SDL refuses), and
has no init check either. A freshly built `Channel(index)` is safe, since `_channel_init` checks init
and range and raises. The hazard is a stored `Channel` outliving a mixer quit (a NULL table) or
restart (a table of 8, below an inner game's live pool). Only `audio/live.py` stores Channels; it
reads and plays only while the table has the channel (`_channel_in_the_table`,
`_channel_table_slots`). Not triggered here: `chan_queue`'s first branch assigns
`channeldata[n].sound` without releasing the previous value (a leaked reference).

**Drafted issue text**: the title "`Channel.play()` over a playing Sound with a Sound queued frees
the queued Sound while it is still referenced (re-entrant `endsound_callback`)", then the
versions, the reproduction, the cause and the suggested fix above, and the three related defects.

### `mkdocs serve` keeps every rebuild alive (griffe and mkdocstrings-python)

Found 2026-10-24, BUGS.md #213. A local `mkdocs serve` (`nox -s docs-serve`) was at 14.5 GB.

**Versions**: griffe (`griffelib`) 2.4.1, mkdocstrings 1.0.8, mkdocstrings-python 2.0.10,
mkdocs 1.6.1, Python 3.14, macOS. Both griffe and mkdocstrings-python were the latest releases
on PyPI when this was measured.

**Measurements** (resident memory after each build; the same inputs every time):

| Build | Four builds in one process, as `serve` builds | With the workaround | `mkdocs serve`, with the workaround |
|---|---|---|---|
| start | | | 674 MB |
| 0 | 694 MB | 688 MB | |
| 1 | 1016 MB | 685 MB | 913 MB |
| 2 | 1375 MB | 718 MB | 936 MB |
| 3 | 1532 MB | 647 MB | 920 MB |
| 4 | | | 905 MB |
| 5 | | | 928 MB |

About 330 MB per rebuild was never freed, though `gc.collect()` ran after each build. In the
live server (last column, rebuilds triggered by touching `docs/index.md`) the first rebuild
raised it to about 920 MB, and it stayed there.

**How the cause was found**:

1. Not the data: the graphs this project's hook generates are a few kilobytes, and its scripts
   load once (`sys.modules` stayed at 736 modules over the builds).
2. Counting live objects by type across one build: the growth was griffe's models
   (`ExprName` +23,876, `Alias` +17,512, `Parameter` +9,304, `Function` +4,314, ...),
   mkdocstrings' `InventoryItem` and autorefs' `BacklinkCrumb`: a whole API tree and its
   handler per build. Weak references to each build's config and Python handler showed every
   one still alive.
3. The old handler's referrers were all inside the build (the mkdocstrings plugin, its
   Markdown extension and `AutoDocProcessor`), so something outside reached that group. Clearing
   every populated `functools` cache in the process freed the first build's handler (958 ->
   521 MB).
4. Clearing the suspect caches one at a time: mkdocstrings-python's `_test_existing_template`
   freed the old handler (959 MB, its tree still held), then griffe's `_dataclass_parameters`
   freed the tree (530 MB). Clearing others after those changed nothing.

**The two caches**:

- griffe, `griffe/_internal/extensions/dataclasses.py`:

  ```python
  @cache
  def _dataclass_parameters(class_: Class) -> list[Parameter]:
  ```

  An unbounded cache keyed by `Class` objects. Each `Class` references its module and the whole
  modules collection, so one entry keeps the build's entire API tree (about 430 MB here).
- mkdocstrings-python, `mkdocstrings_handlers/python/_internal/rendering.py`:

  ```python
  @cache
  @pass_environment
  def _test_existing_template(env: Environment, path: str) -> bool:
      return path in env.list_templates()
  ```

  Keyed by the Jinja `Environment`, which each build makes afresh; through it the cache keeps
  the build's `PythonHandler`.

**Reproduction**: run from a project whose `mkdocs.yml` uses mkdocstrings' Python handler on a
package with dataclasses (`uv run python repeat_builds.py 4`):

```python
"""Build the docs several times in one process, as mkdocs serve does, printing memory after each."""

import gc
import os
import subprocess
import sys
import tempfile

from mkdocs.commands.build import build
from mkdocs.config import load_config


def resident_megabytes() -> int:
    output = subprocess.run(
        ['ps', '-o', 'rss=', '-p', str(os.getpid())], capture_output=True, text=True, check=True
    ).stdout
    return int(output) // 1024


site_directory = tempfile.mkdtemp()
for build_number in range(int(sys.argv[1])):
    # serve loads the config afresh for every rebuild (mkdocs/commands/serve.py builder())
    config = load_config(config_file='mkdocs.yml', site_dir=site_directory)
    config.plugins.on_startup(command='serve', dirty=False)
    build(config, serve_url='http://127.0.0.1:8002/')
    del config
    gc.collect()
    print(f'build {build_number}: resident {resident_megabytes()} MB', flush=True)
```

To name the caches, after two builds clear one at a time and watch the first build's handler
(`weakref.ref(config.plugins['mkdocstrings'].handlers.get_handler('python'))`) and resident
memory:

```python
caches = {
    f'{item.__module__}.{item.__qualname__}': item
    for item in gc.get_objects()
    if isinstance(item, functools._lru_cache_wrapper) and item.cache_info().currsize
}
for name in [
    'mkdocstrings_handlers.python._internal.rendering._test_existing_template',
    'griffe._internal.extensions.dataclasses._dataclass_parameters',
]:
    caches[name].cache_clear()
    gc.collect()
    print(name, 'first handler alive:', first_handler() is not None, resident_megabytes(), 'MB')
```

**Workaround here**: `on_post_build` in `scripts/mkdocs_hooks.py` empties every module-level
`functools` cache of the loaded griffe and mkdocstrings modules after each build
(`documentation_caches()` finds them by scanning the modules, so a renamed cache is still
found); tested in `tests/test_generate_complexity_graphs.py`. The caches only speed up work
within one build, so emptying them between builds costs nothing. Remove both, and their tests,
when both projects have fixed theirs.

**Issue drafted for griffe** (github.com/mkdocstrings/griffe):

!!! bug "_dataclass_parameters cache keeps every mkdocs serve rebuild's API tree alive"
    `griffe/_internal/extensions/dataclasses.py` decorates `_dataclass_parameters(class_)` with an
    unbounded `functools.cache` keyed by `Class` objects. Under `mkdocs serve`, each rebuild loads a
    new API tree, and the cache keeps the previous trees reachable (each `Class` references its
    module and the whole collection). With griffe 2.4.1 on a package of about 4,000 functions,
    memory grew by about 330 MB per rebuild (694 -> 1016 -> 1375 -> 1532 MB over four in-process
    builds, `gc.collect()` after each); calling `_dataclass_parameters.cache_clear()` after each
    build kept it flat (about 690 MB).

    Suggestion: cache on the `Class` instance (e.g. a private attribute), or in a
    `weakref.WeakKeyDictionary`, so the cache dies with the tree.

    Reproduction: load the config and call `mkdocs.commands.build.build(config)` several times in
    one process, `gc.collect()` between, tracking resident memory (script attached).

**Issue drafted for mkdocstrings-python** (github.com/mkdocstrings/python):

!!! bug "_test_existing_template cache keeps every rebuild's handler and Jinja environment alive"
    `mkdocstrings_handlers/python/_internal/rendering.py` decorates `_test_existing_template(env,
    path)` with `functools.cache`, keyed by the Jinja `Environment`. Each `mkdocs serve` rebuild
    makes a new environment, so the cache keeps every previous one and, through it, the previous
    `PythonHandler` (mkdocstrings-python 2.0.10). Clearing it after each build frees the old
    handler.

    Suggestion: cache per environment (on `env` itself, or in a `weakref.WeakKeyDictionary`).

## Fixed

None yet.
