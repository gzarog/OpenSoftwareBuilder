"""Tests for the minimal YAML-subset reader (osb/scripts/yaml_lite.py), including the
exact multi-repo workspace example from the P0-A plan text."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import yaml_lite  # noqa: E402

WORKSPACE_EXAMPLE = """
version: 2
workspace:
  mode: multi-repo
  root: .
  repositories:
    - id: contracts
      path: shared-contracts
    - id: identity
      path: services/identity-api
      depends_on: [contracts]
    - id: payments
      path: services/payment-api
      depends_on: [contracts, identity]
  integration_checks:
    - name: api-contracts
      command: ./scripts/check-contracts.sh
      cwd: .
"""


class YamlLiteTests(unittest.TestCase):
    def test_parses_plan_workspace_example(self) -> None:
        data = yaml_lite.parse(WORKSPACE_EXAMPLE)
        self.assertEqual(data["version"], 2)
        ws = data["workspace"]
        self.assertEqual(ws["mode"], "multi-repo")
        self.assertEqual(ws["root"], ".")
        repos = ws["repositories"]
        self.assertEqual(len(repos), 3)
        self.assertEqual(repos[0], {"id": "contracts", "path": "shared-contracts"})
        self.assertEqual(repos[1]["depends_on"], ["contracts"])
        self.assertEqual(repos[2]["depends_on"], ["contracts", "identity"])
        checks = ws["integration_checks"]
        self.assertEqual(checks[0]["name"], "api-contracts")
        self.assertEqual(checks[0]["command"], "./scripts/check-contracts.sh")

    def test_parses_scalars(self) -> None:
        data = yaml_lite.parse("a: 1\nb: 2.5\nc: true\nd: false\ne: null\nf: hello\n")
        self.assertEqual(data, {"a": 1, "b": 2.5, "c": True, "d": False, "e": None, "f": "hello"})

    def test_parses_nested_mapping(self) -> None:
        data = yaml_lite.parse("models:\n  claude-code:\n    architect: claude-opus-5\n")
        self.assertEqual(data, {"models": {"claude-code": {"architect": "claude-opus-5"}}})

    def test_parses_list_of_scalars(self) -> None:
        data = yaml_lite.parse("items:\n  - a\n  - b\n  - c\n")
        self.assertEqual(data, {"items": ["a", "b", "c"]})

    def test_ignores_comments_and_blank_lines(self) -> None:
        text = "# top comment\na: 1  # inline\n\nb: 2\n"
        data = yaml_lite.parse(text)
        self.assertEqual(data, {"a": 1, "b": 2})

    def test_extract_key_helper(self) -> None:
        ws = yaml_lite.extract_key(WORKSPACE_EXAMPLE, "workspace")
        self.assertEqual(ws["mode"], "multi-repo")
        self.assertIsNone(yaml_lite.extract_key(WORKSPACE_EXAMPLE, "not-present"))


if __name__ == "__main__":
    unittest.main()
