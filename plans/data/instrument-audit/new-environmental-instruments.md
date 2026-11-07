# Audit: proposed new family "environmental instruments" (slug environmental_instruments)

Sources fetched this session (WebFetch/WebSearch, 20+ calls): Wikipedia pages Aeolian harp, Wind chime, Sea Organ, Wave Organ, Suikinkutsu, Shishi-odoshi, Great Stalacpipe Organ, Hydraulophone, Pyrophone, Pigeon whistle, Blackpool High Tide Organ, Sound sculpture; plus searches on Singing Ringing Tree, Zadar chords, aeolian/Chinese kites, pigeon whistles, suikinkutsu acoustics, H-S numbers. Anything not tied to a URL is marked (memory) or UNVERIFIED.

## Summary

- Verdict: DO NOT create the family. Recommend dissolving it and reassigning each entry (table below). Only about 3 entries (aeolian harp, wind chimes, hydraulophone) are real, reproducible instruments with a defined pitch set; the rest are one-off sited artworks or garden fixtures.
- New missing found: 4 (wind harp monumental stay as variant note only; see TSV: aeolian harp, wind chimes (tuned), sea organ voice, pigeon whistle). Counted only entries I'd actually add: 5 rows in TSV including hydraulophone, pyrophone.
- Proposed entries rejected as instruments: 7 (shishi-odoshi, Singing Ringing Tree, Wave Organ SF, Blackpool High Tide Organ, Comb of the Wind, symphonic house, Great Stalacpipe Organ as a separate family member; each kept at most as a "voice" under an existing family or dropped).
- Aliases: 5. Range fixes/corrections: 4.

## The case for and against the family

Against (stronger):
1. The family's own definition ("sound without a player") is a deployment context, not an acoustic mechanism. Every member has a home in H-S: aeolian harp is 314.122 per the Wikipedia H-S list (https://en.wikipedia.org/wiki/List_of_musical_instruments_by_Hornbostel%E2%80%93Sachs_number:_314.122; the missing_categories.md guess of "31 wind-excited" and "free aerophone" is wrong), wind chimes are percussion idiophones (https://en.wikipedia.org/wiki/Wind_chime), sea organs are aerophones (pipes), stalacpipe organ is a struck lithophone.
2. A game voice is a timbre. Whether the wind or a finger drives a chime does not change the timbre; the engine would model them identically to the tuned-percussion entry. A "no player" distinction is a note-triggering policy, not a voice.
3. Most members cannot be a voice: Wave Organ SF has 25 PVC pipes and no tuning given (https://en.wikipedia.org/wiki/Wave_Organ); Sea Organ tuning only in blogs; Blackpool High Tide Organ was removed late 2021/early 2022 (https://en.wikipedia.org/wiki/Blackpool_High_Tide_Organ); shishi-odoshi is not described as an instrument (https://en.wikipedia.org/wiki/Shishi-odoshi); Sound sculpture page does not classify any named work as an instrument (https://en.wikipedia.org/wiki/Sound_sculpture).
4. Count: honest total is about 6 voices, below any sensible family minimum (other families are 15 to 50).

For (weaker):
1. "Sustained, un-struck, swelling gust timbres" (aeolian harp, sea organ, singing ringing tree, hydraulophone) share a distinctive envelope: no attack, amplitude driven by a slowly varying random source. A small "ambient / generative drone" pad group could be useful to a game soundtrack.
2. Hydraulophone, per its own page, has no H-S slot (infobox "NaN", Mann puts it in a separate category; https://en.wikipedia.org/wiki/Hydraulophone), so no existing family fits cleanly.
3. If the owner wants "every instrument known to man", site-bound ones are sometimes cited in instrument lists (oddmusic gallery, Wikipedia "Hydraulophones, tide organs").

Net: if a home is insisted on, put the 3-4 pad-like voices into `organs` or `flutes`, not a new family. Real playable instruments: aeolian harp (reproducible, standard household build ~1 m box, 10-12 strings, https://en.wikipedia.org/wiki/Aeolian_harp), wind chimes, hydraulophone (commercial, sold by Splashtones; concert model 45 jets), pyrophone (replicas exist; Kastner patent 1874; https://en.wikipedia.org/wiki/Pyrophone), pigeon whistles (hand-made products, https://en.wikipedia.org/wiki/Pigeon_whistle). One-off artworks/installations (not voices): Wave Organ (SF, 25 pipes), Sea Organ Zadar (35 pipes), Blackpool High Tide Organ (18 pipes, gone), Singing Ringing Tree (Burnley, 2006; clone in Texas 2017), Great Stalacpipe Organ (single cave, 37 stalactites, 1956-59), Comb of the Wind, Cloud harp, monumental wind harps (Negrar, Exploratorium, South San Francisco). Suikinkutsu is a repeatable garden construction (many exist) but is a fixture, borderline.

## New missing instruments

name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls
aeolian harp	Aeolian harp	plucked strings (proposed home; H-S 314.122 per Wikipedia list)	Ancient (China, Ethiopia, Greece, India, Indonesia, Melanesia); Kircher described 1650/1673	unpitched (harmonics only)	unpitched (harmonics only)	UNVERIFIED (no range in source; harmonics: 3rd, octave, 12th partials)	no attack, swells and fades with wind, only overtones sound, fundamental absent; pentatonic tuning common	needs slow random-LFO amplitude and crossfade between partials of one string; additive partials 3,4,6 with noise-driven gain; fits oscillator set but needs LFO/random modulation of gain	https://en.wikipedia.org/wiki/Aeolian_harp ; https://en.wikipedia.org/wiki/List_of_musical_instruments_by_Hornbostel%E2%80%93Sachs_number:_314.122
wind chimes	Wind chimes	tuned percussion	Rome (tintinnabula), China (feng-ling c.1100 CE), Japan (furin, Edo)	A1	A3	VERIFIED for the example set only (a1 to a3 eight-tone set on the Wikipedia page); real chimes vary, UNVERIFIED as a general range. merged_missing says C5-C8 which contradicts this source; treat as per-set, not intrinsic	struck tube/rod by clapper, inharmonic spectrum, fundamental emphasized when struck near centre and hung at ~2/9 length; pentatonic/tetratonic	inharmonic partials plus long decay: doable; wind randomness is a note-trigger policy (random scheduler), not a voice	https://en.wikipedia.org/wiki/Wind_chime
hydraulophone	Hydraulophone	flutes (nearest; or organs); owner decision	Steve Mann, term 2005, patent 2011 (merged_missing); page gives no dates, UNVERIFIED	A (12-jet diatonic; octave valves shift -2/+1 octaves)	about E, 1.5 octaves above A (12-jet); concert 45-jet about 3.5 octaves A to E	VERIFIED jet counts and A..E span (page gives note letters not octave numbers; absolute octave UNVERIFIED)	sustained tone while jet blocked; siren-disk, reed or fipple variants; WaterHammer variant percussive piano-like decay	siren-disk variant = pulse train with harmonics, easy; water noise needs filtered noise layer; H-S "NaN", Mann separate category	https://en.wikipedia.org/wiki/Hydraulophone
pyrophone	Pyrophone (fire organ)	organs	Georges Kastner, patent 1874, shown 1878 Paris	unpitched (depends on tube)	unpitched (depends on tube)	UNVERIFIED (no range in source)	small detonations in glass tubes at tube resonance; flame height changes or stops tone; hydrogen/propane; resembles calliope	buzzy pulse train at tube resonance (rough saw/pulse plus noise), sharp cutoff; easy	https://en.wikipedia.org/wiki/Pyrophone
pigeon whistle	Pigeon whistle (geling, geshao)	flutes (multi-tone gourd/bamboo whistle)	China (Peking), also Japan, Indonesia per page	unpitched	unpitched	UNVERIFIED (shang, gong, jiao pitches from a 3-slit gourd per a collector, 4 pitches on one Penn Museum gourd; no absolute pitch)	wind through slit/aperture chambers; tubular crisper, gourd deeper; several tones at once; each whistle in a flock tuned differently	2-4 parallel breathy edge-tone oscillators plus Doppler-ish pitch wobble; modest	https://en.wikipedia.org/wiki/Pigeon_whistle ; https://penn.museum/collections/object/202069

## Rejected or corrected proposed entries

- shishi-odoshi: REJECT as instrument. Wikipedia describes a fountain/garden device (bamboo tube tips and knocks a rock), "aesthetic value", not an instrument. Its knock is a single unpitched percussive sample-like event. https://en.wikipedia.org/wiki/Shishi-odoshi
- suikinkutsu: KEEP as an optional single voice in tuned percussion (not a family); it is a "garden ornament and music device". Prior range "C6-C7" is UNVERIFIED and likely invented; page gives no pitch, research indicates bubble size sets pitch and basin resonance amplifies (a 2004 JJAP paper, DOI 10.1143/JJAP.43.6429, has the natural-frequency formula; not read). https://en.wikipedia.org/wiki/Suikinkutsu
- Singing Ringing Tree: REJECT as a voice (unique sculpture, 2006, Panopticons/Tonkin Liu; only some pipes sing, tuned by length and underside slits; one source's "320 pipes" uncorroborated). If a voice is wanted, treat as organ-pipe chord pad. https://www.sonicwonders.org/wind-sculptures/ ; https://panopticons.uk.net/singing-ringing-tree
- Wave Organ (SF), Sea Organ (Zadar), Blackpool High Tide Organ, Comb of the Wind: REJECT as separate instruments; one "sea organ" voice in organs at most. Sea Organ: 35 pipes in 7 groups of 5 (travel sources); chord claims conflict (7 chords vs 2 alternating major chords G and C6), so tuning UNVERIFIED (https://weburbanist.com/2015/11/20/sea-organ-concrete-jetty-makes-music-with-crashing-waves/, https://oddmusic.com/gallery/om24550.html). Wave Organ: 25 PVC pipes, rumbles/gurgles/hisses, no tuning. Blackpool: 18 organ pipes, 8 sea-wall pipes, harmonic series in B-flat (Wikipedia), removed. Prior "sea organ 421 aerophone" is plausible but the Wikipedia page gives no H-S number.
- great stalacpipe organ: CORRECT family. Prior "tuned percussion, 111.2, constant dynamic" is consistent with source (solenoid rubber mallets, 37 stalactites, one octave, constant amplified level; https://en.wikipedia.org/wiki/Great_Stalacpipe_Organ). Not environmental: it is a keyboard-operated lithophone. Keep in tuned percussion if wanted; as a voice it is just "stone bell tone". Range given as "one octave" with no start note: UNVERIFIED.
- symphonic house: REJECT (no source, an architecture concept per ODD only).
- aeolian harp H-S: CORRECT "31 (wind-excited)" to 314.122 (box zither). Source: Wikipedia H-S 314.122 list. Not free aerophone.
- wind chimes as "tuned percussion C5-C8 (PL)": CORRECTED, see range checks. Boundary: wind chimes are tuned percussion (suspended tubes/bars struck by clapper), not a new family; the existing mark tree overlaps the sound. Keep wind chimes in tuned percussion.
- missing_categories.md claim "Wave Organ page calls them hydraulophones": partly true. The page lists them among hydraulophones, tide organs and sound sculptures, but a sea organ is air-through-pipes (organ pipes) and not finger-blocked water jets, so Mann's category is not a good fit (my judgment).

## Aliases

- gezi shao -> pigeon whistle. UNVERIFIED spelling: the sources I found give geling/geshao (鸽铃/鸽哨) and shaozi; "gezi shao" and a distinct Dutch pigeon whistle were NOT found. Do not list "Dutch pigeon whistle" as separate.
- geling -> pigeon whistle
- geshao -> pigeon whistle
- fire organ, fire calliope -> pyrophone (https://en.wikipedia.org/wiki/Pyrophone)
- tide organ, sea organ (generic) -> sea organ voice in organs (Wave Organ page lists them together)
- tintinnabulum, feng-ling, furin -> wind chimes (regional names; furin is a glass bell chime, arguably distinct timbre: glass)
- wind harp -> aeolian harp (monumental versions are the same principle at scale)
- fengzheng (Chinese kite) -> not an alias; see Gaps.

## Range checks

- aeolian harp "overtones only (3rd, octave, 12th partials)": VERIFIED (https://en.wikipedia.org/wiki/Aeolian_harp), but no pitch range exists; pitch depends on string tuning.
- wind chimes "roughly C5-C8": CORRECTED/UNVERIFIED. Source example is A1-A3, so both numbers are single-set examples; no universal range. Recommend catalog range set by design choice, not a historical claim.
- hydraulophone "A to about E an octave and a half up; 45-jet about 3.5 octaves": VERIFIED in letters (https://en.wikipedia.org/wiki/Hydraulophone); octave numbers UNVERIFIED.
- suikinkutsu "C6-C7": UNVERIFIED (no source pitch).
- great stalacpipe organ "one octave, 37 stalactites": VERIFIED octave claim and count (37 stalactites, one octave; note 37 stalactites over one octave would be inconsistent with 12 semitones; the source says both, so either stalactites repeat or the count includes extra; flagged as a bug in the first audit/source). UNVERIFIED which.
- pyrophone: no range in source; first audit's "not stated" is accurate.
- sea organ: no range/tuning in Wikipedia; blog sources conflict.

## Gaps you could not close

- Aeolian kites / fengzheng: real in China (whistle or bamboo-tube kites; bamboo tube at tail produces zheng-like tone; windmusik.com bibliography treats "kite bows" and multi-string "fengquin" as aeolian instruments) but sources are hobbyist and etymology unconfirmed. Not a voice to model separately; same as pigeon whistle (wind-driven whistle). https://chinasage.info/kites.htm ; https://windmusik.com/html/soundex.htm
- Dutch pigeon whistle / "gezi shao": not confirmed; may be a conflation of Chinese geshao and Nathaniel Mann's modern whistle (UK).
- Wind harps on buildings: examples named (Negrar ~6 m, Tempest Song NM 7 m+, Exploratorium 8 m, Cape Breton 18 m "fiddle", South San Francisco 28 m) from the Aeolian harp page; pitch content not given. Same voice as aeolian harp.
- Wind-driven tuned pipe installations beyond Singing Ringing Tree (Cloud harp, A Sound Garden, Golden Gate Bridge wind tone) were only seen as names on Sound sculpture page, not read.
- Other possible members not checked: ocean wave "water organs" (hydraulis is a historical hydraulic organ and is distinct; belongs to organs, probably already catalogued), ice/thunder/rain stick (rain stick is a hand-played percussion, not environmental), aeolian bells (wind-activated bells), Kimmo/Taiwanese bamboo wind chimes (memory, unverified).
- H-S number for hydraulophone: page shows "NaN"; no authority number exists.

## Bugs/risks noticed

- missing_categories.md says aeolian harp H-S "31 wind-excited, UNVERIFIED"; Wikipedia H-S list says 314.122. Fix.
- merged_missing lists wind chimes range C5-C8, but source example is A1-A3; ranges in that file for these entries came from memory.
- Stalacpipe: "37 stalactites" and "one octave" together are inconsistent for a chromatic scale (12-13 notes); source gives both without reconciling.
- merged_missing has "hydraulophone -> flutes" and "sea organ -> organs" while missing_categories.md reassigns them to environmental; the two documents conflict.
