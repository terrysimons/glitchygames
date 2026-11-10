# Tuned percussion audit (round 2)

Research method: about 28 WebFetch/WebSearch calls, mostly Wikipedia pages (Boomwhackers, Great Stalacpipe Organ, Steelpan, Gamelan, Balinese gamelan, Orff Schulwerk, Lamellophone, Thai xylophone, Bianzhong, Pyeongyeong, Kulintang, Timpani, Gyil, Hang, Marimba, Amadinda, Teponaztli, Cristal Baschet, Angklung, Roto-tom, Glass harp, Lithophone, Slit drum) plus one web search for tubulum. Two fetches 404'd (Tubulum and Harry Partch's instruments pages on Wikipedia), so the Partch entries were NOT re-checked. MIMO, the Met and the Horniman were not queried. Wikipedia rarely gives ranges for non-Western instruments, so most new entries have `unknown` lows and highs, marked UNVERIFIED. Lowest and highest are never filled from memory. Anything marked "(memory)" is not from a fetched source.

## Summary

- New missing instruments found: 110 (TSV below; mostly gamelan, Southeast Asian, steelpan and Orff size variants plus distinct regional types).
- Proposed entries rejected or moved: 5 outright (marble machine, gameleste, stamenphone, singing stones, trongos), 9 Partch one-offs flagged low priority, 3 aliases (hank drum, hapi drum, boomwhacker).
- Aliases: about 17 (see list).
- Range fixes: boomwhackers (C2-G5 verified), boomwhacker H-S number (413 is wrong), great stalacpipe organ (source says one octave, 37 stalactites: matches proposal), angklung (G2-C6 verified, H-S 111.232), cristal baschet (verified).
- Family decisions: timpani stays in tuned percussion (catalog already there). Roto-toms go to tuned percussion too (defined pitch is their design purpose, per Wikipedia), though a catalog owner might prefer drums and percussion since the toms live there. Octobans, boobam, pat waing: same reasoning.

## New missing instruments

Columns: name, title, family, origin, lowest, highest, range_status, sound, modeling_notes, source_urls.

```tsv
name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls
soprano glockenspiel	Soprano glockenspiel (Orff)	tuned percussion	Germany (Orff Schulwerk)	unknown	unknown	UNVERIFIED	bright metal bars, short ring	inharmonic bar partials, glockenspiel recipe at another register	https://en.wikipedia.org/wiki/Orff_Schulwerk (type only; no ranges given)
alto glockenspiel	Alto glockenspiel (Orff)	tuned percussion	Germany	unknown	unknown	UNVERIFIED	metal bars, softer than soprano	as glockenspiel	https://en.wikipedia.org/wiki/Orff_Schulwerk
soprano metallophone	Soprano metallophone (Orff)	tuned percussion	Germany	unknown	unknown	UNVERIFIED	metal bars on resonator box, longer ring than glockenspiel	vibraphone-like without motor	https://en.wikipedia.org/wiki/Orff_Schulwerk
alto metallophone	Alto metallophone (Orff)	tuned percussion	Germany	unknown	unknown	UNVERIFIED	as above, lower	as above	https://en.wikipedia.org/wiki/Orff_Schulwerk
bass metallophone	Bass metallophone (Orff)	tuned percussion	Germany	unknown	unknown	UNVERIFIED	as above, low	long decay, needs strong fundamental	https://en.wikipedia.org/wiki/Orff_Schulwerk
soprano xylophone	Soprano xylophone (Orff)	tuned percussion	Germany	unknown	unknown	UNVERIFIED	hard wood bars, short	short click plus bar partials	https://en.wikipedia.org/wiki/Orff_Schulwerk
alto xylophone	Alto xylophone (Orff)	tuned percussion	Germany	unknown	unknown	UNVERIFIED	as above, lower	as above	https://en.wikipedia.org/wiki/Orff_Schulwerk
bass xylophone	Bass xylophone (Orff)	tuned percussion	Germany	unknown	unknown	UNVERIFIED	as above, low	as above	https://en.wikipedia.org/wiki/Orff_Schulwerk
bell lyra	Bell lyra (marching glockenspiel)	tuned percussion	Europe/USA marching bands	unknown	unknown	UNVERIFIED	glockenspiel bars in a lyre frame	as glockenspiel	(memory)
resonator bells	Resonator bells (tone bars)	tuned percussion	educational, USA/Europe	unknown	unknown	UNVERIFIED	single-note metal bars on blocks	as glockenspiel	(memory)
choirchimes	Choirchimes (hand chimes)	tuned percussion	USA (Malmark)	unknown	unknown	UNVERIFIED	aluminium tube with clapper, soft chime	as handbells but gentler	(memory)
tubaphone	Tubaphone	tuned percussion	France, 19th c.	unknown	unknown	UNVERIFIED	metal tubes struck, glockenspiel-like	as small tubular bells	(memory)
almglocken	Almglocken (tuned cowbells)	tuned percussion	Alpine Europe	unknown	unknown	UNVERIFIED	chromatic set of tuned cowbells, clacky	short inharmonic bell, strong attack	(memory)
piccolo timpani	Piccolo timpani	tuned percussion	orchestral	unknown	C4	PARTIAL (top reaches C4 for a 20 in drum; lowest not given)	small pitched thump, high	as timpani, shorter decay	https://en.wikipedia.org/wiki/Timpani
roto toms	Roto-toms (rototoms)	tuned percussion	USA (Al Payson, Michael Colgrass)	unknown	unknown	UNVERIFIED (practical range about a sixth per Remo; 6 to 18 in sizes verified)	shell-less pitched tom, tuned by rotating the head	pitch glide at attack; family decision in Notes	https://en.wikipedia.org/wiki/Roto-tom
octobans	Octobans	tuned percussion	modern kit percussion	unknown	unknown	UNVERIFIED	long thin pitched drums, boomy	toms with defined pitch	(memory)
boobam	Boobam (bamboo tube drums)	tuned percussion	modern	unknown	unknown	UNVERIFIED	tuned tubes with membranes, hollow thump	noise burst plus sine	(memory)
tubulum	Tubulum (PVC pipe percussion)	tuned percussion	modern (popularized by Blue Man Group)	unknown	unknown	UNVERIFIED	hollow whomp from open tubes struck by flaps or sticks	Helmholtz-like: sine plus air-noise burst, short decay	https://wiki.stadtfabrikanten.org/books/projekte-und-anleitungen/page/diy-tubulum/export/pdf (and web search results)
soprano steel pan	Ping pong (single tenor) steel pan	tuned percussion	Trinidad (Winston Simon)	unknown	unknown	UNVERIFIED (overall steelpan A1-G6 only)	bright steel pan, soprano register	as tenor steel pan	https://en.wikipedia.org/wiki/Steelpan
double tenor steel pan	Double tenor steel pan	tuned percussion	Trinidad (Bertie Marshall)	unknown	unknown	UNVERIFIED	mezzo register pan pair	as tenor steel pan	https://en.wikipedia.org/wiki/Steelpan
double guitar steel pan	Double guitar steel pan	tuned percussion	Trinidad (Jonathan Francis)	unknown	unknown	UNVERIFIED	tenor register pan pair	as above	https://en.wikipedia.org/wiki/Steelpan
triple guitar steel pan	Triple guitar steel pan	tuned percussion	Trinidad (Ellie Mannette)	unknown	unknown	UNVERIFIED	baritone register	as above	https://en.wikipedia.org/wiki/Steelpan
quadrophonic steel pan	Quadrophonic steel pan	tuned percussion	Trinidad (Rudolph Charles)	unknown	unknown	UNVERIFIED	tenor register, four pans	as above	https://en.wikipedia.org/wiki/Steelpan
tenor bass steel pan	Tenor bass steel pan	tuned percussion	Trinidad (Ellie Mannette)	unknown	unknown	UNVERIFIED	bass register	as bass steel pan	https://en.wikipedia.org/wiki/Steelpan
six bass steel pan	Six bass steel pan	tuned percussion	Trinidad (Ellie Mannette)	unknown	unknown	UNVERIFIED	bass register, six barrels	as bass steel pan; very low fundamentals	https://en.wikipedia.org/wiki/Steelpan
nine bass steel pan	Nine bass steel pan	tuned percussion	Trinidad (Rudolph Charles)	unknown	unknown	UNVERIFIED	bass register	as above	https://en.wikipedia.org/wiki/Steelpan
twelve bass steel pan	Twelve bass steel pan	tuned percussion	Trinidad (Rudolph Charles)	unknown	unknown	UNVERIFIED	bass register	as above	https://en.wikipedia.org/wiki/Steelpan
steel tongue drum	Steel tongue drum (tank drum)	tuned percussion	modern	unknown	unknown	UNVERIFIED	mellow tonal tongues	sine plus soft partial, medium decay	(memory); https://en.wikipedia.org/wiki/Slit_drum points to a separate steel-tongue-drum article not read
marimba de tecomates	Marimba de tecomates	tuned percussion	Guatemala/Chiapas (documented 1680)	unknown	unknown	UNVERIFIED	marimba with gourd resonators; buzzing membranes (memory)	marimba plus noisy buzz layer	https://en.wikipedia.org/wiki/Marimba
marimba de chonta	Marimba de chonta	tuned percussion	Colombia (Choco, Cauca)	unknown	unknown	UNVERIFIED	peach-palm wood bars	marimba, woodier	https://en.wikipedia.org/wiki/Marimba
marimba esmeraldena	Marimba esmeraldena	tuned percussion	Ecuador (Esmeraldas)	unknown	unknown	UNVERIFIED	as above	as above	https://en.wikipedia.org/wiki/Marimba
zimbabwean marimba	Zimbabwean marimba	tuned percussion	Zimbabwe	unknown	unknown	UNVERIFIED	bars with resonators plus buzzing membranes (memory)	marimba plus buzz; soprano/tenor/baritone/bass sizes are memory, add only one entry unless wanted	https://en.wikipedia.org/wiki/Lamellophone (name only)
gyil	Gyil (gyile)	tuned percussion	Ghana, Burkina Faso (Dagara, Birifor)	unknown	unknown	UNVERIFIED (17 keys over gourds verified)	wood keys over gourds, spider-silk buzz (buzz memory)	balafon-style buzz	https://en.wikipedia.org/wiki/Gyil
amadinda	Amadinda	tuned percussion	Buganda, Uganda	unknown	unknown	UNVERIFIED (12 logs, pentatonic verified)	dry log xylophone, no resonators, no buzz	short woody	https://en.wikipedia.org/wiki/Amadinda
akadinda	Akadinda	tuned percussion	Buganda, Uganda	unknown	unknown	UNVERIFIED	larger log xylophone (key count not found)	as amadinda	https://en.wikipedia.org/wiki/Amadinda
embaire	Embaire	tuned percussion	southern Uganda	unknown	unknown	UNVERIFIED	xylophone, same notation as amadinda	woody	https://en.wikipedia.org/wiki/Amadinda
timbila	Timbila (Chopi)	tuned percussion	Mozambique	unknown	unknown	UNVERIFIED	gourd-resonated xylophone with buzz (memory)	marimba plus buzz	(memory)
likembe	Likembe	tuned percussion	DR Congo	unknown	unknown	UNVERIFIED	plucked metal tongues on a box	plucked tines, optional buzz	https://en.wikipedia.org/wiki/Lamellophone
marimbula	Marimbula	tuned percussion	Caribbean (Cuba)	unknown	unknown	UNVERIFIED	bass lamellophone, thumpy	low sine pluck with box resonance	https://en.wikipedia.org/wiki/Lamellophone
bass kalimba	Bass kalimba	tuned percussion	modern	unknown	unknown	UNVERIFIED	lower kalimba	as kalimba	(memory)
mbira dza vadzimu	Mbira dza vadzimu	tuned percussion	Zimbabwe (Shona)	unknown	unknown	UNVERIFIED	keys on soundboard in gourd, bottle-cap buzz (memory)	plucked tine plus noisy buzz	(memory); https://en.wikipedia.org/wiki/Lamellophone lists Shona mbira
jaw harp	Jaw harp (jews harp)	tuned percussion	worldwide	unknown	unknown	UNVERIFIED	plucked reed, mouth-shaped overtones	needs sweepable formant filter; one drone note	https://en.wikipedia.org/wiki/Lamellophone
khomus	Khomus	tuned percussion	Sakha (Yakutia)	unknown	unknown	UNVERIFIED	jaw harp	as jaw harp	https://en.wikipedia.org/wiki/Lamellophone (name only)
dan moi	Dan moi	tuned percussion	Vietnam	unknown	unknown	UNVERIFIED	bamboo jaw harp	as jaw harp	https://en.wikipedia.org/wiki/Lamellophone
murchunga	Murchunga	tuned percussion	Nepal	unknown	unknown	UNVERIFIED	jaw harp	as jaw harp	https://en.wikipedia.org/wiki/Lamellophone
slenthem	Gamelan slenthem	tuned percussion	Java	unknown	unknown	UNVERIFIED	large bronze keys over tubes, deep long hum	long decay, beating	https://en.wikipedia.org/wiki/Gamelan
gender barung	Gamelan gender barung	tuned percussion	Java	unknown	unknown	UNVERIFIED	bronze keys over bamboo resonators, shimmer	resonator-tuned partials, slight beating	https://en.wikipedia.org/wiki/Gamelan
gender panerus	Gamelan gender panerus	tuned percussion	Java	unknown	unknown	UNVERIFIED	octave above barung	as above	https://en.wikipedia.org/wiki/Gamelan
gender rambat	Balinese gender rambat	tuned percussion	Bali	unknown	unknown	UNVERIFIED	bronze keys, shimmer	needs beating pairs (ombak)	https://en.wikipedia.org/wiki/Gamelan
demung	Gamelan saron demung	tuned percussion	Java	unknown	unknown	UNVERIFIED	lowest saron	as saron	https://en.wikipedia.org/wiki/Gamelan
saron barung	Gamelan saron barung (ricik)	tuned percussion	Java	unknown	unknown	UNVERIFIED	middle saron (catalog saron may already mean this)	as saron	https://en.wikipedia.org/wiki/Gamelan
peking	Gamelan saron peking	tuned percussion	Java	unknown	unknown	UNVERIFIED	highest saron, bright	as saron	https://en.wikipedia.org/wiki/Gamelan
bonang barung	Gamelan bonang barung	tuned percussion	Java	unknown	unknown	UNVERIFIED	row of bossed gong kettles	inharmonic gong	https://en.wikipedia.org/wiki/Gamelan
bonang panerus	Gamelan bonang panerus	tuned percussion	Java	unknown	unknown	UNVERIFIED	octave above barung	as above	https://en.wikipedia.org/wiki/Gamelan
bonang penembung	Gamelan bonang penembung	tuned percussion	Java	unknown	unknown	UNVERIFIED	lowest bonang	as above	https://en.wikipedia.org/wiki/Gamelan
kenong	Gamelan kenong	tuned percussion	Java/Bali	unknown	unknown	UNVERIFIED	large pitched kettle gong	as bonang, lower	https://en.wikipedia.org/wiki/Gamelan
kethuk	Gamelan kethuk (kempli)	tuned percussion	Java/Bali	unknown	unknown	UNVERIFIED	small flat dull gong, nearly unpitched	short dead tone	https://en.wikipedia.org/wiki/Gamelan
kempyang	Gamelan kempyang	tuned percussion	Java	unknown	unknown	UNVERIFIED	small kettle gong	as above	https://en.wikipedia.org/wiki/Gamelan
kempul	Gamelan kempul	tuned percussion	Java	unknown	unknown	UNVERIFIED	small hanging gong set	gong with pitch glide	https://en.wikipedia.org/wiki/Gamelan
gong ageng	Gamelan gong ageng	tuned percussion	Java	unknown	unknown	UNVERIFIED	large hanging gong, deep long boom	very long decay, pitch glide, swell	https://en.wikipedia.org/wiki/Gamelan
gong suwukan	Gamelan gong suwukan	tuned percussion	Java	unknown	unknown	UNVERIFIED	smaller hanging gong	as gong ageng	https://en.wikipedia.org/wiki/Gamelan
gambang	Gamelan gambang	tuned percussion	Java	unknown	unknown	UNVERIFIED	wooden bar xylophone	woody	https://en.wikipedia.org/wiki/Gamelan
gangsa	Balinese gangsa (pemade)	tuned percussion	Bali	unknown	unknown	UNVERIFIED	keys on frame, damped	beating pair	https://en.wikipedia.org/wiki/Gamelan
kantilan	Balinese kantilan	tuned percussion	Bali	unknown	unknown	UNVERIFIED	highest gangsa	as above	https://en.wikipedia.org/wiki/Gamelan
ugal	Balinese ugal (jiyeng)	tuned percussion	Bali	unknown	unknown	UNVERIFIED	leader metallophone	as above	https://en.wikipedia.org/wiki/Gamelan
jublag	Balinese jublag	tuned percussion	Bali	unknown	unknown	UNVERIFIED	low metallophone	as above	https://en.wikipedia.org/wiki/Gamelan
jegogan	Balinese jegogan	tuned percussion	Bali	unknown	unknown	UNVERIFIED	lowest metallophone	very long decay	https://en.wikipedia.org/wiki/Gamelan
penyacah	Balinese penyacah	tuned percussion	Bali	unknown	unknown	UNVERIFIED	small metallophone	as above	https://en.wikipedia.org/wiki/Gamelan
reyong	Balinese reyong	tuned percussion	Bali	unknown	unknown	UNVERIFIED	row of 12 kettle gongs, four players	as bonang	https://en.wikipedia.org/wiki/Gamelan
trompong	Balinese trompong	tuned percussion	Bali	unknown	unknown	UNVERIFIED	row of 10 kettle gongs	as bonang	https://en.wikipedia.org/wiki/Gamelan
kempur	Balinese kempur	tuned percussion	Bali	unknown	unknown	UNVERIFIED	mid hanging gong	as gong ageng	https://en.wikipedia.org/wiki/Gamelan
rindik	Balinese rindik	tuned percussion	Bali	unknown	unknown	UNVERIFIED	bamboo xylophone	woody hollow	https://en.wikipedia.org/wiki/Angklung (name only)
jegog	Jegog (Jembrana bamboo)	tuned percussion	Bali (Jembrana)	unknown	unknown	UNVERIFIED	giant bamboo tubes, deep	low hollow resonance	(memory); https://en.wikipedia.org/wiki/Balinese_gamelan lists gamelan jegog
jengglong	Jengglong (Sundanese)	tuned percussion	West Java	unknown	unknown	UNVERIFIED	set of kettle gongs	as bonang	(memory)
talempong	Talempong	tuned percussion	Minangkabau, Sumatra	unknown	unknown	UNVERIFIED	small bossed gongs	as bonang	(memory)
kolintang	Kolintang (Minahasa)	tuned percussion	Sulawesi	unknown	unknown	UNVERIFIED	wooden bar xylophone	woody	(memory)
kulintang	Kulintang	tuned percussion	Philippines (Maguindanao)	unknown	unknown	UNVERIFIED (5 to 9 gongs verified)	row of graduated pot gongs	as bonang	https://en.wikipedia.org/wiki/Kulintang
gandingan	Gandingan	tuned percussion	Maguindanao	unknown	unknown	UNVERIFIED	set of three or four gongs	as bonang	https://en.wikipedia.org/wiki/Kulintang
agung	Agung (Maguindanao)	tuned percussion	Philippines	unknown	unknown	UNVERIFIED	large suspended gong	as gong ageng	https://en.wikipedia.org/wiki/Kulintang
babandil	Babandil	tuned percussion	Philippines	unknown	unknown	UNVERIFIED	suspended gong	as above	https://en.wikipedia.org/wiki/Kulintang
ranat ek	Ranat ek	tuned percussion	Thailand	unknown	unknown	UNVERIFIED (22 keys verified)	wooden bars on boat resonator, bright	woody short	https://en.wikipedia.org/wiki/Thai_xylophone
ranat thum	Ranat thum	tuned percussion	Thailand	unknown	unknown	UNVERIFIED	lower, wider	as above	https://en.wikipedia.org/wiki/Thai_xylophone
ranat ek lek	Ranat ek lek	tuned percussion	Thailand	unknown	unknown	UNVERIFIED	metal bars	as glockenspiel	https://en.wikipedia.org/wiki/Thai_xylophone
ranat thum lek	Ranat thum lek	tuned percussion	Thailand	unknown	unknown	UNVERIFIED	low metal bars	as above	https://en.wikipedia.org/wiki/Thai_xylophone
ranat kaeo	Ranat kaeo (glass)	tuned percussion	Thailand	unknown	unknown	UNVERIFIED	glass bars	bright glassy	https://en.wikipedia.org/wiki/Thai_xylophone
khong wong yai	Khong wong yai	tuned percussion	Thailand	unknown	unknown	UNVERIFIED	large circle of kettle gongs	as bonang	https://en.wikipedia.org/wiki/Thai_xylophone (name only)
khong wong lek	Khong wong lek	tuned percussion	Thailand	unknown	unknown	UNVERIFIED	small circle of gongs	as bonang	https://en.wikipedia.org/wiki/Thai_xylophone (name only)
roneat ek	Roneat ek	tuned percussion	Cambodia	unknown	unknown	UNVERIFIED	wooden bars, Khmer ranat	woody	(memory)
pattala	Pattala	tuned percussion	Myanmar	unknown	unknown	UNVERIFIED	Burmese xylophone	woody	(memory)
kyi waing	Kyi waing	tuned percussion	Myanmar	unknown	unknown	UNVERIFIED	circle of gongs	as bonang	(memory)
pat waing	Pat waing (drum circle)	tuned percussion	Myanmar	unknown	unknown	UNVERIFIED	circle of tuned drums	pitched drum thumps; pitched-drum family decision	(memory)
dan t rung	Dan T'rung (bamboo xylophone)	tuned percussion	Vietnam highlands	unknown	unknown	UNVERIFIED	bamboo tubes	hollow woody	(memory)
dan da	Dan da (lithophone)	tuned percussion	Vietnam	unknown	unknown	UNVERIFIED (11 schist plates, pentatonic, 1949 find, verified)	stone plates, dry clink	inharmonic stone	https://en.wikipedia.org/wiki/Lithophone
hokyo	Hokyo (sanukite lithophone)	tuned percussion	Japan	unknown	unknown	UNVERIFIED	stone bar clink	as lithophone	https://en.wikipedia.org/wiki/Lithophone
lithophone	Lithophone	tuned percussion	worldwide	C3	C5	VERIFIED for one stone marimba (photo caption), not for the type	hard stone clink	inharmonic short	https://en.wikipedia.org/wiki/Lithophone
fangxiang	Fangxiang	tuned percussion	China (Tang)	unknown	unknown	UNVERIFIED	iron-slab metallophone	metallic clang	(memory)
banghyang	Banghyang	tuned percussion	Korea	unknown	unknown	UNVERIFIED	iron plate metallophone	as fangxiang	(memory)
pyeonjong	Pyeonjong	tuned percussion	Korea	unknown	unknown	UNVERIFIED	hung bronze bell set, imported from Song China	inharmonic bell	https://en.wikipedia.org/wiki/Bianzhong
pyeongyeong	Pyeongyeong	tuned percussion	Korea	unknown	unknown	UNVERIFIED (Chinese replica set reaches up to 3 octaves only)	hung L-shaped stone chimes, imported 1116	as bianqing	https://en.wikipedia.org/wiki/Pyeongyeong
unra	Unra (Korean cloud gong)	tuned percussion	Korea	unknown	unknown	UNVERIFIED	set of ten small gongs (equals yunluo; memory)	as yunluo	(memory)
bonsho	Bonsho (Japanese temple bell)	tuned percussion	Japan	unknown	unknown	UNVERIFIED	large bell struck with log, deep long hum	inharmonic long decay, beating	(memory)
rin	Rin (Japanese bowl bell)	tuned percussion	Japan	unknown	unknown	UNVERIFIED	struck bowl gong	as singing bowl	(memory)
tingsha	Tingsha (Tibetan chimes)	tuned percussion	Tibet	unknown	unknown	UNVERIFIED	pair of small cymbals struck together	inharmonic bell, long decay	(memory)
teponaztli	Teponaztli	tuned percussion	Aztec Mexico	unknown	unknown	UNVERIFIED (two pitches a third or fourth apart; H-S 111.2 verified)	dull woody pitched slit drum	two-pitch woody thump	https://en.wikipedia.org/wiki/Teponaztli
tunkul	Tunkul	tuned percussion	Maya	unknown	unknown	UNVERIFIED	Maya slit drum, two tongues	as teponaztli	(memory)
musical glasses	Musical glasses (glass harp)	tuned percussion	Europe	G3	E6	VERIFIED (Kling 1905 usual compass; some C4-C6)	wet-finger sine tone, slow onset	friction excitation: filtered noise into sine, slow attack	https://en.wikipedia.org/wiki/Glass_harp
euphon	Euphon (Chladni)	tuned percussion	Germany, 1790	unknown	unknown	UNVERIFIED	stroked glass rods, friction idiophone	sine with slow attack	(memory)
waterphone	Waterphone	tuned percussion	USA (Richard Waters)	unknown	unknown	UNVERIFIED	bowed or struck steel rods, eerie	inharmonic partials with pitch bend	(memory)
zimbelstern	Zimbelstern	tuned percussion	Europe (organs)	unknown	unknown	UNVERIFIED	rotating small tuned bells in organs	random bell chimes; may belong to organs	(memory)
mark tree	Mark tree (bar chimes)	tuned percussion	modern	unknown	unknown	UNVERIFIED	swept row of graded metal bars	glissando of bell tones	(memory)
```

## Rejected or corrected proposed entries

- marble machine: a one-off machine playing a vibraphone, bass and cymbal. Not an instrument class; sounds are covered by vibraphone. Reject. (memory; no source fetched)
- gameleste: a celesta-mechanism instrument (Bjork, Biophilia). Celesta is in the keyboards family, so wrong family. Reject or move to keyboards. (memory)
- stamenphone: could not find any source. Reject as UNVERIFIED.
- singing stones: could not find a source; physically a lithophone. Reject (alias of lithophone).
- trongos: could not find a source. Reject as UNVERIFIED.
- sekkin / lithophone: the slash breaks naming rules and the Wikipedia Lithophone page does not mention "sekkin" (it names hokyo for Japan). Use `lithophone`; add `hokyo` separately. https://en.wikipedia.org/wiki/Lithophone
- boomwhacker (413): duplicate of boomwhackers; "413" is an aerophone number but Wikipedia gives 413, 111.232 (both air and rigid tube). https://en.wikipedia.org/wiki/Boomwhackers
- boomwhackers range: proposed C3-C6 and C2-C7 are both wrong. Wikipedia infobox: C2 to G5. https://en.wikipedia.org/wiki/Boomwhackers
- bianzhong: "each bell gives two pitches about a third apart" is right for Zhou-era bells only; Qin and Tang sets give one pitch per bell. Range of the Marquis Yi set is five octaves, so proposed C3-C6 is too narrow for that set. https://en.wikipedia.org/wiki/Bianzhong
- bianqing: proposed C4-C6 UNVERIFIED; Wikipedia gives only "up to three octaves" for one replica set (via Pyeongyeong page), and sets of 25 and 41 stones. https://en.wikipedia.org/wiki/Pyeongyeong
- angklung: H-S 112.13 is wrong, Wikipedia gives 111.232 (sets of percussion tubes). Also it is shaken, so it sits oddly in "tuned percussion"; keep for the engine but note. https://en.wikipedia.org/wiki/Angklung
- great stalacpipe organ: 37 stalactites verified, range one octave per Wikipedia (the proposal agreed). One-off installation; low priority. https://en.wikipedia.org/wiki/Great_Stalacpipe_Organ
- cristal baschet: verified friction idiophone, 56 glass rods, 3.5 to 6 octaves, concert 5 octaves. It belongs with glass harmonica (catalog keeps it in tuned percussion). https://en.wikipedia.org/wiki/Cristal_Baschet
- wind chimes: borderline pitched; keep but give range as unpitched or very loosely tuned (UNVERIFIED).
- tabla tarang: membranophone (drums); fine under tuned percussion only if pitched-drum family decision above is accepted. UNVERIFIED.
- Partch instruments (diamond marimba, cloud chamber bowls, bamboo marimba (boo), marimba eroica, eucal blossom, gourd tree and cone gongs, zymo xyl, mazda marimba, quadrangularis reversum): could not re-verify (Wikipedia page 404). They are real, but each is a one-off in a 43-tone scale; recommend keeping at most `diamond marimba` and `cloud chamber bowls` and modelling them as marimba and glass bowls. UNVERIFIED.
- hank drum, hapi drum: brand or builder names for a steel tongue drum. Not distinct. See aliases.

## Aliases

- hank drum -> steel tongue drum (proposed)
- hapi drum -> steel tongue drum (proposed)
- tank drum -> steel tongue drum (proposed)
- boomwhacker -> boomwhackers (proposed)
- sekkin -> lithophone (new; unconfirmed that sekkin is a Japanese lithophone)
- singing stones -> lithophone (new)
- verrillon -> musical glasses (new). https://en.wikipedia.org/wiki/Glass_harp
- lead pan, ping pong -> soprano steel pan (new). https://en.wikipedia.org/wiki/Steelpan
- chimes, orchestral chimes -> tubular bells (catalog); orchestra bells -> glockenspiel (catalog); antique cymbals -> crotales (catalog); thumb piano, sanza, sansa -> mbira/kalimba (catalog). https://en.wikipedia.org/wiki/Lamellophone

## Range checks

- boomwhackers: CORRECTED to C2-G5. https://en.wikipedia.org/wiki/Boomwhackers
- angklung: VERIFIED G2-C6. https://en.wikipedia.org/wiki/Angklung
- great stalacpipe organ: VERIFIED one octave. https://en.wikipedia.org/wiki/Great_Stalacpipe_Organ
- cristal baschet: VERIFIED 3.5 to 6 octaves, concert 5 octaves. https://en.wikipedia.org/wiki/Cristal_Baschet
- verrophone: UNVERIFIED (only listed in the Glass harp page, no range).
- musical glasses: VERIFIED G3-E6 usual (Kling 1905), some C4-C6. https://en.wikipedia.org/wiki/Glass_harp
- tuning fork A4: UNVERIFIED (not checked).
- steel tongue drum C3-C6: UNVERIFIED; a photo caption on the Slit drum page gives chromatically tuned slit drums at C3-C4 (not steel). https://en.wikipedia.org/wiki/Slit_drum
- txalaparta, rock gong, calung, yunluo, jal tarang, bianqing, bianzhong (C3-C6): UNVERIFIED.
- yunluo: none checked.
- Existing catalog items checked in passing: marimba ranges A2-C7 (4.3 oct, most common), C2-C7 (5 oct), bass marimba G1-G3 or C2-F3. Timpani standard four drums about D2-A3, each drum a fifth. Handpan/Hang Integral: Ding D3, tone fields A3 to A4. https://en.wikipedia.org/wiki/Marimba https://en.wikipedia.org/wiki/Timpani https://en.wikipedia.org/wiki/Hang_(instrument)

## Modeling difficulty

- Beating pairs (gamelan, ombak tuning): needs two detuned partials per note; possible with 2 oscillators.
- Buzz membranes (balafon, gyil, marimba de tecomates, mbira): noise through band-pass gated by the note envelope; possible but approximate.
- Friction instruments (musical glasses, cristal baschet, euphon, waterphone): slow-attack sine with partials; fine. Waterphone needs pitch bend.
- Pitch glide at attack (timpani, roto-toms, gongs): needs frequency envelope; check support.
- Jaw harps need a time-varying formant filter; not just a pitch.
- Gamelan gong ageng: very long decay and amplitude swell.

## Gaps you could not close

- Ranges for nearly every gamelan, steelpan, Orff and Southeast Asian entry (Wikipedia lacks them; MIMO and Grove were not queried).
- Dulcitone, typophone (tuning-fork keyboards): probably keyboards family; not checked.
- Chinese: yongzhong, bo bell, pengling, yuqing (jade chime), muyu; Japanese hensei/tokkei stone chimes, furin, mokugyo; Korean teukjong, teukgyeong, chuk, eo: suspected, not confirmed.
- Indian: ghatam, kanch tarang, nal; Tibetan drilbu; African ogene, gankogui, ekwe, kisanji, kankobela; Oceanic lali, garamut; Philippine gangsa, tongatong, bungkaka; Caribbean ogan: none confirmed. Drums (mridangam, udu, pakhawaj) belong to the drums agent.
- Nail violin (nagelgeige), clavicylinder, musical saw: friction or bowed idiophones, family unclear.
- Partch details (see above).
