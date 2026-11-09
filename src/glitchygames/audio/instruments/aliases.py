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
    # Batch 3's drums (membranophones), in the order of plans/data/instrument-audit/batch-3.tsv,
    # whose notes hold the full quotes and why each sounds like its target. A sound-alike is a
    # distinct instrument that no source sets apart in sound from the entry it resolves to (the
    # owner's ruling, 2026-11-08: a person may search for it by its own name); another name is the
    # same instrument
    # https://en.wikipedia.org/wiki/Alfaia: "Alfaias are usually between 40 centimetres (16 in) and
    # 55 centimetres (22 in) in diameter"; a sound-alike of the catalog taiko, not the same
    # instrument
    'alfaia': 'taiko',
    # https://en.wikipedia.org/wiki/Ashiko: "The ashiko is a drum, shaped like a tapered cylinder or
    # truncated cone with the head on the wide end, and the narrow end open"; a sound-alike of the
    # catalog djembe tone, not the same instrument
    'ashiko': 'djembe tone',
    # https://en.wikipedia.org/wiki/Atabaque: "is a tall, wooden, Afro-Brazilian hand drum, similar
    # to conga"; a sound-alike of the catalog conga, not the same instrument
    'atabaque': 'conga',
    # https://en.wikipedia.org/wiki/Atumpan_(drum): "Played in pairs, these drums provide the bass
    # part in Adowa dance ensembles"; a sound-alike of the catalog tumba, not the same instrument
    'atumpan': 'tumba',
    # https://en.wikipedia.org/wiki/Bamboula: "percussion instrument or type of drum made from a rum
    # barrel with skin stretched over one end"; a sound-alike of the catalog conga, not the same
    # instrument
    'bamboula': 'conga',
    # https://en.wikipedia.org/wiki/Bangu_(drum): "is a Chinese frame drum that, when struck by one
    # or two small bamboo sticks, creates a sharp dry sound essential to the aesthetics of Chinese
    # opera"; a sound-alike of the catalog darbuka tek, not the same instrument
    'bangu': 'darbuka tek',
    # https://en.wikipedia.org/wiki/Bat%C3%A1_drum: "The bàtá drum is a double-headed hourglass drum
    # with one end larger than the other"; a sound-alike of the catalog conga, not the same
    # instrument
    'bata drum': 'conga',
    # https://en.wikipedia.org/wiki/Bedug: "A bedug is a large double-headed drum with water buffalo
    # or cow leather on both ends"; a sound-alike of the catalog orchestral bass drum, not the same
    # instrument
    'bedug': 'orchestral bass drum',
    # https://en.wikipedia.org/wiki/Bougarabou: "The drums are single headed (cow skin), with an
    # elongated goblet or roughly conical shape"; a sound-alike of the catalog djembe bass, not the
    # same instrument
    'bougarabou': 'djembe bass',
    # https://en.wikipedia.org/wiki/Buk_(drum): "it is most often used to refer to a shallow
    # barrel-shaped drum, with a round wooden body that is covered on both ends with animal skin"; a
    # sound-alike of the catalog taiko, not the same instrument
    'buk': 'taiko',
    # https://kalango.com/en/produktberater/caixa https://en.wikipedia.org/wiki/Snare_drum: "12'' x
    # 17cm (Malacacheta / Caixa de Guerra)"; a sound-alike of the catalog snare drum, not the same
    # instrument
    'caixa malacacheta': 'snare drum',
    # https://en.wikipedia.org/wiki/Candombe_drums: "They are single skin headed and there are three
    # sizes: piano (bass range), repique (tenor range), and the chico (alto range)"; a sound-alike
    # of the catalog conga, not the same instrument
    'candombe drums': 'conga',
    # https://en.wikipedia.org/wiki/Carimb%C3%B3: "The drummer, or batedor, sits on the body of the
    # drum, which is often fitted with a wooden support, and strikes it with both hands"; a
    # sound-alike of the catalog tumba, not the same instrument
    'carimbo': 'tumba',
    # https://en.wikipedia.org/wiki/Tom_drum: "Single-headed tom-toms, also known as concert toms,
    # have also been used in drum kits"; a sound-alike of the catalog mid tom, not the same
    # instrument
    'concert tom': 'mid tom',
    # https://en.wikipedia.org/wiki/Cultrun: "It is approximately 35 to 40 cm in diameter and has a
    # height of 12 to 15 cm"; a sound-alike of the catalog bodhran, not the same instrument
    'cultrun': 'bodhran',
    # https://en.wikipedia.org/wiki/Dabakan: "The dabakan is a single-headed Philippine drum,
    # primarily used as a supportive instrument in the kulintang ensemble"; a sound-alike of the
    # catalog conga slap, not the same instrument
    'dabakan': 'conga slap',
    # https://en.wikipedia.org/wiki/Damphu_drum: "is like a bodhrán, a single-sided circular frame
    # drum decorated with symbols or left plain"; a sound-alike of the catalog bodhran, not the same
    # instrument
    'damphu': 'bodhran',
    # https://en.wikipedia.org/wiki/Davul: "is a large double-headed drum that is played with
    # mallets"; a sound-alike of the catalog dhol, not the same instrument
    'davul': 'dhol',
    # https://en.wikipedia.org/wiki/Daf: "The daf (Persian: دف), also known as dap (دپ), dâyere or
    # riq"; another name for the daf
    'dayereh': 'daf',
    # https://en.wikipedia.org/wiki/Dhak_(instrument): "The dhak is a huge membranophone instrument
    # from Bengal and Assam"; a sound-alike of the catalog dhol, not the same instrument
    'dhak': 'dhol',
    # https://en.wikipedia.org/wiki/Dhimay: "it belongs to the category of double-headed cylindrical
    # membranophone"; a sound-alike of the catalog surdo, not the same instrument
    'dhimay': 'surdo',
    # https://en.wikipedia.org/wiki/Dohol: "is a large cylindrical drum with two skinheads"; a
    # sound-alike of the catalog dhol, not the same instrument
    'dohol': 'dhol',
    # https://en.wikipedia.org/wiki/Dollu: "The dollu is a double-headed drum native to Karnataka,
    # India"; a sound-alike of the catalog dhol, not the same instrument
    'dollu': 'dhol',
    # https://en.wikipedia.org/wiki/Dunun: "A dunun is a rope-tuned cylindrical drum with a rawhide
    # skin at both ends, most commonly cow or goat. The drum is played with a stick"; a sound-alike
    # of the catalog floor tom, not the same instrument
    'dunun': 'floor tom',
    # https://en.wikipedia.org/wiki/Fontomfrom: "Fontomfrom is a Bono type of hourglass-shaped drum
    # mostly used in a royal music ensemble"; a sound-alike of the catalog orchestral bass drum, not
    # the same instrument
    'fontomfrom': 'orchestral bass drum',
    # https://en.wikipedia.org/wiki/Kendang: "Makassar: gandrang or ganrang) is a two-headed drum
    # used by people from the Indonesian Archipelago"; another name for the kendang
    'ganrang': 'kendang',
    # https://en.wikipedia.org/wiki/Gbedu: "Gbedu literally means 'big drum' and is a percussion
    # instrument traditionally used in ceremonial Yoruba music in Nigeria and Benin"; a sound-alike
    # of the catalog orchestral bass drum, not the same instrument
    'gbedu': 'orchestral bass drum',
    # https://africandrumming.com.au/cart/gome: "The Gome drum is a fundamental solo and ensemble
    # drum among the Ga and Ashanti of Ghana"; a sound-alike of the catalog cajon bass, not the same
    # instrument
    'gome': 'cajon bass',
    # https://en.wikipedia.org/wiki/Gudugudu: "It is designed to produce a sharp and loud beat that
    # all the other drummers can hear and keep in time with"; a sound-alike of the catalog high
    # timbale, not the same instrument
    'gudugudu': 'high timbale',
    # https://artdrum.com/HIRA_DAIKO.HTM: "Hira means stout or flat which describes the Hira Daiko
    # shape"; a sound-alike of the catalog taiko, not the same instrument
    'hira daiko': 'taiko',
    # https://en.wikipedia.org/wiki/Huehuetl: "It is an upright tubular drum made from a wooden body
    # opened at the bottom that stands on three legs cut from its base, with skin stretched over the
    # top"; a sound-alike of the catalog tumba, not the same instrument
    'huehuetl': 'tumba',
    # https://en.wikipedia.org/wiki/Igba: "is a tom-tom that has a beating surface of the same
    # approximate diameter as a bongo"; a sound-alike of the catalog low bongo, not the same
    # instrument
    'igba': 'low bongo',
    # https://collectionapi.metmuseum.org/public/collection/v1/objects/503213
    # https://en.wikipedia.org/wiki/Buk_(drum): "Membranophone-double-headed / cylindrical drum"; a
    # sound-alike of the catalog taiko, not the same instrument
    'jwago': 'taiko',
    # https://en.wikipedia.org/wiki/Kakko_(instrument): "The kakko (羯鼓/鞨鼓) is a Japanese
    # double-headed drum"; a sound-alike of the catalog high tom, not the same instrument
    'kakko': 'high tom',
    # https://en.wikipedia.org/wiki/Kendang https://nat.museum-digital.de/tag/37818: "Kendhang
    # batangan or kendhang ciblon is a medium-sized drum, used for the most complex or lively
    # rhythms"; a sound-alike of the catalog kendang, not the same instrument
    'kendang ciblon': 'kendang',
    # https://nat.museum-digital.de/tag/37818: "Most are played with the hands but some larger
    # varieties are played with a ball headed stick on the larger head"; a sound-alike of the
    # catalog kendang, not the same instrument
    'kendang wadon': 'kendang',
    # https://en.wikipedia.org/wiki/Dunun: "The kenkeni is the smallest dunun and has the highest
    # pitch. Typical size is 45-50 cm (18-20 in) in length and 25-35 cm (9.8-13.8 in) in diameter";
    # a sound-alike of the catalog mid tom, not the same instrument
    'kenkeni': 'mid tom',
    # https://en.wikipedia.org/wiki/Klong_khaek: "is a type of double-headed barrel drum used in
    # Thai music"; a sound-alike of the catalog kendang, not the same instrument
    'klong khaek': 'kendang',
    # https://en.wikipedia.org/wiki/Kpanlogo_(drum)
    # https://www.djembedirect.com/hand-carved-african-kpanlogo-peg-drum-from-ghana-11x25-cow-skin/:
    # "is a type of barrel drum that is associated with Kpanlogo music, and is usually played with
    # two hands"; a sound-alike of the catalog conga, not the same instrument
    'kpanlogo': 'conga',
    # https://en.wikipedia.org/wiki/Kundu_(drum): "Kundu is a pidgin name in Papua New Guinea for an
    # hourglass drum"; a sound-alike of the catalog conga, not the same instrument
    'kundu': 'conga',
    # https://ktb.gov.tr/EN-98653/janissary-mehter-music.html
    # https://blog.soton.ac.uk/music/2014/10/22/instruments-istanbul/: "The Ruler's Drum (Kös) -
    # This large drum stood in front of the ruler's tent"; a sound-alike of the catalog taiko, not
    # the same instrument
    'kus': 'taiko',
    # https://en.wikipedia.org/wiki/Madal: "The madal has a cylindrical body with a slight bulge at
    # its center and heads at both ends, one head larger than the other. It is usually played
    # horizontally in a seated position, with both heads played simultaneously"; a sound-alike of
    # the catalog kendang, not the same instrument
    'madal': 'kendang',
    # https://en.wikipedia.org/wiki/Madhalam: "It has two sides for playing, made out of leather,
    # and has different kinds of sounds on each side"; a sound-alike of the catalog mridangam, not
    # the same instrument
    'maddalam': 'mridangam',
    # https://en.wikipedia.org/wiki/Makuta_(drum): "Makuta drums are tall cylindrical or
    # barrel-shaped Afro-Cuban drums, often cited as an important influence on the development of
    # the tumbadora or conga drum"; a sound-alike of the catalog conga, not the same instrument
    'makuta': 'conga',
    # https://en.wikipedia.org/wiki/Snare_drum: "Marching snares are typically 12 in (30 cm) deep
    # and 14 in (36 cm) wide. The larger design allows for a deeper-sounding tone, one that is
    # effective for marching bands"; a sound-alike of the catalog field drum, not the same
    # instrument
    'marching snare': 'field drum',
    # https://en.wikipedia.org/wiki/Taiko: "The typical byō-uchi-daiko is the nagadō-daiko, an
    # elongated drum that is roughly shaped like a wine barrel"; a sound-alike of the catalog taiko,
    # not the same instrument
    'nagado daiko': 'taiko',
    # https://en.wikipedia.org/wiki/Naqareh https://en.wikipedia.org/wiki/Nagara_(drum): "The
    # naqareh, naqqāra, nagara or nagada is a Middle Eastern drum with a rounded back and a hide
    # head, usually played in pairs"; another name for the naqareh
    'nagara': 'naqareh',
    # https://en.wikipedia.org/wiki/Ngoma_drums: "Ngoma is derived from the Kikongo word for
    # 'drum'"; a sound-alike of the catalog conga, not the same instrument
    'ngoma': 'conga',
    # https://en.wikipedia.org/wiki/Octoban: "are deep, small diameter, single-head tom-toms"; a
    # sound-alike of the catalog high tom, not the same instrument
    'octoban': 'high tom',
    # https://en.wikipedia.org/wiki/Taiko: "Okedō-daiko or simply okedō, are a type of shime-daiko
    # that are stave-constructed using narrower strips of wood, have a tube-shaped frame"; a
    # sound-alike of the catalog high tom, not the same instrument
    'okedo daiko': 'high tom',
    # https://en.wikipedia.org/wiki/Pahu: "Carved from a single log and covered on the playing end
    # with a stretched sharkskin, the pahu is played with the palms and fingers of the hand"; a
    # sound-alike of the catalog tumba, not the same instrument
    'pahu': 'tumba',
    # https://en.wikipedia.org/wiki/Pakhavaj https://en.wikipedia.org/wiki/Mridangam: "The pakhavaj
    # or pakhawaj is a barrel-shaped, two-headed drum"; a sound-alike of the catalog mridangam, not
    # the same instrument
    'pakhavaj': 'mridangam',
    # https://en.wikipedia.org/wiki/Timbales: "Timbaleta, pailas, pailas criollas"; another name for
    # the high timbale
    'paila criolla': 'high timbale',
    # https://en.wikipedia.org/wiki/Pandero_jarocho: "The pandero jarocho is an octagonal tambourine
    # or pandero traditionally played by men in the Veracruz region of Mexico"; a sound-alike of the
    # catalog tambourine, not the same instrument
    'pandero jarocho': 'tambourine',
    # https://en.wikipedia.org/wiki/Parai: "It consists of a shallow circular ring made of wood of
    # diameter 16-22 in (410-560 mm)"; a sound-alike of the catalog bodhran, not the same instrument
    'parai': 'bodhran',
    # https://en.wikipedia.org/wiki/Snare_drum: "There are many kinds of piccolo snare which can be
    # piccolos, including the popcorn, soprano and standard snares. Popcorn snares typically have a
    # diameter of 10 in (25 cm)"; a sound-alike of the catalog piccolo snare, not the same
    # instrument
    'popcorn snare': 'piccolo snare',
    # https://collectionapi.metmuseum.org/public/collection/v1/objects/501368
    # https://en.wikipedia.org/wiki/Pahu: "Membranophone-single-headed / kettle drum"; a sound-alike
    # of the catalog high bongo, not the same instrument
    'puniu': 'high bongo',
    # https://en.wikipedia.org/wiki/Rebana: "The rebana or terbangan is a tambourine that is used in
    # Islamic devotional music in Southeast Asia"; a sound-alike of the catalog tambourine, not the
    # same instrument
    'rebana': 'tambourine',
    # https://en.wikipedia.org/wiki/Repinique: "It is tuned very high to produce a tone that cuts
    # through the sound of the rest of the bateria and is used as both a lead and solo instrument";
    # a sound-alike of the catalog high timbale, not the same instrument
    'repinique': 'high timbale',
    # https://en.wikipedia.org/wiki/Daf: "dâyere or riq, is an Iranian frame drum musical
    # instrument"; another name for the daf
    'riq': 'daf',
    # https://en.wikipedia.org/wiki/Sabar: "The drum is generally played with one hand and one stick
    # or 'galan'"; a sound-alike of the catalog djembe tone, not the same instrument
    'sabar': 'djembe tone',
    # https://en.wikipedia.org/wiki/Sakara_drum: "The Sakara drum is a shallow membranophone with a
    # circular body made of baked clay"; a sound-alike of the catalog bodhran, not the same
    # instrument
    'sakara drum': 'bodhran',
    # https://en.wikipedia.org/wiki/Samphor: "is a small, 2-headed barrel drum indigenous to
    # Cambodia, approximately .35 meter wide by .5 meter long"; a sound-alike of the catalog
    # kendang, not the same instrument
    'samphor': 'kendang',
    # https://en.wikipedia.org/wiki/Dunun: "The sangban is of medium size, with higher pitch than
    # the dundunba. Typical size is 50-60 cm (20-24 in) in length and 30-40 cm (12-16 in) in
    # diameter"; a sound-alike of the catalog low tom, not the same instrument
    'sangban': 'low tom',
    # https://en.wikipedia.org/wiki/Taiko: "Shime-daiko are a set of smaller, roughly snare
    # drum-sized instrument that are tunable"; a sound-alike of the catalog high tom, not the same
    # instrument
    'shime daiko': 'high tom',
    # https://en.wikipedia.org/wiki/Tabor_(instrument): "is a double-skinned portable drum, often
    # with a gut snare on the batter head, typically played with a single stick in the right hand";
    # a sound-alike of the catalog field drum, not the same instrument
    'tabor': 'field drum',
    # https://en.wikipedia.org/wiki/Tambora_(Dominican_drum): "The Dominican tambora (from the
    # Spanish word tambor, meaning 'drum') is a two headed drum played in merengue music"; a
    # sound-alike of the catalog conga, not the same instrument
    'tambora': 'conga',
    # https://en.wikipedia.org/wiki/Tamborim: "is a small round Brazilian frame drum"; a sound-alike
    # of the catalog darbuka tek, not the same instrument
    'tamborim': 'darbuka tek',
    # https://en.wikipedia.org/wiki/Tan-tan: "A tan-tan is a cylindrical hand drum from Brazil that
    # is used in small samba and pagode ensembles. It imitates the big Surdo"; a sound-alike of the
    # catalog surdo, not the same instrument
    'tan tan': 'surdo',
    # https://en.wikipedia.org/wiki/Tanggu_(drum): "It is medium in size and barrel-shaped, with two
    # heads made of animal skin, and is played with two sticks"; a sound-alike of the catalog mid
    # tom, not the same instrument
    'tanggu': 'mid tom',
    # https://en.wikipedia.org/wiki/Taphon: "It is barrel-shaped with two heads"; a sound-alike of
    # the catalog kendang, not the same instrument
    'taphon': 'kendang',
    # https://en.wikipedia.org/wiki/Tar_(drum): "is an ancient, single-headed frame drum. It is
    # commonly played in the Middle East and North Africa. The tar's drumhead is struck with one
    # hand"; a sound-alike of the catalog frame drum, not the same instrument
    'tar drum': 'frame drum',
    # https://en.wikipedia.org/wiki/Snare_drum: "The tarol snare has similar dimensions to the kit
    # snare. The major distinction is that the snares in this type are on the top head rather than
    # the bottom one"; a sound-alike of the catalog snare drum, not the same instrument
    'tarol': 'snare drum',
    # https://en.wikipedia.org/wiki/Tassa: "The tassa drum proper is a conical or bowl-shaped
    # nagaara- (aka nagada or nagaada) type drum"; a sound-alike of the catalog naqareh, not the
    # same instrument
    'tasha': 'naqareh',
    # https://en.wikipedia.org/wiki/Tbilat: "The tbilat is a percussion instrument from Morocco
    # which resembles bongos and tabla. It consists of a pair of decorated pottery drums of
    # different sizes"; a sound-alike of the catalog high bongo, not the same instrument
    'tbilat': 'high bongo',
    # https://theatrecrafts.com/pages/home/topics/sound/sound-effects-for-the-stage/
    # https://en.wikipedia.org/wiki/Thunder_sheet: "A large wooden frame, covered with a tight
    # drumskin, with a stick with one end covered with chamois"; a sound-alike of the catalog
    # orchestral bass drum, not the same instrument
    'thunder drum': 'orchestral bass drum',
    # https://patents.google.com/patent/US20170178612A1/en
    # https://remo.com/product/spring-drum-thunder-tube: "The spring drum consists of a resonant
    # tube, open at one end and closed by a membrane at the other, with a spring attached to the
    # membrane near its center"; a sound-alike of the catalog thunder sheet, not the same instrument
    'thunder tube': 'thunder sheet',
    # https://en.wikipedia.org/wiki/Tifa_(drum): "The tifa, tiwa or tiva is a single-headed goblet
    # drum used throughout the Maluku Islands of Eastern Indonesia"; a sound-alike of the catalog
    # djembe tone, not the same instrument
    'tifa': 'djembe tone',
    # https://en.wikipedia.org/wiki/Tombak: "is an Iranian goblet drum"; a sound-alike of the
    # catalog darbuka doum, not the same instrument
    'tombak': 'darbuka doum',
    # https://en.wikipedia.org/wiki/Tr%E1%BB%91ng_ch%E1%BA%A7u: "It is a small double-headed drum,
    # beaten with a long wooden stick on the top side, causing a loud snapping sound"; a sound-alike
    # of the catalog darbuka tek, not the same instrument
    'trong chau': 'darbuka tek',
    # https://en.wikipedia.org/wiki/Tr%E1%BB%91ng_c%C6%A1m: "is a kind of traditional barrel-shaped
    # Vietnamese drum"; a sound-alike of the catalog kendang, not the same instrument
    'trong com': 'kendang',
    # https://en.wikipedia.org/wiki/Taiko: "The tsuri-daiko (釣太鼓, 'suspended drum') is a smaller
    # drum that produces a lower sound, its head measuring about 55 cm (22 in) in diameter"; a
    # sound-alike of the catalog orchestral bass drum, not the same instrument
    'tsuri daiko': 'orchestral bass drum',
    # https://en.wikipedia.org/wiki/Taiko: "Uchiwa-daiko (団扇太鼓; literally, fan drum) is a type
    # of racket-shaped Japanese drum. It is the only Japanese traditional drum without a sound box
    # and only one skin. It is played with a drumstick while hanging it with the other hand"; a
    # sound-alike of the catalog bodhran, not the same instrument
    'uchiwa daiko': 'bodhran',
    # https://en.wikipedia.org/wiki/Urumi_(drum): "is a double-headed hourglass drum from the state
    # of Tamil Nadu, South India"; a sound-alike of the catalog high tom, not the same instrument
    'urumi': 'high tom',
    # https://en.wikipedia.org/wiki/Zabumba: "The top head is usually muted with tape or cloth
    # strip(s) and struck with a cloth-covered mallet (held in the right hand) to produce a low
    # fundamental note with minimal overtones"; a sound-alike of the catalog dhol, not the same
    # instrument
    'zabumba': 'dhol',
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
    # https://en.wikipedia.org/wiki/Khanjani: "Khanjani is a percussion musical instrument, a
    # variety of Daf, found in West Bengal & Odisha"; a sound-alike of the catalog daf, not the same
    # instrument
    'khanjani': 'daf',
    # https://en.wikipedia.org/wiki/Kanjira: "The kanjira, khanjira, khanjiri or ganjira, a South
    # Indian frame drum, is an instrument of the tambourine family"; another name for the kanjira
    'ganjira': 'kanjira',
    # https://en.wikipedia.org/wiki/Davul https://en.wikipedia.org/wiki/Tabl: "The Tabl, tapan,
    # atabal or davul is a large double-headed drum that is played with mallets"; a sound-alike of
    # the catalog dhol, not the same instrument
    'tabl': 'dhol',
    # https://en.wikipedia.org/wiki/Daf: "dafli, dap, def, tef, defi, qaval, duf, duff, dof, doira";
    # another name for the daf
    'doira': 'daf',
    # https://en.wikipedia.org/wiki/Bass_drum: "the orchestral, or concert bass drum (in Italian:
    # gran cassa, gran tamburo). It is the largest drum of the orchestra"; another name for the
    # orchestral bass drum
    'gran cassa': 'orchestral bass drum',
    # https://en.wikipedia.org/wiki/Timbau: "The timbau or Brazilian timbal is a membranophone
    # instrument derived from the caxambu drum, usually played with both hands"; a sound-alike of
    # the catalog conga, not the same instrument
    'timbal': 'conga',
    # https://www.outlookindia.com/culture-society/tumbhaknari-the-soulful-rhythm-of-kashmirs-heartbeat
    # https://www.greaterkashmir.com/news/opinion/clay-musical-instruments-of-kashmir/: "a goblet
    # drum traditional to Jammu and Kashmir"; a sound-alike of the catalog darbuka doum, not the
    # same instrument
    'tumbaknari': 'darbuka doum',
}
