"""Drums and percussion's sound-alikes: listed instruments that share another entry's build.

A sound-alike is a distinct instrument, verified by its source, that no fetched source sets apart
in sound from an existing entry. The owner ruled (2026-11-08) that each is a catalog entry of its
own rather than an alias: "could we also consider making them full on instruments that inherit
from the parent and change their details? ... I want them to all show up." Each is listed under
its own name, so a person finds it by the name they know, and each builds its parent's
instrument through ``sounds_like`` (assembled in ``registry.sound_alikes_from``). A true alias,
another name for the same instrument, stays in ``aliases.py``. The family's builds are in
``drums.py``.
"""

from __future__ import annotations

from typing import Final

from glitchygames.audio.instruments.catalog import CatalogEntry, Family

DRUM_SOUND_ALIKES: Final[tuple[CatalogEntry, ...]] = (
    # --- Batch 3's sound-alikes (membranophones), in the order of
    # plans/data/instrument-audit/batch-3.tsv: each a distinct instrument, verified by its source,
    # that no fetched source sets apart in sound from the entry it names (the owner, 2026-11-08:
    # each is listed under its own name, so a person finds it by the name they know). Each builds
    # that entry's instrument (``sounds_like``); the sheet's notes give each row's full quotes and
    # why it sounds like its parent. A later source giving a trait that sets one apart makes it a
    # changed sound-alike (``sound_changes``) or its own build.
    # Sound-alike of the taiko (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Alfaia ("Alfaias are usually between 40 centimetres (16 in) and
    # 55 centimetres (22 in) in diameter")
    CatalogEntry('alfaia', 'Alfaia', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='taiko'),
    # Sound-alike of the djembe tone (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Ashiko ("The ashiko is a drum, shaped like a tapered cylinder or
    # truncated cone with the head on the wide end, and the narrow end open")
    CatalogEntry(
        'ashiko', 'Ashiko', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='djembe tone'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Atabaque ("is a tall, wooden, Afro-Brazilian hand drum, similar
    # to conga")
    CatalogEntry(
        'atabaque', 'Atabaque', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'
    ),
    # Sound-alike of the tumba (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Atumpan_(drum) ("Played in pairs, these drums provide the bass
    # part in Adowa dance ensembles")
    CatalogEntry(
        'atumpan', 'Atumpan', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='tumba'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Bamboula ("percussion instrument or type of drum made from a rum
    # barrel with skin stretched over one end")
    CatalogEntry(
        'bamboula', 'Bamboula', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'
    ),
    # Sound-alike of the darbuka tek (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Bangu_(drum) ("is a Chinese frame drum that, when struck by one
    # or two small bamboo sticks, creates a sharp dry sound essential to the aesthetics of Chinese
    # opera")
    CatalogEntry(
        'bangu', 'Bangu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='darbuka tek'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Bat%C3%A1_drum ("The bàtá drum is a double-headed hourglass drum
    # with one end larger than the other")
    CatalogEntry(
        'bata drum', 'Batá drum', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'
    ),
    # Sound-alike of the orchestral bass drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Bedug ("A bedug is a large double-headed drum with water buffalo
    # or cow leather on both ends")
    CatalogEntry(
        'bedug',
        'Bedug',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='orchestral bass drum',
    ),
    # Sound-alike of the djembe bass (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Bougarabou ("The drums are single headed (cow skin), with an
    # elongated goblet or roughly conical shape")
    CatalogEntry(
        'bougarabou',
        'Bougarabou',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='djembe bass',
    ),
    # Sound-alike of the taiko (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Buk_(drum) ("it is most often used to refer to a shallow
    # barrel-shaped drum, with a round wooden body that is covered on both ends with animal skin")
    CatalogEntry('buk', 'Buk', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='taiko'),
    # Sound-alike of the snare drum (no fetched source sets it apart in sound):
    # https://kalango.com/en/produktberater/caixa https://en.wikipedia.org/wiki/Snare_drum ("12'' x
    # 17cm (Malacacheta / Caixa de Guerra)")
    CatalogEntry(
        'caixa malacacheta',
        'Caixa malacacheta',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='snare drum',
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Candombe_drums ("They are single skin headed and there are three
    # sizes: piano (bass range), repique (tenor range), and the chico (alto range)")
    CatalogEntry(
        'candombe drums',
        'Candombe drums (tamboriles)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='conga',
    ),
    # Sound-alike of the tumba (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Carimb%C3%B3 ("The drummer, or batedor, sits on the body of the
    # drum, which is often fitted with a wooden support, and strikes it with both hands")
    CatalogEntry(
        'carimbo', 'Carimbó', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='tumba'
    ),
    # Sound-alike of the mid tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tom_drum ("Single-headed tom-toms, also known as concert toms,
    # have also been used in drum kits")
    CatalogEntry(
        'concert tom', 'Concert tom', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='mid tom'
    ),
    # Sound-alike of the bodhran (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Cultrun ("It is approximately 35 to 40 cm in diameter and has a
    # height of 12 to 15 cm")
    CatalogEntry(
        'cultrun', 'Cultrun', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='bodhran'
    ),
    # Sound-alike of the conga slap (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dabakan ("The dabakan is a single-headed Philippine drum,
    # primarily used as a supportive instrument in the kulintang ensemble")
    CatalogEntry(
        'dabakan', 'Dabakan', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga slap'
    ),
    # Sound-alike of the bodhran (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Damphu_drum ("is like a bodhrán, a single-sided circular frame
    # drum decorated with symbols or left plain")
    CatalogEntry(
        'damphu', 'Damphu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='bodhran'
    ),
    # Sound-alike of the dhol (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Davul ("is a large double-headed drum that is played with
    # mallets")
    CatalogEntry('davul', 'Davul', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='dhol'),
    # Sound-alike of the dhol (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dhak_(instrument) ("The dhak is a huge membranophone instrument
    # from Bengal and Assam")
    CatalogEntry('dhak', 'Dhak', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='dhol'),
    # Sound-alike of the surdo (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dhimay ("it belongs to the category of double-headed cylindrical
    # membranophone")
    CatalogEntry('dhimay', 'Dhimay', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='surdo'),
    # Sound-alike of the dhol (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dohol ("is a large cylindrical drum with two skinheads")
    CatalogEntry('dohol', 'Dohol', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='dhol'),
    # Sound-alike of the dhol (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dollu ("The dollu is a double-headed drum native to Karnataka,
    # India")
    CatalogEntry('dollu', 'Dollu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='dhol'),
    # Sound-alike of the floor tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dunun ("A dunun is a rope-tuned cylindrical drum with a rawhide
    # skin at both ends, most commonly cow or goat. The drum is played with a stick")
    CatalogEntry(
        'dunun', 'Dunun', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='floor tom'
    ),
    # Sound-alike of the orchestral bass drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Fontomfrom ("Fontomfrom is a Bono type of hourglass-shaped drum
    # mostly used in a royal music ensemble")
    CatalogEntry(
        'fontomfrom',
        'Fontomfrom',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='orchestral bass drum',
    ),
    # Sound-alike of the orchestral bass drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Gbedu ("Gbedu literally means 'big drum' and is a percussion
    # instrument traditionally used in ceremonial Yoruba music in Nigeria and Benin")
    CatalogEntry(
        'gbedu',
        'Gbedu',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='orchestral bass drum',
    ),
    # Sound-alike of the cajon bass (no fetched source sets it apart in sound):
    # https://africandrumming.com.au/cart/gome ("The Gome drum is a fundamental solo and ensemble
    # drum among the Ga and Ashanti of Ghana")
    CatalogEntry('gome', 'Gome', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='cajon bass'),
    # Sound-alike of the high timbale (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Gudugudu ("It is designed to produce a sharp and loud beat that
    # all the other drummers can hear and keep in time with")
    CatalogEntry(
        'gudugudu', 'Gudugudu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='high timbale'
    ),
    # Sound-alike of the taiko (no fetched source sets it apart in sound):
    # https://artdrum.com/HIRA_DAIKO.HTM ("Hira means stout or flat which describes the Hira Daiko
    # shape")
    CatalogEntry(
        'hira daiko', 'Hira-daiko', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='taiko'
    ),
    # Sound-alike of the tumba (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Huehuetl ("It is an upright tubular drum made from a wooden body
    # opened at the bottom that stands on three legs cut from its base, with skin stretched over the
    # top")
    CatalogEntry(
        'huehuetl', 'Huēhuētl', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='tumba'
    ),
    # Sound-alike of the low bongo (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Igba ("is a tom-tom that has a beating surface of the same
    # approximate diameter as a bongo")
    CatalogEntry('igba', 'Igba', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='low bongo'),
    # Sound-alike of the taiko (no fetched source sets it apart in sound):
    # https://collectionapi.metmuseum.org/public/collection/v1/objects/503213
    # https://en.wikipedia.org/wiki/Buk_(drum) ("Membranophone-double-headed / cylindrical drum")
    CatalogEntry('jwago', 'Jwago', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='taiko'),
    # Sound-alike of the high tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Kakko_(instrument) ("The kakko (羯鼓/鞨鼓) is a Japanese
    # double-headed drum")
    CatalogEntry('kakko', 'Kakko', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='high tom'),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Kendang https://nat.museum-digital.de/tag/37818 ("Kendhang
    # batangan or kendhang ciblon is a medium-sized drum, used for the most complex or lively
    # rhythms")
    CatalogEntry(
        'kendang ciblon',
        'Kendang ciblon',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='kendang',
    ),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://nat.museum-digital.de/tag/37818 ("Most are played with the hands but some larger
    # varieties are played with a ball headed stick on the larger head")
    CatalogEntry(
        'kendang wadon',
        'Kendang wadon',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='kendang',
    ),
    # Sound-alike of the mid tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dunun ("The kenkeni is the smallest dunun and has the highest
    # pitch. Typical size is 45-50 cm (18-20 in) in length and 25-35 cm (9.8-13.8 in) in diameter")
    CatalogEntry(
        'kenkeni', 'Kenkeni', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='mid tom'
    ),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Klong_khaek ("is a type of double-headed barrel drum used in
    # Thai music")
    CatalogEntry(
        'klong khaek', 'Klong khaek', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='kendang'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Kpanlogo_(drum)
    # https://www.djembedirect.com/hand-carved-african-kpanlogo-peg-drum-from-ghana-11x25-cow-skin/
    # ("is a type of barrel drum that is associated with Kpanlogo music, and is usually played with
    # two hands")
    CatalogEntry(
        'kpanlogo', 'Kpanlogo', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Kundu_(drum) ("Kundu is a pidgin name in Papua New Guinea for an
    # hourglass drum")
    CatalogEntry('kundu', 'Kundu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'),
    # Sound-alike of the taiko (no fetched source sets it apart in sound):
    # https://ktb.gov.tr/EN-98653/janissary-mehter-music.html
    # https://blog.soton.ac.uk/music/2014/10/22/instruments-istanbul/ ("The Ruler's Drum (Kös) -
    # This large drum stood in front of the ruler's tent")
    CatalogEntry('kus', 'Kös (kus)', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='taiko'),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Madal ("The madal has a cylindrical body with a slight bulge at
    # its center and heads at both ends, one head larger than the other. It is usually played
    # horizontally in a seated position, with both heads played simultaneously")
    CatalogEntry('madal', 'Madal', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='kendang'),
    # Sound-alike of the mridangam (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Madhalam ("It has two sides for playing, made out of leather,
    # and has different kinds of sounds on each side")
    CatalogEntry(
        'maddalam', 'Maddalam', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='mridangam'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Makuta_(drum) ("Makuta drums are tall cylindrical or
    # barrel-shaped Afro-Cuban drums, often cited as an important influence on the development of
    # the tumbadora or conga drum")
    CatalogEntry('makuta', 'Makuta', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'),
    # Sound-alike of the field drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Snare_drum ("Marching snares are typically 12 in (30 cm) deep
    # and 14 in (36 cm) wide. The larger design allows for a deeper-sounding tone, one that is
    # effective for marching bands")
    CatalogEntry(
        'marching snare',
        'Marching snare',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='field drum',
    ),
    # Sound-alike of the taiko (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Taiko ("The typical byō-uchi-daiko is the nagadō-daiko, an
    # elongated drum that is roughly shaped like a wine barrel")
    CatalogEntry(
        'nagado daiko', 'Nagadō-daiko', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='taiko'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Ngoma_drums ("Ngoma is derived from the Kikongo word for
    # 'drum'")
    CatalogEntry('ngoma', 'Ngoma', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'),
    # Sound-alike of the high tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Octoban ("are deep, small diameter, single-head tom-toms")
    CatalogEntry(
        'octoban', 'Octoban', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='high tom'
    ),
    # Sound-alike of the high tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Taiko ("Okedō-daiko or simply okedō, are a type of shime-daiko
    # that are stave-constructed using narrower strips of wood, have a tube-shaped frame")
    CatalogEntry(
        'okedo daiko',
        'Okedō-daiko',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='high tom',
    ),
    # Sound-alike of the tumba (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Pahu ("Carved from a single log and covered on the playing end
    # with a stretched sharkskin, the pahu is played with the palms and fingers of the hand")
    CatalogEntry('pahu', 'Pahu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='tumba'),
    # Sound-alike of the mridangam (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Pakhavaj https://en.wikipedia.org/wiki/Mridangam ("The pakhavaj
    # or pakhawaj is a barrel-shaped, two-headed drum")
    CatalogEntry(
        'pakhavaj', 'Pakhavaj', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='mridangam'
    ),
    # Sound-alike of the tambourine (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Pandero_jarocho ("The pandero jarocho is an octagonal tambourine
    # or pandero traditionally played by men in the Veracruz region of Mexico")
    CatalogEntry(
        'pandero jarocho',
        'Pandero jarocho',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='tambourine',
    ),
    # Sound-alike of the bodhran (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Parai ("It consists of a shallow circular ring made of wood of
    # diameter 16-22 in (410-560 mm)")
    CatalogEntry('parai', 'Parai', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='bodhran'),
    # Sound-alike of the piccolo snare (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Snare_drum ("There are many kinds of piccolo snare which can be
    # piccolos, including the popcorn, soprano and standard snares. Popcorn snares typically have a
    # diameter of 10 in (25 cm)")
    CatalogEntry(
        'popcorn snare',
        'Popcorn snare',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='piccolo snare',
    ),
    # Sound-alike of the high bongo (no fetched source sets it apart in sound):
    # https://collectionapi.metmuseum.org/public/collection/v1/objects/501368
    # https://en.wikipedia.org/wiki/Pahu ("Membranophone-single-headed / kettle drum")
    CatalogEntry(
        'puniu',
        'Puniu (knee drum)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='high bongo',
    ),
    # Sound-alike of the tambourine (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Rebana ("The rebana or terbangan is a tambourine that is used in
    # Islamic devotional music in Southeast Asia")
    CatalogEntry(
        'rebana', 'Rebana', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='tambourine'
    ),
    # Sound-alike of the high timbale (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Repinique ("It is tuned very high to produce a tone that cuts
    # through the sound of the rest of the bateria and is used as both a lead and solo instrument")
    CatalogEntry(
        'repinique',
        'Repinique',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='high timbale',
    ),
    # Sound-alike of the djembe tone (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Sabar ("The drum is generally played with one hand and one stick
    # or 'galan'")
    CatalogEntry(
        'sabar', 'Sabar', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='djembe tone'
    ),
    # Sound-alike of the bodhran (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Sakara_drum ("The Sakara drum is a shallow membranophone with a
    # circular body made of baked clay")
    CatalogEntry(
        'sakara drum', 'Sakara drum', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='bodhran'
    ),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Samphor ("is a small, 2-headed barrel drum indigenous to
    # Cambodia, approximately .35 meter wide by .5 meter long")
    CatalogEntry(
        'samphor', 'Samphor', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='kendang'
    ),
    # Sound-alike of the low tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Dunun ("The sangban is of medium size, with higher pitch than
    # the dundunba. Typical size is 50-60 cm (20-24 in) in length and 30-40 cm (12-16 in) in
    # diameter")
    CatalogEntry(
        'sangban', 'Sangban', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='low tom'
    ),
    # Sound-alike of the high tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Taiko ("Shime-daiko are a set of smaller, roughly snare
    # drum-sized instrument that are tunable")
    CatalogEntry(
        'shime daiko',
        'Shime-daiko',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='high tom',
    ),
    # Sound-alike of the field drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tabor_(instrument) ("is a double-skinned portable drum, often
    # with a gut snare on the batter head, typically played with a single stick in the right hand")
    CatalogEntry(
        'tabor', 'Tabor', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='field drum'
    ),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tambora_(Dominican_drum) ("The Dominican tambora (from the
    # Spanish word tambor, meaning 'drum') is a two headed drum played in merengue music")
    CatalogEntry(
        'tambora',
        'Tambora (Dominican)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='conga',
    ),
    # Sound-alike of the darbuka tek (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tamborim ("is a small round Brazilian frame drum")
    CatalogEntry(
        'tamborim', 'Tamborim', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='darbuka tek'
    ),
    # Sound-alike of the surdo (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tan-tan ("A tan-tan is a cylindrical hand drum from Brazil that
    # is used in small samba and pagode ensembles. It imitates the big Surdo")
    CatalogEntry(
        'tan tan', 'Tan-tan', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='surdo'
    ),
    # Sound-alike of the mid tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tanggu_(drum) ("It is medium in size and barrel-shaped, with two
    # heads made of animal skin, and is played with two sticks")
    CatalogEntry(
        'tanggu', 'Tanggu', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='mid tom'
    ),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Taphon ("It is barrel-shaped with two heads")
    CatalogEntry(
        'taphon', 'Taphon', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='kendang'
    ),
    # Sound-alike of the frame drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tar_(drum) ("is an ancient, single-headed frame drum. It is
    # commonly played in the Middle East and North Africa. The tar's drumhead is struck with one
    # hand")
    CatalogEntry(
        'tar drum',
        'Tar (frame drum)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='frame drum',
    ),
    # Sound-alike of the snare drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Snare_drum ("The tarol snare has similar dimensions to the kit
    # snare. The major distinction is that the snares in this type are on the top head rather than
    # the bottom one")
    CatalogEntry(
        'tarol', 'Tarol', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='snare drum'
    ),
    # Sound-alike of the naqareh (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tassa ("The tassa drum proper is a conical or bowl-shaped
    # nagaara- (aka nagada or nagaada) type drum")
    CatalogEntry(
        'tasha', 'Tassa (tasha)', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='naqareh'
    ),
    # Sound-alike of the high bongo (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tbilat ("The tbilat is a percussion instrument from Morocco
    # which resembles bongos and tabla. It consists of a pair of decorated pottery drums of
    # different sizes")
    CatalogEntry(
        'tbilat', 'Tbilat', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='high bongo'
    ),
    # Sound-alike of the orchestral bass drum (no fetched source sets it apart in sound):
    # https://theatrecrafts.com/pages/home/topics/sound/sound-effects-for-the-stage/
    # https://en.wikipedia.org/wiki/Thunder_sheet ("A large wooden frame, covered with a tight
    # drumskin, with a stick with one end covered with chamois")
    CatalogEntry(
        'thunder drum',
        'Thunder drum',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='orchestral bass drum',
    ),
    # Sound-alike of the thunder sheet (no fetched source sets it apart in sound):
    # https://patents.google.com/patent/US20170178612A1/en
    # https://remo.com/product/spring-drum-thunder-tube ("The spring drum consists of a resonant
    # tube, open at one end and closed by a membrane at the other, with a spring attached to the
    # membrane near its center")
    CatalogEntry(
        'thunder tube',
        'Thunder tube (spring drum)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='thunder sheet',
    ),
    # Sound-alike of the djembe tone (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tifa_(drum) ("The tifa, tiwa or tiva is a single-headed goblet
    # drum used throughout the Maluku Islands of Eastern Indonesia")
    CatalogEntry(
        'tifa', 'Tifa', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='djembe tone'
    ),
    # Sound-alike of the darbuka doum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tombak ("is an Iranian goblet drum")
    CatalogEntry(
        'tombak',
        'Tombak (zarb)',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='darbuka doum',
    ),
    # Sound-alike of the darbuka tek (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tr%E1%BB%91ng_ch%E1%BA%A7u ("It is a small double-headed drum,
    # beaten with a long wooden stick on the top side, causing a loud snapping sound")
    CatalogEntry(
        'trong chau',
        'Trống chầu',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='darbuka tek',
    ),
    # Sound-alike of the kendang (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Tr%E1%BB%91ng_c%C6%A1m ("is a kind of traditional barrel-shaped
    # Vietnamese drum")
    CatalogEntry(
        'trong com', 'Trống cơm', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='kendang'
    ),
    # Sound-alike of the orchestral bass drum (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Taiko ("The tsuri-daiko (釣太鼓, 'suspended drum') is a smaller
    # drum that produces a lower sound, its head measuring about 55 cm (22 in) in diameter")
    CatalogEntry(
        'tsuri daiko',
        'Tsuri-daiko',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='orchestral bass drum',
    ),
    # Sound-alike of the bodhran (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Taiko ("Uchiwa-daiko (団扇太鼓; literally, fan drum) is a type
    # of racket-shaped Japanese drum. It is the only Japanese traditional drum without a sound box
    # and only one skin. It is played with a drumstick while hanging it with the other hand")
    CatalogEntry(
        'uchiwa daiko',
        'Uchiwa-daiko',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='bodhran',
    ),
    # Sound-alike of the high tom (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Urumi_(drum) ("is a double-headed hourglass drum from the state
    # of Tamil Nadu, South India")
    CatalogEntry('urumi', 'Urumi', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='high tom'),
    # Sound-alike of the dhol (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Zabumba ("The top head is usually muted with tape or cloth
    # strip(s) and struck with a cloth-covered mallet (held in the right hand) to produce a low
    # fundamental note with minimal overtones")
    CatalogEntry('zabumba', 'Zabumba', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='dhol'),
    # Sound-alike of the daf (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Khanjani ("Khanjani is a percussion musical instrument, a
    # variety of Daf, found in West Bengal & Odisha")
    CatalogEntry(
        'khanjani', 'Khanjani', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='daf'
    ),
    # Sound-alike of the dhol (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Davul https://en.wikipedia.org/wiki/Tabl ("The Tabl, tapan,
    # atabal or davul is a large double-headed drum that is played with mallets")
    CatalogEntry('tabl', 'Tabl', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='dhol'),
    # Sound-alike of the conga (no fetched source sets it apart in sound):
    # https://en.wikipedia.org/wiki/Timbau ("The timbau or Brazilian timbal is a membranophone
    # instrument derived from the caxambu drum, usually played with both hands")
    CatalogEntry(
        'timbal', 'Timbal (timbau)', Family.DRUMS_AND_PERCUSSION, None, None, sounds_like='conga'
    ),
    # Sound-alike of the darbuka doum (no fetched source sets it apart in sound):
    # https://www.outlookindia.com/culture-society/tumbhaknari-the-soulful-rhythm-of-kashmirs-heartbeat
    # https://www.greaterkashmir.com/news/opinion/clay-musical-instruments-of-kashmir/ ("a goblet
    # drum traditional to Jammu and Kashmir")
    CatalogEntry(
        'tumbaknari',
        'Tumbaknari',
        Family.DRUMS_AND_PERCUSSION,
        None,
        None,
        sounds_like='darbuka doum',
    ),
)
