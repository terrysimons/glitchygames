# Flutes audit (adversarial, round 2)

Method note: 19 Wikipedia pages were fetched (Dizi, Contrabass flute, Recorder, Flute, Panpipes, Fujara, Nose flute, Ocarina, Tin whistle, Slide whistle, Daegeum, Ryuteki, Nohkan, Shinobue, Suling, Gemshorn, Aztec death whistle, Hydraulophone; List_of_flutes returned 404). MIMO, the Met and the Horniman were NOT consulted. Rows whose source_urls say "none fetched" come from memory: existence is plausible but unverified, and no range is given for them ("unknown") rather than an invented one. Wikipedia pages mostly give no ranges, so most ranges stay UNVERIFIED.

## Summary

- New missing instruments found: 94 (all listed below; 33 have a fetched Wikipedia page that mentions them, the rest are from memory).
- Proposed entries rejected: 3 (ringflute, clackamore, hydraulophone: wrong family or unverifiable).
- Proposed entries flagged for correction (range, H-S, scope): 7 (aztec death whistle, gemshorn, suling, koauau/nose flute overlap, nguru, sub/double contrabass flute, putorino).
- Aliases: 24 (below).
- Range fixes against sources: 6 (recorder table, gemshorn width, nohkan "over two octaves", sub/double contrabass, tin whistle D5-D7 confirmed, hydraulophone confirmed).

## New missing instruments

name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls
hyperbass flute	Hyperbass flute	flutes	Netherlands (Roosen), modern	unknown	unknown	UNVERIFIED	near-sine sub-bass edge tone with heavy air noise	fundamental below speaker response; rely on 2nd harmonic	https://en.wikipedia.org/wiki/Flute
eb soprano flute	Soprano flute in E-flat	flutes	Europe, 19th c.	Eb4	unknown	DERIVED lowest (minor third above C4 concert flute); highest UNVERIFIED	concert-flute timbre a minor third higher	trivial transposition	https://en.wikipedia.org/wiki/Flute
flute d amour	Flute d'amour (flute in A)	flutes	Europe, 19th c.	unknown	unknown	UNVERIFIED	mellow veiled flute tone	trivial	none fetched; existence from memory
renaissance flute	Renaissance transverse flute	flutes	Europe, 15th-16th c.	unknown	unknown	UNVERIFIED	cylindrical bore, quiet reedy edge tone	sine+odd harmonics+noise	none fetched; existence from memory
classical flute	Classical flute (keyed)	flutes	Europe, c.1750-1830	unknown	unknown	UNVERIFIED	between baroque and Boehm timbre	baroque flute with brighter filter	none fetched; existence from memory
garklein recorder	Garklein (piccolo) recorder	flutes	Europe	C6	unknown	VERIFIED lowest (recorder table); highest UNVERIFIED	thin shrill whistle	near-sine plus slight noise	https://en.wikipedia.org/wiki/Recorder_(musical_instrument)
subgreat bass recorder	Subgreat bass recorder	flutes	Europe, modern	C2	unknown	VERIFIED lowest; highest UNVERIFIED	airy sub-bass whistle	sine+noise, very low	https://en.wikipedia.org/wiki/Recorder_(musical_instrument)
subcontrabass recorder	Subcontrabass recorder	flutes	Europe, modern	F1	unknown	VERIFIED lowest; highest UNVERIFIED	extremely low, mostly air	below practical audibility on small speakers	https://en.wikipedia.org/wiki/Recorder_(musical_instrument)
voice flute	Voice flute (recorder in D)	flutes	Europe, Baroque	D4	unknown	VERIFIED lowest; highest UNVERIFIED	soft recorder tone	same as recorder	https://en.wikipedia.org/wiki/Recorder_(musical_instrument)
sixth flute	Sixth flute (recorder in D)	flutes	Europe, Baroque	D5	unknown	VERIFIED lowest; highest UNVERIFIED	bright recorder tone	same as recorder	https://en.wikipedia.org/wiki/Recorder_(musical_instrument)
flageolet	English flageolet	flutes	England/France	unknown	unknown	UNVERIFIED	sweet thin duct-flute tone	same as recorder	https://en.wikipedia.org/wiki/Tin_whistle
double flageolet	Double flageolet	flutes	England, 19th c.	unknown	unknown	UNVERIFIED	two parallel pipes, beating	two detuned sines	none fetched; existence from memory
bird flageolet	Bird flageolet	flutes	Europe, 18th c.	unknown	unknown	UNVERIFIED	piercing chirp	sine with glide	none fetched; existence from memory
czakan	Csakan	flutes	Austria-Hungary, 19th c.	unknown	unknown	UNVERIFIED	recorder-like walking-stick flute	same as recorder	none fetched; existence from memory
tabor pipe	Tabor pipe (three-hole pipe)	flutes	Europe, medieval	unknown	unknown	UNVERIFIED	bright piping, overblown harmonics	harmonic-series scale	https://en.wikipedia.org/wiki/Fujara
willow flute	Willow flute (seljefloyte)	flutes	Scandinavia	unknown	unknown	UNVERIFIED	overtone flute without finger holes	harmonic-snapping pitch	https://en.wikipedia.org/wiki/Fujara
koncovka	Koncovka	flutes	Slovakia	unknown	unknown	UNVERIFIED	fipple overtone flute without side holes	harmonic snapping	https://en.wikipedia.org/wiki/Fujara
kalyuka	Kalyuka	flutes	Ukraine	unknown	unknown	UNVERIFIED	overtone fipple flute	harmonic snapping	https://en.wikipedia.org/wiki/Fujara
frula	Frula	flutes	Serbia	unknown	unknown	UNVERIFIED	shepherd duct flute	recorder-like	none fetched; existence from memory
dvojnica	Dvojnica (Balkan double flute)	flutes	Balkans	unknown	unknown	UNVERIFIED	two tubes, drone-like second note	two detuned sines	none fetched; existence from memory
sopilka	Sopilka	flutes	Ukraine	unknown	unknown	UNVERIFIED	folk duct flute	recorder-like	none fetched; existence from memory
floyera	Floyera	flutes	Greece	unknown	unknown	UNVERIFIED	long shepherd end-blown	breathy sine	none fetched; existence from memory
tilinca	Tilinca	flutes	Romania	unknown	unknown	UNVERIFIED	open both ends, no holes	harmonic snapping	none fetched; existence from memory
fluier	Fluier	flutes	Romania	unknown	unknown	UNVERIFIED	folk whistle-flute	recorder-like	none fetched; existence from memory
salamuri	Salamuri	flutes	Georgia	unknown	unknown	UNVERIFIED	open-ended overtone flute	sine+noise	none fetched; existence from memory
shvi	Shvi	flutes	Armenia	unknown	unknown	UNVERIFIED	duct whistle	sine	none fetched; existence from memory
blul	Blul	flutes	Armenia	unknown	unknown	UNVERIFIED	breathy shepherd flute	sine+noise	none fetched; existence from memory
dilli kaval	Dilli kaval	flutes	Turkey	unknown	unknown	UNVERIFIED	overtone-friendly breathy kaval	sine+noise	none fetched; existence from memory
kawala	Kawala	flutes	Egypt	unknown	unknown	UNVERIFIED	notched end-blown, ney-like	sine+noise	none fetched; existence from memory
salamiyya	Salamiyya	flutes	Egypt/Levant	unknown	unknown	UNVERIFIED	ney-like folk flute	ney variant	none fetched; existence from memory
shabbaba	Shabbaba	flutes	Levant	unknown	unknown	UNVERIFIED	end-blown folk flute	ney variant	none fetched; existence from memory
gasba	Gasba	flutes	Maghreb	unknown	unknown	UNVERIFIED	cane end-blown, breathy	ney variant	none fetched; existence from memory
washint	Washint	flutes	Ethiopia	unknown	unknown	UNVERIFIED	bamboo end-blown, four holes	sine+noise	none fetched; existence from memory
embilta	Embilta	flutes	Ethiopia	unknown	unknown	UNVERIFIED	single-note end-blown flute played in hocket	one note per instance	none fetched; existence from memory
atenteben	Atenteben	flutes	Ghana	unknown	unknown	UNVERIFIED	bamboo, pentatonic	sine+noise	none fetched; existence from memory
fulani flute	Fulani flute	flutes	West Africa	unknown	unknown	UNVERIFIED	breathy overblown, voice-like	throat hum not modeled	none fetched; existence from memory
sodina	Sodina	flutes	Madagascar	unknown	unknown	UNVERIFIED	bamboo end-blown	sine+noise	none fetched; existence from memory
umtshingo	Umtshingo	flutes	South Africa	unknown	unknown	UNVERIFIED	overtone mouth flute	sine+noise	none fetched; existence from memory
nyanga panpipes	Ngororombe (nyanga)	flutes	Zimbabwe, Malawi	unknown	unknown	UNVERIFIED	stopped pipes, hocketed with percussion	stopped-tube sines, hocket	https://en.wikipedia.org/wiki/Panpipes
tshikona pipes	Tshikona pipes	flutes	Venda, South Africa	unknown	unknown	UNVERIFIED	ensemble of single-note pipes in hocket	one note per instance	none fetched; existence from memory
kagurabue	Kagurabue	flutes	Japan (gagaku)	unknown	unknown	UNVERIFIED	lowest of the three gagaku flutes	transverse flute	https://en.wikipedia.org/wiki/Ryuteki
komabue	Komabue	flutes	Japan (gagaku)	unknown	unknown	UNVERIFIED	highest of the three gagaku flutes	transverse flute	https://en.wikipedia.org/wiki/Ryuteki
hitoyogiri	Hitoyogiri	flutes	Japan	unknown	unknown	UNVERIFIED	one-node end-blown	sine+noise	none fetched; existence from memory
tempuku	Tempuku	flutes	Japan	unknown	unknown	UNVERIFIED	short shakuhachi-like	shakuhachi variant	none fetched; existence from memory
hocchiku	Hocchiku	flutes	Japan	unknown	unknown	UNVERIFIED	thick-walled shakuhachi, deep breathy	more noise	none fetched; existence from memory
junggeum	Junggeum	flutes	Korea	unknown	unknown	UNVERIFIED	medium samjuk flute, no membrane today	sine+noise	https://en.wikipedia.org/wiki/Daegeum
sogeum	Sogeum	flutes	Korea	unknown	unknown	UNVERIFIED	small samjuk flute, no membrane today	sine+noise	https://en.wikipedia.org/wiki/Daegeum
danso	Danso	flutes	Korea	unknown	unknown	UNVERIFIED	end-blown notched flute	xiao-like	https://en.wikipedia.org/wiki/Daegeum
tungso	Tungso	flutes	Korea	unknown	unknown	UNVERIFIED	longer danso	xiao-like	none fetched; existence from memory
qudi	Qudi	flutes	China	unknown	unknown	UNVERIFIED	longer, mellower dizi	dizi, lower pitch; membrane buzz	https://en.wikipedia.org/wiki/Dizi_(instrument)
bangdi	Bangdi	flutes	China	unknown	unknown	UNVERIFIED	higher brighter dizi	dizi, higher pitch; membrane buzz	https://en.wikipedia.org/wiki/Dizi_(instrument)
xun	Xun	flutes	China	unknown	unknown	UNVERIFIED	egg-shaped clay vessel flute, muffled	sine+noise	https://en.wikipedia.org/wiki/Ocarina
chi flute	Chi (ancient transverse flute)	flutes	China	unknown	unknown	UNVERIFIED	ancient transverse flute	transverse flute	none fetched; existence from memory
paixiao	Paixiao	flutes	China	unknown	unknown	UNVERIFIED	Chinese panpipe	stopped-tube sines	https://en.wikipedia.org/wiki/Panpipes
lingbu	Gling bu	flutes	Tibet	unknown	unknown	UNVERIFIED	end-blown flute	ney-like	none fetched; existence from memory
limbe	Limbe	flutes	Mongolia	unknown	unknown	UNVERIFIED	transverse bamboo flute	dizi without membrane	none fetched; existence from memory
tsuur	Tsuur	flutes	Mongolia/Tuva	unknown	unknown	UNVERIFIED	overtone flute	throat singing not modeled	none fetched; existence from memory
sybyzgy	Sybyzgy	flutes	Kazakhstan	unknown	unknown	UNVERIFIED	end-blown overtone flute	sine+noise	none fetched; existence from memory
sao truc	Sao truc	flutes	Vietnam	unknown	unknown	UNVERIFIED	transverse bamboo flute	dizi-like	none fetched; existence from memory
tieu	Tieu	flutes	Vietnam	unknown	unknown	UNVERIFIED	vertical end-blown flute	xiao-like	none fetched; existence from memory
khlui	Khlui	flutes	Thailand	unknown	unknown	UNVERIFIED	duct flute	recorder-like	none fetched; existence from memory
palwei	Palwei	flutes	Myanmar	unknown	unknown	UNVERIFIED	bamboo flute	dizi-like	none fetched; existence from memory
palendag	Palendag	flutes	Philippines	unknown	unknown	UNVERIFIED	lip-valley flute	sine+noise	none fetched; existence from memory
saluang	Saluang	flutes	Minangkabau, Indonesia	unknown	unknown	UNVERIFIED	four-hole end-blown	sine+noise	none fetched; existence from memory
bangsi	Bangsi	flutes	Java/Sumatra	unknown	unknown	UNVERIFIED	bamboo flute	sine+noise	none fetched; existence from memory
algoza	Algoza	flutes	Punjab/Sindh	unknown	unknown	UNVERIFIED	paired duct flutes, drone+melody	two sources	none fetched; existence from memory
quenacho	Quenacho	flutes	Bolivia/Peru	unknown	unknown	UNVERIFIED	low quena	quena variant	none fetched; existence from memory
pinkillo	Pinkillo	flutes	Andes	unknown	unknown	UNVERIFIED	duct flute	buzz not modeled	none fetched; existence from memory
tarka	Tarka	flutes	Bolivia	unknown	unknown	UNVERIFIED	wooden duct flute, rough ensemble tone	detuned chorus	none fetched; existence from memory
siku	Siku (zampona)	flutes	Andes	unknown	unknown	UNVERIFIED	two-row panpipe played in interlocking pairs	hocket needs two voices	https://en.wikipedia.org/wiki/Panpipes
antara	Antara	flutes	Andes	unknown	unknown	UNVERIFIED	single-row panpipe	stopped-tube sines	none fetched; existence from memory
rondador	Rondador	flutes	Ecuador	unknown	unknown	UNVERIFIED	staggered panpipe	detuned pair	none fetched; existence from memory
pifano	Pifano	flutes	Brazil	unknown	unknown	UNVERIFIED	bamboo fife	fife variant	none fetched; existence from memory
colombian gaita	Gaita colombiana	flutes	Colombia	unknown	unknown	UNVERIFIED	beeswax and graphite duct head	sine+noise	none fetched; existence from memory
huilacapitztli	Huilacapitztli	flutes	Aztec, Mexico	unknown	unknown	UNVERIFIED	clay or cane tube flute	sine+noise	none fetched; existence from memory
whistling vessel	Whistling vessel	flutes	Peru, ancient	unknown	unknown	UNVERIFIED	double chamber whistle with pitch glide	pitch glide	none fetched; existence from memory
solomon panpipes	Solomon Islands panpipes	flutes	Solomon Islands	unknown	unknown	UNVERIFIED	bamboo panpipe ensembles	stopped-tube sines	https://en.wikipedia.org/wiki/Panpipes
porutu	Porutu	flutes	Maori	unknown	unknown	UNVERIFIED	nose flute	nose flute variant	none fetched; existence from memory
tonette	Tonette	flutes	USA, 1938	unknown	unknown	UNVERIFIED	plastic school duct flute	recorder variant	none fetched; existence from memory
flutophone	Flutophone	flutes	USA	unknown	unknown	UNVERIFIED	plastic school duct flute	recorder variant	none fetched; existence from memory
soprano ocarina	Soprano ocarina	flutes	Italy	unknown	unknown	UNVERIFIED	sweet hoot	ocarina variant	https://en.wikipedia.org/wiki/Ocarina
tenor ocarina	Tenor ocarina	flutes	Italy	unknown	unknown	UNVERIFIED	deeper hoot	ocarina variant	none fetched; existence from memory
double ocarina	Double ocarina	flutes	modern	unknown	unknown	UNVERIFIED	two-chamber ocarina	two sources	https://en.wikipedia.org/wiki/Ocarina
police whistle	Pea whistle	flutes	Britain, 1884	unknown	unknown	UNVERIFIED	shrill whistle fluttered by pea	sine with fast tremolo	none fetched; existence from memory
bosuns call	Bosun's call	flutes	Britain, naval	unknown	unknown	UNVERIFIED	whistle with air chamber, trill	sine with trill	none fetched; existence from memory
water whistle	Water whistle	flutes	worldwide	unknown	unknown	UNVERIFIED	warbling tremolo from water	sine with LFO pitch	none fetched; existence from memory
steam whistle	Steam whistle	flutes	industrial	unknown	unknown	UNVERIFIED	loud harmonic-rich hoot	saw+noise	none fetched; existence from memory
wot	Wot	flutes	Laos/Thailand (Isaan)	unknown	unknown	UNVERIFIED	cylindrical panpipe rotated to change notes	stopped-tube sines	https://en.wikipedia.org/wiki/Panpipes
firlinfeu	Firlinfeu	flutes	Lombardy, Italy	unknown	unknown	UNVERIFIED	folk panpipe	stopped-tube sines	https://en.wikipedia.org/wiki/Panpipes
chiflo	Chiflo (knife-grinder panpipe)	flutes	Galicia/Portugal	unknown	unknown	UNVERIFIED	small signalling panpipe	stopped-tube sines	https://en.wikipedia.org/wiki/Panpipes
quills	Quills (cane panpipe)	flutes	African-American, southern USA	unknown	unknown	UNVERIFIED	cane panpipe, breathy hoot	sine+noise	https://en.wikipedia.org/wiki/Panpipes
borrindo	Borrindo	flutes	Sindh, Indus Valley	unknown	unknown	UNVERIFIED	hollow clay ball, 3-4 holes	sine+noise	https://en.wikipedia.org/wiki/Ocarina
lalingedan	Lalingedan (double nose flute)	flutes	Paiwan, Taiwan	unknown	unknown	UNVERIFIED	double-pipe nose flute	two detuned sines	https://en.wikipedia.org/wiki/Nose_flute
koauau ponga ihu	Koauau ponga ihu (gourd nose flute)	flutes	Maori	unknown	unknown	UNVERIFIED	gourd nose flute like an ocarina	sine+noise	https://en.wikipedia.org/wiki/Nose_flute

Catalog note (bug to report): the catalog has `great bass recorder` and `contrabass recorder`. Wikipedia's recorder table lists two sizes named "great bass" (C3 and F2) and a sub-great bass (C2) and subcontrabass (F1). Catalog titles should state the lowest note to avoid ambiguity. The proposed names `subgreat bass recorder` (lowest C2) and `subcontrabass recorder` (lowest F1) follow the table. Also the whole catalog lacks the `flute in G`-style treble/`sopranino` flutes and any whistle other than tin/low (police, pea, steam, bosun's, water, slide: only slide is proposed).

Modeling flags (engine: oscillators + noise + filters, no FM, no sympathetic strings): (1) membrane buzz (dizi, qudi, bangdi, daegeum, khlui, sao truc) needs a noise-AM or buzz source on top of a sine: use one of the 4 sources; (2) overtone flutes (fujara, koncovka, kalyuka, willow flute, tilinca, tsuur, salamuri) need a pitch mapping that snaps to harmonic series and gliding between partials; (3) throat-singing flutes (tsuur, fulani flute) need a second pitched voice (2 sources); (4) hocket-style single-note pipes (embilta, tshikona, ngororombe, siku halves) are best modeled as one note per instance; (5) slide whistle, whistling vessel, bird warbler need continuous pitch glide with a portamento envelope; (6) sub-bass flutes (hyperbass, subcontrabass flute/recorder) sit below small-speaker response, so rely on the second harmonic; (7) double flutes (dvojnica, algoza, double flageolet, rondador) use two detuned sources.

## Rejected or corrected proposed entries

- ringflute (H-S 421, James Johnson): REJECTED pending evidence. No source fetched; not a recognized traditional or documented flute; the proposing audit gave no range ("not stated"). Source: none found.
- clackamore: REJECTED pending evidence. Proposed range "not stated", H-S "4", no source; cannot confirm it exists as a flute. Source: none found.
- hydraulophone: REJECTED from this catalog's flutes family. Wikipedia shows no H-S number and treats hydraulophones as a category separate from aerophones; it is water-jet driven. https://en.wikipedia.org/wiki/Hydraulophone . Ranges were right though: 12-jet diatonic A up an octave and a half to E; 45-jet about 3.5 octaves A to E plus Ab below (VERIFIED, same URL). If wanted, put it in a new "oddities" family.
- aztec death whistle: CORRECTED. Proposed A4-A6 is wrong in kind: sound is wind/noise-like per archaeologist testing, replicas give shriek; Wikipedia gives no pitch. Treat as unpitched noise. https://en.wikipedia.org/wiki/Aztec_death_whistle
- gemshorn: CORRECTED range. Proposed C4-C6 (two octaves); source gives about one octave (chromatic one octave on the 15th c. clay example). It is a duct (fipple) flute with recorder-style window, so the proposed H-S 421.221.42 prefix is plausible but unverified. https://en.wikipedia.org/wiki/Gemshorn
- suling: SCOPE problem. Proposed as one instrument; Wikipedia shows the Indonesian (Sundanese 4/6 hole, tuned by length, "56" about G) and Balinese suling are end-blown with external fipple, while the Philippine Maguindanao suling is a ring flute, so it should be split or described as the Indonesian suling. Range UNVERIFIED. https://en.wikipedia.org/wiki/Suling
- koauau / nguru / nose flute / putorino: nose flute article says nguru is usually mouth-played (only smaller ones by nose), so proposed "closed-end nose/mouth" is acceptable; the generic `nose flute` overlaps koauau as a nose/mouth flute; keep koauau and nguru as the distinct Maori forms and treat other regional nose flutes as aliases (below). putorino: UNVERIFIED (no fetched source for existence, range, or the flute/trumpet duality). https://en.wikipedia.org/wiki/Nose_flute
- subcontrabass flute / double contrabass flute: existence VERIFIED (G sub-contrabass, C double contrabass) but ranges UNVERIFIED. The contrabass flute lowest note is two octaves below middle C (C2), so the double in C should start at C1 (derived) and the sub in G at G1 (derived, matches proposal). https://en.wikipedia.org/wiki/Contrabass_flute
- blown bottle: kept but UNVERIFIED (no source fetched); duplicates nothing in catalog.
- shinobue: shinobue is made in many keys (uta, hayashi, doremi styles), so a single B4-B6 range is a key-specific guess. https://en.wikipedia.org/wiki/Shinobue
- nohkan: proposed C5-C7 is two octaves; source says "over two octaves" and the keynote varies from flute to flute, so the range is only approximate. https://en.wikipedia.org/wiki/Nohkan
- fujara: source says tuned A, G or F (contrabass), 1.6-2 m long; a G2 low is consistent only for the G model. https://en.wikipedia.org/wiki/Fujara
- slide whistle: Wikipedia has no range; proposed C4-C7 UNVERIFIED. Aliases below.

## Aliases

- swanee whistle -> slide whistle (https://en.wikipedia.org/wiki/Slide_whistle)
- lotus flute -> slide whistle
- piston flute -> slide whistle
- jazz flute -> slide whistle
- ohe hano ihu -> nose flute (Hawaii; https://en.wikipedia.org/wiki/Nose_flute)
- ohe hanu ihu -> nose flute
- fangufangu -> nose flute (Tonga, distinct only by node construction)
- pitung ilong -> nose flute (Philippines)
- kalaleng -> nose flute (Bontok)
- tongali -> nose flute (Kalinga)
- bulalri -> lalingedan (Rukai double nose flute)
- aangun -> nose flute (Chuuk)
- hun -> xun (Korean; https://en.wikipedia.org/wiki/Ocarina)
- tsuchibue -> xun (Japanese)
- jula-jula -> siku (https://en.wikipedia.org/wiki/Panpipes)
- julu-julu -> siku
- zampona -> siku
- nai -> pan flute (Romania, Moldova, Ukraine)
- kuvytsi -> pan flute (Ukrainian)
- syrinx -> pan flute (Greek; fistula in Etruscan)
- xipro -> chiflo
- siyotanka -> native american flute (memory)
- penny whistle -> tin whistle (memory)
- venu -> bansuri (memory; Carnatic flute with different fingering and tuning, kept as alias for modeling)

## Range checks

- tin whistle D5-D7: VERIFIED two octaves (https://en.wikipedia.org/wiki/Tin_whistle). Low whistle sounds an octave lower (rarely two), so D4-D6.
- contrabass flute lowest C2: VERIFIED (https://en.wikipedia.org/wiki/Contrabass_flute).
- recorders lowest notes: garklein C6, sopranino F5, voice flute D4, sixth flute D5, great bass C3, contrabass F2, subgreat C2, subcontrabass F1. VERIFIED (https://en.wikipedia.org/wiki/Recorder_(musical_instrument)); soprano C5-D7 (G7) VERIFIED, same URL. Catalog `contrabass recorder` consistent with F2 if it means "(sub)bass" in that table.
- piccolo C5, alto flute G3, bass flute C3, concert flute C4 (B3 with B foot): derived from intervals on https://en.wikipedia.org/wiki/Flute (derived, not stated).
- gemshorn: CORRECTED (one octave).
- hydraulophone: VERIFIED (above).
- ocarina: 10-12 hole transverse covers about an octave plus a fourth to octave plus a minor sixth; English pendant about octave to octave plus a major second; double about two octaves plus a minor third; triple about two octaves plus a minor seventh (VERIFIED widths, no absolute pitches; https://en.wikipedia.org/wiki/Ocarina).
- daegeum, ryuteki, shinobue, dizi, suling, fujara, koncovka, slide whistle: no numeric ranges on the pages: UNVERIFIED. ryuteki is between kagurabue (lower) and komabue (higher); about 40 cm long, seven holes.
- koauau, nguru, nose flute, putorino, blown bottle, aztec death whistle (see above), ringflute, clackamore: UNVERIFIED.
- Every new row above with "unknown": UNVERIFIED.

## Gaps you could not close

- MIMO, the Met, the Horniman and Grove listings were not consulted; List_of_flutes did not resolve. A real sweep there would almost certainly add dozens more (Hornbostel-Sachs 421 subcategories alone).
- Suspected but unchecked: Indian satara and jodi pava double flutes, pulangkuzhal, Persian ney sizes (mansur, bolahenk, davud), kiz neyi, Armenian sring, Tuvan shoor and Kyrgyz choor (probably aliases of tsuur), Ethiopian shembeko, Sundanese suling degung, Japanese tsuchibue as an instrument, Korean ji, Chinese yue and yo, Hawaiian ipu-based flutes, Fijian named nose flute, Mayan whistling jars and ocarinas, Chinese koudi, Swiss pfeife (probably fife alias), piffero (probably fife alias), txistu / galoubet / flabiol (probably tabor-pipe aliases), steam calliope (organs family?), tubulum (named in the brief; could not place it), albisifon and other 19th c. keyboard-flute hybrids, quarter-tone and glissando flutes, bamboo flute sizes by key (C, D, G, A), and other modern experimental flutes (contra-forte, heckelphone-like flutes, 3D-printed designs).
- H-S numbers in the proposed list were not checked against a primary classification source.
