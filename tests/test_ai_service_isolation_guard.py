"""The test harness's promise that no test reaches the real AI service (tests/harness.py).

A machine with the service installed would otherwise load gigabytes of models for a test, and only
there. The harness points the one-folder variable nowhere and removes the two that would win over
it, whatever a developer's shell exports.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from glitchygames import ai_link
from glitchygames.ai_link import ServiceLocations, service_locations
from glitchygames.process import OutputCapture, run_command
from tests.leaked_state_guard import environment_holds

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOWHERE = Path('/nonexistent/glitchygames-ai-service')
SUBPROCESS_TIMEOUT_SECONDS = 120.0
# Loads the harness as the suite does, then asks where the service is
ASK_WHERE_THE_SERVICE_IS = """
import tests.harness
from glitchygames.ai_link import service_locations
print(service_locations().model_dump_json())
"""


def test_this_suites_service_is_nowhere():
    """In this run, the service is in the harness's folder that doesn't exist."""
    assert service_locations() == ServiceLocations.in_one_folder(root=NOWHERE)
    assert environment_holds(name=ai_link.PROGRAM_ROOT_ENVIRONMENT_VARIABLE, value=None)
    assert environment_holds(name=ai_link.USER_ROOT_ENVIRONMENT_VARIABLE, value=None)


def test_the_harness_points_the_service_nowhere_whatever_the_shell_exports(tmp_path: Path):
    """Every location variable exported to a real install, and the harness still wins."""
    installed = tmp_path / 'a real install'
    environment = {
        **os.environ,
        ai_link.INSTALL_ROOT_ENVIRONMENT_VARIABLE: str(installed),
        ai_link.PROGRAM_ROOT_ENVIRONMENT_VARIABLE: str(installed / 'programs'),
        ai_link.USER_ROOT_ENVIRONMENT_VARIABLE: str(installed / 'user'),
    }

    result = run_command(
        command=[sys.executable, '-c', ASK_WHERE_THE_SERVICE_IS],
        environment=environment,
        timeout_seconds=SUBPROCESS_TIMEOUT_SECONDS,
        capture_output=OutputCapture.APART,
        working_directory=PROJECT_ROOT,
    )

    assert result.returncode == 0, result.stderr
    reported = ServiceLocations.model_validate(json.loads(result.stdout.splitlines()[-1]))
    assert reported == ServiceLocations.in_one_folder(root=NOWHERE)
