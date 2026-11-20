"""The game's art rig: it writes the sprite TOML files the game ships.

The TOML files are the assets (master plan, decision 3); this package only writes them. It is
never imported by the game at run time. Feature plan:
plans/2026-11-14-zombies-aint-my-neighbors-3-dex.md; spec: the character BOM
(plans/2026-11-14-zombies-aint-my-neighbors-2-character-bom.md).

* ``palettes``: each kid's look (palette, head and clothes styles).
* ``poses``: the BOM's kid animations, and the pose of every frame.
* ``rig``: draws a frame from a pose and a look, outlined, as rows of palette characters.
* ``hand_points``: where a weapon sits in each weapon frame, from the same poses.
* ``build``: writes the sprite files (``python -m zombies_aint_my_neighbors.art.build``).
* ``contact_sheet``: renders a sprite's frames to a PNG to check by eye.
"""
