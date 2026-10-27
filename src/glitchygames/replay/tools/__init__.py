"""The engine's recording, replay and measurement tools, described once (``registry.TOOLS``).

Each tool is reachable two ways, both built from that one table so their names and options
never drift apart:

- as a flag on any game's own command line (``mygame --replay-trace run.jsonl.gz``), added by
  ``GameEngine.args`` (``registry.add_game_flags``);
- as a subcommand of the ``glitchygames`` command (``glitchygames replay-trace run.jsonl.gz``,
  glitchygames/replay/tools/command.py), which starts the game as a child process
  (glitchygames/replay/tools/children.py) whenever the game has to run.

Nothing is imported here, so importing one tool module loads only what it needs. Importing any
of them never imports pytest.
"""
