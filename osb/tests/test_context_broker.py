"""Tests for the evidence-aware context broker (Next Improvements, Phase 3)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import context_broker  # noqa: E402
import safe_exec  # noqa: E402
import schema_validate  # noqa: E402


class ContentFingerprintTests(unittest.TestCase):
    def test_same_content_same_fingerprint(self) -> None:
        self.assertEqual(context_broker.content_fingerprint("abc"), context_broker.content_fingerprint("abc"))

    def test_different_content_different_fingerprint(self) -> None:
        self.assertNotEqual(context_broker.content_fingerprint("abc"), context_broker.content_fingerprint("abd"))


class RenderConstraintTests(unittest.TestCase):
    def test_verified_entry_rendered_as_is(self) -> None:
        entry = {"lifecycle_status": "verified", "summary": "Contract is stable"}
        self.assertEqual(context_broker.render_constraint_from_knowledge(entry), "Contract is stable")

    def test_provisional_entry_marked_unverified(self) -> None:
        entry = {"lifecycle_status": "provisional", "summary": "May allow null RowVersion"}
        self.assertEqual(
            context_broker.render_constraint_from_knowledge(entry), "[unverified] May allow null RowVersion"
        )

    def test_superseded_entry_dropped(self) -> None:
        entry = {"lifecycle_status": "superseded", "summary": "Old claim"}
        self.assertIsNone(context_broker.render_constraint_from_knowledge(entry))


class BuildCapsuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "contracts").mkdir()
        (self.root / "contracts" / "IContract.cs").write_text("public interface IContract {}", encoding="utf-8")
        self.repositories = [{"id": "contracts", "path": "contracts"}]

    def test_capsule_includes_exact_required_ac_text(self) -> None:
        capsule, _ = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories,
            {"AC1": "exact requirement text must survive verbatim"}, [], [],
        )
        self.assertEqual(capsule["required_ac"]["AC1"], "exact requirement text must survive verbatim")

    def test_capsule_validates_against_schema(self) -> None:
        capsule, _ = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories, {}, [],
            [{"repository_id": "contracts", "source_path": "IContract.cs"}],
        )
        errors = schema_validate.validate(capsule, context_broker.CAPSULE_SCHEMA)
        self.assertEqual(errors, [])

    def test_two_capsules_for_same_unchanged_file_reuse_one_excerpt(self) -> None:
        capsule_a, store = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories, {}, [],
            [{"repository_id": "contracts", "source_path": "IContract.cs"}],
        )
        capsule_b, store = context_broker.build_capsule(
            "T1", "reviewer", self.root, self.repositories, {}, [],
            [{"repository_id": "contracts", "source_path": "IContract.cs"}],
            excerpt_store=store,
        )
        self.assertEqual(capsule_a["evidence"][0]["excerpt_ref"], capsule_b["evidence"][0]["excerpt_ref"])
        self.assertEqual(len(store), 1)

    def test_changed_file_gets_new_excerpt_identity(self) -> None:
        capsule_a, store = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories, {}, [],
            [{"repository_id": "contracts", "source_path": "IContract.cs"}],
        )
        (self.root / "contracts" / "IContract.cs").write_text("public interface IContract { void Update(); }", encoding="utf-8")
        capsule_b, store = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories, {}, [],
            [{"repository_id": "contracts", "source_path": "IContract.cs"}],
            excerpt_store=store,
        )
        self.assertNotEqual(capsule_a["evidence"][0]["excerpt_ref"], capsule_b["evidence"][0]["excerpt_ref"])
        self.assertEqual(len(store), 2)

    def test_missing_source_becomes_unresolved_question(self) -> None:
        capsule, _ = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories, {}, [],
            [{"repository_id": "contracts", "source_path": "Missing.cs"}],
        )
        self.assertEqual(capsule["evidence"], [])
        self.assertEqual(len(capsule["unresolved_questions"]), 1)

    def test_unknown_repository_becomes_unresolved_question(self) -> None:
        capsule, _ = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories, {}, [],
            [{"repository_id": "nope", "source_path": "IContract.cs"}],
        )
        self.assertTrue(any("nope" in q["question"] for q in capsule["unresolved_questions"]))

    def test_path_escaping_repo_root_is_rejected(self) -> None:
        capsule, _ = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories, {}, [],
            [{"repository_id": "contracts", "source_path": "../outside.txt"}],
        )
        self.assertEqual(capsule["evidence"], [])
        self.assertEqual(len(capsule["unresolved_questions"]), 1)

    def test_exceeding_budget_records_unresolved_question_but_keeps_ac_text(self) -> None:
        (self.root / "contracts" / "Big.cs").write_text("x" * 100, encoding="utf-8")
        capsule, _ = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories,
            {"AC1": "must not be truncated"}, [],
            [{"repository_id": "contracts", "source_path": "Big.cs"}],
            initial_budget_chars=10,
        )
        self.assertEqual(capsule["required_ac"]["AC1"], "must not be truncated")
        self.assertTrue(any("budget" in q["question"] for q in capsule["unresolved_questions"]))

    def test_max_chars_trims_stored_excerpt(self) -> None:
        (self.root / "contracts" / "Big.cs").write_text("x" * 100, encoding="utf-8")
        _capsule, store = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories, {}, [],
            [{"repository_id": "contracts", "source_path": "Big.cs", "max_chars": 10}],
        )
        stored = next(iter(store.values()))
        self.assertEqual(len(stored["content"]), 10)

    def test_capsule_fingerprint_deterministic(self) -> None:
        capsule_a, _ = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories, {"AC1": "x"}, ["c1"], [],
        )
        capsule_b, _ = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories, {"AC1": "x"}, ["c1"], [],
        )
        self.assertEqual(capsule_a["capsule_fingerprint"], capsule_b["capsule_fingerprint"])


class RefreshExcerptStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "contracts").mkdir()
        (self.root / "contracts" / "IContract.cs").write_text("v1", encoding="utf-8")
        self.repositories = [{"id": "contracts", "path": "contracts"}]

    def test_unchanged_file_stays_current(self) -> None:
        _capsule, store = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories, {}, [],
            [{"repository_id": "contracts", "source_path": "IContract.cs"}],
        )
        stale = context_broker.refresh_excerpt_store(store, self.root, self.repositories)
        self.assertEqual(stale, [])

    def test_changed_file_marked_stale(self) -> None:
        _capsule, store = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories, {}, [],
            [{"repository_id": "contracts", "source_path": "IContract.cs"}],
        )
        (self.root / "contracts" / "IContract.cs").write_text("v2", encoding="utf-8")
        stale = context_broker.refresh_excerpt_store(store, self.root, self.repositories)
        self.assertEqual(len(stale), 1)
        self.assertEqual(store[stale[0]]["status"], "stale")

    def test_deleted_file_marked_stale(self) -> None:
        _capsule, store = context_broker.build_capsule(
            "T1", "implementer", self.root, self.repositories, {}, [],
            [{"repository_id": "contracts", "source_path": "IContract.cs"}],
        )
        (self.root / "contracts" / "IContract.cs").unlink()
        stale = context_broker.refresh_excerpt_store(store, self.root, self.repositories)
        self.assertEqual(len(stale), 1)


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "contracts").mkdir()
        (self.root / "contracts" / "IContract.cs").write_text("public interface IContract {}", encoding="utf-8")

    def test_build_writes_capsule_and_excerpt_store(self) -> None:
        request = {
            "task_id": "T1",
            "role": "implementer",
            "unit_id": "U1",
            "repositories": [{"id": "contracts", "path": "contracts"}],
            "required_ac": {"AC1": "text"},
            "constraints": [],
            "evidence_requests": [{"repository_id": "contracts", "source_path": "IContract.cs"}],
        }
        request_path = self.root / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")

        rc = context_broker.main(["build", str(request_path), "--workspace-root", str(self.root)])
        self.assertEqual(rc, 0)

        capsule_path = self.root / ".osb" / "context" / "T1" / "implementer-U1.json"
        self.assertTrue(capsule_path.exists())
        self.assertTrue((self.root / ".osb" / "context" / "T1" / "excerpts.json").exists())

        rc = context_broker.main(["validate", str(capsule_path)])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
