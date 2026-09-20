"""Failure-case tests for the deterministic completion verifier (P0-C, Phase 1.3):
missing AC, fabricated pass without evidence, invalid QA revision, stale fingerprint after
a code change, a delta review masquerading as final, an open finding, unknown/truncated
evidence, failed consolidation, corrupt state, and an interrupted/resumed run."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import verify_task  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "a.py").write_text("print('a')\n", encoding="utf-8")
    _git(repo, "add", "a.py")
    _git(repo, "commit", "-q", "-m", "base")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def _complete_state(base_revision: str, fingerprint: str) -> dict:
    return {
        "task_id": "OSB-2026-0101-001",
        "goal": "test task",
        "phase": "complete",
        "architecture_checkpoint": "CP1",
        "acceptance": {"AC1": "the thing works"},
        "units": {"U1": {"status": "complete", "files": ["a.py"], "checkpoint": "CP2"}},
        "review": {"status": "clean", "scope": "final-combined-change", "open": [], "resolved": ["F1"]},
        "qa": {"status": "pass", "failed": []},
        "knowledge_watermark": "CP2",
        "quality": {
            "unresolved_context_requests": [],
            "required_ac_ids": ["AC1"],
            "task_base_revision": base_revision,
            "current_patch_fingerprint": fingerprint,
            "final_review_fingerprint": fingerprint,
            "final_qa_fingerprint": fingerprint,
            "unverified_ac_ids": [],
            "knowledge_consolidated": True,
        },
    }


def _qa_pass_evidence(fingerprint: str) -> dict:
    return {
        "status": "pass",
        "revision": fingerprint,
        "ac": {"AC1": {"result": "pass", "evidence": "unit-test: pass"}},
    }


class VerifyTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        self.base_revision = _init_repo(self.repo)
        self.fingerprint = verify_task.compute_fingerprint(self.repo, self.base_revision)

    def test_valid_complete_task_passes(self) -> None:
        state = _complete_state(self.base_revision, self.fingerprint)
        ok, reasons = verify_task.check_completion(state, self.repo)
        self.assertTrue(ok, reasons)
        self.assertEqual(reasons, [])

    def test_missing_ac_text_is_rejected(self) -> None:
        state = _complete_state(self.base_revision, self.fingerprint)
        state["quality"]["required_ac_ids"] = ["AC1", "AC2"]
        ok, reasons = verify_task.check_completion(state, self.repo)
        self.assertFalse(ok)
        self.assertTrue(any("AC2" in r for r in reasons))

    def test_fabricated_pass_without_evidence_is_rejected(self) -> None:
        state = _complete_state(self.base_revision, self.fingerprint)
        # QA claims pass in task state, but the actual QA evidence file only has 'not-run'.
        evidence = {"status": "pass", "revision": self.fingerprint, "ac": {"AC1": {"result": "not-run", "evidence": "env unavailable"}}}
        ok, reasons = verify_task.check_completion(state, self.repo, evidence)
        self.assertFalse(ok)
        self.assertTrue(any("not 'pass'" in r for r in reasons))

    def test_invalid_qa_revision_is_rejected(self) -> None:
        state = _complete_state(self.base_revision, self.fingerprint)
        evidence = _qa_pass_evidence("fp-0000000000000000")
        ok, reasons = verify_task.check_completion(state, self.repo, evidence)
        self.assertFalse(ok)
        self.assertTrue(any("recorded for revision" in r for r in reasons))

    def test_stale_fingerprint_after_code_change_is_rejected(self) -> None:
        state = _complete_state(self.base_revision, self.fingerprint)
        (self.repo / "a.py").write_text("print('a changed')\n", encoding="utf-8")
        ok, reasons = verify_task.check_completion(state, self.repo)
        self.assertFalse(ok)
        self.assertTrue(any("stale" in r for r in reasons))

    def test_delta_review_used_as_final_is_rejected(self) -> None:
        state = _complete_state(self.base_revision, self.fingerprint)
        state["review"]["scope"] = "delta"
        ok, reasons = verify_task.check_completion(state, self.repo)
        self.assertFalse(ok)
        self.assertTrue(any("delta pass is never" in r for r in reasons))

    def test_open_finding_is_rejected(self) -> None:
        state = _complete_state(self.base_revision, self.fingerprint)
        state["review"]["status"] = "findings"
        state["review"]["open"] = ["F2"]
        ok, reasons = verify_task.check_completion(state, self.repo)
        self.assertFalse(ok)
        self.assertTrue(any("not 'clean'" in r for r in reasons))

    def test_truncated_or_unknown_evidence_is_rejected(self) -> None:
        state = _complete_state(self.base_revision, self.fingerprint)
        evidence = {"status": "pass", "revision": self.fingerprint, "ac": {}}  # no AC1 entry at all
        ok, reasons = verify_task.check_completion(state, self.repo, evidence)
        self.assertFalse(ok)
        self.assertTrue(any("no verdict for required AC 'AC1'" in r for r in reasons))

    def test_failed_consolidation_is_rejected(self) -> None:
        state = _complete_state(self.base_revision, self.fingerprint)
        state["quality"]["knowledge_consolidated"] = False
        ok, reasons = verify_task.check_completion(state, self.repo)
        self.assertFalse(ok)
        self.assertTrue(any("knowledge_consolidated" in r for r in reasons))

    def test_corrupt_state_is_rejected_by_schema(self) -> None:
        state = _complete_state(self.base_revision, self.fingerprint)
        del state["quality"]["current_patch_fingerprint"]  # corrupt: required field missing
        ok, reasons = verify_task.check_completion(state, self.repo)
        self.assertFalse(ok)
        self.assertTrue(any(r.startswith("schema:") for r in reasons))

    def test_interrupted_and_resumed_run_reenters_final_review(self) -> None:
        # Mid-review checkpoint: delta clean, no final review/QA fingerprint recorded yet.
        state = _complete_state(self.base_revision, self.fingerprint)
        state["phase"] = "review"
        state["review"] = {"status": "clean", "scope": "delta", "open": [], "resolved": ["F1"]}
        state["qa"] = {"status": "pending", "failed": []}
        state["quality"]["final_review_fingerprint"] = None
        state["quality"]["final_qa_fingerprint"] = None
        state["quality"]["unverified_ac_ids"] = ["AC1"]
        state["quality"]["knowledge_consolidated"] = False

        ok, reasons = verify_task.check_completion(state, self.repo)
        self.assertFalse(ok, "an interrupted task must never resume directly at completion")
        self.assertTrue(any("final-combined-change" in r or "not 'clean'" in r for r in reasons))

    def test_write_state_atomic_rejects_invalid_and_preserves_previous(self) -> None:
        dest = Path(self._tmp.name) / "state.json"
        good = _complete_state(self.base_revision, self.fingerprint)
        errors = verify_task.write_state_atomic(dest, good)
        self.assertEqual(errors, [])
        original_bytes = dest.read_bytes()

        bad = copy.deepcopy(good)
        del bad["phase"]
        errors = verify_task.write_state_atomic(dest, bad)
        self.assertTrue(errors)
        self.assertEqual(dest.read_bytes(), original_bytes, "a rejected write must not touch the previous valid state")

    def test_fingerprint_stable_for_unchanged_tree(self) -> None:
        fp1 = verify_task.compute_fingerprint(self.repo, self.base_revision)
        fp2 = verify_task.compute_fingerprint(self.repo, self.base_revision)
        self.assertEqual(fp1, fp2)

    def test_fingerprint_ignores_osb_state_and_events(self) -> None:
        (self.repo / ".osb/state").mkdir(parents=True)
        (self.repo / ".osb/state/task.json").write_text("{}", encoding="utf-8")
        (self.repo / ".osb/knowledge/events").mkdir(parents=True)
        (self.repo / ".osb/knowledge/events/task.jsonl").write_text('{"type":"gotcha"}\n', encoding="utf-8")
        fp = verify_task.compute_fingerprint(self.repo, self.base_revision)
        self.assertEqual(fp, self.fingerprint, "excluded paths must not affect the fingerprint")


if __name__ == "__main__":
    unittest.main()
