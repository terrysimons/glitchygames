"""The CDK context the CLI gives the app (infra/cdk.json), for the tests' apps.

The tests build their apps with the same feature flags ``cdk deploy`` uses, so the templates they
check are the templates that get deployed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CDK_JSON_PATH = Path(__file__).resolve().parent.parent / 'cdk.json'


def project_context(**overrides: Any) -> dict[str, Any]:
    """Return cdk.json's context (its feature flags and settings), with overrides applied.

    Args:
        **overrides: Context keys to set, replacing cdk.json's values.

    Returns:
        The context, a new dict.

    """
    context = json.loads(CDK_JSON_PATH.read_text(encoding='utf-8'))['context']
    return {**context, **overrides}
