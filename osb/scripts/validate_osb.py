#!/usr/bin/env python3
"""Validate the portable OSB package structure and integration schemas.

This is validation tooling, not a runtime: it checks that the canonical package under
`osb/` and the generated, host-native adapters at the workspace root are structurally
correct, internally consistent, and free of drift. It never executes `/osb` itself, and
never contacts a network. See `osb/scripts/verify_task.py` for the (separate) executable
completion-gate verifier that validates a specific task's state, not the package.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib  # type: ignore[no-redef]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schema_validate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
OSB_DIR = ROOT / "osb"

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
# These lived at the workspace root before the portable-package migration (P0-I). Their
# framework content must now live exclusively under osb/.
LEGACY_TOP_LEVEL_DIRS = ("docs", "scripts", "templates")

CANONICAL_REFERENCES = (
    "references/workflow.md",
    "references/roles.md",
    "references/handoff.md",
    "references/knowledge.md",
    "references/ragmonk.md",
    "references/state.md",
    "references/quality.md",
)

# Phrasing that implied a delta/repaired-diff review pass was sufficient by itself,
# without a mandatory final combined-change review. Must not reappear anywhere.
FORBIDDEN_STALE_REVIEW_PHRASES = (
    "the repaired diff only, not the whole task, once repaired",
    "runs again on the repaired diff only. repeat until",
)

# Files (relative to OSB_DIR) that must document the quality-guardrails invariants.
QUALITY_CANONICAL_FILES = (
    "references/workflow.md",
    "references/roles.md",
    "references/handoff.md",
    "references/quality.md",
)
FINGERPRINT_FILES = (
    "references/state.md",
    "references/workflow.md",
    "references/quality.md",
)

# Subagent-facing content must be self-contained: no reads of the full canonical skill or
# its shared reference files at dispatch time (token-optimization phase 2).
FORBIDDEN_SUBAGENT_SUBSTRINGS = (
    "SKILL.md",
    "osb/references/",
)

# Expected package source files under osb/ (package-integrity check, P0-I 0A.3).
EXPECTED_PACKAGE_FILES = (
    "SKILL.md",
    "manifest.json",
    "install.sh",
    "install.ps1",
    *(f"agents/{role}.md" for role in ROLES),
    *(f"references/{name}" for name in (
        "workflow.md", "roles.md", "handoff.md", "knowledge.md",
        "ragmonk.md", "state.md", "quality.md",
    )),
    "hosts/claude/skill.md.tmpl",
    "hosts/claude/agent.md.tmpl",
    "hosts/codex/agent.toml.tmpl",
    "hosts/copilot/agent.md.tmpl",
    "hosts/copilot/copilot-instructions.md.tmpl",
    "scripts/install.py",
    "scripts/generate_hosts.py",
    "scripts/validate_osb.py",
    "scripts/schema_validate.py",
    "scripts/verify_task.py",
    "scripts/classify_task.py",
    "scripts/yaml_lite.py",
    "scripts/workspace_validate.py",
    "scripts/worktree_guard.py",
    "scripts/knowledge_lifecycle.py",
    "schemas/knowledge-event.schema.json",
    "scripts/benchmark_report.py",
    "schemas/run-metrics.schema.json",
    "docs/BENCHMARKING.md",
    "scripts/host_preflight.py",
    "docs/HOST_COMPATIBILITY.md",
    "docs/UPGRADE.md",
    "schemas/task-state.schema.json",
    "schemas/role-result.schema.json",
    "templates/osb.yaml",
    "templates/state/task.json",
    "templates/knowledge/task.md",
    "templates/knowledge/component.md",
    "docs/OSB_V2_CONTRACT.md",
    "docs/INSTALL.md",
    "docs/CLAUDE.md",
    "docs/CODEX.md",
    "docs/COPILOT.md",
    "docs/RAGMONK.md",
    "docs/MULTI_REPO.md",
)

# Soft size guardrails (bytes). Guidance, not hard architecture requirements.
SKILL_MD_SIZE_GUARD = 5500
COPILOT_INSTRUCTIONS_SIZE_GUARD = 2000

errors: list[str] = []
warnings: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def warn(message: str) -> None:
    warnings.append(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def split_frontmatter(text: str) -> tuple[str, str] | None:
    """Return (frontmatter, body) if text starts with a --- frontmatter block."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    return text[4:end], text[end + 4 :]


def check_package_integrity() -> None:
    """Every distributed framework/feature file must exist under osb/ (P0-I exit gate)."""

    for relative in EXPECTED_PACKAGE_FILES:
        path = OSB_DIR / relative
        if not path.is_file():
            fail(f"missing expected package file: osb/{relative}")

    for legacy in LEGACY_TOP_LEVEL_DIRS:
        path = ROOT / legacy
        if path.exists():
            fail(
                f"legacy top-level directory must not be reintroduced: {legacy}/ "
                "(framework content belongs under osb/)"
            )

    legacy_agents_skill_dir = ROOT / ".agents/skills/osb/references"
    if legacy_agents_skill_dir.exists():
        fail(
            ".agents/skills/osb/references/ must not exist — canonical references live "
            "under osb/references/; .agents/skills/osb/ may contain only the generated "
            "SKILL.md discovery pointer"
        )


def check_canonical_skill() -> None:
    path = OSB_DIR / "SKILL.md"
    if not path.is_file():
        fail("missing canonical skill: osb/SKILL.md")
        return

    text = read(path)
    fm = split_frontmatter(text)
    if fm is None:
        fail("osb/SKILL.md: missing skill frontmatter (--- ... ---)")
    else:
        frontmatter, _ = fm
        if not re.search(r"^name:\s*osb\s*$", frontmatter, re.MULTILINE):
            fail("osb/SKILL.md: frontmatter missing 'name: osb'")
        if not re.search(r"^description:\s*\S", frontmatter, re.MULTILINE):
            fail("osb/SKILL.md: frontmatter missing non-empty 'description:'")

    for ref in CANONICAL_REFERENCES:
        if f"osb/{ref}" not in text:
            fail(f"osb/SKILL.md: does not reference osb/{ref}")
        ref_path = OSB_DIR / ref
        if not ref_path.is_file():
            fail(f"missing canonical reference file: osb/{ref}")


def check_native_skill_pointer() -> None:
    """.agents/skills/osb/SKILL.md (generated, for Codex/Copilot discovery) must be a
    verbatim reproduction of osb/SKILL.md — never a second, independently maintained copy
    of the workflow policy."""

    pointer_path = ROOT / ".agents/skills/osb/SKILL.md"
    canonical_path = OSB_DIR / "SKILL.md"
    if not pointer_path.is_file():
        warn(".agents/skills/osb/SKILL.md not present — Codex/Copilot native discovery is not registered")
        return
    if not canonical_path.is_file():
        return  # already reported by check_canonical_skill
    if read(pointer_path) != read(canonical_path):
        fail(
            ".agents/skills/osb/SKILL.md has drifted from osb/SKILL.md — it must be a "
            "verbatim generated copy; re-run `osb/install.sh upgrade`"
        )


def check_claude_skill() -> None:
    path = ROOT / ".claude/skills/osb/SKILL.md"
    if not path.is_file():
        warn(".claude/skills/osb/SKILL.md not present — Claude Code is not registered")
        return

    text = read(path)
    fm = split_frontmatter(text)
    if fm is None:
        fail(f"{rel(path)}: missing skill frontmatter (--- ... ---)")
        return
    frontmatter, _ = fm
    if not re.search(r"^name:\s*osb\s*$", frontmatter, re.MULTILINE):
        fail(f"{rel(path)}: frontmatter missing 'name: osb'")


def check_role_agents_no_drift() -> None:
    """Generated per-host role agents must reproduce the canonical osb/agents/<role>.md
    body — this is the drift check called for by P0-I (0A.2/0A.3)."""

    for role in ROLES:
        canonical_path = OSB_DIR / "agents" / f"{role}.md"
        if not canonical_path.is_file():
            fail(f"missing canonical role source: osb/agents/{role}.md")
            continue
        canonical_fm = split_frontmatter(read(canonical_path))
        if canonical_fm is None:
            fail(f"osb/agents/{role}.md: missing frontmatter (--- ... ---)")
            continue
        _, canonical_body = canonical_fm

        claude_path = ROOT / f".claude/agents/{role}.md"
        if claude_path.is_file():
            claude_text = read(claude_path)
            claude_fm = split_frontmatter(claude_text)
            if claude_fm is None:
                fail(f"{rel(claude_path)}: missing agent frontmatter (--- ... ---)")
            else:
                frontmatter, _ = claude_fm
                if not re.search(rf"^name:\s*{role}\s*$", frontmatter, re.MULTILINE):
                    fail(f"{rel(claude_path)}: frontmatter missing 'name: {role}'")
                if claude_text != read(canonical_path):
                    fail(
                        f"{rel(claude_path)}: has drifted from osb/agents/{role}.md — "
                        "re-run `osb/install.sh upgrade` (or `--force` if hand-edited)"
                    )

        copilot_path = ROOT / f".github/agents/{role}.agent.md"
        if copilot_path.is_file():
            copilot_fm = split_frontmatter(read(copilot_path))
            if copilot_fm is None:
                fail(f"{rel(copilot_path)}: missing agent frontmatter (--- ... ---)")
            else:
                frontmatter, _ = copilot_fm
                if not re.search(rf"^name:\s*{role}\s*$", frontmatter, re.MULTILINE):
                    fail(f"{rel(copilot_path)}: frontmatter missing 'name: {role}'")
                body_lines = [l for l in canonical_body.strip("\n").splitlines()]
                missing = [l for l in body_lines if l.strip() and l.strip() not in read(copilot_path)]
                if missing:
                    fail(
                        f"{rel(copilot_path)}: does not reproduce the canonical role body "
                        f"from osb/agents/{role}.md — re-run `osb/install.sh upgrade`"
                    )

        codex_path = ROOT / f".codex/agents/{role}.toml"
        if codex_path.is_file():
            try:
                data = tomllib.loads(read(codex_path))
            except tomllib.TOMLDecodeError as exc:
                fail(f"{rel(codex_path)}: invalid TOML ({exc})")
                continue
            for required_key in ("name", "description", "developer_instructions", "sandbox_mode"):
                if required_key not in data:
                    fail(f"{rel(codex_path)}: missing required key '{required_key}'")
            if "instructions" in data:
                fail(f"{rel(codex_path)}: uses legacy key 'instructions' (must be 'developer_instructions')")
            if "model" in data:
                fail(f"{rel(codex_path)}: must not set 'model' (resolved dynamically from osb.yaml)")
            expected_sandbox = CODEX_SANDBOX_BY_ROLE[role]
            actual_sandbox = data.get("sandbox_mode")
            if actual_sandbox is not None and actual_sandbox != expected_sandbox:
                fail(
                    f"{rel(codex_path)}: sandbox_mode is '{actual_sandbox}', "
                    f"expected '{expected_sandbox}' for role '{role}'"
                )


def check_osb_yaml_template() -> None:
    path = OSB_DIR / "templates/osb.yaml"
    if not path.is_file():
        fail("missing config template: osb/templates/osb.yaml")
        return
    text = read(path)
    for host in ("claude-code", "codex", "copilot"):
        if host not in text:
            fail(f"osb/templates/osb.yaml: missing '{host}' models block")
    for role in ROLES:
        if f"{role}:" not in text:
            fail(f"osb/templates/osb.yaml: missing '{role}:' model field")

    if "max_parallel_implementers" not in text:
        fail("osb/templates/osb.yaml: missing 'max_parallel_implementers'")
    if "refresh_after_knowledge_change" not in text:
        fail("osb/templates/osb.yaml: missing 'ragmonk.refresh_after_knowledge_change'")
    if "refresh_after_checkpoint" in text:
        fail("osb/templates/osb.yaml: uses deprecated key 'refresh_after_checkpoint'")


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
                continue  # already reported elsewhere
            instructions = data.get("developer_instructions", "")
            _check_no_forbidden_substrings(codex_path, instructions)


def _check_no_forbidden_substrings(path: Path, text: str) -> None:
    for substring in FORBIDDEN_SUBAGENT_SUBSTRINGS:
        if substring in text:
            fail(
                f"{rel(path)}: subagent content references '{substring}' "
                "— subagents must be self-contained and not read shared OSB policy files"
            )


def check_compact_and_delta_docs() -> None:
    path = OSB_DIR / "references/handoff.md"
    if not path.is_file():
        return  # already reported by check_canonical_skill
    text = read(path).lower()
    if "unit capsule" not in text:
        fail("osb/references/handoff.md: compact handoff rules (unit capsules) not documented")
    if "delta" not in text:
        fail("osb/references/handoff.md: delta-only repair loop rules not documented")


def check_size_guards() -> None:
    skill_path = OSB_DIR / "SKILL.md"
    if skill_path.is_file() and skill_path.stat().st_size > SKILL_MD_SIZE_GUARD:
        warn(f"osb/SKILL.md: {skill_path.stat().st_size} bytes (guardrail: <= {SKILL_MD_SIZE_GUARD})")

    copilot_path = ROOT / ".github/copilot-instructions.md"
    if copilot_path.is_file() and copilot_path.stat().st_size > COPILOT_INSTRUCTIONS_SIZE_GUARD:
        warn(
            f"{rel(copilot_path)}: {copilot_path.stat().st_size} bytes "
            f"(guardrail: <= {COPILOT_INSTRUCTIONS_SIZE_GUARD})"
        )


def check_quality_contract() -> None:
    """The quality-guardrails invariants (final review/QA gates, evidence escalation,
    staleness/fingerprinting) must be documented in the canonical reference files, and the
    old unqualified 'repaired diff only' phrasing must not have crept back in anywhere."""

    for relative in QUALITY_CANONICAL_FILES:
        path = OSB_DIR / relative
        if not path.is_file():
            continue  # already reported by check_canonical_skill
        text = read(path).lower()
        if "final combined-change review" not in text:
            fail(f"osb/{relative}: 'final combined-change review' gate not documented")
        if "needs-evidence" not in text:
            fail(f"osb/{relative}: 'needs-evidence' evidence-escalation status not documented")

    for relative in FINGERPRINT_FILES:
        path = OSB_DIR / relative
        if not path.is_file():
            continue
        if "fingerprint" not in read(path).lower():
            fail(f"osb/{relative}: patch fingerprint/staleness rule not documented")

    reviewer_agent_paths = [
        ROOT / ".claude/agents/reviewer.md",
        ROOT / ".github/agents/reviewer.agent.md",
    ]
    for path in reviewer_agent_paths:
        if path.is_file() and "final combined-change review" not in read(path).lower():
            fail(f"{rel(path)}: mandatory final review not documented for Reviewer")

    codex_reviewer = ROOT / ".codex/agents/reviewer.toml"
    if codex_reviewer.is_file():
        try:
            data = tomllib.loads(read(codex_reviewer))
            instructions = data.get("developer_instructions", "").lower()
            if "final combined-change review" not in instructions:
                fail(f"{rel(codex_reviewer)}: mandatory final review not documented for Reviewer")
        except tomllib.TOMLDecodeError:
            pass  # already reported by check_role_agents_no_drift

    needs_evidence_roles = ("implementer", "reviewer", "qa")
    for role in needs_evidence_roles:
        claude_path = ROOT / f".claude/agents/{role}.md"
        if claude_path.is_file() and "needs-evidence" not in read(claude_path).lower():
            fail(f"{rel(claude_path)}: 'needs-evidence' status not documented")

        copilot_path = ROOT / f".github/agents/{role}.agent.md"
        if copilot_path.is_file() and "needs-evidence" not in read(copilot_path).lower():
            fail(f"{rel(copilot_path)}: 'needs-evidence' status not documented")

        codex_path = ROOT / f".codex/agents/{role}.toml"
        if codex_path.is_file():
            try:
                data = tomllib.loads(read(codex_path))
                instructions = data.get("developer_instructions", "").lower()
                if "needs-evidence" not in instructions:
                    fail(f"{rel(codex_path)}: 'needs-evidence' status not documented")
            except tomllib.TOMLDecodeError:
                pass

    all_role_paths: list[Path] = []
    for role in ROLES:
        all_role_paths.append(ROOT / f".claude/agents/{role}.md")
        all_role_paths.append(ROOT / f".github/agents/{role}.agent.md")
    all_role_paths.append(OSB_DIR / "references/roles.md")
    all_role_paths.append(OSB_DIR / "references/handoff.md")

    for path in all_role_paths:
        if not path.is_file():
            continue
        text_lower = read(path).lower()
        for phrase in FORBIDDEN_STALE_REVIEW_PHRASES:
            if phrase in text_lower:
                fail(
                    f"{rel(path)}: contains stale unqualified phrase "
                    f"'{phrase}' — a delta/repaired-diff pass must not read as sufficient "
                    "by itself; the mandatory final combined-change review must be named"
                )

    for role in ROLES:
        codex_path = ROOT / f".codex/agents/{role}.toml"
        if codex_path.is_file():
            try:
                data = tomllib.loads(read(codex_path))
                instructions = data.get("developer_instructions", "").lower()
            except tomllib.TOMLDecodeError:
                continue
            for phrase in FORBIDDEN_STALE_REVIEW_PHRASES:
                if phrase in instructions:
                    fail(f"{rel(codex_path)}: contains stale unqualified phrase '{phrase}'")


def check_legacy_dirs_absent() -> None:
    for name in LEGACY_DIRS:
        path = ROOT / name
        if path.exists():
            fail(f"legacy OSB v1 directory must not be reintroduced: {name}/")


def check_manifest() -> None:
    path = OSB_DIR / "manifest.json"
    if not path.is_file():
        fail("missing osb/manifest.json")
        return
    try:
        data = json.loads(read(path))
    except ValueError as exc:
        fail(f"osb/manifest.json: invalid JSON ({exc})")
        return
    if not data.get("package_version"):
        fail("osb/manifest.json: missing 'package_version'")
    for key in ("generated_files", "package_files", "hosts_registered"):
        if key not in data:
            fail(f"osb/manifest.json: missing '{key}'")


def check_state_template_matches_schema() -> None:
    """osb/templates/state/task.json must itself validate against
    task-state.schema.json (P0-C 1.3) — a schema/template mismatch here would mean every
    task created from this template starts out already non-conformant."""

    schema_path = OSB_DIR / "schemas/task-state.schema.json"
    template_path = OSB_DIR / "templates/state/task.json"
    if not schema_path.is_file():
        fail("missing osb/schemas/task-state.schema.json")
        return
    if not template_path.is_file():
        fail("missing osb/templates/state/task.json")
        return
    try:
        schema = json.loads(read(schema_path))
        template = json.loads(read(template_path))
    except ValueError as exc:
        fail(f"task-state schema/template is not valid JSON: {exc}")
        return
    for error in schema_validate.validate(template, schema):
        fail(f"osb/templates/state/task.json does not conform to task-state.schema.json: {error}")


def check_role_result_schema_is_valid_json() -> None:
    path = OSB_DIR / "schemas/role-result.schema.json"
    if not path.is_file():
        fail("missing osb/schemas/role-result.schema.json")
        return
    try:
        json.loads(read(path))
    except ValueError as exc:
        fail(f"osb/schemas/role-result.schema.json is not valid JSON: {exc}")


def check_workspace_exceptions_preserved() -> None:
    """Root osb.yaml / .osb/{state,knowledge} are workspace-owned exceptions to the
    single-folder package rule (P0-I) — flag if osb.yaml looks auto-clobbered."""

    osb_yaml = ROOT / "osb.yaml"
    if osb_yaml.is_file():
        text = read(osb_yaml)
        if "version:" not in text:
            warn("osb.yaml: missing top-level 'version' field")


def main() -> int:
    check_package_integrity()
    check_canonical_skill()
    check_native_skill_pointer()
    check_claude_skill()
    check_role_agents_no_drift()
    check_osb_yaml_template()
    check_legacy_dirs_absent()
    check_subagents_self_contained()
    check_compact_and_delta_docs()
    check_quality_contract()
    check_size_guards()
    check_manifest()
    check_state_template_matches_schema()
    check_role_result_schema_is_valid_json()
    check_workspace_exceptions_preserved()

    if warnings:
        print(f"OSB package validation: {len(warnings)} warning(s):\n")
        for warning in warnings:
            print(f"  - {warning}")
        print()

    if errors:
        print(f"OSB package validation failed with {len(errors)} error(s):\n")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("OSB package validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
