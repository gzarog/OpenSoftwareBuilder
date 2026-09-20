"""Tests for per-task execution reports (Next Improvements, Phase 5)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import run_report  # noqa: E402
import schema_validate  # noqa: E402


def _state(**overrides) -> dict:
    state = {
        "task_id": "T1",
        "goal": "test task",
        "phase": "complete",
        "acceptance": {"AC1": "works", "AC2": "also works"},
        "units": {"U1": {"status": "complete", "files": ["a.py", "b.py"]}},
        "review": {"status": "clean", "scope": "final-combined-change"},
        "qa": {"status": "pass", "failed": []},
        "quality": {
            "unresolved_context_requests": [],
            "required_ac_ids": ["AC1", "AC2"],
            "task_base_revision": "abc",
            "current_patch_fingerprint": "fp-1",
            "final_review_fingerprint": "fp-1",
            "final_qa_fingerprint": "fp-1",
            "unverified_ac_ids": [],
        },
    }
    state.update(overrides)
    return state


class SumMetricTests(unittest.TestCase):
    def test_no_event_reports_metric_is_unavailable(self) -> None:
        self.assertEqual(run_report._sum_metric([{"other": 1}], "tokens"), run_report.UNAVAILABLE)

    def test_sums_numeric_values(self) -> None:
        events = [{"tokens": 10}, {"tokens": 20}]
        self.assertEqual(run_report._sum_metric(events, "tokens"), 30)

    def test_all_unavailable_values_stay_unavailable(self) -> None:
        events = [{"tokens": "unavailable"}, {"tokens": "unavailable"}]
        self.assertEqual(run_report._sum_metric(events, "tokens"), run_report.UNAVAILABLE)

    def test_never_returns_zero_for_absent_metric(self) -> None:
        result = run_report._sum_metric([], "tokens")
        self.assertNotEqual(result, 0)
        self.assertEqual(result, run_report.UNAVAILABLE)


class RenderTests(unittest.TestCase):
    def test_complete_state_yields_complete_status(self) -> None:
        report = run_report.render(_state(), [])
        self.assertEqual(report["task"]["final_status"], "complete")

    def test_blocked_phase_yields_blocked_status(self) -> None:
        report = run_report.render(_state(phase="blocked"), [])
        self.assertEqual(report["task"]["final_status"], "blocked")

    def test_recovery_status_blocked_yields_blocked_status(self) -> None:
        report = run_report.render(_state(phase="qa", recovery={"status": "blocked", "last_blocker": "env down"}), [])
        self.assertEqual(report["task"]["final_status"], "blocked")
        self.assertIn("env down", report["recovery"]["unresolved_blockers"])

    def test_incomplete_state_without_blocker_is_interrupted(self) -> None:
        report = run_report.render(_state(phase="review"), [])
        self.assertEqual(report["task"]["final_status"], "interrupted")

    def test_failed_event_yields_failed_status(self) -> None:
        report = run_report.render(_state(phase="qa"), [{"kind": "failed", "timestamp": "x"}])
        self.assertEqual(report["task"]["final_status"], "failed")

    def test_verified_ac_ids_excludes_unverified(self) -> None:
        state = _state()
        state["quality"]["unverified_ac_ids"] = ["AC2"]
        report = run_report.render(state, [])
        self.assertEqual(report["quality"]["verified_ac_ids"], ["AC1"])
        self.assertEqual(report["quality"]["unverified_ac_ids"], ["AC2"])

    def test_partial_qa_never_shows_full_coverage(self) -> None:
        state = _state()
        state["quality"]["unverified_ac_ids"] = ["AC2"]
        report = run_report.render(state, [])
        self.assertLess(len(report["quality"]["verified_ac_ids"]), len(report["quality"]["required_ac_ids"]))

    def test_elapsed_seconds_computed_from_timestamps(self) -> None:
        report = run_report.render(
            _state(), [], started_at="2026-09-20T00:00:00Z", ended_at="2026-09-20T00:02:00Z"
        )
        self.assertEqual(report["task"]["elapsed_seconds"], 120.0)

    def test_elapsed_seconds_unavailable_without_timestamps(self) -> None:
        report = run_report.render(_state(), [])
        self.assertEqual(report["task"]["elapsed_seconds"], run_report.UNAVAILABLE)

    def test_token_usage_unavailable_when_host_does_not_expose_it(self) -> None:
        report = run_report.render(_state(), [{"kind": "role-dispatch"}])
        self.assertEqual(report["efficiency"]["input_tokens"], run_report.UNAVAILABLE)
        self.assertEqual(report["efficiency"]["output_tokens"], run_report.UNAVAILABLE)

    def test_local_changes_only_defaults_true(self) -> None:
        report = run_report.render(_state(), [])
        self.assertTrue(report["scope"]["local_changes_only"])

    def test_report_validates_against_schema(self) -> None:
        report = run_report.render(_state(), [{"kind": "role-dispatch", "tool_calls": 3}])
        errors = schema_validate.validate(report, run_report.EXECUTION_REPORT_SCHEMA)
        self.assertEqual(errors, [])

    def test_render_is_idempotent_given_pinned_generated_at(self) -> None:
        report_a = run_report.render(_state(), [], generated_at="2026-09-20T00:00:00Z")
        report_b = run_report.render(_state(), [], generated_at="2026-09-20T00:00:00Z")
        self.assertEqual(report_a, report_b)

    def test_stale_final_fingerprint_is_visible_in_report(self) -> None:
        state = _state()
        state["quality"]["current_patch_fingerprint"] = "fp-2"  # diverged from final_review/qa fingerprint
        report = run_report.render(state, [])
        self.assertNotEqual(report["scope"]["current_patch_fingerprint"], report["quality"]["review_fingerprint"])


class SummarizeTests(unittest.TestCase):
    def test_summary_includes_status_and_qa_coverage(self) -> None:
        report = run_report.render(_state(), [], generated_at="2026-09-20T00:00:00Z")
        text = run_report.summarize(report)
        self.assertIn("COMPLETE", text)
        self.assertIn("2/2 required AC(s) verified", text)

    def test_summary_never_hides_unverified_acs(self) -> None:
        state = _state()
        state["quality"]["unverified_ac_ids"] = ["AC2"]
        report = run_report.render(state, [])
        text = run_report.summarize(report)
        self.assertIn("unverified: AC2", text)


class RecordEventTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "events.jsonl"

    def test_appended_event_gets_a_timestamp(self) -> None:
        run_report.append_event(self.path, {"kind": "role-dispatch"})
        events = run_report.load_events(self.path)
        self.assertEqual(len(events), 1)
        self.assertIn("timestamp", events[0])


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_record_and_render_round_trip(self) -> None:
        rc = run_report.main([
            "record", "T1",
            str(self._write_json("event.json", {"kind": "role-dispatch", "tool_calls": 2})),
            "--workspace-root", str(self.root),
        ])
        self.assertEqual(rc, 0)

        state_path = self._write_json("state.json", _state())
        request_path = self._write_json("request.json", {})
        rc = run_report.main(["render", str(state_path), str(request_path), "--workspace-root", str(self.root)])
        self.assertEqual(rc, 0)

        report_path = self.root / ".osb" / "runs" / "T1" / "report.json"
        md_path = self.root / ".osb" / "runs" / "T1" / "report.md"
        self.assertTrue(report_path.exists())
        self.assertTrue(md_path.exists())

    def _write_json(self, name: str, data: dict) -> Path:
        path = self.root / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
