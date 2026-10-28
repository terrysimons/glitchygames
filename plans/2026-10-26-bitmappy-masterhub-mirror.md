# Bitmappy on the MasterHUB: the canvas on every key and the dial

**Status:** PARKED (2026-10-26): designed with the user; not started. It waited for three things;
two remain:
1. ~~Bitmappy's move to `src/apps/bitmappy/` (`plans/2026-10-26-workspace-packages-4-bitmappy.md`).~~
   Done: merged as #110 (2026-10-26).
2. pymasterhub's upright displays (`../PyMasterHub/plans/2026-10-26-masterhub-upright-displays.md`).
3. A pymasterhub slice, not yet planned, that adds writes under WebHID and a reusable display
   mirror (see Revised direction).

It gets a full task-by-task implementation plan when it starts. Paths assume Bitmappy has moved.

## Revised direction (the user, 2026-10-26)

Two later decisions change parts of the Decisions and Design below. Where they conflict, this
section wins.

- **Put the reusable parts in pymasterhub.** The user: "We should do as much as makes sense in the
  pymasterhub project so we can reuse it in other projects." These move into pymasterhub, so other
  games and tools get them too:
  - the picture → key and dial images, in their fixed boxes with whole-number zoom
  - the latest-frame-wins writer
  - detecting the deck without opening it
  - sending the current picture again after a module is plugged back in

  Bitmappy keeps only what is its own: turning its canvas into a picture (magenta made
  transparent), the `--masterhub` / `--no-masterhub` flags, and calling the pymasterhub mirror.
  The box sizes (64 on a key, 128 on the dial) stay Bitmappy's choice, passed to pymasterhub.
- **The browser is in scope (supersedes decision 6, "Desktop only").** The user: "The lightshow
  example has all of the necessary functionality to wire up the web version", and chose "both":
  - First, a pymasterhub slice adds writes under WebHID: an async write path through the WebHID
    shim. Today every image and lighting write goes through `ModuleReader._run_between_reads`,
    which raises "under WebHID: not yet supported".
  - That slice also adds a web version of the lightshow (`examples/lighting/lightshow.py`), which
    already exercises everything needed: key images, the dial, replugs and batched writes.
  - Then this mirror gains its browser path on top. The browser has no threads, so the
    latest-wins writer must be async there.
  - In the browser the deck is offered only after a user click (WebHID's permission prompt), so
    auto-on becomes "a button or menu item to connect the deck", not detection at startup.

## What it does

When Bitmappy starts with a MasterHUB deck connected, the frame being edited is shown on all
15 key screens of the M4315 and on the M131E dial. It is updated whenever the frame changes. On
exit the screens blank, because pymasterhub restores hardware mode.

## Decisions (the user's, 2026-10-25/26)

1. **On by itself.** Mirroring is on when pymasterhub can be imported *and* a keys module or dial
   is listed (enumeration opens nothing and changes no mode). `--masterhub` forces it on, with a
   warning if that is impossible; `--no-masterhub` forces it off and imports nothing. The flags
   use argparse `BooleanOptionalAction`, where `None` means auto. The auto-on log line names the
   module and serial number being opened, since opening is a write (software mode).
2. **Imported only when needed; private.** pymasterhub is not in any `pyproject.toml` or
   `uv.lock`, because it is a private repository CI cannot fetch. It is imported inside the
   function that runs only when mirroring is wanted. Run it with
   `uv run --with-editable ../PyMasterHub bitmappy`. When it is missing, auto is off with one
   debug line. Because the import isn't declared, deptry needs a DEP001 ignore with a comment
   saying why.
3. **The library does every rotation.** Bitmappy never rotates or remaps anything: pymasterhub's
   `write_image` makes a turned module's picture upright, and `key=` is the viewer's grid
   (pymasterhub upright-displays plan).
4. **Fixed boxes, crisp.** The picture is always **64×64 on each key** (centered on the 72×72
   screen) and **128×128 on the dial** (centered on 240×240, a 56-pixel border, the box that gave
   the best JFIF fidelity on the rig, C-29). These are constants, not options. Other sizes are
   "maybe later" (`plans/future-work.md`). The canvas fits into the box by whole-number zoom
   (pymasterhub `prepare_image(zoom='whole')`), nearest-neighbor, 4:4:4, quality 100. The same
   picture goes to all 15 keys.
5. **Not the Hub.** It uses `open_keys`/`open_dial` directly, not pymasterhub's Slice 6 Hub
   (another agent's work, kept separate). Switching to the Hub later is possible, but not planned.
6. **Desktop only.** pymasterhub can't write images under WebHID yet, and WebHID only offers a
   device after a user click, so in the browser auto is always off.
7. **A deck plugged in after launch** is part of this work, done last, once everything else works
   on the rig. It watches with `pymasterhub.watch`, on the desktop only.

## Design

- **`bitmappy/masterhub_mirror.py`, class `MasterHubMirror`.**
  - `setup()` opens it (or decides not to); `cleanup()` closes it.
  - `update()` hands it the canvas each frame: `canvas.pixels` (a flat RGBA list),
    `pixels_across`, `pixels_tall`.
  - It snapshots the pixels and does nothing when they are unchanged.
- **Picture:** a Pillow RGBA image, with magenta (`MAGENTA_TRANSPARENT`, 255,0,255) made
  transparent and composited on black by `prepare_image`.
- **Writes stay off the frame loop.** `write_image` blocks on HID I/O, and one update is 16
  transfers, so a desktop-only writer thread holds only the newest frame: while you paint, frames
  in between are dropped. The writer thread owns the modules, polls them (their queues are bounded
  and overflow as `ReportsDropped`), and on `ModuleReconnected` sends the current frame again.
- **Errors:**
  - A write can race an unplug (`ShortWriteError`, a `TransportError`) or land in the reconnect
    gap (`UnsupportedOperationError`), as seen on the rig on 2026-10-26. Both are caught and
    logged; the editor keeps running.
  - A deck that is listed but busy (another app holds it; macOS opens devices exclusively): one
    log line, no mirroring.
  - Only the keys or only the dial connected: mirror whichever is there.
- **Tests:**
  - CI has no pymasterhub, and coverage stays at 100%.
  - The detection, open and write seam is tested with a stand-in `pymasterhub` module through
    `monkeypatch.setitem(sys.modules, ...)` (a targeted patch of hardware); no test touches a real
    deck.
  - The pixels-to-picture step and the skip-unchanged step are tested with real Pillow.
  - The missing-package, forced-on, forced-off and browser cases are each tested by their log
    line.
- **On the rig:** the user approves each command before it runs (writes), and runs it with `!`.

## Open questions (ask when this starts)

1. The dial/key box sizes are fixed. Should the canvas be centered when it is smaller than a
   whole-number multiple of the box (a 48×48 canvas is 1× in the 64 box, with an 8-pixel border)?
   That is what `zoom='whole'` does.
2. Is a frame's update rate (latest-wins, no fixed cap) fine on the rig, or should it be capped?
   Measure one full 16-write update first.
