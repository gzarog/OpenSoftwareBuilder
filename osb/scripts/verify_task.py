#!/usr/bin/env python3
"""Deterministic OSB task-completion verifier (P0-C, Phase 1).

This never runs a model or a role — it is a schema/fingerprint/state checker only. It
validates a task's compact state (and, optionally, a QA role-result evidence file)
against osb/schemas/*.json and the completion-gate invariants in osb/references/quality.md
§Completion gate. It is deliberately conservative: on any ambiguity it reports the task as
NOT complete rather than inferring success from a narrow, cheap check (see
osb/references/quality.md §Non-negotiable principles).

Subcommands:
  fingerprint <repo-root> <base-revision>        print the current patch fingerprint
  check <state.json> [--repo-root P] [--evidence Q] [--repo ID=PATH ...]
                                                  run the full completion-gate check
  write <source.json> <dest.json>                validate + atomically write task state
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schema_validate  # noqa: E402

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"
TASK_STATE_SCHEMA = json.loads((SCHEMAS_DIR / "task-state.schema.json").read_text())
ROLE_RESULT_SCHEMA = json.loads((SCHEMAS_DIR / "role-result.schema.json").read_text())

# Paths excluded from the fingerprint: ephemeral execution state, incremental knowledge
# events, and the durable task/component records written only during final consolidation
# (i.e. *after* QA passes). Including any of these would make consolidating knowledge, or
# simply checkpointing state, retroactively invalidate the very QA verdict that triggered
# it — a self-invalidating loop. Documented explicitly per P0-C 1.2 so this can't silently
# grow to exclude real implementation files.
FINGERPRINT_EXCLUDED_PREFIXES = (
    ".osb/state/",
    ".osb/knowledge/events/",
    ".osb/knowledge/tasks/",
    ".osb/knowledge/components/",
)


class VerificationError(RuntimeError):
    pass


def _run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise VerificationError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def compute_fingerprint(repo_root: Path, base_revision: str) -> str:
    """A reproducible hash over tracked changes since base_revision plus untracked files,
    excluding FINGERPRINT_EXCLUDED_PREFIXES. Must change whenever tracked OR uncommitted
    implementation content changes — a HEAD SHA alone is not sufficient (quality.md
    §Fingerprinting)."""

    tracked_changed = set(
        line for line in _run_git(repo_root, "diff", "--name-only", base_revision).splitlines() if line
    )
    untracked = set(
        line
        for line in _run_git(repo_root, "ls-files", "--others", "--exclude-standard").splitlines()
        if line
    )
    all_changed = tracked_changed | untracked
    included = sorted(
        f for f in all_changed if not any(f.startswith(prefix) for prefix in FINGERPRINT_EXCLUDED_PREFIXES)
    )

    hasher = hashlib.sha256()
    for rel in included:
        path = repo_root / rel
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        if path.is_file():
            hasher.update(path.read_bytes())
        else:
            hasher.update(b"<deleted>")
        hasher.update(b"\n")
    return f"fp-{hasher.hexdigest()[:16]}"


def compute_workspace_fingerprint(workspace_root: Path, repositories: dict) -> str:
    """Ordered digest over each affected repository's identity, path, base revision, and
    effective patch fingerprint (P0-A 3.2 §Workspace fingerprint). Sorted by repo id so the
    result is independent of dict/config ordering; changing any one repository changes
    this fingerprint, which is what invalidates workspace-level review/QA approvals."""

    hasher = hashlib.sha256()
    for repo_id in sorted(repositories):
        info = repositories[repo_id]
        repo_fp = compute_fingerprint(workspace_root / info["path"], info["base_revision"])
        hasher.update(repo_id.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(info["path"]).encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(repo_fp.encode("utf-8"))
        hasher.update(b"\n")
    return f"wfp-{hasher.hexdigest()[:16]}"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_state_atomic(dest: Path, state: dict) -> list[str]:
    """Validate `state` against the task-state schema, then atomically replace `dest`
    (write temp + os.replace). On validation failure, `dest` is left untouched and the
    schema errors are returned instead of raising, so callers can decide how to report a
    rejected write without losing the previous valid state (P0-C 1.2)."""

    errors = schema_validate.validate(state, TASK_STATE_SCHEMA)
    if errors:
        return errors

    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_path, dest)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    return []


def check_completion(
    state: dict, repo_root: Path, evidence: dict | None = None
) -> tuple[bool, list[str]]:
    """The single source of truth for "is this task actually done" — mirrors
    osb/references/quality.md §Completion gate exactly. Returns (ok, reasons); reasons is
    always populated when ok is False, and never fabricates a pass from missing data."""

    reasons: list[str] = []

    schema_errors = schema_validate.validate(state, TASK_STATE_SCHEMA)
    if schema_errors:
        return False, [f"schema: {e}" for e in schema_errors]

    quality = state["quality"]
    required_ac_ids = set(quality["required_ac_ids"])
    acceptance_ids = set(state["acceptance"].keys())
    if not required_ac_ids:
        reasons.append("quality.required_ac_ids is empty — no AC set to verify against")
    missing_text = required_ac_ids - acceptance_ids
    if missing_text:
        reasons.append(f"required AC id(s) missing exact requirement text in 'acceptance': {sorted(missing_text)}")

    try:
        workspace = state.get("workspace")
        if workspace:
            for repo_id, info in workspace.get("repositories", {}).items():
                repo_fp = compute_fingerprint(repo_root / info["path"], info["base_revision"])
                if info.get("patch_fingerprint") != repo_fp:
                    reasons.append(
                        f"repository '{repo_id}' patch_fingerprint is stale: recorded "
                        f"{info.get('patch_fingerprint')!r}, recomputed {repo_fp!r}"
                    )
            current_fp = compute_workspace_fingerprint(repo_root, workspace.get("repositories", {}))
        else:
            current_fp = compute_fingerprint(repo_root, quality["task_base_revision"])
    except VerificationError as exc:
        return False, [str(exc)]

    if quality["current_patch_fingerprint"] != current_fp:
        reasons.append(
            "current_patch_fingerprint is stale: recorded "
            f"{quality['current_patch_fingerprint']!r} but recomputed {current_fp!r} — "
            "the working tree changed since this was last recorded"
        )

    if state["review"].get("status") != "clean":
        reasons.append(f"review.status is {state['review'].get('status')!r}, not 'clean'")
    if state["review"].get("scope") != "final-combined-change":
        reasons.append(
            f"review.scope is {state['review'].get('scope')!r} — a delta pass is never "
            "sufficient by itself; a final-combined-change review is required"
        )
    if quality["final_review_fingerprint"] != current_fp:
        reasons.append(
            f"final_review_fingerprint {quality['final_review_fingerprint']!r} does not "
            f"match the current patch fingerprint {current_fp!r} — the final review is stale"
        )

    if state["qa"].get("status") != "pass":
        reasons.append(f"qa.status is {state['qa'].get('status')!r}, not 'pass'")
    if quality["final_qa_fingerprint"] != current_fp:
        reasons.append(
            f"final_qa_fingerprint {quality['final_qa_fingerprint']!r} does not match the "
            f"current patch fingerprint {current_fp!r} — QA is stale"
        )

    if quality["unverified_ac_ids"]:
        reasons.append(f"unverified AC id(s) remain: {quality['unverified_ac_ids']}")
    if quality["unresolved_context_requests"]:
        reasons.append(f"{len(quality['unresolved_context_requests'])} unresolved evidence gap(s) remain")

    if not quality.get("knowledge_consolidated", False):
        reasons.append("quality.knowledge_consolidated is not true — durable knowledge has not been consolidated")

    if evidence is not None:
        evidence_errors = schema_validate.validate(evidence, ROLE_RESULT_SCHEMA)
        if evidence_errors:
            reasons.extend(f"evidence: {e}" for e in evidence_errors)
        else:
            if evidence.get("status") != "pass":
                reasons.append(f"QA evidence status is {evidence.get('status')!r}, not 'pass'")
            if evidence.get("revision") != current_fp:
                reasons.append(
                    f"QA evidence was recorded for revision {evidence.get('revision')!r}, "
                    f"not the current fingerprint {current_fp!r}"
                )
            ac_results = evidence.get("ac", {})
            for ac_id in required_ac_ids:
                entry = ac_results.get(ac_id)
                if entry is None:
                    reasons.append(f"QA evidence has no verdict for required AC '{ac_id}'")
                elif entry.get("result") != "pass":
                    reasons.append(
                        f"QA evidence for '{ac_id}' is {entry.get('result')!r}, not 'pass' "
                        "— not-run/blocked/inconclusive is never treated as passing"
                    )

    return (len(reasons) == 0), reasons


def cmd_fingerprint(args: argparse.Namespace) -> int:
    fp = compute_fingerprint(Path(args.repo_root).resolve(), args.base_revision)
    print(fp)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    state = load_json(Path(args.state_file))
    evidence = load_json(Path(args.evidence)) if args.evidence else None
    ok, reasons = check_completion(state, Path(args.repo_root).resolve(), evidence)
    if ok:
        print("COMPLETE: completion gate holds.")
        return 0
    print("NOT COMPLETE:")
    for reason in reasons:
        print(f"  - {reason}")
    return 1


def cmd_write(args: argparse.Namespace) -> int:
    state = load_json(Path(args.source))
    errors = write_state_atomic(Path(args.dest), state)
    if errors:
        print(f"rejected: {args.source} does not conform to task-state.schema.json:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"wrote {args.dest}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="verify_task", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_fp = sub.add_parser("fingerprint", help="Print the current patch fingerprint")
    p_fp.add_argument("repo_root")
    p_fp.add_argument("base_revision")
    p_fp.set_defaults(func=cmd_fingerprint)

    p_check = sub.add_parser("check", help="Run the full completion-gate check")
    p_check.add_argument("state_file")
    p_check.add_argument("--repo-root", default=".")
    p_check.add_argument("--evidence", default=None, help="Path to a QA role-result JSON file")
    p_check.set_defaults(func=cmd_check)

    p_write = sub.add_parser("write", help="Validate and atomically write task state")
    p_write.add_argument("source")
    p_write.add_argument("dest")
    p_write.set_defaults(func=cmd_write)

    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
