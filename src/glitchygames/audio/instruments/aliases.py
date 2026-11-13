"""Other names for catalog instruments (``instruments.entry`` and ``get`` resolve them).

Each key is an alias, lower-case words separated by single spaces, and each value is the catalog
name it stands for. ``registry.aliases_from`` checks the table when the catalog is assembled: an
alias may not be a catalog name, and its target must be one.
"""

from typing import Final

ALIASES: Final[dict[str, str]] = {
    # https://en.wikipedia.org/wiki/Slapstick_(instrument): "a whip or slapstick is a clapper"
    'slapstick': 'whip',
    # https://en.wikipedia.org/wiki/Mbira: the mbira is "also known as kalimba and zanza"
    'zanza': 'mbira',
    # https://en.wikipedia.org/wiki/Music_box: pins "on a revolving cylinder or disc" pluck "the
    # tuned teeth ... of a steel comb"; the catalog music box is this cylinder comb
    'cylinder music box': 'music box',
    # https://en.wikipedia.org/wiki/Polyphon: star wheels pluck the same kind of comb; no range
    'disc music box': 'music box',
    # https://en.wikipedia.org/wiki/Wurlitzer_electric_piano: sound by "striking a metal reed with
    # a felt hammer", read by an electrostatic pickup: the catalog reed electric piano (the
    # audit's spelling is "electronic")
    'wurlitzer electronic piano': 'reed electric piano',
    # https://en.wikipedia.org/wiki/Hohner_Clavinet: Hohner's instrument, "most models have 60
    # keys ranging from F1 to E6", the catalog clavinet's range
    'hohner clavinet': 'clavinet',
    # https://api.vam.ac.uk/v2/object/O74191: the object history says "This rain box" and the brief
    # description calls it a "rain machine": the same device
    'rain box': 'rain machine',
    # https://theatrecrafts.com/pages/home/topics/sound/sound-effects-for-the-stage/: "the classic
    # coconut halves for horses hooves"
    'horse hooves': 'coconut shells',
    # Batch 3's drums (membranophones), in the order of plans/data/instrument-audit/batch-3.tsv:
    # each is another name for the same instrument. A distinct drum that sounds like an entry is
    # its own entry (``sounds_like``, in drum_sound_alikes.py), not an alias
    # https://en.wikipedia.org/wiki/Daf: "The daf (Persian: دف), also known as dap (دپ), dâyere or
    # riq"; another name for the daf
    'dayereh': 'daf',
    # https://en.wikipedia.org/wiki/Kendang: "Makassar: gandrang or ganrang) is a two-headed drum
    # used by people from the Indonesian Archipelago"; another name for the kendang
    'ganrang': 'kendang',
    # https://en.wikipedia.org/wiki/Naqareh https://en.wikipedia.org/wiki/Nagara_(drum): "The
    # naqareh, naqqāra, nagara or nagada is a Middle Eastern drum with a rounded back and a hide
    # head, usually played in pairs"; another name for the naqareh
    'nagara': 'naqareh',
    # https://en.wikipedia.org/wiki/Timbales: "Timbaleta, pailas, pailas criollas"; another name for
    # the high timbale
    'paila criolla': 'high timbale',
    # https://en.wikipedia.org/wiki/Daf: "dâyere or riq, is an Iranian frame drum musical
    # instrument"; another name for the daf
    'riq': 'daf',
    # https://en.wikipedia.org/wiki/Naqareh: "In Uzbekistan the kettledrum is called naqara or
    # nagora"; another name for the naqareh
    'naqara': 'naqareh',
    # https://en.wikipedia.org/wiki/Naqareh: "The naqareh, naqqāra, nagara or nagada is a Middle
    # Eastern drum"; another name for the naqareh
    'naqqara': 'naqareh',
    # https://en.wikipedia.org/wiki/Thavil: "or tavil is a barrel-shaped percussion instrument from
    # Tamil Nadu"; another name for the thavil
    'tavil': 'thavil',
    # https://en.wikipedia.org/wiki/Chenda: "In Tulu Nadu (Coastal Karnataka), it is known as
    # chende"; another name for the chenda
    'chende': 'chenda',
    # https://en.wikipedia.org/wiki/Kanjira: "The kanjira, khanjira, khanjiri or ganjira, a South
    # Indian frame drum, is an instrument of the tambourine family"; another name for the kanjira
    'ganjira': 'kanjira',
    # https://en.wikipedia.org/wiki/Daf: "dafli, dap, def, tef, defi, qaval, duf, duff, dof, doira";
    # another name for the daf
    'doira': 'daf',
    # https://en.wikipedia.org/wiki/Bass_drum: "the orchestral, or concert bass drum (in Italian:
    # gran cassa, gran tamburo). It is the largest drum of the orchestra"; another name for the
    # orchestral bass drum
    'gran cassa': 'orchestral bass drum',
    # Batch 3's idiophones, in the order of the same sheet: each another name for the same
    # instrument. An alias may name a sound-alike entry (the rainstick, sandpaper blocks, frottoir)
    # or an entry of another family (the tuned gong, tuned percussion)
    # https://en.wikipedia.org/wiki/Gong: "In Western symphonic music, the flat faced gongs are
    # generally referred to as tam-tams to distinguish them from their bossed counterparts. Here,
    # the term "gong" is reserved for the bossed type only"; "They are most often but not always
    # tuned to various pitches"; another name for the tuned gong
    'bossed gong': 'tuned gong',
    # https://en.wikipedia.org/wiki/Rainstick: "A rainstick is a long, hollow tube of bamboo or
    # dried cactus that is partially flooded with small pebbles"; another spelling of the rainstick
    'rain stick': 'rainstick',
    # https://tetonmusic.com/products/basic-beat-sand-blocks-with-handle: "Sliding one sand block
    # against the other makes a shaker-like sound. The sandpaper is securely attached to each of
    # the wood blocks"; another name for the sandpaper blocks
    'sand blocks': 'sandpaper blocks',
    # https://en.wikipedia.org/wiki/Jingle_bell: "A jingle bell or sleigh bell is a type of bell";
    # "Sleigh bells" redirects there; another name for the jingle bells
    'sleigh bells': 'jingle bells',
    # https://en.wikipedia.org/wiki/Gong: "By far the most familiar to most Westerners is the chau
    # gong or bullseye gong. Large chau gongs, called tam-tams"; another name for the tam tam
    'chau gong': 'tam tam',
    # https://en.wikipedia.org/wiki/Monkey_stick: "In Newfoundland, it is referred to as an "ugly
    # stick""; another name for the lagerphone
    'ugly stick': 'lagerphone',
    # https://en.wikipedia.org/wiki/Monkey_stick: "A monkey stick (also called a mendoza, mendozer,
    # Murrumbidgee river rattler, lagerphone or zob stick)"; another name for the lagerphone
    'monkey stick': 'lagerphone',
    # https://en.wikipedia.org/wiki/Monkey_stick: "(also called a mendoza, mendozer, Murrumbidgee
    # river rattler, lagerphone or zob stick)"; another name for the lagerphone
    'zob stick': 'lagerphone',
    # https://en.wikipedia.org/wiki/Washboard_(musical_instrument): "Conversely, the frottoir
    # (zydeco rubboard) dispenses with the frame"; another name for the frottoir
    'zydeco rubboard': 'frottoir',
    # https://en.wikipedia.org/wiki/Washboard_(musical_instrument): "The frottoir or vest frottoir
    # is played as a stroked percussion instrument"; another name for the frottoir
    'vest frottoir': 'frottoir',
    # https://en.wikipedia.org/wiki/Washboard_(musical_instrument): "In Ukrainian folk music,
    # washboards, or "zatulas", are also occasionally used"; another name for the washboard
    'zatulas': 'washboard',
    # https://en.wikipedia.org/wiki/Zill: "Zills, or finger cymbals"; the infobox's "Other names"
    # list includes "zillia"; another name for the finger cymbals
    'zillia': 'finger cymbals',
    # https://en.wikipedia.org/wiki/Zill: "Zills, or finger cymbals, are part of a family of musical
    # instruments known as clappers"; another name for the finger cymbals
    'zills': 'finger cymbals',
    # https://en.wikipedia.org/wiki/Cencerro: Wikipedia redirects it to the Cowbell (instrument)
    # article ("(Redirected from Cencerro)"); another name for the cowbell
    'cencerro': 'cowbell',
    # https://en.wikipedia.org/wiki/Cabasa: "This company has built a more durable cabasa that they
    # call an afuche-cabasa"; another name for the cabasa
    'afuche': 'cabasa',
    # --- Batch 4's necked lutes (321.3), in the order of plans/data/instrument-audit/batch-4.tsv
    # https://en.wikipedia.org/wiki/Ukulele: the contrabass size's other names, "| Contrabass |
    # U-Bass, Rumbler | 32 in (81 cm)"; another name for the contrabass ukulele
    'rumbler': 'contrabass ukulele',
    # https://en.wikipedia.org/wiki/Ukulele: "| Contrabass | U-Bass, Rumbler" and "E1-A1-D2-G2
    # for U-Bass style instruments (sometimes called contrabass)"; another name for the
    # contrabass ukulele
    'u bass': 'contrabass ukulele',
    # https://en.wikipedia.org/wiki/Tar_(string_instrument): the tar "was originally known as
    # the chahartar (چهارتار) or chartar (چارتار), which translates into Persian as
    # 'four-stringed'"; another (older) name for the tar
    'chartar': 'tar',
    # https://en.wikipedia.org/wiki/Chitarrone: "\"Chitarrone\" redirects here" (to the Theorbo
    # page, which says "Although the words chitarrone and tiorba were both used to describe the
    # instrument"); another name for the theorbo
    'chitarrone': 'theorbo',
    # https://en.wikipedia.org/wiki/Hawaiian_steel_guitar (redirects to the Lap steel guitar
    # page): "The lap steel guitar, also known as a Hawaiian guitar or lap slide guitar";
    # another name for the lap steel guitar
    'hawaiian steel guitar': 'lap steel guitar',
    # https://en.wikipedia.org/wiki/Liuqin: the infobox's alternative Chinese name 柳葉琴, "Hanyu
    # Pinyin | liǔyèqín"; another name for the liuqin
    'liuyeqin': 'liuqin',
    # https://en.wikipedia.org/wiki/Mandolino (the Mandolin page): "There were a variety of
    # regional variants, but the two most widespread ones were the Neapolitan mandolin and the
    # Lombard mandolin"; "The Neapolitan style has spread worldwide"; the catalog mandolin is
    # this round-backed form, so another name for it
    'neapolitan mandolin': 'mandolin',
    # https://en.wikipedia.org/wiki/Ruan_(instrument): "tenor: zhongruan (中阮, lit. \"medium
    # ruan\"; tuning: G2-D3-G3-D4)", the size the page calls commonly used and the catalog ruan;
    # another name for the ruan
    'zhongruan': 'ruan',
    # https://en.wikipedia.org/wiki/Ukulele: "Less common are the sopranino (also called
    # piccolo, bambino, or \"pocket uke\")"; another name for the sopranino ukulele
    'piccolo ukulele': 'sopranino ukulele',
    # https://en.wikipedia.org/wiki/Ukulele: "Less common are the sopranino (also called
    # piccolo, bambino, or \"pocket uke\")"; "| Pocket | piccolo, sopranino, sopranissimo";
    # another name for the sopranino ukulele
    'pocket ukulele': 'sopranino ukulele',
    # https://en.wikipedia.org/wiki/Ukulele: the Pocket size's other names, "| Pocket | piccolo,
    # sopranino, sopranissimo | 16 in (41 cm)"; another name for the sopranino ukulele
    'sopranissimo': 'sopranino ukulele',
    # https://en.wikipedia.org/wiki/Tar_(lute): "\"Taar\" redirects here"; another spelling of
    # the tar
    'taar': 'tar',
    # https://en.wikipedia.org/wiki/Bouzouki: infobox range "C3 - E6 (tetrachordo), D3 - E6
    # (trichordo)"; "The four-course bouzouki was made popular by Manolis Chiotis"; the catalog
    # greek bouzouki is the four-course (tetrachordo) instrument, so another name for it
    'tetrachordo bouzouki': 'greek bouzouki',
    # https://en.wikipedia.org/wiki/Ba%C4%9Flama: "The bağlama, saz, tambura or bozuk is a
    # long-necked fretted lute used in the folk music of Turkey"; another name for the saz
    'baglama': 'saz',
    # https://en.wikipedia.org/wiki/Ba%C4%9Flama: "The bağlama, saz, tambura or bozuk is a
    # long-necked fretted lute"; another name for the saz
    'bozuk': 'saz',
    # https://en.wikipedia.org/wiki/Oud: "Turkish ouds have been played by Anatolian Greeks,
    # where they are called outi"; another name for the oud
    'outi': 'oud',
    # https://en.wikipedia.org/wiki/Oud: "The oud (Arabic, romanized: ʿūd";
    # another spelling of the oud
    'ud': 'oud',
    # https://en.wikipedia.org/wiki/Qanun_(instrument): "The qanun, kanun, ganoun or kanoon (Arabic:
    # qanun; ... Greek: kanonaki"; the Greek name of the qanun
    'kanonaki': 'qanun',
    # https://en.wikipedia.org/wiki/Kanun (redirects to the Qanun page): "The qanun, kanun, ganoun
    # or kanoon"; another spelling of the qanun
    'kanun': 'qanun',
    # --- Batch 5's bars, plaques, tubes and stones, in the order of
    # plans/data/instrument-audit/batch-5.tsv
    # https://en.wikipedia.org/wiki/Glockenspiel: "In the United Kingdom, the United States, and
    # Canada, a form of glockenspiel is called a bell lyre, bell lyra, or lyra-glockenspiel."; the
    # marching glockenspiel in a lyre-shaped frame, so another name for the glockenspiel
    'bell lyra': 'glockenspiel',
    # https://en.wikipedia.org/wiki/Boomwhacker: the page's own title is the singular ("A
    # Boomwhacker is a percussion instrument ..."); another name for boomwhackers
    'boomwhacker': 'boomwhackers',
    # https://en.wikipedia.org/wiki/Saron_(instrument): "Saron barung (sometimes just saron)";
    # another name for the saron
    'saron barung': 'saron',
    # https://www.vsl.co.at/academy/percussion/glockenspiel: "Glockenspiel (orchestra bells)";
    # another name for the glockenspiel
    'orchestra bells': 'glockenspiel',
    # https://en.wikipedia.org/wiki/Tubular_bells: "Tubular bells (also known as chimes)"; another
    # name for the tubular bells
    'chimes': 'tubular bells',
    # https://en.wikipedia.org/wiki/Tubular_bells: the infobox's alternative names, "Chimes",
    # "orchestral chimes"; another name for the tubular bells
    'orchestral chimes': 'tubular bells',
    # --- Batch 5's gongs, bells, pans and drums (and `antique cymbals`, a plaque row written
    # here), in the order of plans/data/instrument-audit/batch-5.tsv
    # https://en.wikipedia.org/wiki/Standing_bell: the page lists the "rin gong" and "Japanese rin
    # played as struck idiophone" among the standing bells; the struck standing bell is the
    # catalog's singing bowl, and the page gives the rin no pitch of its own
    'rin': 'singing bowl',
    # https://pan-mag.com/basics-of-steelpan-instruments-in-the-steel-orchestra/: the tenor pan is
    # "sometimes referred to as the lead pan, soprano pan or single tenor", range "most often
    # from C4 to E6", which matches the catalog tenor steel pan's range (C4 to E6)
    'soprano steel pan': 'tenor steel pan',
    # https://en.wikipedia.org/wiki/Crotales: crotales are "sometimes called antique cymbals"
    'antique cymbals': 'crotales',
    # https://en.wikipedia.org/wiki/Glass_harp: "verrillon or ghost fiddle" is another name of the
    # glass harp; this crosses families (friction instruments), as aliases are catalog-wide
    'verrillon': 'glass harp',
    # https://pan-mag.com/basics-of-steelpan-instruments-in-the-steel-orchestra/: the tenor pan is
    # "sometimes referred to as the lead pan, soprano pan or single tenor"
    'lead pan': 'tenor steel pan',
    # https://en.wikipedia.org/wiki/Steelpan: its table lists "Single Tenor, or Ping Pong" at
    # soprano pitch, the same top pan the PAN Magazine page calls the tenor pan
    'ping pong': 'tenor steel pan',
    # https://en.wikipedia.org/wiki/Mbira: the infobox's other names include "sansa, sansu, sanza,
    # thumb piano"; the lead has "kalimba and zanza (or variant spellings)", and `zanza` is
    # already this entry's alias (this crosses families, plucked idiophones)
    'sanza': 'mbira',
    # https://en.wikipedia.org/wiki/Mbira: as `sanza` above, from the same infobox list
    'sansa': 'mbira',
    # --- Batch 6's players' instruments (electronic), in the order of
    # plans/data/instrument-audit/batch-6.tsv
    # https://en.wikipedia.org/wiki/Vox_Continental: "The Vox Continental is a transistorised combo
    # organ that was manufactured between 1962 and 1971 by the British musical equipment
    # manufacturer Vox."; the model is the catalog combo organ (organs family), so this crosses
    # families, as aliases are catalog-wide
    'vox continental': 'combo organ',
    # https://en.wikipedia.org/wiki/Theremin: "The theremin (; originally known as the ætherphone,
    # etherphone, thereminophone or termenvox/thereminvox)"; another name for the theremin
    'thereminvox': 'theremin',
    # https://www.sweetwater.com/store/detail/EtherwaveStd: "Moog Etherwave Standard Theremin -
    # Ash"; Moog's model name for a theremin, so another name for the catalog theremin (a name
    # source only: Wikipedia has no Etherwave page and the National Music Centre record returned
    # 403)
    'etherwave': 'theremin',
    # https://en.wikipedia.org/wiki/MOS_Technology_6581 (the SID's "four basic waveform types
    # selectable: triangle, sawtooth, pulse (with variable duty cycle), and pseudorandom
    # noise"); the audit's generic name for the SID's sawtooth (its alias list: "sid chip sawtooth
    # -> chip sawtooth"), the name a person asking for a chip sawtooth would type
    'chip sawtooth': 'sid sawtooth',
    # https://en.wikipedia.org/wiki/General_Instrument_AY-3-8910 ("It was also manufactured under
    # license by Yamaha (with a selectable clock divider pin and a double-resolution and
    # double-rate volume envelope table) as the YM2149F; the Atari ST uses this version."): the
    # licensed chip, its tone channels the AY's; the differences are the clock pin and the
    # envelope table, not the square tone
    'ym2149': 'ay 3 8910',
    # --- Batch 7's bowed strings, in the order of plans/data/instrument-audit/batch-7.tsv
    # https://en.wikipedia.org/wiki/Hurdy-gurdy ("In Poland it is called 'cranked lyre' (lira
    # korbowa)."): the Polish name for the hurdy gurdy; an alias is a name, not a build, so it
    # does not share the approximating hurdy gurdy's sound as a sound-alike would
    'lira korbowa': 'hurdy gurdy',
    # https://musicbrainz.org/instrument/8f15287f-48c1-4a7c-a7f7-30653c490279 (the viol family
    # lists the consort as "Soprano viol (treble)" and the first grouping as "Treble/Diskant or
    # Dessus viol"); https://en.wikipedia.org/wiki/Viol ("treble (dessus in French)"): the
    # catalog treble viol under another name
    'soprano viol': 'treble viol',
    # https://www.thedailystar.net/supplements/28th-anniversary-supplements/deshi-first/news/folk-musical-instruments-the-land-1704676
    # ("the violin; popularly known as behala"): the violin's Bengali name, so an alias, not a
    # sound-alike
    'behala': 'violin',
    # https://en.wikipedia.org/wiki/Morin_khuur (the Matouqin title redirects there; the Huqin
    # page lists "Matouqin (馬頭琴) (Inner Mongolia)"): the Chinese name for the morin khuur
    'matouqin': 'morin khuur',
    # https://en.wikipedia.org/wiki/Kemenche (the Kemençe title redirects there and opens
    # "Kemenche (Turkish: kemençe; Greek: κεμεντζές)"): the Turkish spelling of the catalog
    # kemenche
    'kemence': 'kemenche',
    # --- Batch 8's voices, in the order of plans/data/instrument-audit/batch-8.tsv
    # https://en.wikipedia.org/wiki/Contralto ("A contralto ... (sometimes alto) is a classical
    # female singing voice whose vocal range is the lowest of such voice types."): the solo voice
    # the catalog's alto ah is titled for ("Alto (contralto)"), F3 to F5 as the page gives it
    'contralto': 'alto ah',
    # https://en.wikipedia.org/wiki/Boy_soprano ("A boy soprano ... or boy treble ... is a young
    # male singer with a voice in the soprano range, a range that is often still called the
    # treble voice range"): the catalog's treble ah, titled "Treble (boy soprano)"
    'boy soprano': 'treble ah',
    # --- Batch 9's flutes, in the order of plans/data/instrument-audit/batch-9.tsv
    # https://en.wikipedia.org/wiki/Tin_whistle ("The tin whistle, also known as the penny
    # whistle, is a simple six-holed woodwind instrument."): another name for the tin whistle
    'penny whistle': 'tin whistle',
    # https://en.wikipedia.org/wiki/Pan_flute ("In Bolivia, the panpipes of the altiplano are
    # known as jula-jula, and those of the Andean range as julu-julu."): the altiplano's Bolivian
    # name for the panpipes, which the page does not tie to the siku, so the catalog's pan flute
    'jula jula': 'pan flute',
    # The same page and sentence: the Andean range's Bolivian name for the panpipes
    'julu julu': 'pan flute',
    # https://en.wikipedia.org/wiki/Pan_flute ("A pan flute (also known as panpipes or syrinx) is
    # a musical instrument based on the principle of the closed tube"; "Ancient Greeks called
    # this instrument Syrinx"): the Greek name for the catalog's pan flute
    'syrinx': 'pan flute',
    # https://www.windkanal.de/2-windkanal/88-give-your-spirit-a-voice ("In the original language
    # of the Lakota, the flute is called Siyotanka and is also known as "love flute" and
    # "courting flute". Today, the name Native American Flute or Native American Style Flute has
    # generally prevailed."); https://www.horniman.ac.uk/object/M47-1991 ("Siyotanka, courting
    # flute."): the Lakota name for the catalog's native american flute
    'siyotanka': 'native american flute',
    # --- Batch 10's brass, in the order of plans/data/instrument-audit/batch-10.tsv
    # https://en.wikipedia.org/wiki/Piccolo_trumpet ("Most piccolo trumpets are built to play in
    # either B-flat or A, using a separate leadpipe for each key."): one instrument set to
    # either key by its leadpipe, so the key-first name is the catalog's piccolo trumpet
    'b flat piccolo trumpet': 'piccolo trumpet',
    # https://en.wikipedia.org/wiki/Tuba ("The euphonium, pitched in 9' B-flat a fourth above
    # the bass tuba in F, is sometimes referred to as a tenor tuba, particularly by British
    # composers."): another name for the euphonium
    'tenor tuba': 'euphonium',
    # https://en.wikipedia.org/wiki/Cornett ("The ordinary curved treble cornett is made by
    # splitting a length of wood, usually walnut, boxwood or other tonewoods like plum, cherry
    # or pear."): the page makes the ordinary cornett the treble
    'treble cornett': 'cornett',
    # https://collections.ed.ac.uk/stcecilias/record/99179 ("In French the instrument was called
    # cornet a pistons (cornet with pistons - meaning valves) to distinguish it from its
    # predecessor the cornet de poste (post horn)."): the French name for the catalog's cornet
    'cornet a pistons': 'cornet',
    # https://en.wikipedia.org/wiki/Tenor_horn ("The tenor horn (British English; alto horn in
    # American English, sometimes E-flat horn) is a brass instrument in the saxhorn family
    # pitched in E-flat with three piston valves."): the British name for the alto horn
    'tenor horn': 'alto horn',
    # https://en.wikipedia.org/wiki/Cornett ("The cornett (Italian: cornetto, German: Zink) is a
    # lip-reed wind instrument"): the German name for the cornett
    'zink': 'cornett',
    # --- Batch 10's second half: the natural horns and trumpets, shells and animal horns
    # https://en.wikipedia.org/wiki/Conch_(instrument) ("In Tibet it is known as dung-dkar or
    # dungkar."): the Tibetan name for the catalog's conch
    'dung dkar': 'conch',
    # https://en.wikipedia.org/wiki/Hakgediya ("The hakgediya is a type of conch shell (the
    # shell of a large marine gastropod mollusk) which is used as a kind of trumpet"): the conch
    # shell blown as a trumpet, with no trait of its own (its notes vary only in volume)
    'hakgediya': 'conch',
    # https://en.wikipedia.org/wiki/Titanostrombus_galeatus ("The shells of this species were
    # used as a wind instruments by the Chavín," "They are still used for this purpose in the
    # Andes, where they are known as pututu."): the Andean name for the catalog's conch
    'pututu': 'conch',
    # https://en.wikipedia.org/wiki/Conch_(instrument) ("The sacred chank, Turbinella pyrum, is
    # known in India as the shankha"): the Indian name for the catalog's conch
    'shankha': 'conch',
    # https://en.wikipedia.org/wiki/French_horn (infobox, other names: "German: Horn, Waldhorn,
    # Ventilhorn"): a German name for the catalog's french horn
    'waldhorn': 'french horn',
    # https://en.wikipedia.org/wiki/Natural_horn ("In 1753 Anton Hampel alongside Johann
    # Werner,[who?] developed the Inventionshorn, built with a fixed mouthpiece so that the horn
    # remained at the same distance no matter how many crooks were added."): the natural horn
    # with crooks, no valves, by a design name
    'inventionshorn': 'natural horn',
    # https://en.wikipedia.org/wiki/Didgeridoo ("Yiḏaki (transcribed yidaki in English,
    # sometimes spelt yirdaki) is one of the most commonly used names"): a name for the
    # catalog's didgeridoo
    'yidaki': 'didgeridoo',
    # https://en.wikipedia.org/wiki/Didgeridoo ("In the Bininj Kunwok language of West Arnhem
    # Land it is known as mako (pronounced, and sometimes spelt, as mago)."): the West Arnhem
    # Land name for the catalog's didgeridoo
    'mako': 'didgeridoo',
    # https://en.wikipedia.org/wiki/Alphorn ("The alphorn (German: Alphorn, Alpenhorn; French:
    # cor des Alpes; Italian: corno alpino) is a traditional lip-reed wind instrument."):
    # another name for the catalog's alphorn
    'alpenhorn': 'alphorn',
    # https://en.wikipedia.org/wiki/Conch_(instrument) ("The Arawak word 'fotuto' was used to
    # describe this instrument, and is still used to this day to refer to conch instruments,"):
    # another name for the catalog's conch
    'fotuto': 'conch',
    # --- Batch 11's double reeds, in the order of plans/data/instrument-audit/batch-11.tsv
    # https://en.wikipedia.org/wiki/Cor_anglais ("The cor anglais ... or English horn (mainly
    # North America), is a double-reed woodwind instrument in the oboe family."): another name
    # for the catalog's english horn
    'cor anglais': 'english horn',
    # https://en.wikipedia.org/wiki/Bass_oboe ("The bass oboe or baritone oboe is a double reed
    # instrument in the woodwind family."): another name for the catalog's bass oboe
    'baritone oboe': 'bass oboe',
    # https://en.wikipedia.org/wiki/Bassoon ("The term for bassoon used in classical music scores
    # and parts is often its Italian name fagotto (plural fagotti), which referred initially to
    # the dulcian. This word, adopted in many other European languages as fagot, fagote, or in
    # German, Fagott, comes from an Old French word meaning a bundle of sticks."): the German
    # name of the modern bassoon
    'fagott': 'bassoon',
    # https://en.wikipedia.org/wiki/Rackett ("The rackett, raggett, cervelas, or sausage bassoon
    # is a Renaissance-era double reed wind instrument"): another name for the catalog's rackett
    'cervelas': 'rackett',
    # https://en.wikipedia.org/wiki/Gyaling ("As its name indicates, it is the Chinese double reed
    # Suona horn (much like the Iranian sorna) used mainly in Tibetan monasteries during puja
    # (chanting and prayer)"): the suona under its Tibetan name
    'gyaling': 'suona',
    # https://en.wikipedia.org/wiki/Zurna ("Also called sunay, birbynė, lettish horn, zurla or
    # zurle, surla, sornai, zournas, zurma, or zurnes."): another name for the catalog's zurna
    'zurla': 'zurna',
    # https://en.wikipedia.org/wiki/Bombard_(musical_instrument) ("The bombard (Breton: bombard,
    # talabard, French: bombarde) is a contemporary family of oboes widely used to play
    # traditional Breton music, where it is considered emblematic."): the Breton instrument that
    # is the catalog's bombarde
    'bombard': 'bombarde',
    # https://en.wikipedia.org/wiki/Surna (a disambiguation page: "Zurna or Surna, a
    # multinational outdoor wind instrument" and "Sorna or Surna, an ancient Iranian woodwind
    # instrument"): the name also covers the sorna, a distinct instrument that is not in the
    # catalog, so it stands for the zurna, the disambiguation's first sense
    'surna': 'zurna',
    # https://en.wikipedia.org/wiki/Zurna (its Persian name: "Persian: karna/Kornay/surnay"):
    # another name for the catalog's zurna. The Sorna page gives "surnāy" for the sorna too, so
    # like surna it stands for the zurna, the sense the Zurna page gives directly
    'surnay': 'zurna',
    # https://en.wikipedia.org/wiki/Zurna ("Also called sunay, birbynė, lettish horn, zurla or
    # zurle, surla, sornai, zournas, zurma, or zurnes." and "Greek: ζουρνάς"): the Greek name of
    # the catalog's zurna
    'zournas': 'zurna',
    # https://en.wikipedia.org/wiki/Suona ("The suona, also called dida, laba or haidi, is a
    # traditional double-reeded Chinese musical instrument."): another name for the catalog's
    # suona
    'haidi': 'suona',
}
