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
}
