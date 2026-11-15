# Raspberry Pi Rows From Before numpy 2 Were Never Checked for the Corruption Bug

- **Description**: numpy 1.26.4 on Python 3.14 on Linux ARM64 changed a local array in place once it reached 32,768 8-byte elements (`other = values + 1.0` changed `values`); #153 moved to numpy 2.5.4, which does not. The Raspberry Pi 4's replay rows measured before #153 ran on 1.26.4. Whether any of them measured a corrupted run (wrong numbers, or a replay that took another path) was never checked. Recordings that play the CRT power-on sound crashed outright (`audio/render.py`, `_table_samples`, `IndexError` on index 2048), so the danger is in rows whose runs did not crash
- **Status**: Open (not investigated)
- **Priority**: Low (affects only the Pi's history on the Performance page)
- **Reporter**: Claude, from the numpy 2 work (#153)
- **Date Reported**: 2026-11-14
- **Details**: Ways to check: compare the Pi's last rows before #153 with its first after it, per recording, for frames whose content hash changed (`glitchygames report`), and look for the Pi's rows standing apart from the Mac's before #153 but not after. macOS was not affected on the same versions; Linux x86 was never tested
- **Files**: `quality/replay-ledger/` (the Pi 4's rows before #153)
