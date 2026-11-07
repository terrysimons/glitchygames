# Struck strings audit (family: struck_strings)

## Summary
- New missing found: 14 rows below (13 struck strings plus chapman stick, which belongs in plucked/electric strings). Distinct struck instruments: khim, hackbrett, santoor, yanggeum, chang, pantaleon, tambourin a cordes, utogardon, zhu, malunga, ground bow, marxophone, dolceola.
- Proposed entries rejected or reclassified: 1 rejected (harmonic generator), 1 kept with caveat (harmonic canon). Other families' marxophone, celestaphone and pianoharp are flagged for re-homing.
- Aliases: about 20 (see Aliases). Range fixes: cimbalom (catalog value should be checked to A1-A6), khim, marxophone, chapman stick verified; every other range UNVERIFIED.
- Sources actually fetched: Wikipedia pages (hammered dulcimer, cimbalom, berimbau, khim, santur, santoor, yangqin, yanggeum, tambourin de Gascogne, zhu, utogardon, malunga, ground bow, marxophone, dolceola, chapman stick, harry partch, partch list, HS 314.122 list) plus web searches (hackbrett, Uyghur chang, musical bows, pantaleon, Hawaiian/Chinese/African struck zithers). MIMO, the Met and Grove returned nothing usable; one search mentioned a Horniman page for 314.122-4 but I did not read it. Earlier draft of this file contained rows from memory (khim, tsimbl, tambal, salterio, schlagzither, hungu etc. with guessed ranges); those guessed ranges were removed. Nothing here is from memory unless marked.

## New missing instruments
name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls
khim	Khim	struck strings	Thailand/Cambodia (Chinese-derived)	A2	A4	VERIFIED for 7-note standard size only (A2/A3/A4 low/mid/high)	Soft tone from two bamboo sticks with leather tips; courses of three brass strings (42 on the 7-note model)	short bright plucky; set 2-3 detuned oscillators per course for chorus	https://en.wikipedia.org/wiki/Khim
hackbrett	Hackbrett (Salzburg chromatic)	struck strings	Austria/Germany/Switzerland	unknown	unknown	UNVERIFIED (no note range found; chromatic Salzburg model reported with 128 strings by a retailer, unconfirmed)	Alpine dulcimer; chromatic Salzburg version with crossed strings, mid-1930s per wiki mirror	chorus of detuned strings; crossed-string chromatic layout is irrelevant to synthesis	https://en.wikipedia.org/wiki/Hammered_dulcimer
santoor	Santoor (Indian/Kashmiri)	struck strings	Kashmir, India	unknown	unknown	UNVERIFIED (about three octaves; no note names)	25 bridges, 4 strings each (about 100 strings), two light mezrab mallets, delicate and sensitive to glides	long decays and heavy polyphony; no sympathetic-string model	https://en.wikipedia.org/wiki/Santoor
yanggeum	Yanggeum	struck strings	Korea (via China, 18th c.)	unknown	unknown	UNVERIFIED (article gives no range)	Seven courses of four metal strings; struck with a thin bamboo stick	same synth as yangqin with fewer courses	https://en.wikipedia.org/wiki/Yanggeum
chang	Uyghur chang	struck strings	Xinjiang, China	unknown	unknown	UNVERIFIED (range not found; 38 courses reported, 4 strings per course per one source and 3 per another)	Trapezoid dulcimer struck with two beaters; used in muqam; also called Xinjiang yangqin by one encyclopedia entry	as dulcimer; high string count means thick chorus	https://lbcone.hkust.edu.hk/music-costumes/musical-instruments/uyghur-chang/
pantaleon	Pantaleon	struck strings	Germany/France, Pantaleon Hebenstreit, early 18th c.	unknown	unknown	UNVERIFIED (very large range; possibly 276 strings per 'some sources')	Giant dulcimer with metal and gut strings, played with mallets	as dulcimer with huge range	https://en.wikipedia.org/wiki/Pantalon
tambourin a cordes	Tambourin a cordes (string drum)	struck strings	Gascony/Bearn, France, and Pyrenees (Basque ttun-ttun, Spanish salmo, Aragonese chicoten)	unknown	unknown	UNVERIFIED (5-6 strings tuned tonic and dominant, 4-10 in Pyrenees; no note range)	Struck with a linen-covered stick in one hand while the other plays a tabor pipe; drone chords	drone pair of strings with dull struck attack; pipe companion is separate	https://en.wikipedia.org/wiki/Tambourin_de_Gascogne
utogardon	Utogardon	struck strings	Hungary	D2	D3	UNVERIFIED octave (tuning D-D-D-d from article, octave not stated; memory for octave)	4 strings; struck and plucked with a 40 cm stick; droning accompaniment	dull bass thump plus drone plucking strings	https://en.wikipedia.org/wiki/%C3%9Ct%C5%91gardon
zhu	Zhu	struck strings	Ancient China (Warring States, lost in Song)	unknown	unknown	UNVERIFIED (5-string example from Marquis Yi tomb c. 433 BC; no range)	Slender-stick-struck zither with silk or gut strings; may have been plucked with the stick; reconstruction only	likely plucky; low confidence about timbre	https://en.wikipedia.org/wiki/Zhu_(string_instrument)
malunga	Malunga	struck strings	Siddi community, India (East African origin)	unknown	unknown	UNVERIFIED (two tones an octave apart; no absolute pitch)	One gut string on bamboo bow, stick-struck with a rattle (mai misra) in the same hand; coconut resonator	two-pitch bow, rattle layer needs noise source (filtered noise burst)	https://en.wikipedia.org/wiki/Malunga
ground bow	Ground bow	struck strings	Africa and Caribbean (kalinga, gayumba, tumbandera, tingo-talango)	unknown	unknown	UNVERIFIED (pitch unstable by design)	Bow stick bent while string is struck: glissando effect; accompaniment to singing	needs pitch bend after strike (glide envelope); unstable pitch	https://en.wikipedia.org/wiki/Ground_bow
marxophone	Marxophone	struck strings	USA c.1900s	C4	C6	VERIFIED (two octaves, middle C to C'' in C major, 15 keys)	Spring-steel strips holding lead hammers; hold gives mandolin-like tremolo; strummed chord strings C, G, F, D7. Proposed in chordophones audit; re-home here	needs fast retrigger tremolo while held (repeated envelope); available via LFO gating	https://en.wikipedia.org/wiki/Marxophone
dolceola	Dolceola	struck strings	Toledo Symphony Co., USA 1903-1907	unknown	unknown	UNVERIFIED (no range in article)	Zither played via a keyboard action; characteristic clatter; known gap in brief	keyboard clatter noise at onset	https://en.wikipedia.org/wiki/Dolceola
chapman stick	Chapman Stick	plucked strings	USA, Emmett Chapman 1970s	C1	C6	VERIFIED (standard 36 in scale C1 to C6)	10 or 12 strings tapped with both hands; H-S 321.322 composite chordophone, so it is not a struck zither; place with plucked/electric strings, not this family	like electric guitar/bass tapped attack	https://en.wikipedia.org/wiki/Chapman_Stick

## Rejected or corrected proposed entries
- harmonic generator: not on the Partch pages and no source; reads electromechanical, not a struck chordophone. Reject. Sources: https://en.wikipedia.org/wiki/Harry_Partch and https://en.wikipedia.org/wiki/List_of_instruments_by_Harry_Partch (neither mentions it).
- harmonic canon: real; 44-string sonometer with movable bridges, Canons I, II, III built 1945, 1953, 1965; played with fingers, picks, or in some cases unique mallets, so mostly plucked, not struck. Keep out of this family (plucked strings or oddities). Range not stated: UNVERIFIED. Source: https://en.wikipedia.org/wiki/List_of_instruments_by_Harry_Partch
- luthéal: keyboard, stays in keyboards (not rechecked).
- celestaphone, pianoharp (chordophones audit): Wikipedia's Celestaphone fetch returned a musician, not the instrument, so unverified; pianoharp has only a forum source. Hold as UNVERIFIED.
- marxophone: re-home to struck strings; VERIFIED mechanism and range (C4-C6).
- gopichand: plucked one-string ektara-type instrument (memory, not fetched); not struck, not this family.
- Cello col legno is a technique, not an instrument.
- The HS 314.122 Wikipedia list shows only cimbalom, santur and yangqin as -4 (struck) entries, so none of the Hawaiian/African struck zithers in the brief are documented there.

## Aliases
- santur (Iran), yangqin, cimbalom: already catalog entries; hammered dulcimer type per https://en.wikipedia.org/wiki/Hammered_dulcimer
- yoochin (Mongolia), yangzi/rgyud-mang (Tibet), dan tam thap luc (Vietnam), santouri/santouri (Greece), dulcemele, dultzimar, darushimaa, hakkebord, hakkebraet, hakkebrett, hackbraede, hammarharpa, oprekelj, cimbale, cimbule -> hammered dulcimer or cimbalom per same page
- cimbal (Czech/Slovak/Croatian), cymbaly (Poland), tsymbaly (Ukraine/Belarus), zymbal, tsimbl (Yiddish), tambal (Romania), chimbaly (Russia) -> cimbalom (page lists these as cimbalom-derived names; smaller Belarusian/Ukrainian portable versions differ in size/damping but are not separately cataloged)
- tympanon (France), tiompan (Ireland), salterio (Iberia/Italy) -> hammered dulcimer family (same page); salterio is also a psaltery name, so it is ambiguous
- ttun-ttun, salmo, chicoten, toum-toum -> tambourin a cordes (https://en.wikipedia.org/wiki/Tambourin_de_Gascogne)
- umbulumbumba (mbulumbumba) -> berimbau (Kubik: identical construction and playing technique, per https://en.wikipedia.org/wiki/Berimbau)
- urucungo, madimba lungungu -> berimbau (same page)
- kalinga/galinga, gayumba, tumbandera, tingo-talango, angbindi -> ground bow (https://en.wikipedia.org/wiki/Ground_bow)
- hungu: a Kimbundu name for a gourd bow like the berimbau (via search results, secondary); alias of berimbau unless a separate bow is wanted
- gunga/berra-boi, medio, viola/violinha: berimbau sizes (three tones); candidates for 3 catalog entries
- hudie qin -> butterfly dulcimer; yangqin page says it is a related butterfly zither (not an alias exactly)
- Xinjiang yangqin -> chang (one encyclopedia entry, weak source)

## Range checks
- cimbalom: VERIFIED. Schunda tuning C to e''' Helmholtz (C2 to E6); modern concert AA to a''' (A1 to A6); a Schunda photo caption says E2-E6 plus a D2 string. https://en.wikipedia.org/wiki/Cimbalom
- hammered dulcimer: PARTIAL. 15/14 model spans three octaves; lowest note often G or D; no absolute octave. https://en.wikipedia.org/wiki/Hammered_dulcimer
- yangqin: PARTIAL. Chromatic, slightly over four octaves, middle C on the tenor bridge; no end notes. https://en.wikipedia.org/wiki/Yangqin
- santur: PARTIAL. About three diatonic octaves, 25 tones, no note names. https://en.wikipedia.org/wiki/Santur
- santoor: PARTIAL. About three octaves, no note names. https://en.wikipedia.org/wiki/Santoor
- khim: VERIFIED for the 7-note model A2 to A4 (low A2, mid A3, high A4). https://en.wikipedia.org/wiki/Khim
- berimbau: PARTIAL. Neutral-second microtonal interval; tunings in fourths (C, F, B-flat) or triad (C, E, G); no octave. https://en.wikipedia.org/wiki/Berimbau
- marxophone: VERIFIED C4-C6. https://en.wikipedia.org/wiki/Marxophone
- chapman stick: VERIFIED C1-C6. https://en.wikipedia.org/wiki/Chapman_Stick
- harmonic canon: UNVERIFIED (not stated).

## Gaps you could not close
- Hawaiian and African struck zithers: searched HS 314.122 list and a general search; none documented. Not claimed.
- Dolceola range and string count; celestaphone and pianoharp mechanism (Celestaphone fetch returned a musician).
- Pantaleon string count (276 per "some sources") and range; Grove entry unreadable.
- Salzburg hackbrett range (128 strings reported by a retailer only).
- Uyghur chang range and strings per course (3 vs 4 conflict).
- MIMO and the Met were not reachable for this family; Horniman 314.122-4 page seen only as a search result.
- Not checked: claviharp, harp-piano, zither-banjo, tangent piano, orphica, schlagzither, tsimbl/Yiddish vs Romanian tambal differences, high/alto/bass yangqin sizes (the page says none described).
