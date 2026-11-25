# A replay touches nothing real

- **Status:** the owner's decisions of 2026-11-25 are in the text (section 7 lists them). Nothing
  is built.
- **Read at:** origin/main `023f120b9`. Every `file:line` is there; `G/` is `src/glitchygames/`, `B/` is
  `src/apps/bitmappy/src/bitmappy/`. "(inference)" marks what was reasoned, not read or run.
- **Closes:** four High records of 2026-11-24 in `bugs/`: `replayed-png-drop-writes-and-reads-real-files`,
  `bitmappy-dialogs-touch-real-files-in-a-replay`, `replayed-copy-and-paste-reach-the-real-clipboard`,
  `headless-replay-uses-the-players-sound-cache`. The fifth (Bitmappy's AI worker) was fixed by PR #319, merged.
- **Serves:** `plans/lucid-circuit-4b-mirror.md`, "No real stimulus". It does not build the mirror.

## 1. The example

Pat records Bitmappy with `--record-trace`: pastes `castle` into a text box, drops
`~/art/tower.png` on the canvas, then saves as `tower2.toml`. Next week Pat edits `tower2.toml`
by hand, copies a password, and replays the recording.

**Today, in that replay**

| Step | What happens | Where |
|---|---|---|
| Paste | The password is pasted: `system_clipboard()` is pyperclip whatever the doors are | `G/ui/text_widgets.py:1385`, `G/clipboard.py:106`, `create_clipboard` at 111 |
| Copy or cut | Pat's clipboard is replaced | `G/ui/text_widgets.py:1378`, 1406; `G/clipboard.py:91` |
| Drop | Today's PNG is read (three times) and `tower.toml` written beside it again; PNG moved away: diverges | `B/file_io.py:81`, 253, 309, 396, 413 |
| Save | `tower2.toml`, hand edits included, is overwritten | `G/ui/dialogs.py:468`, `B/animated_canvas.py:1260`, 1299, 1777, `G/sprites/animated.py:2028` |
| Any sound | Pat's sound cache is swept, pruned, locked and written; a held lock waits up to 5 s a sound on the main thread | `G/audio/engine.py:134`, `G/audio/library.py:888`, 1193, `G/audio/disk_cache.py:138`, 268 |

Saves and devices do none of this: `ReplaySources.saves` gives a memory store (`G/replay/driver.py:1805`)
and `devices` gives stand-ins (1796).

**After, by mode**

| Mode | Paste | Drop / open | Save | Sound cache |
|---|---|---|---|---|
| Live | The real clipboard, as today | The real file, as today | The real file, as today | As today |
| Recording | As live; the answer is kept | As live; the contents are kept | As live; the result is kept | As today |
| Replay, watched or headless | `castle` | The recorded PNG | In memory; a later read gets what this replay wrote | Files read, nothing else |
| Instant replay, attract demo | The played recording's or journal's answers; the live player's clipboard and files untouched | same | same, dropped when the scope ends | The live run's own cache, unchanged (decision 8) |
| Inner game (a replay) | As a replay, in its own context | same | same | Files read only; compiled sounds still shared in process |
| Rebaseline | OLD's answers, copied into NEW | same | In memory | Files read only |
| Audit | Both children are replays | same | same | Files read only |
| Browser | Demos: recorded answers. Live: the page's clipboard | Live: the picker; a replay shows none | Live: a download; a replay gives none | As its mode |

## 2. Decisions

1. **One question-and-answer door, not one door per layer.** `EngineSources` gains two members:
   - `touches_the_real_world: bool`, the mirror plan's property. Live: True. Host and recording doors:
     their inner doors'. Replay doors and a playback scope: False.
   - `outside()`, the run's *asker*. Code asks `ask(layer, call, question, live, unrecorded)`. `LiveOutside`
     runs `live` and keeps the answer; `ReplayOutside` serves the recorded answer and **never runs
     `live`**; with none, the layer's `unrecorded` rule.

   Clipboard and files are each one class over an asker, so live, recording and replay share the code and
   only the asker differs. A later layer adds a class, not a Protocol member. The doors hold everything,
   and they already live in a `ContextSlot` (`G/sources.py:282`), so **no new slot**. Observers join
   `_SourcesRegistry` beside the device ones (`G/sources.py:275`).
2. **The layers.**
   - **Clipboard:** `game_clipboard()`, used by the text widgets. `system_clipboard()` stays the platform's
     (audit row S9, shared: `plans/2026-10-25-engine-context.md:123`). The **AI console keeps calling it
     directly** (`G/ai_console.py:1207`, 1218): its keys are hidden beneath the recorder (`G/ai_host.py:90`),
     so what is pasted there must never be recorded.
   - **The player's files:** `player_files()`, for a path named **at run time by the player** (typed,
     dropped, picked) and for anything a game writes outside its saves: `read_bytes`, `read_text`, `size`,
     `write_text`, `write_bytes`, `hand_over` (a download). Package data (sprites, sounds, fonts) is the
     program, not the player's: it keeps its direct reads, is never recorded, and is allowlisted by
     decision 10.
   - **The sound cache is not a question:** its samples never change what a game sees
     (`docs/architecture/gameplay_replay.md:396`). It only asks `touches_the_real_world`.
   - **Saves and devices keep their doors.** Moving the device registry's queues onto the asker
     (`G/input/devices.py:2111`, 2562) is a possible later refactor, unneeded here: their repeat-the-last
     rule differs on purpose (2567).
3. **What is recorded.** A frame field `outside_answers` (ordered: layer, call, question, then value,
   content hash or error) and `outside_contents` (SHA-256 to text or base64, once per recording), with
   header fields of the same names for what came before recording began, as `device_enumeration` has
   (`G/engine/game_engine.py:2586`). Both frame fields are declared in `FrameContent`
   (`G/recording_history.py:90`; an undeclared field is refused at 155) and added to
   `REBASELINE_FRAME_FIELDS` (`G/replay/driver.py:479`). The trace format version does not change: absent fields read as none, as
   `scene_start` did (`G/recording.py:80`). A header list `outside_layers` names the layers this
   recorder keeps, so "nothing was asked" and "made before this existed" differ.
   - **Failures are answers.** An `OSError` is kept by errno *name* and re-raised as its subclass
     (numbers differ between systems); an unavailable clipboard raises
     `ClipboardUnavailableError` again. `copy` is recorded for that alone: a failed cut keeps the
     text (`G/ui/text_widgets.py:1407`). Its text is not.
   - **Questions** are paths as asked, with forward slashes. A drop event already records its path in full.
   - **Reading this run's own write** (the PNG conversion, `B/file_io.py:413`): marked `own_write`, contents
     kept too. A replay serves what *it* wrote, so a rebaseline over changed code sees the new
     text; a playback starting after the write, with no such write, serves the recorded contents.
   - **A write records its content hash** (text with LF ends), and a replay compares it (section 7, 4).
   - **Cost:** nothing on a frame that asks nothing. Probe here: base64, JSON and gzip of 1 MiB of random
     bytes 46 ms, 4 MiB 190 ms (one Mac, one run), on the recorder's main thread.
   - **Limits:** 1 MiB an answer, 8 MiB a recording. Over it, the live read still works; hash and size are
     kept as `omitted`, with one warning, and a replay refuses that read by name.
4. **Ordering.** Answers are served in order per (layer, call, question), within the frame they were given
   in. Code that no longer asks is logged; leftovers are dropped at the frame's end, so a late answer
   cannot serve an earlier question.
5. **No answer in the recording.** Never the real thing.

   | Recording | Paste | Read | Write |
   |---|---|---|---|
   | Made before (no `outside_layers`) | What this replay copied, else empty | This replay's own write, else `FileNotFoundError` | Kept in memory |
   | Made after | As above, **and a divergence naming frame, layer, question and caller** | Same | Same |

   An old recording warns once a layer. **The 26 committed recordings stay valid, none re-recorded.**
   Checked read-only here: none holds a drop event or a Ctrl/Cmd+C, X, V, S or O press, and none has a dialog
   as a frame's scene; 22 are recordings, 4 are the version-2 golden traces. That no bundled demo reads a
   player's file another way is inference, proved by PR 5's test.
6. **Writes in a replay stay in memory, like saves** (`G/state/sandbox.py`). The game sees success (or the
   recorded error), and any later read through the door gets its own bytes. Not refused: the dialog would
   show an error the live run did not. Not a sandbox folder: real disk work, clean-up and path leaks for
   no gain. `AnimatedSprite.save` and `BitmappySprite`'s write (`G/sprites/bitmappy_sprite.py:467`) go
   through the door, so every game is covered; `AnimatedSprite._load_toml` (`G/sprites/animated.py:1340`)
   first asks whether this run wrote the path, else reads package data as today. The player's files are
   loaded by text (`load_text`, `G/sprites/animated.py:1349`). Images decode from bytes with a name hint:
   probed here, PNG, BMP and JPG give the same pixels, flags and depth as by path.
7. **The replay's own outputs are the operator's:** `--rebaseline` NEW, `--replay-digest`, a bookmarked copy
   (S), the restart handoff and a frame stream still write. They never pass through a game's door.
8. **The sound cache in a replay is read-only:** files are read; no sweep, prune, folder, lock, wait, write,
   or deletion of a damaged file (`G/audio/disk_cache.py:245`); a miss compiles at once, in memory.
   - *Why read it:* samples are identical, and a cold compile is real: Mr. Muncher's cold golden takes
     1.0 s in all, 11 sounds (the record); Zombies' title 0.6-0.7 s cold in a browser against under 50 ms
     (`docs/architecture/sound.md:281`); a 16 s melody about 80 ms
     (`plans/2026-11-18-zombies-aint-my-neighbors-11-the-rest-of-the-sounds.md:27`). A read cannot wait.
   - *Why never write:* the mirror would stall the live game on that lock (the record: inference; measured
     on replays at 56 s with 11 locks held), and the files are the player's. An explicit
     `--sound-cache disk` does not change it: `sound-cache-fill` is the way to warm a folder.
   - Asked of the **installed** doors, not the scope's: an attract demo's compiles still reach the live run's cache.
     Otherwise its sounds would be in memory, never on disk, and recompile every launch.
   - The process store `ENGINE_SOUND_CACHE` is unchanged (`G/audio/library.py:1168`): tiles, host and
     restarts still share compiles.
   - *Windows:* a reader holding a file open can make a live writer's replace fail; that is already logged
     and not raised (`G/audio/disk_cache.py` rule 4).
9. **Privacy.** A recording already holds every key typed. This adds the pasted text and named files'
   contents, so:
   - **`--no-outside-contents` from the start** (the owner, 2026-11-25): the recording keeps hashes and sizes
     only, and a replay that needs the contents is refused by name.
   - Only `--record-trace` writes them. The instant-replay journal holds them in memory and drops them with
     the scene.
   - At the end of a run that kept any: one log line at the options block's level, e.g. "This recording
     holds 1 pasted text and 2 files' contents (34 KB)", plus the count in the header summary.
   - **Committed recordings (goldens, demos) hold only synthetic contents:** a test lists every answer held
     by a committed recording and fails on one not named in the workspace expectations. The recording
     scripts install an in-process clipboard (none does today: `install_clipboard` has no caller in
     `scripts/`) and a scratch folder.
   - Whether the AI may see a layer stays the mirror plan's decision; layers are tagged, so it can filter.
10. **Enforcement:** section 5.

## 3. Interfaces (names for the owner to change)

- `G/outside_answers.py` (leaf): `OutsideAnswer` (frozen pydantic, `extra='forbid'`), `AsksOutside`
  (Protocol: `ask`, `take_answers`), `LiveOutside`, `ReplayOutside`, the content store and limits.
- `G/sources.py`: the two members; `run_touches_the_real_world()` (installed doors, not scoped; True with
  none installed and **without making live doors**, since making them draws the run's seed, `G/sources.py:319`);
  an `OutsideAnswerObserver` beside `DeviceAnswerObserver` (241).
- `G/clipboard.py`: `GameClipboard` over an asker, `game_clipboard()`. `G/player_files.py`: `PlayerFiles`
  over an asker, `player_files()`; with no doors installed (tools) it is plain disk.
- `DiskSoundCache(..., read_only: bool)`; `_disk_layer` skips `clear_cache` when read-only.
- Implementers of `EngineSources` to change: `host.py`, `live_sources.py`, `recording.py`,
  `replay/driver.py`, `replay/playback.py`, and the double in `tests/test_host.py`.

## 4. The mirror, other genres, and what is locked out

- **Mirror:** rules 1-6 of its proxy are decisions 1, 3, 4 and 5: ordered answers, failures as answers, drift named,
  outputs nowhere, optional fields, hashes for large contents. A mirror streams `take_answers()` each frame
  beside the events and installs replay doors; it needs no second mechanism. Not covered: live voices,
  failed saves, device outputs, a missing mixer (its worklist); each can become a layer.
- **Other genres:** a level editor opens and saves maps with `player_files()`; a chat box pastes through the
  same widget; a visual novel exports a screenshot with `write_bytes`.
- **Locked out, said plainly:**
  - A C library that needs a real path to a player's file, streaming or memory-mapping, files over 1 MiB in
    an exact replay, folder listing and watching (add `names(folder)` when a game needs it).
  - Background threads: an answer has no frame there. The asker refuses off the main thread.
  - Network chat: sockets need a layer of their own with arrival as a recorded external event.
  - Copied images: the clipboard door is text only, as today.
  - A raw `read_bytes` of text this run wrote, replayed on an OS with other line ends, may differ.
- **Instant replay of a picked file:** the browser's picker calls `on_opened` between frames with no event
  (`G/user_files.py:23`, `B/editor.py:482`), so no recording can place it today. PR 6 makes it one.

## 5. Enforcement

- **Doors guard, extended** (`tests/test_engine_doors.py:45`, its allowlist-with-reason form):
  - names refused outside the doors: `pyperclip`, `pygame.scrap`, `system_clipboard` (allowed:
    `clipboard.py`, `ai_console.py`, the live asker), `installed_user_files`, and string-loaded forms;
  - every writing call in engine and member runtime code (`write_text_whole`, `write_aside_then_replace`,
    the calls `tests/ast_scanning.py:383` `writing_calls` finds, `unlink`, `mkdir`, `shutil`, `tempfile`,
    `pygame.image.save`), allowlisted by function with its reason (saves, sound cache, recorder, tools);
  - every `open`, `read_text`, `read_bytes`, `pygame.image.load` likewise; package-data readers listed.
  - Static limits: a path's origin cannot be seen, so a package-data reader given a player's path passes;
    the run-time proof covers that for what the suite replays.
- **The proof**, `tests/replay/test_replays_touch_nothing_real.py`: a child process sets an audit hook
  **before importing the engine**, replays, and reports. Its world is planted in `tmp_path`: `HOME`, a
  working folder with `a.toml` and the PNG, a sound-cache root holding a stale version folder, a damaged file and an
  over-limit folder, and a stand-in `pyperclip` that logs. Asserted: no writing `open`, rename, remove,
  mkdir, lock, socket or child process outside the operator's named outputs; no read under the player's
  folders except sound files; `pyperclip` unused; every planted tree identical in names, bytes
  and times. Known exception, by name until its own bug is fixed: the two host programs of
  `bugs/2026-11-24-every-engine-start-runs-host-programs.md`.
  - Runs: a Bitmappy session that pastes, drops, opens and saves; one game with sound; the same as an inner
    game, a scope, a rebaseline and an audit.
  - Blind spots: C code below Python (`os.stat` raises no audit event either), so the trees are compared too.
- **Mutation plants, each of which must turn the proof red:** the replay clipboard returns the platform's;
  a write goes to disk; a read falls back to disk; `read_only` ignored in each of sweep, prune, lock, write
  and damaged-file delete; an answer served out of its frame; a new file write added to a widget (static
  guard); the property answering True in a scope.
- **Conservation invariant:** for each recording made in the suite, the questions asked in its replay equal
  the answers it holds, in order, none over, none short.

## 6. Pull requests, most impactful first

Each: regression test proven to fail first, the proof grows by its layer, docs (`gameplay_replay.md`,
`playback/recording-file.md`, the module docstrings, CLAUDE.md within its line limit), bug record updated.
At most three in flight; 1 to 3 change no file format and stop the harm.

| # | Pull request | Files | Tests (behaviours) | Risks | Does not do |
|---|---|---|---|---|---|
| 1 | **A replay writes none of the player's files** (data loss). Property, asker, `PlayerFiles` writes in memory | `sources.py`, new `outside_answers.py`, `player_files.py`, the five door classes, `sprites/animated.py`, `sprites/bitmappy_sprite.py`, `B/file_io.py`; `tests/test_host.py`, engine sprite tests, `src/apps/bitmappy/tests/test_bitmappy_file_io.py`, the new proof | Replayed drop, dialog save and multi-frame save leave the folder as it was; the game reads back its own write; a live save still writes, whole; a save with no engine (a tool) writes; a scope's save stays in memory and is gone after; two contexts' writes never meet | A save path missed (the static guard lists all); a tool run inside a replay | Reads still touch today's file until PR 5 |
| 2 | **A replay leaves the clipboard alone** (data loss, privacy) | `clipboard.py`, `ui/text_widgets.py`, guard | A replayed copy, cut and paste call no platform clipboard; copy then paste in one replay agree; the AI console still uses the platform's and nothing it pastes is recorded; an unavailable clipboard live behaves as today | The harness's fixture hid this: tests use a stand-in pyperclip in a child | Paste text not yet recorded |
| 3 | **A replay only reads the sound cache** (every headless replay, up to 5 s a sound; mirror contract 1). Independent of 2, small | `audio/engine.py`, `audio/disk_cache.py`, `tests/audio/test_disk_cache.py`, `test_sound_cache.py`, `test_audio_engine_goldens.py`, `sound.md` | Cold: nothing written, locked, made or swept, no wait with every lock held; warm: files read, none compiled; a damaged file compiles and stays; live and `sound-cache-fill` unchanged; inner games share compiles; a scope keeps the live run's layer | `test_audio_engine_goldens.py:108` proves the disk layer **by having replays write it**: its cold child must turn writing on by a patch in the child, stated there | Async compiles |
| 4 | **Clipboard answers are recorded** (the format) | `recording.py`, `recording_history.py`, `replay/driver.py`, `rebaseline.py`, `instant_replay.py`, `scene_start.py`, `engine/game_engine.py` (header), recording scripts, the `--no-outside-contents` option | The record's `AAA`/`B` game matches; errors replay; instant replay, scope, rebaseline twice, reseed, audit; a missing answer diverges by name; every old recording loads with the same content hash; the end-of-run line; `--no-outside-contents` keeps hashes only and its replay is refused by name; `outside_layers` absent or present; a question in `setup()` before recording began | Content-hash classification; answers asked between frames | Files |
| 5 | **Files read are recorded and served** | `player_files.py`, `B/file_io.py`, `B/film_strip_sprite.py` (668), `B/animated_canvas.py` (1443, 828), `ui/dialogs.py` | PNG, TOML and film-strip drops and the Load dialog replay with the file changed, gone, and on another folder; missing-file and permission errors replay; own-write read after a rebaseline with changed output; each limit's edge (at, one under, one over); Windows path key; all 26 committed recordings replay with the same digests | Old personal recordings that loaded a file (section 7, 2) | Folder listing |
| 6 | **The browser's picker and downloads** | `user_files.py`, `B/editor.py`, `ui/dialogs.py` (474), `browser/browser_user_files.py` | A picked file arrives as a recorded external event and replays without a picker; a replayed save downloads nothing | A new named custom event type renumbers ids (named types are remapped, `G/recording.py:357`); browser runs needed | MasterHUB (`B/masterhub.py`): a replay in the page may still mirror to the hub; own bug if real |
| 7 | **The guard closed** | `tests/test_engine_doors.py`, a committed-contents test beside `tests/workspace_expectations.py` | Every plant in section 5; no committed recording holds unlisted contents | Allowlist noise | hid, miniaudio, sockets: the mirror's |

PR 1's door classes and `outside()` come first; 2 and 3 depend only on its property and may be reviewed in
parallel, 4 on 2, 5 on 1 and 4. Guard entries land with each PR; 7 is the sweep that proves none is left.

**Conflicts with work in flight**

| Work | Overlap | What to do |
|---|---|---|
| #319 `feature/lucid-circuit-switch` (merged `47263a03`) | `replay/driver.py` (local options), `engine/game_engine.py`, `tests/harness.py`, `tests/test_engine_context.py`, CLAUDE.md, `B/` tests' `conftest.py`. Its `ai_off_reason` uses `replay_sources is not None or has_scoped_sources()`, the same fact as `touches_the_real_world` | A one-line follow-up in PR 1 or 2 makes it ask the property |
| #320 `fix/faulthandler-left-off` | `tests/harness.py`, `tests/test_engine_context.py` | Ours adds no harness fixture or slot, so none expected (inference) |
| Local `refactor/engine-hud-labels` | No source overlap; it re-records Brave and Clockwork recordings | Either order: recordings without the new fields stay valid. If it records after PR 4 its recordings carry `outside_layers`, else not |
| `feature/mascot-demo` | Large: `sprites/animated.py` (705 changed lines), `sprites/bitmappy_sprite.py` (including a `read_text` line), `ui/dialogs.py`, `ui/text_widgets.py`, `ai_console.py`, `replay/driver.py`, `scenes/scene.py`, `workspace_expectations.py`, much of Bitmappy | Textual conflicts in PR 1 (save/load lines) and 2 (imports). Keep those edits to one line each; whichever lands second merges |

## 7. Decided by the owner (2026-11-25)

1. **A recording may hold what was pasted and the files opened,** by default for `--record-trace`, with the
   end-of-run line, the committed-recordings test and `--no-outside-contents` from the start (decision 9).
2. **An old personal recording that reads a file is refused** (decision 5), never given today's file.
3. **The sound cache is read-only in a replay** (decision 8), for now: Arcade tiles compile their sounds each
   launch until that game is played live. The Arcade's own plan may fill it, its host being live. The
   compile cost per tile was not measured.
4. **A replay compares what it would have saved** and diverges, naming the file. An intended change of a
   save format needs the recordings that save rebaselined (none today).

Decision 2 in an example. In October Pat recorded Bitmappy and dropped `tower.png`. That recording holds the
file's name, not its picture. Its replay says the recording has no such file, and diverges there. No
committed recording is affected.

## 8. Not verified

- Nothing was built or run but three read-only probes: event types and scenes of the 26 recordings, image
  decode from bytes, gzip time.
- That no path in the sweep of writing calls is missed: read by grep, not proved until the guard exists.
- The browser (clipboard, picker), Windows reader/writer interplay, Linux; a live game beside a replay.
- The riskiest assumption: that every player file reaches the game by a path the door sees on the main
  thread, so no codepath hands a player's path to a loader that reads package data directly. The
  proof catches only what the suite replays. Sibling paths not traced: `B/ai_manager.py`'s temporary TOML
  files (792, 945) and `SpriteFactory.load_sprite` of them (1353), reached only with an AI answer (#319 stopped it in a
  replay); `B/controllers/error_handling.py:377`, whose caller was not found.
