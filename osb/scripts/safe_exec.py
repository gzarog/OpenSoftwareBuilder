#!/usr/bin/env python3
"""Shared, dependency-free safety helpers for bounded subprocess execution and canonical
workspace path checks (Phase 0, "Next Improvements" plan).

Used by workspace discovery, impact/test selection, and report collectors so each one
doesn't reimplement path-escape checks or unbounded subprocess calls. This module is
deliberately conservative:

- Every path check resolves symlinks and rejects anything that escapes the declared root.
- `run_bounded` never executes a command unless the caller passes `authorized=True` —
  there is no default-on code path that runs an externally discovered command. Callers are
  responsible for obtaining that authorization from explicit user/project configuration
  before setting the flag; this module only enforces that the flag was set, it does not
  grant it.
- Output and wall-clock time are bounded so one runaway command cannot stall or flood a
  caller with unbounded text.

This is read-only, deterministic tooling — it never contacts a network or a model.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_OUTPUT_CHARS = 20_000


class SafeExecError(RuntimeError):
    pass


class PathEscapesRootError(SafeExecError):
    pass


class UnauthorizedCommandError(SafeExecError):
    pass


def resolve_within_root(root: Path, candidate: str | Path) -> Path:
    """Resolve `candidate` (absolute or relative to `root`) and verify the resolved,
    symlink-free path is `root` itself or a descendant of it. Raises PathEscapesRootError
    otherwise — this is the single check discovery/impact/report collectors should use
    before touching anything derived from configuration or scan results."""

    root_resolved = root.resolve()
    candidate_path = Path(candidate)
    unresolved = candidate_path if candidate_path.is_absolute() else root / candidate_path
    resolved = unresolved.resolve()

    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise PathEscapesRootError(
            f"path escapes workspace root: {candidate!r} resolved to {resolved}, "
            f"outside root {root_resolved}"
        ) from None
    return resolved


def is_within_root(root: Path, candidate: str | Path) -> bool:
    try:
        resolve_within_root(root, candidate)
        return True
    except PathEscapesRootError:
        return False


@dataclass
class BoundedResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    command: list[str] = field(default_factory=list)


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def run_bounded(
    cmd: list[str],
    cwd: Path,
    root: Path,
    *,
    authorized: bool,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
) -> BoundedResult:
    """Run `cmd` in `cwd`, bounded by `timeout_seconds` and `max_output_chars`.

    `authorized` must be explicitly True — callers pass it only after checking the
    project's own config authorized this exact command (e.g. a `test_plan` entry with
    `command_source: project-configured`, or explicit user confirmation of a newly
    discovered command). This function never infers authorization itself and never runs a
    command "just to see" what it does.

    `cwd` must resolve inside `root` — this stops a malformed or malicious config from
    directing execution outside the intended workspace.
    """

    if not authorized:
        raise UnauthorizedCommandError(
            f"refusing to run unauthorized command: {cmd!r} — pass authorized=True only "
            "after explicit user/project-configured approval of this exact command"
        )

    cwd_resolved = resolve_within_root(root, cwd)

    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd_resolved,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, _ = _truncate(exc.stdout or "", max_output_chars)
        stderr, _ = _truncate(exc.stderr or "", max_output_chars)
        return BoundedResult(
            returncode=-1,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
            command=cmd,
        )

    stdout, stdout_truncated = _truncate(proc.stdout, max_output_chars)
    stderr, stderr_truncated = _truncate(proc.stderr, max_output_chars)
    return BoundedResult(
        returncode=proc.returncode,
        stdout=stdout,
        stderr=stderr,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
        command=cmd,
    )
