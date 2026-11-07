# New family audit: plucked idiophones (slug plucked_idiophones)

## Summary
- New missing instruments found: 38 (jaw harps 21, lamellophones 15, music-box combs 2; "jaw harp", "marimbula" and music box items include moves).
- Moves from existing catalog: 3 (kalimba, mbira, music box from tuned percussion). Moves from proposed lists: 2 (jaw harp from free_reeds_proposed, marimbula from plucked_strings_proposed).
- Proposed entries rejected or corrected: 6 (see below). Aliases: 40+. Range fixes: 2 (jaw harp, marimbula).
- Correction to the brief: the catalog has NO jaw harp. inputs/free_reeds_catalog.tsv and ../catalog_names.txt contain no jaw harp; it exists only in free_reeds_proposed.tsv. So there is nothing to remove from free reeds in the catalog.
- Sources actually fetched: Wikipedia Lamellophone, Jew's harp, Mbira, Kalimba, Likembe, Marimbula, Polyphon, Music box, Musical box, Khomus (returned the temir komuz article), Kubing, Karinding, Mukkuri, Cricri, Kouxian, Gravikord; searches on Met kalimba/lamellophone collection, MIMO H-S vocabulary, Hokema sansula, jew's harp types, Dani pikon, singing bird boxes, Hohner Pianet/Cembalet, 17-key kalimba retail specs, oberton.pro jaw harp tuning. Two fetches failed (Met perspectives page 429; Pikon and Mechanical_music_box 404). Almost no source gives absolute ranges for traditional types, so most ranges are UNVERIFIED rather than guessed.
- Lamellophone and jaw harp Wikipedia pages are mostly name lists; MIMO H-S pages gave only headings (122 comb, 122.11 without resonator, 122.12 with resonator, 122.2 mechanically driven cut-out lamellae).

## New missing instruments

name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls
jaw harp	Jaw harp	plucked idiophones	worldwide (China earliest per Wikipedia)	E1	E3	fundamental VERIFIED as maker stock range (oberton.pro); overtone melody range UNVERIFIED	plucked steel tongue, mouth cavity as resonator; buzzy drone with moving harmonic melody	needs swept band-pass over sawtooth/pulse fundamental to pick partials; closest to pure filter-envelope sweep; no mouth physics	https://en.wikipedia.org/wiki/Jew%27s_harp ; https://www.oberton.pro/notes.htm?lang=en
khomus	Khomus	plucked idiophones	Sakha (Yakutia), Altai, Tuva	UNVERIFIED	UNVERIFIED	UNVERIFIED	heteroglot metal jaw harp, large Siberian type, strong breath and vocal-like overtones	same as jaw harp; add breath noise	https://en.wikipedia.org/wiki/Jew%27s_harp
morsing	Morsing	plucked idiophones	South India	UNVERIFIED	UNVERIFIED	UNVERIFIED	brass/iron heteroglot jaw harp, twangy drone in Carnatic percussion ensembles (role: memory)	jaw harp filter sweep	https://en.wikipedia.org/wiki/Jew%27s_harp ; https://en.wikipedia.org/wiki/Lamellophone
morchang	Morchang	plucked idiophones	Rajasthan	UNVERIFIED	UNVERIFIED	UNVERIFIED	Rajasthani jaw harp, brass/iron/copper/silver; Wikipedia treats morsing as South Indian relative	alias candidate of morsing (see Aliases)	https://en.wikipedia.org/wiki/Jew%27s_harp
murchunga	Murchunga	plucked idiophones	Nepal	UNVERIFIED	UNVERIFIED	UNVERIFIED	brass jaw harp, tongue extends beyond frame giving longer sustain, about 11 cm sample	longer decay than morsing	https://en.wikipedia.org/wiki/Jew%27s_harp ; https://en.wikipedia.org/wiki/Lamellophone
temir komuz	Temir komuz	plucked idiophones	Kyrgyzstan	UNVERIFIED	UNVERIFIED	about one octave (size dependent) per Wikipedia; absolute pitch UNVERIFIED	iron jaw harp 100-200 mm long, 2-7 mm wide, melodic	jaw harp filter sweep	https://en.wikipedia.org/wiki/Khomus
dan moi	Dan moi	plucked idiophones	Vietnam (Hmong, Ede)	UNVERIFIED	UNVERIFIED	UNVERIFIED	idioglot (single-piece) or brass lamella, 121.21; softer than steel types	soft attack, quieter noise bed	https://en.wikipedia.org/wiki/Lamellophone ; https://www.daviddarling.info/encyclopedia_of_music/J/jews_harp.html
kubing	Kubing	plucked idiophones	Philippines	UNVERIFIED	UNVERIFIED	UNVERIFIED	bamboo idioglot jaw harp, intimate quiet courtship instrument; many ethnic names listed in Wikipedia (see Aliases)	low-level sine/triangle with narrow filter; very quiet	https://en.wikipedia.org/wiki/Kubing
karinding	Karinding	plucked idiophones	Sundanese West Java	UNVERIFIED	UNVERIFIED	UNVERIFIED	bamboo or palm-midrib jaw harp struck on its end with a finger; frog-like rhythmic hum	struck not pulled; short percussive attack then filtered drone	https://en.wikipedia.org/wiki/Karinding
mukkuri	Mukkuri	plucked idiophones	Ainu, Japan	UNVERIFIED	UNVERIFIED	UNVERIFIED	bamboo, about 10 cm by 1.5 cm, string-pulled idioglot, plucked idiophone	string-pull attack: abrupt onset	https://en.wikipedia.org/wiki/Mukkuri
kouxian	Kouxian	plucked idiophones	China	UNVERIFIED	UNVERIFIED	modern 3+ reed sets tuned to first tones of minor pentatonic; absolute pitch UNVERIFIED	bamboo or brass, single or multi-lamella 121.222, earliest examples c. 4000 years old (Shaanxi) per Wikipedia	multi-reed: parallel oscillators on pentatonic tones	https://en.wikipedia.org/wiki/Kouxian
angkuoch	Angkuoch	plucked idiophones	Cambodia	UNVERIFIED	UNVERIFIED	UNVERIFIED	long flat bamboo with central hole or round/leaf-shaped metal with bells	may add bell tinkle	https://en.wikipedia.org/wiki/Jew%27s_harp
genggong	Genggong	plucked idiophones	Bali/Indonesia	UNVERIFIED	UNVERIFIED	UNVERIFIED	idioglot jaw harp listed at Lamellophone page; (material palm, memory)	jaw harp filter sweep	https://en.wikipedia.org/wiki/Lamellophone
gogona	Gogona	plucked idiophones	Assam, India	UNVERIFIED	UNVERIFIED	UNVERIFIED	bamboo jaw harp played during Bihu	jaw harp filter sweep	https://en.wikipedia.org/wiki/Jew%27s_harp
binayo	Binayo	plucked idiophones	Nepal and Sikkim (Kiranti)	UNVERIFIED	UNVERIFIED	UNVERIFIED	bamboo, about 6 in by 1 in; blown, not fingertuned	breath noise plus pulse	https://en.wikipedia.org/wiki/Jew%27s_harp
datok	Datok	plucked idiophones	Amis, Taiwan	UNVERIFIED	UNVERIFIED	UNVERIFIED	bamboo, string-joined body, double (or triple) reed, both idioglot and heteroglot recorded; aliases tiw tiw, fijiq	two detuned oscillators for double reed	https://en.wikipedia.org/wiki/Jew%27s_harp
lubuw	Lubuw	plucked idiophones	Atayal, Taiwan	UNVERIFIED	UNVERIFIED	UNVERIFIED	string-pulled multi-reed; men all-bamboo, women bronze reed	multi-reed parallel oscillators	https://en.wikipedia.org/wiki/Jew%27s_harp
pikon	Pikon	plucked idiophones	Dani, Papua (Baliem Valley)	UNVERIFIED	UNVERIFIED	UNVERIFIED	bamboo (or metal) mouth harp, multiple lengths for tones	jaw harp filter sweep	https://www.auralarchipelago.com/auralarchipelago/pikon ; https://en.wikipedia.org/wiki/Karinding
susap	Susap	plucked idiophones	Papua New Guinea	UNVERIFIED	UNVERIFIED	UNVERIFIED	huge bamboo mouth harp mentioned in New Guinea search result (single secondary mention)	low drone	https://tracingpatterns.org/material-culture/mouth-harps-pikon/
isitolotolo	Isitolotolo	plucked idiophones	Xhosa, South Africa	UNVERIFIED	UNVERIFIED	UNVERIFIED	Xhosa jaw harp, name only in Wikipedia	jaw harp filter sweep	https://en.wikipedia.org/wiki/Jew%27s_harp
jaw harp set	Jaw harp set	plucked idiophones	Europe (Scheibler, Koch, Eulenstein, 19th c.)	UNVERIFIED	UNVERIFIED	UNVERIFIED	up to ten jaw harps tuned to different pitches for chromatic sequences (Scheibler 10; Koch 2; Eulenstein 4)	polyphonic set of jaw harp voices	https://en.wikipedia.org/wiki/Jew%27s_harp
mbira dzavadzimu	Mbira dzavadzimu	plucked idiophones	Zimbabwe (Shona)	UNVERIFIED	UNVERIFIED	22-28 keys, three registers; tuning relative only (Wikipedia); absolute pitch UNVERIFIED	plucked keys on hardwood board, often in deze calabash resonator with bottle-cap buzz (buzz: memory)	needs sustained rattle: AM noise ring mixed in	https://en.wikipedia.org/wiki/Mbira
nyunga nyunga	Nyunga nyunga	plucked idiophones	Manicaland, Zimbabwe	UNVERIFIED	UNVERIFIED	15 keys in two rows, no soundboard hole (Wikipedia); pitch UNVERIFIED	bright, thin mbira; model for Hugh Tracey kalimba	as mbira	https://en.wikipedia.org/wiki/Mbira
njari mbira	Njari mbira	plucked idiophones	Masvingo/Makonde, Zimbabwe	UNVERIFIED	UNVERIFIED	30-32 keys; pitch UNVERIFIED	large mbira	as mbira	https://en.wikipedia.org/wiki/Mbira
nhare	Nhare	plucked idiophones	Zimbabwe	UNVERIFIED	UNVERIFIED	23-24 keys; pitch UNVERIFIED	ritual mbira	as mbira	https://en.wikipedia.org/wiki/Mbira
mbira matepe	Mbira matepe	plucked idiophones	Zimbabwe-Mozambique border	UNVERIFIED	UNVERIFIED	26 keys; pitch UNVERIFIED	mbira with heavy buzzing	as mbira	https://en.wikipedia.org/wiki/Mbira
hugh tracey kalimba	Hugh Tracey kalimba	plucked idiophones	South Africa 1950s	UNVERIFIED	UNVERIFIED	diatonic in G alternating right and left (Wikipedia); 15-note alto model chart; pitch UNVERIFIED	westernised mbira nyunga nyunga	clean pluck, no buzz	https://en.wikipedia.org/wiki/Kalimba ; https://en.wikipedia.org/wiki/Mbira
likembe	Likembe	plucked idiophones	DR Congo	UNVERIFIED	UNVERIFIED	8-12 lamellae in V pattern; pitch UNVERIFIED	box resonator, iron tongues, rattle rings and rear soundhole (wow effect by covering)	amplitude-modulate with hand-wow LFO; buzz noise	https://en.wikipedia.org/wiki/Likembe
zanza	Zanza	plucked idiophones	Cameroon (double lamellaphone)	UNVERIFIED	UNVERIFIED	two groups of 7 or 8 tongues (Met objects 89.4.1621, 89.4.2491); pitch UNVERIFIED	double-row lamellaphone	as likembe	https://www.metmuseum.org/art/collection/search/504845 ; WebSearch Met results
cricri	Cricri	plucked idiophones	Papua New Guinea (clack idiophone, H-S 121.1)	UNVERIFIED	UNVERIFIED	UNVERIFIED	single lamella carved into fruit shell (galip nut snapper)	single click-like pluck with shell resonance	https://en.wikipedia.org/wiki/Cricri
agidigbo	Agidigbo	plucked idiophones	Yoruba, Nigeria	UNVERIFIED	UNVERIFIED	UNVERIFIED	large box lamellophone (bass role, memory)	low thumpy pluck	https://en.wikipedia.org/wiki/Lamellophone
prempensua	Prempensua	plucked idiophones	Ghana	UNVERIFIED	UNVERIFIED	UNVERIFIED	bass lamellophone, related to marimbula per Wikipedia	low thumpy pluck	https://en.wikipedia.org/wiki/Marimbula ; https://en.wikipedia.org/wiki/Lamellophone
quisanche	Quisanche	plucked idiophones	Argentina (candombe)	UNVERIFIED	UNVERIFIED	five steel reeds	small steel-tongue lamellophone	few-note pluck	https://en.wikipedia.org/wiki/Lamellophone
marimbula	Marimbula	plucked idiophones	Cuba/Caribbean	UNVERIFIED	UNVERIFIED	proposed E1-E2 UNVERIFIED; modern Schlagwerk MA840 has 8 tongues in F major pentatonic, D to G (octave not stated)	bass box, plucked metal strips on sound-holed wooden box; also marimbol, marimbola, rumba box	low sine with short decay and woody thump; pitch drop minimal	https://en.wikipedia.org/wiki/Marimbula ; https://www.thomannmusic.com/schlagwerk_ma840_marimbula.htm
sansula	Sansula	plucked idiophones	Germany 2001 (Peter Hokema)	A3	E5	UNVERIFIED (vendor lists a c' e' f' a' ... e'' as A minor, 9 tongues; duplicate a' suspect)	round-bodied with membrane/frame; sustaining soft tones	ring with slow decay; slight chorus	https://www.feeltone.com/en/products/sansula-kal-san ; https://www.musik-produktiv.com/se/hokema-sansula-basic-melody-g-dur-440hz.html
electric kalimba	Electric kalimba	plucked idiophones	Congo (Konono No.1), US (Ekalimba, Embira)	UNVERIFIED	UNVERIFIED	UNVERIFIED	pickup-amplified lamellophones, often distorted (Konono)	needs overdrive/waveshaper	https://en.wikipedia.org/wiki/Lamellophone
cylinder music box	Cylinder music box	plucked idiophones	Geneva (Favre-Salomon 1796 comb)	UNVERIFIED	UNVERIFIED	UNVERIFIED (comb tooth counts not found)	pinned cylinder plucks tuned steel comb teeth; evolved from musical snuff boxes and watches	very high near-sine with short ring; fixed fast tempo	https://en.wikipedia.org/wiki/Music_box ; https://en.wikipedia.org/wiki/Musical_box
disc music box	Disc music box	plucked idiophones	Leipzig (Symphonion 1885, Polyphon)	UNVERIFIED	UNVERIFIED	discs 6-24.5 in (Wikipedia); comb range UNVERIFIED	disc plucks star-wheel and comb; single, duplex or twin alternate combs	double comb: two detuned layers	https://en.wikipedia.org/wiki/Polyphon

Notes: "unpitched" is not used; every entry is pitched but traditional tuning is relative or undocumented. Where lowest/highest is UNVERIFIED, do not invent ranges; use the engine's default melodic range until a source is found. Some rows (morchang, datok vs lubuw, karinding) are borderline distinct instruments; morchang is probably an alias (see Aliases) and can be dropped.

## Moves into this family
- kalimba, mbira (tuned percussion catalog): move. Both are 122.1 plucked lamellophones, not struck. Catalog ranges not inspected (catalog files have no range column).
- music box (tuned percussion catalog): move here (comb, 122.x); also cross-reference to mechanical instruments.
- jaw harp (free_reeds_proposed.tsv; NOT in catalog): add here as 121.2 (Wikipedia gives 121.22 heteroglot, 121.221 individual).
- marimbula (plucked_strings_proposed.tsv): add here, 122.1.
- Candidate cross-family move: "reed electric piano" (keyboards catalog; Hohner Pianet F1-F6 61 keys, Cembalet C2-C7 61 keys; plucked/released reeds with pickup per encyclopedia.pub and reverb listings; Wikipedia Lamellophone lists Pianet, Cembalet, Guitaret as electric lamellophones). Owner decision: keep in keyboards (player view) or move (mechanism).
- Stay out: steel tongue drum, hank drum, hapi drum, teponaztli, slit drum (struck, 111.x; Wikipedia Lamellophone lumps some under 122.2 but they are struck), glass harmonica (friction), singing bird box (bellows and whistle, belongs in mechanical instruments, not a plucked idiophone), gravikord (chordophone per Wikipedia).

## Rejected or corrected proposed entries
- jaw harp in free reeds: wrong family. It is 121.2 plucked idiophone, not a free reed (air-driven). Range "E2-C4 fundamental, partial 16" is wrong: tuned harps are made from E1 to E3 (oberton.pro); partial 16 UNVERIFIED. Source: https://en.wikipedia.org/wiki/Jew%27s_harp , https://www.oberton.pro/notes.htm?lang=en
- marimbula in plucked strings: wrong family (122.1 lamellophone, not strings). Range E1-E2 UNVERIFIED.
- ratchet (112.24): not plucked; stays in drums and percussion. Cog and flexible tongue is a rattle, not a lamella sounding by decay.
- steel tongue drum, hank drum, hapi drum: reject for this family (struck, 111.24).
- bamboo marimba (boo): Partch Boo II has tongues but is struck tubes, stays tuned percussion.
- gravikord (not proposed but near): chordophone, harps family, not here (24 nylon strings, G1-E5 left side, C2-D5 right; Wikipedia Gravikord).

## Aliases
- sanza, sansa, zanza (African usage), thumb piano, finger piano, kaffir piano -> mbira (catalog) (Wikipedia Mbira and Lamellophone; "kaffir piano" is an offensive term, do not use as a display name)
- kalimba is the 1950s Hugh Tracey instrument; catalog "kalimba" = the 17 key C4-E6 retail kalimba
- ikembe, dikembe, lukeme, esanji, kisanji, lukembe, malimbe -> likembe
- insimbi -> maduimba (Wikipedia pairs them); both are unspecified, keep as one gap
- kasayi, eleke, oopoochawa: name-only entries in Wikipedia Lamellophone; treat as aliases of likembe/mbira until a source gives construction
- marimbol, marimbola, rumba box, bass box, calimba, lazy bass, jazz jim, church and clap -> marimbula
- Jew's harp, guimbarde, trump, maultrommel, vargan, vargans, drumla, drymba, doromb, brumle, mungiga, munnharpe, munniharppu, dambrelis, parmupill, scacciapensieri, marranzanu, mariolu, angalarruni, musugitarra, tronpa, drumbla, kamus, ozark harp, ağız kopuzu, changu -> jaw harp
- morchang, murchang -> morsing (Rajasthan vs South India spelling; distinct only by region)
- demir khomus, xomus, komys -> khomus; ooz komuz, temir qomuz, gubuz -> temir komuz
- kobing, kolibau, aru-ding, kuribaw, aribao, aroding, kulaing, ulibaw, karombi, yori, karinta, ore-ore mbondu -> kubing (karinta is palm-leaf; arguably distinct)
- tiw tiw, fijiq -> datok
- benggom (Yonggom/Muyu bamboo, PNG) -> pikon-class bamboo jaw harp (Penn Museum object 266278)
- musical box, carillon a musique, snuff box -> cylinder music box; polyphon, symphonion, regina, kalliope, stella, orphenion -> disc music box (Regina/Symphonion/Polyphon are brands; Kalliope/Stella/Orphenion from memory)
- space harp, frankiphone -> same (Wikipedia Lamellophone); gap, not added

## Range checks
- 17-key kalimba (catalog kalimba): C4 to E6 in C major. VERIFIED by retail listings (Sela, Stagg via thomann.co.uk, pitbullaudio.com); 21-key extends below C4 (retail). Hugh Tracey: G diatonic (Wikipedia Kalimba).
- jaw harp: CORRECTED to fundamentals E1 to E3 (oberton.pro).
- marimbula: UNVERIFIED (E1-E2); only modern Schlagwerk MA840 D to G, 8 tongues, F major pentatonic (thomann).
- mbira dzavadzimu, nyunga nyunga, njari, nhare, matepe: key counts VERIFIED (Wikipedia Mbira), pitch UNVERIFIED (tuning is relative; Wikipedia).
- likembe: 8-12 lamellae VERIFIED (Wikipedia Likembe), pitch UNVERIFIED.
- temir komuz: about an octave VERIFIED (Wikipedia Khomus article), absolute UNVERIFIED.
- kouxian: modern 3+ reeds tuned to minor pentatonic (Wikipedia Kouxian).
- sansula: A3-E5 derived from vendor tongue list: UNVERIFIED (vendor data is marketing, list internally inconsistent).
- music box discs: 6 to 24.5 in diameter VERIFIED (Wikipedia Polyphon); comb ranges UNVERIFIED.
- reed electric piano (keyboards): Pianet F1-F6, Cembalet C2-C7: VERIFIED by secondary listings only.

## Modeling notes (engine limits)
- All lamellophones: pluck is a hard, short transient, then a near-sinusoidal ring with an inharmonic overtone shortly after attack (overtone ratio: memory, UNVERIFIED). Doable with an oscillator plus a short noise click plus decay envelope.
- Buzz (mbira bottle caps, likembe rings, deze): needs noise modulated by the note amplitude or ring-mod; engine has noise sources and envelopes so approximate; no real sympathetic buzz.
- Likembe wow: needs an LFO on a filter; check engine has one.
- Jaw harp: needs a swept formant filter to pick partials; best approximation is a sawtooth with envelope-controlled band-pass. Melody by harmonic selection is not true pitch change; requires the filter sweep per note. Without resonant filter sweeps it will sound like a plain buzzy drone.
- Music-box combs: short very high sine plus fast decay; discs have fixed mechanical tempo, so tempo behavior belongs to mechanical instruments.
- Multi-reed (kouxian, lubuw, datok, jaw harp set): sum of detuned oscillators.

## Gaps you could not close
- MIMO and Met instrument-by-instrument tables: no search result opened a per-instrument record other than the Met objects 09.163.6 (nyonganyonga, Mozambique, ca. 1900, Crosby Brown) and 89.4.1621 / 89.4.2491 (Cameroon zanze double lamellaphones).
- Name-only lamellophones: maduimba, insimbi, kasayi, eleke, oopoochawa, ikembe, malimbe, tom (Ethiopia), array mbira, space harp, whale drum, zimbabwean marimba (Wikipedia list), chisanza, njara (Wikipedia, Elisabethville / S. Rhodesia mbira variants). No construction found; added only where sourced as distinct, otherwise left here.
- Electric lamellophones: Embira (Lucinda Ellison), Ekalimba (David Bellinger), Guitaret (Hohner), bass kalimbas (Yuri Landman). Collapsed into "electric kalimba"; Pianet/Cembalet suggested for keyboards.
- Other musical-box comb forms: reed organ box, manivelle, musical watch (Ransonet 1772), singing bird box (automaton). Wikipedia Music_box does not cover them; Singing_bird_box page surfaced in search only.
- Missing sources for: Solomon Islands jaw harp; Mexican/Native American lamellophones (teponaztli is a slit drum, not plucked); European jaw harp ranges; Pacific Oceania beyond PNG; Madagascar (valiha is a zither; no Madagascar lamellophone found); "ikembe" Burundi variants; kora not relevant; Zimbabwean "mbira huru", "mbira mavembe" names (memory only, not added).
- "genggong" and "agidigbo" descriptions are partly memory.
