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
    # its own entry (``sounds_like``, in drums.py), not an alias
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
}
