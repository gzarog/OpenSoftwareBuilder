"""Tests for bounded failure recovery (Next Improvements, Phase 4)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import recovery_policy  # noqa: E402


def _attempt_event(task_id="T1", role="implementer", target_id="F1", fingerprint="fp-1", signature="boom", **extra):
    event = {
        "task_id": task_id, "role": role, "event_type": "repair-attempt",
        "target_kind": "finding", "target_id": target_id,
        "implementation_fingerprint": fingerprint, "failure_signature": signature,
        "root_cause_id": None, "decision": "retry", "reason": "x",
        "timestamp": "2026-09-20T00:00:00Z",
    }
    event.update(extra)
    return event


class NormalizeFailureSignatureTests(unittest.TestCase):
    def test_case_and_whitespace_insensitive(self) -> None:
        self.assertEqual(
            recovery_policy.normalize_failure_signature("  Expected 500,  got 200 "),
            recovery_policy.normalize_failure_signature("expected 500, got 200"),
        )


class EvaluateRepairAttemptTests(unittest.TestCase):
    def test_first_attempt_is_retry(self) -> None:
        result = recovery_policy.evaluate_repair_attempt(
            [], task_id="T1", role="implementer", target_kind="finding", target_id="F1",
            implementation_fingerprint="fp-1", failure_signature="boom",
        )
        self.assertEqual(result["decision"], recovery_policy.RETRY)
        self.assertEqual(result["attempt_number"], 1)

    def test_changed_fingerprint_is_recoverable_not_identical(self) -> None:
        events = [_attempt_event(fingerprint="fp-1", signature="boom")]
        result = recovery_policy.evaluate_repair_attempt(
            events, task_id="T1", role="implementer", target_kind="finding", target_id="F1",
            implementation_fingerprint="fp-2", failure_signature="boom",
        )
        self.assertEqual(result["decision"], recovery_policy.RETRY)
        self.assertEqual(result["attempt_number"], 2)

    def test_repeated_identical_failure_stops(self) -> None:
        # max_identical_repeats=2 (default): one prior identical attempt + this one = 2 -> stop
        events = [_attempt_event(fingerprint="fp-1", signature="boom")]
        result = recovery_policy.evaluate_repair_attempt(
            events, task_id="T1", role="implementer", target_kind="finding", target_id="F1",
            implementation_fingerprint="fp-1", failure_signature="boom",
        )
        self.assertEqual(result["decision"], recovery_policy.STOP_IDENTICAL_FAILURE)

    def test_repeated_identical_failure_message_is_case_insensitive(self) -> None:
        events = [_attempt_event(fingerprint="fp-1", signature="Boom!  Failed")]
        result = recovery_policy.evaluate_repair_attempt(
            events, task_id="T1", role="implementer", target_kind="finding", target_id="F1",
            implementation_fingerprint="fp-1", failure_signature="boom! failed",
        )
        self.assertEqual(result["decision"], recovery_policy.STOP_IDENTICAL_FAILURE)

    def test_attempts_exhausted_after_budget(self) -> None:
        events = [
            _attempt_event(fingerprint=f"fp-{i}", signature=f"different failure {i}")
            for i in range(3)
        ]
        result = recovery_policy.evaluate_repair_attempt(
            events, task_id="T1", role="implementer", target_kind="finding", target_id="F1",
            implementation_fingerprint="fp-99", failure_signature="yet another failure",
            max_repair_attempts=3,
        )
        self.assertEqual(result["decision"], recovery_policy.ATTEMPTS_EXHAUSTED)
        self.assertEqual(result["attempt_number"], 4)

    def test_unrelated_finding_has_independent_budget(self) -> None:
        events = [_attempt_event(target_id="F1", fingerprint="fp-1", signature="boom")] * 3
        result = recovery_policy.evaluate_repair_attempt(
            events, task_id="T1", role="implementer", target_kind="finding", target_id="F2",
            implementation_fingerprint="fp-1", failure_signature="different problem",
        )
        self.assertEqual(result["decision"], recovery_policy.RETRY)
        self.assertEqual(result["attempt_number"], 1)

    def test_unrelated_task_has_independent_budget(self) -> None:
        events = [_attempt_event(task_id="OTHER-TASK", target_id="F1", fingerprint="fp-1", signature="boom")] * 5
        result = recovery_policy.evaluate_repair_attempt(
            events, task_id="T1", role="implementer", target_kind="finding", target_id="F1",
            implementation_fingerprint="fp-1", failure_signature="boom",
        )
        self.assertEqual(result["decision"], recovery_policy.RETRY)

    def test_new_root_cause_reauthorizes_fresh_series(self) -> None:
        exhausted_events = [
            _attempt_event(fingerprint=f"fp-{i}", signature=f"failure {i}", root_cause_id="cause-1")
            for i in range(3)
        ]
        blocked = recovery_policy.evaluate_repair_attempt(
            exhausted_events, task_id="T1", role="implementer", target_kind="finding", target_id="F1",
            implementation_fingerprint="fp-99", failure_signature="failure 99",
            root_cause_id="cause-1", max_repair_attempts=3,
        )
        self.assertEqual(blocked["decision"], recovery_policy.ATTEMPTS_EXHAUSTED)

        reauthorized = recovery_policy.evaluate_repair_attempt(
            exhausted_events, task_id="T1", role="implementer", target_kind="finding", target_id="F1",
            implementation_fingerprint="fp-100", failure_signature="genuinely new root cause",
            root_cause_id="cause-2", max_repair_attempts=3,
        )
        self.assertEqual(reauthorized["decision"], recovery_policy.RETRY)
        self.assertEqual(reauthorized["attempt_number"], 1)


class EvaluateContextExpansionTests(unittest.TestCase):
    def test_within_budget_expands(self) -> None:
        result = recovery_policy.evaluate_context_expansion(
            [], task_id="T1", role="architect", question_id="Q1", max_expansions=5
        )
        self.assertEqual(result["decision"], recovery_policy.EXPAND_CONTEXT)

    def test_exhausted_budget_marks_unresolved(self) -> None:
        events = [
            {
                "task_id": "T1", "role": "architect", "event_type": "context-expansion",
                "target_kind": "question", "target_id": "Q1", "timestamp": "2026-09-20T00:00:00Z",
            }
            for _ in range(5)
        ]
        result = recovery_policy.evaluate_context_expansion(
            events, task_id="T1", role="architect", question_id="Q1", max_expansions=5
        )
        self.assertEqual(result["decision"], recovery_policy.QUESTION_UNRESOLVED)


class EventLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "recovery.jsonl"

    def test_valid_event_is_appended(self) -> None:
        errors = recovery_policy.append_event(self.path, _attempt_event())
        self.assertEqual(errors, [])
        self.assertEqual(len(recovery_policy.load_events(self.path)), 1)

    def test_invalid_event_is_rejected_and_not_written(self) -> None:
        bad_event = {"task_id": "T1"}  # missing required fields
        errors = recovery_policy.append_event(self.path, bad_event)
        self.assertTrue(errors)
        self.assertFalse(self.path.exists())

    def test_blocked_event_records_blocker_kind(self) -> None:
        event = {
            "task_id": "T1", "role": "qa", "event_type": "blocked",
            "target_kind": "ac", "target_id": "AC3", "blocker_kind": "test-environment-unavailable",
            "timestamp": "2026-09-20T00:00:00Z",
        }
        errors = recovery_policy.append_event(self.path, event)
        self.assertEqual(errors, [])


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_evaluate_and_record_round_trip(self) -> None:
        request = {
            "task_id": "T1", "role": "implementer", "event_type": "repair-attempt",
            "target_kind": "finding", "target_id": "F1",
            "implementation_fingerprint": "fp-1", "failure_signature": "boom",
        }
        request_path = self.root / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")

        rc = recovery_policy.main(["evaluate", str(request_path), "--workspace-root", str(self.root), "--record"])
        self.assertEqual(rc, 0)

        events_path = self.root / ".osb" / "runs" / "T1" / "recovery.jsonl"
        self.assertTrue(events_path.exists())
        self.assertEqual(len(recovery_policy.load_events(events_path)), 1)

        rc = recovery_policy.main(["status", "T1", "--workspace-root", str(self.root)])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
