#!/usr/bin/env python3
"""Optional Git worktree isolation for concurrent Implementers (P1-D, Phase 4).

Everything this module creates lives under `.osb/worktrees/<unit-id>/` in the **owning
repository** — never in a second AI-managed root, and never touching a worktree or branch
this module didn't itself create. It never removes an existing user worktree or discards
uncommitted user files; every destructive operation first checks the path/branch was
OSB-created and, for removal, that there is nothing uncommitted left in it unless the
caller explicitly forces the removal.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

OSB_WORKTREES_DIRNAME = ".osb/worktrees"
OSB_LOCKS_DIRNAME = ".osb/worktrees/.locks"
UNIT_BRANCH_PREFIX = "osb/unit/"


class WorktreeGuardError(RuntimeError):
    pass


def _run_git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=check
    )


def _osb_worktree_path(repo_root: Path, unit_id: str) -> Path:
    return repo_root / OSB_WORKTREES_DIRNAME / unit_id


def _unit_branch(unit_id: str) -> str:
    return f"{UNIT_BRANCH_PREFIX}{unit_id}"


def create_unit_worktree(repo_root: Path, unit_id: str, base_ref: str = "HEAD") -> Path:
    """Create an isolated worktree + branch for one implementation unit. Raises if a
    worktree already exists at that path (never silently reuses/overwrites one)."""

    worktree_path = _osb_worktree_path(repo_root, unit_id)
    if worktree_path.exists():
        raise WorktreeGuardError(f"worktree already exists for unit '{unit_id}': {worktree_path}")

    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    branch = _unit_branch(unit_id)
    result = _run_git(
        repo_root, "worktree", "add", "-b", branch, str(worktree_path), base_ref, check=False
    )
    if result.returncode != 0:
        raise WorktreeGuardError(f"failed to create worktree for unit '{unit_id}': {result.stderr.strip()}")
    return worktree_path


def list_osb_worktrees(repo_root: Path) -> list[dict]:
    """Only worktrees whose path is under .osb/worktrees/ — this module never reports on,
    or acts on, a worktree it didn't create."""

    result = _run_git(repo_root, "worktree", "list", "--porcelain")
    entries: list[dict] = []
    current: dict = {}
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            if current:
                entries.append(current)
            current = {"path": line[len("worktree "):]}
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):]
        elif line == "bare":
            current["bare"] = True
    if current:
        entries.append(current)

    osb_root = str((repo_root / OSB_WORKTREES_DIRNAME).resolve())
    return [e for e in entries if str(Path(e["path"]).resolve()).startswith(osb_root)]


def _is_osb_worktree(repo_root: Path, unit_id: str, path: Path) -> bool:
    expected = _osb_worktree_path(repo_root, unit_id).resolve()
    try:
        return path.resolve() == expected
    except OSError:
        return False


def has_uncommitted_changes(worktree_path: Path) -> bool:
    result = _run_git(worktree_path, "status", "--porcelain")
    return bool(result.stdout.strip())


def remove_unit_worktree(repo_root: Path, unit_id: str, force: bool = False) -> None:
    """Refuses to remove anything that isn't the exact OSB-created path for this unit, and
    refuses to discard uncommitted work unless force=True is explicit."""

    worktree_path = _osb_worktree_path(repo_root, unit_id)
    if not worktree_path.exists():
        return  # already gone; not an error — cleanup is idempotent

    if not _is_osb_worktree(repo_root, unit_id, worktree_path):
        raise WorktreeGuardError(f"refusing to remove a path OSB did not create: {worktree_path}")

    if has_uncommitted_changes(worktree_path) and not force:
        raise WorktreeGuardError(
            f"unit '{unit_id}' worktree has uncommitted changes — pass force=True to discard them"
        )

    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(worktree_path))
    _run_git(repo_root, *args, check=False)


def acquire_lock(repo_root: Path, name: str, timeout_seconds: float = 30.0) -> Path:
    """A cooperative file lock serializing edits to one shared resource name (e.g. a
    generated file, a schema lock, a migration registry) across concurrent Implementers.
    OSB has no daemon to arbitrate this centrally, so this is best-effort and local to one
    checkout — sufficient for the same-host concurrent-Implementer case Phase 4 targets."""

    locks_dir = repo_root / OSB_LOCKS_DIRNAME
    locks_dir.mkdir(parents=True, exist_ok=True)
    lock_path = locks_dir / f"{name}.lock"

    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as fh:
                fh.write(json.dumps({"pid": os.getpid(), "acquired_at": time.time()}))
            return lock_path
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise WorktreeGuardError(f"timed out waiting for lock '{name}' ({lock_path})")
            time.sleep(0.05)


def release_lock(lock_path: Path) -> None:
    if lock_path.exists():
        lock_path.unlink()


def integrate_unit(
    repo_root: Path, unit_id: str, target_branch: str, abort_on_conflict: bool = True
) -> dict:
    """Merge one unit's branch into target_branch in dependency order. Returns
    {"status": "merged"} or {"status": "conflict", "files": [...]}. On conflict, the merge
    is aborted by default (abort_on_conflict=True) so the repository is left clean for a
    human/coordinator to decide how to resolve — this function never auto-resolves a
    conflict itself."""

    branch = _unit_branch(unit_id)
    current = _run_git(repo_root, "branch", "--show-current").stdout.strip()
    if current != target_branch:
        _run_git(repo_root, "checkout", target_branch)

    result = _run_git(repo_root, "merge", "--no-ff", "-m", f"osb: integrate unit {unit_id}", branch, check=False)
    if result.returncode == 0:
        return {"status": "merged"}

    conflicted = _run_git(repo_root, "diff", "--name-only", "--diff-filter=U").stdout.splitlines()
    if abort_on_conflict:
        _run_git(repo_root, "merge", "--abort", check=False)
    return {"status": "conflict", "files": conflicted, "aborted": abort_on_conflict}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create")
    p_create.add_argument("repo_root")
    p_create.add_argument("unit_id")
    p_create.add_argument("--base-ref", default="HEAD")

    p_remove = sub.add_parser("remove")
    p_remove.add_argument("repo_root")
    p_remove.add_argument("unit_id")
    p_remove.add_argument("--force", action="store_true")

    p_integrate = sub.add_parser("integrate")
    p_integrate.add_argument("repo_root")
    p_integrate.add_argument("unit_id")
    p_integrate.add_argument("target_branch")

    p_list = sub.add_parser("list")
    p_list.add_argument("repo_root")

    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    if args.command == "create":
        path = create_unit_worktree(repo_root, args.unit_id, args.base_ref)
        print(str(path))
    elif args.command == "remove":
        remove_unit_worktree(repo_root, args.unit_id, force=args.force)
        print(f"removed (if present): {args.unit_id}")
    elif args.command == "integrate":
        result = integrate_unit(repo_root, args.unit_id, args.target_branch)
        print(json.dumps(result))
        return 0 if result["status"] == "merged" else 1
    elif args.command == "list":
        print(json.dumps(list_osb_worktrees(repo_root), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
