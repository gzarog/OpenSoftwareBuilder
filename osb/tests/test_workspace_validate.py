"""Tests for the multi-repo workspace config validator (P0-A, Phase 3)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import workspace_validate  # noqa: E402


def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, capture_output=True)


class WorkspaceValidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        for rel in ("contracts", "services/identity-api", "services/payment-api"):
            _init_git_repo(self.root / rel)

    def _valid_workspace(self) -> dict:
        return {
            "mode": "multi-repo",
            "repositories": [
                {"id": "contracts", "path": "contracts"},
                {"id": "identity", "path": "services/identity-api", "depends_on": ["contracts"]},
                {"id": "payments", "path": "services/payment-api", "depends_on": ["contracts", "identity"]},
            ],
            "integration_checks": [{"name": "api-contracts", "command": "./check.sh"}],
        }

    def test_valid_workspace_has_no_errors(self) -> None:
        errors = workspace_validate.validate_workspace(self._valid_workspace(), self.root)
        self.assertEqual(errors, [])

    def test_single_repo_mode_is_always_valid_regardless_of_other_fields(self) -> None:
        errors = workspace_validate.validate_workspace({"mode": "single-repo"}, self.root)
        self.assertEqual(errors, [])

    def test_duplicate_ids_rejected(self) -> None:
        ws = self._valid_workspace()
        ws["repositories"][1]["id"] = "contracts"
        errors = workspace_validate.validate_workspace(ws, self.root)
        self.assertTrue(any("duplicate repository id" in e for e in errors))

    def test_unknown_dependency_rejected(self) -> None:
        ws = self._valid_workspace()
        ws["repositories"][0]["depends_on"] = ["nonexistent"]
        errors = workspace_validate.validate_workspace(ws, self.root)
        self.assertTrue(any("unknown repository 'nonexistent'" in e for e in errors))

    def test_dependency_cycle_rejected(self) -> None:
        ws = self._valid_workspace()
        ws["repositories"][0]["depends_on"] = ["payments"]  # contracts -> payments -> ... -> contracts
        errors = workspace_validate.validate_workspace(ws, self.root)
        self.assertTrue(any("dependency cycle" in e for e in errors))

    def test_overlapping_paths_rejected(self) -> None:
        ws = self._valid_workspace()
        ws["repositories"].append({"id": "nested", "path": "contracts/nested"})
        (self.root / "contracts/nested").mkdir(parents=True)
        (self.root / "contracts/nested/.git").mkdir()
        errors = workspace_validate.validate_workspace(ws, self.root)
        self.assertTrue(any("overlap" in e for e in errors))

    def test_missing_git_root_rejected(self) -> None:
        ws = self._valid_workspace()
        ws["repositories"].append({"id": "plain-dir", "path": "not-a-repo"})
        (self.root / "not-a-repo").mkdir()
        errors = workspace_validate.validate_workspace(ws, self.root)
        self.assertTrue(any("not a Git root" in e for e in errors))

    def test_nonexistent_path_rejected(self) -> None:
        ws = self._valid_workspace()
        ws["repositories"].append({"id": "missing", "path": "does-not-exist"})
        errors = workspace_validate.validate_workspace(ws, self.root)
        self.assertTrue(any("path does not exist" in e for e in errors))

    def test_topological_order_respects_dependencies(self) -> None:
        repo_by_id = {r["id"]: r for r in self._valid_workspace()["repositories"]}
        order = workspace_validate.topological_order(repo_by_id)
        self.assertLess(order.index("contracts"), order.index("identity"))
        self.assertLess(order.index("identity"), order.index("payments"))

    def test_topological_order_raises_on_cycle(self) -> None:
        repo_by_id = {
            "a": {"id": "a", "depends_on": ["b"]},
            "b": {"id": "b", "depends_on": ["a"]},
        }
        with self.assertRaises(workspace_validate.WorkspaceConfigError):
            workspace_validate.topological_order(repo_by_id)


if __name__ == "__main__":
    unittest.main()
