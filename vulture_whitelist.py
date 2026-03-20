"""Vulture whitelist for false positives.

This file is not imported anywhere. It exists solely to tell vulture
that certain names are used even though it cannot detect usage statically.
"""

# __deepcopy__ protocol requires a `memo` parameter even when unused.
# Location: glitchygames/events/core.py HashableEvent.__deepcopy__
memo  # noqa: F821

# Protocol method signatures define the interface contract for type checking.
# The parameter names are structural and cannot be removed.
# Location: glitchygames/fonts/font_manager.py GameFont Protocol
fgcolor  # noqa: F821
bgcolor  # noqa: F821
surf  # noqa: F821
dest  # noqa: F821
