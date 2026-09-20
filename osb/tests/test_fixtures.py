"""Phase 0 fixture-based validation harness: loads every representative task fixture and
checks it is well-formed and internally consistent. This never dispatches a model or a
coding host — see osb/docs/BASELINE.md for the live-agent smoke-test layer, which is
separate and explicitly labelled."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "tasks"
EXPECTED_FIXTURES = {
    "single-file-bug",
    "multi-file-feature",
    "security-sensitive",
    "interrupted-task",
    "changed-working-tree",
    "two-repo-shared-contract",
}
VALID_PROFILES = {"small-fix", "feature", "cross-service", "high-risk"}


class FixtureShapeTests(unittest.TestCase):
    def test_all_expected_fixtures_present(self) -> None:
        found = {p.stem for p in FIXTURES_DIR.glob("*.json")}
        self.assertEqual(found, EXPECTED_FIXTURES)

    def test_every_fixture_is_well_formed(self) -> None:
        for path in FIXTURES_DIR.glob("*.json"):
            with self.subTest(fixture=path.stem):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(data["fixture_id"], path.stem)
                self.assertIn("goal", data)
                self.assertIn("expected_task_profile", data)
                self.assertIn(data["expected_task_profile"], VALID_PROFILES)

    def test_interrupted_task_fixture_never_reports_stale_verdicts_as_fresh(self) -> None:
        data = json.loads((FIXTURES_DIR / "interrupted-task.json").read_text())
        quality = data["persisted_state_before_interruption"]["quality"]
        self.assertIsNone(quality["final_review_fingerprint"])
        self.assertIsNone(quality["final_qa_fingerprint"])
        self.assertEqual(set(quality["unverified_ac_ids"]), set(quality["required_ac_ids"]))

    def test_changed_working_tree_fixture_fingerprint_actually_differs(self) -> None:
        data = json.loads((FIXTURES_DIR / "changed-working-tree.json").read_text())
        before = data["persisted_state_before_change"]["quality"]["current_patch_fingerprint"]
        after = data["recomputed_fingerprint"]
        self.assertNotEqual(before, after, "fixture must model an actual fingerprint change, not a no-op")

    def test_two_repo_fixture_declares_dependency_order(self) -> None:
        data = json.loads((FIXTURES_DIR / "two-repo-shared-contract.json").read_text())
        repos = {r["id"]: r for r in data["workspace"]["repositories"]}
        self.assertIn("contracts", repos)
        self.assertIn("payments", repos)
        self.assertEqual(repos["payments"].get("depends_on"), ["contracts"])


if __name__ == "__main__":
    unittest.main()
