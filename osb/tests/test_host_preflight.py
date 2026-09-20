"""Tests for the deterministic host capability preflight (P1-G, Phase 7)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import host_preflight  # noqa: E402

from _helpers import make_fake_workspace, run_install  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "host_capability"


class HostCapabilityFixtureTests(unittest.TestCase):
    def test_every_documented_host_has_a_fixture(self) -> None:
        found = {json.loads(p.read_text())["host"] for p in FIXTURES_DIR.glob("*.json")}
        self.assertEqual(found, set(host_preflight.HOST_KEYS))


class HostPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = make_fake_workspace(Path(self._tmp.name) / "ws")
        run_install(self.workspace, "init", "--host", "claude")

    def _fill_models(self, host_key: str = "claude-code") -> None:
        text = (self.workspace / "osb.yaml").read_text()
        text = text.replace(
            f"{host_key}:\n    architect:\n    implementer:\n    reviewer:\n    qa:",
            f"{host_key}:\n    architect: some-model\n    implementer: some-model\n    reviewer: some-model\n    qa: some-model",
        )
        (self.workspace / "osb.yaml").write_text(text, encoding="utf-8")

    def test_missing_osb_yaml_blocks_models_configured(self) -> None:
        (self.workspace / "osb.yaml").unlink()
        report = host_preflight.run_preflight(self.workspace, "claude")
        self.assertEqual(report["checks"]["models_configured"]["status"], "blocked")
        self.assertEqual(report["overall"], "blocked")

    def test_blank_models_block_overall(self) -> None:
        report = host_preflight.run_preflight(self.workspace, "claude")
        self.assertEqual(report["checks"]["models_configured"]["status"], "blocked")
        self.assertEqual(report["overall"], "blocked")

    def test_filled_models_and_present_adapter_pass_those_checks(self) -> None:
        self._fill_models()
        report = host_preflight.run_preflight(self.workspace, "claude")
        self.assertEqual(report["checks"]["models_configured"]["status"], "pass")
        self.assertEqual(report["checks"]["generated_adapter_present"]["status"], "pass")

    def test_missing_generated_adapter_is_blocked(self) -> None:
        self._fill_models()
        (self.workspace / ".claude/agents/architect.md").unlink()
        report = host_preflight.run_preflight(self.workspace, "claude")
        self.assertEqual(report["checks"]["generated_adapter_present"]["status"], "blocked")
        self.assertEqual(report["overall"], "blocked")

    def test_worktree_isolation_not_configured_is_not_applicable(self) -> None:
        report = host_preflight.run_preflight(self.workspace, "claude")
        self.assertEqual(report["checks"]["git_worktree_supported"]["status"], "not-applicable")

    def test_worktree_isolation_configured_and_supported_passes(self) -> None:
        import subprocess

        subprocess.run(["git", "init", "-q"], cwd=self.workspace, check=True, capture_output=True)
        text = (self.workspace / "osb.yaml").read_text()
        text = text.replace("checkpoint_state: true", "checkpoint_state: true\n  isolation: worktree")
        (self.workspace / "osb.yaml").write_text(text, encoding="utf-8")

        report = host_preflight.run_preflight(self.workspace, "claude")
        self.assertEqual(report["checks"]["git_worktree_supported"]["status"], "pass")

    def test_ragmonk_disabled_is_not_applicable(self) -> None:
        text = (self.workspace / "osb.yaml").read_text().replace(
            "ragmonk:\n  enabled: true", "ragmonk:\n  enabled: false"
        )
        (self.workspace / "osb.yaml").write_text(text, encoding="utf-8")
        report = host_preflight.run_preflight(self.workspace, "claude")
        self.assertEqual(report["checks"]["ragmonk"]["status"], "not-applicable")

    def test_test_command_and_role_independence_are_always_unknown_not_assumed_pass(self) -> None:
        self._fill_models()
        report = host_preflight.run_preflight(self.workspace, "claude")
        self.assertEqual(report["checks"]["test_command_capability"]["status"], "unknown")
        self.assertEqual(report["checks"]["independent_role_contexts"]["status"], "unknown")
        # 'unknown' must never be silently promoted to overall 'pass' when other checks pass.
        self.assertIn(report["overall"], ("unknown", "blocked"))


if __name__ == "__main__":
    unittest.main()
