# Voices and choirs audit

Sources actually fetched (18 fetches, read through a summarizer): Wikipedia pages Voice type, Throat singing, Overtone singing, Oktavist, Castrato, Whistle register, Kulning, Yodeling, Katajjaq, Vocoder, Talk box (the Sonovox URL redirected to it), Voder, Human beatboxing, Cantu a tenore, Gregorian chant. Urtiin duu returned 404. No museum database (MIMO, Met, Horniman) was queried for voices, and Grove was not reached. Rows marked "(memory)" were not checked.

## Summary

- New missing: 68 voice rows and 38 choir rows. About 19 voice rows are Fach subtypes that reuse an existing formant row (low value); about 30 are techniques; about 8 are mechanical or electronic voices.
- Proposed entries rejected: 0. Corrected: vocoder, voder (see below). Talk box (proposed by the electrophones audit) is included as a voice row.
- Aliases: 14.
- Range or data fixes: 3 (oktavist range, countertenor source conflict, whistling C5-C7 versus verified whistle register D6-D7).

## New missing instruments

### voices
```tsv
name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls
coloratura soprano ah	Coloratura soprano (ah)	voices	Western opera	C4	F6	PARTIAL (soprano C4-C6, some coloratura roles to F6: Voice type page)	light agile bright head voice	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
soubrette ah	Soubrette (ah)	voices	Western opera	C4	C6	UNVERIFIED (memory; Voice type page gives no subtype ranges)	light, sweet, little vibrato (soubrette named on page)	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
lyric soprano ah	Lyric soprano (ah)	voices	Western opera	C4	C6	UNVERIFIED (memory; Voice type page gives no subtype ranges)	warm legato soprano	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
spinto soprano ah	Spinto soprano (ah)	voices	Western opera	C4	C6	UNVERIFIED (memory; Voice type page gives no subtype ranges)	lyric with dramatic push	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
dramatic soprano ah	Dramatic soprano (ah)	voices	Western opera	A3	C6	PARTIAL (soprano low about A3 verified)	heavy sustained soprano	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
sopranist ah	Sopranist, male soprano (ah)	voices	Western early music	C4	C6	PARTIAL (countertenor text C4-C6, some to F6)	falsetto male soprano	static formant vowel; same formant-table row as an existing voice, so only range/weight differs; countertenor formant row	https://en.wikipedia.org/wiki/Voice_type
castrato ah	Castrato (ah), historical	voices	Italy, 16th-19th c.	C3	D6	PARTIAL (C3 low note verified from Vinci aria for Farinelli; top D6 is memory, page gives none)	boy-bright upper voice with adult chest and breath; only solo recordings are Alessandro Moreschi 1902 and 1904 (Castrato page)	treble formants over strong chest harmonics for C3-G4; no register switch in engine	https://en.wikipedia.org/wiki/Castrato
haute contre ah	Haute-contre (ah)	voices	French Baroque	C3	D5	UNVERIFIED (memory; Voice type page gives no subtype ranges)	high light tenor, head-voice mix	static formant vowel; same formant-table row as an existing voice, so only range/weight differs; tenor/countertenor row	https://en.wikipedia.org/wiki/Voice_type
dramatic mezzo soprano ah	Dramatic mezzo-soprano (ah)	voices	Western opera	F3	C6	PARTIAL (mezzo extremes F3-C6)	dark heavy mezzo	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
dramatic contralto ah	Dramatic contralto (ah)	voices	Western opera	D3	Bb5	PARTIAL (contralto extremes D3-Bb5)	dark low female voice	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
tenore leggero ah	Leggero tenor (ah)	voices	Western opera	C3	D5	UNVERIFIED (memory; Voice type page gives no subtype ranges)	light flexible tenor	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
spinto tenor ah	Spinto tenor (ah)	voices	Western opera	C3	C5	UNVERIFIED (memory; Voice type page gives no subtype ranges)	strong brilliant tenor	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
heldentenor ah	Heldentenor (ah)	voices	Wagner opera	Bb2	C5	PARTIAL (tenor low Bb2 verified)	heroic dark ringing tenor	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
baritenor ah	Baritenor (ah)	voices	Western opera	Bb2	F5	PARTIAL (tenor extremes Bb2-F5)	baritone-colored tenor	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
bass baritone ah	Bass-baritone (ah)	voices	Western opera	F2	F4	UNVERIFIED (memory; Voice type page gives no subtype ranges)	between baritone and bass	static formant vowel; same formant-table row as an existing voice, so only range/weight differs; existing baritone is already a tenor/bass average	https://en.wikipedia.org/wiki/Voice_type
basso buffo ah	Basso buffo (ah)	voices	Italian comic opera	E2	E4	UNVERIFIED (memory; Voice type page gives no subtype ranges)	agile patter bass	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
basso cantante ah	Basso cantante (ah)	voices	Western opera	E2	E4	UNVERIFIED (memory; Voice type page gives no subtype ranges)	lyrical bass	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
dramatic bass ah	Dramatic bass (ah)	voices	Western opera	D2	E4	UNVERIFIED (memory; Voice type page gives no subtype ranges)	heavy dark bass	static formant vowel; same formant-table row as an existing voice, so only range/weight differs	https://en.wikipedia.org/wiki/Voice_type
oktavist ah	Oktavist (ah)	voices	Russian Orthodox choral	A1	G3	PARTIAL (low A1, sometimes F1, extreme C1 verified: Oktavist page; top G3 is memory)	deep basso profondo below bass, Rachmaninoff All-Night Vigil writes to Bb1	bass formant row; fundamental near 55 Hz is weak on small speakers; extreme C1 and subharmonic singers (Castellucci B0, Foust G0 with growl) need a subharmonic source	https://en.wikipedia.org/wiki/Oktavist
boy alto ah	Boy alto (ah)	voices	Church choirs	G3	D5	UNVERIFIED (memory; Voice type page gives no subtype ranges)	lower treble before voice change	static formant vowel; same formant-table row as an existing voice, so only range/weight differs; treble row	https://en.wikipedia.org/wiki/Voice_type
sprechstimme	Sprechstimme	voices	Schoenberg, Pierrot Lunaire 1912	unpitched	unpitched	n/a	speech rhythm with approximate pitch	needs glide and noise-excited formants	https://en.wikipedia.org/wiki/Sprechgesang (not fetched; (memory, no source fetched))
whisper voice	Whispered voice	voices	universal	unpitched	unpitched	n/a	breath noise shaped by vowel formants, no pitch	engine has breath noise + formants; needs a no-harmonic mode	(memory)
falsetto male	Male falsetto	voices	universal	C4	C6	UNVERIFIED (memory)	thin breathy upper register	tenor formants, steeper tilt, more breath	https://en.wikipedia.org/wiki/Voice_type
whistle register	Whistle register (flute voice)	voices	Western popular and classical	D6	D7	VERIFIED (above D6 up roughly an octave to D7)	near-sinusoidal very high voice; users Minnie Riperton, Mariah Carey	almost the existing whistling source; catalog whistling is C5-C7, so this row extends the top by only the D7	https://en.wikipedia.org/wiki/Whistle_register
vocal fry	Vocal fry (pulse register)	voices	universal	B0	B2	UNVERIFIED (memory; page named, no range)	slow glottal pulses	needs low-rate pulse train source	https://en.wikipedia.org/wiki/Throat_singing
belt voice	Belted voice	voices	musical theatre, gospel, rock	F3	F5	UNVERIFIED (memory)	bright loud chest-dominant voice	raised F1 and strong upper harmonics	https://en.wikipedia.org/wiki/Voice_type
growl voice	Growl voice	voices	rock, metal, jazz	unpitched	unpitched	n/a	aryepiglottic folds vibrate with the vocal folds, rough subharmonic buzz (Throat singing page)	needs subharmonic oscillator at 1/2 to 1/4 frequency plus noise	https://en.wikipedia.org/wiki/Throat_singing
khoomei	Khoomei (khoomii, xoomei)	voices	Tuva, Mongolia, Altai	G2	G6	UNVERIFIED (page gives no Hz; Tuvan melodies use harmonics 6,8,9,10,12,13,16: verified)	drone fundamental with a whistle-like harmonic melody above	needs a moving narrow formant tuned to harmonic N of a fixed drone; engine formants do not move with the note. Approximate: fixed drone plus sine at the played note	https://en.wikipedia.org/wiki/Overtone_singing
sygyt	Sygyt	voices	Tuva	G2	G6	UNVERIFIED (memory)	thin sine-like whistle over a drone	easiest overtone style to fake: sine melody over drone	https://en.wikipedia.org/wiki/Overtone_singing
kargyraa	Kargyraa	voices	Tuva	A1	C3	UNVERIFIED (memory; page verifies a deep tense voice with false-fold second source)	extremely low undertone growl with overtones	needs subharmonic source and rasp, plus moving formant	https://en.wikipedia.org/wiki/Overtone_singing ; https://en.wikipedia.org/wiki/Throat_singing
borbangnadyr	Borbangnadyr (Tuvan rolling overtone)	voices	Tuva	G2	G5	UNVERIFIED (memory; named on page as a sub-style)	rolling trilling overtones	needs 5-8 Hz formant LFO	https://en.wikipedia.org/wiki/Overtone_singing
ezengileer	Ezengileer (stirrup song)	voices	Tuva	G2	G5	UNVERIFIED (memory; named as sub-style)	galloping rhythmic overtone	rhythmic formant modulation	https://en.wikipedia.org/wiki/Overtone_singing
chylandyk	Chylandyk (Tuvan cricket style)	voices	Tuva	G2	G5	UNVERIFIED (memory; named on page, no description)	insect-like high overtone style (memory)	as khoomei	https://en.wikipedia.org/wiki/Overtone_singing
dumchuktaar	Dumchuktaar (nasal Tuvan overtone)	voices	Tuva	G2	G5	UNVERIFIED (memory; named on page, no description)	nasal overtone style (memory)	as khoomei	https://en.wikipedia.org/wiki/Overtone_singing
byrlang	Byrlang (Tuvan trill style)	voices	Tuva	G2	G5	UNVERIFIED (memory; named on page, no description)	trilled overtone style (memory)	as borbangnadyr	https://en.wikipedia.org/wiki/Overtone_singing
tibetan chant	Tibetan multiphonic chant	voices	Tibet and exile India	B1	B2	UNVERIFIED (memory; page confirms vocal-ventricular fold phonation)	very low drone with audible upper partial	stationary formant fits the engine well	https://en.wikipedia.org/wiki/Throat_singing
katajjaq	Katajjaq (Inuit throat singing)	voices	Canada (Nunavut, Nunavik)	unpitched	unpitched	n/a (page gives no pitch)	two women trade rhythmic voiced and unvoiced inhaled/exhaled sounds; described as rhythmic harmonious panting	noise bursts with inhale and exhale envelopes; no duet turn-taking	https://en.wikipedia.org/wiki/Katajjaq
rekuhkara	Rekuhkara (Ainu)	voices	Hokkaido, Japan	unpitched	unpitched	n/a	Ainu women's breath-trading game, now rare	as katajjaq	https://en.wikipedia.org/wiki/Throat_singing
umngqokolo	Umngqokolo (Xhosa overtone singing)	voices	South Africa	G2	G5	UNVERIFIED (memory; throat singing page only links Xhosa music)	growl drone with overtone melody	as kargyraa	https://en.wikipedia.org/wiki/Throat_singing
yodel	Yodel	voices	Alps; Central African pygmies; Georgian krimanchuli	C3	C6	UNVERIFIED (page gives no pitch; chest to falsetto switching verified)	rapid chest to falsetto register alternation	needs a register switch per note: two formant/spectral sets plus fast big jumps	https://en.wikipedia.org/wiki/Yodeling
kulning	Kulning (Scandinavian herding call)	voices	Sweden, Norway	C5	C7	UNVERIFIED (page gives no range; high-pitched non-vibrato head tone, partials up to 16 kHz)	loud piercing call with half and quarter tones	whistle-like with strong 2-4 kHz band; needs microtonal glide	https://en.wikipedia.org/wiki/Kulning
joik	Joik	voices	Sami, Fennoscandia	C3	C5	UNVERIFIED (memory, not fetched)	chant-like throaty vocal	chest formants plus rasp	https://en.wikipedia.org/wiki/Joik
urtiin duu	Urtiin duu (Mongolian long song)	voices	Mongolia	G2	G5	UNVERIFIED (memory; Wikipedia article URL returned 404)	slow melismatic song with shaken ornament	needs pitch LFO ornament	(memory; Urtiin_duu URL 404)
scat singing	Scat singing	voices	USA jazz	C3	C6	UNVERIFIED (memory)	wordless syllables as improvisation	needs consonant bursts	https://en.wikipedia.org/wiki/Scat_singing
beatbox kick	Beatbox kick	voices	1980s New York hip hop	unpitched	unpitched	n/a	bilabial [b] thump, imitates Roland TR-808 (Human beatboxing page)	sine with pitch fall; belongs near drum voices	https://en.wikipedia.org/wiki/Human_beatboxing
beatbox snare	Beatbox snare	voices	hip hop	unpitched	unpitched	n/a	voiceless velar [k] burst	short filtered noise burst	https://en.wikipedia.org/wiki/Human_beatboxing
beatbox hihat	Beatbox hi-hat	voices	hip hop	unpitched	unpitched	n/a	affricate [ts] hiss	high-pass noise	https://en.wikipedia.org/wiki/Human_beatboxing
mouth bass	Vocal bass line (beatbox)	voices	hip hop	E1	E3	UNVERIFIED (memory; page lists bass lines as a separate effect)	low lip-buzz bassline	low sine/triangle with AM buzz	https://en.wikipedia.org/wiki/Human_beatboxing
tongue click	Click consonant (Xhosa, Khoisan)	voices	Southern Africa	unpitched	unpitched	n/a	sharp clicks used rhythmically	very short noise ping with pitch fall	https://en.wikipedia.org/wiki/Click_consonant (not fetched)
ululation	Ululation	voices	Middle East and Africa	C5	C6	UNVERIFIED (memory)	high tongue-fluttered trill	8-10 Hz flutter	https://en.wikipedia.org/wiki/Ululation (not fetched)
silbo whistle	Silbo Gomero whistled speech	voices	La Gomera	C5	C7	UNVERIFIED (memory)	carrying whistled pitch contours	as whistling with glide	https://en.wikipedia.org/wiki/Silbo_Gomero (not fetched)
lilting	Lilting and puirt a beul	voices	Scotland, Ireland	C3	C5	UNVERIFIED (memory)	mouth music syllables imitating dance instruments	as scat	(memory)
pansori voice	Pansori rasp voice	voices	Korea	A2	A4	UNVERIFIED (memory)	hoarse forceful chest voice	rasp and glide	https://en.wikipedia.org/wiki/Pansori (not fetched)
jingju xiaosheng	Jingju young male falsetto (xiaosheng)	voices	Beijing opera	C4	C6	UNVERIFIED (memory)	thin bright falsetto	as falsetto male	(memory)
jingju dan	Jingju female role (dan) voice	voices	Beijing opera	C4	C6	UNVERIFIED (memory)	thin falsetto female role	as falsetto male	(memory)
shomyo chant	Shomyo	voices	Japanese Buddhist chant	C3	C4	UNVERIFIED (memory)	unison chant with glides, no vibrato	long glide	https://en.wikipedia.org/wiki/Shōmyō (not fetched)
dhrupad alap voice	Dhrupad alap voice	voices	North India	C3	C5	UNVERIFIED (memory)	slow vowel exploration over tanpura with glides	needs meend glide	(memory)
qawwali voice	Qawwali lead voice	voices	South Asia	C3	C5	UNVERIFIED (memory)	open-throated improvised runs	fast ornament	(memory)
adhan voice	Adhan (maqam chant)	voices	Islamic world	A2	A4	UNVERIFIED (memory)	unaccompanied call in maqam with quarter tones	microtonal glide	(memory)
cantorial voice	Cantorial voice (hazzan)	voices	Jewish liturgy	B2	B4	UNVERIFIED (memory)	ornamented tenor with sobs	needs ornament	(memory)
hawaiian falsetto	Hawaiian falsetto (leo ki'eki'e)	voices	Hawaii	C4	C6	UNVERIFIED (memory)	male falsetto with sob break	as falsetto male	(memory)
vocoder voice	Vocoder voice (robot vowel)	voices	Homer Dudley, Bell Labs: developed from 1928, patents 1937 and 1939	C2	C7	VERIFIED construction (carrier of noise or sawtooth through 8-20 band-pass filters, Vocoder page); note range is mine, vocoder follows carrier	robot speech	the real thing needs a modulator input and band envelope followers; the engine can only do a static robot vowel (sawtooth plus formants)	https://en.wikipedia.org/wiki/Vocoder
talk box	Talk box	voices	Alvino Rey 1939 (throat mic), Pete Drake 1964, Kustom The Bag 1969, Heil 1971-74	C2	C6	n/a follows source	instrument fed by tube into the mouth so the player shapes words	engine can sweep between vowel formant sets only if per-note formant interpolation is added	https://en.wikipedia.org/wiki/Talk_box
sonovox	Sonovox	voices	Gilbert Wright, 1939	C2	C6	n/a follows source	transducers on the throat drive the vocal tract; used in radio jingles and early film	as talk box	https://en.wikipedia.org/wiki/Talk_box
electrolarynx	Electrolarynx	voices	Bell Labs early 20th c. (memory)	C2	C4	UNVERIFIED (memory)	flat buzzing monotone	pulse train near 100 Hz through vowel formants	https://en.wikipedia.org/wiki/Electrolarynx (not fetched)
speech synth lpc	LPC speech chip voice	voices	Texas Instruments 1978 (memory)	C2	C6	UNVERIFIED (memory)	buzzy pulse-excited vowels and fricatives	pulse source plus formants and noise; consonant frames need automation	https://en.wikipedia.org/wiki/Linear_predictive_coding (not fetched; Vocoder page names LPC as later widely used technique)
vox humana	Vox humana (organ stop)	voices	Europe 17th c.	C2	C7	UNVERIFIED (memory)	small reed pipes with tremulant, nasal	reed plus formants; check organ family	https://en.wikipedia.org/wiki/Vox_humana (not fetched)
voix celeste	Voix celeste	voices	organ stop 19th c.	C2	C7	UNVERIFIED (memory)	two ranks slightly detuned, shimmer	detuned pair via chorus_cents	https://en.wikipedia.org/wiki/Voix_c%C3%A9leste (not fetched)
```

### choirs
```tsv
name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls
choir soprano eh	Choir sopranos (eh)	choirs	SATB	C4	A5	existing catalog range, UNVERIFIED		fills the vowel set; formant data already in FORMANT_TABLE	https://csound.com/docs/manual/MiscFormants.html
choir soprano ee	Choir sopranos (ee)	choirs	SATB	C4	A5	existing catalog range, UNVERIFIED		fills the vowel set; formant data already in FORMANT_TABLE	https://csound.com/docs/manual/MiscFormants.html
choir soprano hum	Choir sopranos (humming)	choirs	bocca chiusa	C4	A5	existing catalog range, UNVERIFIED	closed-mouth hum; solo voices have hum, choirs do not	HUM_FORMANTS already defined	(code: voices.py)
choir alto eh	Choir altos (eh)	choirs	SATB	G3	D5	existing catalog range, UNVERIFIED		fills the vowel set; formant data already in FORMANT_TABLE	https://csound.com/docs/manual/MiscFormants.html
choir alto ee	Choir altos (ee)	choirs	SATB	G3	D5	existing catalog range, UNVERIFIED		fills the vowel set; formant data already in FORMANT_TABLE	https://csound.com/docs/manual/MiscFormants.html
choir alto hum	Choir altos (humming)	choirs	bocca chiusa	G3	D5	existing catalog range, UNVERIFIED	closed-mouth hum; solo voices have hum, choirs do not	HUM_FORMANTS already defined	(code: voices.py)
choir tenor eh	Choir tenors (eh)	choirs	SATB	C3	A4	existing catalog range, UNVERIFIED		fills the vowel set; formant data already in FORMANT_TABLE	https://csound.com/docs/manual/MiscFormants.html
choir tenor ee	Choir tenors (ee)	choirs	SATB	C3	A4	existing catalog range, UNVERIFIED		fills the vowel set; formant data already in FORMANT_TABLE	https://csound.com/docs/manual/MiscFormants.html
choir tenor hum	Choir tenors (humming)	choirs	bocca chiusa	C3	A4	existing catalog range, UNVERIFIED	closed-mouth hum; solo voices have hum, choirs do not	HUM_FORMANTS already defined	(code: voices.py)
choir bass eh	Choir basss (eh)	choirs	SATB	E2	D4	existing catalog range, UNVERIFIED		fills the vowel set; formant data already in FORMANT_TABLE	https://csound.com/docs/manual/MiscFormants.html
choir bass ee	Choir basss (ee)	choirs	SATB	E2	D4	existing catalog range, UNVERIFIED		fills the vowel set; formant data already in FORMANT_TABLE	https://csound.com/docs/manual/MiscFormants.html
choir bass hum	Choir basss (humming)	choirs	bocca chiusa	E2	D4	existing catalog range, UNVERIFIED	closed-mouth hum; solo voices have hum, choirs do not	HUM_FORMANTS already defined	(code: voices.py)
mens choir	Men's choir TTBB (ah)	choirs	Welsh male voice choirs, glee clubs	E2	A4	UNVERIFIED (tenor+bass spans, memory)	dark powerful male sound	tenor and bass formants, CAN do	(memory, no source fetched)
womens choir	Women's choir SSAA (ah)	choirs	convent and school	G3	A5	UNVERIFIED (memory)	bright pure upper voices	soprano+alto formants	(memory, no source fetched)
boys choir	Boys choir (ah)	choirs	English cathedral	A3	A5	PARTIAL (treble A3-A5 verified)	straight-tone treble	treble formants, lower chorus_cents	https://en.wikipedia.org/wiki/Voice_type
girls choir	Girls choir (ah)	choirs	school and cathedral	B3	A5	UNVERIFIED (memory)	slightly warmer than boys	as childrens choir	(memory, no source fetched)
full choir ah	Full SATB choir (ah)	choirs	concert chorus	E2	A5	UNVERIFIED (union of four existing parts)	all four parts at once	one voice per pitch; single-patch polyphony not supported	https://en.wikipedia.org/wiki/SATB (not fetched)
gregorian chant	Gregorian chant schola	choirs	Western Europe, 9th c.	C3	D4	UNVERIFIED (page: pitch not fixed, melodies span about a seventh; monophonic, unison, men and boys or religious orders)	unison unaccompanied chant, free rhythm	unison detuned voices; cloister reverb is absent from the engine	https://en.wikipedia.org/wiki/Gregorian_chant
byzantine chant ison	Byzantine chant with ison	choirs	Orthodox Greece	A2	A4	UNVERIFIED (memory)	melody over held drone by second group	needs fixed drone voice and microtones	(memory, no source fetched)
orthodox choir	Russian Orthodox choir with oktavists	choirs	Russia	A1	A5	PARTIAL (oktavist low A1 verified; top memory)	very low bass doubling, dense a cappella harmony	depends on oktavist voice	https://en.wikipedia.org/wiki/Oktavist
gospel choir	Gospel choir	choirs	African American church	F3	C6	UNVERIFIED (memory)	powerful call-and-response with vibrato and scoops	needs vibrato LFO and pitch scoop	(memory, no source fetched)
barbershop quartet	Barbershop quartet	choirs	USA, c. 1900	C3	E5	UNVERIFIED (memory)	four-part a cappella, just intonation ring	needs just-intonation detune per part	(memory, no source fetched)
doo wop group	Doo-wop vocal group	choirs	USA 1950s	C3	C5	UNVERIFIED (memory)	nonsense syllables, falsetto lead	as scat	(memory, no source fetched)
cantu a tenore	Cantu a tenore (boche, mesu boche, contra, bassu)	choirs	Sardinia	G2	G4	UNVERIFIED (pitch memory; four voices verified)	boche solo and mesu boche in normal voice; contra (a fifth above bassu) and bassu use a larynx technique, bassu on the boche's note; contra said to imitate a sheep, bassu a cow, mesu boche wind; UNESCO 2005	needs per-voice timbre and false-fold rasp; four voices as separate instruments	https://en.wikipedia.org/wiki/Cantu_a_tenore
corsican paghjella	Corsican paghjella	choirs	Corsica	A2	A4	UNVERIFIED (memory; Throat singing page notes no throat singing involved)	three-voice male polyphony	three detuned voices	https://en.wikipedia.org/wiki/Throat_singing
bulgarian choir	Bulgarian women's choir	choirs	Bulgaria	A3	A5	UNVERIFIED (memory)	tight dissonant seconds, bright open-throat chest voice	chest-belt formants, no vibrato, tighter beating	(memory, no source fetched)
georgian choir	Georgian polyphonic choir	choirs	Georgia	G2	A5	UNVERIFIED (memory; krimanchuli as top voice of 3-4 part polyphony verified)	three-part male drone harmony with yodel top	drone plus yodel voice	https://en.wikipedia.org/wiki/Yodeling
pygmy polyphony	Central African pygmy polyphony	choirs	Congo, Aka, Baka, Mbuti	C3	C6	UNVERIFIED (memory; yodels woven into polyphony verified)	interlocking hocket and yodel	timing across voices	https://en.wikipedia.org/wiki/Yodeling
sacred harp choir	Sacred Harp shape note choir	choirs	Southern USA	C3	C5	UNVERIFIED (memory)	loud open fifths	no vibrato	(memory, no source fetched)
isicathamiya choir	Isicathamiya / mbube choir	choirs	Zulu South Africa	E2	E5	UNVERIFIED (memory)	male a cappella call-and-response	as men's choir	(memory, no source fetched)
kecak chorus	Kecak chorus	choirs	Bali	unpitched	unpitched	n/a	many men chant interlocking cak syllables	percussive noise-vowel bursts	(memory, no source fetched)
gamelan gerongan	Gamelan gerong and pesindhen	choirs	Java, Bali	D3	D5	UNVERIFIED (memory)	male unison chorus and female soloist in slendro/pelog	needs microtonal tuning	(memory, no source fetched)
tahitian himene	Tahitian himene	choirs	French Polynesia	E2	E5	UNVERIFIED (memory)	mixed choir with very low drone and high sustained voice	several drones	(memory, no source fetched)
bunun pasibutbut	Bunun pasibutbut	choirs	Taiwan	A2	A4	UNVERIFIED (memory)	harvest song with rising overlapping polyphony	as cantu a tenore	(memory, no source fetched)
vedic chant	Vedic chanting group	choirs	India	C3	C4	UNVERIFIED (memory)	three-pitch recitation	unison narrow-range voices	(memory, no source fetched)
tuvan ensemble	Tuvan throat singing ensemble	choirs	Tuva	G2	G6	UNVERIFIED (memory)	kargyraa plus sygyt together	depends on khoomei patches	https://en.wikipedia.org/wiki/Overtone_singing
cossack choir	Cossack men's choir	choirs	Russia, Ukraine	A1	A4	UNVERIFIED (memory)	male choir with oktavists	oktavist dependent	(memory, no source fetched)
qawwali party	Qawwali chorus	choirs	South Asia	C3	C5	UNVERIFIED (memory)	lead plus chorus with clapping	as qawwali voice	(memory, no source fetched)
```

## What the engine's formant voice model can and cannot do

Read from src/glitchygames/audio/instruments/voices.py and timbres.py (formant_series), in the glitchygames-performance-select checkout.

Can do: static vowel colour (Csound formant table, five formants per voice type and vowel), humming (two formants), breath noise, attack and release, chorus detune (3 cents solo, 11 cents choir), and a whistle (sine plus faint second harmonic).

Cannot do: (1) the formant filter does not move with the note; harmonic levels are fixed at the middle of the range, so a vowel is true only mid-range (stated in the module docstring); (2) no vowel-to-vowel morphing within a note, which blocks diphthongs, talk box, speech and consonants; (3) no consonant transients beyond the attack; (4) voices.py sets no vibrato or glide (engine-level support not checked, UNVERIFIED); (5) no moving high-Q formant for overtone singing; (6) no subharmonic source for kargyraa, growl and the oktavist extremes; (7) no analysis input, so no true vocoder, Voder, talk box or sonovox; (8) no reverb for cloister chant; (9) choirs are three detuned copies, with no per-singer drift; (10) one pitch per instrument, so cantu a tenore, SATB in one patch and Bulgarian clusters need several instruments.

Cheap wins using only what exists: subtype rows (range only), choir eh/ee/hum, men's, women's, boys and girls choirs, Gregorian unison, whistle register, whisper, voix celeste, tongue click and beatbox percussion (as noise and sine bursts).

## Rejected or corrected proposed entries

- vocoder: acceptable only as a static "robot vowel" named `vocoder voice`. A real vocoder needs a modulator signal, an analyzer and 8-20 bands (Vocoder page). History confirmed: developed from 1928, patents 1937 and 1939 (https://en.wikipedia.org/wiki/Vocoder). The audit's H-S number "5" is not a Hornbostel-Sachs class (the system has four; electrophones are an extension, 5 in the Sachs-Hornbostel revised numbering of some authors). Its range "follows carrier" is not a note range, so I gave C2-C7 as my own choice.
- voder: confirmed to exist: Homer Dudley, Bell Labs 1937-38, shown at the 1939 World's Fair; ten band-pass filters, wrist bar picks buzz for vowels or hiss for sibilants, foot pedal sets pitch, fifteen keys (https://en.wikipedia.org/wiki/Voder). Keep as a separate historical entry if wanted; as a modelable sound it is a static ten-band buzz/hiss, close to `vocoder voice`.
- talk box: confirmed (Talk box page): Alvino Rey 1939, Pete Drake 1964, Kustom The Bag 1969, Heil 1974. The proposed origin string "Kustom 1969; Rey 1939; Drake 1964-65" is right except Drake's album is 1964. Keep but classify as a voice row.
- Existing catalog `whistling` C5-C7: the Whistle register page gives D6-D7 for the whistle register; C5-C7 is plausible for ordinary human whistling but UNVERIFIED.
- Existing catalog `countertenor` E3-E5: the Voice type page contradicts itself (caption E3-E5, text C4-C6 and D3-D5). Owner decision needed.
- Existing `basso profundo` C2-C4: the page gives only C2-G4 for bass extremes, nothing for profundo; the Oktavist page shows true profundo/oktavist reaches A1 and lower. Catalog is conservative, not wrong.
- Existing `treble` shares the soprano formant row; code comments say so. A boy's formants are higher than the adult female table, so the sound is only approximate.

## Aliases

- soprano sfogato -> alto ah (contralto with extension, Voice type page)
- tenore contraltino -> countertenor ah (memory)
- falsettist -> countertenor ah
- contralto -> alto ah
- boy soprano -> treble ah
- khoomii, xoomei, hoomi -> khoomei
- overtone singing, harmonic singing -> khoomei (generic technique)
- khargyraa -> kargyraa
- borbannadyr -> borbangnadyr (page spelling)
- Inuit throat singing, iirngaaq, piqqusiraarniq, qiarvaaqtuq, nipaquhiit -> katajjaq (regional names, Katajjaq page)
- jodel -> yodel
- octavist, oktavist -> oktavist ah
- lockrop, kauka, kula, kulokk -> kulning (regional names, Kulning page)
- sprechgesang -> sprechstimme
- flute voice, flageolet register -> whistle register
- artificial larynx -> electrolarynx

## Range checks

- soprano C4-C6, mezzo A3-A5, contralto F3-F5, tenor C3-C5, baritone A2-A4, bass E2-E4: VERIFIED (https://en.wikipedia.org/wiki/Voice_type).
- countertenor E3-E5: CONFLICT in source, see above.
- treble A3-A5: VERIFIED as caption; text gives A3-F5, some to C6.
- basso profundo C2-C4: UNVERIFIED (see above).
- whistling C5-C7: UNVERIFIED; the whistle register D6-D7 is VERIFIED.
- oktavist A1 (sometimes F1, extreme C1): VERIFIED (https://en.wikipedia.org/wiki/Oktavist).
- castrato low C3: VERIFIED (Farinelli aria); top D6 UNVERIFIED.
- choir parts: UNVERIFIED (textbook SATB ranges, memory).
- throat singing, Tuvan harmonics: harmonic numbers 6,8,9,10,12,13,16 VERIFIED, no frequencies in sources.

## Gaps you could not close

- Subtype ranges for every Fach (no source gave them); castrato top note; Urtiin duu (404); kulning, yodel, katajjaq and Gregorian pitch ranges (pages give none).
- Not searched: MIMO, Met, Horniman and Grove for voice-related instruments; Wikipedia pages for Joik, Pansori, Qawwali, Ululation, Silbo Gomero and the choir traditions were not fetched, so those rows are memory.
- Possible missing traditions not researched: Kunqu, Vietnamese ca tru, Altai kai, Albanian iso-polyphony, Epirus polyphony, Faroese chain dance, Maori karanga and waiata, native North American powwow vocalizing, flamenco cante jondo, fado, Andean kantu, Hungarian parlando, Finnish runo singing, Aboriginal Australian song, Mongolian khoomii varieties (Overtone singing page lists labial, palatal, nasal and glottal classes), Persian tahrir ornament (Yodeling page), Sufi dhikr hum.
- Crowd chants and laughs, sobs and sighs are sound effects, not instruments; excluded.
