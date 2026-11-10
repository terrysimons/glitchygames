# Friction instruments (proposed new family `friction_instruments`)

## Summary
- New missing found: 16 rows in the TSV (musical saw, daxophone, nail violin, waterphone and cristal baschet were already in `new_family_proposed.tsv`; verrophone, glass harp and glass harmonica/singing bowl are moves; the others are new: glass harp, terpodion, clavicylinder, euphon, adiaphonon, triolin, livika, glass violin). Genuinely NEW to both catalog and proposed list: glass harp (not in catalog; verrophone is in merged_missing), terpodion, clavicylinder, euphon, adiaphonon, triolin, livika, glass violin = 8. Plus ekola/tortoise-shell friction vessel as boundary notes.
- Proposed entries rejected or corrected: 3 (nail violin inventor wrong; waterphone H-S "unnumbered" wrong; cristal baschet "133.?" wrong, it is a set of friction sticks per Wikipedia).
- Aliases: 6.
- Range fixes/checks: verrophone and glass harp VERIFIED; the rest UNVERIFIED.
- Moves from the catalog (catalog_names.txt): `glass harmonica` (tuned percussion), `singing bowl` (tuned percussion; the rubbed mode only; keep a struck bowl elsewhere). No other catalog entries belong here. `cuica` stays in drums (friction DRUM, H-S 23 boundary note). `jal tarang` (struck water bowls, 111) stays in tuned percussion. `harmonica`, `chromatic harmonica` are free reeds, not friction (name collision with glass harmonica; the catalog "harmonica" entries must never be reassigned).
- Moves from merged_missing / proposed files: musical saw, daxophone, nail violin, waterphone, cristal baschet (new_family_proposed.tsv); verrophone (tuned_percussion proposal) and cristal baschet (electrophones proposal) are duplicates of these rows.

## Catalog moves (explicit)
- glass harmonica: tuned percussion -> friction instruments
- singing bowl: tuned percussion -> friction instruments, renamed `rubbed singing bowl` (or keep `singing bowl` and add a struck variant in tuned percussion; owner choice)
- verrophone (proposed in tuned percussion) -> friction instruments
- pyrophone: NOT friction (internal combustion in tubes); stays organs/other. The Musical glasses page only links it (https://en.wikipedia.org/wiki/Musical_glasses).
- cloud chamber bowls (Partch, struck): stay tuned percussion.
- marimbaphone (Deagan): struck bars that can be rotated and BOWED (https://en.wikipedia.org/wiki/Marimbaphone); the Wikipedia H-S list puts it under 132 friction plaques (https://en.wikipedia.org/wiki/List_of_idiophones_by_Hornbostel%E2%80%93Sachs_number), but the instrument is primarily mallet-played. Keep in tuned percussion, cross-reference.

## New missing instruments
name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls
musical saw	Musical saw	friction instruments	worldwide (US/Europe)	A3	A5	UNVERIFIED pitch; width-dependent: ~2 oct typical, bass saw ~2.5 oct, some 3-4 oct (VERIFIED span, https://en.wikipedia.org/wiki/Musical_saw)	bowed S-curved blade, ethereal voice/theremin-like, continuous glissando and vibrato	continuous pitch via glide, sine-ish plus harmonics through formant-ish filter, slow bow-attack envelope; vibrato LFO; no friction noise model (add faint noise source)	https://en.wikipedia.org/wiki/Musical_saw
daxophone	Daxophone	friction instruments	Germany (Hans Reichel, 1980s)	C2	C6	UNVERIFIED (Wikipedia gives no range; tongue length/dax position set pitch)	bowed wooden tongue stopped by dax block; squeaky voice/animal-like glissandi	continuous pitch, voice-like formant sweeps; needs strong filter automation, not available as per-note envelope	https://en.wikipedia.org/wiki/Daxophone
nail violin	Nail violin	friction instruments	Germany (Johann Wilde, 1740; NOT Wilhelm Bauer)	C5	C7	UNVERIFIED (page: chromatic, no range)	bowed iron nails on semicircular board; sweet bell-like thin tone	bowed-attack sine-plus-partials, high register; easy	https://en.wikipedia.org/wiki/Nail_violin
waterphone	Waterphone	friction instruments	USA (Richard Waters)	unpitched	unpitched	VERIFIED inharmonic/atonal (page gives no range)	bowed or superball-struck bronze rods on steel bowl; eerie inharmonic wail, water-bend	inharmonic partial set + slow pitch wobble from water; tune detuned sources; needs bending glide	https://en.wikipedia.org/wiki/Waterphone
cristal baschet	Cristal Baschet	friction instruments	France (Bernard and Francois Baschet, 1952)	C3	C8	UNVERIFIED; 3.5 to 6 octaves, concert 5 octaves, 56 chromatic rods (VERIFIED span only)	wet-finger rubbed glass rods driving metal rods and fibreglass cones; glass-harmonica-like swell, very ethereal	slow attack/release, sine with shimmer, long swell; easy-moderate	https://en.wikipedia.org/wiki/Cristal_Baschet
glass harmonica	Glass harmonica (armonica)	friction instruments	USA (Benjamin Franklin, 1761-62)	G3	C6	UNVERIFIED (Franklin: 37 bowls, no pitch range on page; Schmittbaur extended range; modern ~3.5 oct/43 notes per maker)	wet fingers on rotating glass bowls; pure, floating, slow-onset sine-like tone, dominant 1-4 kHz	MOVE from tuned percussion; slow attack sine with weak 2nd partial; easy	https://en.wikipedia.org/wiki/Glass_harmonica
glass harp	Glass harp (musical glasses)	friction instruments	England (Richard Pockrich, 1741; older origins)	G3	E6	VERIFIED 18th-c compass G3-E6 (some C4-C6) per https://en.wikipedia.org/wiki/Glass_harp	wet finger around goblet rims, water-tuned; pure sine-like	same as glass harmonica; can also be struck (short ring)	https://en.wikipedia.org/wiki/Glass_harp
verrophone	Verrophone	friction instruments	Germany (Sascha Reckert, 1983)	G3	F6	VERIFIED G3-F6, extendable to ~D7 with wine glasses (https://en.wikipedia.org/wiki/Verrophone)	rubbed glass tubes, resonant chords; sine-like, long sustain	glass-harp-like; can be struck with padded mallet	https://en.wikipedia.org/wiki/Verrophone
rubbed singing bowl	Singing bowl (rubbed)	friction instruments	Himalayan region/Nepal/N. India (modern use)	unpitched	unpitched	UNVERIFIED (page: no pitch range; bowls ~few cm to ~1 m)	wand rubbed around rim; sustained bowl tone with beating	MOVE catalog 'singing bowl'; slow swell inharmonic partials with beating (two detuned sources)	https://en.wikipedia.org/wiki/Singing_bowl
terpodion	Terpodion	friction instruments	Germany (J. D. Buschmann, 1816)	F1	F7	UNVERIFIED (page: ~5.5 octaves by 1817, caption F1-f4; inconsistent)	keyboard pressing friction rods onto a rotating rosin-coated wooden cylinder; sustained cello-organ-like bowed tone	bowed-organ patch, sustained saw-ish tone; moderate	https://en.wikipedia.org/wiki/Terpodion
clavicylinder	Clavicylinder	friction instruments	Germany (Ernst Chladni, 1799)	unpitched	unpitched	UNVERIFIED (no range stated)	keyboard friction on rotating glass cylinder; glass-harmonica-like with per-note swell (archive: nested glass bowls with pads)	same as glass harmonica	https://en.wikipedia.org/wiki/Clavicylinder
euphon	Euphon (Chladni)	friction instruments	Germany (Ernst Chladni, 1791)	unpitched	unpitched	UNVERIFIED (no range stated)	stroked glass rods; direct ancestor of Cristal Baschet	same as cristal baschet; minor variant, maybe merge	https://en.wikipedia.org/wiki/Clavicylinder
adiaphonon	Adiaphonon	friction instruments	Vienna (Franz Schuster, 1818-19)	F1	F7	VERIFIED F1-F7 as quoted on nail violin page, secondary source only	bowed steel rods in keyboard; sustained pure bell-ish bowed tone	bowed-bar patch; easy	https://en.wikipedia.org/wiki/Nail_violin
triolin	Triolin	friction instruments	USA (Hal Rammel, 1991)	unpitched	unpitched	UNVERIFIED (no range)	bowed upright rods on triangular resonator, twisted while played	nail-violin patch with warble; niche	https://en.wikipedia.org/wiki/Triolin
livika	Livika (lounuat)	friction instruments	New Ireland, Papua New Guinea	unpitched	unpitched	UNVERIFIED (three tongues, shrill; no range)	resin-coated hands stroke three carved tongues; shrill bird/spirit squeal	short noisy squeal with resonance; easy	https://en.wikipedia.org/wiki/Livika
glass violin	Glass violin	friction instruments	Japan (Hario Glass Company, 2000s)	G3	E7	UNVERIFIED (assumed violin-like; page does not give range)	bowed glass body; glassy tone	low-confidence, memory-adjacent; bowed glass, a bowed-strings-like patch; consider omitting	https://en.wikipedia.org/wiki/Glass_instrument

## Rejected or corrected proposed entries
- nail violin: the proposal's origin "Wilhelm Bauer" is wrong. Wikipedia: Johann Wilde, German violinist, 1740; H-S 131.2 (sets of friction sticks); tone "sweet bell-like". https://en.wikipedia.org/wiki/Nail_violin
- nail violin H-S: other listings (Sachs-Hornbostel PDF) place it at 131.21; labelling of .21/.22 differs between mirrors. UNVERIFIED subnumber. https://www.culturalequity.org/sites/default/files/2020-08/Sachs-Hornbostel%20Classification%20of%20Musical%20Instruments.pdf
- musical saw: H-S 132.1 confirmed; MIMO revision gives 151 (metal sheet). https://en.wikipedia.org/wiki/Musical_saw
- waterphone: "unnumbered" is fine, but Wikipedia says it is both friction and struck, inharmonic and atonal; the sources call it "tuned" in the lead yet atonal in the infobox (internal inconsistency). Four sizes: Standard 7 in, Whaler 12 in, Bass 14 in, MegaBass 16 in. https://en.wikipedia.org/wiki/Waterphone. Not a bowl with water tuning pitch in a scale, so `unpitched` stays.
- cristal baschet: proposal H-S "133.?" is wrong. Wikipedia files it under friction idiophones, sets of sticks (131); range 3.5-6 octaves, 56 rods. https://en.wikipedia.org/wiki/Cristal_Baschet
- suikinkutsu: proposal put it in `water idiophones`; not friction. Goes to environmental instruments (see missing_categories.md).
- musical glasses/glass harp: the earlier audit did not list it at all.

## Aliases
- armonica, glass armonica, hydrocrystalophone, bowl organ, glass harmonium -> glass harmonica (https://en.wikipedia.org/wiki/Glass_harmonica; search result confirmed hydrocrystalophone)
- musical glasses, singing glasses, angelic organ, verrillon, ghost fiddle -> glass harp (https://en.wikipedia.org/wiki/Musical_glasses). Note "verrillon" is also used for glass harmonica in the H-S listing (confusing).
- singing saw -> musical saw
- violino harmonico (Senal, c. 1780-90, nail violin with sympathetic strings) -> nail violin variant (https://en.wikipedia.org/wiki/Nail_violin)
- Stockspiel / Melkharmonica (19th c., wooden rods, rosined gloves) -> a separate friction-stick instrument (low confidence; one-sentence mention only on the Nail violin page; not added)
- melodion (friction sense) -> terpodion per https://en.wikipedia.org/wiki/Friction_idiophone ("terpodion/melodion"); do NOT confuse with the reed melodeon.
- lounuat -> livika (https://en.wikipedia.org/wiki/Livika)
- Cristal Baschet "euphone (modern)" -> cristal baschet (Glass instrument page calls it a newer Cristal Baschet); Chladni's euphon is the 1791 ancestor and kept separate.

## Range checks
- verrophone G3-F6 (to ~D7): VERIFIED https://en.wikipedia.org/wiki/Verrophone
- glass harp G3-E6 (18th c.), some C4-C6: VERIFIED https://en.wikipedia.org/wiki/Glass_harp
- musical saw proposed A3-A5: UNVERIFIED pitch; span ~2 octaves typical, 2.5 bass, 3-4 for some: VERIFIED span.
- daxophone proposed C2-C6: UNVERIFIED; Wikipedia states no range. https://en.wikipedia.org/wiki/Daxophone
- nail violin proposed C5-C7: UNVERIFIED; Wikipedia states none.
- glass harmonica: Franklin 37 bowls; page gives no note names; G3-C6 in the TSV is my estimate (memory). Search found K. 617 range not stated in any retrieved source. A modern maker quotes 3.5 octaves/43 notes (parlancechamberconcerts / glasharmonika.at search hits, not fetched).
- cristal baschet: span 3.5 to 6 octaves, concert 5, 56 rods VERIFIED; lowest/highest note names UNVERIFIED.
- terpodion: 5.5 octaves (1817) vs F1-f4 as "six octaves" caption: inconsistent (F1-f4 is 3 octaves if f4 = F4; likely typos); UNVERIFIED. The TSV row F1-F7 is a stretch; treat as wide.
- adiaphonon F1-F7: VERIFIED only as stated on nail violin page.
- waterphone, singing bowl, livika, ekola: unpitched; no source gives pitch.

## Gaps you could not close
- Ekola (Ovambo, 2-4 calabashes with notched palm rib rubbed by sticks; https://en.wikipedia.org/wiki/Ekola): Wikipedia calls it a friction idiophone, but a notched stick scraped is a RASP (H-S 112.1). H-S number not on page. Boundary: put it in friction family only if the owner follows Wikipedia; otherwise scraped idiophones/rasps.
- Turtle-shell friction vessel (Latin America, resin-smeared shell, rubbed; Sachs-Hornbostel PDF 133.1) and Bora kjuumuhe (Colombia): from search snippets only, not fetched. UNVERIFIED.
- Grand Harmonicon (Francis Hopkinson Smith, 1825): Wikipedia describes it as a form of glass harp; I recall it as struck glasses (memory). Not added.
- Glass instruments in Wikipedia's Glass instrument page also list glass marimba, glasschord (Met: object 89.4.1202, a KEYBOARD instrument with hammers striking glass bars: struck, not friction). Not friction. https://www.metmuseum.org/art/collection/search/501781 (Met glass harmonica, Crosby Brown 1889, 18th c., possibly German).
- Keyboard-friction glass harmonicas of the early 19th century (Klavierglasharmonika; felt pads dried out so players had to rest) mentioned at https://greifenberger-institut.de/en/wissensvermittlung/besaitete-tasteninstrumente/kuriosa/klavierglasharmonika.php: no model named; not added.
- Hooke's musical cylinder, Uchatius, Harmonichord (Kaufmann): searched, nothing confirmed. https://epub.ub.uni-muenchen.de/81743/ (German, not read).
- Baschet others (Baschet Bass Cristal, Le Sifflant Tournant, Voice Leaf 1965, Signal Sonor 1968, Educational Instrumentarium 14 structures): not confirmed to be friction; skipped. Sources: https://interlude.hk/the-baschet-brothers-and-their-instruments/ (snippet)
- Turntable listed under 132 on Friction idiophone page: not an instrument for the catalog; I declined to add.
- Triolin is a one-person art instrument (Hal Rammel, 1991), probably too niche; add only if the owner wants maker-instruments.
- Bowed vibraphone / bowed crotales: a technique on a struck idiophone (H-S gives no separate bowed number per search snippets); recommend articulation of vibraphone, NOT a friction entry. Marimbaphone is the only instrument built for both.
- Friction DRUMS (cuica, lion's roar, H-S 23): kept in drums, boundary only. Not researched beyond the brief.
- MIMO and Grove were not queried directly (MIMO appears only via Wikipedia's mention of the 151 reclassification and a vocabulary.mimo-international.com hit in a search result).
- Waterphone variants beyond four sizes (Hyperstellar for Evelyn Glennie, double chamber, deep bass): mentioned; not added as separate rows.
- 20th-century experimental: Harry Bertoia/Partch friction bowls, Hal Rammel's others, Bernard Baschet: partially searched, none confirmed.
