"""Tests for deterministic repository discovery (Next Improvements, Phase 1)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import workspace_discovery  # noqa: E402


def _init_git_repo(path: Path, *, commit: bool = True) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, capture_output=True)
    if commit:
        (path / "README.md").write_text("placeholder\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-q", "-m", "init"],
            cwd=path,
            check=True,
            capture_output=True,
        )


class ScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_single_repo_workspace_root_discovered_as_one_repo(self) -> None:
        _init_git_repo(self.root)
        result = workspace_discovery.scan(self.root)
        self.assertEqual([r["path"] for r in result["repositories"]], ["."])
        self.assertFalse(result["partial"])

    def test_four_sibling_repos_discovered_without_entering_excluded_dirs(self) -> None:
        for name in ("a", "b", "c", "d"):
            _init_git_repo(self.root / name)
        (self.root / "node_modules" / "fake-pkg" / ".git").mkdir(parents=True)
        (self.root / ".venv").mkdir()

        result = workspace_discovery.scan(self.root)
        paths = sorted(r["path"] for r in result["repositories"])
        self.assertEqual(paths, ["a", "b", "c", "d"])

    def test_ordinary_subdirectory_of_root_repo_is_not_a_separate_repo(self) -> None:
        _init_git_repo(self.root)
        (self.root / "src" / "lib").mkdir(parents=True)
        result = workspace_discovery.scan(self.root)
        self.assertEqual([r["path"] for r in result["repositories"]], ["."])

    def test_git_worktree_is_discovered_as_its_own_repo(self) -> None:
        main_repo = self.root / "main-repo"
        _init_git_repo(main_repo)
        worktree_path = self.root / "main-repo-wt"
        subprocess.run(
            ["git", "worktree", "add", "-b", "wt-branch", str(worktree_path)],
            cwd=main_repo,
            check=True,
            capture_output=True,
        )
        result = workspace_discovery.scan(self.root)
        paths = sorted(r["path"] for r in result["repositories"])
        self.assertEqual(paths, ["main-repo", "main-repo-wt"])

    def test_symlink_escape_is_skipped_and_marked_partial(self) -> None:
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(outside, ignore_errors=True))
        _init_git_repo(outside)
        link = self.root / "escape"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks not supported in this environment")

        result = workspace_discovery.scan(self.root)
        self.assertEqual(result["repositories"], [])
        self.assertTrue(result["partial"])
        self.assertTrue(any(w["kind"] == "symlink-escape" for w in result["warnings"]))

    def test_depth_limit_produces_partial_scan_warning(self) -> None:
        nested = self.root / "a" / "b" / "c"
        _init_git_repo(nested)
        result = workspace_discovery.scan(self.root, max_depth=1)
        self.assertEqual(result["repositories"], [])
        self.assertTrue(result["partial"])
        self.assertTrue(any(w["kind"] == "depth-limit" for w in result["warnings"]))

    def test_nested_child_repo_boundary_not_descended_by_default(self) -> None:
        child = self.root / "vendor" / "nested-repo"
        _init_git_repo(child)
        (child / "deep" / "deeper").mkdir(parents=True)
        # a plain (non-repo) grandchild inside a discovered child repo must not itself be
        # scanned for further independent repos unless follow_nested=True.
        deep_repo = child / "deep" / "deeper" / "inner-repo"
        _init_git_repo(deep_repo)
        result = workspace_discovery.scan(self.root)
        paths = sorted(r["path"] for r in result["repositories"])
        self.assertEqual(paths, ["vendor/nested-repo"])

        result_follow = workspace_discovery.scan(self.root, follow_nested=True, max_depth=8)
        paths_follow = sorted(r["path"] for r in result_follow["repositories"])
        self.assertIn("vendor/nested-repo", paths_follow)
        self.assertIn("vendor/nested-repo/deep/deeper/inner-repo", paths_follow)


class ProposeIdsTests(unittest.TestCase):
    def test_basename_ids_assigned_by_default(self) -> None:
        repos = [{"path": "services/payments"}, {"path": "contracts"}]
        proposals = workspace_discovery.propose_ids(repos)
        ids = {p["path"]: p["id"] for p in proposals}
        self.assertEqual(ids["services/payments"], "payments")
        self.assertEqual(ids["contracts"], "contracts")

    def test_basename_collision_resolved_with_path_qualified_id(self) -> None:
        repos = [{"path": "services/api"}, {"path": "legacy/api"}]
        proposals = workspace_discovery.propose_ids(repos)
        ids = sorted(p["id"] for p in proposals)
        self.assertEqual(ids, ["legacy-api", "services-api"])

    def test_known_id_reused_for_matching_path(self) -> None:
        repos = [{"path": "services/payments-api"}]
        proposals = workspace_discovery.propose_ids(repos, known={"payments": "services/payments-api"})
        self.assertEqual(proposals[0]["id"], "payments")

    def test_ids_are_deterministic_across_runs(self) -> None:
        repos = [{"path": "b/api"}, {"path": "a/api"}]
        first = [p["id"] for p in workspace_discovery.propose_ids(repos)]
        second = [p["id"] for p in workspace_discovery.propose_ids(repos)]
        self.assertEqual(first, second)


class DetectRenamesTests(unittest.TestCase):
    def test_matching_root_commit_at_new_path_flagged_as_rename(self) -> None:
        prior = [{"id": "payments", "path": "services/payments-old", "root_commit": "abc123"}]
        current = [{"id": "payments-new", "path": "services/payments-new", "root_commit": "abc123"}]
        updated, warnings = workspace_discovery.detect_renames(current, prior)
        self.assertEqual(updated[0]["id"], "payments")
        self.assertEqual(updated[0]["source"], "renamed")
        self.assertEqual(updated[0]["renamed_from"], "services/payments-old")
        self.assertTrue(any(w["kind"] == "rename-candidate" for w in warnings))

    def test_unrelated_new_repo_is_not_flagged_as_rename(self) -> None:
        prior = [{"id": "payments", "path": "services/payments", "root_commit": "abc123"}]
        current = [
            {"id": "payments", "path": "services/payments", "root_commit": "abc123"},
            {"id": "brand-new", "path": "services/brand-new", "root_commit": "def456"},
        ]
        updated, warnings = workspace_discovery.detect_renames(current, prior)
        self.assertEqual(warnings, [])
        new_entry = next(r for r in updated if r["path"] == "services/brand-new")
        self.assertNotIn("source", new_entry)


class EdgesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_project_reference_becomes_confirmed_edge(self) -> None:
        contracts = self.root / "contracts"
        payments = self.root / "payments"
        contracts.mkdir()
        (payments / "src").mkdir(parents=True)
        (payments / "src" / "Payments.csproj").write_text(
            '<Project><ItemGroup><ProjectReference Include="..\\..\\contracts\\Contracts.csproj" /></ItemGroup></Project>',
            encoding="utf-8",
        )
        repositories = [{"id": "contracts", "path": "contracts"}, {"id": "payments", "path": "payments"}]
        confirmed, possible = workspace_discovery.build_edges(self.root, repositories)
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(confirmed[0]["from"], "payments")
        self.assertEqual(confirmed[0]["to"], "contracts")
        self.assertEqual(confirmed[0]["source"], "project-reference")
        self.assertEqual(possible, [])

    def test_package_reference_matching_repo_id_becomes_possible_edge_only(self) -> None:
        contracts = self.root / "contracts"
        payments = self.root / "payments"
        contracts.mkdir()
        (payments / "src").mkdir(parents=True)
        (payments / "src" / "Payments.csproj").write_text(
            '<Project><ItemGroup><PackageReference Include="contracts" Version="1.0.0" /></ItemGroup></Project>',
            encoding="utf-8",
        )
        repositories = [{"id": "contracts", "path": "contracts"}, {"id": "payments", "path": "payments"}]
        confirmed, possible = workspace_discovery.build_edges(self.root, repositories)
        self.assertEqual(confirmed, [])
        self.assertEqual(len(possible), 1)
        self.assertEqual(possible[0]["from"], "payments")
        self.assertEqual(possible[0]["to"], "contracts")


class BuildManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _init_git_repo(self.root / "contracts")
        _init_git_repo(self.root / "payments")

    def test_manifest_never_writes_any_file(self) -> None:
        before = list(self.root.rglob("*"))
        workspace_discovery.build_manifest(self.root, discovery_enabled=True)
        after = list(self.root.rglob("*"))
        self.assertEqual(sorted(str(p) for p in before), sorted(str(p) for p in after))

    def test_explicit_repository_included_even_with_discovery_disabled(self) -> None:
        manifest = workspace_discovery.build_manifest(
            self.root,
            discovery_enabled=False,
            explicit_repositories=[{"id": "contracts", "path": "contracts"}],
        )
        self.assertEqual([r["id"] for r in manifest["repositories"]], ["contracts"])
        self.assertEqual(manifest["repositories"][0]["source"], "configured")

    def test_explicit_repository_outside_root_is_rejected(self) -> None:
        manifest = workspace_discovery.build_manifest(
            self.root,
            discovery_enabled=False,
            explicit_repositories=[{"id": "evil", "path": "../outside"}],
        )
        self.assertEqual(manifest["repositories"], [])
        self.assertTrue(any(w["kind"] == "outside-root-rejected" for w in manifest.get("warnings", [])))

    def test_explicit_depends_on_becomes_confirmed_edge(self) -> None:
        manifest = workspace_discovery.build_manifest(
            self.root,
            discovery_enabled=True,
            explicit_repositories=[
                {"id": "contracts", "path": "contracts"},
                {"id": "payments", "path": "payments", "depends_on": ["contracts"]},
            ],
        )
        explicit_edges = [e for e in manifest["confirmed_edges"] if e["source"] == "explicit"]
        self.assertEqual(len(explicit_edges), 1)
        self.assertEqual(explicit_edges[0], {
            "from": "payments", "to": "contracts", "source": "explicit",
            "evidence": "osb.yaml workspace.repositories[].depends_on",
        })

    def test_fingerprint_changes_when_a_repository_is_added(self) -> None:
        manifest_before = workspace_discovery.build_manifest(self.root, discovery_enabled=True)
        _init_git_repo(self.root / "new-service")
        manifest_after = workspace_discovery.build_manifest(self.root, discovery_enabled=True)
        self.assertNotEqual(manifest_before["manifest_fingerprint"], manifest_after["manifest_fingerprint"])

    def test_fingerprint_is_stable_across_repeated_builds(self) -> None:
        first = workspace_discovery.build_manifest(self.root, discovery_enabled=True)
        second = workspace_discovery.build_manifest(self.root, discovery_enabled=True)
        self.assertEqual(first["manifest_fingerprint"], second["manifest_fingerprint"])

    def test_manifest_validates_against_schema(self) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        import schema_validate

        manifest = workspace_discovery.build_manifest(self.root, discovery_enabled=True)
        errors = schema_validate.validate(manifest, workspace_discovery.MANIFEST_SCHEMA)
        self.assertEqual(errors, [])


class ConfigLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_missing_osb_yaml_disables_discovery_by_default(self) -> None:
        enabled, max_depth, exclude, repos = workspace_discovery.load_osb_config(self.root / "osb.yaml")
        self.assertFalse(enabled)
        self.assertEqual(repos, [])

    def test_workspace_discovery_block_enables_scanning(self) -> None:
        osb_yaml = self.root / "osb.yaml"
        osb_yaml.write_text(
            "version: 2\nworkspace:\n  discovery:\n    enabled: true\n    max_depth: 2\n",
            encoding="utf-8",
        )
        enabled, max_depth, exclude, repos = workspace_discovery.load_osb_config(osb_yaml)
        self.assertTrue(enabled)
        self.assertEqual(max_depth, 2)


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        _init_git_repo(self.root / "contracts")

    def test_confirm_without_yes_does_not_write_manifest(self) -> None:
        rc = workspace_discovery.main(["confirm", str(self.root), "--force-enable"])
        self.assertEqual(rc, 1)
        self.assertFalse((self.root / ".osb" / "cache" / "workspace-manifest.json").exists())

    def test_confirm_with_yes_writes_manifest(self) -> None:
        rc = workspace_discovery.main(["confirm", str(self.root), "--force-enable", "--yes"])
        self.assertEqual(rc, 0)
        manifest_path = self.root / ".osb" / "cache" / "workspace-manifest.json"
        self.assertTrue(manifest_path.exists())

    def test_validate_reports_moved_repository(self) -> None:
        out_path = self.root / ".osb" / "cache" / "workspace-manifest.json"
        rc = workspace_discovery.main(["confirm", str(self.root), "--force-enable", "--yes", "--out", str(out_path)])
        self.assertEqual(rc, 0)
        (self.root / "contracts").rename(self.root / "contracts-moved")
        rc = workspace_discovery.main(["validate", str(out_path), "--workspace-root", str(self.root)])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
