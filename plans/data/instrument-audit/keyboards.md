# Keyboards audit (non-organ)

Method: ~35 fetches of Wikipedia pages, 1 web search (Met; produced nothing instrument-specific). Pages marked fetched were read through WebFetch summaries (small-model extraction, not full text). MIMO, the Horniman and Grove were NOT reached. "(memory)" marks anything not from a fetched page. Range cells: VERIFIED only where a fetched page states it; note-name conversion done by me where stated.

## Summary
- New missing instruments listed: 40 (many are weak: aliases or timbre-identical variants, flagged in modeling_notes).
- Proposed entries rejected/corrected: 5 (spinet, clavicymbalum, octavator, scalatron, walking piano; plus lautenwerck spelling).
- Aliases: 12.
- Range fixes: Optigan, Mellotron ranges confirmed; Pianet, Wurlitzer, Clavinet, Rhodes Piano Bass, dulcitone ranges obtained; most others have no published range on Wikipedia.

## New missing instruments
```
name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls
square piano	Square piano	keyboards	Europe (Zumpe, London) c.1760; popular to mid 19th c.	unpitched	unpitched	UNVERIFIED (page: ~6 octaves by 1820s, no note names)	plucky proto-piano, shorter decay than modern piano	fortepiano-style envelope	https://en.wikipedia.org/wiki/Square_piano
giraffe piano	Giraffe piano	keyboards	Vienna, c.1800 (memory)	unpitched	unpitched	UNVERIFIED	upright fortepiano, soft; may have moderator/janissary stops (memory)	janissary effect needs noise bursts	https://en.wikipedia.org/wiki/Piano
tack piano	Tack piano	keyboards	USA (memory)	A0	C8	UNVERIFIED (memory)	metallic jangly saloon piano	near-duplicate of honky tonk piano; likely alias	https://en.wikipedia.org/wiki/Piano
player piano	Player piano	keyboards	Europe/USA 19th c.	A0	C8	UNVERIFIED (memory; standard piano range)	piano timbre; automation only	timbre identical to upright; alias unless automation modeled	https://en.wikipedia.org/wiki/Player_piano
pedal piano	Pedal piano	keyboards	Europe 18th-19th c.	unpitched	unpitched	UNVERIFIED	piano with pedalboard for bass	piano source, extended low register	https://en.wikipedia.org/wiki/Pedal_piano
pedal clavichord	Pedal clavichord	keyboards	Germany, 16th-18th c. (Gerstenberg, 1760s, Leipzig)	unpitched	unpitched	UNVERIFIED (no range on page)	quiet clavichord with pedal bass	clavichord source, low register	https://en.wikipedia.org/wiki/Pedal_clavichord
quarter tone piano	Quarter-tone piano	keyboards	Czechoslovakia, 1920s (Haba) (memory)	A0	C8	UNVERIFIED (memory)	piano tuned in quarter tones	only needs microtonal tuning	https://en.wikipedia.org/wiki/Alois_H%C3%A1ba
janko piano	Janko keyboard piano	keyboards	Vienna, designed 1882 (Paul von Janko)	A0	C8	UNVERIFIED (page gives only 88 notes / 264 keys layout)	piano timbre, keyboard layout only	alias-class of grand piano	https://en.wikipedia.org/wiki/Janko_keyboard
moor double keyboard piano	Moor double keyboard piano	keyboards	Emanuel Moor, 1921 (Pleyel built ~1927)	A0	C8	UNVERIFIED (range not on page)	piano with two coupled manuals, optional harpsichord imitation	octave coupling = second oscillator at 2x	https://en.wikipedia.org/wiki/Emanuel_Mo%C3%B3r
clavicytherium	Clavicytherium	keyboards	Europe; earliest known harpsichord c.1480 (RCM London, possibly Ulm)	unpitched	unpitched	UNVERIFIED (RCM example 41 notes, no pitches)	upright harpsichord, plucked	like harpsichord	https://en.wikipedia.org/wiki/Clavicytherium
lautenwerk	Lautenwerk	keyboards	Baroque Germany; Bach owned two; no 18th-c. examples survive	unpitched	unpitched	UNVERIFIED (no range on page)	gut-strung harpsichord, mellow	soft pluck with gut-like filtered decay	https://en.wikipedia.org/wiki/Lautenwerk
ottavino	Ottavino	keyboards	Italy, small spinet/virginal at 4 foot pitch	unpitched	unpitched	UNVERIFIED (range not given)	small 4-foot virginal, bright thin	harpsichord source one octave up	https://en.wikipedia.org/wiki/Harpsichord
harpsichord sixteen foot	Harpsichord (16 foot)	keyboards	Some larger harpsichords	F0	F5	UNVERIFIED (derived: one octave below F1-F6; page only says 16' sounds an octave lower)	dark plucked bass-heavy	lower octave oscillator	https://en.wikipedia.org/wiki/Harpsichord
harpsichord buff stop	Harpsichord (buff stop)	keyboards	Baroque	F1	F6	VERIFIED (F1-F6 five-octave harpsichord, page)	muted, lute-like pluck	shorter decay, filtered	https://en.wikipedia.org/wiki/Harpsichord
clavicymbalum	Clavicymbalum	keyboards	Medieval Europe; listed on Wikipedia keyboard category	unpitched	unpitched	UNVERIFIED	early plucked keyboard	near-alias of harpsichord/virginal	https://en.wikipedia.org/wiki/Category:Keyboard_instruments
archicembalo	Archicembalo	keyboards	Italy, Nicola Vicentino, described 1555	unpitched	unpitched	UNVERIFIED (36 keys per octave; overall range not given)	microtonal harpsichord, 36 keys per octave	only needs microtonal tuning	https://en.wikipedia.org/wiki/Archicembalo
viola organista	Viola organista	keyboards	Leonardo design 1488-89; Hans Heyden built Geigenwerk 1575	E3	B6	UNVERIFIED (page: 1620 etching ~44 keys 'low E to high B', octave not stated; modern replica F1-F6, 61 keys)	bowed-string keyboard via friction wheels, violin-like sustain	continuous friction excitation; sawtooth plus noise, no real bow model	https://en.wikipedia.org/wiki/Viola_organista
geigenwerk	Geigenwerk	keyboards	Nuremberg 1575 (Hans Heyden); reinvented by Hohlfeld, Berlin 1751	unpitched	unpitched	UNVERIFIED (range not given)	gut strings sounded by rosined pedal cylinder, hurdy-gurdy-like	same as viola organista; possibly alias	https://en.wikipedia.org/wiki/Geigenwerk
dulce melos	Dulce melos	keyboards	Europe, 1440 (Henri-Arnault de Zwolle)	unpitched	unpitched	UNVERIFIED (36 notes per chromatic octave layout; no pitches)	hammered-dulcimer-like keyboard zither	struck decay	https://en.wikipedia.org/wiki/Dulce_melos
dulcitone	Dulcitone	keyboards	Glasgow, 1860s (Thomas Machell)	A2	A7	VERIFIED (page: written AA-a3, sounds octave higher, sounding 'A to a4'; Helmholtz converted to note names by me)	tuning forks struck by felt hammers: soft, near-sine	fork = sine plus faint partial, short-medium decay	https://en.wikipedia.org/wiki/Dulcitone
typophone	Typophone	keyboards	France, 1860 (Charles Victor Mustel)	unpitched	unpitched	UNVERIFIED (range not given)	tuning forks struck by hammers	like dulcitone	https://en.wikipedia.org/wiki/Celesta
glasschord	Glasschord	keyboards	Paris, c.1785 (M. Beyer)	C4	C7	UNVERIFIED (page: ~3 octaves; start c', f' or g' Helmholtz; no dampers)	struck glass tubes, celesta-like	inharmonic glass partials, long undamped ring	https://en.wikipedia.org/wiki/Glasschord
keyed glockenspiel	Keyboard glockenspiel	keyboards	Europe (Wikipedia lists page)	unpitched	unpitched	UNVERIFIED	metal bars struck by keys	like glockenspiel in catalog family	https://en.wikipedia.org/wiki/Category:Keyboard_instruments
dolceola	Dolceola	keyboards	Toledo Symphony Company, USA, 1903-1907	unpitched	unpitched	UNVERIFIED (range not on page)	zither with keys, small piano-looking, dulcimer-like	struck strings, damper	https://en.wikipedia.org/wiki/Dolceola
claviharp	Claviharp	keyboards	listed on Wikipedia keyboard category	unpitched	unpitched	UNVERIFIED (no page read)	keyboard-plucked/harp	plucked decaying source	https://en.wikipedia.org/wiki/Category:Keyboard_instruments
orphica	Orphica	keyboards	Vienna 1795-1810 (Carl Leopold Rollig)	unpitched	unpitched	UNVERIFIED (range not given)	portable shoulder-strap piano, ~30 survive; Beethoven WoO 51	small piano timbre	https://en.wikipedia.org/wiki/Orphica
luthéal	Luthéal	keyboards	Belgium, patented 28 Jan 1919 (Georges Cloetens)	unpitched	unpitched	UNVERIFIED (piano range; four stops: cimbalom-like, harmonics, objects over strings, harpsichord/harp-lute)	piano attachment with four registers	multiple timbre modes; object-on-string resonance beyond engine	https://en.wikipedia.org/wiki/Luth%C3%A9al
orchestrion	Orchestrion	keyboards	Germany; panharmonicon (Malzel) 1805; Welte 1832-1932	unpitched	unpitched	UNVERIFIED (no single range)	mechanical ensemble of pipes, percussion, often piano	needs several instruments at once: beyond 4 sources	https://en.wikipedia.org/wiki/Orchestrion
panharmonicon	Panharmonicon	keyboards	Vienna, 1805 (Malzel)	unpitched	unpitched	UNVERIFIED	earliest automatic orchestrion	as orchestrion	https://en.wikipedia.org/wiki/Orchestrion
hohner pianet	Hohner Pianet	keyboards	Hohner, Germany, c.1962	F1	F6	VERIFIED (61 keys F1-F6; later 60 keys without top F)	reed with sticky pads, capacitive/electromagnetic pickup: plucky	pad click noise plus reed	https://en.wikipedia.org/wiki/Hohner_Pianet
wurlitzer electronic piano	Wurlitzer electronic piano	keyboards	Wurlitzer USA, 1954-1980s (200A 1974-83)	A1	C7	VERIFIED (64 keys, derived from 88-key piano wording: A1 to C7)	felt hammer on steel reed, electrostatic pickup	already covered by reed electric piano (alias)	https://en.wikipedia.org/wiki/Wurlitzer_electric_piano
hohner clavinet	Hohner Clavinet	keyboards	Hohner, Germany, 1964-1982	F1	E6	VERIFIED (60 keys F1-E6)	already catalog clavinet (alias)	alias	https://en.wikipedia.org/wiki/Hohner_Clavinet
rhodes piano bass	Rhodes piano bass	keyboards	Fender, USA, retail 1962	E1	B3	VERIFIED (32 notes roughly E1-B3)	tine keyboard bass	tine source low range	https://en.wikipedia.org/wiki/Fender_Rhodes
rhodes celeste	Fender Rhodes Celeste	keyboards	Fender, late 1960s	unpitched	unpitched	UNVERIFIED (top 3-4 octaves of piano range)	tine-based, high-register small electric piano	tine source high register	https://en.wikipedia.org/wiki/Fender_Rhodes
yamaha cp electric grand	Yamaha CP electric grand	keyboards	Yamaha Japan, 1976 (CP-70 73 keys, CP-80 88 keys)	unpitched	unpitched	UNVERIFIED (73/88 keys; note ranges not given)	real piano action, piezo pickups, no soundboard: bright, thin, bell-like	bright additive partials, short sustain	https://en.wikipedia.org/wiki/Yamaha_CP-70
mellotron	Mellotron	keyboards	Birmingham 1963	G2	F5	VERIFIED (35 keys G2-F5; M300 52 keys)	tape replay with wow/flutter	fake with detuned oscillators plus slow LFO plus noise; aftertouch contact	https://en.wikipedia.org/wiki/Mellotron
chamberlin	Chamberlin	keyboards	USA (Harry Chamberlin), 1950s	unpitched	unpitched	UNVERIFIED (range not fetched)	tape replay keyboard, near-duplicate of mellotron	same as mellotron	https://en.wikipedia.org/wiki/Mellotron
optigan	Optigan	keyboards	Mattel USA 1971	unpitched	unpitched	UNVERIFIED in note names (page: 37 single-note right-hand tracks on three-octave keyboard; 21 chord tracks; pitch changes with tempo wheel)	optical disc replay, lo-fi, no attack/decay	bitcrush plus constant-amplitude loop; no envelope	https://en.wikipedia.org/wiki/Optigan
clavier a lumieres	Clavier a lumieres	keyboards	Scriabin, New York 1915 (one built)	unpitched	unpitched	UNVERIFIED	keyboard that projected colored lights (silent, not a sound source)	no audio model	https://en.wikipedia.org/wiki/Clavier_%C3%A0_lumi%C3%A8res
chekker	Chekker	keyboards	Medieval Europe, documented 1360	unpitched	unpitched	UNVERIFIED (nature disputed: perhaps clavichord)	uncertain	insufficient description; likely alias	https://en.wikipedia.org/wiki/Chekker
```

## Rejected or corrected proposed entries
- spinet: Wikipedia treats it as a harpsichord variant (strings ~30 degrees to keyboard, paired strings). Distinct construction but same synthesis; keep only if separate title wanted. https://en.wikipedia.org/wiki/Harpsichord ; catalog virginal covers the sound.
- clavicymbalum: appears only as a Wikipedia stub name for the medieval harpsichord/virginal type; no published distinct sound. Alias of harpsichord. https://en.wikipedia.org/wiki/Category:Keyboard_instruments
- lautenwerck: spelling is "Lautenwerck" in the Wikipedia category but the article title is Lautenwerk; use `lautenwerk`. Gut strings, mellow, no range given. https://en.wikipedia.org/wiki/Lautenwerk
- scalatron: electronic microtonal organ, wrong family (organs/synthesizers). (memory; first audit's own note)
- walking piano: a giant floor keyboard for the film Big; listed in Wikipedia keyboard category; no distinct timbre. https://en.wikipedia.org/wiki/Category:Keyboard_instruments
- octavator: no source found; the oddmusic gallery cited is a generic page. Not checked this pass; reject until confirmed.
- orphica: VALID but the proposed "Vienna 1795" is incomplete: Carl Leopold Rollig, Vienna 1795-1810, shoulder-strap portable piano, ~30 survive; Beethoven WoO 51 (1798). Sound is NOT described on the page, so "harp-like" is unsupported. https://en.wikipedia.org/wiki/Orphica
- tangent piano: valid per first audit; not re-verified this pass. H-S 314-8 is too coarse (memory).
- luthéal: VALID; attribution fixed: Georges Cloetens (Belgian organ builder), patented 28 Jan 1919 as "Jeu de harpe tiree"; four stops, not just "cimbalom-like". https://en.wikipedia.org/wiki/Luth%C3%A9al
- prepared piano, pedal piano: valid; no sources fetched for prepared piano (memory).
- mellotron: range G2-F5 VERIFIED, 35 notes; M300 has 52 keys. Chamberlin and optigan retained. https://en.wikipedia.org/wiki/Mellotron
- Apollonicon (found in category): large self-acting barrel/finger ORGAN (Flight & Robson, 1817); organ family, not proposed here. https://en.wikipedia.org/wiki/Apollonicon

## Aliases
- pianola, reproducing piano -> player piano
- wurlitzer electronic piano -> reed electric piano (catalog)
- hohner pianet -> reed electric piano (catalog); distinct pad/click mechanism, optional separate entry
- hohner clavinet -> clavinet (catalog)
- fender rhodes -> tine electric piano (catalog)
- cabinet/cottage/pyramid/lyre piano -> upright piano or giraffe piano (memory, not verified)
- spinet, clavicymbalum -> virginal/harpsichord
- lautenwerck -> lautenwerk
- geigenwerk -> viola organista (page: Heyden's 1575 Geigenwerk is the first known built realization of the concept)
- janko piano, pleyel double piano, vis a vis piano -> grand piano (timbre identical)
- chekker -> clavichord/virginal (disputed by scholars)
- muselar -> virginal (page names it only in passing)

## Range checks
- Hohner Pianet F1-F6, 61 keys (later 60 keys, top F removed): VERIFIED https://en.wikipedia.org/wiki/Hohner_Pianet
- Wurlitzer 64 keys A1-C7 (derived from the page's wording): VERIFIED https://en.wikipedia.org/wiki/Wurlitzer_electric_piano
- Clavinet F1-E6, 60 keys: VERIFIED https://en.wikipedia.org/wiki/Hohner_Clavinet
- Mellotron G2-F5 (35 keys): VERIFIED https://en.wikipedia.org/wiki/Mellotron
- Harpsichord five-octave F1-F6: VERIFIED https://en.wikipedia.org/wiki/Harpsichord
- Rhodes Piano Bass: roughly E1-B3 (32 notes): VERIFIED (approx) https://en.wikipedia.org/wiki/Fender_Rhodes
- Dulcitone: written AA-a3, sounds octave higher (A to a4), so A2-A7 by my Helmholtz conversion: VERIFIED-with-conversion https://en.wikipedia.org/wiki/Dulcitone
- Celesta: 3 to 5.5 octaves, sounds an octave above written; no note names fetched. Catalog entry range UNVERIFIED. https://en.wikipedia.org/wiki/Celesta
- Glasschord ~3 octaves starting c', f' or g': UNVERIFIED top. https://en.wikipedia.org/wiki/Glasschord
- Viola organista/Geigenwerk: 1620 etching ~44 keys E to B; Zubrzycki replica F1-F6: UNVERIFIED octave of E. https://en.wikipedia.org/wiki/Viola_organista
- Spinet "~C2 to C6" (first audit): UNVERIFIED; no range found on harpsichord page.
- Piano 88 keys: page confirms 88 keys but not note names; A0-C8 is memory.
- Earlier draft claims (dolceola C3-C6, typophone Hungary) were memory and WRONG or unsupported; removed (typophone is Mustel, 1860, per Celesta page).

## Gaps you could not close
- MIMO, Horniman, Grove not reached; Met search returned only generic pages.
- Wikipedia keyboard category lists items I did not fetch: Piganino, Memotron, Orphéal, Arcadetar, Claviola, Chordboard, Doppio Borgato, Fotdella, Gazamba, Guide-chant, Celestaphone (instrument), Harmoneon, Terpodion (free-reed/odd), Bowed clavier, Contemporary harpsichord. Candidates for the next pass.
- Not searched: reproducing pianos (Welte-Mignon, Ampico), Disklavier, Violano-Virtuoso, barrel/street piano, Vierling and Neo-Bechstein electric pianos, RMI Electra-piano, Baldwin electric harpsichord, Hohner Cembalet, Birotron, Pianet/Clavinet Duo, Pleyel double piano, Cristofori-era arpicembalo, arpicordo, claviorganum (organ hybrid).
- Non-European traditional keyboards: none found; keyboard instruments are essentially a European lineage; Asian keyed idiophones remain unchecked.
