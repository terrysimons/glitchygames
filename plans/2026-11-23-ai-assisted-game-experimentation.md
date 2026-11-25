# GlitchyGames: AI-assisted game experimentation

**Status:** direction and design constraints (the owner, 2026-11-23). Nothing here is built. The
next step is the first-pass architecture report (below); no implementation starts before the
owner has read it and agreed a first increment.

**Branch:** `docs/spare-credits-exploration-plan` (a plan only).

**Related:** the lighting plan's AI-steerable stages
([2026-11-23-engine-lighting.md](2026-11-23-engine-lighting.md), section 5.9: named strategies and
layered parameters an AI layer can read and set, with provenance) is the first engine feature
already shaped for this direction; [2026-11-17-sprite-generation-in-the-ai-service.md](2026-11-17-sprite-generation-in-the-ai-service.md)
is the AI service's current scope.

## Purpose

GlitchyGames should evolve toward an environment in which AI can help investigate, understand,
and experiment with game behavior, not simply generate code or act as an autonomous player.

The central idea is to make the game observable and replayable enough that an AI-assisted
workflow can form hypotheses, run controlled experiments, compare outcomes, and help a developer
decide which changes are worth applying.

Treat this as a direction and a set of design constraints, not as a mandate to build every
capability immediately. First understand what the project already does and preserve the useful
architecture that exists.

## Instructions before changing anything

1. Inspect the repository, its documentation, current architecture, and existing replay
   implementation.
2. Identify the current three-process architecture and the responsibilities and communication
   paths of each process.
3. Trace how the authoritative live game runs, how state is recorded, and how replay works today.
4. Identify existing boundaries, interfaces, data formats, and operational constraints that a
   future experimentation workflow could reuse.
5. Summarize what exists, what is already possible, and what is missing before proposing
   implementation changes.
6. Do not assume that a concept described in this document is already implemented.
7. Do not replace, redesign, or refactor working systems merely to make the architecture
   resemble a speculative ideal.

If an implementation decision depends on missing information or would materially alter the
architecture, explain the trade-off and ask before proceeding.

### Where to start reading (pointers, not findings)

These are the places the repository's own docs name for the topics above. They are starting
points for the report; nothing in this list is verified here, and the report must confirm or
correct each one from the code.

| Topic | Starting points |
|---|---|
| Live game, frame loop | `src/glitchygames/engine/__init__.py` (GameEngine), `src/glitchygames/scenes/__init__.py` (SceneManager), docs/architecture/playback/how-a-frame-runs.md |
| Game Host (outer game around every live run) | `src/glitchygames/host.py` (`HostSources`, `GameHost.run_async`) |
| Recording and replay | `sources.py`, `live_sources.py`, `recording.py`, `replay/` (`replay/driver.py`'s docstring: modes and exit codes), `randomness.py`, `clock.py`; docs/architecture/gameplay_replay.md, docs/architecture/playback/ (recording-file.md, speeds-and-timing.md, testing.md) |
| What a recording compares | `tracing.py` (`sample_scene_frame`: per-frame sprite id, rect, visible; not pixels), `replay/audit.py` |
| Several games in one process | `src/glitchygames/engine_context.py`, docs/architecture/engine_context.md, `src/glitchygames/inner_game.py` |
| The local AI service (a separate process) | `services/ai-service/`, `src/glitchygames/ai_link.py`, `ai_host.py`, `ai_console.py` (read-only console; `/sprite` adds a recorded spawn event), `events/sprite_spawn.py`, `ansible/ai_service.yml` |
| Tools over recordings | `src/glitchygames/replay/tools/registry.py` (`TOOLS`), `uv run glitchygames --help` |

Which three processes the owner means is itself a question for the report: name each with
evidence from the code, rather than inferring it from this table.

## Core vision

The long-term workflow should support a scientific-method loop:

1. **Observe:** inspect what happened in a real game session using recorded state, events, logs,
   and replay.
2. **Investigate:** ask questions about behavior, identify patterns, and locate relevant systems
   or causal factors.
3. **Hypothesize:** formulate a specific explanation or proposed change that could produce a
   desired effect.
4. **Experiment:** test the hypothesis in a controlled way, ideally without disrupting the
   authoritative live game.
5. **Evaluate:** compare the experiment with the original behavior and determine whether the
   evidence supports the hypothesis.
6. **Apply:** when the developer chooses, turn a validated experiment into a deliberate change to
   the actual game.

The AI should help the developer move through this loop. It should not silently turn an
observation into a code change or treat an experimental result as permission to modify the live
game.

## Preserve the distinction between live play and experimentation

The live game remains authoritative.

- Normal gameplay must continue to work independently of AI experimentation.
- Experiments should not unexpectedly change the player's live session.
- Experimental state and results should be distinguishable from authoritative game state.
- Applying a change to the real game should be an explicit, reviewable step.
- A failed, interrupted, or abandoned experiment must not corrupt the live game or its replay
  data.

Keep the separation clear in both architecture and user-facing explanations.

## Existing architecture: understand before extending

The project already has a three-process architecture and a replay system. These are important
foundations, not incidental implementation details.

Document the actual responsibilities of the three processes, how they communicate, what state
each owns, and which process is authoritative. Do not infer these details from process names
alone; verify them in the code.

In particular, investigate:

- Which process owns the live simulation and authoritative state.
- Which process records, stores, or serves replay information.
- Which process handles orchestration, tools, interfaces, or other supporting work.
- How messages and state move between processes.
- Whether process boundaries already provide isolation that experiments can use.
- What happens when a process restarts, falls behind, or becomes unavailable.

Prefer extending existing interfaces and responsibilities over adding another process or
introducing a parallel architecture without a demonstrated need.

## Replay as a foundation

Replay is more than a playback feature. It can become the basis for reproducible investigation.

Understand the current replay guarantees before relying on them. Determine whether replay
captures inputs, events, snapshots, random seeds, timing, state transitions, or some combination.
Identify what can be reproduced exactly and what is only approximate.

Potential future uses include:

- Reconstructing the sequence of events that led to an outcome.
- Inspecting the game state at a particular point in time.
- Re-running a session to reproduce a bug or interesting behavior.
- Comparing a baseline run with a modified or experimental run.
- Branching an experiment from a known point, if the current model safely supports it.
- Preserving the provenance of an experiment: its starting state, parameters, changes, and
  results.

Do not claim deterministic replay unless the implementation demonstrates it. If replay has
limitations, document them clearly and design experiments around the guarantees that actually
exist.

## Shadow simulation and isolated experiments

A promising direction is to use recorded state or replay data to support experiments away from
the live game.

A shadow or experimental simulation could allow a proposed change to be tested without affecting
the player-facing session. This might eventually include alternative parameters, AI policies, game
rules, or other controlled variations.

Treat this as a capability to investigate, not an assumption that a complete shadow-simulation
system must be built now.

Before implementing it, determine:

- Whether the simulation can be instantiated independently.
- Whether a replay can provide a valid starting point.
- Which state must be copied, reconstructed, or shared.
- Whether the experiment can safely diverge from the original run.
- How results can be compared with the baseline.
- What resource and runtime costs the experiment introduces.

Keep the experiment's inputs and outputs explicit so that a result can be understood and
reproduced.

## The role of AI

AI should be an investigative and experimental collaborator.

Useful roles may include:

- Summarizing a replay or a sequence of events.
- Answering questions about what happened and when.
- Finding relevant code paths for an observed behavior.
- Suggesting plausible explanations, while distinguishing evidence from speculation.
- Proposing experiments that isolate one variable at a time.
- Selecting or adjusting experimental parameters within developer-approved bounds.
- Comparing baseline and experimental outcomes.
- Explaining uncertainty, confounding factors, and limitations.
- Preparing a proposed code change after an experiment supports it.

The AI should expose its reasoning in terms of observable evidence, hypotheses, and test results.
It should not present guesses as facts, invent state that was not recorded, or claim causation
from a simple correlation.

Keep developer control over consequential actions. The AI may recommend an experiment or a
change; applying it to the authoritative game remains a separate decision.

## Open-ended and emergent behavior

Do not constrain the vision to a small collection of pre-scripted experiments or a fixed list of
questions.

An important possibility is that useful investigations will emerge from observing the game. The
AI may notice an unexpected pattern, ask a new question, or propose an experiment that was not
anticipated when the system was designed.

The architecture should make such exploration possible where practical:

- Expose meaningful observations and state in discoverable, structured ways.
- Make it possible to formulate experiments from available controls and parameters.
- Preserve enough context to understand how an experiment was configured.
- Support comparing outcomes rather than merely reporting that an experiment ran.
- Avoid hard-coding every future investigative question into the engine.

At the same time, open-ended exploration does not mean unrestricted access to mutate the live
game, execute arbitrary code, or consume unlimited resources. Keep permissions, isolation,
resource limits, and explicit application boundaries.

## Latency and independence

AI requests may be slow, intermittent, or unavailable. The game must not depend on an AI response
to maintain normal gameplay.

- Keep real-time game execution independent of model latency.
- Avoid blocking the main game loop on AI, network, or orchestration work.
- Treat AI analysis and experiments as asynchronous work where appropriate.
- Define what happens when requests time out, fail, or return late.
- Ensure stale results cannot accidentally overwrite newer or authoritative state.
- Keep the system useful when no AI provider is configured or reachable.

Do not optimize for a particular model's response time. The architecture should tolerate a wide
range of latency and throughput.

## Resource management and scheduling

Experiments may compete with the live game and other work for CPU, memory, GPU, storage, and
process capacity.

Investigate the actual resource profile before introducing a scheduler or elaborate
resource-management layer. A future system may need to:

- Bound the number of concurrent experiments.
- Limit CPU, memory, or other resource use.
- Prioritize live gameplay over background experiments.
- Pause, cancel, or resume work safely where feasible.
- Avoid allowing a runaway experiment to destabilize the application.
- Record enough information to explain why an experiment was delayed, limited, or stopped.

Start with the simplest controls that address demonstrated risks. Do not build a generalized
distributed scheduler prematurely.

## Portability and provider independence

Avoid coupling the core game and replay model to one AI provider, model, or hosting environment.

Keep provider-specific integration at a boundary. Prefer stable internal representations for
observations, experiment descriptions, results, and proposed changes.

The system should remain understandable and useful across different development environments and
deployment targets. Do not introduce platform-specific dependencies without a clear reason, and do
not assume that every environment has the same accelerators or services available.

## Experiment design and evaluation

Experiments should be understandable and comparable.

Where practical, each experiment should record:

- The question or hypothesis being tested.
- The baseline replay, state, or scenario used.
- The specific variables or code differences introduced.
- The parameters and configuration used.
- The random seed or other reproducibility information, when applicable.
- The execution environment and relevant version information.
- The observations and metrics collected.
- The result, including failures and incomplete runs.
- The limitations that affect interpretation.

Prefer experiments that change one meaningful factor at a time when the goal is to identify cause
and effect. When multiple factors change, make that explicit.

Do not assume that one successful run proves a general result. Repeated trials, controlled
baselines, and uncertainty may matter depending on the behavior being studied.

## Suggested conceptual modes

These are useful ways to think about the workflow, not necessarily literal product modes or
separate processes:

- **Observe:** inspect a live session or replay without changing it.
- **Investigate:** ask questions and trace evidence into the codebase.
- **Experiment:** run isolated variations against a known scenario or state.
- **Compare:** examine differences between baseline and experimental outcomes.
- **Apply:** prepare and review a change for the authoritative game.

Do not create separate subsystems for each label unless the existing architecture and user
experience demonstrate that this is necessary.

## Repository and implementation guidance

Work incrementally and ground every proposal in the repository.

### First pass: architecture report (the next step)

Before coding, provide a concise report containing:

1. The three processes and their verified responsibilities.
2. The authoritative live-game execution path.
3. The current replay data flow and guarantees.
4. Existing APIs or interfaces that could support observation and experimentation.
5. Current isolation and failure boundaries.
6. Gaps between current capabilities and the vision in this document.
7. The smallest useful next step, with its rationale and risks.

Cite relevant files, classes, functions, and data structures in the report so the developer can
verify the findings.

### Implementation approach

- Prefer small, reversible increments.
- Reuse existing replay and process boundaries where they fit.
- Keep live gameplay behavior unchanged unless a change is explicitly requested.
- Avoid broad refactors, speculative abstractions, and unnecessary dependencies.
- Do not build a large AI agent framework as a prerequisite for basic observability.
- Do not add a new process, message bus, database, scheduler, or provider abstraction merely
  because it might be useful later.
- Make experimental state and authoritative state clearly distinguishable.
- Add tests around any new state transitions, replay guarantees, isolation, and failure handling.
- Document assumptions and known limitations.

If a proposed change would alter process ownership, replay compatibility, persistence formats, or
live-game behavior, stop and explain the impact before proceeding.

### Definition of a good first increment

A good first increment should improve one concrete part of the observe-investigate-experiment loop
while preserving the working game.

Examples of useful first increments might include better replay inspection, a structured way to
query recorded events, or a small reproducible experiment using an existing replay. Choose based on
what the repository already supports; do not assume one of these is automatically the right
starting point.

## What not to do

- Do not redesign the whole engine around a hypothetical future AI workflow.
- Do not replace the existing three-process architecture without evidence that it cannot support
  the goal.
- Do not treat replay as deterministic unless verified.
- Do not allow experimental changes to leak into the authoritative live game.
- Do not block gameplay on model calls or remote services.
- Do not equate an AI-generated explanation with verified evidence.
- Do not hard-code the system around a single model or provider.
- Do not build speculative scheduling, orchestration, or agent infrastructure before it is needed.
- Do not make unrelated performance or gameplay changes.
- Do not commit, publish, deploy, or send changes anywhere unless explicitly asked.

## Expected collaboration style

Think like a careful engineer helping build an experimental scientific instrument.

First establish what the system can already observe and reproduce. Then identify the smallest
missing capability that would enable a meaningful experiment. Explain the trade-offs, implement
only the agreed scope, and validate the result.

Keep a clear distinction between:

- What the repository currently does.
- What the system could support with modest extensions.
- What is only a longer-term possibility.
- What has actually been implemented and tested.

The goal is not to build an elaborate AI architecture for its own sake. The goal is to make
GlitchyGames increasingly observable, reproducible, and experimentally useful while keeping the
game itself reliable and under developer control.
