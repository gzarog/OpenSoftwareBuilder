#!/usr/bin/env python3
"""Deterministic, read-only repository discovery (Next Improvements, Phase 1).

Walks a workspace root looking for independent Git repositories, proposes stable IDs and
confirmed/possible dependency edges, and — only once explicitly confirmed — writes a
derived snapshot to `.osb/cache/workspace-manifest.json`
(`osb/schemas/workspace-manifest.schema.json`). This is a *build/change* dependency graph,
not a runtime call graph, and it never edits `osb.yaml` or registers anything with
RagMonk. See `osb/docs/MULTI_REPO.md` §Discovery.

Subcommands:
  scan     <workspace-root> [--osb-yaml PATH] [--max-depth N] [--json]
           Read-only scan + proposal. Never writes anything.
  confirm  <workspace-root> --yes [--osb-yaml PATH] [--out PATH]
           Same as scan, then writes the confirmed manifest. Refuses without --yes (the
           noninteractive/CI-safe default: propose, never auto-confirm).
  validate <manifest-path> --workspace-root PATH
           Reconciles a previously confirmed manifest against the repositories' current
           state on disk (moved/removed/newly discovered repos, stale git_head).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import safe_exec  # noqa: E402
import schema_validate  # noqa: E402
import yaml_lite  # noqa: E402

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "workspace-manifest.schema.json"
MANIFEST_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

DEFAULT_EXCLUDES = frozenset({".git", ".osb", "node_modules", ".venv", "bin", "obj"})
DEFAULT_MAX_DEPTH = 4

_CSPROJ_PROJECT_REF_RE = re.compile(r'<ProjectReference\s+[^>]*Include="([^"]+)"', re.IGNORECASE)
_CSPROJ_PACKAGE_REF_RE = re.compile(r'<PackageReference\s+[^>]*Include="([^"]+)"', re.IGNORECASE)


class DiscoveryError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Git helpers (read-only)
# ---------------------------------------------------------------------------


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def _is_git_root(path: Path) -> bool:
    if not (path / ".git").exists():
        return False
    result = _run_git(path, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return False
    try:
        return Path(result.stdout.strip()).resolve() == path.resolve()
    except OSError:
        return False


def _git_head(path: Path) -> str | None:
    result = _run_git(path, "rev-parse", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def _git_root_commit(path: Path) -> str | None:
    result = _run_git(path, "rev-list", "--max-parents=0", "HEAD")
    if result.returncode != 0:
        return None
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return lines[-1].strip() if lines else None


def _rel(path: Path, root: Path) -> str:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return str(path)
    return "." if str(rel) == "." else rel.as_posix()


def _normalize(path_str: str) -> str:
    return Path(path_str).as_posix().rstrip("/") or "."


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


def scan(
    workspace_root: Path,
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    exclude: frozenset[str] | set[str] | None = None,
    follow_nested: bool = False,
) -> dict:
    """Bounded, symlink-safe walk for independent Git roots. Never raises on a permission
    error or an escaping symlink — both are recorded as warnings and the scan continues
    elsewhere, with `partial: true` set whenever the result cannot be a complete inventory."""

    exclude = frozenset(exclude) if exclude is not None else DEFAULT_EXCLUDES
    root_resolved = workspace_root.resolve()

    repositories: list[dict] = []
    warnings: list[dict] = []
    seen_canonical: set[str] = set()
    visited = 0
    skipped = 0
    partial = False

    stack: list[tuple[Path, int]] = [(workspace_root, 0)]
    while stack:
        current, depth = stack.pop()

        try:
            current_resolved = current.resolve()
        except OSError:
            skipped += 1
            continue

        try:
            current_resolved.relative_to(root_resolved)
        except ValueError:
            warnings.append({
                "kind": "symlink-escape",
                "path": _rel(current, workspace_root),
                "detail": f"resolved outside workspace root: {current_resolved}",
            })
            skipped += 1
            partial = True
            continue

        visited += 1
        is_repo = _is_git_root(current)
        if is_repo:
            canon_str = str(current_resolved)
            if canon_str not in seen_canonical:
                seen_canonical.add(canon_str)
                repositories.append({
                    "path": _rel(current, workspace_root),
                    "canonical_path": canon_str,
                    "git_head": _git_head(current),
                    "root_commit": _git_root_commit(current),
                })
            if current_resolved != root_resolved and not follow_nested:
                continue  # do not descend through an already-discovered child repo boundary

        if depth >= max_depth:
            try:
                has_children = any(p.is_dir() for p in current.iterdir())
            except OSError:
                has_children = False
            if has_children:
                warnings.append({
                    "kind": "depth-limit",
                    "path": _rel(current, workspace_root),
                    "detail": f"max_depth={max_depth} reached with unscanned subdirectories",
                })
                partial = True
            continue

        try:
            children = sorted((p for p in current.iterdir() if p.is_dir()), key=lambda p: p.name)
        except OSError:
            warnings.append({
                "kind": "permission-denied",
                "path": _rel(current, workspace_root),
                "detail": "permission denied listing directory",
            })
            skipped += 1
            partial = True
            continue

        for child in children:
            if child.name in exclude or child.name == ".git":
                continue
            stack.append((child, depth + 1))

    return {
        "workspace_root": str(workspace_root),
        "repositories": repositories,
        "warnings": warnings,
        "visited": visited,
        "skipped": skipped,
        "partial": partial,
    }


# ---------------------------------------------------------------------------
# ID proposal
# ---------------------------------------------------------------------------


def propose_ids(repositories: list[dict], known: dict[str, str] | None = None) -> list[dict]:
    """Assign a stable, deterministic id to each discovered repository. An id from `known`
    (explicit osb.yaml repositories or a prior confirmed manifest, keyed by id -> path) is
    reused whenever the path still matches. Everything else gets a basename-derived id,
    with deterministic collision resolution (path-qualified, then numeric suffix)."""

    known = known or {}
    path_to_known_id = {_normalize(path): repo_id for repo_id, path in known.items()}
    used_ids = set(known.keys())

    order = {repo["path"]: i for i, repo in enumerate(repositories)}
    proposals: list[dict] = []
    pending: list[dict] = []

    for repo in repositories:
        norm = _normalize(repo["path"])
        if norm in path_to_known_id:
            proposals.append({**repo, "id": path_to_known_id[norm]})
        else:
            pending.append(repo)

    basename_counts: dict[str, int] = {}
    for repo in pending:
        base = Path(repo["path"]).name or "root"
        basename_counts[base] = basename_counts.get(base, 0) + 1

    assigned_this_round: set[str] = set()
    for repo in sorted(pending, key=lambda r: r["path"]):
        base = Path(repo["path"]).name or "root"
        candidate = base
        if basename_counts[base] > 1 or candidate in used_ids or candidate in assigned_this_round:
            candidate = _normalize(repo["path"]).replace("/", "-") or "root"
        original = candidate
        suffix = 1
        while candidate in used_ids or candidate in assigned_this_round:
            suffix += 1
            candidate = f"{original}-{suffix}"
        assigned_this_round.add(candidate)
        proposals.append({**repo, "id": candidate})

    proposals.sort(key=lambda r: order[r["path"]])
    return proposals


def detect_renames(
    current_repos: list[dict], prior_repositories: list[dict] | None
) -> tuple[list[dict], list[dict]]:
    """Compares current scan results against a prior confirmed manifest's repositories by
    root commit identity. Returns (updated_repos, warnings) — a repo whose path
    disappeared but whose root commit reappears at a new path is flagged as a rename
    candidate (source='renamed') rather than silently treated as a brand-new repository;
    it still requires explicit confirmation like any other manifest change."""

    if not prior_repositories:
        return current_repos, []

    prior_by_path = {_normalize(r["path"]): r for r in prior_repositories}
    prior_root_commits = {
        r.get("root_commit"): r for r in prior_repositories if r.get("root_commit")
    }

    updated: list[dict] = []
    warnings: list[dict] = []
    matched_current_paths = {_normalize(r["path"]) for r in current_repos}

    for repo in current_repos:
        norm = _normalize(repo["path"])
        if norm in prior_by_path:
            updated.append(repo)
            continue
        root_commit = repo.get("root_commit")
        prior_match = prior_root_commits.get(root_commit) if root_commit else None
        if prior_match and _normalize(prior_match["path"]) not in matched_current_paths:
            warnings.append({
                "kind": "rename-candidate",
                "path": repo["path"],
                "detail": (
                    f"repository id '{prior_match['id']}' previously at "
                    f"'{prior_match['path']}' appears moved here (same root commit); "
                    "requires explicit confirmation"
                ),
            })
            updated.append({**repo, "id": prior_match["id"], "source": "renamed", "renamed_from": prior_match["path"]})
        else:
            updated.append(repo)
    return updated, warnings


# ---------------------------------------------------------------------------
# Dependency edges
# ---------------------------------------------------------------------------


def extract_csproj_references(repo_root: Path) -> tuple[list[dict], list[dict]]:
    """Minimal C# extractor (metadata inspection, not a model). Returns
    (project_references, package_references) — each a list of
    {"file": <csproj path relative to repo_root>, "reference": <raw Include value>}."""

    project_refs: list[dict] = []
    package_refs: list[dict] = []
    for csproj in sorted(repo_root.rglob("*.csproj")):
        try:
            text = csproj.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(csproj.relative_to(repo_root))
        for match in _CSPROJ_PROJECT_REF_RE.finditer(text):
            project_refs.append({"file": rel, "reference": match.group(1)})
        for match in _CSPROJ_PACKAGE_REF_RE.finditer(text):
            package_refs.append({"file": rel, "reference": match.group(1)})
    return project_refs, package_refs


def build_edges(workspace_root: Path, repositories: list[dict]) -> tuple[list[dict], list[dict]]:
    """Confirmed edges: a ProjectReference that resolves to a path inside another
    discovered repository. Possible edges: a PackageReference whose name exactly matches
    another discovered repository's id — a naming hint only, never promoted automatically
    (see MULTI_REPO.md §Discovery)."""

    confirmed: list[dict] = []
    possible: list[dict] = []

    canonical_by_id = {
        repo["id"]: (workspace_root / repo["path"]).resolve() for repo in repositories
    }
    ids_lower = {repo["id"].lower(): repo["id"] for repo in repositories}

    for repo in repositories:
        repo_dir = canonical_by_id[repo["id"]]
        project_refs, package_refs = extract_csproj_references(repo_dir)

        for ref in project_refs:
            csproj_dir = (repo_dir / ref["file"]).parent
            try:
                target = (csproj_dir / ref["reference"].replace("\\", "/")).resolve()
            except OSError:
                continue
            for other_id, other_canonical in canonical_by_id.items():
                if other_id == repo["id"]:
                    continue
                try:
                    target.relative_to(other_canonical)
                except ValueError:
                    continue
                confirmed.append({
                    "from": repo["id"],
                    "to": other_id,
                    "source": "project-reference",
                    "evidence": f"{repo['path']}/{ref['file']}: ProjectReference {ref['reference']}",
                })
                break

        for ref in package_refs:
            candidate_id = ids_lower.get(ref["reference"].lower())
            if candidate_id and candidate_id != repo["id"]:
                possible.append({
                    "from": repo["id"],
                    "to": candidate_id,
                    "reason": "PackageReference name matches another discovered repository's id",
                    "evidence": f"{repo['path']}/{ref['file']}: PackageReference {ref['reference']}",
                })

    return confirmed, possible


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------


def compute_manifest_fingerprint(manifest: dict) -> str:
    hasher = hashlib.sha256()
    for repo in sorted(manifest["repositories"], key=lambda r: r["id"]):
        hasher.update(
            f"{repo['id']}\0{repo['path']}\0{repo.get('git_head')}\0{repo.get('source')}\n".encode()
        )
    for edge in sorted(manifest["confirmed_edges"], key=lambda e: (e["from"], e["to"], e["source"])):
        hasher.update(f"{edge['from']}\0{edge['to']}\0{edge['source']}\0{edge['evidence']}\n".encode())
    for edge in sorted(manifest["possible_edges"], key=lambda e: (e["from"], e["to"], e.get("reason", ""))):
        hasher.update(f"{edge['from']}\0{edge['to']}\0{edge.get('reason')}\n".encode())
    return f"wmf-{hasher.hexdigest()[:16]}"


def build_manifest(
    workspace_root: Path,
    *,
    discovery_enabled: bool = True,
    max_depth: int = DEFAULT_MAX_DEPTH,
    exclude: frozenset[str] | set[str] | None = None,
    explicit_repositories: list[dict] | None = None,
    prior_manifest: dict | None = None,
) -> dict:
    """Build a proposed (unconfirmed) manifest: scan results reconciled with explicit
    `osb.yaml` overrides and a prior confirmed manifest, with confirmed/possible
    dependency edges. Never writes anything — callers persist it explicitly (see
    `cmd_confirm`)."""

    explicit_repositories = explicit_repositories or []
    workspace_root = workspace_root.resolve()

    explicit_by_norm_path = {_normalize(r["path"]): r for r in explicit_repositories}
    known: dict[str, str] = {r["id"]: r["path"] for r in explicit_repositories}
    if prior_manifest:
        for repo in prior_manifest.get("repositories", []):
            known.setdefault(repo["id"], repo["path"])

    warnings: list[dict] = []
    scan_status = "complete"

    discovered: list[dict] = []
    if discovery_enabled:
        scan_result = scan(workspace_root, max_depth=max_depth, exclude=exclude)
        discovered = scan_result["repositories"]
        warnings.extend(scan_result["warnings"])
        if scan_result["partial"]:
            scan_status = "partial"

    # Merge explicit repositories not found by the scan (e.g. discovery disabled, or path
    # outside the scanned depth) — reject anything that resolves outside the workspace root.
    discovered_norm_paths = {_normalize(r["path"]) for r in discovered}
    for repo_id, path in {r["id"]: r["path"] for r in explicit_repositories}.items():
        norm = _normalize(path)
        if norm in discovered_norm_paths:
            continue
        try:
            resolved = safe_exec.resolve_within_root(workspace_root, path)
        except safe_exec.PathEscapesRootError:
            warnings.append({
                "kind": "outside-root-rejected",
                "path": path,
                "detail": f"configured repository '{repo_id}' path escapes workspace root; not included",
            })
            continue
        if not (resolved / ".git").exists():
            warnings.append({
                "kind": "outside-root-rejected",
                "path": path,
                "detail": f"configured repository '{repo_id}' path is not a Git root; not included",
            })
            continue
        discovered.append({
            "path": norm,
            "canonical_path": str(resolved),
            "git_head": _git_head(resolved),
            "root_commit": _git_root_commit(resolved),
        })

    proposed = propose_ids(discovered, known)

    reconciled, rename_warnings = detect_renames(
        proposed, prior_manifest.get("repositories") if prior_manifest else None
    )
    warnings.extend(rename_warnings)

    repositories = []
    for repo in reconciled:
        norm = _normalize(repo["path"])
        source = repo.get("source") or ("configured" if norm in explicit_by_norm_path else "discovered")
        entry = {
            "id": repo["id"],
            "path": norm,
            "git_head": repo.get("git_head"),
            "root_commit": repo.get("root_commit"),
            "source": source,
        }
        if repo.get("renamed_from"):
            entry["renamed_from"] = _normalize(repo["renamed_from"])
        repositories.append(entry)

    confirmed_edges = []
    for repo in explicit_repositories:
        for dep in repo.get("depends_on", []) or []:
            confirmed_edges.append({
                "from": repo["id"],
                "to": dep,
                "source": "explicit",
                "evidence": "osb.yaml workspace.repositories[].depends_on",
            })

    project_edges, possible_edges = build_edges(workspace_root, repositories)
    confirmed_edges.extend(project_edges)

    manifest = {
        "schema_version": 1,
        "workspace_root": ".",
        "scan_status": scan_status,
        "repositories": repositories,
        "confirmed_edges": confirmed_edges,
        "possible_edges": possible_edges,
        "confirmed_at": None,
    }
    if warnings:
        manifest["warnings"] = warnings
    manifest["manifest_fingerprint"] = compute_manifest_fingerprint(manifest)
    return manifest


def load_osb_config(osb_yaml_path: Path) -> tuple[bool, int, set[str] | None, list[dict]]:
    """Returns (discovery_enabled, max_depth, exclude, explicit_repositories) from an
    optional osb.yaml. Defaults match DEFAULT_MAX_DEPTH/DEFAULT_EXCLUDES and
    discovery_enabled=True only when a `workspace.discovery` block is present and doesn't
    explicitly disable itself — an omitted `workspace` block does not silently turn on
    filesystem scanning of a project that never asked for it."""

    if not osb_yaml_path.is_file():
        return False, DEFAULT_MAX_DEPTH, None, []

    workspace = yaml_lite.extract_key(osb_yaml_path.read_text(encoding="utf-8"), "workspace") or {}
    discovery = workspace.get("discovery") or {}
    enabled = bool(discovery.get("enabled", False))
    max_depth = int(discovery.get("max_depth", DEFAULT_MAX_DEPTH))
    exclude_list = discovery.get("exclude")
    exclude = set(exclude_list) | DEFAULT_EXCLUDES if exclude_list else None
    explicit_repositories = workspace.get("repositories") or []
    return enabled, max_depth, exclude, explicit_repositories


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cmd_scan(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace_root).resolve()
    osb_yaml_path = Path(args.osb_yaml) if args.osb_yaml else workspace_root / "osb.yaml"
    enabled, max_depth, exclude, explicit_repositories = load_osb_config(osb_yaml_path)
    if args.max_depth is not None:
        max_depth = args.max_depth
    if args.force_enable:
        enabled = True

    manifest = build_manifest(
        workspace_root,
        discovery_enabled=enabled,
        max_depth=max_depth,
        exclude=exclude,
        explicit_repositories=explicit_repositories,
    )

    if args.json:
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    print(f"scan_status: {manifest['scan_status']}")
    print(f"repositories ({len(manifest['repositories'])}):")
    for repo in manifest["repositories"]:
        print(f"  - {repo['id']:20s} {repo['path']:40s} source={repo['source']}")
    if manifest["confirmed_edges"]:
        print("confirmed_edges:")
        for edge in manifest["confirmed_edges"]:
            print(f"  - {edge['from']} -> {edge['to']} ({edge['source']}): {edge['evidence']}")
    if manifest["possible_edges"]:
        print("possible_edges (hints only, not dispatch dependencies):")
        for edge in manifest["possible_edges"]:
            print(f"  - {edge['from']} -> {edge['to']}: {edge['reason']}")
    for warning in manifest.get("warnings", []):
        print(f"warning [{warning['kind']}] {warning['path']}: {warning['detail']}")
    print(f"manifest_fingerprint: {manifest['manifest_fingerprint']}")
    print("\nNo files were written. Re-run with `confirm --yes` to persist this manifest.")
    return 0


def cmd_confirm(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace_root).resolve()
    osb_yaml_path = Path(args.osb_yaml) if args.osb_yaml else workspace_root / "osb.yaml"
    enabled, max_depth, exclude, explicit_repositories = load_osb_config(osb_yaml_path)
    if args.max_depth is not None:
        max_depth = args.max_depth
    if args.force_enable:
        enabled = True

    out_path = Path(args.out) if args.out else workspace_root / ".osb" / "cache" / "workspace-manifest.json"
    prior_manifest = _load_manifest(out_path) if out_path.is_file() else None

    manifest = build_manifest(
        workspace_root,
        discovery_enabled=enabled,
        max_depth=max_depth,
        exclude=exclude,
        explicit_repositories=explicit_repositories,
        prior_manifest=prior_manifest,
    )

    if not args.yes:
        print("refusing to write a manifest without --yes (discovery never auto-confirms).")
        print(f"proposed manifest_fingerprint: {manifest['manifest_fingerprint']}")
        return 1

    errors = schema_validate.validate(manifest, MANIFEST_SCHEMA)
    if errors:
        print("refusing to write an invalid manifest:")
        for error in errors:
            print(f"  - {error}")
        return 1

    from datetime import datetime, timezone

    manifest["confirmed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_manifest(out_path, manifest)
    print(f"wrote {out_path}")
    print(f"manifest_fingerprint: {manifest['manifest_fingerprint']}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    workspace_root = Path(args.workspace_root).resolve()
    manifest = _load_manifest(manifest_path)

    errors = schema_validate.validate(manifest, MANIFEST_SCHEMA)
    if errors:
        print(f"manifest is structurally invalid, {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1

    problems: list[str] = []
    for repo in manifest["repositories"]:
        repo_dir = workspace_root / repo["path"]
        if not repo_dir.is_dir():
            problems.append(f"repository '{repo['id']}': path no longer exists: {repo['path']}")
            continue
        if not _is_git_root(repo_dir):
            problems.append(f"repository '{repo['id']}': {repo['path']} is no longer a Git root")
            continue
        current_head = _git_head(repo_dir)
        if repo.get("git_head") and current_head and repo["git_head"] != current_head:
            problems.append(
                f"repository '{repo['id']}': git_head changed ({repo['git_head']} -> {current_head})"
            )

    if problems:
        print(f"manifest is stale, {len(problems)} issue(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("manifest is structurally valid and consistent with the current workspace.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="workspace_discovery", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common_flags = argparse.ArgumentParser(add_help=False)
    common_flags.add_argument("--osb-yaml", default=None, help="Path to osb.yaml (default: <workspace-root>/osb.yaml)")
    common_flags.add_argument("--max-depth", type=int, default=None)
    common_flags.add_argument(
        "--force-enable",
        action="store_true",
        help="Scan even if osb.yaml has no workspace.discovery.enabled: true (useful for CLI exploration)",
    )

    p_scan = sub.add_parser("scan", parents=[common_flags], help="Read-only scan + proposal")
    p_scan.add_argument("workspace_root")
    p_scan.add_argument("--json", action="store_true")
    p_scan.add_argument("--dry-run", action="store_true", help="No-op: scan never writes anything regardless")
    p_scan.set_defaults(func=cmd_scan)

    p_confirm = sub.add_parser("confirm", parents=[common_flags], help="Scan, then persist the manifest")
    p_confirm.add_argument("workspace_root")
    p_confirm.add_argument("--yes", action="store_true", help="Required to actually write the manifest")
    p_confirm.add_argument("--out", default=None)
    p_confirm.set_defaults(func=cmd_confirm)

    p_validate = sub.add_parser("validate", help="Reconcile a confirmed manifest against current disk state")
    p_validate.add_argument("manifest")
    p_validate.add_argument("--workspace-root", default=".")
    p_validate.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
