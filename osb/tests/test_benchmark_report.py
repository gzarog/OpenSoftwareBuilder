"""Tests for the before/after benchmark report (P1-F, Phase 6)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import benchmark_report  # noqa: E402
import schema_validate  # noqa: E402


def _run(fixture_id="single-file-bug", revision="fp-1", **overrides) -> dict:
    base = {
        "fixture_id": fixture_id,
        "run_label": "baseline",
        "task_revision": revision,
        "metrics": {
            "elapsed_seconds": 120,
            "model_dispatches": 4,
            "tool_calls": 20,
            "input_tokens": "unavailable",
            "output_tokens": "unavailable",
            "repair_cycles": 0,
        },
        "quality": {"ac_coverage": 1.0, "regressions_found": 0, "unresolved_blockers": 0, "repeatable": True},
    }
    base.update(overrides)
    return base


class RunMetricsSchemaTests(unittest.TestCase):
    def test_valid_run_has_no_schema_errors(self) -> None:
        self.assertEqual(schema_validate.validate(_run(), benchmark_report.SCHEMA), [])

    def test_unavailable_string_is_valid_for_a_numeric_metric(self) -> None:
        run = _run()
        run["metrics"]["elapsed_seconds"] = "unavailable"
        self.assertEqual(schema_validate.validate(run, benchmark_report.SCHEMA), [])

    def test_arbitrary_string_is_rejected_for_a_numeric_metric(self) -> None:
        run = _run()
        run["metrics"]["elapsed_seconds"] = "fast"
        self.assertTrue(schema_validate.validate(run, benchmark_report.SCHEMA))


class CompareTests(unittest.TestCase):
    def test_faster_run_with_no_quality_change_is_not_rejected(self) -> None:
        baseline = _run()
        changed = _run(**{"metrics": {**_run()["metrics"], "elapsed_seconds": 60, "tool_calls": 10}})
        result = benchmark_report.compare(baseline, changed)
        self.assertEqual(result["quality_regressions"], [])
        self.assertIn("no quality regression", result["verdict"])
        self.assertEqual(result["metric_deltas"]["elapsed_seconds"]["delta"], -60)

    def test_lower_ac_coverage_is_a_rejected_regression_even_if_faster(self) -> None:
        baseline = _run()
        changed = _run(
            quality={"ac_coverage": 0.5, "regressions_found": 0, "unresolved_blockers": 0, "repeatable": True},
            metrics={**_run()["metrics"], "elapsed_seconds": 10},
        )
        result = benchmark_report.compare(baseline, changed)
        self.assertTrue(result["quality_regressions"])
        self.assertTrue(result["verdict"].startswith("REJECTED"))

    def test_more_unresolved_blockers_is_a_regression(self) -> None:
        baseline = _run()
        changed = _run(quality={"ac_coverage": 1.0, "regressions_found": 0, "unresolved_blockers": 2, "repeatable": True})
        result = benchmark_report.compare(baseline, changed)
        self.assertTrue(any("unresolved_blockers" in r for r in result["quality_regressions"]))

    def test_repeatable_going_false_is_a_regression(self) -> None:
        baseline = _run()
        changed = _run(quality={"ac_coverage": 1.0, "regressions_found": 0, "unresolved_blockers": 0, "repeatable": False})
        result = benchmark_report.compare(baseline, changed)
        self.assertTrue(any("repeatable" in r for r in result["quality_regressions"]))

    def test_unavailable_metric_never_fabricates_a_delta(self) -> None:
        baseline = _run()
        changed = _run()
        result = benchmark_report.compare(baseline, changed)
        self.assertEqual(result["metric_deltas"]["input_tokens"], "unavailable")

    def test_mismatched_revision_raises(self) -> None:
        baseline = _run(revision="fp-1")
        changed = _run(revision="fp-2")
        with self.assertRaises(ValueError):
            benchmark_report.compare(baseline, changed)

    def test_mismatched_fixture_raises(self) -> None:
        baseline = _run(fixture_id="single-file-bug")
        changed = _run(fixture_id="multi-file-feature")
        with self.assertRaises(ValueError):
            benchmark_report.compare(baseline, changed)

    def test_format_report_handles_unavailable_and_numeric(self) -> None:
        result = benchmark_report.compare(_run(), _run())
        text = benchmark_report.format_report(result)
        self.assertIn("unavailable", text)
        self.assertIn("no quality regression", text)


if __name__ == "__main__":
    unittest.main()
