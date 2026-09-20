#!/usr/bin/env python3
"""Task-specific impact analysis and test selection (Next Improvements, Phase 2).

This is deterministic parsing/normalization, not a second code index: OSB still delegates
symbol/caller/callee/semantic queries to RagMonk (`osb/references/ragmonk.md`,
`osb/references/impact.md`). What lives here is (a) a minimal, metadata-only C#
`<ProjectReference>` graph — reused from `workspace_discovery.py`'s extractor — used to
compute confirmed project-reference impacts and candidate test projects without a model
call, and (b) the merge/fingerprint/validation plumbing that combines those deterministic
findings with whatever confirmed/possible impacts and unknowns an agent's RagMonk queries
supplied, into one schema-conformant `.osb/cache/impact/<task-id>.json` record
(`osb/schemas/impact-plan.schema.json`).

Narrowing test selection here never narrows the mandatory final combined-change review or
final QA on every required acceptance criterion (`osb/references/quality.md`) — this is an
*intermediate*-stage artifact only, and every `test_plan` entry is `stage: intermediate`.
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
import workspace_discovery  # noqa: E402

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "impact-plan.schema.json"
IMPACT_PLAN_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

DEFAULT_MAX_DEPENDENTS = 500

_TEST_SUFFIXES = ("tests", "test", "spec", "specs")


class ImpactPlanError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# C# project-reference graph (deterministic, metadata-only)
# ---------------------------------------------------------------------------


def build_reference_graph(repo_root: Path) -> dict[str, set[str]]:
    """Forward edges {csproj_rel_path: {referenced_csproj_rel_path, ...}} within one
    repository, reusing workspace_discovery's extractor so the reference regex has one
    definition. An unresolved/external reference (e.g. a NuGet-only path) is dropped —
    it doesn't identify an in-repo dependent."""

    repo_root_resolved = repo_root.resolve()
    graph: dict[str, set[str]] = {}
    for csproj in repo_root_resolved.rglob("*.csproj"):
        rel = str(csproj.relative_to(repo_root_resolved)).replace("\\", "/")
        graph.setdefault(rel, set())

    project_refs, _package_refs = workspace_discovery.extract_csproj_references(repo_root_resolved)
    for ref in project_refs:
        csproj_dir = (repo_root_resolved / ref["file"]).parent
        try:
            target = (csproj_dir / ref["reference"].replace("\\", "/")).resolve()
            target_rel = str(target.relative_to(repo_root_resolved)).replace("\\", "/")
        except (OSError, ValueError):
            continue
        graph.setdefault(ref["file"], set()).add(target_rel)
    return graph


def _reverse_graph(graph: dict[str, set[str]]) -> dict[str, set[str]]:
    reversed_graph: dict[str, set[str]] = {node: set() for node in graph}
    for node, targets in graph.items():
        for target in targets:
            reversed_graph.setdefault(target, set()).add(node)
    return reversed_graph


def transitive_dependents(
    graph: dict[str, set[str]], seeds: set[str], *, max_nodes: int = DEFAULT_MAX_DEPENDENTS
) -> tuple[set[str], bool]:
    """Every node that (transitively) references one of `seeds`. Bounded by `max_nodes` —
    hitting the bound sets truncated=True rather than silently stopping (osb/references/
    quality.md §Context expansion triggers applies at the agent layer when this happens)."""

    reversed_graph = _reverse_graph(graph)
    visited: set[str] = set()
    queue = list(seeds)
    truncated = False
    while queue:
        node = queue.pop()
        if node in visited:
            continue
        if len(visited) >= max_nodes:
            truncated = True
            break
        visited.add(node)
        for dependent in reversed_graph.get(node, ()):
            if dependent not in visited:
                queue.append(dependent)
    visited -= seeds
    return visited, truncated


def is_test_project(rel_path: str) -> bool:
    name = Path(rel_path).stem.lower()
    if any(name.endswith(suffix) for suffix in _TEST_SUFFIXES):
        return True
    parts = {p.lower() for p in Path(rel_path).parts}
    return bool(parts & {"tests", "test"})


def find_owning_project(repo_root: Path, changed_file_rel: str) -> str | None:
    """Nearest ancestor `.csproj` for a changed file, or the file itself if it already is
    one. Returns None if no `.csproj` is found in any ancestor within the repository —
    callers surface that as an `unknowns[]` entry rather than guessing."""

    if changed_file_rel.endswith(".csproj"):
        return changed_file_rel

    repo_root_resolved = repo_root.resolve()
    current = (repo_root_resolved / changed_file_rel).resolve().parent
    while True:
        candidates = sorted(current.glob("*.csproj"))
        if candidates:
            return str(candidates[0].relative_to(repo_root_resolved)).replace("\\", "/")
        if current == repo_root_resolved:
            return None
        current = current.parent


def analyze_repo_impact(
    repo_id: str, repo_root: Path, changed_files: list[str], *, max_dependents: int = DEFAULT_MAX_DEPENDENTS
) -> dict:
    """Deterministic, single-repository impact analysis: which projects transitively
    depend (via `<ProjectReference>`) on a changed file's owning project, and which of
    those are test projects (candidate intermediate test targets)."""

    graph = build_reference_graph(repo_root)
    owning_projects: set[str] = set()
    unknowns: list[dict] = []

    for changed in changed_files:
        owner = find_owning_project(repo_root, changed)
        if owner is None:
            unknowns.append({
                "question": f"which project owns changed file '{changed}' in repository '{repo_id}'?",
                "reason": "no .csproj found in any ancestor directory within the repository",
            })
        else:
            owning_projects.add(owner)

    dependents, truncated = transitive_dependents(graph, owning_projects, max_nodes=max_dependents)

    confirmed_impacts = [
        {
            "repository_id": repo_id,
            "path": dependent,
            "symbol": None,
            "kind": "test-dependent" if is_test_project(dependent) else "project-reference",
            "evidence": f"{dependent} transitively references a changed project via <ProjectReference>",
        }
        for dependent in sorted(dependents)
    ]

    test_targets = sorted(
        {d for d in dependents if is_test_project(d)} | {p for p in owning_projects if is_test_project(p)}
    )

    return {
        "confirmed_impacts": confirmed_impacts,
        "test_targets": test_targets,
        "unknowns": unknowns,
        "truncated": truncated,
        "owning_projects": sorted(owning_projects),
    }


def build_workspace_reference_graph(workspace_root: Path, repositories: list[dict]) -> dict[str, set[str]]:
    """Cross-repository forward edges, so a shared-contract repository's dependents in
    *other* discovered repositories are found, not just dependents within the same repo.
    Nodes are `"<repository_id>::<rel_path>"` strings; a reference that doesn't resolve to
    any known project in any repository (external/unresolved) is dropped."""

    canonical_by_repo = {repo["id"]: (workspace_root / repo["path"]).resolve() for repo in repositories}
    node_by_canonical: dict[Path, str] = {}
    graph: dict[str, set[str]] = {}

    for repo in repositories:
        repo_root = canonical_by_repo[repo["id"]]
        for csproj in repo_root.rglob("*.csproj"):
            rel = str(csproj.relative_to(repo_root)).replace("\\", "/")
            node_key = f"{repo['id']}::{rel}"
            graph.setdefault(node_key, set())
            node_by_canonical[csproj.resolve()] = node_key

    for repo in repositories:
        repo_root = canonical_by_repo[repo["id"]]
        project_refs, _package_refs = workspace_discovery.extract_csproj_references(repo_root)
        for ref in project_refs:
            csproj_path = (repo_root / ref["file"]).resolve()
            node_key = node_by_canonical.get(csproj_path)
            if node_key is None:
                continue
            try:
                target = (csproj_path.parent / ref["reference"].replace("\\", "/")).resolve()
            except OSError:
                continue
            target_key = node_by_canonical.get(target)
            if target_key is None:
                continue
            graph[node_key].add(target_key)

    return graph


def analyze_workspace_impact(
    workspace_root: Path,
    repositories: list[dict],
    changed_files: dict[str, list[str]],
    *,
    max_dependents: int = DEFAULT_MAX_DEPENDENTS,
) -> dict:
    """Cross-repository counterpart of `analyze_repo_impact`: finds every project, in any
    discovered repository, that transitively depends on a changed file's owning project
    via `<ProjectReference>` — this is what makes a shared-contract change visible to its
    consumers in other repositories, not just within the same one."""

    canonical_by_repo = {repo["id"]: (workspace_root / repo["path"]).resolve() for repo in repositories}
    graph = build_workspace_reference_graph(workspace_root, repositories)

    owning_nodes: set[str] = set()
    unknowns: list[dict] = []
    for repo_id, files in changed_files.items():
        repo_root = canonical_by_repo.get(repo_id)
        if repo_root is None:
            continue  # unknown repository id is reported by the caller
        for changed in files:
            owner = find_owning_project(repo_root, changed)
            if owner is None:
                unknowns.append({
                    "question": f"which project owns changed file '{changed}' in repository '{repo_id}'?",
                    "reason": "no .csproj found in any ancestor directory within the repository",
                })
            else:
                owning_nodes.add(f"{repo_id}::{owner}")

    dependents, truncated = transitive_dependents(graph, owning_nodes, max_nodes=max_dependents)

    confirmed_impacts: list[dict] = []
    test_targets_by_repo: dict[str, set[str]] = {}
    for node in sorted(dependents):
        dep_repo_id, rel = node.split("::", 1)
        kind = "test-dependent" if is_test_project(rel) else "project-reference"
        confirmed_impacts.append({
            "repository_id": dep_repo_id,
            "path": rel,
            "symbol": None,
            "kind": kind,
            "evidence": f"{dep_repo_id}/{rel} transitively references a changed project via <ProjectReference>",
        })
        if kind == "test-dependent":
            test_targets_by_repo.setdefault(dep_repo_id, set()).add(rel)

    for node in owning_nodes:
        owner_repo_id, rel = node.split("::", 1)
        if is_test_project(rel):
            test_targets_by_repo.setdefault(owner_repo_id, set()).add(rel)

    return {
        "confirmed_impacts": confirmed_impacts,
        "test_targets_by_repo": {repo_id: sorted(targets) for repo_id, targets in test_targets_by_repo.items()},
        "unknowns": unknowns,
        "truncated": truncated,
    }


def build_test_plan_entries(
    repo_id: str, repo_path: str, test_targets: list[str], *, start_id: int = 1, covers_ac_ids: list[str] | None = None
) -> tuple[list[dict], int]:
    entries = []
    next_id = start_id
    for target in test_targets:
        entries.append({
            "id": f"T{next_id}",
            "stage": "intermediate",
            "repository_id": repo_id,
            "targets": [target],
            "command_source": "discovered-suggestion",
            "command": f"dotnet test {target} --verbosity quiet",
            "cwd": repo_path,
            "covers_ac_ids": covers_ac_ids or [],
            "reason": "changed project has a transitive project-reference dependent test project",
            "status": "proposed",
        })
        next_id += 1
    return entries, next_id


# ---------------------------------------------------------------------------
# Plan assembly
# ---------------------------------------------------------------------------


def compute_plan_fingerprint(plan: dict) -> str:
    hasher = hashlib.sha256()
    hasher.update(plan["task_id"].encode())
    hasher.update(b"\0")
    hasher.update(str(plan.get("workspace_manifest_fingerprint")).encode())
    hasher.update(b"\n")
    for item in sorted(plan["confirmed_impacts"], key=lambda i: (i["repository_id"], i["path"], i["kind"])):
        hasher.update(json.dumps(item, sort_keys=True).encode())
        hasher.update(b"\n")
    for item in sorted(plan["possible_impacts"], key=lambda i: (i["repository_id"], i["path"], i["reason"])):
        hasher.update(json.dumps(item, sort_keys=True).encode())
        hasher.update(b"\n")
    for item in sorted(plan["test_plan"], key=lambda i: i["id"]):
        hasher.update(json.dumps(item, sort_keys=True).encode())
        hasher.update(b"\n")
    return f"ifp-{hasher.hexdigest()[:16]}"


def build_impact_plan(
    task_id: str,
    repositories: list[dict],
    changed_files: dict[str, list[str]],
    *,
    workspace_root: Path,
    workspace_manifest_fingerprint: str | None = None,
    source_revisions: dict[str, str] | None = None,
    seeds: list[dict] | None = None,
    ac_to_repository_map: dict[str, list[str]] | None = None,
    required_integration_boundaries: list[str] | None = None,
    suggested_units: list[str] | None = None,
    external_confirmed_impacts: list[dict] | None = None,
    external_possible_impacts: list[dict] | None = None,
    external_unknowns: list[dict] | None = None,
    external_truncated: bool = False,
    max_dependents_per_repo: int = DEFAULT_MAX_DEPENDENTS,
) -> dict:
    """Assemble one schema-conformant impact-plan record. `repositories` is
    `[{"id": ..., "path": ...}]` (typically the confirmed workspace manifest's list).
    `changed_files` maps repository id to the changed/seed file paths (relative to that
    repository) that should drive the deterministic C# reference-graph analysis.
    `external_*` carries whatever an agent's own RagMonk queries already established —
    this function merges rather than replaces it, and never demotes an external confirmed
    impact to possible or drops an external unknown."""

    repo_by_id = {r["id"]: r for r in repositories}
    confirmed_impacts: list[dict] = list(external_confirmed_impacts or [])
    possible_impacts: list[dict] = list(external_possible_impacts or [])
    unknowns: list[dict] = list(external_unknowns or [])
    test_plan: list[dict] = []
    truncated = external_truncated
    affected: set[str] = set(changed_files.keys())
    next_test_id = 1

    for repo_id in changed_files:
        if repo_id not in repo_by_id:
            unknowns.append({
                "question": f"repository '{repo_id}' referenced by changed_files is not in the workspace manifest",
                "reason": "unknown repository id",
            })

    known_changed_files = {repo_id: files for repo_id, files in changed_files.items() if repo_id in repo_by_id}
    if known_changed_files:
        for repo in repositories:
            safe_exec.resolve_within_root(workspace_root, repo["path"])  # reject an escaping configured path early

        analysis = analyze_workspace_impact(
            workspace_root, repositories, known_changed_files, max_dependents=max_dependents_per_repo
        )
        confirmed_impacts.extend(analysis["confirmed_impacts"])
        unknowns.extend(analysis["unknowns"])
        truncated = truncated or analysis["truncated"]

        for repo_id, targets in sorted(analysis["test_targets_by_repo"].items()):
            entries, next_test_id = build_test_plan_entries(
                repo_id, repo_by_id[repo_id]["path"], targets, start_id=next_test_id
            )
            test_plan.extend(entries)

    for impact in confirmed_impacts + possible_impacts:
        affected.add(impact["repository_id"])
    for seed in seeds or []:
        affected.add(seed["repository_id"])

    plan = {
        "task_id": task_id,
        "workspace_manifest_fingerprint": workspace_manifest_fingerprint,
        "repositories": sorted(repo_by_id.keys()),
        "source_revisions": source_revisions or {},
        "seeds": seeds or [],
        "confirmed_impacts": confirmed_impacts,
        "possible_impacts": possible_impacts,
        "unknowns": unknowns,
        "truncated": truncated,
        "affected_repositories": sorted(affected),
        "suggested_units": suggested_units or [],
        "required_integration_boundaries": required_integration_boundaries or [],
        "ac_to_repository_map": ac_to_repository_map or {},
        "test_plan": test_plan,
    }
    plan["plan_fingerprint"] = compute_plan_fingerprint(plan)
    return plan


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_build(args: argparse.Namespace) -> int:
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    workspace_root = Path(args.workspace_root).resolve()

    plan = build_impact_plan(
        request["task_id"],
        request["repositories"],
        request.get("changed_files", {}),
        workspace_root=workspace_root,
        workspace_manifest_fingerprint=request.get("workspace_manifest_fingerprint"),
        source_revisions=request.get("source_revisions"),
        seeds=request.get("seeds"),
        ac_to_repository_map=request.get("ac_to_repository_map"),
        required_integration_boundaries=request.get("required_integration_boundaries"),
        suggested_units=request.get("suggested_units"),
        external_confirmed_impacts=request.get("external_confirmed_impacts"),
        external_possible_impacts=request.get("external_possible_impacts"),
        external_unknowns=request.get("external_unknowns"),
        external_truncated=request.get("external_truncated", False),
    )

    errors = schema_validate.validate(plan, IMPACT_PLAN_SCHEMA)
    if errors:
        print(f"refusing to write an invalid impact plan, {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1

    out_path = Path(args.out) if args.out else workspace_root / ".osb" / "cache" / "impact" / f"{plan['task_id']}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"plan_fingerprint: {plan['plan_fingerprint']}")
    if plan["truncated"]:
        print("truncated: true — resolve via needs-evidence before treating impact as complete")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    errors = schema_validate.validate(plan, IMPACT_PLAN_SCHEMA)
    if errors:
        print(f"impact plan invalid, {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("impact plan valid.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="impact_plan", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Assemble and write an impact plan from a request JSON file")
    p_build.add_argument("request")
    p_build.add_argument("--workspace-root", default=".")
    p_build.add_argument("--out", default=None)
    p_build.set_defaults(func=cmd_build)

    p_validate = sub.add_parser("validate", help="Validate an existing impact plan against the schema")
    p_validate.add_argument("plan")
    p_validate.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
