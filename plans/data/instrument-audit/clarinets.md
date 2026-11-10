# Clarinets audit

## Summary

- New missing found: 38 (many names from the Wikipedia Single-reed list; only the clarinet-size ones have verified ranges)
- Proposed entries rejected: 0 outright; 1 corrected (bohlen pierce clarinet: not a distinct voice, see below)
- Aliases: 4 (mijwiz/zummara pairing caveat; hornpipe, stock and horn, pibgorn are one type; cifte -> arghul)
- Range fixes: arghul, launeddas, alboka, tarogato ranges all UNVERIFIED (from memory of first audit); size-variant ranges VERIFIED from Clarinet family page

## New missing instruments

```tsv
name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls
piccolo clarinet	Piccolo clarinet in A-flat	clarinets	Europe, 19th c. military bands	C4	E7	VERIFIED	Very small, shrill clarinet; odd-harmonic reed tone	none beyond clarinet voice; extreme top needs bright filter	https://en.wikipedia.org/wiki/Clarinet_family
d clarinet	D clarinet	clarinets	Europe	F#3	B6	VERIFIED	Bright clarinet a tone above C; Strauss, Ravel	clarinet voice	https://en.wikipedia.org/wiki/Clarinet_family
c clarinet	C clarinet	clarinets	Europe	E3	Bb6	VERIFIED	Brighter, thinner clarinet; non-transposing	clarinet voice	https://en.wikipedia.org/wiki/Clarinet_family
b natural clarinet	B-natural clarinet	clarinets	Europe	Eb3	Bb6	VERIFIED	Rare; clarinet tone	clarinet voice	https://en.wikipedia.org/wiki/Clarinet_family
low g clarinet	Low G clarinet (Turkish/Romani)	clarinets	Turkey, Balkans	B2	G6	VERIFIED	Large-bore folk clarinet, fruity woody tone	clarinet voice; add pitch ornament/slide optional	https://en.wikipedia.org/wiki/Clarinet_family
basset clarinet	Basset clarinet in A	clarinets	Europe, 1780s (Stadler)	A2	A6	VERIFIED	Soprano clarinet with extended low range; Mozart concerto	clarinet voice	https://en.wikipedia.org/wiki/Clarinet_family
octocontrabass clarinet	Octocontrabass clarinet	clarinets	Europe/USA, 20th c.	Bb-1	G3	VERIFIED	Sub-bass, mostly breathy fundamental, near infrasonic	lowest note ~14 Hz; needs sub-bass oscillator and heavy noise	https://en.wikipedia.org/wiki/Clarinet_family
heckel clarina	Heckel-clarina	clarinets	Germany, Heckel	unknown	unknown	UNVERIFIED	Metal, conical bore, single reed, resembles soprano sax; made in sopranino Eb and soprano Bb	sax-like voice	https://en.wikipedia.org/wiki/Heckel-clarina
heckelphone clarinet	Heckelphone-clarinet	clarinets	Germany, Heckel	unknown	unknown	UNVERIFIED	Page exists (not fetched)	unknown	https://en.wikipedia.org/wiki/Heckelphone-clarinet
octavin	Octavin	clarinets	Germany, Julius Jehring (bassoon maker) 1881	G#3	G6	VERIFIED (written range)	Conical-bore single-reed, 19th c., sax-like	clarinet/sax voice	https://en.wikipedia.org/wiki/Octavin; search result via https://en.wikipedia.org/wiki/Octavin
venova	Venova	clarinets	Japan, Yamaha	unknown	unknown	UNVERIFIED	Existence from the Wikipedia Single-reed list only; search found no page	unknown	https://en.wikipedia.org/wiki/Single-reed_instrument
xaphoon	Xaphoon (pocket sax)	clarinets	USA, Brian Wittman (Maui Xaphoon)	unknown	unknown	UNVERIFIED	Chalumeau-like construction and range per one source; trademarked name	chalumeau voice	https://en.wikipedia.org/wiki/Xaphoon
mijwiz	Mijwiz	clarinets	Levant	unknown	unknown	UNVERIFIED	Two equal bamboo pipes, 5-6 holes each, both fingered, continuous tone	two parallel oscillators	https://en.wikipedia.org/wiki/Mijwiz
zummara	Zummara	clarinets	Egypt	unknown	unknown	UNVERIFIED	Double-pipe idioglot, buzzy, parallel melody pipes (distinct from arghul: no drone pipe)	two parallel oscillators	https://en.wikipedia.org/wiki/Single-reed_instrument
dozaleh	Dozaleh	clarinets	Iran, Kurdish areas	unknown	unknown	UNVERIFIED	Double clarinet; parallel pipes, nasal	two oscillators	https://en.wikipedia.org/wiki/Single-reed_instrument
sipsi	Sipsi	clarinets	Aegean Turkey	unknown	unknown	UNVERIFIED (span ~1.5 octaves only)	Bone/wood/reed body, 5+1 holes; timbre likened to Irish bagpipe	none; no absolute pitch given	https://en.wikipedia.org/wiki/Sipsi
diplica	Diplica	clarinets	Croatia, Balkans	unknown	unknown	UNVERIFIED (usually key of E)	Two pipes from one piece of wood, mouth horn, one tube drone	drone + melody	https://en.wikipedia.org/wiki/Diplica
pibgorn	Pibgorn	clarinets	Wales (Anglesey)	unknown	unknown	UNVERIFIED (hornpipe general: up to an octave plus a note)	Hornpipe: single-reed idioglot with horn bell, rustic buzz	none	https://en.wikipedia.org/wiki/Hornpipe_(instrument)
pilili	Pilili	clarinets	Sardinia/Spain (memory)	unknown	unknown	UNVERIFIED	Single-reed pipe, reedy	none	https://en.wikipedia.org/wiki/Single-reed_instrument
reclam de xeremies	Reclam de xeremies	clarinets	Balearic Islands	unknown	unknown	UNVERIFIED	Two equal cane tubes, idioglot, pentatonic, tuning varies (per Wikipedia page fetched under that name; the page was the Dilli/Reclam mixup check: see gaps)	two parallel oscillators	https://en.wikipedia.org/wiki/Reclam_de_xeremies
zhaleika	Zhaleika	clarinets	Russia	unknown	unknown	UNVERIFIED (hornpipe general: up to an octave plus a note)	Single-reed (or double in some) folk pipe with horn bell, piercing	none	https://en.wikipedia.org/wiki/Hornpipe_(instrument)
birbyne	Birbyne (soprano)	clarinets	Lithuania	A3	G6	VERIFIED	Single- or double-reed (sources conflict) folk pipe with horn bell, octave key; non-transposing	clarinet voice	https://en.wikipedia.org/wiki/Birbynė
stock and horn	Stock-and-horn	clarinets	Scotland, Highlands	unknown	unknown	UNVERIFIED (hornpipe general: up to an octave plus a note)	Hornpipe with cow-horn bell, rustic	none	https://en.wikipedia.org/wiki/Hornpipe_(instrument)
hornpipe	Hornpipe (Welsh/English)	clarinets	British Isles	unknown	unknown	UNVERIFIED (hornpipe general: up to an octave plus a note)	Generic single-reed pipe with animal-horn bell	alias-prone; keep as generic	https://en.wikipedia.org/wiki/Hornpipe_(instrument)
ganurags	Ganurags	clarinets	Latvia/Lithuania (memory)	unknown	unknown	UNVERIFIED	Single-reed horn-bell pipe	none	https://en.wikipedia.org/wiki/Single-reed_instrument
dilli tuiduk	Dilli tuiduk	clarinets	Turkmenistan	F	E	UNVERIFIED (octave numbers vague: F in first octave to D/E in second; about a sixth or seventh)	Bulrush body, split reed, penetrating	none	https://en.wikipedia.org/wiki/Dilli_tuiduk
bulban	Bulban	clarinets	Central Asia	unknown	unknown	UNVERIFIED	Single-reed pipe (listed in Wikipedia Central Asian list; details unconfirmed)	none	https://en.wikipedia.org/wiki/Single-reed_instrument
pungi	Pungi	clarinets	India	unknown	unknown	UNVERIFIED (melody pipe spans one octave, 7 holes)	Gourd, two pipes, one drone; high thin tone over low hum	drone oscillator + melody	https://en.wikipedia.org/wiki/Pungi
pepa	Pepa	clarinets	Assam, India	unknown	unknown	UNVERIFIED (hornpipe general: up to an octave plus a note)	Buffalo-horn-bell hornpipe with single reed	none	https://en.wikipedia.org/wiki/Hornpipe_(instrument)
tarpa	Tarpa	clarinets	Maharashtra/Gujarat, India	unknown	unknown	UNVERIFIED	Large spiral gourd-bell single-reed horn	none	https://en.wikipedia.org/wiki/Single-reed_instrument
pey pok	Pey pok	clarinets	Cambodia	unknown	unknown	UNVERIFIED	Single-reed bamboo pipe, nasal	none	https://en.wikipedia.org/wiki/Single-reed_instrument
sarune etek	Sarune etek	clarinets	Sumatra, Indonesia	unknown	unknown	UNVERIFIED	Single-reed Batak pipe with rolled-leaf bell? (memory)	none	https://en.wikipedia.org/wiki/Single-reed_instrument
sneng	Sneng	clarinets	Cambodia	unknown	unknown	UNVERIFIED	Single-reed buffalo-horn-bell pipe	none	https://en.wikipedia.org/wiki/Single-reed_instrument
toleat	Toleat	clarinets	Philippines	unknown	unknown	UNVERIFIED	Single-reed bamboo pipe	none	https://en.wikipedia.org/wiki/Single-reed_instrument
memet	Memet	clarinets	Ancient Egypt c. 2700 BCE	unknown	unknown	UNVERIFIED	Ancient double single-reed pipe	none	https://en.wikipedia.org/wiki/Single-reed_instrument
mock trumpet	Mock trumpet	clarinets	England, 18th c.	unknown	unknown	UNVERIFIED	Single-reed mouthpiece instrument imitating trumpet	none	https://en.wikipedia.org/wiki/Single-reed_instrument
contrabass birbyne	Contrabass birbyne	clarinets	Lithuania	F1	G3	VERIFIED	Largest birbyne	low-register oscillator	https://en.wikipedia.org/wiki/Birbynė
tenor birbyne	Tenor birbyne	clarinets	Lithuania	B2	G5	VERIFIED	Larger birbyne	clarinet voice	https://en.wikipedia.org/wiki/Birbynė
clarinet d amore	Clarinet d'amore	clarinets	Germany, 19th c.	unknown	unknown	UNVERIFIED	Clarinet in G/A-flat with pear-shaped bell, veiled tone (memory)	none	(memory) https://en.wikipedia.org/wiki/Clarinet_d%27amore
saxonette	Saxonette	clarinets	UK/Netherlands, 1920s (memory)	unknown	unknown	UNVERIFIED	Clarinet-like with sax-style fingering, bright	none	(memory)
```

## Rejected or corrected proposed entries

- bohlen pierce clarinet: real (Stephen Fox, Wikipedia Experimental_musical_instrument), but it is a clarinet voice with a 13-step tritave tuning, not a distinct timbre; engine can only model it if it supports custom scales. Keep only if a scale system exists. Its odd harmonics are clarinet-standard (a cylindrical bore is the point). Range not stated; UNVERIFIED.
- tarogato: Wikipedia gives no H-S number (cannot check 422.212). Modern form is single-reed conical bore; sound 'mix of cor anglais and soprano sax' (https://en.wikipedia.org/wiki/Tárogató). Range CORRECTED to written Bb3-C6 (proposed G3-C6 wrong). Wikipedia Single-reed list confirms it exists as a modern instrument (https://en.wikipedia.org/wiki/Single-reed_instrument). Historical (shawm-like, double reed) tarogato exists too: choose single-reed modern form.
- arghul: H-S number CORRECTED to 422.211.2 (https://en.wikipedia.org/wiki/Arghul); melody pipe plus longer drone pipe; small/medium/large sizes. The proposed range is not supported by the page.
- alboka: confirmed (https://en.wikipedia.org/wiki/Alboka): two melody pipes sharing one reed cap and one horn bell on a wooden arch; no range or H-S given. Range UNVERIFIED.
- launeddas: three pipes (two five-hole chanters of different length plus a drone), melody in thirds and sixths (https://en.wikipedia.org/wiki/Launeddas). The pipe names I first wrote were from memory and not on the page. Range UNVERIFIED.

## Aliases

- cifte (argun, argul) -> arghul: Turkish tied double pipe, demli type has drone pipe (https://en.wikipedia.org/wiki/Arghul)
- hornpipe -> pibgorn / stock and horn are regional forms of one construction (hornpipe is the generic; pibgorn Welsh; stock and horn Scots). Keep pibgorn and stock and horn as separate only if distinct timbre is wanted.
- zummara: no page found; only named as related to the arghul. Existence confirmed by name only; likely close to mijwiz. Consider folding into mijwiz.
- pku -> unknown (could not identify; memory says nothing confident).
- octavin -> possibly similar to xaphoon in modeling; separate instruments.

## Range checks

- Verified (from https://en.wikipedia.org/wiki/Clarinet_family sounding ranges): E-flat G3-C7; B-flat D3-Bb6; A C#3-A6; basset horn F2-F6; alto G2-Eb6; bass Bb1-Bb5; contra-alto Gb1-C5; contrabass Bb0-G4; octocontrabass Bb-1-G3 (these also apply to the catalog entries).
- chalumeau: Wikipedia gives no per-size range (only that early two-key design gave about twelve notes); UNVERIFIED. Met has a chalumeau in F (Galpin copy).
- alboka A3-A5, arghul C2-C3/C4-C5, launeddas G3-G5: UNVERIFIED (pages give no ranges). tarogato G3-C6: CORRECTED to written Bb3-C6.

## Gaps you could not close

- Ranges and timbres of all folk pipes (only existence was confirmed via Wikipedia list pages; no ranges given).
- Pku, bulban, sarune etek, toleat, pilili, ganurags, pey pok, sneng, tarpa, dozaleh, zummara, clarinet d amore, saxonette: not fetched; existence only from Wikipedia Single-reed list (or memory for clarinet d amore, saxonette, pilili/ganurags origins). Sound descriptions in the table for folk entries are my paraphrase/memory unless the sound column cites a page.
- The reclam de xeremies row was only a partial read: the page text I got may have been mixed with another page; recheck.
- Pibgorn page fetch returned a disambiguation page only.
- The Met and MIMO were not systematically searched; one Met search only.
- Not searched: MIMO, Met, Horniman, Grove. Likely missing: African single-reed pipes, Ethiopian/Berber examples, Indigenous American, Chinese/Korean single-reed pipes (bawu is free reed, belongs elsewhere), Caucasian (zurna family is double reed), Spanish tible/gaita variants.
- Whether Clarinet family page tail (offset 100000+) lists more variants (e.g. contrabass in other keys, albisiphone) was not read.
- Modeling: no instruments need FM or physical modeling beyond two-oscillator parallel pipes and a sustained drone (pungi, arghul, launeddas, alboka); circular breathing means no breath gaps.
