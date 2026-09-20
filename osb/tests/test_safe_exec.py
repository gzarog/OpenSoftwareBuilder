"""Tests for the shared safe-subprocess/path helper (Phase 0, Next Improvements plan)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import safe_exec  # noqa: E402


class ResolveWithinRootTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "child").mkdir()

    def test_relative_path_inside_root_resolves(self) -> None:
        resolved = safe_exec.resolve_within_root(self.root, "child")
        self.assertEqual(resolved, (self.root / "child").resolve())

    def test_dotdot_escape_is_rejected(self) -> None:
        with self.assertRaises(safe_exec.PathEscapesRootError):
            safe_exec.resolve_within_root(self.root, "../outside")

    def test_absolute_path_outside_root_is_rejected(self) -> None:
        with self.assertRaises(safe_exec.PathEscapesRootError):
            safe_exec.resolve_within_root(self.root, "/etc/passwd")

    def test_symlink_escape_is_rejected(self) -> None:
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(outside, ignore_errors=True))
        link = self.root / "escape"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks not supported in this environment")
        with self.assertRaises(safe_exec.PathEscapesRootError):
            safe_exec.resolve_within_root(self.root, "escape")

    def test_is_within_root_true_and_false(self) -> None:
        self.assertTrue(safe_exec.is_within_root(self.root, "child"))
        self.assertFalse(safe_exec.is_within_root(self.root, "../outside"))


class RunBoundedTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_unauthorized_call_is_refused(self) -> None:
        with self.assertRaises(safe_exec.UnauthorizedCommandError):
            safe_exec.run_bounded([sys.executable, "-c", "print(1)"], self.root, self.root, authorized=False)

    def test_authorized_call_runs_and_captures_output(self) -> None:
        result = safe_exec.run_bounded(
            [sys.executable, "-c", "print('hello')"], self.root, self.root, authorized=True
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("hello", result.stdout)
        self.assertFalse(result.timed_out)

    def test_cwd_outside_root_is_rejected(self) -> None:
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(outside, ignore_errors=True))
        with self.assertRaises(safe_exec.PathEscapesRootError):
            safe_exec.run_bounded([sys.executable, "-c", "print(1)"], outside, self.root, authorized=True)

    def test_output_is_truncated_at_max_chars(self) -> None:
        result = safe_exec.run_bounded(
            [sys.executable, "-c", "print('x' * 1000)"],
            self.root,
            self.root,
            authorized=True,
            max_output_chars=10,
        )
        self.assertEqual(len(result.stdout), 10)
        self.assertTrue(result.stdout_truncated)

    def test_timeout_is_reported_not_raised(self) -> None:
        result = safe_exec.run_bounded(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            self.root,
            self.root,
            authorized=True,
            timeout_seconds=0.2,
        )
        self.assertTrue(result.timed_out)
        self.assertEqual(result.returncode, -1)


if __name__ == "__main__":
    unittest.main()
