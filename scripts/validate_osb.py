#!/usr/bin/env python3
"""Validate the OSB v2 repository structure and integration schemas.

This is validation tooling, not a runtime: it checks that the skill/agent files present
in this repository are structurally correct and internally consistent. It never executes
`/osb` itself.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parent.parent

ROLES = ("architect", "implementer", "reviewer", "qa")
CODEX_SANDBOX_BY_ROLE = {
    "architect": "read-only",
    "implementer": "workspace-write",
    "reviewer": "read-only",
    "qa": "read-only",
}
LEGACY_DIRS = (
    "analysis",
    "buildsystems",
    "cli",
    "cmd",
    "core",
    "executors",
    "internal",
    "profiles",
    "providers",
    "toolchains",
)
CANONICAL_REFERENCES = (
    "references/workflow.md",
    "references/roles.md",
    "references/handoff.md",
    "references/knowledge.md",
    "references/ragmonk.md",
    "references/state.md",
)

# Subagent-facing content must be self-contained: no reads of the full canonical skill or
# its shared reference files at dispatch time (token-optimization phase 2).
FORBIDDEN_SUBAGENT_SUBSTRINGS = (
    "SKILL.md",
    "osb/references/",
)

# Soft size guardrails (bytes). Guidance, not hard architecture requirements.
SKILL_MD_SIZE_GUARD = 4000
COPILOT_INSTRUCTIONS_SIZE_GUARD = 1500

errors: list[str] = []
warnings: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def warn(message: str) -> None:
    warnings.append(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def split_frontmatter(text: str) -> tuple[str, str] | None:
    """Return (frontmatter, body) if text starts with a --- frontmatter block."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    return text[4:end], text[end + 4 :]


def check_canonical_skill() -> None:
    path = ROOT / ".agents/skills/osb/SKILL.md"
    if not path.is_file():
        fail(f"missing canonical skill: {path.relative_to(ROOT)}")
        return

    text = read(path)
    fm = split_frontmatter(text)
    if fm is None:
        fail(f"{path.relative_to(ROOT)}: missing skill frontmatter (--- ... ---)")
    else:
        frontmatter, _ = fm
        if not re.search(r"^name:\s*osb\s*$", frontmatter, re.MULTILINE):
            fail(f"{path.relative_to(ROOT)}: frontmatter missing 'name: osb'")
        if not re.search(r"^description:\s*\S", frontmatter, re.MULTILINE):
            fail(f"{path.relative_to(ROOT)}: frontmatter missing non-empty 'description:'")

    for ref in CANONICAL_REFERENCES:
        if ref not in text:
            fail(f"{path.relative_to(ROOT)}: does not reference {ref}")
        ref_path = ROOT / ".agents/skills/osb" / ref
        if not ref_path.is_file():
            fail(f"missing canonical reference file: {ref_path.relative_to(ROOT)}")


def check_claude_skill() -> None:
    path = ROOT / ".claude/skills/osb/SKILL.md"
    if not path.is_file():
        fail(f"missing Claude skill: {path.relative_to(ROOT)}")
        return

    text = read(path)
    fm = split_frontmatter(text)
    if fm is None:
        fail(f"{path.relative_to(ROOT)}: missing skill frontmatter (--- ... ---)")
        return
    frontmatter, _ = fm
    if not re.search(r"^name:\s*osb\s*$", frontmatter, re.MULTILINE):
        fail(f"{path.relative_to(ROOT)}: frontmatter missing 'name: osb'")


def check_claude_agents() -> None:
    for role in ROLES:
        path = ROOT / f".claude/agents/{role}.md"
        if not path.is_file():
            fail(f"missing Claude agent definition: {path.relative_to(ROOT)}")
            continue
        text = read(path)
        fm = split_frontmatter(text)
        if fm is None:
            fail(f"{path.relative_to(ROOT)}: missing agent frontmatter (--- ... ---)")
            continue
        frontmatter, _ = fm
        if not re.search(rf"^name:\s*{role}\s*$", frontmatter, re.MULTILINE):
            fail(f"{path.relative_to(ROOT)}: frontmatter missing 'name: {role}'")


def check_codex_agents() -> None:
    for role in ROLES:
        path = ROOT / f".codex/agents/{role}.toml"
        if not path.is_file():
            fail(f"missing Codex agent definition: {path.relative_to(ROOT)}")
            continue

        raw = read(path)
        try:
            data = tomllib.loads(raw)
        except tomllib.TOMLDecodeError as exc:
            fail(f"{path.relative_to(ROOT)}: invalid TOML ({exc})")
            continue

        for required_key in ("name", "description", "developer_instructions", "sandbox_mode"):
            if required_key not in data:
                fail(f"{path.relative_to(ROOT)}: missing required key '{required_key}'")

        if "instructions" in data:
            fail(
                f"{path.relative_to(ROOT)}: uses legacy key 'instructions' "
                "(must be 'developer_instructions')"
            )

        if "model" in data:
            fail(
                f"{path.relative_to(ROOT)}: must not set 'model' "
                "(resolved dynamically from osb.yaml)"
            )

        expected_sandbox = CODEX_SANDBOX_BY_ROLE[role]
        actual_sandbox = data.get("sandbox_mode")
        if actual_sandbox is not None and actual_sandbox != expected_sandbox:
            fail(
                f"{path.relative_to(ROOT)}: sandbox_mode is '{actual_sandbox}', "
                f"expected '{expected_sandbox}' for role '{role}'"
            )


def check_copilot_agents() -> None:
    for role in ROLES:
        path = ROOT / f".github/agents/{role}.agent.md"
        if not path.is_file():
            fail(f"missing Copilot agent definition: {path.relative_to(ROOT)}")
            continue
        text = read(path)
        fm = split_frontmatter(text)
        if fm is None:
            fail(f"{path.relative_to(ROOT)}: missing agent frontmatter (--- ... ---)")
            continue
        frontmatter, _ = fm
        if not re.search(rf"^name:\s*{role}\s*$", frontmatter, re.MULTILINE):
            fail(f"{path.relative_to(ROOT)}: frontmatter missing 'name: {role}'")


def check_osb_yaml_template() -> None:
    path = ROOT / "templates/osb.yaml"
    if not path.is_file():
        fail(f"missing config template: {path.relative_to(ROOT)}")
        return
    text = read(path)
    for host in ("claude-code", "codex", "copilot"):
        if host not in text:
            fail(f"{path.relative_to(ROOT)}: missing '{host}' models block")
    for role in ROLES:
        if f"{role}:" not in text:
            fail(f"{path.relative_to(ROOT)}: missing '{role}:' model field")

    if "max_parallel_implementers" not in text:
        fail(
            f"{path.relative_to(ROOT)}: missing 'max_parallel_implementers' "
            "(execution.max_parallel_implementers must exist or default explicitly)"
        )
    if "refresh_after_knowledge_change" not in text:
        fail(
            f"{path.relative_to(ROOT)}: missing 'ragmonk.refresh_after_knowledge_change'"
        )
    if "refresh_after_checkpoint" in text:
        fail(
            f"{path.relative_to(ROOT)}: uses deprecated key 'refresh_after_checkpoint' "
            "(renamed to 'refresh_after_knowledge_change')"
        )


def check_subagents_self_contained() -> None:
    """Subagents must not read the full OSB skill or shared reference files at dispatch
    time — each role prompt should be self-contained (token-optimization phase 2)."""

    for role in ROLES:
        claude_path = ROOT / f".claude/agents/{role}.md"
        if claude_path.is_file():
            _check_no_forbidden_substrings(claude_path, read(claude_path))

        copilot_path = ROOT / f".github/agents/{role}.agent.md"
        if copilot_path.is_file():
            _check_no_forbidden_substrings(copilot_path, read(copilot_path))

        codex_path = ROOT / f".codex/agents/{role}.toml"
        if codex_path.is_file():
            raw = read(codex_path)
            try:
                data = tomllib.loads(raw)
            except tomllib.TOMLDecodeError:
                continue  # already reported by check_codex_agents
            instructions = data.get("developer_instructions", "")
            _check_no_forbidden_substrings(codex_path, instructions)


def _check_no_forbidden_substrings(path: Path, text: str) -> None:
    for substring in FORBIDDEN_SUBAGENT_SUBSTRINGS:
        if substring in text:
            fail(
                f"{path.relative_to(ROOT)}: subagent content references '{substring}' "
                "— subagents must be self-contained and not read shared OSB policy files"
            )


def check_compact_and_delta_docs() -> None:
    path = ROOT / ".agents/skills/osb/references/handoff.md"
    if not path.is_file():
        return  # already reported by check_canonical_skill
    text = read(path).lower()
    if "unit capsule" not in text:
        fail(f"{path.relative_to(ROOT)}: compact handoff rules (unit capsules) not documented")
    if "delta" not in text:
        fail(f"{path.relative_to(ROOT)}: delta-only repair loop rules not documented")


def check_size_guards() -> None:
    skill_path = ROOT / ".agents/skills/osb/SKILL.md"
    if skill_path.is_file() and skill_path.stat().st_size > SKILL_MD_SIZE_GUARD:
        warn(
            f"{skill_path.relative_to(ROOT)}: {skill_path.stat().st_size} bytes "
            f"(guardrail: <= {SKILL_MD_SIZE_GUARD})"
        )

    copilot_path = ROOT / ".github/copilot-instructions.md"
    if copilot_path.is_file() and copilot_path.stat().st_size > COPILOT_INSTRUCTIONS_SIZE_GUARD:
        warn(
            f"{copilot_path.relative_to(ROOT)}: {copilot_path.stat().st_size} bytes "
            f"(guardrail: <= {COPILOT_INSTRUCTIONS_SIZE_GUARD})"
        )


def check_legacy_dirs_absent() -> None:
    for name in LEGACY_DIRS:
        path = ROOT / name
        if path.exists():
            fail(f"legacy OSB v1 directory must not be reintroduced: {name}/")


def main() -> int:
    check_canonical_skill()
    check_claude_skill()
    check_claude_agents()
    check_codex_agents()
    check_copilot_agents()
    check_osb_yaml_template()
    check_legacy_dirs_absent()
    check_subagents_self_contained()
    check_compact_and_delta_docs()
    check_size_guards()

    if warnings:
        print(f"OSB v2 structure validation: {len(warnings)} warning(s):\n")
        for warning in warnings:
            print(f"  - {warning}")
        print()

    if errors:
        print(f"OSB v2 structure validation failed with {len(errors)} error(s):\n")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("OSB v2 structure validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
