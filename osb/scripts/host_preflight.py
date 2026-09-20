#!/usr/bin/env python3
"""Host capability preflight (P1-G, Phase 7).

Deterministic, local checks only — this never calls a model or a host API (no such
generic API exists to call). Where a capability genuinely cannot be verified from a
script, it is reported as `unknown`, never silently assumed to pass. A host-specific LIVE
smoke test (actually dispatching a role on that host) is a separate, explicitly labelled
layer — see osb/docs/HOST_COMPATIBILITY.md — and this script does not attempt it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yaml_lite  # noqa: E402

ROLES = ("architect", "implementer", "reviewer", "qa")
HOST_KEYS = {"claude": "claude-code", "codex": "codex", "copilot": "copilot"}
GENERATED_PATHS_BY_HOST = {
    "claude": [".claude/skills/osb/SKILL.md", ".claude/agents/architect.md",
               ".claude/agents/implementer.md", ".claude/agents/reviewer.md", ".claude/agents/qa.md"],
    "codex": [".agents/skills/osb/SKILL.md", ".codex/agents/architect.toml",
              ".codex/agents/implementer.toml", ".codex/agents/reviewer.toml", ".codex/agents/qa.toml"],
    "copilot": [".agents/skills/osb/SKILL.md", ".github/copilot-instructions.md",
                ".github/agents/architect.agent.md", ".github/agents/implementer.agent.md",
                ".github/agents/reviewer.agent.md", ".github/agents/qa.agent.md"],
}
STATUS_RANK = {"pass": 0, "not-applicable": 0, "unknown": 1, "blocked": 2}


def _status(status: str, detail: str = "") -> dict:
    return {"status": status, "detail": detail}


def check_models_configured(config: dict | None, host: str) -> dict:
    if config is None:
        return _status("blocked", "osb.yaml not found")
    host_key = HOST_KEYS[host]
    models = (config.get("models") or {}).get(host_key) or {}
    missing = [r for r in ROLES if not models.get(r)]
    if missing:
        return _status("blocked", f"missing model for role(s): {', '.join(missing)}")
    return _status("pass")


def check_generated_adapter_present(workspace_root: Path, host: str) -> dict:
    missing = [rel for rel in GENERATED_PATHS_BY_HOST[host] if not (workspace_root / rel).is_file()]
    if missing:
        return _status("blocked", f"missing generated file(s): {', '.join(missing)}")
    return _status("pass")


def check_git_available() -> dict:
    return _status("pass") if shutil.which("git") else _status("blocked", "git not found on PATH")


def check_git_worktree_supported(workspace_root: Path, config: dict | None) -> dict:
    isolation = ((config or {}).get("execution") or {}).get("isolation", "shared")
    if isolation != "worktree":
        return _status("not-applicable", "execution.isolation is not 'worktree'")
    result = subprocess.run(
        ["git", "worktree", "list"], cwd=workspace_root, capture_output=True, text=True
    )
    if result.returncode == 0:
        return _status("pass")
    return _status("blocked", result.stderr.strip() or "git worktree not usable in this repository")


def check_ragmonk(config: dict | None) -> dict:
    ragmonk_cfg = (config or {}).get("ragmonk") or {}
    if ragmonk_cfg.get("enabled") is False:
        return _status("not-applicable", "ragmonk.enabled is false")
    cli_available = shutil.which("ragmonk") is not None
    if cli_available:
        return _status("pass", "ragmonk CLI found on PATH")
    detail = (
        "ragmonk CLI not found on PATH; MCP-server availability cannot be checked by a "
        "standalone script — treat as unknown/unverified, not failed, unless the host "
        "confirms no RagMonk MCP tools are registered either"
    )
    if ragmonk_cfg.get("required") is True:
        return _status("unknown", detail + " (ragmonk.required: true — block dispatch if the host also finds no MCP access)")
    return _status("unknown", detail)


def check_test_command_capability() -> dict:
    return _status(
        "unknown",
        "project-specific; OSB does not introduce a custom toolchain abstraction to probe "
        "this — verify the project's own test command runs before relying on QA's results",
    )


def check_independent_role_contexts(host: str) -> dict:
    return _status(
        "unknown",
        f"{host} is documented to support independent per-role subagent/agent contexts "
        "when configured natively, but this cannot be confirmed from a standalone script — "
        "see osb/docs/HOST_COMPATIBILITY.md for the documented, testable happy path",
    )


def run_preflight(workspace_root: Path, host: str) -> dict:
    osb_yaml_path = workspace_root / "osb.yaml"
    config = yaml_lite.parse(osb_yaml_path.read_text(encoding="utf-8")) if osb_yaml_path.is_file() else None

    checks = {
        "models_configured": check_models_configured(config, host),
        "generated_adapter_present": check_generated_adapter_present(workspace_root, host),
        "git_available": check_git_available(),
        "git_worktree_supported": check_git_worktree_supported(workspace_root, config),
        "ragmonk": check_ragmonk(config),
        "test_command_capability": check_test_command_capability(),
        "independent_role_contexts": check_independent_role_contexts(host),
    }
    overall_rank = max(STATUS_RANK[c["status"]] for c in checks.values())
    overall = {v: k for k, v in STATUS_RANK.items()}[overall_rank]
    return {"host": host, "overall": overall, "checks": checks}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", choices=list(HOST_KEYS))
    parser.add_argument("--workspace-root", default=".")
    args = parser.parse_args(argv)

    report = run_preflight(Path(args.workspace_root).resolve(), args.host)
    print(json.dumps(report, indent=2))
    return 1 if report["overall"] == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
