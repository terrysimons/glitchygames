# Recording Content Hashes and Measurement History — Design

- **Date:** 2026-10-20
- **Status:** Implemented 2026-10-21 on `feature/gameplay-replay` (uncommitted), hashing option
  "Better" (below), per `plans/2026-10-21-recording-content-hash-and-history-implementation.md`.
  Contract: `glitchygames/recording_history.py`; user docs: `docs/architecture/gameplay_replay.md`
  ("Content hashes and measurement history"). Still open: a git commit per run (see "Open
  decisions"). The plan's Task 5 is done (2026-10-21): the four golden replay fixtures and the
  bundled demo were rebaselined (each "no frames differ"), so each now holds one measured run
  (unpaced, on the developer's machine) and one-entry histories; their key events had first
  been given their QWERTY positions (`plans/future-work.md`, Input).
- **Builds on:** the gameplay replay spec (`plans/2026-10-19-gameplay-replay.md`), the
  processing-time comparison (`glitchygames/replay/processing.py`, built 2026-10-20 on
  `feature/gameplay-replay`) and `--rebaseline` (`glitchygames/replay/rebaseline.py`).
- **Listed in:** `plans/future-work.md` (Gameplay replay).

## Why

Two recordings of the same scripted session are never byte-identical. The file layout is
deterministic (gzip mtime 0, no file name, sorted keys, a fixed seed), but a recording holds what
the run measured. Recording PaddleSlap's 450-frame script twice on one machine:

- `dt` differed in all 450 frames (0.02062, 0.01581, 0.01694 s against 0.01987, 0.01674,
  0.01666 s), though both summed to 7.485 s;
- so the sprites differed in 400 frames (game logic moves by `dt`; the paddle was 1 px apart by
  frame 2, at most 13 px), and the event batches in 226 (FPS events carry the measured rate, and
  fire on the summed `dt`);
- `processing_seconds` differed in every frame;
- the header's `recorded_at` (wall clock) and `options` (the `--record-trace` output path)
  differed.

Replay is unaffected (it serves the recorded `dt`, so each recording reproduces itself), but
nothing tells you cheaply whether two recordings show the same behaviour, and a rebaseline throws
away the measurements of the run before it.

## Goals (user direction)

1. A **content hash** per frame over everything the game did, leaving out what is measured
   (times), so a rebaseline whose game behaves the same gives the same hashes, and one whose game
   changed shows exactly which frames changed.
2. A **history of measurements** across rebaselines: each measured (or derived) per-frame value is
   kept as a list, newest first, so the change of each frame over time can be read from one file.
3. Each history has its own depth, a named constant, starting at 10, to be tuned later.
4. The baselines stay in the repository: they become the record that later runs are compared
   against, with a tolerance margin.

## The key observation: what a rebaseline keeps

A rebaseline (`--replay-trace OLD --rebaseline NEW --headless`) replays OLD's inputs into the
current code and records the result. Its `dt` is not noise: it is input, copied from OLD, and
FPS events come from the recorded frame clock. So across a chain of rebaselines everything but the
timing measurements stays identical unless the game's behaviour changed. That is what makes a
content hash meaningful: stable across replays and rebaselines of one recording, different
exactly where the code changed what the game does. (Across two fresh recordings it differs anyway,
as above: different `dt` means different behaviour.)

## Field inventory

### Frame fields: hashed (stable across rebaselines unless behaviour changes)

| Field | Why it is stable |
|---|---|
| `frame` | the frame's index |
| `dt` | input: copied from OLD (what the original recorded run measured) |
| `event_batches` | OLD's input events plus the current code's posts; FPS events hold values derived from the recorded `dt` |
| `input_changes` (including `held_key_codes`) | input: copied |
| `control_events` | recorded, re-applied |
| `devices_opened`, `device_enumeration`, `saves_opened` | copied from OLD |
| `scene_start` | captured by the current code; its clock readings derive from the recorded `dt` |
| `redelivered_events` | produced the same way each run |
| `scene`, `sprites` | **the current code's output: the behaviour the hash watches** |
| `resume_bridge`, `playback_answers` | the in-memory instant-replay journal only (never in files); hashed when present |

### Frame fields: measurements (left out of the hash, stacked)

| Field | Depth constant (start: 10) |
|---|---|
| `processing_seconds` (a list from now on) | `PROCESSING_SECONDS_HISTORY_DEPTH` |
| `content_hash` (new, a list; it never hashes itself) | `CONTENT_HASH_HISTORY_DEPTH` |

### Not fields: the on-disk delta encoding

`kind`, `added`, `changed`, `removed`, `rect_delta` and `present` are how sprites are encoded on
disk (`glitchygames/tracing.py`). The hash is taken of the decoded frame, so the encoding never
matters.

### Header fields

- **Unaffected (copied from OLD, never stacked):** `format_version`, `source`, `frame_seconds`,
  `input_capture_format_version` (structure); `game_class`, `game_module`, `scene_class`,
  `screen_size`, `options`, `random_seed` (what was run); `saves`, `devices`, `device_enumeration`
  (what the run took in before recording); `recorded_at` (the wall clock's origin, which the game
  reads, so it must stay); `source_truncated`; `bookmarked_copy_of`.
- **Replaced by each run, kept top-level as the latest:** `engine_version`, `pygame_version`,
  `python_version`. They describe the code that drew the current sprites, and the replay's version
  check reads them.
- **Moved into a stacked `measurement_runs` list** (`MEASUREMENT_RUNS_HISTORY_DEPTH`, start 10):
  one entry per run with `machine`, `processing_paced`, the three versions, a new `measured_at`
  (when the run measured) and `rebaselined_from` (the path it was rebaselined from, or null for a
  fresh recording). The top-level `machine` and `processing_paced` added on 2026-10-20 go away;
  nothing with them has shipped, so this costs no compatibility.

## Format

- Every stacked value is a list, even with one entry. `[0]` is the newest; a new run inserts at
  `[0]` and the oldest falls off the end at the list's depth.
- Newest first keeps the indexes aligned: entries are only ever dropped from the tail, so index
  `i` means "run `i`" in every list. `processing_seconds[i]`, `content_hash[i]` and
  `measurement_runs[i]` describe the same run, even when the depths are tuned apart (a shorter
  list simply ends sooner).
- Speed (measured 2026-10-21, Apple Silicon, Python 3.14; decided: keep newest first). Each
  history gets exactly one insert per run: it is read from the old recording's JSON as a list,
  gains one entry and is written back as JSON, so the insert, not the lookup, is what a run
  pays. Lookup is O(1) either way (`[0]` or `[-1]`). The insert into a full history of 10, over
  15 alternating runs of each:

  | Insert | Median | Range |
  |---|---|---|
  | Newest first, `[new, *old][:depth]` (built) | 69.3 ns | 66.4-69.7 |
  | Newest last, `[*old, new][-depth:]` | 78.5 ns | 75.3-80.3 |
  | Newest last, copy then `append` and `del [0]` | 118 ns | single run |
  | Newest first, copy then `insert(0)` and `del [depth:]` | 157 ns | single run |
  | `collections.deque(old, maxlen=depth)` then `append` | 197 ns | single run |

  Newest first is the fastest insert: 9 ns (13%) ahead of newest last, with ranges that do not
  overlap. A deque is the slowest here, although its append is O(1): a deque only pays when one
  object lives across many appends, and each history is built from a list, takes one insert
  and must become a list again for `json` (which cannot encode a deque); `appendleft` has the
  same problem. In absolute terms the gap is 18 ns per frame (two lists), 184 µs per
  10,000-frame recording, 0.017% of a frame's history work (the content hash, about 107 µs on
  the largest golden frame, dominates).
- Readers: newest first also keeps plain positive indexes aligned (`[i]` is "i runs ago" in
  every list, whatever its depth); with newest last only negative indexes line up, and a reader
  using `[i]` on lists of different lengths would pair different runs without any error. What
  newest last offers, time order for plotting a frame's history, is a `reversed()` in the tool
  that plots it.
- A fresh `--record-trace` writes one-entry lists. A rebaseline writes OLD's lists with its own
  entry in front. `--compare-processing` compares against `processing_seconds[0]`.
- No format version bump: these are optional frame and header fields, which readers already pass
  through (the format-3 rule). `processing_seconds` changes from a number to a list before any
  recording with the number was committed or shipped.

## The content hash

### Options considered (chosen: Better, 2026-10-21)

Measured on the largest frame of each golden fixture (Apple Silicon, Python 3.14): canonical JSON
encoding costs 5-39 µs a frame (6 to 105 sprites, 0.7-6.9 KB) and dominates; hashing is 15-20x
cheaper.

| Hash on the 6.8 KB frame | Bits | Time |
|---|---|---|
| XXH3-64 / XXH3-128 (`xxhash`, not stdlib) | 64 / 128 | 0.17 µs |
| `zlib.crc32` | 32 | 0.21 µs |
| SHA-256 (hardware accelerated here) | 256 | 2.36 µs |
| BLAKE3 (`blake3`, not stdlib) | 256 | 4.29 µs |
| BLAKE2b-64 | 64 | 4.98 µs |
| MD5 | 128 | 7.93 µs |

- **Good:** canonical JSON of the frame's content plus SHA-256, every frame. O(F) per frame (F
  the frame's size), 5-37 µs measured, stdlib only; but the content/measurement split is an ad hoc
  list and nothing enforces it.
- **Better (chosen):** Good's encoding with the classification on a pydantic model (an
  unclassified field fails), SHA-256 cut to 64 bits, one `frame_content_hash()` for the recorder,
  rebaselines and tools, a recording-level hash derived from the frame hashes, and a
  `hash_scheme` in each run's provenance so the definition can change later without every frame
  looking changed.
- **Best:** per-sprite (Merkle) hashes, cached and recomputed only for sprites that changed:
  O(Δ) encoding plus O(n) joining of digests, a few µs instead of 37 at 105 sprites; but a stale
  cache would make a changed frame look unchanged, and uncached it is 3-4x slower than Good.
  Kept for later, as a new `hash_scheme`, if hashing ever costs real frame time.
- **Rejected:** orjson or msgpack (a compiled dependency whose upgrades could change float
  formatting, and so every hash in the baselines; stdlib `json` floats are stable since Python
  3.1); xxHash now (14x faster than SHA-256 but saves about 2 µs of a 41 µs frame; the dependency
  is not worth it yet, and XXH3-128 is the candidate for a later scheme); CRC32 (32 bits, an error
  check, not a hash); a rolling chain hash (every frame after the first change would differ,
  losing which frames changed); a hand-written per-field encoder (26 µs against 37, maintained
  forever).
- **Why 64 bits of SHA-256:** file size only (speed and uniqueness are unaffected: 1 in 2^64 per
  comparison, and nobody is forging frames). When every run changes every frame, 10 history
  entries for 600 frames gzip to 231 KB at 256 bits and 64 KB at 64 bits, against fixtures of
  11-35 KB and a 22 KB bundled demo that ships in the wheel; when behaviour is stable the repeats
  compress to almost nothing either way.

### Definition

- **Canonical encoding:** the decoded frame's hashed fields (above), as a JSON reader decodes
  them (string keys, lists; final review 2026-10-21: int keys sorted numerically before
  encoding, and mixed key types could not be sorted at all), as compact JSON with sorted keys
  and sprites in draw order, then SHA-256 (the same encoding `--audit`'s `frame_digest`
  uses). Stored as hex, possibly truncated (64 bits is plenty within one recording; decide in the
  plan with the size numbers below).
- **Classification is explicit and exhaustive:** every frame field is declared either *hashed* or
  a *measurement* in one place, and a test fails when a field is neither. Hashing everything except
  the declared measurements (the user's choice) is the safer default: a behaviour field left out by
  mistake would hide changes silently, while a measurement left in by mistake makes hashes
  unstable, which the tests catch at once.
- **A pydantic model for the frame schema** (frozen, `extra='forbid'`) for reading, validating and
  hashing, with the classification on it. The write path during live play stays light (plain
  dicts, or `model_construct`), so recording adds no validation to every frame; benchmark before
  choosing.
- **Where it is computed:** by the recorder as it writes each frame (live recordings get `[0]`
  too). It costs a JSON encode and a SHA-256 per frame: benchmark it on the example games, and if
  it is too slow for live play, compute it only in rebaselines (fresh recordings would then get
  their first hash at their first rebaseline).
- **Size:** each hash is incompressible on its own, but a frame whose behaviour did not change
  repeats the same hash at every depth, and gzip compresses repeats within a line well. Expect
  little growth while behaviour is stable, and about one hash per frame per behaviour-changing
  run otherwise.

## Baselines in the repository

The golden fixtures (and the bundled demo) stay in the repo and gain these fields at their next
rebaseline. They become the record later runs are compared against with a tolerance margin: the
content hashes exactly (any change is a behaviour change to review), the processing times within
a tolerance (`--max-processing-slowdown`). Their reviews will show history churn on every
rebaseline; that churn is the record being asked for. Processing times only compare on the machine
that measured them (each run's `machine` says which), so a tolerance check in CI needs a baseline
measured on its runner; that is a follow-up.

## Open decisions

1. **A git commit in `measurement_runs`.** The best answer to "which code did this run measure",
   but only a checkout has it, not a wheel install. Recommendation: optional, the commit when `git`
   can give it (a clean or dirty marker included), else null.
2. ~~**A recording-level hash**~~ **Decided (2026-10-21): included, derived, not stored.** It is
   the SHA-256 (64 bits) of a recording's frame hashes in frame order, so it is computed from the
   frames (`recording_content_hash`), and its history is too: run `i`'s recording hash is the hash
   of every frame's `content_hash[i]`. Storing it would need a trailer (the header is written
   first, while frames stream), so it is not. It is what C12 (a content hash of a played demo in
   the `playback` marker, `plans/future-work.md`) needs; wiring C12 is a follow-up.

## What we are not doing, and why

- **Not stacking FPS.** In a replay, FPS comes from the recorded `dt`, so it is identical in every
  run; only `--replay-fps real` measures it, and processing time is the more useful measurement.
- **Not stacking `dt`.** A rebaseline copies it (it is input), so every entry would be the same.
- **Not keeping old sprites (or other content) across runs.** A full history of what was drawn
  would multiply the file; the content-hash history says which frames changed and in which run,
  and the run's own recording (or git history of the fixture) has what they were.
- **Not making fresh re-records byte-identical** (for example by recording the scripted sessions at
  a fixed frame time, as the golden-trace harness does). The golden replays are meant to cover the
  real loop, real jitter included; fixed-dt recordings already exist as the golden traces.
- **Not hashing measurements or provenance:** `processing_seconds`, the hash itself, and
  `measurement_runs` (machine, versions, times, paths) describe the run, not the game.
- **Not hashing the header's fields** beyond the frames (and the optional recording-level hash):
  the header's content is copied unchanged by rebaselines, so it has nothing to report per run.
- **Not keeping the history in a sidecar file.** The user wants the baselines to be the record, in
  the repository, read from one file; a sidecar would split a recording from its own history.
- **Not changing what a replay compares.** A replay still compares what it samples (scene, sprites,
  events, input); it does not check `content_hash[0]`, which would duplicate that comparison. The
  hashes are for tools, rebaselines and baselines.
- **Not unifying `--audit`'s digest yet.** The audit digests only what a replay samples (scene and
  sprites); switching it to the content hash would make it compare events and inputs too, a change
  of what `--audit` checks. The two share the canonical encoding; unifying them is a follow-up.
- **Not bumping the format version** (see Format).

## Testing (for the plan)

- The classification test: every frame field is hashed or a measurement.
- A replay and a rebaseline of a recording reproduce its content hashes exactly; a rebaseline on
  changed code changes exactly the frames whose sprites (or events) changed.
- History lists: one entry for a fresh recording; a rebaseline inserts at `[0]`; each list stops at
  its own depth constant; the indexes stay aligned across lists of different depths.
- `measurement_runs[0]` describes the run (machine, paced, versions, `measured_at`,
  `rebaselined_from`).
- `--compare-processing` reads `processing_seconds[0]`.
- A benchmark of the per-frame hash (and of the pydantic model if it is used on the write path).

## Documentation (for the plan)

`docs/architecture/gameplay_replay.md` (recording format, rebaselining, comparing processing
time), `glitchygames/recording.py`'s module docstring (the format), `glitchygames/replay/
processing.py` (reading `[0]`), CLAUDE.md, and the corrected re-record note in
`scripts/record_scripted_session.py` (re-records differ in content, not just layout).
