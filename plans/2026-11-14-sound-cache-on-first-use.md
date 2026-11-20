# Sounds on first use: the disk cache and the listening WAVs

Master: the sound engine specs, `docs/specs/2026-11-02-sound-engine-feature-spec.md` (§9, the
cache) and `docs/specs/2026-11-02-sound-engine-implementation-spec.md` (§6.4, the disk layer;
§11.0 and M3, the order of work). Branch `chore/upgrade-and-sounds-on-first-use`, after the
dependency upgrade (its own commit, every gate green, ff920c60). Sibling: `plans/2026-11-14-sound-migration.md` (the games
moved onto the library, so the disk layer has their sounds to keep). TODO: `plans/future-work.md`,
"Upgrade every locked dependency, then generate sounds on first use".

## Goal

Nothing the engine can render is stored in the repository or shipped: it is made the first time
it is needed and kept in the user's cache folder. An installed wheel runs no code at install
time, so first use is the earliest point; a subcommand fills the cache ahead of time.

- The engine's compiled sounds (the CRT power-on's, a game's) survive between launches.
- The listening WAVs (every catalog instrument across its range; the pipe tunes) come from the
  installed engine, a family or instrument at a time, instead of from scripts in `scripts/`.

## Decisions

1. **The disk layer is spec §6.4's, built now, before M2** (the owner, 2026-11-14). The spec's
   order had M2 (games on the new API, old paths removed) and M3's `none` and `ram` benchmarks
   first. Building the layer early changes nothing those benchmarks measure: they choose the
   mode by flag, so `none` and then `ram` are still measured before `disk`. The spec's §6.4 and
   M3 list are updated to say the layer was built early, and why.
2. **`disk` is opt-in; `ram` stays the default** (the owner, 2026-11-14). `--sound-cache disk`
   stops being refused. Making it the default waits for M3's numbers or the owner's say-so.
   **Superseded 2026-11-15 (the owner):** `disk` is the default. Measured with
   `scripts/benchmark_sound_cache.py`, a cold read beats compiling 2x to 9x on a Raspberry Pi 4
   and Pi 5 from SD cards and a Pi 5 from NVMe, and 7x to 31x warm on an Apple M4 Max. With it:
   one folder per game (`<root>/<game package>/sounds/<render_version>/`, its own 64 MB), and a
   hit writes nothing, so pruning goes oldest written first (decision 3's "oldest-accessed" and
   the read's time refresh are gone).
3. **The spec's layout and limits hold** (§6.4, owner decisions): `<cache>/sounds/
   <render_version>/<key[:2]>/<key>.wav`, 16-bit PCM at the mixer rate, written aside then moved;
   64 MB, oldest-accessed pruned at startup; a read
   verifies the header (rate, channels, width, length) and a bad file is deleted and compiled
   again; in the browser `disk` falls back to `ram` with one log line. Where tests are concerned
   decision 7 replaces the spec's "falls back in tests". One change from the spec's text: a write goes to a temporary file of
   its own (`<key>.wav.writing-*`, `tempfile.mkstemp` in the same folder), not
   `output_files.write_aside_then_replace`, whose one fixed `.partial` name two processes writing
   the same sound would share (one could move the other's half-written file into place).
4. **A disk hit gives a replay exactly what a compile would.** A WAV holds int16 samples, not the
   float samples the memory cache keeps, and CLAUDE.md requires a sound's `peak`, `length` and
   `sample_rate` never to depend on the cache. So each file also carries the compile's exact
   `peak` (a float64 in a private RIFF chunk, `gGpk`, which WAV readers skip), and a disk hit
   installs the int16 samples and that peak. Float samples are not stored: a caller that needs
   them (today only `audio/offline.py`'s render) compiles the sound fresh, counted as a compile.
   **[Call; owner to confirm]** The alternative, storing float64 samples, makes every file four
   times larger and the 64 MB limit four times smaller in practice.
5. **The listening WAVs move into the engine and get their own cache folder.** At about 300 MB
   (724 instrument files, 26 pipe files) they would flush the 64 MB sound cache, so they live in
   `<cache>/listening/<render_version>/` with no size limit, and only the clear subcommand
   removes them. Their code moves from `scripts/make_instrument_demos.py`, `scripts/make_pipes.py`
   and `scripts/pipe_tunes.py` into `src/glitchygames/audio/listening/` (the engine may not import
   `scripts/`), the tunes' `.abc` files into its package data; the scripts go (their `build/`
   output with them), checked with `git log --diff-filter=D` that nothing else expects them.
6. **The cache root is `state/paths.get_cache_directory(app_name)`**, beside
   `get_save_directory`, per §6.4: macOS `~/Library/Caches/<app>/`, Linux
   `$XDG_CACHE_HOME/<app>/` (default `~/.cache/<app>/`), Windows `%LOCALAPPDATA%\<app>\Cache\`.
   The engine's app name is `glitchygames` (one cache per machine, shared by every game, since a
   sound's identity already names everything that makes it).
7. **Explicit controls, not a hidden "in tests" switch** (the owner, 2026-11-14, after a review
   noted that the spec's "in tests, `disk` falls back to `ram`" would make the replay proof run
   on the memory cache and pass without touching the disk):
   - `GLITCHYGAMES_SOUND_CACHE_ROOT` overrides the cache root: unset, the platform folder
     (decision 6); a path, that folder; empty, no disk layer (`disk` runs as `ram` and logs one
     line saying why). An environment variable, not a command-line option, because golden
     replays and bundled demos run as child processes, which inherit it; an option would have to
     be threaded through every launcher. The pattern is `GLITCHYGAMES_AI_INSTALL_ROOT`'s.
   - The test harness sets it empty by default, so no test writes to the user's cache folder; a
     test that wants the disk sets it to its own `tmp_path`.
   - A `disk_sound_cache` fixture does that and fails the test at teardown when no file in its
     folder was written or read, so a test that claims to test the disk proves it touched it.
   - `CacheStatistics` gains `disk_hits`, `disk_misses` and `disk_writes` (also shown in the Audio
     panel and by `sound-cache size`).
8. **Steps 3-4 revised: the cache's operations are an engine API; the commands are thin** (the
   owner, 2026-11-15, branch `feat/sound-cache-subcommands`, after the migration made `disk` the
   default with a folder per game, and with GG Sound Studio, the spec's M6 sound editor, in
   view). The Studio's cache panel, the command line and the tests all need the same answers, so
   the logic lives once, in `glitchygames.audio.cache_inventory`, returning frozen pydantic
   models, and nothing copies it:
   - `inventory(root)`: every game's folders, by render version, with their sound count and
     bytes, a version other than the current one marked stale; the listening folder too.
   - `clear(root, ...)`: one game's folder, every game's, only the stale render versions, or the
     listening WAVs; it reports what it removed.
   - `verify(root)`: reads every file back and reports the damaged ones (a game already copes
     with one, deleting and recompiling it, but silently).
   - `fill(game)`: compiles a game's declared sounds (`Scene.SOUNDS`) into its folder, so even a
     first launch reads them (the remedy for a slow machine's first-launch stall, measured on a
     Raspberry Pi 4).
   - **Stale render versions are removed at a game's start**, beside pruning: a found gap,
     since pruning looks only at the current version's folder, so after a render version bump
     every older folder stayed on disk for good.
   - The commands, each a registry `Tool` (so both `glitchygames <name>` and a game flag on
     that game's own folder): `sound-cache-fill`, `sound-cache-clear`, `sound-cache-size`,
     `sound-cache-list`, `sound-cache-verify`, then `listening-instruments` and
     `listening-pipes`. **Flat names** (the owner): every tool is one name used both ways, a
     flag takes no sub-actions, and `--sound-cache` is already the mode option; the grammar
     matters least, since the Studio calls the API, not the command line.
   - **As built** (2026-11-16, branch `feat/sound-cache-subcommands`): the API and all seven
     commands. The listening folder is listed apart (`CacheInventory.listening`) and removed only
     by `clear(listening=True)` (`sound-cache-clear --listening`, refused with a game: the files
     are no game's); `verify` never reads it (plain WAVs, no peak chunk). Left out:
     `sound-cache-fill --listening` (Interfaces), since `listening-instruments` and
     `listening-pipes` render the same files; the owner may still want it in one command. Only
     `sound-cache-fill` reads the project's settings; the other cache commands work without
     them. Inner games now get the outer game's command line, less the refused flags (found
     when the new flags made `--sound-cache` a prefix of refused ones).

## Interfaces

- `state/paths.get_cache_directory(app_name: str) -> Path`.
- `audio/disk_cache.py` (new, a leaf): `DiskSoundCache(*, root: Path, limit_bytes: int)` with
  `read(*, identity_key, sample_rate, frame_count) -> CachedSamples | None` (int16 samples and
  peak; None on a miss or a bad file, which it deletes), `write(*, identity_key, samples_int16,
  peak, sample_rate)`, `prune()` (oldest-accessed first, down to the limit) and `size_bytes()`.
  `CachedSamples` is a frozen pydantic model: measured at 0.36 us to construct, 1.2% of a disk
  read of a one-second sound (its docstring has the measurement).
- `SoundLibrary(cache=CacheMode.DISK, disk=DiskSoundCache | None)`: memory first, then disk, then
  compile and write. `ENGINE_SOUND_CACHE` (the engine's own sounds, process-wide) reads and writes
  the same disk layer when the mode is `disk`.
- `GameEngine`: `--sound-cache disk` no longer refused; the root comes from
  `GLITCHYGAMES_SOUND_CACHE_ROOT` (decision 7); an empty root and the browser run as `ram` (one
  log line).
- Subcommands (each a `Tool` in `replay/tools/registry.py`, so also a game flag with a game
  handler, as the registry requires of a tool that runs no game):
  - `glitchygames listening instruments [--family F] [--only TEXT]` and `glitchygames listening
    pipes [--only TEXT]`: render what is missing into the listening folder, print each WAV's path
    (so a player can open it), and the index (`index.txt`, as today).
  - `glitchygames sound-cache fill [--listening]`: compile the engine's own sounds and every sound
    in the project's games' sound directories (`[tool.glitchygames] games`) into the disk layer;
    `--listening` also renders every listening WAV.
  - `glitchygames sound-cache clear [--listening]` and `glitchygames sound-cache size`.
  - Names are proposals; the owner may rename (full names, no abbreviations).

## Tests (behaviours)

- A disk hit's int16 samples are byte-identical to a fresh compile's, and its peak, length and
  sample rate equal the compile's, for a version 1 sound, an instrument note, a version 0 recipe
  and a recorded file.
- Every golden replay and bundled demo replays to the same digests under `--sound-cache disk`
  with a cold cache and again with a warm one (the inner-game proof's digest comparison, reused).
- A second library over the same folder compiles nothing for sounds the first compiled.
- A truncated file, a file of another rate or width, a file without the peak chunk and a file of
  the wrong length are each deleted and compiled again, and the compile is counted.
- Pruning removes the oldest-accessed files until the folder is under the limit and never a file
  a library holds open; an over-limit folder at startup is pruned once.
- Two processes writing the same key never leave a partial file (write aside, then replace).
- The root's three states: unset gives the platform folder, a path gives that folder, empty runs
  `disk` as `ram` and logs exactly once; the browser runs `disk` as `ram` and logs once.
- The replay proof cannot pass on the wrong layer: the cold run shows `disk_writes > 0`, the
  warm run `disk_hits > 0` and no compile of a sound already kept, and both match the solo
  replay's digests; it uses `disk_sound_cache`, which fails a test that touched no file.
- `disk_sound_cache` itself: a test that writes or reads a file passes; one that touches none
  fails at teardown (checked with pytester).
- `get_cache_directory` per platform (the three branches, with the environment variables set and
  unset), and an invalid app name refused as `get_save_directory` refuses it.
- The offline render of a sound that came from disk equals the offline render of a fresh compile.
- The listening subcommands render only what is missing, print paths that exist, and reproduce
  today's scripts' WAVs sample for sample (the scripts' output, rendered once in the test from
  the moved code before the scripts are deleted, is the reference).
- `sound-cache clear` removes only the cache folder's own contents; `size` reports what is there.
- Each new tool has its case in `tests/replay/tools/test_an_unseen_game.py` (every tool in
  `TOOLS` must).

## Order of work

1. `get_cache_directory` and `DiskSoundCache`, with their tests.
2. The library and `ENGINE_SOUND_CACHE` on the disk layer; `--sound-cache disk` accepted; the
   replay proof under a cold and a warm cache.
3. (Revised, decision 8.) The cache API in order: `inventory` and the stale-version cleanup;
   `clear` and `verify`; `fill`. Then the commands over it.
4. The listening code moved into the engine, reproduced sample for sample, then the scripts
   removed; its two commands.
5. Docs (the owner, 2026-11-14: every new environment variable and option is documented):
   - `GLITCHYGAMES_SOUND_CACHE_ROOT`: its three states, why an environment variable, and that
     the test harness sets it empty, in `docs/architecture/sound.md` (the cache section), in
     CLAUDE.md's Sound Synthesis lines and Testing Guidelines (beside the harness's other
     defaults), and in the docstring of the module that reads it.
   - `--sound-cache disk`: its entry in `docs/architecture/argument_system.md` (no longer
     "arrives in M3") and the `disk` row of `docs/architecture/sound.md`'s mode table.
   - Every new subcommand and its options (`listening instruments|pipes`, `sound-cache
     fill|clear|size`, `--family`, `--only`, `--listening`) in
     `docs/architecture/gameplay_replay.md` (the command reference) and, where a subcommand is
     also a game flag, `docs/architecture/argument_system.md`.
   - The disk counters in `docs/architecture/sound.md`'s Audio panel section.
   - Spec §6.4 and M3 (built early, why; decision 7 replaces "falls back in tests"), the TODO
     marked done.
   - Before the push, grep the docs for each new name to show it is documented, and run the
     docs claims check and the strict docs build.

## Risks

- The 64 MB limit holds about 6 minutes of mono 44.1 kHz sound; a game with more evicts its own
  sounds each launch. M3's measurements decide whether the limit moves.
- A process killed mid-write leaves only a `.partial` file, which a read never trusts and a prune
  removes.
- An installed engine without write access to its cache folder runs as `ram` and logs once.
