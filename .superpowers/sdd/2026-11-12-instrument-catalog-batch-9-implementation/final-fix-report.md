# Batch 9 final review fixes

Status: DONE. All seven findings fixed.

- Alias order: penny whistle, jula jula, julu julu, syrinx, siyotanka in aliases.py, the test parameters and docstring.
- Headers: aliases.py and flute_sound_alikes.py name plans/data/instrument-audit/batch-9.tsv; NEW_FLUTE_NAMES uses batch 7's wording.
- APPROXIMATING_NAMES comment and docstring now say "imitate or omit".
- PORTAMENTO_NAMES: added singing bird box and whistling vessel (the sheet's only portamento waits besides slide whistle); comment says exact names, adds the Slide_whistle URL. build/batch-9-form-check.py copy updated (uncommitted, gitignored).
- Sheet: alias_of cleared on the 6 "its target" WAIT rows.
- #79: garklein, alias-order and header minors removed; 30-earlier-flutes wording rephrased; two Follow-ups added.

Checks: pytest 1598 passed, no warnings; ruff clean; basedpyright 0 errors; lint-docs successful; form check `bad: []`; code check `matches 146 rows`.
