#!/usr/bin/env python3
"""Validate an opt-in multi-repository `workspace` config (P0-A, Phase 3).

Checks repository path/id integrity, dependency references, and dependency-graph cycles
before any role is dispatched — this is deterministic, dependency-free validation only; it
never contacts RagMonk or a model. See osb/docs/MULTI_REPO.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yaml_lite  # noqa: E402


class WorkspaceConfigError(RuntimeError):
    pass


def load_workspace_config(osb_yaml_path: Path) -> dict | None:
    """Returns the `workspace` block, or None if absent (single-repo default)."""

    text = osb_yaml_path.read_text(encoding="utf-8")
    return yaml_lite.extract_key(text, "workspace")


def validate_workspace(workspace: dict, workspace_root: Path) -> list[str]:
    """Returns a list of errors (empty = valid). Never raises on a malformed config —
    every problem is collected so a single run reports everything wrong at once."""

    errors: list[str] = []

    mode = workspace.get("mode")
    if mode not in ("single-repo", "multi-repo"):
        errors.append(f"workspace.mode must be 'single-repo' or 'multi-repo', got {mode!r}")
        return errors
    if mode == "single-repo":
        return errors  # nothing further to validate; multi-repo fields are optional here

    repositories = workspace.get("repositories") or []
    if not isinstance(repositories, list) or not repositories:
        errors.append("workspace.repositories must be a non-empty list when mode is multi-repo")
        return errors

    seen_ids: set[str] = set()
    seen_paths: dict[str, str] = {}
    repo_by_id: dict[str, dict] = {}

    for entry in repositories:
        if not isinstance(entry, dict) or "id" not in entry or "path" not in entry:
            errors.append(f"each workspace.repositories entry needs 'id' and 'path': {entry!r}")
            continue
        repo_id = entry["id"]
        path = entry["path"]

        if repo_id in seen_ids:
            errors.append(f"duplicate repository id: '{repo_id}'")
        seen_ids.add(repo_id)
        repo_by_id[repo_id] = entry

        for other_id, other_path in seen_paths.items():
            if _paths_overlap(path, other_path):
                errors.append(f"repository paths overlap/nest: '{repo_id}' ({path!r}) and '{other_id}' ({other_path!r})")
        seen_paths[repo_id] = path

        repo_dir = workspace_root / path
        if not repo_dir.is_dir():
            errors.append(f"repository '{repo_id}': path does not exist: {path}")
        elif not (repo_dir / ".git").exists():
            errors.append(f"repository '{repo_id}': {path} is not a Git root (no .git)")

    for repo_id, entry in repo_by_id.items():
        for dep in entry.get("depends_on", []) or []:
            if dep not in repo_by_id:
                errors.append(f"repository '{repo_id}' depends_on unknown repository '{dep}'")

    cycle = _find_cycle(repo_by_id)
    if cycle:
        errors.append(f"dependency cycle detected: {' -> '.join(cycle)}")

    for check in workspace.get("integration_checks", []) or []:
        if not isinstance(check, dict) or "name" not in check or "command" not in check:
            errors.append(f"each workspace.integration_checks entry needs 'name' and 'command': {check!r}")

    return errors


def _paths_overlap(a: str, b: str) -> bool:
    a_parts = Path(a).parts
    b_parts = Path(b).parts
    shorter, longer = (a_parts, b_parts) if len(a_parts) <= len(b_parts) else (b_parts, a_parts)
    return longer[: len(shorter)] == shorter


def _find_cycle(repo_by_id: dict[str, dict]) -> list[str] | None:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {repo_id: WHITE for repo_id in repo_by_id}
    path: list[str] = []

    def visit(repo_id: str) -> list[str] | None:
        color[repo_id] = GRAY
        path.append(repo_id)
        for dep in repo_by_id[repo_id].get("depends_on", []) or []:
            if dep not in color:
                continue  # unknown dep already reported separately
            if color[dep] == GRAY:
                return path[path.index(dep) :] + [dep]
            if color[dep] == WHITE:
                found = visit(dep)
                if found:
                    return found
        path.pop()
        color[repo_id] = BLACK
        return None

    for repo_id in repo_by_id:
        if color[repo_id] == WHITE:
            found = visit(repo_id)
            if found:
                return found
    return None


def topological_order(repo_by_id: dict[str, dict]) -> list[str]:
    """Dependency-first order for dispatch (contracts before its dependents, etc.).
    Callers should run _find_cycle()/validate_workspace() first — this raises if a cycle
    exists rather than silently truncating the order."""

    if _find_cycle(repo_by_id):
        raise WorkspaceConfigError("cannot compute a topological order: dependency cycle present")

    order: list[str] = []
    visited: set[str] = set()

    def visit(repo_id: str) -> None:
        if repo_id in visited:
            return
        for dep in repo_by_id[repo_id].get("depends_on", []) or []:
            if dep in repo_by_id:
                visit(dep)
        visited.add(repo_id)
        order.append(repo_id)

    for repo_id in repo_by_id:
        visit(repo_id)
    return order


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("osb_yaml", help="Path to the workspace's osb.yaml")
    parser.add_argument("--workspace-root", default=".")
    args = parser.parse_args(argv)

    workspace = load_workspace_config(Path(args.osb_yaml))
    if workspace is None:
        print("no 'workspace' block present — single-repo mode (default), nothing to validate")
        return 0

    errors = validate_workspace(workspace, Path(args.workspace_root).resolve())
    if errors:
        print(f"workspace config invalid, {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    if workspace.get("mode") == "multi-repo":
        repo_by_id = {r["id"]: r for r in workspace["repositories"]}
        print("workspace config valid. Dispatch order: " + " -> ".join(topological_order(repo_by_id)))
    else:
        print("workspace config valid (single-repo).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
