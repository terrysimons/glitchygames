# The AI Query Inspector's Button Labels Never Showed

- **Description**: `scripts/ai_query_inspector.py`'s three buttons (Send Query, Toggle Full, Back) showed as plain coloured boxes, with no label. `add_button_text` rendered each label and centred it on `button.rect.center`, the button's position on the screen (about (80, 520) for Send Query), then drew it onto `button.image`, the button's own 120×40 surface. Measured in surface coordinates, that centre is far outside the surface, so nothing landed on it. Reproduced headless (2026-11-21): the old drawing leaves 0 label pixels on the button; the fixed one leaves 224.
- **Status**: Fixed (2026-11-21, `fix/assert-replacement-scripts`)
- **Priority**: Low (a hand-run tool, never shipped)
- **Root Cause**: screen coordinates used where surface coordinates were needed: the label was centred on the button's rect, not on its image's own rect.
- **Test gap**: the script has no tests, and nothing looked at its buttons' pixels. Found while removing its asserts.
- **Fix**: `_ButtonSprite` draws its face and centres its label on the face's own rect (`face.get_rect().center`), and keeps its own area for hit tests (`contains`), so the 15 asserts on `image`/`rect` went too.
- **Siblings checked** (a label centred on a rect's centre, outside tests in `src/` and `scripts/`, `git grep -nE "center=[a-z_.]*rect\.center"`): one other, `src/glitchygames/ui/sliders.py`'s tab labels, which is correct: its `tab_rect` is in the image's own coordinates (it starts at 0).
- **Reporter**: Claude
- **Date Reported**: 2026-11-21
- **Files**: `scripts/ai_query_inspector.py`
