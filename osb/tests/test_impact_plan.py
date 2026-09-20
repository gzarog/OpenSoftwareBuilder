"""Tests for task-specific impact analysis and test selection (Next Improvements, Phase 2)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import impact_plan  # noqa: E402
import schema_validate  # noqa: E402


def _write_csproj(path: Path, *, project_refs: list[str] | None = None, package_refs: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    refs = "".join(f'<ProjectReference Include="{r}" />' for r in project_refs or [])
    pkgs = "".join(f'<PackageReference Include="{r}" Version="1.0.0" />' for r in package_refs or [])
    path.write_text(f"<Project><ItemGroup>{refs}{pkgs}</ItemGroup></Project>", encoding="utf-8")


class ReferenceGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)

    def test_graph_includes_all_projects_and_forward_edges(self) -> None:
        _write_csproj(self.repo / "src" / "Lib" / "Lib.csproj")
        _write_csproj(self.repo / "src" / "Api" / "Api.csproj", project_refs=["../Lib/Lib.csproj"])
        graph = impact_plan.build_reference_graph(self.repo)
        self.assertIn("src/Lib/Lib.csproj", graph)
        self.assertEqual(graph["src/Api/Api.csproj"], {"src/Lib/Lib.csproj"})

    def test_external_reference_is_dropped(self) -> None:
        _write_csproj(self.repo / "src" / "Api" / "Api.csproj", project_refs=["../../../outside/Other.csproj"])
        graph = impact_plan.build_reference_graph(self.repo)
        self.assertEqual(graph["src/Api/Api.csproj"], set())


class TransitiveDependentsTests(unittest.TestCase):
    def test_finds_multi_hop_dependents(self) -> None:
        graph = {"A": {"B"}, "B": {"C"}, "C": set(), "D": {"C"}}
        dependents, truncated = impact_plan.transitive_dependents(graph, {"C"})
        self.assertEqual(dependents, {"A", "B", "D"})
        self.assertFalse(truncated)

    def test_seed_itself_excluded_from_result(self) -> None:
        graph = {"A": {"B"}, "B": set()}
        dependents, _ = impact_plan.transitive_dependents(graph, {"B"})
        self.assertNotIn("B", dependents)

    def test_truncates_at_max_nodes(self) -> None:
        graph = {f"n{i}": {f"n{i-1}"} for i in range(1, 20)}
        graph["n0"] = set()
        dependents, truncated = impact_plan.transitive_dependents(graph, {"n0"}, max_nodes=5)
        self.assertTrue(truncated)
        self.assertLessEqual(len(dependents), 5)


class IsTestProjectTests(unittest.TestCase):
    def test_name_suffix_detected(self) -> None:
        self.assertTrue(impact_plan.is_test_project("src/Payments.Tests/Payments.Tests.csproj"))
        self.assertTrue(impact_plan.is_test_project("src/Payments.Test/Payments.Test.csproj"))

    def test_directory_named_tests_detected(self) -> None:
        self.assertTrue(impact_plan.is_test_project("tests/Payments/Payments.csproj"))

    def test_ordinary_project_not_detected(self) -> None:
        self.assertFalse(impact_plan.is_test_project("src/Payments/Payments.csproj"))


class FindOwningProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)

    def test_finds_nearest_ancestor_csproj(self) -> None:
        _write_csproj(self.repo / "src" / "Api" / "Api.csproj")
        (self.repo / "src" / "Api" / "Deep" / "Nested").mkdir(parents=True)
        owner = impact_plan.find_owning_project(self.repo, "src/Api/Deep/Nested/File.cs")
        self.assertEqual(owner, "src/Api/Api.csproj")

    def test_csproj_file_itself_is_its_own_owner(self) -> None:
        owner = impact_plan.find_owning_project(self.repo, "src/Api/Api.csproj")
        self.assertEqual(owner, "src/Api/Api.csproj")

    def test_no_owner_found_returns_none(self) -> None:
        (self.repo / "loose").mkdir()
        owner = impact_plan.find_owning_project(self.repo, "loose/File.cs")
        self.assertIsNone(owner)


class AnalyzeRepoImpactTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        _write_csproj(self.repo / "src" / "Payments" / "Payments.csproj")
        _write_csproj(
            self.repo / "src" / "Api" / "Api.csproj",
            project_refs=["../Payments/Payments.csproj"],
        )
        _write_csproj(
            self.repo / "tests" / "Payments.Tests" / "Payments.Tests.csproj",
            project_refs=["../../src/Payments/Payments.csproj"],
        )

    def test_confirmed_impacts_and_test_targets(self) -> None:
        result = impact_plan.analyze_repo_impact(
            "payments", self.repo, ["src/Payments/Payments.csproj"]
        )
        paths = {i["path"] for i in result["confirmed_impacts"]}
        self.assertIn("src/Api/Api.csproj", paths)
        self.assertIn("tests/Payments.Tests/Payments.Tests.csproj", paths)
        self.assertEqual(result["test_targets"], ["tests/Payments.Tests/Payments.Tests.csproj"])
        self.assertFalse(result["truncated"])

    def test_unresolvable_file_becomes_unknown(self) -> None:
        (self.repo / "loose").mkdir()
        result = impact_plan.analyze_repo_impact("payments", self.repo, ["loose/File.cs"])
        self.assertEqual(len(result["unknowns"]), 1)
        self.assertIn("loose/File.cs", result["unknowns"][0]["question"])


class BuildImpactPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _write_csproj(self.root / "contracts" / "Contracts.csproj")
        _write_csproj(
            self.root / "payments" / "Payments.csproj",
            project_refs=["../contracts/Contracts.csproj"],
        )
        _write_csproj(
            self.root / "payments-tests" / "Payments.Tests.csproj",
            project_refs=["../payments/Payments.csproj"],
        )
        self.repositories = [
            {"id": "contracts", "path": "contracts"},
            {"id": "payments", "path": "payments"},
            {"id": "payments-tests", "path": "payments-tests"},
        ]

    def test_shared_contract_change_maps_to_dependents_and_tests(self) -> None:
        plan = impact_plan.build_impact_plan(
            "T1",
            self.repositories,
            {"contracts": ["Contracts.csproj"]},
            workspace_root=self.root,
        )
        self.assertIn("payments", plan["affected_repositories"])
        self.assertTrue(any(t["repository_id"] == "payments-tests" for t in plan["test_plan"]))
        for entry in plan["test_plan"]:
            self.assertEqual(entry["stage"], "intermediate")
            self.assertEqual(entry["status"], "proposed")

    def test_plan_validates_against_schema(self) -> None:
        plan = impact_plan.build_impact_plan(
            "T1", self.repositories, {"contracts": ["Contracts.csproj"]}, workspace_root=self.root
        )
        errors = schema_validate.validate(plan, impact_plan.IMPACT_PLAN_SCHEMA)
        self.assertEqual(errors, [])

    def test_external_evidence_is_merged_not_replaced(self) -> None:
        plan = impact_plan.build_impact_plan(
            "T1",
            self.repositories,
            {},
            workspace_root=self.root,
            external_confirmed_impacts=[{
                "repository_id": "payments", "path": "src/Handler.py", "symbol": "Handler.process",
                "kind": "caller", "evidence": "ragmonk_callers Handler.process",
            }],
            external_possible_impacts=[{
                "repository_id": "payments", "path": "src/Dynamic.py", "reason": "dynamic dispatch",
                "confidence": "possible",
            }],
            external_unknowns=[{"question": "does X have external callers?", "reason": "reflection use"}],
            external_truncated=True,
        )
        self.assertEqual(len(plan["confirmed_impacts"]), 1)
        self.assertEqual(len(plan["possible_impacts"]), 1)
        self.assertEqual(len(plan["unknowns"]), 1)
        self.assertTrue(plan["truncated"])
        self.assertIn("payments", plan["affected_repositories"])

    def test_unknown_repository_id_recorded_not_silently_dropped(self) -> None:
        plan = impact_plan.build_impact_plan(
            "T1", self.repositories, {"nonexistent": ["File.cs"]}, workspace_root=self.root
        )
        self.assertTrue(any("nonexistent" in u["question"] for u in plan["unknowns"]))

    def test_fingerprint_deterministic_and_sensitive_to_content(self) -> None:
        plan_a = impact_plan.build_impact_plan(
            "T1", self.repositories, {"contracts": ["Contracts.csproj"]}, workspace_root=self.root
        )
        plan_b = impact_plan.build_impact_plan(
            "T1", self.repositories, {"contracts": ["Contracts.csproj"]}, workspace_root=self.root
        )
        self.assertEqual(plan_a["plan_fingerprint"], plan_b["plan_fingerprint"])

        plan_c = impact_plan.build_impact_plan(
            "T1", self.repositories, {}, workspace_root=self.root
        )
        self.assertNotEqual(plan_a["plan_fingerprint"], plan_c["plan_fingerprint"])

    def test_no_possible_impact_promoted_to_confirmed(self) -> None:
        plan = impact_plan.build_impact_plan(
            "T1",
            self.repositories,
            {},
            workspace_root=self.root,
            external_possible_impacts=[{
                "repository_id": "payments", "path": "src/Dynamic.py", "reason": "dynamic dispatch",
                "confidence": "possible",
            }],
        )
        confirmed_paths = {i["path"] for i in plan["confirmed_impacts"]}
        self.assertNotIn("src/Dynamic.py", confirmed_paths)


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _write_csproj(self.root / "contracts" / "Contracts.csproj")

    def test_build_writes_plan_and_validate_accepts_it(self) -> None:
        request = {
            "task_id": "T1",
            "repositories": [{"id": "contracts", "path": "contracts"}],
            "changed_files": {"contracts": ["Contracts.csproj"]},
        }
        request_path = self.root / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")

        rc = impact_plan.main(["build", str(request_path), "--workspace-root", str(self.root)])
        self.assertEqual(rc, 0)
        out_path = self.root / ".osb" / "cache" / "impact" / "T1.json"
        self.assertTrue(out_path.exists())

        rc = impact_plan.main(["validate", str(out_path)])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
