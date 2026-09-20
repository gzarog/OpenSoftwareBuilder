"""Self-check: the structural validator must pass against this repository's own state.

This is a contract-simulation test (P0-C/P0-I), not a live-agent test — it never invokes a
model or a coding host.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class ValidateOsbSelfCheckTests(unittest.TestCase):
    def test_validator_passes_on_this_repository(self) -> None:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "osb/scripts/validate_osb.py")],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
