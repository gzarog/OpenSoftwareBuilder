"""Tests for optional Git worktree isolation (P1-D, Phase 4)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import worktree_guard  # noqa: E402


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "shared.py").write_text("value = 1\n", encoding="utf-8")
    _git(repo, "add", "shared.py")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "branch", "-M", "main")


class WorktreeGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name) / "repo"
        _init_repo(self.repo)

    def test_create_unit_worktree_creates_branch_and_path(self) -> None:
        path = worktree_guard.create_unit_worktree(self.repo, "U1")
        self.assertTrue(path.is_dir())
        self.assertTrue((path / "shared.py").is_file())
        branches = _git(self.repo, "branch", "--list", "osb/unit/U1").stdout
        self.assertIn("osb/unit/U1", branches)

    def test_create_unit_worktree_refuses_duplicate(self) -> None:
        worktree_guard.create_unit_worktree(self.repo, "U1")
        with self.assertRaises(worktree_guard.WorktreeGuardError):
            worktree_guard.create_unit_worktree(self.repo, "U1")

    def test_list_osb_worktrees_only_reports_osb_created_ones(self) -> None:
        worktree_guard.create_unit_worktree(self.repo, "U1")
        entries = worktree_guard.list_osb_worktrees(self.repo)
        self.assertEqual(len(entries), 1)
        self.assertIn(".osb/worktrees/U1", entries[0]["path"].replace("\\", "/"))

    def test_remove_clean_worktree_succeeds(self) -> None:
        path = worktree_guard.create_unit_worktree(self.repo, "U1")
        worktree_guard.remove_unit_worktree(self.repo, "U1")
        self.assertFalse(path.exists())

    def test_remove_is_idempotent_when_already_gone(self) -> None:
        worktree_guard.remove_unit_worktree(self.repo, "never-created")  # must not raise

    def test_remove_refuses_to_discard_uncommitted_changes_without_force(self) -> None:
        path = worktree_guard.create_unit_worktree(self.repo, "U1")
        (path / "shared.py").write_text("value = 2  # uncommitted\n", encoding="utf-8")
        with self.assertRaises(worktree_guard.WorktreeGuardError):
            worktree_guard.remove_unit_worktree(self.repo, "U1")
        self.assertTrue(path.exists(), "uncommitted work must survive a refused removal")

    def test_remove_with_force_discards_uncommitted_changes(self) -> None:
        path = worktree_guard.create_unit_worktree(self.repo, "U1")
        (path / "shared.py").write_text("value = 2  # uncommitted\n", encoding="utf-8")
        worktree_guard.remove_unit_worktree(self.repo, "U1", force=True)
        self.assertFalse(path.exists())

    def test_integrate_unit_merges_cleanly_when_no_conflict(self) -> None:
        path = worktree_guard.create_unit_worktree(self.repo, "U1")
        (path / "new_file.py").write_text("addition = True\n", encoding="utf-8")
        _git(path, "add", "new_file.py")
        _git(path, "commit", "-q", "-m", "unit change")

        result = worktree_guard.integrate_unit(self.repo, "U1", "main")
        self.assertEqual(result["status"], "merged")
        self.assertTrue((self.repo / "new_file.py").is_file())

    def test_integrate_unit_reports_conflict_and_leaves_repo_clean(self) -> None:
        path = worktree_guard.create_unit_worktree(self.repo, "U1")
        (path / "shared.py").write_text("value = 999\n", encoding="utf-8")
        _git(path, "commit", "-am", "unit edits shared.py")

        # A conflicting edit lands directly on main after the worktree was branched off.
        (self.repo / "shared.py").write_text("value = 2\n", encoding="utf-8")
        _git(self.repo, "commit", "-am", "main also edits shared.py")

        result = worktree_guard.integrate_unit(self.repo, "U1", "main")
        self.assertEqual(result["status"], "conflict")
        self.assertIn("shared.py", result["files"])

        self.assertFalse((self.repo / ".git/MERGE_HEAD").exists(), "merge must be aborted, not left in progress")
        status_lines = _git(self.repo, "status", "--porcelain").stdout.splitlines()
        unmerged = [line for line in status_lines if line.startswith("U")]
        self.assertEqual(unmerged, [], "an aborted conflicting merge must leave no unmerged paths")

    def test_lock_serializes_and_times_out(self) -> None:
        lock_path = worktree_guard.acquire_lock(self.repo, "shared-schema", timeout_seconds=0.2)
        self.assertTrue(lock_path.is_file())
        with self.assertRaises(worktree_guard.WorktreeGuardError):
            worktree_guard.acquire_lock(self.repo, "shared-schema", timeout_seconds=0.2)
        worktree_guard.release_lock(lock_path)
        # Now that it's released, acquiring again must succeed immediately.
        lock_path2 = worktree_guard.acquire_lock(self.repo, "shared-schema", timeout_seconds=0.2)
        worktree_guard.release_lock(lock_path2)


if __name__ == "__main__":
    unittest.main()
