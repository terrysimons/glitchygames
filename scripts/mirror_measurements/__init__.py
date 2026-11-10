r"""Measurements for the mirror game (plans/lucid-circuit-4b-mirror.md, step 1), to run again later.

Each measures one risk of the design, every run in a process of its own, from the repository's
root:

- ``clone_speed``: how fast a clone (a headless, uncapped replay) runs every golden replay and
  bundled demo, its start-up, and how far behind the live game it would stay::

      uv run python -m scripts.mirror_measurements.clone_speed --output DIR --repeats 3

- ``live_stream_cost``: the recorder's main-thread work per frame, piece by piece, in a live run on
  the real display, optionally beside a stand-in clone replaying flat out (``clone_loop``)::

      uv run python -m scripts.mirror_measurements.live_stream_cost --game mr_muncher --output DIR
      uv run python -m scripts.mirror_measurements.live_stream_cost --game mr_muncher \
          --output DIR --clone-load mr-muncher

- ``churn``: collector pauses against slow frames, Python allocations, Surface-making calls and
  each sprite class's construction, each in its own run::

      uv run python -m scripts.mirror_measurements.churn --output DIR

- ``state_size``: each frame's whole state as the AI's tools read it, with no sprite cap::

      uv run python -m scripts.mirror_measurements.state_size --output DIR

Each writes JSON per run into DIR and prints a summary. The results of 2026-11-08 are in the
plan's step 1.
"""
