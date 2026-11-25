# Feature Flags, and Lucid Circuit's Switch

- **Date:** 2026-11-24
- **Status:** Built (2026-11-24), all four tasks, on the branch below. Not merged yet.
- **Master plan:** [lucid-circuit.md](lucid-circuit.md). The mirror's own plan is
  [lucid-circuit-4b-mirror.md](lucid-circuit-4b-mirror.md).
- **Branch:** `feature/lucid-circuit-switch`

## What the owner decided (2026-11-24)

- `--lucid-circuit` / `--no-lucid-circuit` is the AI's control switch, on by default for now.
- The AI switches go: `--ai` and `--no-ai` are removed, and Lucid Circuit replaces them.
- `AI_FEATURES_ENABLED` is replaced by feature flags, at least one, for Lucid Circuit.
- The mirror process's marker is `--lucid-circuit-mirror`. It is not built here.
- Agreed: flags declared once, parents win, read at use, local to the run, logged at start.
- Bitmappy's AI stays off in headless runs and replays.

## The problem

`--ai` gates one place, `ai_link.create_link`, with `--headless` and the browser checked beside it.
Bitmappy's AI reads `constants.AI_FEATURES_ENABLED`, set from `sys.platform` as the module loads, so
`--no-ai` does not reach it, and its tests reload or patch modules to change it.

## The design

`src/glitchygames/feature_flags.py`:

- **`FeatureFlag`**, a frozen pydantic model: `name` (kebab case), `summary` (the help text),
  `default`, `parent` (a flag's name or None), `availability` (a function giving None or the reason
  it cannot be on here), `recorded` (False: local to the run; True is refused until a flag needs it).
- **`FEATURE_FLAGS`**, a read-only mapping of the declared flags. Today: `lucid-circuit`, default on,
  no parent, unavailable in the browser (it cannot start processes).
- **`FlagState`**, frozen: `on`, and `reason` when off (turned off on the command line, its parent
  is off, or unavailable and why).
- **`flag_state(name=...)`** answers from the running game's engine context (a `ContextSlot`), and
  raises for an undeclared name.
- **The command line:** one `--NAME` / `--no-NAME` per flag, generated from the declaration.

A flag says whether a feature is wanted and possible. Whether a run may connect is still
`create_link`'s: never with `--headless`, never in a replay, and only where the service is installed.

| Where | Before | After |
|---|---|---|
| `ai_link.create_link` | `options['ai']`, `sys.platform` | the flag's state; `--headless` stays its own |
| Bitmappy's `AIManager` | `AI_FEATURES_ENABLED` | the flag's state at `setup()` and at each request, its reason shown |
| Engine arguments | `--ai` | generated |
| `REPLAY_LOCAL_OPTIONS` | `ai` | keeps `ai`, gains `lucid_circuit` |

**Old recordings.** 14 of the 26 committed recordings hold `ai: True`. A replay keeps ignoring it, and
ignores `lucid_circuit` the same way: a recording never switches the AI on or off. None is re-recorded.

**Removed outright:** `--ai` and `--no-ai` end as unknown arguments, with no alias.

## The guard

A source scan, beside the project's others (`tests/test_unseeded_randomness_guard.py` is the model),
that fails when engine or member code:

- assigns a module- or class-level name ending `_ENABLED`, or starting `ENABLE_` or `FEATURE_`,
  outside `feature_flags.py` (a private name too; two bits of `BallSpawnMode`, which switch nothing
  by themselves, are allowed by name);
- calls `flag_state` at import (module or class level, a decorator or a default argument).

It is a test, not another kind of flag: it keeps the next feature from bringing back a constant.

## Tasks

1. **The flags and their option.** Behaviours: the default; on and off from the command line; an
   undeclared name raises; a child is off with its parent, with that reason; an unavailable flag is
   off with its reason whatever was asked; two engine contexts hold different states (an isolation
   check); a declaration with an unknown parent or a cycle is refused; a clash with a tool's or a
   game's argument is refused as the engine already does; the start log's options block shows it.
2. **The link and the replay.** Behaviours: `--no-lucid-circuit` makes no link, no host and no
   console; on is as `--ai` is today, `--headless` and the browser included; a recording holding
   `ai: True` or `lucid_circuit: True` connects nothing, and one holding `False` blocks nothing;
   `--ai` and `--no-ai` are refused; every committed recording still verifies.
3. **Bitmappy.** Behaviours: `--no-lucid-circuit` starts no AI worker and every request says why; the
   browser's reason is the one shown there. Its AI also stays off with `--headless` and in a replay,
   as the link does (the owner, 2026-11-24; measured: a headless replay started a real worker), each
   with its reason; a live windowed run with Lucid Circuit on is unchanged. Its tests set the flag instead of
   reloading or patching modules. `AI_FEATURES_ENABLED` and its message constant are gone.
4. **The guard and the docs.** The scan with plants for each form; `docs/architecture/argument_system.md`,
   `CLAUDE.md` (within its line limit), and the Lucid Circuit plans' live instructions (history
   keeps the old names).

## Not built here

- The mirror, its marker and any child flag: they arrive with their features. Proposed, not decided:
  AI-written code and events sent back into the game default to off even when Lucid Circuit is on.
- Remote or percentage rollouts, and flags kept per player. Callers would not change.
