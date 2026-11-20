# Every Browser Game Stopped at Startup: No Module Named `filelock`

- **Description**: Every play page (Zombies Ain't My Neighbors, Paddle Slap, Brave Adventurer, Clockwork Keep, Mr. Muncher, Drawing Fire, Bitmappy) stopped before its first frame with `ModuleNotFoundError: No module named 'filelock'`. The traceback runs from the game's package through `glitchygames.engine`, `replay/tools/registry.py`, `audio/__init__.py`, `audio/engine.py` and `audio/cache_inventory.py` to `audio/disk_cache.py`, line 59 (the owner's report, 2026-11-19).
- **Status**: Fixed (2026-11-19, branch `fix/browser-games-without-filelock`)
- **Priority**: High (no browser game could start; the desktop was unaffected)
- **Root Cause**: #213 (2026-11-15, the disk sound cache) imported `filelock` at the top of `audio/disk_cache.py`. Every game reaches that module at startup, and the browser bundle installs only `PYODIDE_PACKAGES` (numpy, pydantic, tomli-w), `scripts/build_browser_bundle.py`. The browser never used the disk layer (`audio/engine.py`'s `_disk_layer` returns None there), but importing the module was enough.
- **Test gap**: Nothing imported a game with only the packages the browser bundle installs. Every desktop test has `filelock` installed, so #213 passed CI while every play page was broken.
- **Solution**:
  - `disk_cache.py` imports `filelock` inside `DiskSoundCache.write_lock`, only where it takes a lock.
  - In the browser (`sys.platform` is `emscripten`, `BROWSER_PLATFORM`), `write_lock` takes no lock and yields True. A page runs one Python process, so there is no other process to wait for. Two tabs writing one sound write the same bytes through their own temporary files, and a read checks the file. This is the lock path the browser disk cache will use (the owner, 2026-11-19: the browser should keep compiled sounds in its own storage; a branch of its own).
- **The class, and its invariant**: a game's startup imports a third-party module the browser bundle does not install. `tests/test_build_browser_bundle.py::test_every_browser_game_imports_with_only_the_browser_packages` imports every game in `GAMES` (its first scene module, as the page does) in a child Python that refuses every third-party module outside the bundle: the standard library, pygame, the engine, the workspace members the bundle ships, and `PYODIDE_PACKAGES` with their dependencies. An import guarded by `try`/`except ImportError` still passes, as it does in Pyodide. It failed on main for all 7 games on `filelock`, and passes with the fix.
- **Sweep**: With `filelock` allowed, all 7 games import. The other third-party modules they reach (`miniaudio`, `speech_recognition` and `hid` in `audio/controller_audio.py`) are guarded. Not covered: modules a game imports later than its first scene module (a scene it changes to, a function's own import); the test sees only what loads at startup.
- **Tests**:
  - `tests/test_build_browser_bundle.py`: the invariant above, one case per game, and a check that a package's dependencies' modules count as installed.
  - `tests/audio/test_disk_cache.py`: on the desktop the write lock is the sound's lock file; in the browser it is held at once, with no lock file and no `filelock`; a sound written under the browser's lock reads back exactly.
- **Verified in a browser** (2026-11-19): Zombies Ain't My Neighbors built with `scripts/build_browser_bundle.py` and the cached Pyodide pygame-ce wheel, served locally, and loaded in Playwright's Chromium. Main's build stopped with this traceback (`disk_cache.py`, line 59, `No module named 'filelock'`); the fixed build reached "click to play" and, clicked, its title screen, with no Python error.
- **Not verified**: the other six games in a browser (the import test covers their startup), and WebKit and Firefox.
- **Reporter**: The owner
- **Date Reported**: 2026-11-19
- **Files**: `src/glitchygames/audio/disk_cache.py`, `tests/audio/test_disk_cache.py`, `tests/test_build_browser_bundle.py`
