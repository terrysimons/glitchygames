# Mechanical instruments (proposed new family `mechanical_instruments`)

## Summary
- New missing instruments found: 16 (rows below, many are alias candidates; only about 9 differ audibly from an existing catalog timbre).
- Proposed entries rejected or moved: 12 moves of proposed/catalog entries into this family (see Moves); 0 rejected outright; duplicate proposals between organs.md and keyboards.md resolved (orchestrion, panharmonicon).
- Aliases: 14.
- Range fixes: none CORRECTED; barrel piano and serinette partly VERIFIED (counts, not pitches). Almost no source gives pitches for automatic instruments; most ranges here are UNVERIFIED.
- Sources actually fetched (28 calls): Wikipedia Player piano, Reproducing piano, Music box, Orchestrion, Polyphon, Serinette, Panharmonicon, Violano-Virtuoso, Componium, Singing bird box, Barrel piano, Musical clock, Photoplayer, Fairground organ, Automaton clock, Mechanical music; mim.org mechanical gallery; searches on MBSI, Speelklok museum, Siegfried's Mechanical Music Cabinet, MIM Phoenix, MIMO/H-S, Hupfeld, Orchestrelle. Not obtained: MBSI own pages (search returned none), MIMO records (not opened), Utrecht PDF (unreadable binary), Wikipedia Flute clock and Phonoliszt-Violina (404).
- Family note: the H-S system marks automatic instruments with a /9 suffix per a Utrecht University chapter (search summary, UNVERIFIED in detail): https://muziekinstrumenten.sites.uu.nl/wp-content/uploads/sites/419/2018/07/Muziekinstrumenten-13-Automatische-muziekinstrumenten.pdf . MIMO's exact sub-codes for automatic instruments were not confirmed.

## Moves into this family
Catalog (../catalog_names.txt):
- music box (tuned percussion) -> mechanical instruments, and also cross-reference plucked idiophones (comb, H-S 122.x per missing_categories.md). A pure comb timbre; hand-plucked lamellophones go to plucked idiophones.
- calliope (organs, catalog line 260) -> NOT moved by me: the steam calliope is keyboard-played, so it is a hand-played organ-type; only automatic roll/cylinder calliopes are mechanical. Recommend keep in organs, owner question 2 in missing_categories.md. If the owner wants a pure "automaton" family, move it.
- carillon (tuned percussion) -> stays: hand-played at a baton keyboard; only the "mechanical carillon" row here is the automatic version.
- toy piano (keyboards) -> stays (hand-played).
Other agents' proposals (decision made here, drop from their files):
- organs.md: barrel organ, street organ, fairground organ, band organ, dance organ, orchestrion, panharmonicon, apollonicon, serinette -> mechanical instruments. street/band/dance organ are aliases of fairground organ (see Aliases). air calliope -> alias of calliope (stays organs).
- keyboards.md: player piano, orchestrion, panharmonicon -> mechanical instruments (orchestrion/panharmonicon appear in BOTH organs.md and keyboards.md: duplicate, keep one here). pianola, reproducing piano -> alias of player piano.
- Not moved: pyrophone (organs or friction, unverified), welte philharmonic organ (organ, roll-played: mechanical; no range).
Rows for barrel organ, fairground organ, orchestrion, panharmonicon, apollonicon, player piano are NOT repeated in the TSV below (organs.md/keyboards.md own their data); they just change family.

## New missing instruments
```tsv
name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls
polyphon	Polyphon (disc music box)	mechanical instruments	Leipzig, Germany (1870 invented; production c.1896)	C4	C7	UNVERIFIED (disc 6 to 24.5 in; tooth count and pitch span not given; memory estimate)	plucked steel comb teeth, bright tinkling, fast decay, brief inharmonic ring; larger models duplex combs	comb pluck = short filtered noise click plus decaying near-sine partials; fine. Disc spacing/clockwork speed wobble can be a slow LFO	https://en.wikipedia.org/wiki/Polyphon
cylinder music box	Cylinder music box	mechanical instruments	Switzerland (from 18th c. musical snuffboxes)	C4	C7	UNVERIFIED (typical 36/72/144 teeth; 96 for a large box; span not given; memory estimate)	pinned cylinder plucks tuned steel comb; same tone as catalog music box	timbre duplicate of catalog music box; keep only if the owner wants the control mechanism, otherwise alias	https://en.wikipedia.org/wiki/Music_box ; https://www.mmdigest.com/Archives/Digests/200203/2002.03.10.01.html
musical snuffbox	Musical snuffbox (carillon a musique)	mechanical instruments	Geneva, Switzerland, 18th c.	C5	C7	UNVERIFIED (memory)	tiny comb in a snuffbox; thin, quiet, very high	same as music box with higher register and lower level; alias candidate	https://en.wikipedia.org/wiki/Music_box
singing bird box	Singing bird box	mechanical instruments	Geneva, 1784/85 (Pierre Jaquet-Droz); Paris (Bontems)	C5	C7	UNVERIFIED (verified only: single variable-pitch piston pipe spanning more than an octave; exact notes not given)	trilling warble from a miniature pipe with a piston; about 15 s per performance (Bontems)	needs a gliding-pitch tone with fast random pitch cams: sine oscillator plus pitch envelope plus tremolo is enough; no samples needed	https://en.wikipedia.org/wiki/Singing_bird_box
serinette	Serinette (bird organ)	mechanical instruments	France, 18th c.	C5	C7	UNVERIFIED (one rank of ten metal pipes at 2 ft pitch verified; notes not given)	piccolo-like thin pipe tone, ten notes only	easy; see Moves (organs proposed it)	https://en.wikipedia.org/wiki/Serinette
flute clock	Flute clock (Floetenuhr)	mechanical instruments	Central Europe, 18th c.	C3	C6	UNVERIFIED (memory; Wikipedia Musical clock page mentions flute clock only in a caption)	small organ in a clock case, pinned barrel, soft flue pipes at the hour	stopped/flue pipe tone; easy; Haydn wrote pieces for it (memory)	https://en.wikipedia.org/wiki/Musical_clock
barrel piano	Barrel piano (street piano)	mechanical instruments	Europe, 19th c.	C2	C6	VERIFIED (40 to 48 non-chromatic notes; Greek laterna 3.5 octaves; no exact pitches)	pinned barrel hammers piano strings, often tuned slightly sharp and jangly; some add triangle, drum, bells	struck-string tone with detune; percussion extras need a second source	https://en.wikipedia.org/wiki/Barrel_piano
laterna	Laterna (rhombia)	mechanical instruments	Greece	C3	F6	UNVERIFIED pitches (3.5 octaves verified, start note not)	Greek variant of barrel piano	alias candidate of barrel piano	https://en.wikipedia.org/wiki/Barrel_piano
nickelodeon	Coin-operated piano (nickelodeon)	mechanical instruments	USA, c.1900-1930 (memory)	A0	C8	UNVERIFIED (memory; roll formats 65 or 88 notes verified for player pianos in general)	player piano with mandolin/ percussion attachments, often tinny	piano plus effect layers; alias of player piano unless attachments modeled	https://en.wikipedia.org/wiki/Player_piano (formats only)
photoplayer	Photoplayer (Fotoplayer, Reproduco)	mechanical instruments	USA, 1910-1928	A0	C8	UNVERIFIED (piano plus percussion; no range given)	automatic piano plus drums, bells and effects (gunshots, sirens, horns) triggered by cow-tail pulls	multi-timbral with effects: beyond 4 sources; model as piano plus one effect source	https://en.wikipedia.org/wiki/Photoplayer
violano virtuoso	Violano-Virtuoso	mechanical instruments	Chicago, Mills Novelty (sold 1911; patented 1912; ended c.1930)	G3	E6	UNVERIFIED (verified: 4 violin strings each with an octave = 64 notes, piano 44 notes; note names derived from violin tuning, memory)	self-playing violin bowed by four celluloid wheels plus a piano	bowed sawtooth with fast filter for wheel noise plus piano; two instruments at once	https://en.wikipedia.org/wiki/Violano-Virtuoso
phonoliszt violina	Hupfeld Phonoliszt-Violina	mechanical instruments	Leipzig, Hupfeld, c.1907-1930	G3	E7	UNVERIFIED (3 violins plus piano; ranges not found)	piano with three automated violins bowed by a rotating circular bow	as violano virtuoso; the Atlas Obscura and MBSI pages confirm the mechanism	https://en.wikipedia.org/wiki/Ludwig_Hupfeld ; https://www.atlasobscura.com/articles/phonoliszt-violin-self-playing-instruments-player-piano-ludwig-hupfeld
orchestrelle	Aeolian Orchestrelle	mechanical instruments	USA, Aeolian Company (1890s-1900s)	C2	C7	UNVERIFIED (58-note model reported; rolls up to 116 note two-manual: not a pitch range)	roll-playing pressure reed organ, rich reedy; Solo Orchestrelle (1906) 14 reeds plus triangle	reed organ tone; easy; free reed, not pipe	https://en.wikipedia.org/wiki/Aeolian_Company ; https://www.pianola.org/history/history_playerorgans.cfm
componium	Componium	mechanical instruments	Amsterdam, D. N. Winkel, 1821	unpitched	unpitched	UNVERIFIED (no range found; sound source not stated beyond automatic organ)	automatic organ that recombines stored passages: two cylinders, random variation	sound is organ; the generative variation is a sequencer, not synth	https://en.wikipedia.org/wiki/Componium
piano melodico	Piano Melodico (cardboard book piano)	mechanical instruments	Bologna, G. Racca, c.1886-1910	unpitched	unpitched	UNVERIFIED (range not found)	street piano read from cardboard books	as barrel piano; alias candidate	https://mbsi.org/manufacturers/page/29/ (via search snippet, not opened)
mechanical carillon	Automatic tower carillon (clock-drum carillon)	mechanical instruments	Low Countries, medieval onward (memory)	C3	C7	UNVERIFIED (memory)	bells struck by pinned drum; Speelklok museum holds a turret clock with carillon	would reuse catalog carillon timbre; family exists only to mark automation; low priority	https://en.wikipedia.org/wiki/Museum_Speelklok (collection list)
```
Region/era sweep (honest): the family is almost entirely European and North American, 1700-1930. Non-Western examples found only: Greek laterna, Japanese singing caged birds (a mid-20th-century Japanese music box at MIM, https://mim.org/galleries/mechanical-music-gallery/), karakuri clocks (Japan, Automaton clock page; automata, not instruments). Modern: Yamaha Disklavier (1987), Steinway Spirio, Bosendorfer SE (https://en.wikipedia.org/wiki/Player_piano): alias of player piano timbre.

## Rejected or corrected proposed entries
- orchestrion (keyboards.md, range "unpitched") and orchestrion (organs.md): duplicate proposals in two files; keep one in this family. Orchestrion is not a single timbre: Kaufmann (Dresden, 1851) combined winds, kettledrums, side drums, cymbals, tambourine, triangle; Welte (1832-1932) paper-roll; MIM's "Apollonia" has pipes, two accordions and a drum set (sources above). Model as a preset, not an instrument.
- panharmonicon (both files): earliest automatic orchestrion, Maelzel 1805, includes cannon and gunfire effects (https://en.wikipedia.org/wiki/Panharmonicon). Same as orchestrion; alias or drop.
- apollonicon (organs.md): Flight & Robson, London, 1817; Wikipedia Orchestrion calls it similar to the Panharmonicon with no contents: alias of orchestrion for timbre. UNVERIFIED as separate instrument.
- player piano range "A0-C8 verified"? The keyboards.md range is memory; the only verified numbers are roll formats of 65 and 88 notes (https://en.wikipedia.org/wiki/Player_piano). 65 notes is NOT a pitch range; 88-note format matches A0-C8 only by inference.
- serinette in organs.md: ten pipes at 2 ft pitch verified, so its "range" is ten notes, not a chromatic range.

## Aliases
- street organ, band organ, dance organ, carousel organ, limonaire -> fairground organ (https://en.wikipedia.org/wiki/Fairground_organ: "band organ" is the US name; limonaire the generic French term)
- bird organ, perroquette (similar barrel organ) -> serinette (https://en.wikipedia.org/wiki/Serinette)
- pianola, reproducing piano, Welte-Mignon, Ampico, Duo-Art, Disklavier -> player piano (timbre is piano; difference is control)
- roller piano, street piano, piano organ(?) -> barrel piano (piano organ UNVERIFIED, not on the Wikipedia page)
- laterna, rhombia -> barrel piano
- musical snuffbox, carillon a musique -> music box
- air calliope, calliaphone -> calliope
- cylinder music box -> music box (timbre)
- symphonion, regina, kalliope, stella -> polyphon / disc music box (makers of the same disc comb type; only Symphonion verified: https://en.wikipedia.org/wiki/Music_box)

## Range checks
- barrel piano 40-48 notes, non-chromatic: VERIFIED count, pitches UNVERIFIED (https://en.wikipedia.org/wiki/Barrel_piano)
- laterna 3.5 octaves: VERIFIED span only
- serinette ten pipes at 2 ft: VERIFIED count, pitches UNVERIFIED
- singing bird box: piston pipe spanning more than an octave: VERIFIED span only
- violano virtuoso: 4 strings x octave = 64 notes, piano 44 notes: VERIFIED counts (https://en.wikipedia.org/wiki/Violano-Virtuoso)
- polyphon: disc 6 to 24.5 in, plectra and star wheels: VERIFIED mechanics, pitches UNVERIFIED (https://en.wikipedia.org/wiki/Polyphon)
- music box tooth counts 36/72/144, 96, 150+: from dealer/auction pages in a search, not Wikipedia; UNVERIFIED as authoritative.
- player piano 65 vs 88 notes: VERIFIED (https://en.wikipedia.org/wiki/Player_piano)
- all other ranges in the TSV: UNVERIFIED (memory).

## Modeling difficulty
- Comb instruments (music box, polyphon, snuffbox): easy; the sound is a decaying high partial set plus a pluck click; add slow clockwork speed drift as an LFO on tempo if tempo is part of the engine.
- Orchestrion, photoplayer, nickelodeon, fairground organ with percussion: multi-timbral; the 4-source limit forces a single combined patch (pipe plus drum noise). Violano/phonoliszt need two voices (bowed plus piano).
- Singing bird: needs fast pitch envelope; feasible.
- The control mechanism (cylinder pins, rolls, books) has no analogue in a synthesized-instrument catalog: the timbres equal existing ones, which is the main reason this family risks being duplicate-heavy. Honest recommendation: ship as a tag on existing instruments plus about 9 distinct timbres (polyphon/music box, singing bird box, serinette, flute clock, barrel piano, photoplayer, violano virtuoso, phonoliszt violina, orchestrelle) unless the owner wants the family.

## Gaps you could not close
- Names without sources: Kaufmann Belloneon and mechanical trumpeter automaton (memory only), Welte Philharmonic organ pitches, Hupfeld Helios/ Pan orchestrions, Seeburg and Wurlitzer nickelodeon models, Chordephon, Harmonipan, mechanical zithers (MIM gallery lists "mechanical zithers" but no names found).
- Non-European traditions: Japanese karakuri-related music boxes, Chinese or Indian automatic instruments, Ottoman clocks with organs (the Markwick Markham 1770 Turkish-market organ clock was seen, https://en.wikipedia.org/wiki/Musical_clock): none confirmed as instrument types.
- Pitch ranges for almost everything: MIMO records were not opened; MBSI manufacturer pages returned in search but were not read.
- Hydraulis (ancient water organ, Mechanical music page) is an organ, not automatic; belongs in organs/environmental.
