# Drums and percussion audit (audit2)

Method note: ~26 WebFetch/WebSearch calls were made (Wikipedia list pages, instrument articles, MIT/BC sabar pages, LACMA/British Museum pahu records via search). MIMO, the Met and the Horniman were NOT reached. Wikipedia 404s occurred for Sabar_(drum), Pahu_(drum), List_of_Korean_musical_instruments, Spoons_(percussion), Bones page with parentheses worked. The List of percussion instruments page was read only through 'Sambal drum' for membranophones/idiophones A-R and again from offset 100000 (R-Z); a middle slice and the end of the idiophone section may have been truncated by the fetch summarizer. Tagging: "(VERIFIED)" = stated by a fetched page; "(listed)" = the name appears in the fetched list but sound/description is from memory; "(memory)" = not fetched. Almost every instrument here is unpitched, so lowest/highest = unpitched. The sources never give note ranges for any proposed drum.

## Summary

- New missing found: 158 rows below (including ~25 tuned-percussion-leaning items flagged with family "tuned percussion"). All of the user's named known gaps are covered (chenda, thavil, sabar, kebero, pahu, plus Indian/African/Middle East/East Asia/Latin/folk lists); mridangam, pakhawaj, dholak, dhol, khol, edakka(=idakka), maddalam, kanjira, ghatam, nagara, damaru, udukku are in proposed or below.
- Proposed entries rejected or needing rename: 17 (see section).
- Aliases: 24.
- Range fixes: 8 (all drums have no source-backed range; mostly "est." ranges struck).
- Jaw harp decision: NOT drums and NOT free reeds. H-S 121.22 (lamellophone, plucked idiophone, VERIFIED, https://en.wikipedia.org/wiki/Jew%27s_harp). Put it with mbira/kalimba (new "lamellophones" family or tuned percussion). Morsing, khomus, kouxian, mukkuri, kubing, gogona, karinding, morchang are regional names/builds of the same class (VERIFIED names).

## New missing instruments

name	title	family	origin	lowest	highest	range_status	sound	modeling_notes	source_urls
chenda	Chenda	drums and percussion	Kerala and Tulu Nadu, India	unpitched	unpitched	N/A unpitched (existence per URL)	cylindrical two-headed drum, two sticks; loud rigid sound; right head 5-7 skin layers gives bass (VERIFIED); decay short (memory)	noise click plus short sine; easy	https://en.wikipedia.org/wiki/Chenda
thavil	Thavil	drums and percussion	Tamil Nadu, India	unpitched	unpitched	N/A unpitched (existence per URL)	barrel drum; right head hand/thumb-capped fingers, left head short thick stick; left head loose for pitch bend; always with nadaswaram (VERIFIED)	two-layer drum with left-head pitch bend; easy	https://en.wikipedia.org/wiki/Thavil
sabar	Sabar	drums and percussion	Senegal and Gambia (Wolof, Serer)	unpitched	unpitched	N/A unpitched (existence per URL)	open-bottom tapered drums played with one hand and one stick; ensemble: nder (tallest lead), mbeng-mbeng, tungune (shortest), col (closed bass drum) (VERIFIED via search of MIT/BC pages); slap sound memory	slap = noise burst + click, bass = sine drop; easy	https://sites.google.com/bc.edu/bc-west-african-music-ensemble/sabar-in-culture/drum-types
kebero	Kebero	drums and percussion	Ethiopia and Eritrea	unpitched	unpitched	N/A unpitched (existence per URL)	two-headed conical hand drum; one head tuned higher; Orthodox liturgical use (VERIFIED)	two-pitch sine thud; easy	https://en.wikipedia.org/wiki/Kebero
pahu	Pahu (Hawaiian/Tahitian drum)	drums and percussion	Polynesia	unpitched	unpitched	N/A unpitched (existence per URL)	hollow log with shark or ray skin head, played with hands, seated; temple (heiau) vs hula sizes (VERIFIED, LACMA/BM records)	deep sine thump, dry slap; easy	https://en.wikipedia.org/wiki/Pahu
puniu	Puniu (Hawaiian knee drum)	drums and percussion	Hawaii	unpitched	unpitched	N/A unpitched (existence per URL)	small coconut-shell drum tied to the knee, struck with a cord-tipped stick; companion to pahu (VERIFIED via same search; sound memory)	short high thud; easy	https://en.wikipedia.org/wiki/Pahu
dhak	Dhak	drums and percussion	eastern India	unpitched	unpitched	N/A unpitched (existence per URL)	barrel stick drum (list_of_drums barrel class VERIFIED)	easy	https://en.wikipedia.org/wiki/List_of_drums
khol	Khol	drums and percussion	Bengal, Assam, Manipur	unpitched	unpitched	N/A unpitched (existence per URL)	clay/wood barrel hand drum (listed; sound memory)	easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
maddalam	Maddalam (Shuddha Madalam)	drums and percussion	Kerala	unpitched	unpitched	N/A unpitched (existence per URL)	barrel hand drum (listed; sound memory)	easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
udukku	Udukku (Udukai)	drums and percussion	South India	unpitched	unpitched	N/A unpitched (existence per URL)	small hourglass hand drum (listed; sound memory)	pitch-glide; moderate	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
urumi	Urumi (urumee)	drums and percussion	South India	unpitched	unpitched	N/A unpitched (existence per URL)	stick drum, friction/two stick listing; (memory on sound)	easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
parai	Parai (Parai thappu)	drums and percussion	Tamil Nadu	unpitched	unpitched	N/A unpitched (existence per URL)	frame drum played with sticks (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
tasha	Tasha (Tassa)	drums and percussion	India and Caribbean (Trinidad)	unpitched	unpitched	N/A unpitched (existence per URL)	high-tension kettle stick drum (listed; Caribbean use memory)	sharp crack; easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
manjira	Manjira (jhanj, taal)	drums and percussion	India	unpitched	unpitched	N/A unpitched (existence per URL)	hand cymbals/clash cymbals (listed; Taal confirmed as Indian clash cymbal via Cymbal article)	inharmonic ring; easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
khartal	Khartal (kartal, chiplya)	drums and percussion	India	unpitched	unpitched	N/A unpitched (existence per URL)	clapper idiophone (listed; sound memory)	click bursts; easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
chimta	Chimta	drums and percussion	Punjab	unpitched	unpitched	N/A unpitched (existence per URL)	tongs with jingles (listed; description memory)	easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
ghungroo	Ghungroo	drums and percussion	India	unpitched	unpitched	N/A unpitched (existence per URL)	strings of pellet bells worn on ankles (listed; memory)	noise cluster; easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
chengila	Chengila	drums and percussion	Kerala	unpitched	unpitched	N/A unpitched (existence per URL)	gong/bell idiophone (listed; description memory)	easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
elathalam	Elathalam	drums and percussion	Kerala	unpitched	unpitched	N/A unpitched (existence per URL)	cymbals (listed; description memory)	easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
dunun	Dunun (Manding bass drum)	drums and percussion	Mali, Guinea (note: easily confused with dundun, Yoruba talking drum)	unpitched	unpitched	N/A unpitched (existence per URL)	cylindrical double-headed bass drum, stick plus bell; sizes dundunba, sangban, kenkeni (memory; not fetched)	3 pitch variants; easy	https://en.wikipedia.org/wiki/List_of_drums
sangban	Sangban	drums and percussion	Manding	unpitched	unpitched	N/A unpitched (existence per URL)	mid dunun (memory)	easy	https://en.wikipedia.org/wiki/List_of_drums
kenkeni	Kenkeni	drums and percussion	Manding	unpitched	unpitched	N/A unpitched (existence per URL)	small dunun (memory)	easy	https://en.wikipedia.org/wiki/List_of_drums
bougarabou	Bougarabou	drums and percussion	Casamance, Senegal	unpitched	unpitched	N/A unpitched (existence per URL)	open-bottom tapered drums played in sets (listed; description memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
ashiko	Ashiko	drums and percussion	Yoruba, Nigeria	unpitched	unpitched	N/A unpitched (existence per URL)	tapered hand drum (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
kpanlogo	Kpanlogo	drums and percussion	Ga, Ghana	unpitched	unpitched	N/A unpitched (existence per URL)	tall barrel hand drum (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
fontomfrom	Fontomfrom	drums and percussion	Akan, Ghana	unpitched	unpitched	N/A unpitched (existence per URL)	royal drum (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
gome	Gome	drums and percussion	Ghana (Ga/Ewe)	unpitched	unpitched	N/A unpitched (existence per URL)	box drum (listed in List of percussion; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
gudugudu	Gudugudu	drums and percussion	Yoruba, Nigeria	unpitched	unpitched	N/A unpitched (existence per URL)	small kettle-shaped drum (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
igba	Igba	drums and percussion	Yoruba, Nigeria	unpitched	unpitched	N/A unpitched (existence per URL)	drum (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
sakara drum	Sakara drum	drums and percussion	Yoruba, Nigeria	unpitched	unpitched	N/A unpitched (existence per URL)	shallow clay-frame drum (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
gbedu	Gbedu	drums and percussion	Yoruba, Nigeria	unpitched	unpitched	N/A unpitched (existence per URL)	large royal drum (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
ngoma	Ngoma drums	drums and percussion	Bantu Africa	unpitched	unpitched	N/A unpitched (existence per URL)	tall single-head drum family (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
udu	Udu	drums and percussion	Igbo, Nigeria	unpitched	unpitched	N/A unpitched (existence per URL)	pot drum with a hole, Helmholtz bass and slap (listed; memory)	sine with bend + noise; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
ekwe	Ekwe	drums and percussion	Igbo, Nigeria	unpitched	unpitched	N/A unpitched (existence per URL)	slit drum (listed; memory)	two-tone woody; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
ikoro	Ikoro	drums and percussion	Igbo, Nigeria	unpitched	unpitched	N/A unpitched (existence per URL)	large slit drum (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
axatse	Axatse	drums and percussion	Ewe, Ghana	unpitched	unpitched	N/A unpitched (existence per URL)	gourd rattle with outer bead net (listed; memory); kin to shekere	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
hosho	Hosho	drums and percussion	Zimbabwe (Shona)	unpitched	unpitched	N/A unpitched (existence per URL)	paired gourd rattles (listed; memory)	filtered noise; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
karkabou	Karkabou (qraqeb)	drums and percussion	Morocco (Gnawa)	unpitched	unpitched	N/A unpitched (existence per URL)	iron castanets (memory; not fetched)	metal clatter; easy	https://en.wikipedia.org/wiki/Krakebs
tbilat	Tbilat	drums and percussion	Maghreb	unpitched	unpitched	N/A unpitched (existence per URL)	paired small clay drums (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
ferrinho	Ferrinho	drums and percussion	Cape Verde	unpitched	unpitched	N/A unpitched (existence per URL)	iron rod scraped with metal (listed; memory)	metal scrape; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
makuta	Makuta	drums and percussion	Cuba/Congo	unpitched	unpitched	N/A unpitched (existence per URL)	drum (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
riq	Riq	drums and percussion	Arab world	unpitched	unpitched	N/A unpitched (existence per URL)	small frame drum with paired jingle cymbals (listed; memory)	drum pop + jingle burst; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
daf	Daf	drums and percussion	Iran, Kurdistan, Arab world, India	unpitched	unpitched	N/A unpitched (existence per URL)	frame drum with internal rings; listed under Indian hand frame drums too (VERIFIED)	deep thud + ring burst; easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
dayereh	Dayereh	drums and percussion	Iran, Central Asia	unpitched	unpitched	N/A unpitched (existence per URL)	frame drum with rings (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
tar drum	Tar (frame drum)	drums and percussion	North Africa, Middle East	unpitched	unpitched	N/A unpitched (existence per URL)	frame drum (listed as Tar (drum); memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
tombak	Tombak (zarb)	drums and percussion	Iran	unpitched	unpitched	N/A unpitched (existence per URL)	goblet drum (listed; memory)	finger rolls; moderate	https://en.wikipedia.org/wiki/List_of_percussion_instruments
naqareh	Naqareh (naqqara)	drums and percussion	Iran, Middle East	unpitched	unpitched	N/A unpitched (existence per URL)	small kettle drum pair (listed under three spellings VERIFIED)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
davul	Davul	drums and percussion	Turkey, Balkans, India	unpitched	unpitched	N/A unpitched (existence per URL)	large double-headed drum, in Indian list also (VERIFIED)	easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
kus	Kus (kos)	drums and percussion	Turkey, Ottoman	unpitched	unpitched	N/A unpitched (existence per URL)	large kettle (listed as Kus; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
dohol	Dohol	drums and percussion	Iran	unpitched	unpitched	N/A unpitched (existence per URL)	cylindrical bass drum (VERIFIED in list of drums)	easy	https://en.wikipedia.org/wiki/List_of_drums
tabor	Tabor	drums and percussion	medieval Europe	unpitched	unpitched	N/A unpitched (existence per URL)	shallow snare drum, 11-13 in (28-33 cm) wide per Snare drum article (VERIFIED)	snare; easy	https://en.wikipedia.org/wiki/Snare_drum
txalaparta	Txalaparta	drums and percussion	Basque Country	unpitched	unpitched	N/A unpitched (existence per URL)	struck wooden planks on trestles, idiophone (listed)	woody clack, pitched-ish; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
triccaballacca	Triccaballacca	drums and percussion	Sicily/Naples	unpitched	unpitched	N/A unpitched (existence per URL)	mallet-hammered clapper frame (listed; description memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
skrabalai	Skrabalai	tuned percussion	Lithuania	unpitched	unpitched	N/A unpitched (existence per URL)	tuned bells (listed; may be tuned percussion, UNVERIFIED)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
lagerphone	Lagerphone	drums and percussion	Australia, New Zealand, England	unpitched	unpitched	N/A unpitched (existence per URL)	pole with bottle tops struck on floor, bass-drum + tambourine mix; H-S 112.12 VERIFIED; monkey stick/ugly stick/zob stick are variants	noise thump; easy	https://en.wikipedia.org/wiki/Lagerphone
frottoir	Frottoir (rub-board)	drums and percussion	Louisiana zydeco	unpitched	unpitched	N/A unpitched (existence per URL)	vest-style ribbed metal, played with spoon handles, guiro-like rhythms (VERIFIED)	scrape noise; easy	https://en.wikipedia.org/wiki/Washboard_(musical_instrument)
stomp box	Stomp box	drums and percussion	USA folk and blues	unpitched	unpitched	N/A unpitched (existence per URL)	foot-struck wooden box (listed; sound memory)	low thump; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
sand blocks	Sand blocks	drums and percussion	USA	unpitched	unpitched	N/A unpitched (existence per URL)	sandpapered blocks rubbed (listed; memory)	noise swish; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
jam block	Jam block	drums and percussion	USA	unpitched	unpitched	N/A unpitched (existence per URL)	hollow plastic block (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
garamut	Garamut	drums and percussion	Papua New Guinea	unpitched	unpitched	N/A unpitched (existence per URL)	large log slit drum (memory)	low pulse; easy	https://en.wikipedia.org/wiki/Garamut
kundu	Kundu	drums and percussion	Papua New Guinea	unpitched	unpitched	N/A unpitched (existence per URL)	hourglass hand drum (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
teponaztli	Teponaztli	drums and percussion	Aztec Mexico	unpitched	unpitched	N/A unpitched (existence per URL)	slit log drum with two tongues giving two pitches (listed; memory)	two pitches; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
cultrun	Cultrun (kultrun)	drums and percussion	Mapuche Chile	unpitched	unpitched	N/A unpitched (existence per URL)	kettle drum with painted head (listed as Cultrun)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
bombo leguero	Bombo leguero	drums and percussion	Argentina	unpitched	unpitched	N/A unpitched (existence per URL)	(listed; keep)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
quijada	Quijada	drums and percussion	Latin America	unpitched	unpitched	N/A unpitched (existence per URL)	donkey jawbone (listed under Jawbone)	rattle noise; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
tambora	Tambora	drums and percussion	Dominican Republic, Colombia, Venezuela	unpitched	unpitched	N/A unpitched (existence per URL)	drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
guira	Guira	drums and percussion	Dominican Republic	unpitched	unpitched	N/A unpitched (existence per URL)	metal scraper (listed as Guira, distinct from wooden guiro)	HP noise; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
catá	Cata	drums and percussion	Cuba	unpitched	unpitched	N/A unpitched (existence per URL)	hollow log struck with sticks (listed; memory)	woody; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
repinique	Repinique (repique)	drums and percussion	Brazil	unpitched	unpitched	N/A unpitched (existence per URL)	samba drum (listed as Repique, Ring-repique)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
alfaia	Alfaia	drums and percussion	Pernambuco, Brazil	unpitched	unpitched	N/A unpitched (existence per URL)	large stick drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
atabaque	Atabaque	drums and percussion	Brazil	unpitched	unpitched	N/A unpitched (existence per URL)	tall hand drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
candombe drums	Candombe drums (chico, repique, piano)	drums and percussion	Uruguay	unpitched	unpitched	N/A unpitched (existence per URL)	three sizes (listed; sizes memory)	three voices; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
carimbo	Carimbo (curimbo)	drums and percussion	Brazil	unpitched	unpitched	N/A unpitched (existence per URL)	(listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
zabumba	Zabumba	drums and percussion	Brazil	unpitched	unpitched	N/A unpitched (existence per URL)	bass drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
caxixi	Caxixi	drums and percussion	Brazil	unpitched	unpitched	N/A unpitched (existence per URL)	basket rattle (listed)	soft noise; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
caxirola	Caxirola	drums and percussion	Brazil	unpitched	unpitched	N/A unpitched (existence per URL)	(listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
afoxe	Afoxe	drums and percussion	Brazil	unpitched	unpitched	N/A unpitched (existence per URL)	gourd rattle with bead net (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
ganza	Ganza	drums and percussion	Brazil	unpitched	unpitched	N/A unpitched (existence per URL)	metal tube shaker (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
reco reco	Reco-reco	drums and percussion	Brazil	unpitched	unpitched	N/A unpitched (existence per URL)	scraper (memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
gongue	Gongue	drums and percussion	Brazil (maracatu)	unpitched	unpitched	N/A unpitched (existence per URL)	iron double bell (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
esterilla	Esterilla	drums and percussion	Colombia	unpitched	unpitched	N/A unpitched (existence per URL)	scraper (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
pandero jarocho	Pandero jarocho	drums and percussion	Veracruz, Mexico	unpitched	unpitched	N/A unpitched (existence per URL)	frame drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
paila criolla	Paila criolla	drums and percussion	Venezuela, Colombia	unpitched	unpitched	N/A unpitched (existence per URL)	pan (timbale-like) (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
bamboula	Bamboula	drums and percussion	Haiti, New Orleans	unpitched	unpitched	N/A unpitched (existence per URL)	drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
tan tan	Tan-tan	drums and percussion	Cape Verde/Caribbean	unpitched	unpitched	N/A unpitched (existence per URL)	(listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
tifa	Tifa	drums and percussion	Maluku Indonesia	unpitched	unpitched	N/A unpitched (existence per URL)	single-headed drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
bedug	Bedug	drums and percussion	Indonesia	unpitched	unpitched	N/A unpitched (existence per URL)	mosque drum (listed)	deep boom; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
rebana	Rebana	drums and percussion	Malay world	unpitched	unpitched	N/A unpitched (existence per URL)	frame drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
kendang ageng	Kendang ageng	drums and percussion	Java	unpitched	unpitched	N/A unpitched (existence per URL)	largest, deepest tone; Javanese varieties wayang, ciblon (batangan), ketipung (smallest) (VERIFIED)	easy	https://en.wikipedia.org/wiki/Kendang
kendang ciblon	Kendang ciblon	drums and percussion	Java	unpitched	unpitched	N/A unpitched (existence per URL)	medium, lively rhythms (VERIFIED)	easy	https://en.wikipedia.org/wiki/Kendang
ketipung	Ketipung	drums and percussion	Java	unpitched	unpitched	N/A unpitched (existence per URL)	smallest kendang (VERIFIED)	easy	https://en.wikipedia.org/wiki/Kendang
kendang wadon	Kendang wadon and lanang	drums and percussion	Bali	unpitched	unpitched	N/A unpitched (existence per URL)	pair of equal-size drums, wadon lowest, lanang highest (VERIFIED)	two voices; easy	https://en.wikipedia.org/wiki/Kendang
ganrang	Ganrang (Makassarese kendang)	drums and percussion	Sulawesi	unpitched	unpitched	N/A unpitched (existence per URL)	lompo largest, pakarena 30-40 cm, pamancak 20-25 cm (VERIFIED)	easy	https://en.wikipedia.org/wiki/Kendang
kenong	Kenong	tuned percussion	Java	unpitched	unpitched	N/A unpitched (existence per URL)	gamelan kettle gong; listed; probably tuned percussion	pitched bossed; moderate	https://en.wikipedia.org/wiki/List_of_percussion_instruments
kempyang	Kempyang and ketuk	tuned percussion	Java	unpitched	unpitched	N/A unpitched (existence per URL)	small gong pair (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
kecer	Kecer	drums and percussion	Java	unpitched	unpitched	N/A unpitched (existence per URL)	cymbals (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
kepyak	Kepyak	tuned percussion	Java	unpitched	unpitched	N/A unpitched (existence per URL)	hanging metal plates (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
talempong	Talempong	tuned percussion	Minangkabau, Indonesia	unpitched	unpitched	N/A unpitched (existence per URL)	pitched bossed gongs; tuned percussion candidate	moderate	https://en.wikipedia.org/wiki/List_of_percussion_instruments
agung	Agung	drums and percussion	Philippines (Maguindanao)	unpitched	unpitched	N/A unpitched (existence per URL)	hanging gong (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
dabakan	Dabakan	drums and percussion	Philippines	unpitched	unpitched	N/A unpitched (existence per URL)	goblet drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
klong khaek	Klong khaek	drums and percussion	Thailand	unpitched	unpitched	N/A unpitched (existence per URL)	drum pair (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
taphon	Taphon	drums and percussion	Thailand	unpitched	unpitched	N/A unpitched (existence per URL)	barrel drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
samphor	Samphor	drums and percussion	Cambodia	unpitched	unpitched	N/A unpitched (existence per URL)	drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
trong chau	Trong chau	drums and percussion	Vietnam	unpitched	unpitched	N/A unpitched (existence per URL)	barrel drum (VERIFIED in list of drums)	easy	https://en.wikipedia.org/wiki/List_of_drums
dong son drums	Dong Son drum	tuned percussion	Vietnam, ancient	unpitched	unpitched	N/A unpitched (existence per URL)	bronze kettle drum (listed, H-S idiophone actually; memory)	metallic boom; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
buk	Buk	drums and percussion	Korea	unpitched	unpitched	N/A unpitched (existence per URL)	barrel drum for pansori, pungmul, samulnori (VERIFIED)	easy	https://en.wikipedia.org/wiki/Janggu
jing	Jing	drums and percussion	Korea	unpitched	unpitched	N/A unpitched (existence per URL)	large gong (VERIFIED)	long swell; easy	https://en.wikipedia.org/wiki/Janggu
kkwaenggwari	Kkwaenggwari	drums and percussion	Korea	unpitched	unpitched	N/A unpitched (existence per URL)	small bright gong (VERIFIED)	easy	https://en.wikipedia.org/wiki/Janggu
bak	Bak	drums and percussion	Korea	unpitched	unpitched	N/A unpitched (existence per URL)	wooden clapper (VERIFIED), listed also in WP list	clap click; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
eo	Eo	drums and percussion	Korea	unpitched	unpitched	N/A unpitched (existence per URL)	tiger-shaped scraper, bamboo whisk across serrated back (VERIFIED)	ratchet scrape; easy	https://en.wikipedia.org/wiki/Janggu
chuk	Chuk	drums and percussion	Korea	unpitched	unpitched	N/A unpitched (existence per URL)	wooden box struck inside with stick (VERIFIED)	hollow knock; easy	https://en.wikipedia.org/wiki/Janggu
pyeongyeong	Pyeongyeong	tuned percussion	Korea	unpitched	unpitched	N/A unpitched (existence per URL)	lithophone chime, different pitches (VERIFIED); tuned percussion	tuned; moderate	https://en.wikipedia.org/wiki/Janggu
jwago	Jwago	drums and percussion	Korea	unpitched	unpitched	N/A unpitched (existence per URL)	suspended drum (VERIFIED as unpitched in Korean source)	easy	https://en.wikipedia.org/wiki/Janggu
moktak	Moktak (wooden fish)	drums and percussion	Korea	unpitched	unpitched	N/A unpitched (existence per URL)	wooden fish (memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
tanggu	Tanggu	drums and percussion	China	unpitched	unpitched	UNVERIFIED (existence per URL)	(memory; sole source the first audit)	UNVERIFIED	https://en.wikipedia.org/wiki/List_of_percussion_instruments
paigu	Paigu	drums and percussion	China	unpitched	unpitched	UNVERIFIED (existence per URL)	(memory)	UNVERIFIED	https://en.wikipedia.org/wiki/List_of_percussion_instruments
bo	Bo (Chinese cymbals)	drums and percussion	China	unpitched	unpitched	N/A unpitched (existence per URL)	(listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
paiban	Paiban	drums and percussion	China	unpitched	unpitched	N/A unpitched (existence per URL)	clapper (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
tiger gong	Tiger gong	drums and percussion	China	unpitched	unpitched	N/A unpitched (existence per URL)	opera gong with slight descending (rarely ascending) pitch shift (VERIFIED)	easy	https://en.wikipedia.org/wiki/Gong
nao	Nao (Chinese large cymbals)	drums and percussion	China	unpitched	unpitched	UNVERIFIED (existence per URL)	(memory)	UNVERIFIED	https://en.wikipedia.org/wiki/List_of_percussion_instruments
dollu	Dollu	drums and percussion	Karnataka	unpitched	unpitched	N/A unpitched (existence per URL)	drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
damphu	Damphu drum	drums and percussion	Nepal/Bhutan	unpitched	unpitched	N/A unpitched (existence per URL)	frame drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
madal	Madal	drums and percussion	Nepal	unpitched	unpitched	N/A unpitched (existence per URL)	barrel hand drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
dhimay	Dhimay	drums and percussion	Nepal (Newar)	unpitched	unpitched	N/A unpitched (existence per URL)	stick drum (VERIFIED in Indian list)	easy	https://en.wikipedia.org/wiki/List_of_Indian_musical_instruments
nagado daiko	Nagado daiko (chu-daiko)	drums and percussion	Japan	unpitched	unpitched	N/A unpitched (existence per URL)	barrel nailed-head, 30-182 cm heads, chu-daiko 48-85 cm (VERIFIED)	easy	https://en.wikipedia.org/wiki/Taiko
shime daiko	Shime daiko	drums and percussion	Japan	unpitched	unpitched	N/A unpitched (existence per URL)	tunable rope-tensioned about 27 cm (VERIFIED)	high crack; easy	https://en.wikipedia.org/wiki/Taiko
okedo daiko	Okedo daiko	drums and percussion	Japan	unpitched	unpitched	N/A unpitched (existence per URL)	stave-built (VERIFIED)	easy	https://en.wikipedia.org/wiki/Taiko
hira daiko	Hira daiko	drums and percussion	Japan	unpitched	unpitched	N/A unpitched (existence per URL)	flat nailed-head (VERIFIED)	easy	https://en.wikipedia.org/wiki/Taiko
tsuri daiko	Tsuri daiko	drums and percussion	Japan	unpitched	unpitched	N/A unpitched (existence per URL)	suspended, 55 cm head, bugaku (VERIFIED)	easy	https://en.wikipedia.org/wiki/Taiko
uchiwa daiko	Uchiwa daiko	drums and percussion	Japan	unpitched	unpitched	N/A unpitched (existence per URL)	fan drum (VERIFIED)	easy	https://en.wikipedia.org/wiki/Taiko
den den daiko	Den-den daiko	drums and percussion	Japan	unpitched	unpitched	N/A unpitched (existence per URL)	pellet drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
shoko	Shoko	drums and percussion	Japan	unpitched	unpitched	N/A unpitched (existence per URL)	gagaku gong (listed; memory)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
hyoshigi	Hyoshigi	drums and percussion	Japan	unpitched	unpitched	N/A unpitched (existence per URL)	wooden clappers (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
binzasara	Binzasara	drums and percussion	Japan	unpitched	unpitched	N/A unpitched (existence per URL)	clapper of wooden slats (listed distinct from sasara)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
singing bowl	Singing bowl	tuned percussion	Himalaya, Asia	unpitched	unpitched	N/A unpitched (existence per URL)	(listed; likely tuned percussion)	moderate	https://en.wikipedia.org/wiki/List_of_percussion_instruments
shishi odoshi	Shishi-odoshi	drums and percussion	Japan	unpitched	unpitched	N/A unpitched (existence per URL)	bamboo water knocker (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
piccolo snare	Piccolo snare	drums and percussion	modern kit	unpitched	unpitched	N/A unpitched (existence per URL)	about 3 in depth, pitch higher; soprano 12-13 in; popcorn 10 in (VERIFIED)	easy	https://en.wikipedia.org/wiki/Snare_drum
popcorn snare	Popcorn snare	drums and percussion	modern kit	unpitched	unpitched	N/A unpitched (existence per URL)	10-12 in shallow (VERIFIED)	easy	https://en.wikipedia.org/wiki/Snare_drum
marching snare	Marching snare	drums and percussion	modern	unpitched	unpitched	N/A unpitched (existence per URL)	14 in x 12 in deep (VERIFIED)	easy	https://en.wikipedia.org/wiki/Snare_drum
pipe band snare	Pipe band snare	drums and percussion	Scotland	unpitched	unpitched	N/A unpitched (existence per URL)	deep, tight, second snare set (VERIFIED)	easy	https://en.wikipedia.org/wiki/Snare_drum
field drum	Field drum	drums and percussion	Europe/US	unpitched	unpitched	N/A unpitched (existence per URL)	14-16 in dia, 9-16 in deep (VERIFIED)	easy	https://en.wikipedia.org/wiki/Snare_drum
tarol	Tarol	drums and percussion	Brazil	unpitched	unpitched	N/A unpitched (existence per URL)	snares on top head (VERIFIED)	easy	https://en.wikipedia.org/wiki/Snare_drum
caixa malacacheta	Caixa malacacheta	drums and percussion	Southern Brazil	unpitched	unpitched	N/A unpitched (existence per URL)	12 or 14 in x 8 in (VERIFIED)	easy	https://en.wikipedia.org/wiki/Snare_drum
concert tom	Concert tom	drums and percussion	modern	unpitched	unpitched	N/A unpitched (existence per URL)	single-headed (VERIFIED)	easy	https://en.wikipedia.org/wiki/Tom-tom_drum
rototom	Rototom	drums and percussion	USA	unpitched	unpitched	N/A unpitched (existence per URL)	shell-less, definite variable pitch (VERIFIED)	pitched sine sweep; easy	https://en.wikipedia.org/wiki/Tom-tom_drum
octoban	Octoban	drums and percussion	modern	unpitched	unpitched	N/A unpitched (existence per URL)	related drum (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
gong bass drum	Gong bass drum	drums and percussion	modern	unpitched	unpitched	N/A unpitched (existence per URL)	large single-headed tom, 20-22 in (VERIFIED)	easy	https://en.wikipedia.org/wiki/Tom-tom_drum
swish cymbal	Swish cymbal	drums and percussion	modern kit	unpitched	unpitched	N/A unpitched (existence per URL)	(listed in Cymbal types)	easy	https://en.wikipedia.org/wiki/Cymbal
sizzle cymbal	Sizzle cymbal	drums and percussion	modern kit	unpitched	unpitched	N/A unpitched (existence per URL)	(rivets; memory)	easy	https://en.wikipedia.org/wiki/Cymbal
flat ride cymbal	Flat ride cymbal	drums and percussion	modern kit	unpitched	unpitched	N/A unpitched (existence per URL)	listed (VERIFIED)	easy	https://en.wikipedia.org/wiki/Cymbal
crash ride cymbal	Crash/ride cymbal	drums and percussion	modern kit	unpitched	unpitched	N/A unpitched (existence per URL)	listed (VERIFIED) -> name 'crash ride cymbal'	easy	https://en.wikipedia.org/wiki/Cymbal
tingsha	Tingsha	drums and percussion	Tibet/Nepal	unpitched	unpitched	N/A unpitched (existence per URL)	small paired cymbals on a strap (listed)	sines; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
bossed gong	Nipple (bossed) gong	drums and percussion	Asia	unpitched	unpitched	N/A unpitched (existence per URL)	15-50 cm, often tuned, differs boss vs side strike (VERIFIED); overlaps catalog tuned gong	moderate	https://en.wikipedia.org/wiki/Gong
bell plate	Bell plate	tuned percussion	modern orchestral	unpitched	unpitched	N/A unpitched (existence per URL)	(listed)	metallic ring; moderate	https://en.wikipedia.org/wiki/List_of_percussion_instruments
wind machine	Wind machine	drums and percussion	theatre	unpitched	unpitched	N/A unpitched (existence per URL)	(listed)	filtered noise; easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
lummi stick	Lummi stick	drums and percussion	USA	unpitched	unpitched	N/A unpitched (existence per URL)	(listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
boobam	Boobam	tuned percussion	USA	unpitched	unpitched	N/A unpitched (existence per URL)	bamboo tuned tubes (listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments
pixiphone	Pixiphone	tuned percussion	toy	unpitched	unpitched	N/A unpitched (existence per URL)	(listed)	easy	https://en.wikipedia.org/wiki/List_of_percussion_instruments

Notes on the table: rows whose family is "tuned percussion" are pitched or gamelan-type items placed there for the caller to route. Rows tagged "(listed)" exist per Wikipedia's List of percussion instruments (https://en.wikipedia.org/wiki/List_of_percussion_instruments), sound text from memory. Not yet in table because not checked: see Gaps.

## Rejected or corrected proposed entries

- jingle bells: same class as sleigh bells (both appear in the WP list, https://en.wikipedia.org/wiki/List_of_percussion_instruments, but as strung pellet bells they are one sound); treat as alias unless stick version wanted (UNVERIFIED difference).
- thunder tube: H-S "17" is not a valid number (memory); rename "thunder tube" only if a source for a spring/tube instrument is found; likely the spring drum (UNVERIFIED).
- bones: H-S "111.1x" corrected to 111.11 concussion sticks, 12-18 cm (VERIFIED, https://en.wikipedia.org/wiki/Bones_(instrument)).
- jaw harp: wrong family (free reeds); H-S 121.2 corrected to 121.22 (VERIFIED, Jew's harp article).
- lion's roar: name has apostrophe (use lions roar); "below C3" range is meaningless, friction drum, unpitched (https://en.wikipedia.org/wiki/List_of_drums lists it as friction drum, VERIFIED).
- pellet drum (bolang gu / tao): name violates naming rules, merges a class with Chinese/Japanese regional types; use "pellet drum"; damaru is a separate proposed entry (pellet drum is the class, VERIFIED as separate WP entry; Den-den daiko is the Japanese form, listed).
- sasara / binzasara: slash name; binzasara is listed separately by WP list as a distinct instrument (clapper of slats); split.
- intonarumori (noise intoners), drum machine voices (808 and 909 style): parentheses; drum machine voices belong to electronic (also catalog has electronic kick/snare).
- chip noise, chip dpcm sample, rhythmicon, wurlitzer side man, drum machine voices, syndrum: electronic family, not drums.
- mridangam, ghatam, talking drum, atumpan: ranges "tuned C3-G3 est." etc are unsourced; mridangam article says tuned by pitch pipe/tambura but names no note (VERIFIED https://en.wikipedia.org/wiki/Mridangam); talking drum article gives no range (VERIFIED https://en.wikipedia.org/wiki/Talking_drum).
- kemanak, ghatam range: kemanak is gamelan, pitched; better tuned percussion; sources unchecked.
- flexatone, bell tree, mark tree, wind chimes: pitched; route to tuned percussion rather than unpitched family.
- ocean drum, boobam, wobble board: exist (listed on WP list); ocean drum attribution to Messiaen 1972 (France) UNVERIFIED.
- shekere vs axatse vs cabasa (catalog): axatse appears as separate WP entry; cabasa/afuche likely alias; not all verified.
- kendang (generic) is too coarse: WP (https://en.wikipedia.org/wiki/Kendang) separates ageng, wayang, ciblon, ketipung, Balinese wadon/lanang, Makassar ganrang (VERIFIED); added above.
- Name collision warning: proposed "dunun" (Manding cylindrical bass drum) vs Yoruba "dundun" (hourglass talking drum) are different drums; WP gives dundun and gangan as Yoruba names of the talking drum (VERIFIED).
- rhythmicon: not an instrument family fit; keep out.

## Aliases

- jingle bells -> sleigh bells
- dundun (Yoruba) -> talking drum (gangan alias; VERIFIED)
- gangan -> talking drum
- kalangu, dan karbi -> talking drum (Hausa; VERIFIED)
- tama, tamma, tamanin -> talking drum (tama also a distinct tiny Wolof build; VERIFIED)
- donno, lunna, odondo, doodo, obodom -> talking drum (VERIFIED regional names)
- chau gong -> tam tam (VERIFIED, Gong article)
- naqara, naqqara, naqareh -> nagara (cluster; WP lists three spellings)
- morsing, khomus, kouxian, mukkuri, kubing, gogona, karinding, morchang -> jaw harp (VERIFIED)
- ugly stick, monkey stick, zob stick -> lagerphone (VERIFIED for monkey/zob; ugly stick listed)
- frottoir, zydeco rub-board, vest frottoir -> washboard variants (VERIFIED)
- zatulas -> washboard (Ukrainian; VERIFIED)
- tavil -> thavil (VERIFIED)
- chende -> chenda (Tulu; VERIFIED)
- khanjani, kanjira, ganjira -> kanjira cluster (UNVERIFIED)
- tabl -> tabla/davul variants (UNVERIFIED)
- doira -> dayereh (memory)
- zilli, zills -> finger cymbals (memory)
- gran cassa -> orchestral bass drum (memory)
- cencerro -> cowbell (memory)
- timbal -> timbale (memory; WP list shows Timbal and Timbales separately)
- guayo -> guira (memory)
- tabor pipe drum -> tabor (VERIFIED size)
- afuche -> cabasa (memory)
- edakka -> idakka (listed; spelling variants)
- tumbak, tumbaknari -> tombak/tumbak cluster (Indian list)
- tabla bayan (catalog) = left drum of tabla pair

## Range checks

All unpitched. VERIFIED statements:
- sabar: no pitch; ensemble of drums of different sizes (VERIFIED, https://sites.google.com/bc.edu/bc-west-african-music-ensemble/sabar-in-culture/drum-types).
- talking drum: pitch rises with squeeze; no absolute range given; proposed "C3-C4" UNVERIFIED.
- mridangam: proposed "C3-G3" UNVERIFIED (tuned to singer tonic, no fixed note).
- kebero, thavil, chenda: sources give no pitch; thavil's larger face is higher pitched.
- gong/tam-tam: tam-tam gives crash not tuned note (VERIFIED); nipple gongs often tuned; daluo descending, xiaoluo rising (VERIFIED).
- cymbals: most indefinite pitch; bell gives higher ping; crotales definite (VERIFIED, https://en.wikipedia.org/wiki/Cymbal).
- snare/tom diameters VERIFIED above (Snare drum, Tom-tom articles).
- Korean bak, buk, janggu, jing, kkwaenggwari, jwago unpitched; pyeongyeong/pyeonjong pitched (search summary of a mirror; VERIFIED weakly).
- ghatam, pakhavaj, dholak, kanjira, bendir, kendang, nagara, water drum, huehuetl, trong com: ranges UNVERIFIED.
- bell tree, mark tree, flexatone, anvil, tuning fork-like items: UNVERIFIED, pitched; "C6-C8" etc rejected as memory.

## Gaps you could not close

- MIMO, the Met, Horniman and Grove were not consulted; run those for chenda/thavil/sabar sub-variants and for missing African and Oceanic drums.
- Wikipedia list truncations: List of percussion instruments membranophone section stops at Sambal drum in the first slice; entries between Sambal and R (e.g. Sistrum, Shekere) and the idiophone section end were not fully seen. Suspect missing: sistrum, kudum, davandai, nyatiti (plucked drum-lyre), tabla tarang (tuned), geophone, mirwas, bara, aburukuwa, babendil, bubon, junjung, jori, pambai, derkach, malimbe, kisanji (lamellophone), ikembe.
- Korean list page 404; Korean drum names beyond the seven found (e.g. sogo, jinggoh, galgo, jeolgu, yonggo, jin-gu, yeonggo, bu, chuk) not checked.
- Folk: spoons page 404, so spoons H-S unverified (proposed 111.14 may be wrong; bones are 111.11).
- Cuban/Puerto Rican: bomba barrels (buleador/subidor), cua, palos, tambor alegre/llamador (Colombia), cununo, guacharaca, maracon not searched.
- Oceania: to'ere, ipu heke, ili'ili, uli'uli, lali not fetched (memory); Maori and Fijian forms unverified.
- Indigenous Americas: powwow drum, turtle shell rattle, ayoyotes, chachayotl, Inuit qilaut not searched.
- Eastern Europe/Central Asia: doira, davul variants, qaval, shaman drums, rommelpot, zambomba (listed as friction drum, VERIFIED), putipu (friction), tsymbaly are cited only in lists.
- Modeling: no instrument here needs more than noise + short sine except: udu/ghatam/pot drums (Helmholtz resonance, approximated by damped sine), tingsha/singing bowl (inharmonic ringing, long decay), mridangam/pakhawaj/kendang (membrane ring with pitch bend; a pitch-envelope sine suffices), friction drums (cuica, lions roar, eo, rommelpot: sawtooth with pitch sweep), waterphone/rototom (pitch sweep), jaw harp (narrow formant sweep on a sawtooth). Frame drums with jingles (riq, daf, mazhar) need the 4-source budget: drum body + jingle noise + metal partials.
