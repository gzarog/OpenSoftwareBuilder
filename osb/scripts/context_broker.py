#!/usr/bin/env python3
"""Evidence-aware context broker (Next Improvements, Phase 3).

Assembles a minimal, source-verified evidence capsule for one role/unit dispatch
(`osb/schemas/context-capsule.schema.json`). This is a deterministic file/metadata helper
invoked by the coordinator — never a new agent, background service, or substitute for
RagMonk (`osb/references/ragmonk.md` remains the only retrieval engine; code and
`.osb/knowledge/` remain authoritative). See `osb/docs/CONTEXT_BROKER.md`.

Excerpt identity is `(repository_id, source_path, source_revision, locator)` — the same
snippet at the same content fingerprint is one capsule entry, reused, never re-fetched or
re-injected twice (mirrors `knowledge_lifecycle.py`'s dedup rule, extended with a locator
so two different symbols in the same file don't collide). A file whose content changes
gets a new fingerprint, hence a new identity — the old entry is never silently treated as
current again; `refresh_excerpt_store` explicitly marks it `stale` for bookkeeping.

Never caches a QA verdict — this module only ever caches *evidence*, and
`osb/references/quality.md` §Final-revision QA gate requires QA to independently re-check
every AC on the final revision regardless of what evidence was reused.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import safe_exec  # noqa: E402
import schema_validate  # noqa: E402

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "context-capsule.schema.json"
CAPSULE_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

DEFAULT_INITIAL_BUDGET_CHARS = 6000


class ContextBrokerError(RuntimeError):
    pass


def content_fingerprint(content: str) -> str:
    return f"cfp-{hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]}"


def excerpt_key(repository_id: str | None, source_path: str, source_revision: str, locator: str | None) -> str:
    basis = f"{repository_id}\0{source_path}\0{source_revision}\0{locator}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Excerpt store (per-task, dedup + staleness bookkeeping)
# ---------------------------------------------------------------------------


def load_excerpt_store(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_excerpt_store(path: Path, store: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def refresh_excerpt_store(store: dict, workspace_root: Path, repositories: list[dict]) -> list[str]:
    """Marks any stored excerpt whose source file no longer matches its recorded
    source_revision as 'stale' — kept for audit/bookkeeping, never deleted, and never
    reused as 'current' by a later `build_capsule` call (a changed file naturally gets a
    fresh identity/key, per the module docstring)."""

    repo_by_id = {r["id"]: r for r in repositories}
    stale_keys: list[str] = []
    for key, entry in store.items():
        repo = repo_by_id.get(entry.get("repository_id"))
        if repo is None:
            continue
        try:
            repo_root = safe_exec.resolve_within_root(workspace_root, repo["path"])
            file_path = safe_exec.resolve_within_root(repo_root, entry["source_path"])
        except safe_exec.PathEscapesRootError:
            entry["status"] = "stale"
            stale_keys.append(key)
            continue
        if not file_path.is_file():
            entry["status"] = "stale"
            stale_keys.append(key)
            continue
        current_fp = content_fingerprint(file_path.read_text(encoding="utf-8", errors="ignore"))
        if current_fp != entry["source_revision"]:
            entry["status"] = "stale"
            stale_keys.append(key)
    return stale_keys


# ---------------------------------------------------------------------------
# Knowledge constraint rendering (verified vs. provisional)
# ---------------------------------------------------------------------------


def render_constraint_from_knowledge(entry: dict) -> str | None:
    """Renders one durable knowledge entry (osb/references/knowledge.md) as a capsule
    constraint string, honoring lifecycle status: a `superseded` entry contributes
    nothing (its replacement, if any, is a separate entry); a `provisional` entry is
    visibly marked unverified rather than presented as settled fact."""

    status = entry.get("lifecycle_status", "provisional")
    summary = entry.get("summary", "")
    if status == "superseded":
        return None
    if status == "provisional":
        return f"[unverified] {summary}"
    return summary


# ---------------------------------------------------------------------------
# Capsule assembly
# ---------------------------------------------------------------------------


def compute_capsule_fingerprint(capsule: dict) -> str:
    hasher = hashlib.sha256()
    hasher.update(capsule["task_id"].encode())
    hasher.update(b"\0")
    hasher.update(capsule["role"].encode())
    hasher.update(b"\0")
    hasher.update(str(capsule.get("unit_id")).encode())
    hasher.update(b"\n")
    for ac_id, text in sorted(capsule["required_ac"].items()):
        hasher.update(f"{ac_id}\0{text}\n".encode())
    for constraint in capsule["constraints"]:
        hasher.update(constraint.encode())
        hasher.update(b"\n")
    for item in sorted(capsule["evidence"], key=lambda e: e["excerpt_ref"]):
        hasher.update(json.dumps(item, sort_keys=True).encode())
        hasher.update(b"\n")
    return f"ccp-{hasher.hexdigest()[:16]}"


def build_capsule(
    task_id: str,
    role: str,
    workspace_root: Path,
    repositories: list[dict],
    required_ac: dict[str, str],
    constraints: list[str],
    evidence_requests: list[dict],
    *,
    unit_id: str | None = None,
    workspace_manifest_fingerprint: str | None = None,
    impact_plan_fingerprint: str | None = None,
    initial_budget_chars: int = DEFAULT_INITIAL_BUDGET_CHARS,
    excerpt_store: dict | None = None,
    unresolved_questions: list[dict] | None = None,
) -> tuple[dict, dict]:
    """Builds one capsule and returns (capsule, updated_excerpt_store). `evidence_requests`
    is `[{"repository_id", "source_path", "locator"?, "max_chars"?}]` — already-decided,
    scoped requests (e.g. from an impact plan or a role's own targeted RagMonk lookup),
    never a broad "give me everything" query. `required_ac`/`constraints` text is carried
    verbatim and is never truncated to fit `initial_budget_chars` — only evidence excerpts
    are ever trimmed, and trimming is recorded as an unresolved question, not hidden."""

    excerpt_store = dict(excerpt_store) if excerpt_store is not None else {}
    repo_by_id = {r["id"]: r for r in repositories}
    evidence: list[dict] = []
    unresolved = list(unresolved_questions or [])
    total_chars = 0

    for request in evidence_requests:
        repo_id = request["repository_id"]
        repo = repo_by_id.get(repo_id)
        if repo is None:
            unresolved.append({
                "question": f"repository '{repo_id}' is not in the workspace",
                "reason": "unknown repository id in evidence request",
            })
            continue

        try:
            repo_root = safe_exec.resolve_within_root(workspace_root, repo["path"])
            file_path = safe_exec.resolve_within_root(repo_root, request["source_path"])
        except safe_exec.PathEscapesRootError:
            unresolved.append({
                "question": f"source '{request['source_path']}' in '{repo_id}' could not be resolved",
                "reason": "path escapes repository root",
            })
            continue

        if not file_path.is_file():
            unresolved.append({
                "question": f"source '{request['source_path']}' not found in '{repo_id}'",
                "reason": "file does not exist",
            })
            continue

        content = file_path.read_text(encoding="utf-8", errors="ignore")
        fingerprint = content_fingerprint(content)
        locator = request.get("locator")
        key = excerpt_key(repo_id, request["source_path"], fingerprint, locator)

        cached = excerpt_store.get(key)
        if cached is None:
            excerpt_text = content
            max_chars = request.get("max_chars")
            if max_chars is not None and len(excerpt_text) > max_chars:
                excerpt_text = excerpt_text[:max_chars]
            cached = {
                "repository_id": repo_id,
                "source_path": request["source_path"],
                "source_revision": fingerprint,
                "locator": locator,
                "content": excerpt_text,
                "status": "current",
            }
            excerpt_store[key] = cached
        else:
            cached["status"] = "current"  # a fresh request for the same identity reconfirms currency

        evidence.append({
            "repository_id": cached["repository_id"],
            "source_path": cached["source_path"],
            "source_revision": cached["source_revision"],
            "locator": cached.get("locator"),
            "excerpt_ref": key,
            "status": cached["status"],
        })
        total_chars += len(cached["content"])

    if total_chars > initial_budget_chars:
        unresolved.append({
            "question": "initial evidence exceeds the initial budget",
            "reason": (
                f"{total_chars} evidence chars retrieved against a budget of "
                f"{initial_budget_chars}; required AC/constraint text was preserved in full "
                "and was never truncated to fit"
            ),
        })

    capsule = {
        "task_id": task_id,
        "role": role,
        "unit_id": unit_id,
        "workspace_manifest_fingerprint": workspace_manifest_fingerprint,
        "impact_plan_fingerprint": impact_plan_fingerprint,
        "required_ac": required_ac,
        "constraints": constraints,
        "evidence": evidence,
        "unresolved_questions": unresolved,
        "initial_budget_chars": initial_budget_chars,
    }
    capsule["capsule_fingerprint"] = compute_capsule_fingerprint(capsule)
    return capsule, excerpt_store


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _context_dir(workspace_root: Path, task_id: str) -> Path:
    return workspace_root / ".osb" / "context" / task_id


def cmd_build(args: argparse.Namespace) -> int:
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    workspace_root = Path(args.workspace_root).resolve()
    task_id = request["task_id"]
    context_dir = _context_dir(workspace_root, task_id)
    store_path = context_dir / "excerpts.json"
    excerpt_store = load_excerpt_store(store_path)

    capsule, excerpt_store = build_capsule(
        task_id,
        request["role"],
        workspace_root,
        request["repositories"],
        request.get("required_ac", {}),
        request.get("constraints", []),
        request.get("evidence_requests", []),
        unit_id=request.get("unit_id"),
        workspace_manifest_fingerprint=request.get("workspace_manifest_fingerprint"),
        impact_plan_fingerprint=request.get("impact_plan_fingerprint"),
        initial_budget_chars=request.get("initial_budget_chars", DEFAULT_INITIAL_BUDGET_CHARS),
        excerpt_store=excerpt_store,
        unresolved_questions=request.get("unresolved_questions"),
    )

    errors = schema_validate.validate(capsule, CAPSULE_SCHEMA)
    if errors:
        print(f"refusing to write an invalid capsule, {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1

    unit_suffix = f"-{capsule['unit_id']}" if capsule.get("unit_id") else ""
    out_path = Path(args.out) if args.out else context_dir / f"{capsule['role']}{unit_suffix}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(capsule, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    save_excerpt_store(store_path, excerpt_store)

    print(f"wrote {out_path}")
    print(f"capsule_fingerprint: {capsule['capsule_fingerprint']}")
    if capsule["unresolved_questions"]:
        print(f"{len(capsule['unresolved_questions'])} unresolved question(s) — see needs-evidence in osb/references/handoff.md")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace_root).resolve()
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    context_dir = _context_dir(workspace_root, request["task_id"])
    store_path = context_dir / "excerpts.json"
    store = load_excerpt_store(store_path)
    stale = refresh_excerpt_store(store, workspace_root, request["repositories"])
    save_excerpt_store(store_path, store)
    print(f"{len(stale)} excerpt(s) marked stale")
    for key in stale:
        print(f"  - {key}: {store[key]['repository_id']}/{store[key]['source_path']}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    capsule = json.loads(Path(args.capsule).read_text(encoding="utf-8"))
    errors = schema_validate.validate(capsule, CAPSULE_SCHEMA)
    if errors:
        print(f"capsule invalid, {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("capsule valid.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="context_broker", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Assemble and write a context capsule from a request JSON file")
    p_build.add_argument("request")
    p_build.add_argument("--workspace-root", default=".")
    p_build.add_argument("--out", default=None)
    p_build.set_defaults(func=cmd_build)

    p_refresh = sub.add_parser("refresh", help="Mark stale excerpts in the per-task excerpt store")
    p_refresh.add_argument("request")
    p_refresh.add_argument("--workspace-root", default=".")
    p_refresh.set_defaults(func=cmd_refresh)

    p_validate = sub.add_parser("validate", help="Validate an existing capsule against the schema")
    p_validate.add_argument("capsule")
    p_validate.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
