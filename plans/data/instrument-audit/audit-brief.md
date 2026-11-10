# Adversarial instrument audit — shared brief

## Context

GlitchyGames is a Python game engine with a synthesized sound engine and an instrument
catalog (431 instruments in 18 families). The owner wants "every musical instrument known to
man" in the catalog. A first audit (five agents, one per Hornbostel–Sachs class) proposed 402
missing instruments. That audit is known to be weak:

- most ranges and timbre descriptions came from the agents' memory, not their sources;
- coverage gaps are known (Korean and Indian idiophones, ~20 drums such as chenda, thavil,
  sabar, kebero, pahu; dolceola, zither-banjo, harp-piano, claviharp; tubulum);
- no agent used museum databases (MIMO https://mimo-international.com, the Met's musical
  instrument collection, the Horniman, the Grove Dictionary of Musical Instruments listings,
  Wikipedia's per-family "List of ..." pages, Hornbostel–Sachs classification lists).

Your job is ADVERSARIAL: assume the catalog plus the proposed list is incomplete and partly
wrong, and prove it. Do not confirm the earlier work; attack it.

## Inputs (all in this directory's `inputs/`)

- `<family>_catalog.tsv`: what the catalog already has in your family (family, name, title).
- `<family>_proposed.tsv`: what the first audit proposed adding (columns: name, source_audit,
  H-S number, origin, family, range, sound, sources).
- `../catalog_names.txt`: the WHOLE catalog (all families), to check that a "missing"
  instrument is not already present elsewhere or under another name.
- `../audit/merged_missing.tsv`: the whole proposed list, all families.

## What to do

1. **Find what is still missing** in your family. Sweep systematically: by region (every
   continent and major tradition — West/Central/East/Southern Africa, Maghreb, Middle East,
   Central Asia, South Asia, Southeast Asia, East Asia incl. Korea/Japan/China/Mongolia/Tibet,
   Oceania, Indigenous Americas, Latin America, Caribbean, Europe by region), by era
   (ancient, medieval, Renaissance, Baroque, 19th-century inventions, 20th-century, modern
   experimental), and by size/register variant (piccolo/soprano/alto/tenor/bass/contrabass
   members of each instrument family). Include odd and obscure named instruments. Use real
   sources (web search, museum databases, Wikipedia list pages) and cite a URL for each.
2. **Attack the proposed list** for your family: entries that do not exist, are the same
   instrument as a catalog entry or another proposed entry under another name (aliases),
   are regional names for one instrument, are in the wrong family, or have wrong ranges.
3. **Verify ranges** for the proposed entries and your new ones against a source where you
   can find one. Mark each range VERIFIED (with URL) or UNVERIFIED.
4. **Flag modeling difficulty**: the engine synthesizes each instrument from up to 4 sources
   (oscillators/noise with envelopes and filters; no samples, no FM yet, no physical
   modeling of sympathetic strings). Note instruments that need something it lacks.

"Every instrument" includes regional variants only when they are distinct instruments
(different construction or sound), not just different local names — list pure synonyms as
aliases instead.

## Naming rules for proposed names

Catalog names are lower-case ASCII words separated by single spaces (no punctuation, no
slashes, no parentheses, no apostrophes, no accents): `alto saxophone`, `lions roar`,
`lutheal`. Give the display title separately if it needs accents or punctuation.

## Output

Write ONE file: `audit2/<family-slug>.md` (path given in your prompt), containing:

1. `## Summary`: counts (new missing found; proposed entries rejected; aliases; range fixes).
2. `## New missing instruments`: a TSV block with columns
   `name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls`
   (lowest/highest as note names like C4, or `unpitched`).
3. `## Rejected or corrected proposed entries`: each with the reason and a source.
4. `## Aliases`: `alias -> canonical name (catalog or proposed)`.
5. `## Range checks`: proposed entries whose ranges you checked, VERIFIED/CORRECTED/UNVERIFIED.
6. `## Gaps you could not close`: what you suspect is missing but could not confirm.

Be honest: anything from memory rather than a source is marked "(memory)". Do not edit any
file other than your output file. Do not touch the git repository. Return to the caller only
a 3-line summary (counts and the output path).
