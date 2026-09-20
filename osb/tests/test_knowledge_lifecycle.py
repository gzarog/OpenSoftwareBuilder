"""Tests for provenance-aware knowledge dedup/supersession (P1-E, Phase 5)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import knowledge_lifecycle  # noqa: E402


class NormalizeTests(unittest.TestCase):
    def test_fills_in_defaults(self) -> None:
        entry = knowledge_lifecycle.normalize({"type": "gotcha", "summary": "x may be null"})
        self.assertEqual(entry["lifecycle_status"], "provisional")
        self.assertIsNone(entry["repository_id"])
        self.assertIsNone(entry["superseded_by"])
        self.assertTrue(entry["id"])

    def test_assign_id_is_deterministic(self) -> None:
        entry = {"repository_id": "payments", "source_path": "a.py", "summary": "x", "type": "gotcha"}
        self.assertEqual(knowledge_lifecycle.assign_id(entry), knowledge_lifecycle.assign_id(dict(entry)))


class DedupeTests(unittest.TestCase):
    def test_exact_duplicate_by_source_identity_is_dropped(self) -> None:
        entries = [
            {"type": "gotcha", "summary": "x may be null", "repository_id": "r", "source_path": "a.py", "source_revision": "rev1"},
            {"type": "gotcha", "summary": "x may be null (retrieved again)", "repository_id": "r", "source_path": "a.py", "source_revision": "rev1"},
        ]
        kept = knowledge_lifecycle.dedupe(entries)
        self.assertEqual(len(kept), 1)

    def test_different_source_revision_is_not_deduplicated(self) -> None:
        entries = [
            {"type": "gotcha", "summary": "x", "repository_id": "r", "source_path": "a.py", "source_revision": "rev1"},
            {"type": "gotcha", "summary": "x", "repository_id": "r", "source_path": "a.py", "source_revision": "rev2"},
        ]
        kept = knowledge_lifecycle.dedupe(entries)
        self.assertEqual(len(kept), 2)

    def test_entries_without_source_identity_are_never_deduplicated_away(self) -> None:
        entries = [
            {"type": "decision", "summary": "use RowVersion"},
            {"type": "decision", "summary": "use RowVersion"},
        ]
        kept = knowledge_lifecycle.dedupe(entries)
        self.assertEqual(len(kept), 2, "entries with no source_path/revision can't be confidently deduped")


class SupersedeStaleTests(unittest.TestCase):
    def test_stale_entry_is_marked_superseded_not_deleted(self) -> None:
        existing = [
            {
                "id": "e1",
                "type": "gotcha",
                "summary": "legacy rows have null RowVersion",
                "repository_id": "r",
                "source_path": "CustomerRepository.cs",
                "source_revision": "rev1",
                "lifecycle_status": "verified",
            }
        ]
        updated = knowledge_lifecycle.supersede_stale(existing, {"CustomerRepository.cs": "rev2"})

        original = next(e for e in updated if e["id"] == "e1")
        self.assertEqual(original["lifecycle_status"], "superseded")
        self.assertIsNotNone(original["superseded_by"])
        self.assertIn(original, updated, "original entry must still be present (audit history), not deleted")

        replacement = next(e for e in updated if e["id"] == original["superseded_by"])
        self.assertEqual(replacement["lifecycle_status"], "provisional")
        self.assertEqual(replacement["source_revision"], "rev2")
        self.assertNotEqual(replacement["lifecycle_status"], "verified", "a stale entry is never promoted straight to verified")

    def test_unaffected_entry_untouched_when_no_current_revision_known(self) -> None:
        existing = [
            {
                "id": "e1", "type": "gotcha", "summary": "x", "repository_id": "r",
                "source_path": "a.py", "source_revision": "rev1", "lifecycle_status": "verified",
            }
        ]
        updated = knowledge_lifecycle.supersede_stale(existing, {})
        self.assertEqual(updated[0]["lifecycle_status"], "verified")

    def test_matching_revision_is_not_superseded(self) -> None:
        existing = [
            {
                "id": "e1", "type": "gotcha", "summary": "x", "repository_id": "r",
                "source_path": "a.py", "source_revision": "rev1", "lifecycle_status": "verified",
            }
        ]
        updated = knowledge_lifecycle.supersede_stale(existing, {"a.py": "rev1"})
        self.assertEqual(updated[0]["lifecycle_status"], "verified")

    def test_already_superseded_entry_is_not_touched_again(self) -> None:
        existing = [
            {
                "id": "e1", "type": "gotcha", "summary": "x", "repository_id": "r",
                "source_path": "a.py", "source_revision": "rev1",
                "lifecycle_status": "superseded", "superseded_by": "e0",
            }
        ]
        updated = knowledge_lifecycle.supersede_stale(existing, {"a.py": "rev2"})
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["superseded_by"], "e0")


class ValidateEventsTests(unittest.TestCase):
    def test_valid_events_pass(self) -> None:
        errors = knowledge_lifecycle.validate_events(
            [{"type": "gotcha", "summary": "x", "lifecycle_status": "provisional"}]
        )
        self.assertEqual(errors, [])

    def test_invalid_lifecycle_status_is_rejected(self) -> None:
        errors = knowledge_lifecycle.validate_events(
            [{"id": "e1", "type": "gotcha", "summary": "x", "lifecycle_status": "definitely-true"}]
        )
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
