"""Package/discovery fixture tests for Phase 0A (copy -> setup -> discovery -> resume).

These are deterministic fixture tests only — they never invoke a live coding host or
model. Host-specific native-command smoke tests are a separate, explicitly labelled layer
(see osb/docs/HOST_COMPATIBILITY.md) and are not run here.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _helpers import make_fake_workspace, run_install

CLAUDE_FILES = [
    ".claude/skills/osb/SKILL.md",
    ".claude/agents/architect.md",
    ".claude/agents/implementer.md",
    ".claude/agents/reviewer.md",
    ".claude/agents/qa.md",
]
CODEX_FILES = [
    ".agents/skills/osb/SKILL.md",
    ".codex/agents/architect.toml",
    ".codex/agents/implementer.toml",
    ".codex/agents/reviewer.toml",
    ".codex/agents/qa.toml",
]
COPILOT_FILES = [
    ".agents/skills/osb/SKILL.md",
    ".github/copilot-instructions.md",
    ".github/agents/architect.agent.md",
    ".github/agents/implementer.agent.md",
    ".github/agents/reviewer.agent.md",
    ".github/agents/qa.agent.md",
]


class InitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = make_fake_workspace(Path(self._tmp.name) / "empty-single-repo")

    def test_init_single_host_generates_only_that_hosts_files(self) -> None:
        result = run_install(self.workspace, "init", "--host", "claude")
        self.assertEqual(result.returncode, 0, result.stderr)

        for rel in CLAUDE_FILES:
            self.assertTrue((self.workspace / rel).is_file(), f"missing {rel}")
        for rel in CODEX_FILES + COPILOT_FILES:
            if rel in CLAUDE_FILES:
                continue
            self.assertFalse((self.workspace / rel).exists(), f"unexpected {rel}")

        self.assertTrue((self.workspace / "osb.yaml").is_file())
        self.assertTrue((self.workspace / ".osb/state").is_dir())
        self.assertTrue((self.workspace / ".osb/knowledge/tasks").is_dir())

    def test_init_all_hosts_generates_every_adapter(self) -> None:
        result = run_install(self.workspace, "init", "--host", "all")
        self.assertEqual(result.returncode, 0, result.stderr)
        for rel in {*CLAUDE_FILES, *CODEX_FILES, *COPILOT_FILES}:
            self.assertTrue((self.workspace / rel).is_file(), f"missing {rel}")

        native_pointer = (self.workspace / ".agents/skills/osb/SKILL.md").read_text()
        canonical = (self.workspace / "osb/SKILL.md").read_text()
        self.assertEqual(native_pointer, canonical, "native discovery pointer must reproduce osb/SKILL.md verbatim")

    def test_init_never_overwrites_existing_osb_yaml(self) -> None:
        custom = "version: 2\ncustom_marker: keep-me\n"
        (self.workspace / "osb.yaml").write_text(custom, encoding="utf-8")
        result = run_install(self.workspace, "init", "--host", "claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.workspace / "osb.yaml").read_text(), custom)

    def test_init_is_idempotent_and_preserves_knowledge(self) -> None:
        run_install(self.workspace, "init", "--host", "all")
        knowledge_file = self.workspace / ".osb/knowledge/components/widget.md"
        knowledge_file.write_text("# widget\n\ncurrent shape: durable knowledge\n", encoding="utf-8")

        manifest_before = json.loads((self.workspace / "osb/manifest.json").read_text())
        result = run_install(self.workspace, "init", "--host", "all")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_after = json.loads((self.workspace / "osb/manifest.json").read_text())

        self.assertEqual(manifest_before["generated_files"], manifest_after["generated_files"])
        self.assertEqual(knowledge_file.read_text(), "# widget\n\ncurrent shape: durable knowledge\n")

    def test_doctor_passes_after_init(self) -> None:
        run_install(self.workspace, "init", "--host", "all")
        result = run_install(self.workspace, "doctor")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_doctor_blocked_before_init(self) -> None:
        result = run_install(self.workspace, "doctor")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not initialized", result.stdout)

    def test_upgrade_dry_run_reports_without_modifying(self) -> None:
        run_install(self.workspace, "init", "--host", "claude")
        before = (self.workspace / ".claude/agents/architect.md").read_text()
        result = run_install(self.workspace, "upgrade", "--host", "claude", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        after = (self.workspace / ".claude/agents/architect.md").read_text()
        self.assertEqual(before, after)
        self.assertIn("Dry run", result.stdout)

    def test_upgrade_flags_hand_edited_generated_file_as_conflict(self) -> None:
        run_install(self.workspace, "init", "--host", "claude")
        agent_path = self.workspace / ".claude/agents/architect.md"
        agent_path.write_text(agent_path.read_text() + "\nHAND EDITED\n", encoding="utf-8")

        result = run_install(self.workspace, "upgrade", "--host", "claude")
        self.assertIn("conflict", result.stdout)
        self.assertIn("HAND EDITED", agent_path.read_text(), "unforced upgrade must not overwrite a modified generated file")

        result = run_install(self.workspace, "upgrade", "--host", "claude", "--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("HAND EDITED", agent_path.read_text(), "--force must overwrite the conflicting file")


class ExistingProjectFixtureTests(unittest.TestCase):
    """Simulates the 'existing single-repo project' fixture: a project that already has
    its own osb.yaml and non-OSB files before OSB is introduced."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = make_fake_workspace(
            Path(self._tmp.name) / "existing-single-repo",
            existing_files={
                "src/app.py": "print('existing project file')\n",
                "README.md": "# Existing project\n",
            },
        )

    def test_init_does_not_touch_unrelated_project_files(self) -> None:
        result = run_install(self.workspace, "init", "--host", "claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.workspace / "src/app.py").read_text(), "print('existing project file')\n")
        self.assertEqual((self.workspace / "README.md").read_text(), "# Existing project\n")


class MultiRepoFixtureTests(unittest.TestCase):
    """Simulates the 'multi-repo root' fixture (P0-A 0A.3 / P0-A Phase 3): the osb/
    package installs cleanly at a root whose children are independent Git repositories,
    and the workspace config validates with the expected dependency order."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = make_fake_workspace(Path(self._tmp.name) / "multi-repo-root")

        for rel in ("shared-contracts", "services/identity-api", "services/payment-api"):
            path = self.workspace / rel
            path.mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=path, check=True, capture_output=True)

        (self.workspace / "osb.yaml").write_text(
            "version: 2\n"
            "workspace:\n"
            "  mode: multi-repo\n"
            "  root: .\n"
            "  repositories:\n"
            "    - id: contracts\n"
            "      path: shared-contracts\n"
            "    - id: identity\n"
            "      path: services/identity-api\n"
            "      depends_on: [contracts]\n"
            "    - id: payments\n"
            "      path: services/payment-api\n"
            "      depends_on: [contracts, identity]\n",
            encoding="utf-8",
        )

    def test_init_succeeds_at_a_multi_repo_root_without_touching_child_repos(self) -> None:
        result = run_install(self.workspace, "init", "--host", "claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        for rel in CLAUDE_FILES:
            self.assertTrue((self.workspace / rel).is_file())
        # osb.yaml must be preserved exactly (it already existed with the workspace block).
        self.assertIn("workspace:", (self.workspace / "osb.yaml").read_text())

    def test_workspace_validator_reports_correct_dispatch_order(self) -> None:
        script = self.workspace / "osb/scripts/workspace_validate.py"
        result = subprocess.run(
            [sys.executable, str(script), "osb.yaml", "--workspace-root", "."],
            cwd=self.workspace,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("contracts -> identity -> payments", result.stdout)


if __name__ == "__main__":
    unittest.main()
