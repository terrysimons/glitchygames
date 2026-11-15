# Sounds on first use: the disk cache and the listening WAVs

Master: the sound engine specs, `docs/specs/2026-11-02-sound-engine-feature-spec.md` (§9, the
cache) and `docs/specs/2026-11-02-sound-engine-implementation-spec.md` (§6.4, the disk layer;
§11.0 and M3, the order of work). Branch `chore/upgrade-and-sounds-on-first-use`, after the
dependency upgrade (its own commit, every gate green, ff920c60). TODO: `plans/future-work.md`,
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
3. The listening code moved into the engine, reproduced sample for sample, then the scripts
   removed.
4. The subcommands.
5. Docs: spec §6.4 and M3 (built early, why), `docs/architecture/sound.md`, CLAUDE.md's Sound
   Synthesis lines, the TODO marked done.

## Risks

- The 64 MB limit holds about 6 minutes of mono 44.1 kHz sound; a game with more evicts its own
  sounds each launch. M3's measurements decide whether the limit moves.
- A process killed mid-write leaves only a `.partial` file, which a read never trusts and a prune
  removes.
- An installed engine without write access to its cache folder runs as `ram` and logs once.
