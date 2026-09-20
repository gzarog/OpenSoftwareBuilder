"""Phase 2 classifier tests, driven by the Phase 0 baseline fixtures so classification
and the fixture repository stay in sync (osb/tests/fixtures/tasks/*.json)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "tasks"
sys.path.insert(0, str(SCRIPTS_DIR))
import classify_task  # noqa: E402


class FixtureDrivenClassificationTests(unittest.TestCase):
    def test_every_fixture_classifies_as_expected(self) -> None:
        for path in FIXTURES_DIR.glob("*.json"):
            with self.subTest(fixture=path.stem):
                data = json.loads(path.read_text(encoding="utf-8"))
                result = classify_task.classify(data["scenario"])
                self.assertEqual(result["task_profile"], data["expected_task_profile"])
                self.assertEqual(sorted(result["risk_flags"]), sorted(data.get("expected_risk_flags", [])))


class ClassifyTaskUnitTests(unittest.TestCase):
    def test_small_fix_uses_one_implementer_profile(self) -> None:
        result = classify_task.classify(
            {"files_estimate": 1, "repositories": 1, "acceptance_criteria_count": 1}
        )
        self.assertEqual(result["task_profile"], "small-fix")
        self.assertEqual(result["risk_flags"], [])

    def test_uncertain_defaults_to_feature_never_small_fix(self) -> None:
        result = classify_task.classify({"uncertain": True})
        self.assertEqual(result["task_profile"], "feature")

    def test_missing_signals_default_to_feature(self) -> None:
        result = classify_task.classify({})
        self.assertEqual(result["task_profile"], "feature")

    def test_security_sensitive_adds_high_risk_flag_without_forcing_cross_service(self) -> None:
        result = classify_task.classify(
            {"files_estimate": 2, "repositories": 1, "security_sensitive": True}
        )
        self.assertEqual(result["task_profile"], "feature")
        self.assertEqual(result["risk_flags"], ["high-risk"])

    def test_multi_repo_is_cross_service_even_with_small_file_count(self) -> None:
        result = classify_task.classify({"files_estimate": 1, "repositories": 2})
        self.assertEqual(result["task_profile"], "cross-service")

    def test_reclassify_never_narrows_an_existing_broader_profile(self) -> None:
        previous = {"task_profile": "cross-service", "risk_flags": []}
        narrower_signal = {"files_estimate": 1, "repositories": 1, "acceptance_criteria_count": 1}
        result = classify_task.reclassify_on_new_evidence(previous, narrower_signal)
        self.assertEqual(result["task_profile"], "cross-service")

    def test_reclassify_widens_and_unions_risk_flags(self) -> None:
        previous = {"task_profile": "small-fix", "risk_flags": []}
        wider_signal = {"files_estimate": 1, "repositories": 2, "security_sensitive": True}
        result = classify_task.reclassify_on_new_evidence(previous, wider_signal)
        self.assertEqual(result["task_profile"], "cross-service")
        self.assertEqual(result["risk_flags"], ["high-risk"])

    def test_all_returned_profiles_are_valid(self) -> None:
        scenarios = [
            {"files_estimate": 1, "repositories": 1},
            {"files_estimate": 5, "repositories": 1},
            {"files_estimate": 1, "repositories": 2},
            {"uncertain": True},
        ]
        for scenario in scenarios:
            result = classify_task.classify(scenario)
            self.assertIn(result["task_profile"], classify_task.VALID_PROFILES)


if __name__ == "__main__":
    unittest.main()
