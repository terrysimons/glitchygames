# The Performance Charts' "commit" Axis Title Overlaps the Commit Hashes

- **Description**: On the Performance page's charts, the x axis title `commit` is drawn over the rotated short commit hashes under the axis (seen 2026-11-06 in "Processing time per frame", in a local build in Chrome at 1400 px wide). The layout's bottom margin is 48 px (`margin: { l: 56, r: 16, t: 40, b: 48 }`), which the hashes, rotated when there are many commits, fill
- **Status**: Open
- **Priority**: Low (cosmetic)
- **Reporter**: Claude, checking the game list (#154) in a browser
- **Date Reported**: 2026-11-14
- **Files**: `src/glitchygames/replay/tools/performance_pages.py` (the chart layouts, `title: { text: 'commit' }`)
