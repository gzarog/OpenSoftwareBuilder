"""Unit tests for the deterministic host-template renderer (osb/scripts/generate_hosts.py)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import generate_hosts  # noqa: E402


class SplitFrontmatterTests(unittest.TestCase):
    def test_splits_valid_frontmatter(self) -> None:
        text = "---\nname: architect\ndescription: does things\n---\nBody line 1\nBody line 2\n"
        fields, body = generate_hosts.split_frontmatter(text)
        self.assertEqual(fields["name"], "architect")
        self.assertEqual(fields["description"], "does things")
        self.assertEqual(body, "Body line 1\nBody line 2\n")

    def test_missing_frontmatter_raises(self) -> None:
        with self.assertRaises(generate_hosts.GenerationError):
            generate_hosts.split_frontmatter("no frontmatter here\n")

    def test_unterminated_frontmatter_raises(self) -> None:
        with self.assertRaises(generate_hosts.GenerationError):
            generate_hosts.split_frontmatter("---\nname: x\n")


class MarkdownToPlainTests(unittest.TestCase):
    def test_strips_bold_markers(self) -> None:
        self.assertEqual(generate_hosts.markdown_to_plain("**Allowed:** do the thing"), "Allowed: do the thing")

    def test_strips_code_fences_but_keeps_content(self) -> None:
        body = "Return exactly this structure:\n\n```yaml\nstatus: done\n```\n"
        plain = generate_hosts.markdown_to_plain(body)
        self.assertNotIn("```", plain)
        self.assertIn("status: done", plain)

    def test_strips_any_fence_language(self) -> None:
        body = "```markdown\n## Goal\n```\n"
        plain = generate_hosts.markdown_to_plain(body)
        self.assertNotIn("```", plain)
        self.assertIn("## Goal", plain)


class GenerateForRealPackageTests(unittest.TestCase):
    """Exercises generation against this repo's own canonical osb/agents/*.md sources
    (read-only — writes land in a temp workspace, never the real repo)."""

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        from _helpers import make_fake_workspace  # local import: adjusts sys.path via discovery

        self.workspace = make_fake_workspace(Path(self._tmp.name) / "ws")

    def test_generate_claude_reproduces_canonical_body(self) -> None:
        generate_hosts.generate(self.workspace, ["claude"], "9.9.9")
        for role in generate_hosts.ROLES:
            canonical = (self.workspace / "osb/agents" / f"{role}.md").read_text()
            generated = (self.workspace / ".claude/agents" / f"{role}.md").read_text()
            self.assertEqual(canonical, generated)

    def test_generate_codex_produces_valid_toml_without_fences(self) -> None:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]

        generate_hosts.generate(self.workspace, ["codex"], "9.9.9")
        for role in generate_hosts.ROLES:
            path = self.workspace / ".codex/agents" / f"{role}.toml"
            data = tomllib.loads(path.read_text())
            self.assertEqual(data["sandbox_mode"], generate_hosts.CODEX_SANDBOX_BY_ROLE[role])
            self.assertNotIn("```", data["developer_instructions"])
            self.assertNotIn("model", data)

    def test_generate_unknown_host_raises(self) -> None:
        with self.assertRaises(generate_hosts.GenerationError):
            generate_hosts.generate(self.workspace, ["not-a-real-host"], "9.9.9")


if __name__ == "__main__":
    unittest.main()
