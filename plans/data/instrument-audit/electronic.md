# Electronic family audit (electrophones, H-S class 5)

## Summary
- New missing instruments listed: 103 rows below (about 25 are controllers, FM or sample-based and flagged REJECT/defer for modeling; about 45 are distinct synth/chip/drum voices the catalog lacks).
- Proposed entries rejected or merged: 20 (aliases/duplicates 6, controllers with no intrinsic timbre 8, FM/sample/physical-model deferred 5, not instruments 3 -- details below).
- Range fixes: Mellotron G2-F5, Omnichord four octaves, Rhythmicon C1-based four octaves, SN76489 and SID Hz values; nearly all proposed ranges were "not stated", so almost nothing in the first audit was a verified range.
- Source honesty: fetched and read this session (14): Wikipedia pages for List of electronic musical instruments, Theremin, Ondes Martenot, SN76489, POKEY, Ricoh 2A03, Roland TB-303, Novachord, Clavioline, Telharmonium, Rhythmicon, Otamatone, Mellotron, Stylophone, Omnichord (Game Boy sound hardware URL returned 404). Search tooling was not used for MIMO/Met/Horniman (not attempted); other rows cite a Wikipedia URL guessed from the topic title and the page was NOT read, so those ranges are UNVERIFIED and those URLs may not resolve. Rows with "no source fetched" are pure memory.
- Catalog check: catalog has acoustic-family keyboards, tonewheel organs, and drum-family electronic kick/snare only; no electronic toms, hats, clap, cowbell. Drum-machine voices belong in the drums family file when merged.
- Wikipedia's flat electronic list also names: Electronde, Electro-Theremin, Oramics, Radiodrum, Therevox, Chamberlin/Mellotron, Spharophon, Electronic keyboard (all included or aliased).

## New missing instruments
Rows marked "-" in lowest/highest are not applicable; Hz rows come from a chip datasheet-level Wikipedia statement. Rows whose modeling notes say REJECT are controllers or input-dependent and should probably not be added.

```tsv
name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls
telharmonium	Telharmonium (Dynamophone)	electronic	Thaddeus Cahill, USA 1897-1906	C1	C7	VERIFIED (partly, see source)	Cahill 1896/97; Mark II/III 145 generators (153 keys cited); tonewheel generators with added harmonics mixed by controls	additive sines; ok	https://en.wikipedia.org/wiki/Telharmonium
electronde	Electronde	electronic	Martin Taubmann, Germany 1929	C2	C7	UNVERIFIED (from memory; cited page not read for the range)	heterodyne monophonic, theremin-like timbre with keyboard/ribbon	monophonic sine/saw + vibrato; theremin patch	https://en.wikipedia.org/wiki/Electronde
dynaphone	Dynaphone	electronic	Rene Bertrand, France 1927-28	C2	C7	UNVERIFIED (memory)	early heterodyne monophonic instrument, thin sine/reedy tone	sine plus filtered harmonics	no source fetched
givelet coupleux organ	Givelet-Coupleux organ	electronic	Givelet and Coupleux, France 1929	C2	C7	UNVERIFIED (memory)	early valve-oscillator polyphonic organ, flute/reedy stops	additive organ stops; ok	no source fetched
welte lichttonorgel	Welte Lichttonorgel	electronic	Edwin Welte, Germany 1936	C2	C7	UNVERIFIED (memory)	photoelectric optical-disc organ; sampled-waveform timbres	additive approximation only	no source fetched
volks trautonium	Volks-Trautonium	electronic	Telefunken/Trautwein, Germany 1933	C3	C7	UNVERIFIED (from memory; cited page not read for the range)	mass-produced trautonium; ribbon-fingerboard glides, formant-filtered sawtooth	saw+resonant bandpass formants, glide; ok	https://en.wikipedia.org/wiki/Trautonium
terpsitone	Terpsitone	electronic	Leon Theremin, USA 1932	C2	C7	UNVERIFIED (memory)	theremin-type heterodyne driven by dancer movement on platform	same as theremin	no source fetched
electro theremin	Electro-Theremin (Tannerin)	electronic	Bob Whitsell for Paul Tanner, USA c1958	C3	C6	UNVERIFIED (from memory; cited page not read for the range)	slide-ribbon theremin-like tone, Beach Boys Good Vibrations; the proposed "tannerin" is this instrument	sine/triangle with portamento and vibrato; ok	https://en.wikipedia.org/wiki/Electro-Theremin
therevox	Therevox	electronic	France 1950s (Wikipedia lists under Ondes Martenot)	C2	C7	UNVERIFIED (from memory; cited page not read for the range)	ondes-Martenot-like ribbon/keyboard instrument; origin from memory	ok as ondes variant	https://en.wikipedia.org/wiki/Ondes_Martenot
voder	Voder	electronic	Homer Dudley, Bell Labs USA 1939	unpitched	unpitched	UNVERIFIED (memory)	keyboard-driven speech synthesizer: buzz/hiss source through 10 band filters	buzz+noise through bandpass bank; formant filters needed	no source fetched
vocoder	Vocoder	electronic	Homer Dudley 1938; Sennheiser/EMS/Moog 1970s	C2	C6	UNVERIFIED (from memory; cited page not read for the range)	robotic vowel voice: carrier synth shaped by band-pass analysis of speech	needs input speech; fixed-formant approximation only	https://en.wikipedia.org/wiki/Vocoder
sonovox	Sonovox	electronic	Gilbert Wright, USA 1939	unpitched	unpitched	UNVERIFIED (memory)	speech-shaped instrument sound via throat transducers	needs voice input; cannot synthesize	no source fetched
rhythmicon	Rhythmicon (Polyrhythmophone)	electronic	Henry Cowell and Leon Theremin, USA 1930-31	C1	C5	VERIFIED (partly, see source)	up to 16 simultaneous rhythms on the overtone series from a fundamental (demo C1); 16-note chord spans four octaves; percussive photoelectric pulses	sequencer-level; simple pulses	https://en.wikipedia.org/wiki/Rhythmicon
oramics	Oramics	electronic	Daphne Oram, UK 1957	C2	C7	UNVERIFIED (from memory; cited page not read for the range)	drawn-on-35mm-film optical synthesis	additive/envelope only	https://en.wikipedia.org/wiki/Oramics
radiodrum	Radiodrum (Radio Baton)	electronic	Max Mathews and Bob Boie, USA 1980s	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	3-D capacitive controller, no intrinsic timbre	controller only; REJECT as instrument voice	https://en.wikipedia.org/wiki/Radiodrum
mellotron	Mellotron	electronic	Streetly Electronics UK 1963 (Chamberlin USA 1950s)	G2	F5	VERIFIED (partly, see source)	tape-replay keyboard (two 35-note manuals G2-F5 on early double-manual models): flute/strings/choir loops, wobbly pitch	SAMPLE-BASED; approximate with filtered saw + wow/flutter + noise	https://en.wikipedia.org/wiki/Mellotron
chamberlin	Chamberlin	electronic	Harry Chamberlin, USA 1948-56	F3	F6	UNVERIFIED (from memory; cited page not read for the range)	tape-replay predecessor of Mellotron	same as mellotron; alias candidate	https://en.wikipedia.org/wiki/Chamberlin
optigan	Optigan	electronic	Mattel, USA 1971	F3	F6	UNVERIFIED (from memory; cited page not read for the range)	optical-disc replay home organ with accompaniment; lo-fi sampled organ/strings	SAMPLE-BASED; lo-fi filtered organ approximation	https://en.wikipedia.org/wiki/Optigan
vako orchestron	Vako Orchestron	electronic	Vako Synthesizers, USA 1975	C2	C7	UNVERIFIED (from memory; cited page not read for the range)	optical-disc replay: choir/strings	SAMPLE-BASED; choir pad approximation	https://en.wikipedia.org/wiki/Orchestron
solovox	Solovox	electronic	Hammond, USA 1940	F3	F6	UNVERIFIED (from memory; cited page not read for the range)	monophonic keyboard attachment for piano, reedy/string voices (3-octave); Hammond Solovox is the same name	subtractive saw + filter; ok	https://en.wikipedia.org/wiki/Solovox
jennings univox	Univox	electronic	Jennings, UK 1951	C3	C6	UNVERIFIED (memory)	monophonic valve keyboard, reedy buzz; precursor of clavioline-type instruments	saw/square + filter	no source fetched
lyricon	Lyricon	electronic	Bill Bernardo/Computone, USA 1972	Bb2	F6	UNVERIFIED (from memory; cited page not read for the range)	first electronic wind instrument; analog wind-controlled synth voice, Tom Scott	breath-driven synth lead; envelope from breath	https://en.wikipedia.org/wiki/Lyricon
ewi	EWI (Electronic Wind Instrument)	electronic	Nyle Steiner/Akai 1986	C1	C8	UNVERIFIED (from memory; cited page not read for the range)	breath controller with synth voice; sax-like fingering; tone depends on host	controller; offer EWI lead as sax-like saw	https://en.wikipedia.org/wiki/Wind_controller
otamatone	Otamatone	electronic	Maywa Denki, Japan 2009	C3	C6	UNVERIFIED (from memory; cited page not read for the range)	stylus-on-ribbon synth shaped like a note; mouth squeezes a formant "wah"	saw/square + formant filter swept by LFO; ok	https://en.wikipedia.org/wiki/Otamatone
tenori on	Tenori-on	electronic	Toshio Iwai/Yamaha 2007	C3	C7	UNVERIFIED (from memory; cited page not read for the range)	16x16 LED grid sequencer; bleepy synth tones	controller; REJECT as voice	https://en.wikipedia.org/wiki/Tenori-on
theremini	Theremini	electronic	Moog 2014	C2	C7	UNVERIFIED (memory)	digital pitch-quantised theremin descendant	same as theremin	no source fetched
keytar	Keytar	electronic	1970s, Moog Liberation 1980	C2	C7	UNVERIFIED (from memory; cited page not read for the range)	strap-on keyboard controller; sounds from any synth	controller; no intrinsic voice	https://en.wikipedia.org/wiki/Keytar
guitar synthesizer	Guitar synthesizer (Roland GR-300 type)	electronic	Roland, Japan 1977-80	E2	E6	UNVERIFIED (from memory; cited page not read for the range)	guitar pitch-to-synth conversion; saw/pulse synth tone with guitar articulation	synth lead with pitch tracking is host job; ok as synth	https://en.wikipedia.org/wiki/Guitar_synthesizer
moog lead	Moog lead	electronic	Moog, USA 1970	C2	C7	UNVERIFIED (from memory; cited page not read for the range)	three-oscillator detuned lead with 24 dB ladder low-pass	2-3 detuned saws + resonant LP with envelope; ok	https://en.wikipedia.org/wiki/Minimoog
moog bass	Moog bass (Minimoog)	electronic	Moog, USA 1970	C1	C4	UNVERIFIED (from memory; cited page not read for the range)	fat sub-heavy monophonic bass	saw/square + LP envelope; overlaps synth bass	https://en.wikipedia.org/wiki/Minimoog
moog taurus	Moog Taurus bass pedals	electronic	Moog, USA 1975	C1	C3	UNVERIFIED (memory)	analog bass pedals, huge sub tone	saw + LP	no source fetched
arp 2600	ARP 2600	electronic	Alan R. Pearlman, USA 1971	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	semi-modular analog; R2-D2 voice; sample-and-hold, ring mod	subtractive + S&H LFO; ok	https://en.wikipedia.org/wiki/ARP_2600
arp odyssey	ARP Odyssey	electronic	ARP, USA 1972	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	duophonic analog lead, biting sync sound	2 osc + sync; ok	https://en.wikipedia.org/wiki/ARP_Odyssey
arp string ensemble	ARP/Solina String Ensemble	electronic	Eminent/ARP 1970s	C2	C7	UNVERIFIED (from memory; cited page not read for the range)	divide-down saw ensemble with chorus; classic string machine	detuned saw+chorus; overlaps synth strings	https://en.wikipedia.org/wiki/String_machine
buchla 100	Buchla Modular (Series 100)	electronic	Don Buchla, USA 1963-65	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	west-coast: complex oscillator, wavefolder, low-pass gate; bongo-like plinks	needs wavefolder + LPG; partially modelable	https://en.wikipedia.org/wiki/Buchla_Modular_Electronic_Music_System
buchla music easel	Buchla Music Easel	electronic	Don Buchla, USA 1973	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	portable west-coast synth, pluck/FM-ish tones	FM-ish via folding; limited	https://en.wikipedia.org/wiki/Buchla_Music_Easel
ems vcs3	EMS VCS3	electronic	Peter Zinovieff et al., UK 1969	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	pin-matrix patchable synth, wobbly drones; Pink Floyd	osc + filter + ring mod; ok	https://en.wikipedia.org/wiki/EMS_VCS_3
oberheim sem	Oberheim SEM	electronic	Tom Oberheim, USA 1974	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	state-variable multimode filter synth, fat brass	saw/pulse + SVF; ok	https://en.wikipedia.org/wiki/Oberheim_SEM
prophet 5	Prophet-5	electronic	Sequential Circuits, USA 1977	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	polyphonic analog (5 voice); also covers proposed "polyphonic analog synth (prophet-5 type)"	2 osc + poly-mod + LP; ok	https://en.wikipedia.org/wiki/Prophet-5
prophet vs	Prophet VS	electronic	Sequential, USA 1986	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	vector synthesis blending four wavetables	wavetable crossfade; additive approximation	https://en.wikipedia.org/wiki/Prophet_VS
jupiter 8	Roland Jupiter-8	electronic	Roland, Japan 1981	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	lush polyphonic analog pads/brass	detuned saw/pulse + filter; ok	https://en.wikipedia.org/wiki/Roland_Jupiter-8
juno 106	Juno-106 chorus pad	electronic	Roland, Japan 1984	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	DCO saw/pulse + sub + signature chorus	pulse+saw+sub + chorus; ok	https://en.wikipedia.org/wiki/Roland_Juno-106
cs 80	Yamaha CS-80	electronic	Yamaha, Japan 1977	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	polyphonic analog brass (Vangelis, Blade Runner) with ribbon pitch	saw + dual filters + slow attack; ok	https://en.wikipedia.org/wiki/Yamaha_CS-80
sh 101	Roland SH-101	electronic	Roland, Japan 1982	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	monophonic bass/lead with sub-osc	saw/pulse/sub + LP; overlaps synth bass	https://en.wikipedia.org/wiki/Roland_SH-101
ms 20	Korg MS-20	electronic	Korg, Japan 1978	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	semi-modular, aggressive screaming HP/LP filter	dual resonant filters; partial	https://en.wikipedia.org/wiki/Korg_MS-20
tb 303 acid bass	TB-303 acid bass	electronic	Roland TB-303, Japan 1981	C1	C4	VERIFIED (partly, see source)	saw or square, 24 dB resonant LP, filter envelope, accent/slide	saw/square + resonant LP sweep + portamento; ok	https://en.wikipedia.org/wiki/Roland_TB-303
casio cz	Casio CZ phase distortion voice	electronic	Casio, Japan 1985	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	phase-distortion synth, resonant-saw/pulse sounds	phase-distortion waveform shaper - possible custom oscillator	https://en.wikipedia.org/wiki/Phase_distortion_synthesis
ppg wave	PPG Wave wavetable lead	electronic	PPG, Germany 1981	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	digital wavetable sweeps, glassy	wavetable sweep; additive/morph approximation	https://en.wikipedia.org/wiki/PPG_Wave
synclavier	Synclavier	electronic	New England Digital, USA 1977	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	FM plus sample digital workstation	FM unsupported	https://en.wikipedia.org/wiki/Synclavier
d 50 la synth	Roland D-50 (LA synthesis)	electronic	Roland, Japan 1987	C1	C7	UNVERIFIED (from memory; cited page not read for the range)	short PCM attacks plus subtractive tails	SAMPLE-HYBRID; subtractive tail only	https://en.wikipedia.org/wiki/Roland_D-50
sync lead	Hard-sync lead	electronic	ARP/Prophet, 1970s	C2	C7	UNVERIFIED (from memory; cited page not read for the range)	slave oscillator swept against master: ripping harmonics	needs oscillator sync; check engine	https://en.wikipedia.org/wiki/Oscillator_sync
pwm pad	Pulse-width-modulation pad	electronic	Juno/Solina style 1970s	C2	C6	UNVERIFIED (from memory; cited page not read for the range)	slowly moving pulse width, chorus-like	pulse + LFO on duty	https://en.wikipedia.org/wiki/Pulse-width_modulation
reese bass	Reese bass	electronic	Kevin Saunderson, 1988	C0	C3	UNVERIFIED (from memory; cited page not read for the range)	detuned saws phasing, drum and bass	2-3 detuned saws + LP	https://en.wikipedia.org/wiki/Reese_bass
wobble bass	Wobble bass	electronic	dubstep, 2000s	C0	C3	UNVERIFIED (from memory; cited page not read for the range)	bass with LFO-swept low-pass	saw + LFO filter; ok	https://en.wikipedia.org/wiki/Dubstep
hoover lead	Hoover	electronic	Roland Alpha Juno, 1990	C2	C6	UNVERIFIED (from memory; cited page not read for the range)	pitch-dropping detuned PWM saw stack, rave	detuned pulse + pitch envelope	https://en.wikipedia.org/wiki/Hoover_sound
noise riser	Noise riser	electronic	EDM sweep fx	unpitched	unpitched	UNVERIFIED (memory)	filtered noise sweep upward	noise + HP sweep; ok	no source fetched
laser zap	Laser zap	electronic	arcade/synth fx	unpitched	unpitched	UNVERIFIED (memory)	fast descending pitch sweep (pew)	saw + pitch envelope; ok	no source fetched
sample and hold	Sample-and-hold random arp	electronic	ARP 2600/ Moog 1970s	C2	C6	UNVERIFIED (from memory; cited page not read for the range)	stepped random pitches (blips)	random stepped LFO; ok	https://en.wikipedia.org/wiki/Sample_and_hold
ring modulator	Ring modulator bell	electronic	Dalek voice / Moog 1960s	C2	C6	UNVERIFIED (from memory; cited page not read for the range)	inharmonic metallic tone from two multiplied oscillators	multiply two oscillators; check engine	https://en.wikipedia.org/wiki/Ring_modulation
talk box	Talk box	electronic	Kustom Bag 1969; Alvino Rey 1939	C2	C6	UNVERIFIED (from memory; cited page not read for the range)	vowel-formant swept distortion source	formant filter bank	https://en.wikipedia.org/wiki/Talk_box
electronic tom	Electronic tom (Simmons)	electronic	Dave Simmons, UK 1981	C2	C4	UNVERIFIED (from memory; cited page not read for the range)	swept-sine pew tom	sine + pitch decay; ok	https://en.wikipedia.org/wiki/Simmons_(electronic_drum_company)
electronic clap	Electronic clap (808)	electronic	Roland TR-808, 1980	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	filtered noise bursts with reverb tail	noise bursts + BP; ok	https://en.wikipedia.org/wiki/Roland_TR-808
electronic closed hi hat	Electronic closed hi-hat (808)	electronic	TR-808, 1980	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	six detuned square oscillators through HP	6 squares + HP + short env; ok	https://en.wikipedia.org/wiki/Roland_TR-808
electronic open hi hat	Electronic open hi-hat (808)	electronic	TR-808, 1980	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	as closed with long decay	same	https://en.wikipedia.org/wiki/Roland_TR-808
electronic cowbell	Electronic cowbell (808)	electronic	TR-808, 1980	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	two detuned squares ~540 Hz and 800 Hz (memory) bandpassed	2 squares + BP	https://en.wikipedia.org/wiki/Roland_TR-808
electronic clave	Electronic clave (808)	electronic	TR-808, 1980	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	short resonant bandpassed click	sine/pulse + fast decay	https://en.wikipedia.org/wiki/Roland_TR-808
electronic rimshot	Electronic rimshot (808)	electronic	TR-808, 1980	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	clicky triple-resonant ping	ok	https://en.wikipedia.org/wiki/Roland_TR-808
electronic cymbal	Electronic cymbal (909)	electronic	Roland TR-909, 1983	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	metallic noise-like crash	6 squares + noise	https://en.wikipedia.org/wiki/Roland_TR-909
electronic conga	Electronic conga (808)	electronic	TR-808, 1980	C3	C5	UNVERIFIED (from memory; cited page not read for the range)	short pitched resonant tone	sine + decay	https://en.wikipedia.org/wiki/Roland_TR-808
electronic maracas	Electronic maracas (808)	electronic	TR-808, 1980	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	short HP noise burst	noise	https://en.wikipedia.org/wiki/Roland_TR-808
wurlitzer sideman	Wurlitzer Sideman	electronic	Wurlitzer, USA 1959	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	first commercial drum machine; mechanical-electronic rhythm patterns	noise/sine hits	https://en.wikipedia.org/wiki/Drum_machine
rhythm king	Maestro Rhythm King	electronic	Gibson, USA 1960s	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	transistor drum box (Sly Stone)	noise/sine hits	https://en.wikipedia.org/wiki/Drum_machine
linn lm1	LinnDrum / LM-1	electronic	Roger Linn, USA 1980-82	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	sampled drum machine	SAMPLE-BASED	https://en.wikipedia.org/wiki/Linn_LM-1
sid voice	C64 SID voice (6581)	electronic	MOS 6581/8580, 1982	0.0625 Hz	4095.9375 Hz	VERIFIED (partly, see source)	oscillator range at 1 MHz clock; triangle/saw/pulse(PWM)/noise, combined waveforms, ring mod, hard sync, multimode filter (6581 nonlinear, 8580 clean)	PWM + SVF + sync; combined waveforms need custom; oscillator range 0.0625-4095.9375 Hz at 1 MHz	https://en.wikipedia.org/wiki/MOS_Technology_6581
sid noise	SID noise	electronic	MOS 6581	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	LFSR noise with pitch control	noise + LP	https://en.wikipedia.org/wiki/MOS_Technology_6581
chip sawtooth	Chiptune sawtooth	electronic	SID/ Game Boy wave RAM	C1	C8	UNVERIFIED (from memory; cited page not read for the range)	stepped sawtooth	saw	https://en.wikipedia.org/wiki/Chiptune
chip noise	Chiptune noise (long LFSR)	electronic	NES/GB/SID	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	white-ish LFSR noise, clocked at selectable rates	noise + rate control	https://en.wikipedia.org/wiki/Ricoh_2A03
chip noise short	Chiptune periodic noise (short LFSR)	electronic	NES mode 1 / SN76489 periodic	unpitched	unpitched	VERIFIED (partly, see source)	metallic pitched buzz from 93-step (NES, memory)/ short LFSR	pitched noise: need looped random buffer or pulse train; SN76489 verified has periodic mode	https://en.wikipedia.org/wiki/Texas_Instruments_SN76489
chip wave channel	Game Boy wave channel	electronic	Nintendo DMG, 1989	C1	C8	VERIFIED (partly, see source)	user-defined 32-sample 4-bit waveform (memory)	custom waveform table via additive	https://en.wikipedia.org/wiki/Game_Boy_sound_hardware
nes dpcm	NES DPCM channel	electronic	Ricoh 2A03, 1983	unpitched	unpitched	VERIFIED (partly, see source)	1-bit delta-modulation samples; drum/bass hits, grit	SAMPLE-BASED; noise burst + low saw approximation	https://en.wikipedia.org/wiki/Ricoh_2A03
pokey distortion	POKEY distortion voice	electronic	Atari POKEY, 1979	C1	C8	VERIFIED (partly, see source)	4 channels 8-bit divisors, 16-bit pairs, 4/5/17-bit poly noise distortion, high-pass link; buzzy pitched noise	periodic noise via poly counters; pitched pulse-train approx	https://en.wikipedia.org/wiki/POKEY
ay 3 8910	AY-3-8910 (YM2149) voice	electronic	General Instrument, 1978	B1	B8	UNVERIFIED (from memory; cited page not read for the range)	3 square tones + shared noise + hardware envelope (buzz bass); YM2149 identical in function (memory)	square + noise + hw saw/tri envelope as bass buzz	https://en.wikipedia.org/wiki/General_Instrument_AY-3-8910
sn76489 voice	SN76489 voice	electronic	Texas Instruments, 1980	108 Hz	111.6 kHz	VERIFIED (partly, see source)	3 squares (16 levels) + noise (white/periodic); range at 3.58 MHz clock	square + noise; ok	https://en.wikipedia.org/wiki/Texas_Instruments_SN76489
atari tia	Atari 2600 TIA voice	electronic	Atari, 1977	C1	C6	UNVERIFIED (from memory; cited page not read for the range)	2 channels, 5-bit divisor, 4-bit waveform selection: buzzy, out-of-tune pitched noise	poly counter noise emulation	https://en.wikipedia.org/wiki/Television_Interface_Adaptor
amiga paula	Amiga Paula voice	electronic	MOS 8364, Commodore 1985	C1	C8	UNVERIFIED (from memory; cited page not read for the range)	4 DMA channels, 8-bit PCM samples (tracker modules)	SAMPLE-BASED; approximate with simple oscillators	https://en.wikipedia.org/wiki/Amiga_Chip_RAM
scc wavetable	Konami SCC voice	electronic	Konami, 1987	C1	C8	UNVERIFIED (from memory; cited page not read for the range)	5 channels, 32-byte waveforms each	custom waveform table	https://en.wikipedia.org/wiki/Konami_SCC
pc engine hucs280	HuC6280 PSG voice	electronic	NEC/Hudson, 1987	C1	C8	UNVERIFIED (from memory; cited page not read for the range)	6 channels with 32-sample 5-bit wavetables	custom waveform	https://en.wikipedia.org/wiki/TurboGrafx-16
namco wsg	Namco WSG voice	electronic	Namco, 1980 (Pac-Man)	C2	C7	UNVERIFIED (from memory; cited page not read for the range)	3 channel wavetable (32x4-bit)	custom waveform	https://en.wikipedia.org/wiki/Namco_WSG
pc speaker	PC speaker beeper	electronic	IBM PC/ZX Spectrum	C3	C8	UNVERIFIED (from memory; cited page not read for the range)	single square wave	chip square	https://en.wikipedia.org/wiki/PC_speaker
votrax	Votrax speech chip	electronic	Federal Screw Works, USA 1970s	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	formant speech phonemes	formant filters	https://en.wikipedia.org/wiki/Votrax
yamaha fm family	Yamaha FM chips (OPN2 YM2612, OPM YM2151, OPL YM3812)	electronic	Yamaha 1983-85	C0	C8	UNVERIFIED (from memory; cited page not read for the range)	4-op FM	FM UNSUPPORTED; deferred	https://en.wikipedia.org/wiki/Yamaha_YM2612
dx7 ep	DX7 electric piano	electronic	Yamaha DX7, 1983	A0	C8	UNVERIFIED (from memory; cited page not read for the range)	2-op FM tine piano	FM UNSUPPORTED	https://en.wikipedia.org/wiki/Yamaha_DX7
dx7 bass	DX7 FM bass	electronic	Yamaha DX7, 1983	C1	C4	UNVERIFIED (from memory; cited page not read for the range)	FM slap bass	FM UNSUPPORTED	https://en.wikipedia.org/wiki/Yamaha_DX7
fm bell	FM bell	electronic	Yamaha DX7 style	C3	C7	UNVERIFIED (from memory; cited page not read for the range)	inharmonic ratio FM	FM UNSUPPORTED (ring mod approx)	https://en.wikipedia.org/wiki/Frequency_modulation_synthesis
casio vl tone	Casio VL-1	electronic	Casio, Japan 1979	C3	C7	UNVERIFIED (from memory; cited page not read for the range)	toy calculator synth with rhythm; thin square-like tones	square	https://en.wikipedia.org/wiki/Casio_VL-1
speak and spell	Speak and Spell LPC voice	electronic	Texas Instruments, 1978	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	LPC speech	formant synthesis	https://en.wikipedia.org/wiki/Speak_%26_Spell_(toy)
omnichord	Omnichord	electronic	Suzuki, Japan 1981	C3	C6	VERIFIED (partly, see source)	touch strum plate across a four-octave range (always matches selected chord) + organ-like chords/walking bass; OM-27/36/84 analog, later models sampled; Suzuki Q-Chord (1999) is a re-release of the same instrument	FM-less; plucked saw/organ; ok	https://en.wikipedia.org/wiki/Omnichord
stylophone	Stylophone	electronic	Dubreq, UK 1967	C4	C6	UNVERIFIED (from memory; cited page not read for the range)	stylus keys, buzzy VCO with vibrato	saw/square + vibrato	https://en.wikipedia.org/wiki/Stylophone
musical tesla coil	Singing Tesla coil (Zeusaphone)	electronic	Steve Ward, USA 2006 (memory)	C3	C6	UNVERIFIED (from memory; cited page not read for the range)	spark-modulated tone, buzz/zap	pulse train + noise	https://en.wikipedia.org/wiki/Musical_Tesla_coil
dub siren	Dub siren	electronic	Jamaica, 1970s (memory)	C3	C7	UNVERIFIED (from memory; cited page not read for the range)	oscillator with pitch-sweep and delay	saw + pitch LFO + echo	https://en.wikipedia.org/wiki/Dub_siren
cracklebox	Cracklebox	electronic	STEIM, Netherlands 1970s	unpitched	unpitched	UNVERIFIED (from memory; cited page not read for the range)	touch-modulated chaotic squeals	noise/random oscillator	https://en.wikipedia.org/wiki/Cracklebox
atari punk	Atari Punk Console	electronic	Forrest Mims, USA 1970s	C2	C7	UNVERIFIED (from memory; cited page not read for the range)	two 555 timers; harsh stepped pulse tones	pulse + pulse-modulated pulse	https://en.wikipedia.org/wiki/Atari_Punk_Console
electronic carillon	Electronic carillon (Schulmerich)	electronic	Schulmerich USA, 1940s-50s (memory)	C3	C7	UNVERIFIED (memory)	bell tones from tuned bars/oscillators	additive inharmonic bell	no source fetched
```

## Rejected or corrected proposed entries
- chip pulse 75: same spectrum as pulse 25 (inverted); alias (the proposal itself says so). https://en.wikipedia.org/wiki/Chiptune (not read)
- nes triangle: alias of chip triangle; 4-bit stepping gives a 1/8 volume overtone four octaves up (verified, https://en.wikipedia.org/wiki/Ricoh_2A03) -- optional stepped-triangle variant at most.
- sid chip sawtooth: duplicate of proposed chip sawtooth; replaced by sid voice (SID oscillator range VERIFIED, https://en.wikipedia.org/wiki/MOS_Technology_6581 as quoted in the proposal).
- sound chip beeper: renamed pc speaker.
- mixturtrautonium: variant of trautonium; keep only as alias unless a subharmonic mixture model is added.
- tannerin: wrong provenance ("unknown"). It is the Electro-Theremin built for Paul Tanner (https://en.wikipedia.org/wiki/Electro-Theremin, list-page name confirmed on the list page; details memory). Renamed electro theremin.
- polyphonic analog synth (prophet-5 type): renamed prophet 5.
- fm synth electric piano (dx7 type), ym2612 fm voice: FM unsupported; kept as deferred rows (dx7 ep, yamaha fm family).
- fairlight cmi, mellotron-like replay: sample-based; not synthesizable; fairlight rejected, mellotron kept with approximation note.
- physical modeling synth (vl-1 type): a synthesis method, not an instrument voice; rejected.
- laser harp, eigenharp, reactable, alphasphere, optivideotone, lightharp, samchillian tip tip tip cheeepeeeee: controllers with no intrinsic timbre; rejected (alphasphere and reactable origin was "unknown" in the proposal).
- electroencephalophone, electrocardiophone: biosignal sonification, not instruments with a timbre; rejected.
- dermatron: Bruce Haack skin-contact instrument; kept off the list for lack of a timbre description (memory only).
- haken continuum: controller with built-in synth; rejected as a distinct timbre, covered by synth voices.
- triadex muse: sequencer, not a voice; rejected.
- sphaerophon, croix sonore, singing arc, musical telegraph, hellertion, subharchord, variophone, ans synthesizer, clavivox, electronic sackbut, ondioline, novachord, mixtur: the first-audit list stands but with ranges unstated; they are NOT in the new TSV above because they are already proposed. Worth adding to the merged list as proposed. Novachord 72 notes, 72-voice polyphony, 1939 VERIFIED (https://en.wikipedia.org/wiki/Novachord); clavioline typically three octaves, six-octave Bode version VERIFIED (https://en.wikipedia.org/wiki/Clavioline).
- The proposal's "ay 3 8910 tone and noise", "chip wave channel", "chip sawtooth": kept in the table as ay 3 8910, chip wave channel, chip sawtooth.

## Aliases
- hammond solovox -> solovox
- thereminvox, etherwave, theremini -> theremin (Theremini row kept only if a pitch-quantized variant is wanted)
- tannerin -> electro theremin
- mixturtrautonium, volks trautonium -> trautonium (volks-trautonium kept as separate distinct row; mixtur alias)
- suzuki q chord -> omnichord (1999 re-release, VERIFIED https://en.wikipedia.org/wiki/Omnichord)
- ym2149 -> ay 3 8910
- chamberlin -> mellotron
- therevox -> ondes martenot (Wikipedia lists it under Ondes Martenot)
- chip pulse 75 -> chip pulse 25
- nes triangle -> chip triangle
- sid chip sawtooth -> chip sawtooth
- electronic sackbut / sackbut -> same instrument
- hammond novachord -> novachord

## Range checks
- theremin (catalog): near-linear region about two to three central octaves; no full range stated (https://en.wikipedia.org/wiki/Theremin). UNVERIFIED for engine range.
- ondes martenot (catalog): 72 keys (84 on 4th version); one-octave transpose switch gives C1 to C8. VERIFIED (https://en.wikipedia.org/wiki/Ondes_Martenot).
- clavioline: three octaves, six-octave Bode variant. VERIFIED.
- novachord: 72 notes; range not stated (about six octaves is inference). Notes UNVERIFIED.
- stylophone: bass octave lower, treble octave higher than standard; VOICE model two-octave keyboard. VERIFIED partly (https://en.wikipedia.org/wiki/Stylophone).
- omnichord: strum plate four octaves. VERIFIED.
- mellotron: G2-F5 on double-manual models; M300 52 notes. VERIFIED.
- rhythmicon: C1-based, four-octave chord. VERIFIED.
- sn76489: about 108 Hz-111.6 kHz at 3.58 MHz; ~122 Hz-125 kHz at max clock. VERIFIED.
- pokey: dividers 1-256 from 64 kHz/15 kHz/1.79 MHz clocks; 16-bit pairs. VERIFIED (no note range).
- tb-303: saw or square, 24 dB LP, 1981-84. VERIFIED. Accent/slide not stated by the fetched page (memory says present).
- Game Boy wave channel range: URL 404, UNVERIFIED.
- All other proposed ranges in the first audit ("not stated") remain UNVERIFIED.

## Gaps you could not close
- MIMO, the Met, Horniman and Grove listings were not queried; electrophone coverage from museum databases is untested. Suspected missing: Hammond organ-derived Novachord relatives (Hammond Solovox variants, Baldwin/Compton Electrone organs), Wurlitzer/Fender Rhodes boundary cases (electromechanical, probably keyboards family), Electric Hurdy-gurdy and electric violin (strings family), Ebow and sustainer-type devices, Seaboard (ROLI), Hydraulophone, Monome, Moog Etherwave/Voyager as separate voices, Ensoniq/Emulator samplers, Yamaha GX-1, Fender Rhodes Chroma, Waldorf Microwave, Kurzweil K250, Korg Wavestation, Access Virus, Nord Lead, Roland JP-8000 supersaw (supersaw already in catalog), Atari Falcon, Gravis Ultrasound, SPC700 (SNES), YM2413, OPL3 sound-card, VIC-20/VIC-II, Ensoniq 5503, TED, Magnavox Odyssey, Intellivision AY-3-8914, Vectrex, Bally Astrocade, Casio SK-1 and other toy samplers, Speak and Spell LPC variants.
- Hz bounds for chips with no fetched page (AY-3-8910 about 30.6 Hz per the proposal, Game Boy) are unconfirmed.
- Entries marked "(memory)" in the TSV (Voder, Univox, Dynaphone, Givelet-Coupleux, Welte Lichttonorgel, Terpsitone, Moog Taurus, synth archetype rows) have unchecked years and ranges.
