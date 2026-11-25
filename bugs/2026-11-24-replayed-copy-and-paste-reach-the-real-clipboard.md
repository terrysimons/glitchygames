# A Replayed Copy or Paste Reaches the Real Clipboard, and Pasted Text Is Not Recorded

- **Description**: In a replay, a recorded Ctrl+C or Ctrl+X overwrites the player's clipboard and a
  recorded Ctrl+V pastes whatever it holds today. The text a paste gave live is not in the
  recording, so a game that shows or acts on it can diverge.
- **Reproduction**: Reproduced 2026-11-24 at `5006bcb6` (macOS arm64, Python 3.15.1, pygame-ce
  2.5.8, SDL 2.32.10) in child processes on the dummy drivers, with `HOME`, the sound cache root and
  the AI install root in a scratch folder.
  - pyperclip was replaced by a stand-in module that logs its calls, so the real clipboard was never
    touched. Bitmappy's bundled demo with a click in a text box, `a`, Ctrl+C and Ctrl+V added to its
    events at frames 700-717, replayed with `--headless --replay-trace`: the stand-in logged `copy
    'a'` and `paste`. The replay still matched 900 frames: the box's text is not compared.
  - The game is a throwaway scene of one 4x4 sprite that quits itself at frame 90 and moves the
    sprite when the branch is taken; it is recorded with `--headless --no-ai --record-trace
    run.jsonl.gz` and replayed with `--headless --replay-trace run.jsonl.gz`. At frame 10 it moves
    by the length of `system_clipboard().paste()`. Recorded with `AAA` held, replayed with `B`: exit
    1, `Replay diverged at frame 9: sprite Mover#0 rect expected [3, 0, 4, 4], got [1, 0, 4, 4]`.
- **Status**: Open
- **Priority**: High. A replay destroys what the player had copied, and can bring private text into
  a replay (and into the mirror).
- **Root Cause**: `system_clipboard()` is not a door: `PyperclipClipboard`
  (`src/glitchygames/clipboard.py:91`, `:106`) is chosen by `create_clipboard`
  (`src/glitchygames/clipboard.py:111`) whatever the active sources are. Callers:
  `src/glitchygames/ui/text_widgets.py:1378` (copy), 1385 (paste), 1406 (cut).
- **Test gap**: The harness installs an `InProcessClipboard`, so every replay test is isolated and
  none could see it; `tests/test_engine_doors.py` watches time, datetime and pygame input modules,
  not pyperclip.
- **Solution**: Not chosen. Options, all unproven:
  - A clipboard door: live answers recorded per paste, replay answers from them, copies go nowhere.
  - Short of recording: a replay uses `InProcessClipboard` (no player text touched; pastes of other
    programs' text still diverge).
- **Known limits**: The old recordings hold no paste text. Whether the AI may see recorded clipboard
  text is a privacy decision not taken.
- **Sweep**: Covered: every `system_clipboard` caller in `src/`
  (`src/glitchygames/ui/text_widgets.py`'s three; `src/glitchygames/ai_console.py`, which is not
  built in a replay). `pygame.scrap` is never initialised. Not covered: the browser's clipboard
  (`browser/browser_clipboard.py`).
- **Related**: [No real
  stimulus](../plans/lucid-circuit-4b-mirror.md#no-real-stimulus-the-owner-2026-11-24) in the
  mirror's plan.
- **Reporter**: The mirror game's hardware inventory, the coordinator
- **Date Reported**: 2026-11-24
- **Files**: `src/glitchygames/clipboard.py`, `src/glitchygames/ui/text_widgets.py`
