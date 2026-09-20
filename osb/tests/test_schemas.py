"""Unit tests for osb/scripts/schema_validate.py against the real osb/schemas/*.json
contracts (P0-C 1.1/1.3)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"
sys.path.insert(0, str(SCRIPTS_DIR))
import schema_validate  # noqa: E402

TASK_STATE_SCHEMA = json.loads((SCHEMAS_DIR / "task-state.schema.json").read_text())
ROLE_RESULT_SCHEMA = json.loads((SCHEMAS_DIR / "role-result.schema.json").read_text())


def _valid_task_state() -> dict:
    return {
        "task_id": "OSB-2026-0919-001",
        "goal": "Add optimistic locking to CustomerRepository",
        "phase": "review",
        "architecture_checkpoint": "CP1",
        "acceptance": {"AC1": "existing public API remains unchanged"},
        "units": {"U1": {"status": "complete", "files": ["a.cs"], "checkpoint": "CP2"}},
        "review": {"status": "findings", "scope": "delta", "open": ["F2"], "resolved": ["F1"]},
        "qa": {"status": "pending", "failed": []},
        "knowledge_watermark": "CP2",
        "quality": {
            "unresolved_context_requests": [],
            "required_ac_ids": ["AC1"],
            "task_base_revision": "base-1",
            "current_patch_fingerprint": "fp-1",
            "final_review_fingerprint": None,
            "final_qa_fingerprint": None,
            "unverified_ac_ids": ["AC1"],
        },
    }


class TaskStateSchemaTests(unittest.TestCase):
    def test_valid_instance_has_no_errors(self) -> None:
        errors = schema_validate.validate(_valid_task_state(), TASK_STATE_SCHEMA)
        self.assertEqual(errors, [])

    def test_missing_quality_fingerprint_field_is_rejected(self) -> None:
        instance = _valid_task_state()
        del instance["quality"]["current_patch_fingerprint"]
        errors = schema_validate.validate(instance, TASK_STATE_SCHEMA)
        self.assertTrue(any("current_patch_fingerprint" in e for e in errors))

    def test_unknown_phase_is_rejected(self) -> None:
        instance = _valid_task_state()
        instance["phase"] = "not-a-real-phase"
        errors = schema_validate.validate(instance, TASK_STATE_SCHEMA)
        self.assertTrue(errors)

    def test_malformed_ac_id_key_is_rejected(self) -> None:
        instance = _valid_task_state()
        instance["acceptance"] = {"not-an-ac-id": "text"}
        errors = schema_validate.validate(instance, TASK_STATE_SCHEMA)
        self.assertTrue(errors)


class RoleResultSchemaTests(unittest.TestCase):
    def test_implementer_done_result_matches_exactly_one_branch(self) -> None:
        instance = {
            "status": "done",
            "changed": ["src/a.cs"],
            "verify": [{"command": "dotnet test", "result": "pass"}],
            "knowledge": [],
        }
        errors = schema_validate.validate(instance, ROLE_RESULT_SCHEMA)
        self.assertEqual(errors, [])

    def test_reviewer_needs_evidence_with_scope_is_unambiguous(self) -> None:
        instance = {
            "status": "needs-evidence",
            "scope": "delta",
            "context_request": {"question": "does X have other callers?"},
        }
        errors = schema_validate.validate(instance, ROLE_RESULT_SCHEMA)
        self.assertEqual(errors, [])

    def test_qa_pass_result_with_evidence_map(self) -> None:
        instance = {
            "status": "pass",
            "revision": "fp-8a3c1e",
            "ac": {"AC1": {"result": "pass", "evidence": "api-compatibility-test: pass"}},
        }
        errors = schema_validate.validate(instance, ROLE_RESULT_SCHEMA)
        self.assertEqual(errors, [])

    def test_qa_result_cannot_encode_not_run_as_pass(self) -> None:
        # The schema permits 'not-run' as its own result value; a fabricated "pass" for an
        # unexecuted check is a semantic error verify_task.py must catch, not a schema
        # violation — this test documents that the enum keeps the values distinct.
        instance = {
            "status": "pass",
            "revision": "fp-1",
            "ac": {"AC1": {"result": "not-run", "evidence": "environment unavailable"}},
        }
        errors = schema_validate.validate(instance, ROLE_RESULT_SCHEMA)
        self.assertEqual(errors, [])
        self.assertNotEqual(instance["ac"]["AC1"]["result"], "pass")

    def test_completely_malformed_result_matches_nothing(self) -> None:
        instance = {"status": "banana"}
        errors = schema_validate.validate(instance, ROLE_RESULT_SCHEMA)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
