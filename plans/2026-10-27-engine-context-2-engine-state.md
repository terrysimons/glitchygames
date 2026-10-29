# Engine Context, Sub-plan 2: The Engine's Own State — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task (execution is subagent-driven: the owner, 2026-10-25, decision 4 of the master plan). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every remaining piece of the engine's own process-wide state (audit rows C7–C19 of
the master plan, C16 excepted, and the new row C20 the review found) belong to an engine context, prove for each that two contexts in
one process never see each other's value (reproducing the collision the engine-context spike
found, where it found one), and turn the audit into guards: an allowlist scan of the engine and
every member for process-wide state, and a scan that nothing restyles a shared cached font.

**Architecture:** The same mechanism as sub-plan 1, never save-and-restore swapping. State with no
owning object (the shared event managers, the font options, the performance manager, the
singleton sprites, the debug-events log set, the sprite counters, the internal-post tracker,
and the context's current engine) becomes a `ContextSlot` declared in the module that owns it
and read with `current_context().value(slot=...)` when needed, each public function keeping its
signature. State of an object the context already owns (the `GameEngine`'s options, game, event
handlers and event bookkeeping; the per-context `SceneManager`'s copy of the options) moves from
the class onto that object, under lowercase instance names (`engine.options`,
`engine.event_handlers`, `manager.engine_options`, ...), so it is per context because the object
is (answer 1, 2026-10-28). The old public names stay as **read-only views** that store nothing and forward
to the current context's object (answer 2, 2026-10-28): each view is one descriptor in the
class body (`ReadOnlyView`, `ClassOnlyView`) whose overloaded `__get__` answers the current
context's value when read on the class and the object's own state when read on an instance; a
write-refusing metaclass (`ReadOnlyViews`, or `ReadOnlyViewsABC` for `Sprite`, whose metaclass is
`ABCMeta`) makes class-level writes raise; and `glitchygames.performance.performance_manager` is
a module `__getattr__` (PEP 562), marked as a view by its module's `READ_ONLY_MODULE_VIEWS`
(a module `__getattr__` alone is never a view). Writing to a
view raises an `AttributeError` naming where to write; engine code never reads a view (a guard).
`current_engine()` answers with the context's engine. Then three guards:
`tests/test_process_state_guard.py` (every module- and class-level mutable, rebound name,
`global` and cache in the engine and every member is either gone into a slot, computed by a view,
or listed with its audit row), `tests/test_shared_font_cache_guard.py` (R9, decision 2) and the
view guards in `tests/test_read_only_views.py`.

**Tech Stack:** Python 3.14 (`contextvars`, PEP 695 generics), pygame-ce, pytest + pytest-mock +
xdist + pytest-cov, ruff, basedpyright, ty.

**Spec:** [2026-10-25-engine-context.md](2026-10-25-engine-context.md) (the master plan: the audit,
the design, the sub-plans, the owner's decisions). This is its sub-plan 2: "The engine's own state:
rows C7-C19 ..., with the test lines that reach C17 and C19 rewritten under Decisions, 1; the guard
test that nothing changes a cached font's style in place (R9, Decisions, 2); and the process-state
guard (the audit as an allowlist scan of the engine and every member)." Evidence: the engine
context spike, `.superpowers/arcade-spike/engine-context-spike-findings.md` in the main checkout
(2026-10-27), with `engine-changes-main.diff` and `arcade_spike_in_process.py` beside it.

## Questions for the owner (all answered, 2026-10-28)

No open questions. The owner answered both questions and asked three more of their own, on
2026-10-28; the answers are decisions now (called "answer N" below, to keep them apart from the master
plan's decisions 1-5), and the tasks implement them.

1. **C7–C11 live on the objects (the owner, 2026-10-28).** The question: the master plan's rule 1
   says per-context state is a `ContextSlot`; its rule 6 says objects are not bound to a context.
   The engine's options, game, event handlers and event bookkeeping (C8–C11) belong to one
   `GameEngine`, and `SceneManager.OPTIONS` (C7) to the scene manager, already one per context
   (C6). **Decision: instance attributes on those objects** (Tasks 2, 5, 7): an object belongs to
   the context that made it, two engines never share even inside one context, and nothing reads
   the current context to answer for an object. Engine code uses the instance names
   (`self.options`, `self.event_handlers`, `self.missing_events`, `self.unimplemented_events`,
   `self.last_event_miss`, `self.game`; the scene manager's `self.engine_options`).
2. **The old names stay, as read-only views (the owner, 2026-10-28).** First answer: remove them
   with no aliases, the only loss being REPL and debugger convenience. Replaced the same day by
   the owner's idea: "What if the old names were actually just lambdas that called the instance
   (if not None)?" **Decision:** the state moves exactly as planned; the old public names become
   computed, read-only views that store nothing:
   - `GameEngine.OPTIONS`, `.EVENT_HANDLERS`, `.MISSING_EVENTS`, `.UNIMPLEMENTED_EVENTS`,
     `.LAST_EVENT_MISS`, `.game` read `current_engine().<instance attribute>`, or `None` when the
     context has no engine;
   - `SceneManager.OPTIONS` reads the current context's scene manager's `engine_options` (`None`
     when the context has no scene manager);
   - `FontManager.OPTIONS` reads the current context's font options (a fresh context: `{}`);
   - `Sprite.SPRITE_COUNTERS`, `.SPRITE_BREAKPOINTS`, `.SPRITE_COUNT` read the current game's
     sprite counters (a fresh context: empty, `None`, `0`);
   - `glitchygames.performance.performance_manager` reads the current context's
     `AdaptiveClamping()`, through a module `__getattr__` (PEP 562).
   The owner asked for class-level properties on a small metaclass per class; after the review
   (I-1, I-4) each view is one descriptor in the class body, read on the class for the current
   game's value and through an instance (`engine.OPTIONS`, `manager.OPTIONS`) for that object's
   own state, and the metaclass (one shared `ReadOnlyViews`, `ReadOnlyViewsABC` for `Sprite`)
   only refuses writes (Task 1 records the prototype and why). Writing to a view
   (an assignment, `del`, `mocker.patch.object`) raises `ReadOnlyViewError` (an
   `AttributeError`) naming where to write instead. Rules, each pinned by a test (Task 1 and each
   view's task): engine code never reads a view; each view answers per context and with `None` or
   an empty default outside a game; setting a view raises. `current_engine()` stays (Task 1).
   Readers in the tests that type-check stay as they are; writers, stand-ins that offered the old
   name, and class-level readers that use a `None`-able view as a value (basedpyright strict
   refuses them: review I-4) are rewritten: about **200 test lines in 22 files** (each task
   lists its lines; the review found the extra writers, I-2, I-3).
3. **Performance reports: per game, and the wrapper's is the aggregate (the owner, 2026-10-28,
   asked; a requirement of Task 4).** Each context has its own performance manager, so each game
   gets its own report. The Arcade's wrapper is itself a game in its own context, and its frame
   contains every inner game's ticks, so its report is the whole system's aggregate: a wrapper
   frame's time is the sum of the inner games' work plus its own. Task 4 pins both.
4. **Sprite counters per game (the owner, 2026-10-28): confirmed** (Task 12, as planned).
5. **Documentation (the owner, 2026-10-28):** "update the documentation since this changes some
   assumptions". Task 16 documents the views ("read-only; the current game's; None outside a
   game") everywhere the docs state or rely on the old process-wide names or on one game per
   process, and guards that no living doc tells code to write to a view.
6. **What it costs (the owner, 2026-10-28, asked).** Answered by the per-read figures under "Calls"
   and enforced by Task 17's performance gate: interleaved runs of the base and the branch on the
   same day, a stated noise rule, and per-call and per-read micro-benchmarks with explicit
   thresholds (review I-9).
7. **C16 belongs to the player roster (the owner, 2026-10-28: "makes sense for bitmappy").** C16
   (`MultiControllerManager`'s singleton) is out of this sub-plan and has an owner: the
   player-roster work, design `plans/2026-10-28-player-roster-design.md` on branch
   `feature/player-roster`, which moves the generic multi-controller code into the engine as a
   per-context roster and deletes `MultiControllerManager`'s singleton. `plans/future-work.md`
   points C16 there. The process-state guard keeps listing it under C16 until that work lands.
   Bitmappy's two other pieces of process state the guard found, `onion_skinning_manager` and
   `ai_training_state`, are not the roster's: they stay listed (under C16, Bitmappy's own), with
   no owning plan yet, and the same `plans/future-work.md` entry names them.
8. **The review's fixes (the owner, 2026-10-28: approved).** The adversarial review of this plan
   (`.superpowers/arcade-spike/sub-plan-2-adversarial-review.md` in the main checkout: I-1 to
   I-10, M-1 to M-12) is applied; each fix names its finding.

## Decisions this plan applies (the owner, 2026-10-25, master plan "Decisions")

1. "A test line that reaches private module state this plan moves (`randomness._STATE`,
   `recording._INTERNAL_POSTS`: 15 lines in `tests/test_recording.py`,
   `events.base._unhandled_event_types`: 4 lines, and any like them) is rewritten, in the sub-plan
   that moves the state, to test the behaviour where it is observable (posts tagged internal or
   external in a recorded session's event batches; the unhandled-event warning and the shutdown
   table through `caplog`), and to read through the current context
   (`current_context().value(slot=...)`) only where the state has no observable effect. The engine
   gets no test-only module accessors."
2. "The font caches (R9) stay shared, one per process, with a guard test that nothing changes a
   cached font's style (bold, italic, underline, size) in place. Owned by sub-plan 2."
3. "`ContextSlot` is internal to the engine, not public API, until a game needs module-level
   state; games keep their state on their scenes."
4. "Execution is subagent-driven, every sub-plan."
5. "The path guard. This master plan goes on `LIVING_PLAN_FILES` ...; the sub-plans do not."

And from the master plan's "Options considered and set aside": "Save and restore the module
globals on every switch ... one forgotten global leaks silently". The spike's class-state swap
(`ClassStateSwap` in `spike_two_games.py`, 13 attributes swapped around every switch) is that
option; this plan replaces it, it does not port it.

## Calls this plan makes (mine, not the owner's)

- **Order: the rows that broke first.** C10 (PaddleSlap diverged at frame 2 when unswapped), C19
  (its last frame, 621: `event Quit missing internal event`) and C14 (one game's FPS samples merged
  under another's scene: 257 + 975 + 167 samples for 1399 frames) lead (Tasks 2–4), then the
  options (Tasks 5, the spike's weak evidence: both goldens recorded 800x480, 60.01 FPS, the same
  seed), then the latent rows.
- **C19 moves here, its queue in sub-plan 6.** Settled by the master plan (C19's note and
  sub-plan 6's line); the spike asked again (its open question 2). Moving the tracker alone fixes
  the collision the spike measured (one context's pump forgetting another's pending posts); where
  a context's posts go (SDL's one queue, S5) stays sub-plan 6's. The fix holds for the
  `forget_pending_posts` path the spike measured; it does not cover an engine callback run in
  another context's switch (review M-3: `pygame.register_quit(self.quit_game)`,
  `game_engine.py:1243`, piles one callback per engine, and `pygame.quit()` runs them all in the
  caller's context, where `quit_game`'s posted QUIT is tracked): that is sub-plan 7's (S8).
- **C14 per context**, not keyed by context inside one manager (the spike's open question 3): the
  audit row says per context, and a keyed manager would be a second mechanism. `AdaptiveClamping()`
  answers with the current context's manager, exactly as `SceneManager()` does (C6).
- **C16 is not in this sub-plan: the owner's answer 7.** Why it cannot be done here:
  `MultiControllerManager` is Bitmappy's (`src/apps/bitmappy/src/bitmappy/controllers/manager.py:69`),
  the engine must not import an app, and `ContextSlot` is internal to the engine (decision 3).
  Its test-isolation symptom, BUGS.md #234, is fixed by the test-only fixture
  `fresh_controller_manager` (`src/apps/bitmappy/tests/conftest.py`, commit dfb569b9 on PR #111's
  branch, squash-merged to main as 3f1999a9).
- **Different options in the isolation tests** (the spike's open question 1): every engine-level
  test here starts its two engines with different options, and Task 15 runs two engines with
  different options side by side.
- **Every new slot is reset per test** in the default context by `tests/harness.py` (as
  `fresh_random_streams` does), so tests no longer clear these by hand. Two resets are not
  `reset_value` calls, and are enough (review M-6): the internal-post tracker (Task 3) is reset
  through `reset_internal_post_tracking()`, which the harness already calls and which resets every
  field of the current (default) context's tracker; the font options (Task 9) through the harness's
  existing `FontManager.OPTIONS.clear()`, which empties the current context's dict.
- **New, unaudited state the guard finds** is classified in Task 13's table and added to the master
  plan's audit in Task 16: `Sprite.SPRITE_COUNT` (moves with C18), `RendererService.
  pygame_initialized` (new S16), the engine's event-type tables (new R15), the Bitmappy pieces
  (under C16), and `<GameClass>.options` (new C20, found by the review: Task 6 removes it). The
  re-check on main (3f916b97, 2026-10-29) found two more, ruled by the controller the same day,
  neither put in a context: `GameEngine.PYGAME_FOUND_WITH_SDL_SIGNAL_HANDLERS` (S8, process
  services: whether this process's pygame started with SDL's signal handlers) and
  `glitchygames.events.base.pygame_event_names` (R15: pygame's compiled event names, an
  immutable table scanned once per process, the same in every context).
- **Slots and views stay off the engine's hot paths.** Measured per read on the owner's machine
  (2026-10-28): a class or instance attribute about 12 ns, an instance property about 19 ns, a
  slot read about 73 ns, a context switch about 430 ns; a class-level view read over
  `current_engine()` in the shape Task 1 builds (the descriptor's `__get__`, `read_current`,
  `_running_engine_attribute`, a slot read and the read itself, in a `try`) about 181 ns (the
  review's re-check, a timeit emulation; the owner's 80–110 ns was the earlier metaclass-property
  design). Task 1 measures the real one. So engine code reads its own state from the object (`self.options`,
  `self.event_handlers`: the dispatch at `game_engine.py:3620` runs per event), reads a slot once
  per function into a local, and never reads a view (Task 1's guard); the views exist for games,
  tools, tests and the REPL. Task 17's gate measures the result against the base.
- **Views in the class body; one shared write-refusing metaclass (review I-1, I-4).** The first
  version put class-level views on a metaclass per class beside instance views in the class body;
  basedpyright strict cannot type that (Task 1 records the prototype), and `Sprite`'s metaclass is
  `abc.ABCMeta`, not `type` (its MRO has `EventInterface(abc.ABC)`, `src/glitchygames/events/base.py:1415`,
  through `MouseEvents`, `events/input_event_interfaces.py:139`; all 25 engine subclasses of
  `Sprite` inherit it), so a `type`-based metaclass would conflict. `GameEngine`, `SceneManager`
  and `FontManager` (metaclass `type`) take `ReadOnlyViews(type)`; `Sprite` takes
  `ReadOnlyViewsABC(ReadOnlyViews, abc.ABCMeta)`. A member class mixing a `Sprite` with a
  `Protocol` (metaclass `_ProtocolMeta`) would conflict; none does at b5f16688 or at 3f916b97 (`src`, `tests` and
  `scripts` searched), and collecting the suite catches one (Task 1).
- **The scene manager's own copy is `engine_options`, not `options`.** The event managers are
  built with `game=self.scene_manager` (`game_engine.py:1771-1803`) and `unhandled_event` reads
  `getattr(game, 'options', None)` (`events/base.py:249`): a scene manager with an `options`
  attribute would switch on unhandled-event checks that are off today. The engine's own is
  `options`: no `unhandled_event` call is given the engine (checked in Task 5).
- **`current_engine()` is the engine constructed last in the context**, held in a slot
  (`CURRENT_ENGINE_SLOT`), never a process-wide variable: what the class attributes answered
  with before (each `GameEngine.__init__` overwrote them), now per context.

## Where each row is now (verified at b5f16688; rechecked on main at 3f916b97, 2026-10-29, after #112–#116; the audit's lines are as of 53869ac4)

| Row | State, declared at | Writers | Readers | Audit's location still right? |
|---|---|---|---|---|
| C7 | `SceneManager.OPTIONS`, `src/glitchygames/scenes/scene.py:231` | `scene.py:377` (the `game_engine` setter), `src/glitchygames/engine/game_engine.py:3322` (`_build_game`), `src/glitchygames/replay/tools/golden_traces.py:476` (`install_game`) | `scene.py:378-383, 1635, 2143, 2613`; `src/glitchygames/replay/playback.py:1239` (`manager.OPTIONS`) | no: audit says `scene.py:193` |
| C8 | `GameEngine.OPTIONS`, `game_engine.py:702` | `game_engine.py:1117, 1121` (`initialize_arguments`, a classmethod) | `game_engine.py:1122, 1126, 1778, 1788, 1884, 1931, 2022, 2964-2997, 3029, 3145 (_log_the_startup_options, new since b5f16688: the startup options block), 3181, 3273-3296, 3319, 3480`; `golden_traces.py:474` | no: audit says `:407` |
| C9 | `GameEngine.game`, `game_engine.py:693` | `game_engine.py:1331` (class), `:3319` (instance, `_build_game`) | `self.game` in `initialize_event_handlers` (`:1455`), `initialize_system_icons` (`:1735`), `trace_recording_header` (`:1903`), `_game_name` (`:3150-3160`, new since b5f16688), `_begin_start` (`:3162`), `_build_game` (`:3310`) | no: audit says `:398` |
| C10 | `GameEngine.EVENT_HANDLERS`, `game_engine.py:718` | `game_engine.py:1473-1485` (`initialize_event_handlers`), `:1531-1549` (`initialize_input_event_handlers`) | `game_engine.py:3620-3621` (`process_events`) | no: audit says `:420` |
| C11 | `LAST_EVENT_MISS`, `MISSING_EVENTS`, `UNIMPLEMENTED_EVENTS`, `game_engine.py:704-706` | `:4206` (`process_unimplemented_event`), `:4331` (`missing_event`), `:4366` (`__getattr__`) | `:4200, 4330-4336` | no: audit says `:409-411` |
| C12 | `ResourceManager.__instances__`, `src/glitchygames/events/base.py:365` | `base.py:395-396` (`__new__`), `:419` (`release_shared_instances`, called at `game_engine.py:1768`) | `base.py:395-399` | yes (lines moved) |
| C13 | `FontManager.OPTIONS`, `src/glitchygames/fonts/font_manager.py:137` | `font_manager.py:187-196` (`__init__`), `:324, 326, 394, 396` (`font`/`pygame_font` fill defaults in place), `:469` (`set_font_system`) | `:199, 320, 390, 447, 480` | yes |
| C14 | `AdaptiveClamping._instance` `src/glitchygames/performance/adaptive_clamping.py:79`; `performance_manager` `:926` | `adaptive_clamping.py:84-86` | `scene.py:389-392, 1491-1494, 1657-1670`; `game_engine.py:2931-2941, 2987-2997`; `src/glitchygames/performance/__init__.py:3,5`; `src/glitchygames/performance/example_usage.py:5, 22, 35` | yes (lines moved) |
| C15 | `__instance__` of `Singleton`, `SingletonBitmappySprite`, `FocusableSingletonBitmappySprite`, `src/glitchygames/sprites/bitmappy_sprite.py:1019, 1053, 1101` | `bitmappy_sprite.py:1042, 1066, 1114` | `:1039, 1063, 1111`; users: `MenuBar` (`src/glitchygames/ui/menus.py:34`) | yes |
| C16 | `MultiControllerManager._instance`, `src/apps/bitmappy/src/bitmappy/controllers/manager.py:69` | `manager.py:75, 104` | `manager.py:74, 103`; `get_instance()` callers `src/apps/bitmappy/src/bitmappy/film_strip_events.py:374`, `controllers/film_strip_operations.py:164` | no: audit says `src/glitchygames/bitmappy/controllers/manager.py:69` (Bitmappy moved, #110) |
| C17 | `_unhandled_event_types`, `src/glitchygames/events/base.py:221` | `base.py:275` | `base.py:274` | yes (lines moved) |
| C18 | `Sprite.SPRITE_BREAKPOINTS` `src/glitchygames/sprites/sprite.py:45`, `SPRITE_COUNTERS` `:46-48`; also `SPRITE_COUNT` `:49` (not in the audit) | `sprite.py:62-69` (`break_when`), `:145-157` (`__init__`) | `sprite.py:160-170`; `game_engine.py:4265-4268` (`_log_sprite_count_report`) | partly: `SPRITE_COUNT` is missing from the row |
| C19 | `_INTERNAL_POSTS` (`InternalEventPosts`, `src/glitchygames/recording.py:384-411`), `recording.py:414` | `recording.py:417-451, 477-487, 585-603`; callers `game_engine.py:1304-1305, 3662`, `src/glitchygames/replay/driver.py:1551, 1558, 1589` | `recording.py:454-542` | yes |
| C20 (new, review I-6) | `<GameClass>.options`: `initialize_arguments` sets the game's options on the game's Scene **class** | `game_engine.py:1129` | no reader in the engine or the members; tests `tests/engine/test_game_engine.py:255`, `tests/engine/test_engine_properties.py:86` | not in the audit |
| R9 | `FontManager.RENDER_CACHE`, `_font_cache`, `font_manager.py:138-139` | `font_manager.py:345, 375, 412, 426` (`RENDER_CACHE` is declared and never used) | `:332-333, 402-403` | yes |

Two more pieces of process state, found by the re-check on main and ruled by the controller
(2026-10-29), are not rows of this sub-plan and go in no context: `GameEngine.
PYGAME_FOUND_WITH_SDL_SIGNAL_HANDLERS` (`game_engine.py:710`, rebound at `:1142, 1147` in
`_warn_about_a_pygame_that_may_own_the_signals`) under S8, and `events/base.py`
`pygame_event_names` (`@functools.cache`, #114, behind `supported_events`) under R15. Task 13
lists both; Task 16 adds them to the master plan's audit.

Test lines that reach C17 and C19 (decision 1), verified: `tests/test_recording.py:144, 525, 591,
597, 598, 604, 623, 873, 877, 933, 937, 945, 954, 956, 964` (15) and
`tests/engine/test_game_engine.py:2863`, `tests/events/test_events_core.py:1268, 1280, 1334` (4):
the counts in the audit are right.

## Not in this sub-plan

What the spike found that belongs to later sub-plans; nothing here touches it.

- **The render target** (S1): an inner context draws on its own offscreen surface and never calls
  `set_mode`; the spike's `render_target.py` and `display_surface()`. Sub-plan 4.
- **The opaque tiles**: an unpresented render target must be made opaque (or made without an
  alpha mask), or per-pixel-alpha sprites vanish on macOS only (the spike's "Bug: animated sprites
  vanish"). Sub-plan 4.
- **Window services and the window's size** (S2): caption, icon, cursor; a launched game's
  `set_mode` not undone. Sub-plan 4. The debug overlay on an unpresented frame: sub-plan 4.
- **Audio** (S3, S4): every engine reserves the same live-voice channels 0–3; one mixer. Sub-plan 5.
- **The event queue** (S5): one game's FPS event taken by the other (Mr. Muncher diverged at frame
  29, PaddleSlap at 30); a per-context private queue. Sub-plan 6, which also decides "first drain"
  apart from "blocked SDL" (the spike's caveat on `is_first_drain`).
- **SDL input blocking** (S6): an inner replay blocks KEYDOWN for the whole process; the live
  engine's `allow_every_event_type()` unblocks it for good. Sub-plan 6.
- **The joystick subsystem** (S7). Sub-plan 6.
- **The hosted start**: `GameEngine.start()` blocks inside a crash boundary whose teardown calls
  `pygame.quit()`; a context-owning engine must hand itself back instead. Sub-plan 7.
- **`sys.argv`**: every engine parses `sys.argv`, and the Brave Adventurer launcher rewrites it.
  Sub-plan 7 (an inner engine takes its options explicitly). This plan's tests patch `sys.argv`
  per engine, as existing tests do.
- **Process services** (S8): `_enter_headless_mode`, `pygame.init`, `register_quit`,
  `setswitchinterval`, `logging.basicConfig`, signal handlers. Sub-plan 7.
- **Pacing**: an inner game stepped once per outer tick, unpaced. Sub-plan 7 (or the Arcade's
  `GameHost`/`TickPacer`).
- **An inner game that raises; frames run outside their context**: sub-plan 3.
- **C16**: the player-roster work (answer 7). Bitmappy's `onion_skinning_manager` and
  `ai_training_state`: no owning plan yet (`plans/future-work.md`).
- **The engine's threads** (voice recognition, controller audio) see the default context unless
  started with a copied one; this sub-plan adds slots they would then read wrongly (the shared
  managers, the font options, the performance manager, the current engine). Sub-plan 3 decides
  the threads' rule (master plan, "Still open"); review M-3.
- **Engine callbacks run in another context** (`pygame.register_quit`): sub-plan 7 (S8).

## Global Constraints

- Work on `feature/engine-context-2-engine-state` in the worktree
  `/Users/terry/Dropbox/dev.glitchygames/glitchygames-engine-context-2`. The branch is on `main`
  (3f916b97; PR #111 merged 2026-10-28); Task 0 checks the base. Never touch the main checkout or another
  branch.
- Python 3.14. Holders of per-context state are `@dataclasses.dataclass` (like
  `InternalEventPosts`, `EngineRandomState`). Test value types are pydantic models with
  `model_config = ConfigDict(frozen=True, extra='forbid')`, like sub-plan 1's `StandInGame`.
- pytest-mock (`mocker`) only, never `unittest.mock`; keyword arguments in every call we write;
  full names (no abbreviations).
- No `# noqa`, no `# ruff: ignore`, no new `# type: ignore` / `# ty: ignore` / `# pyright:
  ignore`, no lint or type-checker configuration loosened. The suppressions on the class-attribute
  rebindings this plan removes go with them (`scene.py:377`, `game_engine.py:1117, 4366`,
  `sprite.py:63, 157`) and `adaptive_clamping.py:86`'s `# type: ignore[return-value]` is replaced
  by `cast`, as Task 7 of sub-plan 1 did for `SceneManager`.
- Coverage stays at 100% (`--cov-fail-under=100`).
- Lint before tests: `ruff format`, `ruff check`, `basedpyright`, `ty check` on the touched files,
  then the tests. TDD: write the failing test, run it and see it fail for the stated reason, then
  implement.
- Every existing test, golden replay, golden trace and bundled demo passes. Existing test lines
  change only where a task lists them (decision 1; answer 2): writers of the old names
  (assignments, `del`, `mocker.patch.object`/`mocker.patch` of a view, which now raise), resets of
  `_instance` and `__instance__`, the reaches into `_INTERNAL_POSTS` and `_unhandled_event_types`,
  declaration checks that read a view with no game running, stand-ins that offered the old name,
  and class-level readers of a `None`-able view used as a value; about 200 lines in 22 files.
  Readers of a view stay as they are. Everything else in existing test files only gains lines.
- Engine tests use stand-in scenes inside `tests/` and never import a member.
- Engine code never reads a view (`tests/test_read_only_views.py::test_the_engine_never_reads_a_view`):
  it reads its objects (`self.options`), a slot once per function into a local, or the owner
  function (`sprite_counters()`, `AdaptiveClamping()`).
- `ContextSlot` stays internal to the engine (decision 3): only `src/glitchygames/` declares slots.
- Recordings are never re-recorded or rebaselined; no `*.jsonl.gz` file changes.
- Commits: stage explicitly by path (never `git add -A` or `git add .`), message ending with the
  trailer `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`; never push;
  never restore files from git. The pre-commit `replay-metrics` hook measures every golden replay
  and bundled demo on a commit that changes `src/` (about 15 s) and stages its ledger rows into the
  same commit; never `--no-verify`, never `SKIP=`; keep no untracked files under `src/`.
- Code comments name modules by dotted name (`glitchygames.engine_context`), plans by path.
- Each new slot gets, in the same task: its declaration, its isolation check in
  `ISOLATION_CHECKS` (`tests/test_engine_context.py:851`; `test_every_engine_slot_has_an_isolation_check`
  in `tests/test_engine_context_source_guards.py:82` fails otherwise), its per-test reset in
  `tests/harness.py`, and a test reproducing the collision the spike found (or, where it found
  none, two contexts holding different values).
- Each new view gets, in the same task: its `ReadOnlyView` (or `ClassOnlyView`) in the class
  body, its entry in
  `VIEW_CHECKS` (`tests/test_read_only_views.py`; `test_every_view_has_a_check` fails otherwise:
  two contexts each see their own value, a fresh context reads `None` or the empty default, and
  setting the view raises naming where to write), and the engine's own reads moved off it.

Standard commands (every task uses them; `<files>` are the task's touched files):

```bash
uv run ruff format <files>
uv run ruff check <files>
uv run basedpyright <files>
uv run ty check <files>
uv run pytest --dummy-only --no-cov -q <test file> -k <test name>
uv run pytest --dummy-only        # the whole suite, coverage 100%
```

## Review Focus

1. **Two engines with different options.** The spike could not see an options mix-up (both goldens
   recorded the same options). Pinned by `test_each_engine_keeps_the_options_it_was_started_with`
   (Task 5) and `test_two_engines_with_different_options_side_by_side_read_what_each_reads_alone`
   (Task 15).
2. **One context's reset dropping another's state.** A new engine's `__init__` calls
   `reset_internal_post_tracking()` and its build calls `release_shared_instances()`; in the spike
   these reached the other game. Pinned by
   `test_a_new_run_in_one_context_keeps_another_contexts_tracking` (Task 3) and the release step of
   `check_shared_instances` (Task 8).
3. **A view that is written, or read by the engine.** A test or a game assigning
   `GameEngine.OPTIONS = ...` (or `mocker.patch.object` on it) would silently replace a class
   attribute before; now it must raise and say where to write, and no engine module may read a
   view on a hot path. Pinned by `test_writing_a_view_raises_and_names_where_to_write`,
   `test_the_engine_never_reads_a_view` and each view's check (Task 1, then each view's task).
4. **A view outside a game.** A REPL or a tool in a context with no engine (or a scene manager
   with none attached) reads `None`, never another context's value; `current_engine()` raises,
   naming the context. Pinned by every `VIEW_CHECKS` entry and
   `test_current_engine_refuses_when_no_engine_runs_in_the_context` (Task 1).
5. **The aggregate report.** An outer game stepping inner games must report the whole tick, and no
   inner sample may land in the outer manager or another inner one. Pinned by
   `test_an_outer_games_report_covers_the_inner_games_it_steps` (Task 4).
6. **State the guard cannot see, and state it must not see.** An int class attribute rebound in a
   method (`Sprite.SPRITE_COUNT += 1`), a `global`, a `functools.cache` and a module-level object
   must be reported; a view (a metaclass property, a class-body view descriptor) stores nothing
   and must not be. Pinned by `test_the_process_state_scan_finds_every_kind` (Task 13).
7. **Subclass singletons** (`MenuBar`) per context: `test_each_context_has_its_own_singletons`
   (Task 10). **A shared cached font restyled by one context**:
   `test_the_font_style_scan_finds_every_in_place_change` (Task 14).

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `src/glitchygames/read_only_views.py` | Create (Task 1) | `ReadOnlyView`, `ClassOnlyView`, `ReadOnlyViews`, `ReadOnlyViewsABC`, `ReadOnlyViewError`, `ViewReadError` (standard library only) |
| `src/glitchygames/engine/game_engine.py` | Modify (Tasks 1, 2, 4, 5, 6, 7, 12) | `metaclass=ReadOnlyViews`, `current_engine()`, `NoRunningEngineError`, `CURRENT_ENGINE_SLOT`; options, game, handlers, event bookkeeping on the engine; sprite report through `sprite_counters()` |
| `src/glitchygames/engine/__init__.py` | Modify (Task 1) | re-exports `current_engine`, `NoRunningEngineError` |
| `src/glitchygames/scenes/scene.py` | Modify (Tasks 1, 4, 5) | `metaclass=ReadOnlyViews`; the manager's own `engine_options`; `AdaptiveClamping()` |
| `src/glitchygames/replay/tools/golden_traces.py`, `src/glitchygames/replay/playback.py` | Modify (Task 5) | the engine's and manager's own options |
| `src/glitchygames/recording.py` | Modify (Task 3) | `INTERNAL_POSTS_SLOT` replaces `_INTERNAL_POSTS` |
| `src/glitchygames/performance/adaptive_clamping.py`, `performance/__init__.py`, `performance/example_usage.py` | Modify (Task 4) | `PERFORMANCE_MANAGERS_SLOT`; `performance_manager` becomes a module view |
| `src/glitchygames/events/base.py` | Modify (Tasks 8, 11) | `SHARED_INSTANCES_SLOT`, `UNHANDLED_EVENT_TYPES_SLOT` |
| `src/glitchygames/fonts/font_manager.py` | Modify (Tasks 1, 9) | `metaclass=ReadOnlyViews`; `FONT_OPTIONS_SLOT` |
| `src/glitchygames/sprites/bitmappy_sprite.py` | Modify (Task 10) | `SINGLETONS_SLOT` |
| `src/glitchygames/sprites/sprite.py` | Modify (Tasks 1, 12) | `metaclass=ReadOnlyViewsABC`; `SPRITE_COUNTERS_SLOT`, `SpriteCounters`, `sprite_counters()` |
| `tests/test_read_only_views.py` | Create (Task 1), extend (Tasks 2, 4, 5, 7, 9, 12) | the views' mechanism, `VIEW_CHECKS`, the engine-reads-no-view guard, the engine context page's views section |
| `tests/test_engine_context.py` | Modify (Tasks 1, 3, 4, 5, 8–12) | an isolation check per new slot; `check_scene_managers` covers C7 |
| `tests/harness.py` | Modify (Tasks 1, 3, 4, 5, 7, 8, 10–12) | per-test resets of the new slots; drops the resets of what became views |
| `tests/test_process_state_guard.py` | Create (Task 13) | the audit as an allowlist scan |
| `tests/test_shared_font_cache_guard.py` | Create (Task 14) | nothing restyles a cached font in place |
| `tests/test_suite_collection.py` | Modify (Tasks 13, 14, 16) | both guards in `REPOSITORY_TEST_FILES`; no living doc writes to a view |
| `tests/engine/test_engine_contexts_side_by_side.py` | Create (Task 15) | two engines with different options in two contexts |
| `tests/test_engine_context_source_guards.py` | Modify (Task 4) | the import-time scan also reports a module-level read of a module view |
| `tests/benchmarks/test_engine_context_benchmarks.py` | Create (Task 16), extend (Task 17) | per-call and per-read benchmarks for the performance gate |
| the test files each task lists | Modify | the collision tests and the rewritten writer lines |
| the documentation Task 16 lists | Modify (Task 16) | the views documented; per-game reports; audit and status |

---

### Task 0: Pre-flight — check the base against this plan

**Files:** none changed.

- [ ] **Step 1: The branch and its base**

Run:
```bash
git -C /Users/terry/Dropbox/dev.glitchygames/glitchygames-engine-context-2 status --short
git -C /Users/terry/Dropbox/dev.glitchygames/glitchygames-engine-context-2 log --oneline -1
gh pr view 111 --json state,headRefName,mergedAt
```
Expected: a clean tree on `feature/engine-context-2-engine-state`; this plan was verified at
b5f16688 and rechecked on `main` at 3f916b97 (2026-10-29: PR #111 merged, the branch rebased;
`.superpowers/sdd/2026-10-27-engine-context-2-engine-state/task-0-rerun-report.md`). `<base>` is
the plan-corrections commit, the last commit before Task 1's code (the plan cannot hold its own
hash: the ledger, `progress.md`, records it): Task 17 diffs against it.

- [ ] **Step 2: Every citation in "Where each row is now" still holds**

Run:
```bash
cd /Users/terry/Dropbox/dev.glitchygames/glitchygames-engine-context-2
grep -n 'OPTIONS: ClassVar' src/glitchygames/scenes/scene.py src/glitchygames/engine/game_engine.py src/glitchygames/fonts/font_manager.py
grep -n 'EVENT_HANDLERS: ClassVar\|MISSING_EVENTS: ClassVar\|^    game: Any = None' src/glitchygames/engine/game_engine.py
grep -n '__instances__: ClassVar\|^_unhandled_event_types' src/glitchygames/events/base.py
grep -n '_instance = None\|^performance_manager' src/glitchygames/performance/adaptive_clamping.py
grep -n '__instance__: ClassVar' src/glitchygames/sprites/bitmappy_sprite.py
grep -n 'SPRITE_BREAKPOINTS: ClassVar\|SPRITE_COUNTERS: ClassVar\|SPRITE_COUNT = 0' src/glitchygames/sprites/sprite.py
grep -n '^_INTERNAL_POSTS' src/glitchygames/recording.py
grep -c '_INTERNAL_POSTS' tests/test_recording.py
grep -rn '_unhandled_event_types' tests | wc -l
```
Expected: the lines in the table (231; 702; 137; 718, 705, 693; 365, 221; 79, 926; 1019, 1053,
1101; 45, 46, 49; 414), `15` and `4`. Where a line moved, correct the citations in this plan
before Task 2 (the controller reviews the change); where a row's state is gone or renamed, stop
and report.

- [ ] **Step 3: The suite is green before anything changes**

Run: `uv run pytest --dummy-only`
Expected: every test passes, coverage 100%. A failure here is not this plan's: report it.


- [ ] **Step 4: Each class's metaclass, so the views metaclasses fit (review I-1)**

Run:
```bash
uv run python -c "
import pygame.sprite
from glitchygames.engine import GameEngine
from glitchygames.fonts.font_manager import FontManager
from glitchygames.scenes import SceneManager
from glitchygames.sprites import Sprite
for cls in (GameEngine, SceneManager, FontManager, Sprite):
    print(cls.__name__, type(cls).__name__, sorted({type(base).__name__ for base in cls.__mro__}))
"
```
Expected: `GameEngine type`, `SceneManager type`, `FontManager type` (each base `type`), and
`Sprite ABCMeta ['ABCMeta', 'type']` (`EventInterface(abc.ABC)`, `events/base.py:1415`). So
`GameEngine`, `SceneManager` and `FontManager` take `ReadOnlyViews(type)` and `Sprite` takes
`ReadOnlyViewsABC(ReadOnlyViews, abc.ABCMeta)`: each views metaclass subclasses the class's current
metaclass. Any other metaclass (a `Protocol`'s `_ProtocolMeta`, a pydantic one) means a conflict:
stop and report.

- [ ] **Step 5: Record the base for the performance gate**

Task 17 measures the base and the branch interleaved on the same day (review I-9), from a scratch
worktree of `<base>`; nothing is measured now. Record `<base>` and the machine (`uv run
glitchygames measure --help` runs nothing; the machine is what `LedgerRow.run` names) in the
task's notes.

---

### Task 1: Read-only views, the write-refusing metaclasses and `current_engine()` (answer 2, 2026-10-28)

The mechanism every later view uses, the context's current engine, and the guard that engine code
never reads a view. No view exists yet at the end of this task: each row's task adds its own.

**The design (review I-4, prototyped 2026-10-28).** One descriptor in the class body per view,
with an overloaded `__get__`: read on the class, it answers the current context's value (`T |
None` where there may be no game); read on an instance, it answers that object's own state. A
metaclass refuses writes through `__setattr__`/`__delattr__` for names whose entry along the MRO
is a view. The first plan (a class-level view on a per-class metaclass beside an instance view in the
class body) does not type-check: basedpyright resolves instance access to the metaclass
descriptor ("Cannot access attribute OPTIONS for class Engine") and class access to `dict |
None` everywhere. The prototype of the design below
(`read_only_views.py`, an engine-like class and a reader module, run with this repository's
`pyrightconfig.json` settings under basedpyright strict) gave **0 errors, 0 warnings** for: an
instance read (`engine.OPTIONS['input_mode']`, typed `dict[str, Any]`), a class read narrowed
from `dict[str, Any] | None`, a never-`None` class view (`Sprite.SPRITE_COUNTERS['x']`), a
class-level read of `game` and an instance write `engine.game = ...`. It gave the expected
`reportOptionalSubscript`/`reportOperatorIssue` errors for an unnarrowed class-level subscript or
`in` on a view that may be `None`: those test readers are rewritten (Tasks 2, 5, 7 list them). At
run time, `Engine.OPTIONS = {}`, `engine.OPTIONS = {}`, `Engine.game = 1`, `del Engine.OPTIONS`
and `Sprite.SPRITE_COUNTERS = {}` (an `ABCMeta` class) each raised with the view's message;
`engine.game = 'h'` stored on the instance.

**Files:**
- Create: `src/glitchygames/read_only_views.py`
- Modify: `src/glitchygames/engine/game_engine.py` (the slot, `current_engine`,
  `NoRunningEngineError`; `class GameEngine(events.EventManager, metaclass=ReadOnlyViews)`;
  `__init__` registers the engine; `_shutdown` clears it), `src/glitchygames/engine/__init__.py`
  (re-exports), `src/glitchygames/scenes/scene.py` and `src/glitchygames/fonts/font_manager.py`
  (`metaclass=ReadOnlyViews`), `src/glitchygames/sprites/sprite.py` (`metaclass=ReadOnlyViewsABC`:
  `Sprite`'s metaclass is `ABCMeta`, review I-1)
- Modify: `tests/harness.py` (`_reset_all_singleton_instances` resets `CURRENT_ENGINE_SLOT`)
- Create: `tests/test_read_only_views.py`
- Test: `tests/engine/test_game_engine.py`, `tests/test_engine_context.py`

**Interfaces:**
- Produces, in `src/glitchygames/read_only_views.py` (standard library and `abc` only):
  ```python
  class ReadOnlyViewError(AttributeError): ...      # a view was written or deleted
  class ViewReadError(RuntimeError): ...            # a view's read raised AttributeError (review M-9)
  class ViewBase:                                   # name, write_instead, refusal(*, owner: type) -> str
      ...
  class ReadOnlyView[ClassReadT, InstanceReadT](ViewBase):   # data descriptor
      def __init__(self, *, read_current: Callable[[type], ClassReadT],
                   read_own: Callable[[Any], InstanceReadT], write_instead: str) -> None: ...
      @overload
      def __get__(self, instance: None, owner: type) -> ClassReadT: ...
      @overload
      def __get__(self, instance: object, owner: type | None = None) -> InstanceReadT: ...
      def __set__(self, instance: object, value: object) -> Never: ...   # ReadOnlyViewError
      def __delete__(self, instance: object) -> Never: ...               # ReadOnlyViewError
  class ClassOnlyView[ClassReadT](ViewBase):       # non-data: for a name each instance keeps
      def __init__(self, *, read_current: Callable[[type], ClassReadT], write_instead: str) -> None: ...
      def __get__(self, instance: object | None, owner: type) -> ClassReadT: ...
  class ReadOnlyViews(type): ...                    # __setattr__/__delattr__ refuse a view's name
  class ReadOnlyViewsABC(ReadOnlyViews, abc.ABCMeta): ...
  ```
  `refusal` reads, exactly: `f'{owner.__name__}.{name} is a read-only view of the current game;
  write {write_instead}'`. `read_current` takes the class read through (so a subclass, such as
  `GoldenTraceSceneManager`, answers its own: review M-2). A view stores nothing: `read_current` /
  `read_own` run on every access, and an `AttributeError` they raise is re-raised as
  `ViewReadError` (chained), so `GameEngine.__getattr__` or `ResourceManager.__getattr__` never
  swallows it. `ClassOnlyView` read through an instance that has no attribute of its own answers
  `None`, as the class default it replaces did. Why one shared pair of metaclasses rather than one
  per class (answer 2 said "a small metaclass per class"): with the views in the class bodies the
  metaclass only refuses writes, which is the same for every class; `ReadOnlyViewsABC` exists
  because `Sprite`'s metaclass is `ABCMeta`. My call; the owner's per-class metaclass existed to
  hold the views, which now live in the class bodies.
- Produces, the module-view mark (the controller's ruling, 2026-10-29): a module view is a name
  listed in that module's module-level `READ_ONLY_MODULE_VIEWS: frozenset[str] =
  frozenset({...})` (string literals only), answered by the module's module-level
  `def __getattr__(name)`. A module `__getattr__` alone is never a view: `glitchygames.audio`'s
  lazy `VoiceAssistant` import (PEP 562, #114) carries no mark and is not one. The check, in
  `declared_views`: the module defines both, and every marked name is a string the
  `__getattr__` compares `name` against (a marked name it never compares is reported as a scan
  error). Task 4 declares the first mark (`glitchygames.performance`), and its write-refusing
  module class refuses exactly the marked names.
- Produces, in `game_engine.py`:
  ```python
  class NoRunningEngineError(RuntimeError): ...   # "No game engine is running in the engine context '<name>'"
  CURRENT_ENGINE_SLOT: ContextSlot[_CurrentEngine]  # name 'glitchygames.engine.game_engine.current_engine'
  def current_engine() -> GameEngine: ...
  ```
  `_CurrentEngine` is a dataclass with `engine: GameEngine | None = None`. `GameEngine.__init__`
  sets the current context's `engine` to itself immediately after `options =
  self.initialize_arguments(game=game)` (`:1173`). Tasks 2, 5 and 7 put every piece of the
  engine's own state above that line (`self.game` included, which moves from `:1331` to the top),
  so no view finds a half-made engine. The first statement of `_shutdown` (`:2877`, before its
  `try`, so before `_shut_down_the_run`'s early return on a replay restart at `:2922-2927`) sets
  it back to `None` when it holds this engine: every teardown path clears it, so after a game ends
  its views read `None` and the finished engine is not kept alive (review M-1, re-check m-6).
- Produces, in `tests/test_read_only_views.py`: `VIEW_CHECKS: dict[str, Callable[..., None]]`
  (view name, as `'GameEngine.OPTIONS'` or `'glitchygames.performance.performance_manager'`, to
  its check; empty here), `declared_views(*, source_paths: Sequence[Path]) -> dict[str,
  frozenset[str]]` (owner class name, or module name for a marked module `__getattr__`, to its view
  names), `engine_view_reads(*, source_path: Path, views: Mapping[str, frozenset[str]]) ->
  list[str]`, and `make_stand_in_engine(*, mocker: MockerFixture, target_fps: int) -> GameEngine`
  (a `GoldenTraceEngine` of a stand-in scene, `sys.argv` patched as
  `tests/events/test_events_integration.py:110-128` does). A check's signature is
  `(*, first: EngineContext, second: EngineContext, mocker: MockerFixture) -> None`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_read_only_views.py`:

```python
# What the stand-in class-level view reads (a box, so the test can change it between reads)
SHOWN_BOX: list[int] = [0]


def _current_shown(owner: type) -> int | None:
    return SHOWN_BOX[0] if owner is StandInOwner else None


class StandInOwner(metaclass=ReadOnlyViews):
    """A stand-in owner whose instances keep their own state under lowercase names."""

    SHOWN = ReadOnlyView[int | None, int](
        read_current=_current_shown,
        read_own=lambda owner: owner.shown,
        write_instead='owner.shown',
    )
    kept = ClassOnlyView[int | None](read_current=_current_shown, write_instead='owner.kept')
    plain = 0

    def __init__(self, *, shown: int) -> None:
        self.shown = shown


def test_a_class_read_answers_the_current_value_on_every_access():
    SHOWN_BOX[0] = 1
    first_read = StandInOwner.SHOWN
    SHOWN_BOX[0] = 2

    assert (first_read, StandInOwner.SHOWN, StandInOwner.kept) == (1, 2, 2)


def test_an_instance_read_answers_the_instances_own_state():
    owner = StandInOwner(shown=7)
    no_own_kept = owner.kept
    owner.kept = 5

    assert (owner.SHOWN, no_own_kept, owner.kept) == (7, None, 5)


def test_writing_a_view_raises_and_names_where_to_write(mocker):
    owner = StandInOwner(shown=7)
    message = 'StandInOwner.SHOWN is a read-only view of the current game; write owner.shown'
    for write in (
        lambda: setattr(StandInOwner, 'SHOWN', 3),
        lambda: setattr(owner, 'SHOWN', 3),
        lambda: delattr(StandInOwner, 'SHOWN'),
        lambda: delattr(owner, 'SHOWN'),
        lambda: mocker.patch.object(StandInOwner, 'SHOWN', 3),
    ):
        with pytest.raises(ReadOnlyViewError, match=re.escape(message)):
            write()
    with pytest.raises(ReadOnlyViewError, match=re.escape('write owner.kept')):
        StandInOwner.kept = 3


def test_the_metaclass_lets_every_other_class_attribute_be_written():
    StandInOwner.plain = 1
    del StandInOwner.plain

    assert not hasattr(StandInOwner, 'plain')


def test_a_read_that_fails_is_never_mistaken_for_a_missing_attribute():
    class Broken(metaclass=ReadOnlyViews):
        SHOWN = ReadOnlyView[int, int](
            read_current=lambda _owner: {}['missing'],
            read_own=lambda broken: broken.never_set,
            write_instead='nowhere',
        )

    with pytest.raises(ViewReadError):
        Broken().SHOWN
    with pytest.raises(KeyError):
        Broken.SHOWN


def test_an_abc_class_takes_the_abc_views_metaclass():
    class AbstractOwner(abc.ABC, metaclass=ReadOnlyViewsABC):
        SHOWN = ReadOnlyView[int | None, int](
            read_current=_current_shown, read_own=lambda _owner: 0, write_instead='nowhere'
        )

    assert AbstractOwner.SHOWN is None
    with pytest.raises(ReadOnlyViewError):
        AbstractOwner.SHOWN = 1


def test_every_view_has_a_check():
    """A view added without a check here fails (each view answers per context)."""
    found = {
        f'{owner}.{name}'
        for owner, names in declared_views(source_paths=engine_source_files()).items()
        for name in names
    }

    assert found == set(VIEW_CHECKS)


def test_the_engine_never_reads_a_view():
    """Engine code reads its own state (self.options, slots), never a view (the hot paths)."""
    views = declared_views(source_paths=engine_source_files())
    reads = {
        str(path): found
        for path in engine_source_files()
        if (found := engine_view_reads(source_path=path, views=views))
    }

    assert reads == {}
```

(`test_each_view_answers_per_context`, parametrized over `VIEW_CHECKS`, comes with Task 2's first
entry: an empty parameter set would only be a skipped test.) A planted-source test,
`test_the_view_read_scan_finds_class_instance_and_module_reads`, declares an owner class
(`metaclass=ReadOnlyViews`) with an `OPTIONS` `ReadOnlyView` and a `game` `ClassOnlyView`, a
module `__getattr__` answering `'manager'`, and a second class `Other` with no views, then reads
`Owner.OPTIONS`, `owner.OPTIONS`, `self.game.OPTIONS`, `Owner.game` and `from planted import
manager`: the scan reports those five reads (by line) and not the views' own definitions, nor
`owner.game` (an instance's own attribute), nor `Other.OPTIONS` (a class that owns no such
view). The planted module marks its view (`READ_ONLY_MODULE_VIEWS = frozenset({'manager'})`); a second
planted module, `lazy.py`, has a module `__getattr__` answering `'Helper'` (a lazy import, as
`glitchygames.audio`'s) and no mark, and `from lazy import Helper` is not reported: `declared_views`
returns no entry for `lazy`. `engine_source_files()` is every `*.py` under `tests.engine_source.ENGINE_DIRECTORY`.

**The scan's rules** (`declared_views`, `engine_view_reads`): a view is a class-body assignment
`NAME = ReadOnlyView[...](...)` or `NAME = ClassOnlyView[...](...)` (subscripted or not), owned by
that class and its subclasses (resolved by name within the engine), or a name the module marks in
its `READ_ONLY_MODULE_VIEWS` and its module-level `def __getattr__(name)` answers (owner: the
module's dotted name; the mark above: a `__getattr__` without it is never a view). A read is:
- an attribute load `<Name>.<view>` where `<Name>` is an owner class or a subclass of one;
- an attribute load `.<view>` of a `ReadOnlyView` name on any other receiver (`self`,
  `manager`, `self.game`, ...), except a bare capitalized name of a class that owns no view of
  that name (`FontManager.OPTIONS` before Task 9 makes it one; review I-3, M-11);
- an import or attribute load of a module view.
The view definitions themselves (`read_only_views.py`, the class-body assignments, the lambdas and
helpers passed to them, the marked module `__getattr__` and its mark) are allowed. Documented false positive: an
unrelated engine attribute that happens to be called like a view (`OPTIONS`) is reported; rename
it.

In `tests/engine/test_game_engine.py`:

```python
def test_current_engine_answers_with_each_contexts_own_engine(mocker):
    """current_engine() is the engine made last in the current context (answer 2)."""
    first_context = EngineContext(name='first')
    second_context = EngineContext(name='second')
    with first_context.active():
        first_engine = _make_engine(mocker, '--target-fps', '30')
    with second_context.active():
        second_engine = _make_engine(mocker, '--target-fps', '50')
    with first_context.active():
        first_answer = current_engine()
    with second_context.active():
        second_answer = current_engine()
    for context in (first_context, second_context):
        with context.active():
            reset_sources()

    assert first_answer is first_engine
    assert second_answer is second_engine


def test_current_engine_refuses_when_no_engine_runs_in_the_context():
    with (
        EngineContext(name='idle').active(),
        pytest.raises(
            NoRunningEngineError,
            match=re.escape("No game engine is running in the engine context 'idle'"),
        ),
    ):
        current_engine()


def test_an_engine_that_shut_down_is_no_longer_current(mocker):
    engine = _make_engine(mocker, '--target-fps', '30')
    engine._shutdown()

    with pytest.raises(NoRunningEngineError):
        current_engine()
```

(The last test mocks what `_shutdown` would do to the process, as the existing `_shutdown` tests
in that file do: check them before writing it.) In `tests/test_engine_context.py`,
`check_current_engine` (a stand-in engine object, cast, set on `first`'s slot value through the
context: no observable effect besides `current_engine()`, which it then asserts; `second` raises
`NoRunningEngineError`; the default context's answer is unchanged) and its entry
`'glitchygames.engine.game_engine.current_engine'`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_read_only_views.py tests/engine/test_game_engine.py -k "view or current_engine or shut_down"`
Expected: fails at import (`glitchygames.read_only_views` and `current_engine` do not exist).

- [ ] **Step 3: Implement** the module, the metaclasses on the four classes, the slot,
`current_engine()` (reads the slot; raises when its `engine` is `None`), the registration and the
clearing; `glitchygames.engine` re-exports `current_engine` and `NoRunningEngineError`
(`__all__`). Harness: `_reset_all_singleton_instances` gains
`default_context().reset_value(slot=CURRENT_ENGINE_SLOT)`.

- [ ] **Step 4: Lint** (basedpyright strict on the new module and test file: 0 errors), then
collect the whole suite: `uv run pytest --dummy-only --no-cov -q --co` (collection imports every
engine and member module: a metaclass conflict is a `TypeError` at import; a member class that
mixed a `Sprite` with a `Protocol`, whose metaclass `_ProtocolMeta` does not derive from
`ReadOnlyViewsABC`, would fail here; none does at b5f16688). Expected: collected, no error.

- [ ] **Step 5: Run the tests, then the suite.** Expected: all pass, coverage 100% (the tests
above reach every branch of `read_only_views.py`: class and instance reads of both descriptors,
an instance with and without its own `kept`, the refused set and delete on the class and the
instance, the metaclass passing other names through, a failing read; review I-5).

- [ ] **Step 5b: Measure what a class-level view read costs (review re-check N-3)**

Outside the suite (wall-clock timings never belong in it), a view of exactly the `GameEngine`
views' shape over the slot this task adds, and the slot read it is compared with:
```bash
SETUP='
from types import SimpleNamespace
from glitchygames.engine_context import current_context
from glitchygames.engine.game_engine import CURRENT_ENGINE_SLOT
from glitchygames.read_only_views import ReadOnlyView, ReadOnlyViews
current_context().value(slot=CURRENT_ENGINE_SLOT).engine = SimpleNamespace(options={})
def read_current(owner):
    engine = current_context().value(slot=CURRENT_ENGINE_SLOT).engine
    return None if engine is None else engine.options
class Owner(metaclass=ReadOnlyViews):
    OPTIONS = ReadOnlyView(read_current=read_current, read_own=lambda owner: owner.options, write_instead="nowhere")
'
uv run python -I -m timeit -s "$SETUP" 'Owner.OPTIONS'
uv run python -I -m timeit -s "$SETUP" 'current_context().value(slot=CURRENT_ENGINE_SLOT)'
```
Expected: the view about 180 ns and the slot read about 75 ns on the owner's machine (the
re-check's emulation). Record both numbers and their ratio in this task's notes; Task 16 quotes
the view's cost, and Task 17's per-read gate is a ratio to the slot read (about twice this one).
A ratio far above 2.4 means the view does more than its shape needs: fix it here.

- [ ] **Step 6: Commit** every touched file by path, message `Engine context: read-only views,
the write-refusing metaclasses and current_engine()` with the trailer.

---

### Task 2: The event handlers belong to their engine (audit C10)

The spike's first collision: the second engine built overwrote the class-wide map with its bound
methods, so PaddleSlap's keys were dispatched to Mr. Muncher's managers (`--unswap C10`: "sprite
VerticalPaddle#0 rect expected [0, 197, 20, 100], got [0, 190, 20, 100]" at frame 2).

**Files:**
- Modify: `src/glitchygames/engine/game_engine.py:711-718` (the declaration), `:1473-1549`,
  `:3620-3621`, `__init__` (the dict, above the engine's registration); add
  `_running_engine_attribute` (moved here from Task 1, which has no caller for it: review I-5)
- Test: `tests/events/test_events_integration.py`, `tests/test_read_only_views.py`
- Rewrite (22 lines): the declaration read with no engine running,
  `tests/engine/test_engine_initialization.py:161`; and the class-level readers that use the
  view as a dict, which basedpyright strict refuses on a `dict | None` (review I-4; each test
  holds its engine, so they read `engine.event_handlers`):
  `tests/events/test_events_integration.py:253-256, 259, 261`,
  `tests/engine/test_game_engine.py:513, 523, 524, 527-529, 1314, 1339, 1359, 1394, 1402, 1422,
  1435, 1447, 1468`. Instance readers (`engine.EVENT_HANDLERS`,
  `tests/engine/test_engine_event_system.py:235-249`) stay.

**Interfaces:**
- Consumes: `ReadOnlyView`, `ReadOnlyViews` (Task 1); `EngineContext`;
  the test module's `start_engine_with_scene(*, scene_class, extra_arguments=())`,
  `ScriptedBatchSources(*, batch)`, `AudioAndControllerRecordingScene`.
- Produces: `engine.event_handlers: dict[int, Callable[..., Any]]`, set at the top of `__init__`;
  module-private `_running_engine_attribute[T](*, read: Callable[[GameEngine], T]) -> T | None`
  (the current context's engine's value, `None` with no engine; the `GameEngine` views share it);
  the view `EVENT_HANDLERS = ReadOnlyView[dict[int, Callable[..., Any]] | None, dict[int,
  Callable[..., Any]]](...)` in the class body: `GameEngine.EVENT_HANDLERS` is the current
  engine's (`None` with none), `engine.EVENT_HANDLERS` that engine's, `write_instead='the
  engine\'s own: engine.event_handlers'`. Mutating the dict an instance read returns mutates that
  engine's own map; only rebinding the name raises.

- [ ] **Step 1: Write the failing tests**

In `tests/events/test_events_integration.py` add `from glitchygames.engine_context import
EngineContext` and `from glitchygames.sources import reset_sources` (beside `install_sources`),
and at the end of the file:

```python
def test_each_engine_dispatches_events_to_its_own_handlers():
    """Two engines in two contexts: one's events never reach the other's scene (audit C10).

    The engine context spike (2026-10-27): the second engine built overwrote the class-wide
    handler map, so the first game's events went to the second game's managers.
    """
    first_context = EngineContext(name='first')
    second_context = EngineContext(name='second')
    with first_context.active():
        first_engine, first_scene = start_engine_with_scene(
            scene_class=AudioAndControllerRecordingScene,
            extra_arguments=['--no-unhandled-events', '--target-fps', '30'],
        )
    with second_context.active():
        _second_engine, second_scene = start_engine_with_scene(
            scene_class=AudioAndControllerRecordingScene,
            extra_arguments=['--no-unhandled-events', '--target-fps', '50'],
        )

    with first_context.active():
        install_sources(
            sources=ScriptedBatchSources(
                batch=[pygame.event.Event(pygame.AUDIODEVICEADDED, which=1, iscapture=0)]
            )
        )
        first_engine.process_events()
    for context in (first_context, second_context):
        with context.active():
            reset_sources()

    assert [event.which for event in first_scene.audio_events_received] == [1]
    assert second_scene.audio_events_received == []
```

In `tests/test_read_only_views.py`, the parametrized test every view's check runs under:

```python
@pytest.mark.parametrize('view_name', sorted(VIEW_CHECKS))
def test_each_view_answers_per_context(view_name, mocker):
    VIEW_CHECKS[view_name](
        first=EngineContext(name='first'), second=EngineContext(name='second'), mocker=mocker
    )
```

and `check_event_handlers_view`: an engine made in each context
(`make_stand_in_engine`, different target FPS); inside each, `GameEngine.EVENT_HANDLERS is
engine.event_handlers` and `engine.EVENT_HANDLERS is engine.event_handlers`; in a fresh context
`GameEngine.EVENT_HANDLERS is None`; `GameEngine.EVENT_HANDLERS = {}` and
`engine.EVENT_HANDLERS = {}` raise `ReadOnlyViewError` naming `engine.event_handlers`. Entry
`'GameEngine.EVENT_HANDLERS'`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/events/test_events_integration.py -k own_handlers`
Expected: `1 failed`: `assert [] == [1]` (the event went to the second engine's scene).
`tests/test_read_only_views.py::test_every_view_has_a_check` fails until the view is declared.

- [ ] **Step 3: Implement**

At the top of `GameEngine.__init__` (above the registration), `self.event_handlers: dict[int,
Callable[..., Any]] = {}`; every `GameEngine.EVENT_HANDLERS` in `initialize_event_handlers`,
`initialize_input_event_handlers` and `process_events` becomes `self.event_handlers`. The class
body's `EVENT_HANDLERS` becomes the `ReadOnlyView` under its existing comment (which gains "one
per engine; a read-only view of `event_handlers`").

Rewrite the 22 lines: `test_engine_initialization.py:161` asserts `GameEngine.EVENT_HANDLERS is
None` (outside a game); each class-level reader becomes its test's `engine.event_handlers`
(`mocker.patch.dict(engine.event_handlers, ...)`, `pygame.KEYDOWN in engine.event_handlers`).
Check: `grep -rn 'EVENT_HANDLERS' src/glitchygames` shows only the two views and comments, and
`test_the_engine_never_reads_a_view` passes.

- [ ] **Step 4: Lint** the touched files (standard commands). Expected: no errors.

- [ ] **Step 5: Run the tests, then the suite**

Run: `uv run pytest --dummy-only --no-cov -q tests/events/test_events_integration.py tests/test_read_only_views.py`
Expected: all pass. Then `uv run pytest --dummy-only`: every test passes, coverage 100%.

- [ ] **Step 6: Commit**

```bash
git add src/glitchygames/engine/game_engine.py tests/events/test_events_integration.py tests/test_read_only_views.py tests/engine/test_engine_initialization.py tests/engine/test_game_engine.py
git commit -m "$(cat <<'EOF'
Engine context: each engine dispatches through its own event handlers (C10)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: the hook measures and stages its rows.

---

### Task 3: The internal-post tracker per context (audit C19)

The spike's second collision: B's pump (`forget_pending_posts()`) forgot A's pending posts, so A's
own posted QUIT was no longer recognized ("event Quit missing internal event" at PaddleSlap's last
frame, `--unswap C19`).

**Files:**
- Modify: `src/glitchygames/recording.py:384-603`
- Modify: `tests/harness.py` (docstring of `reset_engine_sources`, `:376-392`: "per engine
  context"; its calls stay)
- Test: `tests/test_recording.py`, `tests/test_engine_context.py`
- Rewrite: the 15 lines of `tests/test_recording.py` (above)

**Interfaces:**
- Consumes: `ContextSlot`, `current_context`, `default_context`, `EngineContext`.
- Produces: `INTERNAL_POSTS_SLOT: ContextSlot[InternalEventPosts]`, name
  `'glitchygames.recording.internal_posts'`, factory `InternalEventPosts`. Every public function
  (`start_tracking_internal_posts`, `stop_tracking_internal_posts`,
  `reset_internal_post_tracking`, `forget_pending_posts`, `pending_internal_posts`,
  `live_game_code_running`, `set_live_game_code_running`, `live_game_posts`, `is_input_post`,
  `pending_code_post_count`, `is_live_game_post`, `post_event`, `post_input_event`) keeps its
  signature and works on the current context's tracker. `_INTERNAL_POSTS` is removed. Test helper
  in `tests/test_recording.py`: `posts_are_tracked() -> bool`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_recording.py`, import `EngineContext` and `default_context` from
`glitchygames.engine_context`, and add to `TestInternalPostTracking`:

```python
    def test_one_contexts_pump_never_forgets_another_contexts_posts(self, event_queue):
        """A pump in one context forgets only that context's pending posts (audit C19).

        The engine context spike (2026-10-27): the second game's pump forgot the first game's
        posted QUIT, so the first game's replay no longer knew it as its own.
        """
        first = EngineContext(name='first')
        second = EngineContext(name='second')
        with first.active():
            start_tracking_internal_posts()
            post_event(pygame.event.Event(pygame.QUIT))
        with second.active():
            start_tracking_internal_posts()
            forget_pending_posts()
            stop_tracking_internal_posts()
        with first.active():
            first_pending = list(pending_internal_posts())
            stop_tracking_internal_posts()
        pygame.event.clear()

        assert first_pending == [(pygame.QUIT, {})]

    def test_a_new_run_in_one_context_keeps_another_contexts_tracking(self, event_queue):
        """reset_internal_post_tracking (every GameEngine.__init__) resets only its context."""
        first = EngineContext(name='first')
        with first.active():
            start_tracking_internal_posts()
        with EngineContext(name='second').active():
            reset_internal_post_tracking()
        with first.active():
            first_still_tracks = posts_are_tracked()
            stop_tracking_internal_posts()

        assert first_still_tracks is True
```

and, beside `_pump_batch`, the helper:

```python
def posts_are_tracked() -> bool:
    """Whether a code post is tracked now: it waits in pending_internal_posts() (decision 1).

    Posts a USEREVENT probe with post_event, then takes it back out of the tracker's pending list
    and SDL's queue, so the tracker and the queue are as they were.

    Returns:
        True when the probe was tracked.
    """
```

(Body: refuse to probe while `live_game_code_running()` (an `AssertionError` naming why: the
probe would be recorded among the live game's posts too); remember `len(pending_internal_posts())`;
`post_event` an event of the module's own `PROBE_EVENT_TYPE = pygame.event.custom_type()`; compare
lengths; `pop()` the probe from `pending_internal_posts()` when tracked; and
`pygame.event.get(eventtype=PROBE_EVENT_TYPE)`, which drains only the probe, never a test's own
`USEREVENT`s (review M-8).)

In `tests/test_engine_context.py` add `check_internal_post_tracker` and its entry:

```python
def check_internal_post_tracker(*, first: EngineContext, second: EngineContext) -> None:
    """Each context keeps its own internal-post tracker, and the default context its own."""
    default_running = live_game_code_running()
    with first.active():
        start_tracking_internal_posts()
        set_live_game_code_running(running=True)
    with second.active():
        assert live_game_code_running() is False
        reset_internal_post_tracking()
    with first.active():
        assert live_game_code_running() is True
        reset_internal_post_tracking()
    assert live_game_code_running() is default_running
```

`ISOLATION_CHECKS['glitchygames.recording.internal_posts'] = check_internal_post_tracker` (in the
dict literal, sorted with the others), importing the four functions from `glitchygames.recording`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_recording.py -k "another_contexts"`
Expected: `2 failed`: `assert [] == [(256, {})]` and `assert False is True`.
Run: `uv run pytest --dummy-only --no-cov -q tests/test_engine_context.py tests/test_engine_context_source_guards.py`
Expected: `test_every_engine_slot_has_an_isolation_check` fails (a check with no slot yet), and
`test_no_slot_value_leaks_between_two_contexts[glitchygames.recording.internal_posts]` fails
(`assert True is False`).

- [ ] **Step 3: Implement**

In `recording.py`, below `InternalEventPosts`: the slot (comment `# Each engine context's
internal-post tracker (glitchygames.engine_context)`) and
`_internal_posts() -> InternalEventPosts` returning `current_context().value(slot=INTERNAL_POSTS_SLOT)`;
every `_INTERNAL_POSTS` becomes `_internal_posts()`, read once per function into a local where a
function reads it more than once. The `InternalEventPosts` docstring says "one per engine
context; where its posts go (SDL's one queue) is sub-plan 6's".

Rewrite the 15 lines (decision 1):
- `:144` (`no_tracked_posts`): reset the default context's slot before and after the test
  (`default_context().reset_value(slot=recording.INTERNAL_POSTS_SLOT)`, then `yield`, then again):
  a reset with no behaviour of its own, as `fresh_random_streams` does.
- `:525`: `list(pending_internal_posts())`.
- `:591`: keep the post (`input_post = pending_internal_posts()[0]` before forgetting) and assert
  `is_input_post(post=input_post) is False`.
- `:597, 604`: `pending_internal_posts() == []`; `:598`: as `:591`, with the post kept before the
  call.
- `:623, 873, 877, 933, 937, 945, 954, 956, 964` (`is_tracking`): `posts_are_tracked()`, each test
  requesting `event_queue`; at `:873` and `:933` the reading is taken where the old one was.
Check: `grep -rn '_INTERNAL_POSTS' src tests` prints nothing.

- [ ] **Step 4: Lint** the touched files. Expected: no errors.

- [ ] **Step 5: Run the tests, then the suite**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_recording.py tests/test_engine_context.py tests/test_engine_context_source_guards.py`
Expected: all pass. Then `uv run pytest --dummy-only`: every test passes, coverage 100%.

- [ ] **Step 6: Commit** `src/glitchygames/recording.py tests/test_recording.py
tests/test_engine_context.py tests/harness.py`, message `Engine context: the internal-post
tracker belongs to the context (C19)` with the trailer.

---

### Task 4: The performance manager per context, and the outer game's aggregate (audit C14)

The spike's third finding: every game's frames were counted under whichever scene was set last (in
700 window ticks, `Paddle Slap` 257 + `Mr. Muncher` 975 + `PauseScene` 167 samples for 1399
frames); the statistics and the shutdown report were wrong.

**Requirement (the owner, 2026-10-28):**
- Each context has its own performance manager, so each game gets its own report.
- The Arcade's wrapper is itself a game in its own context, and its frame contains every inner
  game's ticks, so its report is the whole system's aggregate: a wrapper frame's time is the sum
  of the inner games' work plus its own. Nothing is merged by hand: it follows from each frame
  being timed in its own context.

**Files:**
- Modify: `src/glitchygames/performance/adaptive_clamping.py:73-87, 925-926`,
  `src/glitchygames/performance/__init__.py`, `src/glitchygames/performance/example_usage.py:5,
  22, 35`, `src/glitchygames/scenes/scene.py:389-392, 1491-1494, 1650-1670`,
  `src/glitchygames/engine/game_engine.py:2931-2941, 2987-2997`
- Modify: `tests/harness.py` (`_reset_all_singleton_instances`, `:265-290`)
- Test: `tests/performance/test_adaptive_clamping.py`, `tests/world/test_finish_frame.py`,
  `tests/test_engine_context.py`, `tests/test_read_only_views.py`
- Modify: `tests/test_engine_context_source_guards.py` (the module view in the import-time scan)
- Rewrite (writers only, 38 lines): the 18 `AdaptiveClamping._instance = None` resets in
  `tests/performance/test_adaptive_clamping.py`, its `:33`
  (`assert AdaptiveClamping._instance is instance1`); `tests/test_hypothesis_properties.py:452, 456,
  516, 520, 554, 558`; the module patches, which now raise: `tests/scenes/test_scene.py:1852-1853,
  1985-1988`, `tests/world/test_finish_frame.py:263-265`, `tests/engine/test_game_engine.py:2681,
  2986, 3046`, `tests/performance/test_adaptive_clamping.py:837`. Readers stay: `from glitchygames.performance import performance_manager` in
  `test_game_engine.py:1144, 1171, 3008` and the `mocker.patch.object(performance_manager, ...)`
  calls on the manager's own attributes.

**Interfaces:**
- Consumes: `ContextSlot`, `current_context`, `default_context`, `EngineContext`;
  `ReadOnlyViewError` (Task 1); `FakeClock` and `FPS_LOG_INTERVAL_MS`
  (`tests/world/test_finish_frame.py:42-82`).
- Produces: `PERFORMANCE_MANAGERS_SLOT: ContextSlot[dict[type[AdaptiveClamping],
  AdaptiveClamping]]`, name `'glitchygames.performance.adaptive_clamping.managers'`, factory
  `dict`. `AdaptiveClamping()` returns the current context's manager of that class, made on first
  use (the `SceneManager.__new__` pattern, `scene.py:235-241`); `AdaptiveClamping._instance` and
  the module-level instance at `adaptive_clamping.py:926` are removed (a module-level instance
  would be the default context's for every context: rule 2).
  `glitchygames.performance.performance_manager` becomes a module view: `__getattr__(name)` in
  `performance/__init__.py` answers `AdaptiveClamping()` for `'performance_manager'` (and raises
  `AttributeError` for any other name), the package declares Task 1's mark,
  `READ_ONLY_MODULE_VIEWS = frozenset({'performance_manager'})`, and the package module's class
  becomes a `types.ModuleType` subclass whose `__setattr__`/`__delattr__` raise
  `ReadOnlyViewError` for each name in `READ_ONLY_MODULE_VIEWS` (`write_instead='nothing: AdaptiveClamping() is the current context\'s
  manager; patch its methods'`). `__all__` keeps the name, and a module `__dir__` lists it
  (review M-4). A module-level `from glitchygames.performance import performance_manager` would
  bind the importing module to the default context's manager for good, so the import-time scan
  (`test_no_module_reads_a_context_as_it_is_imported`,
  `tests/test_engine_context_source_guards.py:29`) also reports a module-level import or
  attribute read of a module view, in the engine and every member, with a planted case
  (`example_usage.py:5` does it today; this task fixes it). A module view is a marked name only
  (Task 1's rule, `declared_views`): Brave Adventurer's module-level `from glitchygames.audio
  import VoiceAssistant` (`src/games/brave-adventurer/src/brave_adventurer/game.py:15`) reads a
  lazy import, not a view, and is not reported; the planted case includes such an import.
  Test helper in `tests/world/test_finish_frame.py`: `StandInFrameStepper` (a small class) with `__init__(self, *, mocker, clock: FakeClock, context:
  EngineContext, scene_name: str, work_seconds: float = 0.0, frame_body: Callable[[], None] | None
  = None)`, `step(self) -> None` and the attribute `performance_manager: AdaptiveClamping` (the
  context's).

- [ ] **Step 1: Write the failing tests**

In `tests/performance/test_adaptive_clamping.py` (import `EngineContext`):

```python
def test_each_context_counts_only_its_own_frames():
    """Two games' frames never merge into one manager's scenes (audit C14).

    The engine context spike (2026-10-27): both games' FPS samples were counted under whichever
    scene was set last.
    """
    first = EngineContext(name='first')
    second = EngineContext(name='second')
    with first.active():
        AdaptiveClamping().set_current_scene('First Scene')
        AdaptiveClamping().track_fps_from_event(60.0, 0.010)
    with second.active():
        AdaptiveClamping().set_current_scene('Second Scene')
        AdaptiveClamping().track_fps_from_event(30.0, 0.020)
    with first.active():
        AdaptiveClamping().track_fps_from_event(60.0, 0.010)
        first_scenes = set(AdaptiveClamping().get_per_scene_shutdown_stats())
    with second.active():
        second_scenes = set(AdaptiveClamping().get_per_scene_shutdown_stats())

    assert first_scenes == {'First Scene'}
    assert second_scenes == {'Second Scene'}
```

In `tests/world/test_finish_frame.py`, the owner's requirement, on real frame steps
(`SceneManager.begin_frames`/`run_frame_step(paced=False)`, the outer driver's path) and a fake
clock:

```python
# Fake work per frame: the two inner games' and the outer game's own
INNER_WORK_SECONDS = (1 / 256, 1 / 128)
OUTER_WORK_SECONDS = 1 / 1024
AGGREGATE_FRAME_COUNT = 4


def test_an_outer_games_report_covers_the_inner_games_it_steps(mocker):
    """Each game's report holds its own frames; the outer game's covers the whole tick (C14).

    The owner, 2026-10-28: the Arcade's wrapper is a game in its own context whose frame
    contains every inner game's ticks, so its report is the whole system's aggregate.
    """
    clock = FakeClock()
    # The one clock (glitchygames.clock): patched on the module, as FrameDriver does
    mocker.patch('glitchygames.clock.raw_counter_seconds', new=clock.perf_counter)
    mocker.patch('glitchygames.scenes.scene.post_event')
    recorded = mocker.spy(AdaptiveClamping, 'track_fps_from_event')
    inner_steppers = [
        StandInFrameStepper(
            mocker=mocker,
            clock=clock,
            context=EngineContext(name=f'inner {index}'),
            scene_name=f'Inner {index}',
            work_seconds=work_seconds,
        )
        for index, work_seconds in enumerate(INNER_WORK_SECONDS)
    ]

    def outer_frame() -> None:
        for stepper in inner_steppers:
            stepper.step()
        clock.advance(seconds=OUTER_WORK_SECONDS)

    outer_stepper = StandInFrameStepper(
        mocker=mocker,
        clock=clock,
        context=default_context(),
        scene_name='Outer',
        frame_body=outer_frame,
    )
    for _frame_index in range(AGGREGATE_FRAME_COUNT):
        outer_stepper.step()

    processing_by_manager: dict[int, list[float]] = {}
    for call in recorded.call_args_list:
        processing_by_manager.setdefault(id(call.args[0]), []).append(call.args[2])
    inner_samples = [
        processing_by_manager[id(stepper.performance_manager)] for stepper in inner_steppers
    ]
    outer_samples = processing_by_manager[id(outer_stepper.performance_manager)]
    for stepper in [*inner_steppers, outer_stepper]:
        assert set(stepper.performance_manager.get_per_scene_shutdown_stats()) == {
            stepper.scene_name
        }
    assert len(outer_samples) == AGGREGATE_FRAME_COUNT
    for frame_index in range(AGGREGATE_FRAME_COUNT):
        inner_total = sum(samples[frame_index] for samples in inner_samples)
        assert outer_samples[frame_index] >= inner_total + OUTER_WORK_SECONDS
        for samples, work_seconds in zip(inner_samples, INNER_WORK_SECONDS, strict=True):
            assert samples[frame_index] >= work_seconds
```

`StandInFrameStepper.__init__`, inside its context: `SceneManager()` (the context's; the harness
resets the default context's per test), an active `Scene(options={})`, the manager's options set
to `{'fps_log_interval_ms': FPS_LOG_INTERVAL_MS, 'log_timer_jitter': False}` (through
`manager.OPTIONS = ...` until Task 5, which rewrites that one line to `manager.engine_options`),
the manager's `_run_scene_frame` patched (`mocker.patch.object(manager, '_run_scene_frame',
side_effect=...)`, as `FrameDriver.run` does at `:299-316`) to advance the clock by
`work_seconds` and call `frame_body`, `AdaptiveClamping().set_current_scene(scene_name)`,
`self.performance_manager = AdaptiveClamping()`, and `begin_frames()`; `step()` runs
`run_frame_step(frame_start_seconds=..., paced=False)` inside its context and keeps the returned
reading for the next step.

In `tests/test_engine_context.py`, `check_performance_managers` (as planned: each context's
`AdaptiveClamping()` is its own; `_target_fps` read through the manager, no public reader and no
observable effect: decision 1), entry `'glitchygames.performance.adaptive_clamping.managers'`.
In `tests/test_read_only_views.py`, `check_performance_manager_view`: inside each context
`performance_manager` (imported from `glitchygames.performance` inside the check) is that
context's `AdaptiveClamping()`; a fresh context's is a new one; assigning
`glitchygames.performance.performance_manager` and `mocker.patch('glitchygames.performance.
performance_manager', ...)` raise `ReadOnlyViewError`. Entry
`'glitchygames.performance.performance_manager'`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/performance/test_adaptive_clamping.py tests/world/test_finish_frame.py -k "own_frames or covers_the_inner"`
Expected: `2 failed`: `assert {'First Scene', 'Second Scene'} == {'First Scene'}` and
`assert {'Inner 0', 'Inner 1', 'Outer'} == {'Inner 0'}` (one process-wide manager).

- [ ] **Step 3: Implement**

`AdaptiveClamping.__new__` looks up `cls` in the current context's slot value and makes and stores
one when absent; it returns `cast('Self', instance)`. `_initialized = False` stays (an immutable
class default; each instance sets its own). Engine code never reads the view: every
`from glitchygames.performance import performance_manager` in `scene.py` and `game_engine.py`
becomes `from glitchygames.performance import AdaptiveClamping` and `AdaptiveClamping()` (one call
per method, into a local), kept function-local where it is today; `example_usage.py` does the same
in each function. The class docstring says: one manager per engine context, so each game has its
own report, and an outer game's frames, which contain the inner games' steps, make its report
the aggregate. In `tests/harness.py`, `_reset_all_singleton_instances` gains
`default_context().reset_value(slot=PERFORMANCE_MANAGERS_SLOT)`.

Rewrite the 38 lines (decision 1): a reset of `_instance` becomes
`default_context().reset_value(slot=PERFORMANCE_MANAGERS_SLOT)` (the paired
`AdaptiveClamping._initialized = False` lines stay: an immutable class default, harmless); `:33`
is deleted (identity is asserted on the line before it); a
`mocker.patch('glitchygames.performance.performance_manager', ...)` becomes
`mocker.patch.object(AdaptiveClamping, '<method>', autospec=True)` for **every** method the test
asserts on or whose real effect the old whole-manager mock suppressed (`test_game_engine.py:2986,
3046` watch the trim percent and histogram mode and the reports: each of those methods is patched;
review M-7), and the test asserts on those mocks' calls (with `autospec` the manager is
`call.args[0]`).
Check: `grep -rn 'AdaptiveClamping._instance\|performance_manager' src/glitchygames` shows only
the module view and its docstring; `test_the_engine_never_reads_a_view` passes.

- [ ] **Step 4: Lint** the touched files. Expected: no errors.

- [ ] **Step 5: Run the tests, then the suite**

Run: `uv run pytest --dummy-only --no-cov -q tests/performance tests/world/test_finish_frame.py tests/test_engine_context.py tests/test_engine_context_source_guards.py tests/test_read_only_views.py`
Expected: all pass. Then `uv run pytest --dummy-only`: every test passes, coverage 100%.

- [ ] **Step 6: Commit** every touched file by path, message `Engine context: each context has
its own performance manager; the outer game's report is the aggregate (C14)` with the trailer.

---

### Task 5: The options belong to their engine and its scene manager (audit C8, C7)

The spike saw no divergence for C7, C8 (or C13), and said why: "both goldens record the same
engine options (800x480, 60.01 FPS, update, the same seed), so a mix-up cannot show. Games with
different options would diverge." These tests start their engines with different options.

**Files:**
- Modify: `src/glitchygames/engine/game_engine.py:702, 1065-1131, 1173` and every
  `GameEngine.OPTIONS` in it (`_log_the_startup_options`'s `{**GameEngine.OPTIONS, ...}`, `:3145`,
  new since b5f16688, included); `:3319-3322`; `src/glitchygames/scenes/scene.py:231, 243-259,
  377` and every `self.OPTIONS` in it (`:378-383, 1635, 2143, 2613`);
  `src/glitchygames/fonts/font_manager.py:187-195` (`FontManager.__init__` reads its game's
  options: the scene manager's `engine_options` now, review I-3);
  `src/glitchygames/replay/tools/golden_traces.py:474-476`; `src/glitchygames/replay/playback.py:1239`;
  the docstrings naming `GameEngine.OPTIONS` (`src/glitchygames/replay/driver.py:3049`,
  `src/glitchygames/replay/tools/registry.py:642, 688, 727`,
  `src/glitchygames/replay/tools/traces.py:379, 446`) and the comments at
  `scripts/cached_fonts.py:71`, `scripts/compound_sprite.py:154`: "the engine's ``options``"
- Modify: `tests/harness.py:337-359` (`restore_game_engine_class_state` drops `'OPTIONS'` from
  its tuple and docstring: it is a view now, and setting a view raises; Task 7 drops `'game'`)
- Test: `tests/engine/test_game_engine.py`, `tests/test_engine_context.py`,
  `tests/test_read_only_views.py`
- Rewrite (writers, stand-ins and readers the type checker refuses, 67 lines):
  - `mocker.patch.object(SceneManager, 'OPTIONS', ...)`: `tests/test_host.py:474`,
    `tests/game_objects/test_game_over_scene.py:149`, `tests/scenes/test_scene_manager.py:25`,
    `tests/scenes/test_scene_events.py:218`, `tests/scenes/test_scene.py:1847-1848, 1931`,
    `tests/scenes/test_scene_timer_pacing.py:20`, `tests/scenes/builtin_scenes/test_pause_screen.py:86`,
    `tests/engine/test_game_engine.py:1180, 1608, 1643, 2116`, `tests/world/test_finish_frame.py:257-261`
    and Task 4's `StandInFrameStepper` line (19 lines);
  - assignments `type(manager).OPTIONS = ...` (`tests/scenes/test_scene.py:1713, 1733, 2195,
    2204, 2312, 2321, 2780`) and `scene_manager.OPTIONS = ...`
    (`tests/scenes/test_scene_manager.py:352`) (8);
  - `mocker.patch.object(GameEngine, 'OPTIONS', ...)`: `tests/engine/test_game_engine.py:2683-2685,
    2988-2990, 3019-3021, 3049-3051`, and `GameEngine.OPTIONS = {` at `:2729` (13);
  - stand-in engines given `.OPTIONS`, which the setter no longer reads (it reads
    `new_engine.options`): `mocker.Mock()` engines at `tests/test_host.py:479`,
    `tests/debug/test_manager_overlay.py:174, 186`, `tests/scenes/test_scene_manager.py:92, 225,
    244, 494, 571`, `tests/scenes/test_scene.py:2775`, `tests/scenes/test_scene_timer_pacing.py:100,
    146, 157, 192, 227`; `mocker.Mock(OPTIONS=...)` at `tests/debug/test_manager_overlay.py:453`;
    `types.SimpleNamespace(OPTIONS=...)` at `tests/game_objects/test_game_over_scene.py:153` and
    `tests/scenes/builtin_scenes/test_pause_screen.py:104`; the `EngineWithoutGameEvents` stand-in's
    `self.OPTIONS` at `tests/scenes/test_scene_events.py:226` (18; review I-2);
  - stand-in games handed to `FontManager`, which now reads `engine_options`:
    `tests/events/test_events_font_events.py:52, 69` (`self.OPTIONS`),
    `tests/fonts/test_font_manager.py:191, 404` (`types.SimpleNamespace(OPTIONS=...)`) (4; review
    I-3);
  - class-level readers that subscript a `dict | None` view (basedpyright strict refuses them;
    each test holds its engine): `tests/engine/test_engine_lifecycle.py:921`,
    `tests/engine/test_game_engine.py:1627, 2122` (3; review I-4);
  - declaration reads with no engine running: `tests/engine/test_engine_initialization.py:156, 255`
    (2).
  Readers that type-check stay (`manager.OPTIONS`, `manager.OPTIONS.update(...)`, `engine.OPTIONS`,
  `test_engine_lifecycle.py:262`'s `SceneManager.OPTIONS is GameEngine.OPTIONS`).

**Interfaces:**
- Consumes: `ReadOnlyView` (Task 1), `_running_engine_attribute` (Task 2), `make_stand_in_engine`
  (Task 1); `_make_engine(mocker, *arguments, game=...)`.
- Produces: `engine.options: dict[str, Any]` and `manager.engine_options: dict[str, Any]`,
  instance attributes. `GameEngine.initialize_arguments(game) -> dict[str, Any]` keeps its
  signature and return and stores nothing on the class; `GameEngine.__init__` sets
  `self.options` from it, just above the engine's registration (Task 1). `SceneManager.__init__`
  sets `self.engine_options = {}`; the `game_engine` setter sets
  `self.engine_options = new_engine.options` (the same dict, as today). `FontManager.__init__`
  reads `self.game.engine_options[...]`. Views (`ReadOnlyView[dict[str, Any] | None, dict[str,
  Any]]` in the class bodies): `GameEngine.OPTIONS` (the current engine's `options`, `None` with
  none) / `engine.OPTIONS` (that engine's), `write_instead='the engine\'s own: engine.options'`;
  `SceneManager.OPTIONS` (the current context's manager of the class read through, looked up
  with `_scene_manager_for_class(scene_manager_class=owner)` so reading it never makes one, and
  `None` when there is none; review M-2) / `manager.OPTIONS` (that manager's),
  `write_instead='the manager\'s own: manager.engine_options (the game_engine setter sets it)'`.

- [ ] **Step 1: Write the failing tests**

In `tests/engine/test_game_engine.py` (import `EngineContext`, and `reset_sources` from
`glitchygames.sources`):

```python
def test_each_engine_keeps_the_options_it_was_started_with(mocker):
    """Two engines started with different options in two contexts keep their own (C8, C7).

    The spike's goldens recorded the same options, so a mix-up could not show there.
    """
    first_context = EngineContext(name='first')
    second_context = EngineContext(name='second')
    with first_context.active():
        first_engine = _make_engine(mocker, '--target-fps', '30')
        first_engine.scene_manager.game_engine = first_engine
    with second_context.active():
        second_engine = _make_engine(mocker, '--target-fps', '50')
        second_engine.scene_manager.game_engine = second_engine
    with first_context.active():
        first_manager_target = SceneManager().OPTIONS['target_fps']
        first_view_target = GameEngine.OPTIONS['target_fps']
    for context in (first_context, second_context):
        with context.active():
            reset_sources()

    assert first_engine.OPTIONS['target_fps'] == 30.0
    assert second_engine.OPTIONS['target_fps'] == 50.0
    assert first_manager_target == 30.0
    assert first_view_target == 30.0
```

(It reads through the views on purpose: a test is a reader, and the views must answer per
context.) In `tests/test_engine_context.py`, `check_scene_managers` (`:832`) gains, after
`second_manager` is made, `assert second_manager.engine_options is not
first_manager.engine_options`, and at its end `assert default_manager.engine_options is not
first_manager.engine_options`. In `tests/test_read_only_views.py`, `check_engine_options_view`
and `check_scene_manager_options_view` (as Task 2's check: each context's view is its own
object's dict, `None` in a fresh context, and assignments and `mocker.patch.object` raise naming
`engine.options` / `manager.engine_options`), entries `'GameEngine.OPTIONS'` and
`'SceneManager.OPTIONS'`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/engine/test_game_engine.py -k started_with`
Expected: `1 failed`: `assert 50.0 == 30.0` (the class-wide options are the second engine's).
Run: `uv run pytest --dummy-only --no-cov -q tests/test_engine_context.py -k scene_managers`
Expected: fails: `SceneManager` has no attribute `engine_options`.

- [ ] **Step 3: Implement**

`initialize_arguments` builds `options = vars(args)`, resolves `options['target_fps']`, sets
`game.options = options` and returns it; `__init__` does `self.options = options` right after
`:1173`, above the registration. Every `GameEngine.OPTIONS` in `game_engine.py` becomes
`self.options` (all are in instance methods, `initialize_arguments` aside; `_log_the_startup_options`'s
at `:3145` too); `:3322`
(`SceneManager.OPTIONS = ...`) is deleted, because the setter on the next line sets it. In
`golden_traces.py` `install_game`, `scene_class(options=self.options)` and its `SceneManager.OPTIONS`
line deleted likewise; `playback.py:1239` reads `manager.engine_options`. In `scene.py`, the setter
writes `self.engine_options` and every `self.OPTIONS` reads `self.engine_options`; `__init__` sets
`self.engine_options: dict[str, Any] = {}` beside `update_type`; the class body's `OPTIONS`
becomes the `ReadOnlyView`; `FontManager.__init__`'s seven reads become
`self.game.engine_options[...]`. Check that the engine's attribute name changes no unhandled-event
behaviour: `grep -n "getattr(game, 'options'" src/glitchygames/events/base.py` is the one reader
(`:249`), and every manager is built with `game=self.scene_manager` (`game_engine.py:1771-1803`).

Rewrite the 67 lines: a `mocker.patch.object(SceneManager | GameEngine, 'OPTIONS', value)` that
only put a class attribute back is deleted (the harness gives every test a fresh scene manager
and no current engine); one that gave a test its options sets them on the object the test uses
(`manager.engine_options = {...}` or `engine.options = {...}`); `type(manager).OPTIONS = ...` and
`scene_manager.OPTIONS = ...` become `manager.engine_options = ...`; a stand-in `Mock` engine's
`.OPTIONS = {...}` (or `OPTIONS=` keyword) becomes `.options = {...}` (`options=`); a stand-in game
for `FontManager` gets `engine_options`; a class-level subscript of `GameEngine.OPTIONS` reads
the test's `engine.options`; `test_engine_initialization.py:156` asserts
`GameEngine.OPTIONS is None` (outside a game) and `test_engine_options_initialization`
(`:251-255`) asserts the same with `hasattr`.
Check: `test_the_engine_never_reads_a_view` passes (its rule leaves `FontManager.OPTIONS`, not a
view until Task 9, alone); `grep -rnE '(GameEngine|SceneManager|type\(manager\)|scene_manager|engine|engine_mock)\.OPTIONS\s*=[^=]' src tests`
prints nothing (Task 9's `FontManager.OPTIONS = ` lines are that task's).

- [ ] **Step 4: Lint** the touched files. Expected: no errors.

- [ ] **Step 5: Run the tests, then the suite**

Run: `uv run pytest --dummy-only --no-cov -q tests/engine tests/scenes tests/world tests/test_engine_context.py tests/test_read_only_views.py`
Expected: all pass. Then `uv run pytest --dummy-only`: every test passes, coverage 100%.

- [ ] **Step 6: Commit** every touched file by path, message `Engine context: each engine and
scene manager keeps its own options (C8, C7)` with the trailer.

---

### Task 6: The game class's options are no longer set on the class (new audit row C20)

Found by the review (I-6), confirmed at b5f16688: `GameEngine.initialize_arguments` ends with
`game.options = options` (`src/glitchygames/engine/game_engine.py:1129`). `game` is the game's
Scene **class** (`GameEngine(game=Game)`; `_build_game` calls it, `:3319`), so this sets a class
attribute every context shares: the Arcade's demo tile and a launched copy of the same game
overwrite each other's. It is latent: each scene instance sets its own `self.options`
(`scenes/scene.py:2924`), and nothing in the engine or the members reads the class-level value
(`grep -rn '\.options\b' src/glitchygames` finds no reader of it). Only two tests do. Neither the
audit nor Task 13's rule 4 saw it (the receiver is a lowercase parameter).

**Files:**
- Modify: `src/glitchygames/engine/game_engine.py:1126-1131` (`initialize_arguments`)
- Test: `tests/engine/test_game_engine.py`
- Rewrite (2 lines): `tests/engine/test_game_engine.py:255` (`assert EngineTestGame.options is
  result`) and `tests/engine/test_engine_properties.py:86` (`assert PropertiesTestGame.options is
  not None`): `:255` is deleted (the lines above it assert the returned options), and `:86`
  asserts `real_engine.options is not None`.

**Interfaces:**
- Produces: `GameEngine.initialize_arguments(game) -> dict[str, Any]`, signature and return
  unchanged; it no longer writes `game.options`. The game's options reach the scene as they do
  today, at construction (`self.game = self.game(options=self.options)`, `_build_game`).

- [ ] **Step 1: Write the failing test**

```python
def test_parsing_the_options_leaves_the_game_class_alone(mocker):
    """Two contexts running one game class never share its options (new audit row C20)."""
    mocker.patch.object(sys, 'argv', ['test_game_engine', *ENGINE_TEST_ARGUMENTS])
    options_before = vars(EngineTestGame).get('options')

    GameEngine.initialize_arguments(EngineTestGame)

    assert vars(EngineTestGame).get('options') is options_before
```

- [ ] **Step 2: Run it.** Expected: `1 failed`: the class now holds the parsed options.
- [ ] **Step 3: Implement.** Delete the `game.options = options` line and its "Back propagate the
  options" comment; the docstring says the options are returned, never stored on the game. Rewrite
  the 2 lines.
- [ ] **Step 4–6:** lint; run the engine tests and the suite (every test passes, coverage 100%);
  commit by path, message `Engine context: parsing the options no longer sets them on the game
  class (C20)` with the trailer.

---

### Task 7: The game and the event bookkeeping belong to their engine (audit C9, C11)

Latent in the spike (no divergence unswapped): its engines each ran `_build_game` before the next
was built. Built first and used after, the class attribute answers with the last engine's game.

**Files:**
- Modify: `src/glitchygames/engine/game_engine.py:693, 704-706, 1331, 4200-4206, 4330-4336, 4366`
- Modify: `tests/harness.py:337-359` (`restore_game_engine_class_state` drops `'game'`: a view now;
  it keeps `'icon'`, `'USE_FASTEVENTS'` and `'PYGAME_FOUND_WITH_SDL_SIGNAL_HANDLERS'`, the last
  process state under S8: the controller's ruling, 2026-10-29)
- Test: `tests/engine/test_game_engine.py`, `tests/engine/test_engine_initialization.py`,
  `tests/test_read_only_views.py`
- Rewrite (writers, declaration reads and readers the type checker refuses, 29 lines):
  `GameEngine.LAST_EVENT_MISS = ...` at
  `tests/engine/test_game_engine.py:1235, 1244`; `mocker.patch.object(GameEngine,
  'LAST_EVENT_MISS' | 'MISSING_EVENTS', ...)` at `:1257, 1258`; `GameEngine.game = ...` at
  `:1659, 2728`; `mocker.patch.object(GameEngine, 'game', ...)` at `:2682, 2987, 3018, 3048`;
  declaration reads with no engine running at `tests/engine/test_engine_initialization.py:157-159,
  273-274`; class-level readers that call or test membership on a `list | None` view (review
  I-4; each test holds its engine): `tests/engine/test_game_engine.py:965, 970, 978, 984, 989, 998,
  1008, 1018, 1234, 1238, 1243, 1248, 1336, 1345`. Readers that type-check stay (the equality
  checks at `:1264-1265`, the `hasattr` lines at `test_engine_initialization.py:268-270`).

**Interfaces:**
- Consumes: `_make_engine`, `EngineTestGame`, `NoIconGame` (`tests/engine/test_game_engine.py:94,
  112`); `ReadOnlyView`, `ClassOnlyView` (Task 1), `_running_engine_attribute` (Task 2).
- Produces: `self.game` set at the top of `__init__`, above the registration (it moves from
  `:1331`, so no view sees the engine before its game: review M-1); `engine.missing_events:
  list[str]`, `engine.unimplemented_events: list[int]` and `engine.last_event_miss: str` set
  there too, declared `self.game: Any = game`. Views in the class body: `game =
  ClassOnlyView[Any](...)` (it replaces the class default `game: Any = None`: `GameEngine.game` is
  the current engine's, `None` with none; an instance's `game` is its own attribute, and an
  instance whose `__init__` never set one reads `None`, as the class default answered). `Any`, not
  `type[Scene] | Scene | None` (review re-check N-1, reversing M-10): the narrower view type makes
  every instance read of `self.game` that union, which basedpyright strict refuses at
  `game_engine.py:3319` (`self.game(options=...)`: "Object of type Scene is not callable", and
  `None` cannot be called), `:1914` (`game: Scene = self.game`) and `:1494`, `scene.py:624`,
  `pause_scene.py:94`. Re-probed (scratchpad, this repository's basedpyright settings):
  `ClassOnlyView[Any]` with the instance attribute declared `self.game: Any` in `__init__` gives 0
  errors for `self.game = self.game(options=self.options)`, `game: Scene = self.game`, a class
  read and an instance write; without the declaration, `self.game` is "partially unknown";
  `MISSING_EVENTS`, `UNIMPLEMENTED_EVENTS`, `LAST_EVENT_MISS` as `ReadOnlyView[list[str] | None,
  list[str]]`, `ReadOnlyView[list[int] | None, list[int]]`, `ReadOnlyView[str | None, str]`;
  `write_instead` naming `engine.game`, `engine.missing_events`, `engine.unimplemented_events`,
  `engine.last_event_miss`.

- [ ] **Step 1: Write the failing tests**

```python
def test_each_engine_keeps_its_own_game(mocker):
    """An engine built before another keeps its own game (audit C9)."""
    first_context = EngineContext(name='first')
    second_context = EngineContext(name='second')
    with first_context.active():
        first_engine = _make_engine(mocker, '--target-fps', '30', game=EngineTestGame)
    with second_context.active():
        _make_engine(mocker, '--target-fps', '50', game=NoIconGame)
    for context in (first_context, second_context):
        with context.active():
            reset_sources()

    assert first_engine.game is EngineTestGame


def test_each_engine_notes_its_own_missing_and_unimplemented_events(mocker, caplog):
    """One engine's missing handlers and unimplemented events are never another's (C11)."""
    first_context = EngineContext(name='first')
    second_context = EngineContext(name='second')
    with first_context.active():
        first_engine = _make_engine(mocker, '--target-fps', '30')
    with second_context.active():
        second_engine = _make_engine(mocker, '--target-fps', '50')
    first_engine.on_never_defined_event(events.HashableEvent(pygame.USEREVENT))
    first_engine.process_unimplemented_event(events.HashableEvent(UNMAPPED_EVENT_TYPE))
    with caplog.at_level(logging.INFO, logger='game.engine'):
        second_engine.on_never_defined_event(events.HashableEvent(pygame.USEREVENT))
    for context in (first_context, second_context):
        with context.active():
            reset_sources()

    assert any(
        record.getMessage().startswith('Unimplemented method called: on_never_defined_event')
        for record in caplog.records
    )
    assert UNMAPPED_EVENT_TYPE not in second_engine.unimplemented_events
```

In `tests/engine/test_engine_initialization.py`,
`test_each_engine_starts_with_its_own_empty_event_bookkeeping`: two engines (`sys.argv` patched as
`_make_engine` does), each with empty `missing_events` and `unimplemented_events`, its own
`event_handlers` and `options` dicts, none the other's. In `tests/test_read_only_views.py`, the
checks for `'GameEngine.game'`, `'GameEngine.MISSING_EVENTS'`, `'GameEngine.UNIMPLEMENTED_EVENTS'`
and `'GameEngine.LAST_EVENT_MISS'` (as Task 2's).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/engine/test_game_engine.py -k "own_game or own_missing"`
Expected: `2 failed`: `assert <class NoIconGame> is <class EngineTestGame>`, and
`AttributeError: ... 'unimplemented_events'` (then, once the attribute exists, the second engine
never logs: the class-wide list already holds the name).

- [ ] **Step 3: Implement**

`GameEngine.game = game` (`:1331`) is deleted and `self.game: Any = game` set at the top of
`__init__` with the three lists and the string; `__getattr__` writes `self.last_event_miss = attr` (setting an instance attribute
never re-enters `__getattr__`); `missing_event` and `process_unimplemented_event` use the instance
names. The class body's four names become the views above.

Rewrite the 29 lines: `GameEngine.LAST_EVENT_MISS = 'x'` becomes the test's
`engine.last_event_miss = 'x'`; the `mocker.patch.object(GameEngine, ...)` lines that only put a
class attribute back are deleted (a fresh engine has its own); `GameEngine.game = X` and
`mocker.patch.object(GameEngine, 'game', X)` set `engine.game = X` on the engine the test uses;
`test_engine_initialization.py:157-159, 273-274` assert each view is `None` outside a game; the
class-level `.clear()`, `in` and `.count()` readers use the test's `engine.unimplemented_events`
/ `engine.missing_events`.
Check: `test_the_engine_never_reads_a_view` passes.

- [ ] **Step 4–6:** lint; run `-k "own_game or own_missing"` (`2 passed`), the views file, the
suite (every test passes, coverage 100%); commit by path, message `Engine context: each engine
keeps its own game and event bookkeeping (C9, C11)` with the trailer.

---

### Task 8: The shared event managers per context (audit C12)

Latent in the spike ("each engine keeps its own managers on its own attributes, so no
divergence"), but "any `SomeManager()` lookup made later (by a scene's proxies, or a font) would
get the other context's", and each engine's build released every context's managers.

**Files:**
- Modify: `src/glitchygames/events/base.py:334-419` (docstring `:346-356`, `__instances__` `:365`,
  `__new__`, `release_shared_instances`)
- Modify: `tests/harness.py:278`
- Test: `tests/events/test_events_core.py` (the class holding
  `test_releasing_the_shared_managers_lets_a_new_run_build_new_ones`, `:1106`),
  `tests/test_engine_context.py`

**Interfaces:**
- Produces: `SHARED_INSTANCES_SLOT: ContextSlot[dict[type, Any]]`, name
  `'glitchygames.events.base.shared_instances'`, factory `dict`. `ResourceManager.__new__` and
  `release_shared_instances()` (signature unchanged) use the current context's dict.
  `ResourceManager.__instances__` is removed.

- [ ] **Step 1: Write the failing tests**

```python
    def test_each_context_has_its_own_shared_managers(self):
        """A shared manager is shared within its context only (audit C12)."""
        first = EngineContext(name='first')
        second = EngineContext(name='second')
        first_game = GameWithOptions(options={})
        second_game = GameWithOptions(options={})
        with first.active():
            first_manager = MouseEventManager(game=first_game)
        with second.active():
            second_manager = MouseEventManager(game=second_game)
            ResourceManager.release_shared_instances()
        with first.active():
            first_again = MouseEventManager()

        assert second_manager is not first_manager
        assert first_again is first_manager
        assert first_again.proxies[0].game is first_game
```

`check_shared_instances` in `tests/test_engine_context.py`: a manager made in `first` is answered
in `first` again, `second` gets its own, `release_shared_instances()` in `second` leaves `first`'s,
the default context's lookup is untouched. Entry `'glitchygames.events.base.shared_instances'`.

- [ ] **Step 2: Run** `-k own_shared_managers`. Expected: `1 failed`: `assert <MouseEventManager>
is not <MouseEventManager>`.

- [ ] **Step 3: Implement.** `__new__` reads `current_context().value(slot=SHARED_INSTANCES_SLOT)`;
`release_shared_instances` clears the current context's dict; the class docstring says "one per
class per engine context" and "releases this context's". `tests/harness.py:278` becomes
`default_context().reset_value(slot=SHARED_INSTANCES_SLOT)`.
Check: `grep -rn '__instances__' src tests` prints nothing.

- [ ] **Step 4–6:** lint; run the test, the two engine-context test files, the suite (every test
passes, coverage 100%); commit by path, message `Engine context: the shared event managers belong
to the context (C12)` with the trailer.

---

### Task 9: The font options per context (audit C13)

Latent in the spike, with the same weak evidence as C7/C8 (both goldens used the same font
options).

**Files:**
- Modify: `src/glitchygames/fonts/font_manager.py:137, 180-199, 300-480`
- Test: `tests/fonts/test_font_manager.py`, `tests/test_engine_context.py`,
  `tests/test_read_only_views.py`
- Rewrite (writers only, 4 lines): `FontManager.OPTIONS = {...}` at
  `tests/events/test_events_font_events.py:439, 462, 474, 487`. Readers stay, including the ones
  that change the dict the view returns in place (`FontManager.OPTIONS.clear()`, item
  assignments, `mocker.patch.dict(FontManager.OPTIONS, ...)` in the engine's and Bitmappy's
  tests, and `tests/harness.py:282`): the dict is the current context's options, as before.

**Interfaces:**
- Produces: `FONT_OPTIONS_SLOT: ContextSlot[dict[str, Any]]`, name
  `'glitchygames.fonts.font_manager.options'`, factory `dict`; module-private
  `_font_options() -> dict[str, Any]`. `FontManager.font`, `pygame_font`, `get_font`,
  `set_font_system`, `get_font_system` and `__init__` keep their signatures and use the current
  context's options through `_font_options()`. View: `OPTIONS = ReadOnlyView[dict[str, Any],
  dict[str, Any]](...)` in the class body (class or instance read: the current context's dict,
  `{}` in a fresh one; never `None`, so `FontManager.OPTIONS[...]` readers type-check),
  `write_instead='the current context\'s font options in place (FontManager.OPTIONS.update(...))
  or FontManager.set_font_system(...)'`. `RENDER_CACHE` and `_font_cache` stay shared (R9,
  decision 2).

- [ ] **Step 1: Write the failing tests**

```python
def test_each_context_has_its_own_font_system():
    """One context's font system never changes another's (audit C13)."""
    first = EngineContext(name='first')
    second = EngineContext(name='second')
    with first.active():
        FontManager.set_font_system(font_system='freetype')
    with second.active():
        second_system = FontManager.get_font_system()
    with first.active():
        first_system = FontManager.get_font_system()

    assert first_system == 'freetype'
    assert second_system == 'pygame'
```

`check_font_options` in `tests/test_engine_context.py`, entry
`'glitchygames.fonts.font_manager.options'`; `check_font_options_view` in
`tests/test_read_only_views.py` (each context's `FontManager.OPTIONS` is its own dict, `{}` in a
fresh context, `FontManager.OPTIONS = {}` raises), entry `'FontManager.OPTIONS'`.

- [ ] **Step 2: Run** `-k own_font_system`. Expected: `1 failed`: `assert 'freetype' == 'pygame'`.

- [ ] **Step 3: Implement.** Every `FontManager.OPTIONS` in `font_manager.py` becomes
`_font_options()` (once per method, into a local); the class body's `OPTIONS` declaration goes,
and the class body gains the view. Rewrite the 4 lines:
`FontManager.OPTIONS = {'font_name': 'arial', 'font_size': 16}` becomes
`FontManager.OPTIONS.clear()` and `FontManager.OPTIONS.update({...})` (the same options, set in
the current context's dict in place).
Check: `test_the_engine_never_reads_a_view` passes.

- [ ] **Step 4–6:** lint; run the font tests, the Bitmappy film-strip tests, the engine-context
and views files, the suite; commit by path, message `Engine context: the font options belong to
the context (C13)` with the trailer.

---

### Task 10: The singleton sprites per context (audit C15)

Not swapped by the spike (no tile game uses them); proven directly.

**Files:**
- Modify: `src/glitchygames/sprites/bitmappy_sprite.py:1016-1120`
- Modify: `tests/harness.py:267-290` (the `__instance__` loop)
- Test: `tests/sprites/test_sprite_core.py`, `tests/test_engine_context.py`
- Rewrite: `tests/sprites/test_sprite_core.py:1620, 2027, 2054`

**Interfaces:**
- Produces: `SINGLETONS_SLOT: ContextSlot[dict[type, object]]`, name
  `'glitchygames.sprites.bitmappy_sprite.singletons'`, factory `dict`, keyed by the exact class
  constructed (so a subclass never receives its base's instance, the rule the `isinstance` checks
  keep today). The three `__new__` methods keep their signatures; the three `__instance__` class
  attributes are removed.

- [ ] **Step 1: Write the failing test**

```python
def test_each_context_has_its_own_singletons():
    """A singleton is single within its context only, a subclass's too (audit C15)."""

    class PanelSingleton(Singleton):
        """A subclass, which gets its own instance, never its base's."""

    first = EngineContext(name='first')
    second = EngineContext(name='second')
    with first.active():
        first_base = Singleton('first')
        first_panel = PanelSingleton()
    with second.active():
        second_base = Singleton('second')
        second_panel = PanelSingleton()
    with first.active():
        first_again = Singleton()

    assert second_base is not first_base
    assert second_panel is not first_panel
    assert first_panel is not first_base
    assert first_again is first_base
```

`check_singletons`, entry `'glitchygames.sprites.bitmappy_sprite.singletons'`.

- [ ] **Step 2: Run** `-k own_singletons`. Expected: `1 failed`: `assert <Singleton> is not
<Singleton>`.

- [ ] **Step 3: Implement.** Each `__new__`: `singletons = current_context().value(slot=
SINGLETONS_SLOT)`; `instance = singletons.get(cls)`; when `not isinstance(instance, cls)`, make it
and store it under `cls`. Harness: the loop becomes
`default_context().reset_value(slot=SINGLETONS_SLOT)`; the docstring of
`_reset_all_singleton_instances` drops the `__instance__` explanation. The three test lines
become the same reset.
Check: `grep -rn '__instance__' src tests` prints nothing.

- [ ] **Step 4–6:** lint; run; suite; commit by path, message `Engine context: the singleton
sprites belong to the context (C15)` with the trailer.

---

### Task 11: The debug-events log set per context (audit C17)

Latent in the spike. Its four test lines are rewritten here (decision 1).

**Files:**
- Modify: `src/glitchygames/events/base.py:221, 270-283`
- Modify: `tests/harness.py`: a new autouse fixture `reset_engine_bookkeeping`, listed in
  `per_context_state_resets` (`:592-610`), resetting `UNHANDLED_EVENT_TYPES_SLOT` in the default
  context before and after each test (Task 12 adds its own slot to it)
- Test: `tests/events/test_events_core.py`, `tests/test_engine_context.py`
- Rewrite: `tests/engine/test_game_engine.py:2863`, `tests/events/test_events_core.py:1268, 1280,
  1334`

**Interfaces:**
- Produces: `UNHANDLED_EVENT_TYPES_SLOT: ContextSlot[set[int]]`, name
  `'glitchygames.events.base.unhandled_event_types'`, factory `set`. `unhandled_event` keeps its
  signature. `_unhandled_event_types` is removed.

- [ ] **Step 1: Write the failing test**

```python
    def test_each_context_logs_an_unhandled_event_type_once(self, caplog):
        """--debug-events logs each type once per context: a second game logs its own (C17)."""
        game = GameWithOptions(options={'debug_events': True, 'no_unhandled_events': False})
        event_to_report = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        with caplog.at_level(logging.WARNING, logger='game.events'):
            with EngineContext(name='first').active():
                unhandled_event(game, event_to_report)
                unhandled_event(game, event_to_report)
            with EngineContext(name='second').active():
                unhandled_event(game, event_to_report)

        warnings = [
            record for record in caplog.records if record.getMessage().startswith('Unhandled Event')
        ]
        assert len(warnings) == 2
```

(`'game.events'` is `glitchygames.events.base.LOG`'s name, `base.py:48`.)
`check_unhandled_event_types` in `tests/test_engine_context.py`, entry
`'glitchygames.events.base.unhandled_event_types'`.

- [ ] **Step 2: Run** `-k logs_an_unhandled_event_type_once`. Expected: `1 failed`: `assert 1 == 2`.

- [ ] **Step 3: Implement** the slot; `unhandled_event` reads it once into a local. Rewrite
(decision 1): `test_game_engine.py:2863` and `test_events_core.py:1268, 1334` are deleted (the
harness starts every test with none logged; the comment at `:2862` goes with its line);
`test_events_core.py:1280` is deleted, the next lines asserting the behaviour (no second warning).
Check: `grep -rn '_unhandled_event_types' src tests` prints nothing.

- [ ] **Step 4–6:** lint; run; the leak-check guard
`test_the_harness_leak_check_is_torn_down_before_every_engine_state_reset` passes with the new
fixture; suite; commit by path, message `Engine context: the debug-events log set belongs to the
context (C17)` with the trailer.

---

### Task 12: The sprite counters per context (audit C18, with `SPRITE_COUNT`)

Latent in the spike; confirmed per game by the owner (2026-10-28). `Sprite.SPRITE_COUNT`
(`sprite.py:49`, rebound at `:157`, logged at `game_engine.py:4265`) is the same report's total
and was missing from the audit; it moves here.

**Files:**
- Modify: `src/glitchygames/sprites/sprite.py:38-170`;
  `src/glitchygames/engine/game_engine.py:4257-4268`
- Modify: `tests/harness.py` (`reset_engine_bookkeeping` also resets `SPRITE_COUNTERS_SLOT`)
- Test: `tests/sprites/test_sprite_core.py`, `tests/test_engine_context.py`,
  `tests/test_read_only_views.py`
- Rewrite (writers only, 9 lines): `Sprite.SPRITE_BREAKPOINTS = ...` at
  `tests/sprites/test_sprite_core.py:752, 756, 762, 1707, 1711, 1717`;
  `mocker.patch.object(Sprite, 'SPRITE_COUNT' | 'SPRITE_COUNTERS', ...)` at
  `tests/engine/test_game_engine.py:2622-2624`. Readers stay (`:182-200`, `:758, 764-765, 1713,
  1720`; `'SPRITE_COUNT' not in vars(first_sprite)` still holds: a view is not an instance
  attribute).

**Interfaces:**
- Produces, in `sprite.py`:
  ```python
  @dataclasses.dataclass
  class SpriteCounters:
      counters: collections.OrderedDict[str, dict[str, int | float]]  # default_factory OrderedDict
      breakpoints: list[str] | None = None   # None: no breakpoints; []: every sprite
      count: int = 0
  SPRITE_COUNTERS_SLOT: ContextSlot[SpriteCounters]  # name 'glitchygames.sprites.sprite.counters'
  def sprite_counters() -> SpriteCounters: ...  # the current context's
  ```
  `Sprite.break_when` keeps its signature. Views in the class body (`ReadOnlyView`, never `None`):
  `Sprite.SPRITE_COUNTERS`,
  `Sprite.SPRITE_BREAKPOINTS`, `Sprite.SPRITE_COUNT` (the current context's `counters`,
  `breakpoints`, `count`; a fresh context's: empty, `None`, `0`), `write_instead` naming
  `sprite_counters().counters` / `.breakpoints` / `.count`. The class body's three declarations
  go.

- [ ] **Step 1: Write the failing test**

```python
def test_each_context_counts_its_own_sprites():
    """Sprites made in one context are never counted in another's report (audit C18)."""
    first = EngineContext(name='first')
    second = EngineContext(name='second')
    with first.active():
        Sprite(x=0, y=0, width=SPRITE_WIDTH, height=SPRITE_HEIGHT)
        Sprite.break_when(sprite_type=Sprite)
    with second.active():
        second_count = Sprite.SPRITE_COUNT
        second_breakpoints = Sprite.SPRITE_BREAKPOINTS
    with first.active():
        first_count = Sprite.SPRITE_COUNT

    assert first_count == 1
    assert second_count == 0
    assert second_breakpoints is None
```

(It reads through the views, the names games and tests know.) `check_sprite_counters` in
`tests/test_engine_context.py`, entry `'glitchygames.sprites.sprite.counters'`; the three view
checks in `tests/test_read_only_views.py` (`'Sprite.SPRITE_COUNTERS'`,
`'Sprite.SPRITE_BREAKPOINTS'`, `'Sprite.SPRITE_COUNT'`).

- [ ] **Step 2: Run** `-k own_sprites`. Expected: `1 failed`: `second_count` (or `first_count`) is the
process-wide count, not the context's.

- [ ] **Step 3: Implement.** `break_when` and `__init__` read `sprite_counters()` once into a local
and update its fields; the comment at `:155-156` (BUGS.md #201) now says the count is the
context's, never the sprite's. `_log_sprite_count_report` reads `sprite_counters()`.
Rewrite the 9 lines: `Sprite.SPRITE_BREAKPOINTS = None` resets are deleted (the harness resets)
and assignments of `[]` become `sprite_counters().breakpoints = []`; `test_game_engine.py:2622-2624`
make the sprites the report should count (three `Sprite`s of a test type) instead of patching,
and assert the logged lines.
Check: `test_the_engine_never_reads_a_view` passes.

- [ ] **Step 4–6:** lint; run; suite; commit by path, message `Engine context: the sprite counters
belong to the context (C18)` with the trailer.

---

### Task 13: The process-state guard (the audit as an allowlist scan)

**Files:**
- Create: `tests/test_process_state_guard.py`
- Modify: `tests/test_suite_collection.py:1180-1220` (`REPOSITORY_TEST_FILES` gains
  `'tests/test_process_state_guard.py': SOURCE_GUARD_REASON`)

**Interfaces:**
- Consumes: `tests.ast_scanning.PROJECT_ROOT`; `tests.workspace_sources.scanned_source_files(*,
  project_root: Path) -> list[tuple[str, Path]]` and `write_project_with_member_module(*,
  project_root: Path, source: str) -> str`.
- Produces:
  ```python
  def process_state_in_source(*, source_path: Path, frozen_classes: frozenset[str]) -> dict[str, int]: ...
  def frozen_class_names(*, source_paths: Sequence[Path]) -> frozenset[str]: ...
  def scanned_process_state(*, project_root: Path) -> dict[str, dict[str, int]]: ...
  PROCESS_STATE: dict[str, dict[str, str]]   # allowlist key -> {qualified name: reason}
  AUDIT_ROW_REASON = re.compile(r'(S\d+|R\d+|C16): .+')
  ```
  `process_state_in_source` returns each finding's qualified name (`name`, `Class.name`,
  `Outer.Inner.name`) and its first line.

**What the scan reports** (decide nothing else; this is the rule):

1. A module-level or class-body binding (`=`, annotated `=`) whose value is not evidently
   immutable, except `__all__` and `model_config`. Evidently immutable: a literal constant, an
   f-string, a name or attribute reference (but a bare name bound, in the same module, to a value
   this scan reports is reported too: an alias of a mutable), a subscript (a type alias such as
   `FloatArray = npt.NDArray[np.float64]`, `Literal[...]`, `Annotated[...]`, or
   `vars(SomeClass)['name']`; review I-7), a lambda, a comparison or boolean expression, a tuple
   (starred items included) of evidently immutable values, a unary or binary operation on them, a
   method call on a string literal (`'; '.join(...)`), and a call to `frozenset`, `tuple`, `int`,
   `float`, `str`, `bool`, `bytes`, `object`, `re.compile`, `logging.getLogger`, `ContextSlot`,
   `contextvars.ContextVar`, `TypeVar`, `ParamSpec`, `TypeVarTuple`, `TypeAliasType`, `NewType`, `Path`/`pathlib.Path`, `types.MappingProxyType`,
   `dataclasses.field`, pydantic `Field`/`ConfigDict`, `struct.Struct`, `enum.auto`, `typing.cast`,
   `fractions.Fraction`, `math.*`, `pygame.event.custom_type`, `datetime.timedelta`,
   `decimal.Decimal`, `collections.namedtuple`, `ReadOnlyView`, `ClassOnlyView` (a view computes, it
   stores nothing: answer 2), or a class in `frozen_class_names` (scanned classes
   that subclass `Enum`/`IntEnum`/`StrEnum`/`Flag`/`NamedTuple`, are `@dataclass(frozen=True)`, or
   set `model_config = ConfigDict(frozen=True, ...)`). A `type X = ...` statement is not a
   binding and is never reported.
2. Except: a constant-named binding (`_*[A-Z][A-Z0-9_]*`) whose value is a dict, list or set
   display or comprehension, or an operation on one, is a table, reported only when the scan sees
   it written anywhere in the scanned files: an item or attribute assignment, augmented assignment
   or `del` through it, or a call of `append`, `extend`, `insert`, `update`, `setdefault`, `pop`,
   `popitem`, `clear`, `remove`, `discard`, `add`, `sort`, `reverse` on it (matched by its last
   name: `NAME`, `self.NAME`, `cls.NAME`, `Class.NAME`).
3. Every name in a `global` statement.
4. Every assignment, augmented assignment or `del`, inside a function, of an attribute of a
   class object: the receiver is `cls` (reported as the enclosing class's), a capitalized,
   non-constant name, a parameter annotated `type[...]` (alone or in a union, such as
   `game: type[Scene] | Scene`: review I-6), `type(<expression>)` or `<expression>.__class__`;
   and every `setattr(...)`/`delattr(...)` call whose first argument is one of those, or an
   imported module or an attribute of one (`setattr(pygame.mixer.music, ...)`), reported as
   `setattr(<receiver>)`. An attribute store is reported as `<class>.<name>`: the enclosing class
   for `cls`, `type(self)` and `self.__class__`, the annotated class for a `type[...]` parameter
   (the first `type[...]` member of a union).
5. Every function decorated with `functools.cache`, `functools.lru_cache`, `cache` or
   `lru_cache` (a process-wide cache), reported by the function's qualified name.

Limits (in the module docstring): an object bound to a constant-named table is trusted unless the
scan sees it written by those means; changes through other methods are not seen, which is why rule
1 reports every non-immutable object whatever its name. A frozen class is trusted even when it
holds a mutable field (`BOOKMARK_CONTROL_EVENT = ControlEvent(..., data={...})`,
`replay/driver.py:471`). A `setattr` whose receiver is only known at run time is not seen
(`replay/tools/golden_traces.py:386-396` swaps a module function in a loop over pairs, restoring
it in a `finally`: the same kind of state as S17's, which the scan does see, a recording tool's,
never in a game).

**The allowlist after Tasks 2–12** (each reason begins with its audit row; rows marked new are
added to the master plan by Task 16). Engine files are keyed from `src/glitchygames/`, members from
the repository:

| Key | Names | Row |
|---|---|---|
| `api/dependencies.py` | `get_config`, `get_sprite_generation_service`, `get_renderer_service` (caches) | R11 |
| `api/main.py`, `api/routes/health.py`, `api/routes/sprites.py` | `app`, `router`, `router`, `ALLOWED_OUTPUT_ROOT` | R11 (the API server's, not a game's) |
| `audio/live.py` | `_pool_grown_mixer_channel_counts` | S3 |
| `backgrounds.py` | `background_pattern_surface` (cache) | R7 |
| `build_info.py` | `package_source_revision`, `engine_source_revision` (caches) | R6 |
| `machine_state.py` | `current_machine_state` (cache) | R6 |
| `clipboard.py` | `_REGISTRY` | S9 |
| `user_files.py` | `_REGISTRY` | S10 |
| `state/manager.py` | `_DISK_SAVE_CHANGE_OBSERVERS` | S11 |
| `replay/viewer.py` | `_SLEEP_TIMER` | S12 |
| `events/base.py` | `HashableEvent._hashing_ids`, `HashableEvent._comparing_ids` | S13 |
| `events/base.py` | `AUDIO_EVENTS` … `GAME_EVENTS` (the event-type lists the scan reports) | R15 (new: the engine's tables computed at import, never written) |
| `events/base.py` | `pygame_event_names` (`@functools.cache`, #114, behind `supported_events`) | R15 (pygame's compiled event names, an immutable table scanned once per process, the same in every context; the controller's ruling, 2026-10-29) |
| `world.py` | `_scenes_warned_about_double_update` | S14 |
| `replay/silence.py` | `_MUSIC_FOLLOWING`, `setattr(pygame.mixer.music)` (`:144`) | S4 |
| `replay/tools/scripted_sessions.py` | `setattr(live_sources)` (`:182, 186`, `polled_input_follows`) | S17 (new, review re-check N-2: a recording tool's temporary swap of a module function, `glitchygames.live_sources.capture_live_snapshot`, process-wide while held and restored in a `finally`; `record-session` records one game in its own process, never inside a game or an inner context) |
| `color/constants.py` | `_default_colors` and the colors made by `_to_rgb`/`_to_rgba` | R2 |
| `debug/panels.py` | `_BACKING_SURFACES` | R8 |
| `fonts/font_manager.py` | `FontManager._font_cache` | R9 |
| `input/devices.py`, `events/midi.py` | `_SDL_CONTROLLER_MODULE`, `MIDI_MODULE` | R5 |
| `input/state.py` | `_SCANCODE_OF_KEY_CODE` | R3 |
| `engine_context.py` | `_DECLARED_SLOTS`, `_DEFAULT_CONTEXT` | R13 (the default context is the mechanism itself) |
| `engine/game_engine.py` | `GameEngine.icon` | S2 |
| `engine/game_engine.py` | `GameEngine.PYGAME_FOUND_WITH_SDL_SIGNAL_HANDLERS` (`:710`, rebound at `:1142, 1147`) | S8 (process services: whether this process's pygame started with SDL's signal handlers; one pygame per process; the controller's ruling, 2026-10-29) |
| `engine/game_engine.py` | `GameEngine.USE_FASTEVENTS` | R12 (decided by the pygame version) |
| `services/renderer_service.py` | `RendererService.pygame_initialized` | S16 (new: the API server's renderer started pygame; the process's) |
| `sprites/bitmappy_sprite.py` | `BitmappySprite.DEFAULT_SURFACE` | R12 (a class default nothing draws on) |
| `replay/tools/settings.py`, `testing/frame_comparison.py` | `ProjectSettings.recording_renames`, `DriverComparison.frames_vary` | R12 (pydantic field defaults, copied per instance) |
| `src/apps/bitmappy/src/bitmappy/ai_manager.py` | `_RUNNING_AI_MANAGERS`, `_AI_REQUEST_COUNTER` | S15 |
| `src/apps/bitmappy/src/bitmappy/pixel_sprite.py` | `BitmapPixelSprite.PIXEL_CACHE` | R10 |
| `src/apps/bitmappy/src/bitmappy/controllers/manager.py` | `MultiControllerManager._instance` | C16 |
| `src/apps/bitmappy/src/bitmappy/onion_skinning.py` | `onion_skinning_manager` | C16 (Bitmappy's onion-skinning state) |
| `src/apps/bitmappy/src/bitmappy/constants.py` | `ai_training_state` | C16 (Bitmappy's AI training data) |
| `src/games/brave-adventurer/...` | `_COMMON_POSE_X_RANGES`, `_vertical_gradient_cache` | R14 |
| `src/games/clockwork-keep/src/clockwork_keep/levels.py` | `FLOOR_BOILER_ROOM`, `FLOOR_GEAR_WORKS`, `FLOOR_CLOCK_FACE` (a non-frozen `FloorData` dataclass, `levels.py:56`; never written) | R14 |
| `src/games/drawing-fire/...` | `text_surface`, `_banner_surface` (caches), `SCANCODE_NAMES` | R14 |
| `src/games/mr-muncher/...` | the ten `drawing.py` caches, `shared_sound_bank` (cache), `CRUNCH_ONE`, `CRUNCH_TWO` | R14 |

The read-only views (Tasks 1–12) need no entry: they are computed on every read and store
nothing, so the scan does not report them (a `ReadOnlyView` or `ClassOnlyView` in a class body,
a `@property` on a metaclass, a module `__getattr__`); the planted test pins that. The
write-refusing metaclasses hold no state.

The table was checked against a prototype of these rules over `scanned_source_files` at
b5f16688 (this plan's author's, and the review's: its rules 3–5 output matched the table
exactly), and again on main at 3f916b97 (2026-10-29): the same findings plus the two rows marked
2026-10-29 (`GameEngine.PYGAME_FOUND_WITH_SDL_SIGNAL_HANDLERS`, `pygame_event_names`). Before writing `PROCESS_STATE`, run the scan and compare: a finding that fits no row
above is newly found state: stop and report it to the controller (the owner decides its row);
never add a row on your own. A C7–C15 or C17–C20 name in the findings means a task above missed
it: fix that task. `REBUILD_KEYS` (`replay/controls.py:99`) is an unwritten constant table under
rule 2 and not reported.

- [ ] **Step 1: Write the scan's own tests first**

```python
PLANTED_PROCESS_STATE = """\
import functools
import itertools
from typing import NamedTuple

import numpy as np
import numpy.typing as npt

from glitchygames.engine_context import ContextSlot
from glitchygames.read_only_views import ClassOnlyView, ReadOnlyView, ReadOnlyViews

LIMIT = 3
NAMES = ('a', 'b')
TABLE = {'a': 1}
WRITTEN_TABLE = {'a': 1}
cache_of_drawings = {}
COUNTER = itertools.count()
SLOT = ContextSlot(name='planted.slot', factory=dict)


class Point(NamedTuple):
    x: int


ORIGIN = Point(x=0)


class Holder:
    DEFAULTS = ()
    instances = []
    count = 0

    @classmethod
    def made(cls):
        cls.count += 1


def remember(key):
    global last_key
    last_key = key
    WRITTEN_TABLE[key] = 2


@functools.cache
def picture(size):
    return size


FloatArray = npt.NDArray[np.float64]
COUNT_SLOT = vars(Holder)['count']
ALIAS = cache_of_drawings


class Rebinder:
    def touch(self, game: type[Holder] | Holder):
        type(self).touched = True
        self.__class__.seen = True
        setattr(Rebinder, 'flag', True)
        game.options = {}


class PlantedMeta(type):
    @property
    def computed(cls):
        return LIMIT


class Viewed(metaclass=ReadOnlyViews):
    SHOWN = ReadOnlyView(read_current=lambda owner: LIMIT, read_own=lambda viewed: LIMIT, write_instead='nowhere')
    kept = ClassOnlyView(read_current=lambda owner: None, write_instead='nowhere')


def __getattr__(name):
    if name == 'manager':
        return LIMIT
    raise AttributeError(name)
"""


def test_the_process_state_scan_finds_every_kind(tmp_path):
    """Mutable bindings, written tables, objects, rebound class names, globals and caches.

    Never a view: the class's ReadOnlyView and ClassOnlyView, a metaclass property and the module
    __getattr__ store nothing.
    """
    source_path = tmp_path / 'planted.py'
    source_path.write_text(PLANTED_PROCESS_STATE, encoding='utf-8')
    frozen = frozen_class_names(source_paths=[source_path])

    found = process_state_in_source(source_path=source_path, frozen_classes=frozen)

    assert set(found) == {
        'WRITTEN_TABLE',
        'cache_of_drawings',
        'COUNTER',
        'Holder.instances',
        'Holder.count',
        'last_key',
        'picture',
        'ALIAS',
        'Rebinder.touched',
        'Rebinder.seen',
        'setattr(Rebinder)',
        'Holder.options',
    }


def test_process_state_in_a_member_is_reported_under_its_repository_path(tmp_path):
    key = write_project_with_member_module(project_root=tmp_path, source='seen = []\n')

    assert scanned_process_state(project_root=tmp_path) == {key: {'seen': 1}}


def test_every_piece_of_process_state_is_in_the_audit():
    """A new module- or class-level mutable, rebinding, global or cache fails until listed."""
    found = scanned_process_state(project_root=PROJECT_ROOT)
    unlisted = {
        f'{key}: {name} (line {line})'
        for key, names in found.items()
        for name, line in names.items()
        if name not in PROCESS_STATE.get(key, {})
    }

    assert unlisted == set()


def test_every_listed_piece_of_process_state_still_exists():
    found = scanned_process_state(project_root=PROJECT_ROOT)
    stale = {
        f'{key}: {name}'
        for key, names in PROCESS_STATE.items()
        for name in names
        if name not in found.get(key, {})
    }

    assert stale == set()


def test_every_listing_names_its_audit_row():
    unnamed = {
        f'{key}: {name}'
        for key, names in PROCESS_STATE.items()
        for name, reason in names.items()
        if AUDIT_ROW_REASON.fullmatch(reason) is None
    }

    assert unnamed == set()
```

Start with `PROCESS_STATE = {}`.

- [ ] **Step 2: Run them to see the right ones fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_process_state_guard.py`
Expected: fails at import (the functions do not exist yet).

- [ ] **Step 3: Implement the scan** in the test module (as `tests/test_engine_doors.py` keeps its
scan), with the module docstring stating the five rules and the limits. It parses one file at a
time and keeps no tree past its file (CI's 1600 MiB memory limit; #112 made
`tests/test_suite_collection.py`'s `_root_test_modules` yield one tree at a time for the same
reason): a first pass over the files collects only names (`frozen_class_names`, the written
tables), then a second pass parses each file again and runs `process_state_in_source` on it. Run the file: the two
planted tests pass and `test_every_piece_of_process_state_is_in_the_audit` lists the findings.

- [ ] **Step 4: Fill `PROCESS_STATE` from the table**, every reason a full sentence after its row
(`'S9: the player's clipboard; the browser page installs its own'`). Add the file to
`REPOSITORY_TEST_FILES`.

- [ ] **Step 5: Lint, run the file and `tests/test_suite_collection.py`, then the suite**

Expected: all pass; coverage 100%.

- [ ] **Step 6: Commit** `tests/test_process_state_guard.py tests/test_suite_collection.py`,
message `Engine context: the process-state guard (the audit as an allowlist scan)` with the
trailer.

---

### Task 14: Nothing restyles a shared cached font (R9, decision 2)

**Files:**
- Create: `tests/test_shared_font_cache_guard.py`
- Modify: `tests/test_suite_collection.py` (`REPOSITORY_TEST_FILES`: `SOURCE_GUARD_REASON`)

**Interfaces:**
- Produces: `in_place_font_style_changes(*, source_path: Path) -> list[str]` (`'<line>: <what>'`
  each), `FONT_STYLE_SETTERS`, `FONT_STYLE_ATTRIBUTES`, `FONT_SIZE_ATTRIBUTES`.

**The rule** (review I-8): a call of `set_bold`, `set_italic`, `set_underline`,
`set_strikethrough`, `set_point_size`, `set_script` or `set_direction` (pygame-ce
`pygame.font.Font`'s setters; distinctive names) on anything; and, on a receiver whose dotted
name contains `font` (any case: `font`, `self.title_font`, `label_font`), an assignment,
augmented assignment or `del` of an attribute that changes how it renders: `bold`, `italic`,
`underline`, `strikethrough`, `point_size`, `outline`, `align` (pygame.font.Font), `size`,
`style`, `strong`, `oblique`, `wide`, `strength`, `underline_adjustment`, `antialiased`,
`kerning`, `vertical`, `rotation`, `fgcolor`, `bgcolor`, `pad`, `origin`, `ucs4`,
`use_bitmap_strikes` (pygame.freetype.Font), or a `setattr`/`delattr` on such a receiver. The
attribute names are generic (`self.strength` is the gravity behaviour's acceleration,
`physics/behaviors.py:57`; `rect.size` is a `Rect`'s), hence the receiver condition. There is no
allowlist: fonts come from `FontManager`'s one cache per process (`font_manager.py:138-139`), so
a font is restyled per render call (`render(..., style=...)`), never in place. Checked at
b5f16688, and again at 3f916b97 (2026-10-29), with these rules (a grep of the setters and of font-named receivers): the engine and
every member have no finding.

- [ ] **Step 1: Write the tests**

```python
PLANTED_FONT_CHANGES = """\
def restyle(font, title_font, label, gravity):
    font.set_bold(True)
    title_font.strong = True
    font.underline = True
    title_font.size = 24
    label.rect.size = (4, 4)
    font.render('text', style=1)
    gravity.strength = 2
    setattr(title_font, 'fgcolor', (1, 2, 3))
    label.font.rotation += 90
"""


def test_the_font_style_scan_finds_every_in_place_change(tmp_path):
    source_path = tmp_path / 'planted.py'
    source_path.write_text(PLANTED_FONT_CHANGES, encoding='utf-8')

    assert in_place_font_style_changes(source_path=source_path) == [
        '2: set_bold',
        '3: strong',
        '4: underline',
        '5: size',
        '9: setattr',
        '10: rotation',
    ]


def test_nothing_restyles_a_shared_cached_font_in_place():
    """The font caches are one per process (R9): a style change would reach every context."""
    findings = {
        key: changes
        for key, path in scanned_source_files(project_root=PROJECT_ROOT)
        if (changes := in_place_font_style_changes(source_path=path))
    }

    assert findings == {}
```

- [ ] **Step 2: Run** the file. Expected: fails at import.
- [ ] **Step 3: Implement** the scan; the module docstring quotes decision 2.
- [ ] **Step 4: Run** the file (`2 passed`), `tests/test_suite_collection.py`, the suite.
- [ ] **Step 5: Commit** both files, message `Engine context: guard that nothing restyles a shared
cached font (R9)` with the trailer.

---

### Task 15: Two engines with different options side by side

The engine-level counterpart of sub-plan 1's `test_two_contexts_hold_two_games_worth_of_state_without_leaking`:
the spike's open question 1 ("two stand-in games with different options, so options cannot be
mixed up silently"). It steps events, not frames (a frame step outside its context is sub-plan 3's;
an inner engine is sub-plan 7's).

**Files:**
- Create: `tests/engine/test_engine_contexts_side_by_side.py`

**Interfaces:**
- Consumes: `start_engine_with_scene`, `ScriptedBatchSources`, `AudioAndControllerRecordingScene`
  (`tests/events/test_events_integration.py`); `AdaptiveClamping`, `FontManager`,
  `sprite_counters`, `pending_internal_posts`, `post_event`.
- Produces: `StandInRun` (pydantic, frozen: `scene_class: type[Scene]` (a stand-in subclass of
  `AudioAndControllerRecordingScene` per run, so the two runs' game classes differ),
  `arguments: tuple[str, ...]`, `font_system: str`, `scene_name: str`, `audio_device: int`,
  `missing_handler: str`, `singleton_label: str`; the two scene classes are
  `FirstStandInScene` and `SecondStandInScene`, empty subclasses defined in the test module) and `EngineReadings` (frozen), one field per
  row (review M-5): `target_fps` (C8), `manager_target_fps` (C7), `game_class_name` (C9:
  `engine.game`'s class name), `game_class_keeps_no_options` (C20: `'options' not in
  vars(run.scene_class)`), `event_reached_own_scene` (C10), `missing_events` (C11:
  `tuple(engine.missing_events)` after calling `engine.<missing_handler>()`),
  `shared_mouse_manager_is_own` (C12: `MouseEventManager() is engine.mouse_manager`), `font_system`
  (C13), `performance_scenes` (C14), `singleton_is_own` (C15: `Singleton() is` the instance `set_up_run` made with
  `Singleton(run.singleton_label)` in the run's context; identity, because `Singleton.__new__`
  sets `args` on every call, `bitmappy_sprite.py:1043-1044`, so its args would equal the label
  even if shared: re-check m-2),
  `sprite_count` (C18), `pending_post_count` (C19), and through the views `view_target_fps`
  (`GameEngine.OPTIONS`, narrowed), `view_sprite_count` (`Sprite.SPRITE_COUNT`),
  `current_engine_is_own` (`current_engine() is engine`). C17 has no field: its effect is a
  warning logged once, which needs `--debug-events` and `caplog` around each step; its collision
  test (Task 11) and isolation check cover it. `set_up_run(*, run: StandInRun) -> tuple[GameEngine,
  Scene, Singleton]` and `play_step(*, run: StandInRun, engine: GameEngine, scene: Scene,
  singleton: Singleton) -> EngineReadings`.

- [ ] **Step 1: Write the test**

```python
def test_two_engines_with_different_options_side_by_side_read_what_each_reads_alone():
    """Two engines started with different options, stepped in turn, read what each reads alone."""
    runs = [
        StandInRun(
            scene_class=FirstStandInScene,
            arguments=('--target-fps', '30'),
            font_system='freetype',
            scene_name='First',
            audio_device=1,
            missing_handler='on_first_missing_event',
            singleton_label='first',
        ),
        StandInRun(
            scene_class=SecondStandInScene,
            arguments=('--target-fps', '50'),
            font_system='pygame',
            scene_name='Second',
            audio_device=2,
            missing_handler='on_second_missing_event',
            singleton_label='second',
        ),
    ]
    alone = [run_alone(run=run, step_count=STEP_COUNT) for run in runs]
    side_by_side = run_side_by_side(runs=runs, step_count=STEP_COUNT)

    assert side_by_side == alone
    assert alone[0] != alone[1]
```

`set_up_run` (inside the run's context): `start_engine_with_scene(scene_class=run.scene_class,
...)` with the run's arguments plus `--no-unhandled-events`, `engine.scene_manager.game_engine =
engine`, `FontManager.set_font_system(...)`, `AdaptiveClamping().set_current_scene(run.scene_name)`,
and `Singleton(run.singleton_label)`, kept with the engine for `singleton_is_own`; it returns
`(engine, scene, singleton)` (its signature in Interfaces gains the singleton).
`play_step` (inside the run's context): installs a `ScriptedBatchSources` with one
`AUDIODEVICEADDED` of `which=run.audio_device`, `engine.process_events()`, one
`AdaptiveClamping().track_fps_from_event(...)`, one `post_event(pygame.event.Event(pygame.USEREVENT))`
(then `pygame.event.get(eventtype=pygame.USEREVENT)` to leave SDL's queue empty), one `Sprite`,
and returns the readings. `run_alone` runs one run's steps in a fresh context;
`run_side_by_side` sets up both in their contexts, then alternates a step of each; both end each
context with `reset_sources()` inside it and return a list of readings per run.

- [ ] **Step 2: Run it**

Run: `uv run pytest --dummy-only --no-cov -q tests/engine/test_engine_contexts_side_by_side.py`
Expected: `1 passed`. This is a regression test written after the moves (each row's failing test
came first, in its task); the reviewer checks that every row C7–C20 (C16 aside, C17 as said
above) has a field and every field reads its row, so none of them is vacuous.

- [ ] **Step 3–4:** lint; suite; commit the file, message `Engine context: two engines with
different options side by side` with the trailer.

---

### Task 16: Documentation, audit and status (answer 5, 2026-10-28)

The owner: "update the documentation since this changes some assumptions". Every doc that states or
relies on the process-wide names, or on one game per process, now says what is per game and
documents the views as "read-only; the current game's; None outside a game", and tells code to
write the instance (or the slot's owner function) instead.

**Files** (found with `grep -rnE 'GameEngine\.(OPTIONS|EVENT_HANDLERS|MISSING_EVENTS|UNIMPLEMENTED_EVENTS|LAST_EVENT_MISS|game)|SceneManager\.OPTIONS|FontManager\.OPTIONS|performance_manager|SPRITE_COUNT|SPRITE_BREAKPOINTS|__instances__|_INTERNAL_POSTS|_unhandled_event_types|EVENT_HANDLERS|shutdown report' docs CLAUDE.md README.md BUGS.md plans/future-features.md plans/future-work.md plans/2026-10-23-arcade-showcase.md plans/2026-10-24-workspace-packages.md plans/2026-10-25-engine-context.md src --include='*.md' --include='*.py'` at b5f16688, rechecked at 3f916b97: one new code hit,
`game_engine.py:3145`, Task 5's, and BUGS.md #238, a resolved entry left as it is; rerun it in
Step 1 and add any new hit):
- `docs/architecture/engine_context.md` (`:5-10` intro, the slot table, a new "Read-only views"
  section, the guards)
- `docs/architecture/event_system.md:339, 586, 2553, 2663-2716`
- `docs/architecture/argument_system.md:38, 136, 140, 149, 232-233` (`:38` also shows
  `game.options = OPTIONS`, which Task 6 removes)
- `docs/architecture/bitmappy.md:84, 191, 247, 256, 388` (`EVENT_HANDLERS`: "the engine's")
- `docs/quality/performance.md` (one game per process; per-game reports)
- `README.md:238-239` and the `--perf-trim-percent` / `--fps-histogram` help in
  `src/glitchygames/engine/game_engine.py` with its copy in `docs/glitchygames/index.md:87-141`
  ("the game's shutdown report")
- `CLAUDE.md:254, 1093-1115, 1200, 1330`, the Design Patterns Singleton line
- `BUGS.md:627` (#210, active: "`FontManager.OPTIONS`" becomes "the context's font options
  (`FontManager.OPTIONS`, a read-only view)")
- `plans/2026-10-25-engine-context.md`, `plans/future-features.md`
- docstrings that tell readers to use a view: `src/glitchygames/replay/driver.py:3049`,
  `src/glitchygames/replay/tools/registry.py:642, 688, 727`,
  `src/glitchygames/replay/tools/traces.py:379, 446` (already "the engine's ``options``" from
  Task 5: check), and the module docstrings of `read_only_views.py`, `performance/__init__.py`,
  `adaptive_clamping.py`
- `tests/test_suite_collection.py` (the living-docs guard), `tests/test_read_only_views.py`
  (the engine context page's views section, and the documented read costs against the gate),
  `tests/benchmarks/test_engine_context_benchmarks.py` (created with `READ_RATIO_LIMITS` only)

No game's own docs or docstrings name a view (checked at b5f16688 and 3f916b97: the members' `*.md` and source
have no hit); rerun the grep over `src/games`, `src/demos`, `src/apps` in Step 1.

**Interfaces:**
- Produces, in `tests/test_suite_collection.py`: `VIEW_WRITE_PATTERN: re.Pattern[str]` (an
  assignment, augmented assignment or `del` of `GameEngine.`/`SceneManager.`/`FontManager.`/
  `Sprite.` + a view name, `performance_manager =`, `mocker.patch.object(<one of the four>,
  '<view>'` and `patch('glitchygames.performance.performance_manager'`), and
  `test_no_living_documentation_writes_to_a_read_only_view` over `living_documentation_lines()`
  (`:581`). It replaces nothing: no project guard checks names in the docs today (the living-docs
  guard checks paths). In `tests/test_read_only_views.py`:
  `test_the_engine_context_page_lists_every_view_and_where_to_write`.

- [ ] **Step 1: Write the two guard tests and run them.** `test_no_living_documentation_writes_to_a_read_only_view`
  fails on `docs/architecture/argument_system.md:38` (`GameEngine.OPTIONS = the options`) and
  `:140` (`SceneManager.OPTIONS = OPTIONS`); the page test fails (no views section yet).
  Rerun the Files grep; any new hit joins this task's list.
- [ ] **Step 2: `docs/architecture/engine_context.md`.** The intro says what is per context now
  (the slots, the engine's and scene manager's own attributes) and what is shared (the master
  plan's S rows); the slot table gains the eight slots of Tasks 1, 3, 4, 8–12 and the missing
  `glitchygames.game_frames.clock` row (`src/glitchygames/game_frames.py:67`,
  `game_frame_clock()`); a "Read-only views" section lists every view as a table (view, what it
  reads, outside a game, where to write: the `write_instead` text), states the rules (a view
  stores nothing; a module view is a name its module marks in `READ_ONLY_MODULE_VIEWS`, never a
  module `__getattr__` alone; a class-level read costs about 180 ns, Task 1's measurement says exactly, so
  engine code reads its objects; writing it
  raises `ReadOnlyViewError`), and names `current_engine()`; a paragraph names the guards
  (`tests/test_process_state_guard.py`, `tests/test_shared_font_cache_guard.py`,
  `tests/test_read_only_views.py`), and says the reports are per game, an outer game's being the
  aggregate (answer 3).
- [ ] **Step 2b: The known performance costs (the owner, 2026-10-28: "make sure you update the
  documentation to talk about these known performance impacts").** In
  `docs/architecture/engine_context.md`, a "Performance" section:
  - **The costs**, as a table whose rows are labelled exactly `attribute read`, `instance
    property`, `slot read`, `read-only view`, `current_engine()` and `context switch`, each with its
    median in ns, and a line naming the machine and the date. The view, slot and `current_engine()`
    figures are **Task 1 Step 5b's recorded measurements**, not this plan's estimates (about 181,
    73 and 75 ns); the attribute (about 12 ns), instance property (about 19 ns) and context switch
    (about 430 ns) are the owner's 2026-10-28 measurements on the same machine, cited as such.
    Task 17 replaces the read figures with its gate (c) medians when it runs (its Step 7).
  - **What they mean per frame:** engine code reads its own objects (`self.options`,
    `self.event_handlers`), so it pays nothing new; the slot-backed state a frame reads (doors,
    streams, input, the frame clock, the performance manager, the sprite counters, the post
    tracker) costs roughly 1–3 µs a frame; the Arcade pays about 0.4 µs per game per tick for
    switching; each game's performance report covers that game alone, and an outer game's
    (the Arcade wrapper's) is the aggregate of every game it steps (answer 3).
  - **The rules that follow:** engine code never reads a view (`test_the_engine_never_reads_a_view`
    enforces it); games, tools and tests may read views for convenience, but read their own object
    or a local in a hot loop; Task 17's gate (the recordings A/B against the base, behaviour
    unchanged, the per-call benchmarks and the per-read ratios to a slot read) keeps the numbers
    honest and is never relaxed.
  In `docs/quality/performance.md`, two sentences: these measurements replay one game alone in its
  process; when several games share a process, see `docs/architecture/engine_context.md`'s
  "Performance" section for what contexts cost and how each game's report stays its own.
  **The check:** `test_the_documented_read_costs_stay_within_the_gate` in
  `tests/test_read_only_views.py` parses the table's `slot read`, `read-only view` and
  `current_engine()` rows and asserts each documented ratio to the slot read is within
  `READ_RATIO_LIMITS` (`{'read-only view': 4.0, 'current_engine()': 2.0}`), which the benchmark
  module `tests/benchmarks/test_engine_context_benchmarks.py` defines and Task 17's gate (c) script
  uses, so the documented numbers can never drift past the gate. Task 16 creates the constant in
  that module (with the benchmarks' file, which Task 17 fills).
- [ ] **Step 3: The other docs**, as listed: `EVENT_HANDLERS` is "each engine's own
  (`engine.event_handlers`); `GameEngine.EVENT_HANDLERS` is the current game's, read-only";
  `ResourceManager`'s shared instances are "one per class per engine context"; the argument flow
  sets `engine.options` and `manager.engine_options`; `docs/quality/performance.md` says each
  measurement replays one game alone in its process, and that when several games share a process
  (the Arcade) each keeps its own FPS statistics and shutdown report, the outer game's covering
  the whole tick; the shutdown-report help and its copies say "the game's".
- [ ] **Step 4: `CLAUDE.md`**: the Engine Context section's "Only the slots below ..." sentence
  and "Slots today" list follow Step 2; a bullet on the views (read-only, the current game's,
  `None` outside a game, engine code uses the instance, `current_engine()`); a bullet naming the
  guards; `:254` "Pre-computes `EVENT_HANDLERS` dict (per engine)"; `:1330` the performance
  manager is per engine context; the Singleton line: "`SceneManager`, `AdaptiveClamping`, the
  shared event managers and `FontManager` (one per engine context)".
- [ ] **Step 5: `plans/2026-10-25-engine-context.md`**: the Status paragraph records sub-plan 2
  done on `feature/engine-context-2-engine-state` with its commit range; the audit: C7–C15,
  C17–C19 marked done (sub-plan 2), C7–C11 noting "on the engine / scene manager, old names
  read-only views" (answers 1, 2), C16's location corrected to
  `src/apps/bitmappy/src/bitmappy/controllers/manager.py:69`, its sub-plan column "the player
  roster (`plans/2026-10-28-player-roster-design.md`, `feature/player-roster`; the owner,
  2026-10-28)", and a note that Bitmappy's onion-skinning manager and AI training state are listed
  beside it with no owning plan yet; C18
  gains `SPRITE_COUNT`; a new row C20 (`<GameClass>.options`, written by
  `initialize_arguments` at `game_engine.py:1129`, removed by Task 6: found by the review); new S16,
  S17 (the recording tools' temporary module-function swaps: `scripted_sessions.py:182, 186` and
  `golden_traces.py:386-396`) and R15 rows as in Task 13's table; S8 gains
  `GameEngine.PYGAME_FOUND_WITH_SDL_SIGNAL_HANDLERS` and R15 gains `pygame_event_names` (the
  controller's ruling, 2026-10-29: process-wide, in no context); totals updated; the "Risks"
  bullet on state nobody listed points at `tests/test_process_state_guard.py`.
  `plans/future-features.md` entry 43: sub-plan 2 (the engine's own state) done.
- [ ] **Step 6:** Run the two guard tests (pass),
  `uv run pytest --dummy-only --no-cov -q tests/test_suite_collection.py -k living_documentation`
  (passes), and `nox -s lint-docs` (the strict mkdocs build succeeds).
- [ ] **Step 7: Commit** every touched file by path, message `Docs: the engine's own state per
  context, the read-only views, and the guards` with the trailer.

---

### Task 17: Whole-branch verification, and the performance gate

**Files:** Modify: `tests/benchmarks/test_engine_context_benchmarks.py` (created by Task 16 with
`READ_RATIO_LIMITS`; Step 7 adds the benchmarks), `docs/architecture/engine_context.md` (Step 7
writes the measured medians into its "Performance" table). Nothing else
changes: a failure is fixed in the task that owns it, then this task runs again.

- [ ] **Step 1:** `nox -s lint` — every lint session succeeds.
- [ ] **Step 2:** `nox -s static-analysis` — basedpyright `0 errors, 0 warnings, 0 notes`; ty `All
checks passed!`.
- [ ] **Step 3:** `CI=true nox -s test` — every test passes on the dummy driver, `Required test
coverage of 100% reached`.
- [ ] **Step 4:** `uv run pytest` — both drivers, no differing frame, coverage 100%.
- [ ] **Step 5:** `uv run pytest --dummy-only --no-cov -k "jsonl.gz"` and
`uv run pytest --dummy-only --no-cov tests/world/test_golden_traces.py tests/replay/test_golden_replays.py tests/replay/test_bundled_demos.py`
— every golden replay, golden trace and bundled demo passes.
- [ ] **Step 6:** `git diff <base>..HEAD --stat -- '*.jsonl.gz'` prints nothing; every removed test
line in `git diff <base>..HEAD -- tests/ src/apps/bitmappy/tests/ | grep '^-[^-]'` is one a task
lists (about 200); `grep -rnw '__instances__\|__instance__\|_INTERNAL_POSTS\|_unhandled_event_types' src tests`
prints nothing; `test_the_engine_never_reads_a_view` passes.

- [ ] **Step 7: The performance gate (the owner, 2026-10-28; design from review I-9)**

The base and the branch are measured on the same machine, the same day, interleaved, so drift
between sessions (heat, power, background load) hits both alike. Three measurements:

*Setup.* `<base>` is the plan-corrections commit, the last before Task 1's code (its hash is in
the ledger, `.superpowers/sdd/2026-10-27-engine-context-2-engine-state/progress.md`). With
`$PERFORMANCE` a scratch directory outside the repository:
```bash
git -C /Users/terry/Dropbox/dev.glitchygames/glitchygames-engine-context-2 worktree add --detach "$PERFORMANCE/base-tree" <base>
cp tests/benchmarks/test_engine_context_benchmarks.py "$PERFORMANCE/base-tree/tests/benchmarks/"
(cd "$PERFORMANCE/base-tree" && uv sync --all-extras --all-groups --all-packages)
```
The benchmark file (created in this step, below) uses only what exists at `<base>` for its
per-call benchmarks, so it runs in both trees. The scratch worktree is removed at the end
(`git worktree remove "$PERFORMANCE/base-tree"`).

*(a) Every golden and bundled demo, A B A B A B.* For `i` in 1, 2, 3, in that order:
```bash
(cd "$PERFORMANCE/base-tree" && uv run glitchygames measure --force --allow-dirty --rows-directory "$PERFORMANCE/rows/base-$i")
uv run glitchygames measure --force --allow-dirty --rows-directory "$PERFORMANCE/rows/branch-$i"
```
(`--allow-dirty`: the rows are trial rows in a scratch directory, never the ledger; the base tree
holds the copied benchmark file, the branch may hold the owner's uncommitted note.) Each row file
names its recording and holds `summary.p50_processing_seconds` and
`summary.p99_processing_seconds` (`RunSummary`, `src/glitchygames/recording_history.py:276`).
**Noise rule:** for each recording and each of p50 and p99, the base's run-to-run noise is the
spread of its three runs; the branch regresses when the **median of its three runs exceeds the
largest of the base's three by more than 0.2 ms**, the report tool's own "smaller changes are
timer noise" minimum (`DEFAULT_MINIMUM_CHANGE_SECONDS`, `src/glitchygames/recording_metrics.py:75`,
`--minimum-ms 0.2`). The command that applies it:
```bash
uv run python -I -c '
import json, statistics, sys
from pathlib import Path
root = Path(sys.argv[1]); margin = 0.0002; failures = []
def runs(side):
    found = {}
    for index in (1, 2, 3):
        for row_path in sorted((root / "rows" / f"{side}-{index}").glob("*.json")):
            row = json.loads(row_path.read_text())
            found.setdefault(row["recording"], []).append(row["summary"])
    return found
base, branch = runs("base"), runs("branch")
for recording in sorted(set(base) ^ set(branch)):
    failures.append(f"{recording}: measured on one side only")
for recording in sorted(set(base) & set(branch)):
    base_runs, branch_runs = base[recording], branch[recording]
    if len(base_runs) != 3 or len(branch_runs) != 3 or None in base_runs or None in branch_runs:
        failures.append(f"{recording}: not three measured runs on each side")
        continue
    for field in ("p50_processing_seconds", "p99_processing_seconds"):
        branch_median = statistics.median(run[field] for run in branch_runs)
        base_largest = max(run[field] for run in base_runs)
        print(f"{recording} {field}: base max {base_largest * 1000:.3f} ms, branch median {branch_median * 1000:.3f} ms")
        if branch_median > base_largest + margin:
            failures.append(f"{recording} {field}")
if failures:
    print("REGRESSED:", failures)
else:
    print("gate (a) passed")
sys.exit(1 if failures else 0)
' "$PERFORMANCE"
```
Expected: `gate (a) passed`, exit 0. Gate (a) compares p50 and p99 only, not #116's mean and 5%
slice summaries (the controller's ruling, 2026-10-29; `plans/future-work.md` notes it could).

*(b) Behaviour unchanged.* For each recording (from a row file), rebaseline a scratch copy on the
base, then that copy on the branch, and read the report with the tool's thresholds passed
explicitly and enough spans to list every one:
```bash
(cd "$PERFORMANCE/base-tree" && uv run <console_script> --replay-trace <recording> --headless --rebaseline "$PERFORMANCE/behaviour/base/<name>.jsonl.gz")
uv run <console_script> --replay-trace "$PERFORMANCE/behaviour/base/<name>.jsonl.gz" --headless --rebaseline "$PERFORMANCE/behaviour/branch/<name>.jsonl.gz"
uv run glitchygames report "$PERFORMANCE/behaviour/branch/<name>.jsonl.gz" --threshold 25 --minimum-ms 0.2 --spans 100000
```
Expected: for the base-run-to-branch-run pair, no frame whose content hash differs. The copies keep
the recording's own history, so the report also lists the recorded run against the base run (made
on another machine or commit): ignore that pair (review M-12). Its timing spans are informational;
(a) and (c) are the timing gate.

*(c) Per call and per read, micro-benchmarks* in a new file,
`tests/benchmarks/test_engine_context_benchmarks.py` (benchmarks run once, untimed, in the normal
suite under xdist, as `tests/benchmarks/test_benchmarks.py`'s do):
- per call (exist at `<base>` too): `test_process_events_per_call` (an engine from
  `tests/events/test_events_integration.py`'s `start_engine_with_scene`, one scripted batch of a
  KEYDOWN and an AUDIODEVICEADDED per call) and `test_run_frame_step_per_call` (a bare
  `SceneManager` with an active `Scene`, unpaced). Run A B three times, each branch run compared
  with the base run just before it:
  ```bash
  (cd "$PERFORMANCE/base-tree" && uv run pytest tests/benchmarks/test_engine_context_benchmarks.py -k per_call -o addopts= -p no:xdist --benchmark-only --benchmark-storage="file://$PERFORMANCE/benchmarks" --benchmark-save="base-$i")
  uv run pytest tests/benchmarks/test_engine_context_benchmarks.py -k per_call -o addopts= -p no:xdist --benchmark-only --benchmark-storage="file://$PERFORMANCE/benchmarks" --benchmark-save="branch-$i" --benchmark-compare="<the base-$i run's id>" --benchmark-compare-fail=median:5%
  ```
  **Noise rule:** a per-call regression is real when **all three** paired comparisons fail
  (`median:5%`); one or two failing are noise, reported, and the three pairs are run once more.
- per read (the branch only): `test_reading_an_engine_attribute` (`engine.options`, for the
  record), `test_reading_a_slot` (`current_context().value(slot=...)`, the reference),
  `test_reading_a_class_view` (`GameEngine.OPTIONS` with an engine running) and
  `test_reading_the_current_engine` (`current_engine()`), saved as JSON. **The gate is a ratio
  to the slot read taken in the same run** (review re-check N-3), not an absolute limit: heat,
  load or another machine move every read alike, so a same-run ratio holds where an absolute
  limit with about 20% headroom (220 ns against a measured ~181 ns) would fail on noise:
  ```bash
  uv run pytest tests/benchmarks/test_engine_context_benchmarks.py -k reading -o addopts= -p no:xdist --benchmark-only --benchmark-json="$PERFORMANCE/benchmarks/reads.json"
  uv run python -I -c '
  import json, sys
  medians = {bench["name"]: bench["stats"]["median"] for bench in json.load(open(sys.argv[1]))["benchmarks"]}
  slot = medians["test_reading_a_slot"]
  ratio_limits = {"test_reading_a_class_view": 4.0, "test_reading_the_current_engine": 2.0}  # == READ_RATIO_LIMITS
  for name, median in sorted(medians.items()):
      print(f"{name}: {median * 1e9:.0f} ns ({median / slot:.2f} x the slot read)")
  failures = [f"{name}: {medians[name] / slot:.2f} x > {limit} x" for name, limit in ratio_limits.items() if medians[name] > limit * slot]
  print("\n".join(failures) or "gate (c) reads passed"); sys.exit(1 if failures else 0)
  ' "$PERFORMANCE/benchmarks/reads.json"
  ```
  The script's two ratios equal `READ_RATIO_LIMITS` in the benchmark module (Task 16 Step 2b);
  change neither alone. When the gate passes, write its medians (attribute, slot, view,
  `current_engine()`) into the "Performance" table of `docs/architecture/engine_context.md` with
  this machine and date, run `test_the_documented_read_costs_stay_within_the_gate`, and commit the
  page with the benchmark file.
  The ratios are about twice the expected ones (a class view about 181 / 75, so 2.4 x a slot read;
  `current_engine()` about 1 x): they catch a view implemented badly (a dictionary scan, a copy,
  an extra lookup per read), not ordinary jitter. The benchmark file imports
  `current_engine`, the views and the slots **inside** the per-read test functions, because the
  file is copied into the `<base>` tree, where those names do not exist and a top-level import
  would fail collection even with `-k per_call` (re-check m-4; ruff allows it: `PLC0415` is
  ignored, `pyproject.toml:453`).

**On a regression:** never relax the gate, its margins or its limits. Profile the regressed
recording on both trees (`uv run <console_script> --replay-trace <recording> --headless
--profile`), find the hot read (a view, a slot read or `current_engine()` on a per-frame or
per-event path), move it onto the object or into a local in the task that owns it, and rerun this
task from Step 1. The benchmark file is committed with this step (message `Engine context:
benchmarks of the engine's per-call and per-read costs`, with the trailer).

- [ ] **Step 8: Report** the commits (`git log --oneline <base>..HEAD`), the summaries of Steps
3–5, gate (a)'s table (per recording, p50 and p99: the base's largest and the branch's median),
gate (b)'s behaviour result, gate (c)'s three paired per-call comparisons and the per-read
medians against their limits.

---

## Bugs noticed while writing this plan (not fixed here; for BUGS.md)

- `src/glitchygames/api/routes/health.py:26`: `pygame_initialized: bool =
  RendererService.pygame_initialized` is a default argument, read once at import (False), so the
  health check reports pygame uninitialized after the renderer started it.
- `docs/architecture/engine_context.md`'s slot table omits `glitchygames.game_frames.clock`, a slot
  with an isolation check (`check_game_frame_clock`); Task 16 adds it.
- `FontManager.RENDER_CACHE` (`font_manager.py:138`) is declared and never used;
  `BitmappySprite.DEFAULT_SURFACE` (`bitmappy_sprite.py:55`) is made at import and read nowhere.
  Possibly dead; left in place (the guard lists the surface under R12).
