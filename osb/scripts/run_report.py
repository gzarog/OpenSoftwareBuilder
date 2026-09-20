#!/usr/bin/env python3
"""Per-task execution report (Next Improvements, Phase 5).

`record`/`render`/`summarize` produce a concise, honest report of one actual `/osb` run
from validated task state plus concise event records — never by re-dispatching a role,
re-running a test, or re-indexing RagMonk (osb/references/quality.md's completion gate is
unaffected by anything here). A missing measurement is always the literal string
`"unavailable"`, never `0` (osb/docs/METRICS.md §Labelling discipline) — a `0` claims
"measured zero," a different, false statement.

Distinct from `osb/scripts/benchmark_report.py` (`osb/schemas/run-metrics.schema.json`),
which is for before/after **benchmark fixture** comparisons and requires a `fixture_id`;
this module is for an ordinary task's own report and never forces that linkage.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schema_validate  # noqa: E402

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "execution-report.schema.json"
EXECUTION_REPORT_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

UNAVAILABLE = "unavailable"


class RunReportError(RuntimeError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Event log
# ---------------------------------------------------------------------------


def load_events(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_event(path: Path, event: dict) -> None:
    """Appends one concise event record. No schema is enforced here (events are an
    intentionally loose, checkpoint-boundary log — osb/docs/EXECUTION_REPORTS.md), but raw
    logs/full agent messages must never be written here; keep records to the measured
    fields a report actually aggregates."""

    event = dict(event)
    event.setdefault("timestamp", now_utc())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def _sum_metric(events: list[dict], key: str) -> float | str:
    """Sums `key` across events that report it as a number. If no event reports `key` at
    all (or every event that names it explicitly reports "unavailable"), the aggregate is
    "unavailable" — never fabricated as 0."""

    present = [e[key] for e in events if key in e]
    if not present:
        return UNAVAILABLE
    numeric = [v for v in present if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not numeric:
        return UNAVAILABLE
    return sum(numeric)


def _count_events(events: list[dict], kind: str) -> int:
    return sum(1 for e in events if e.get("kind") == kind)


def _role_dispatch_count(events: list[dict]) -> float | str:
    explicit = _sum_metric(events, "role_dispatches")
    if explicit != UNAVAILABLE:
        return explicit
    count = _count_events(events, "role-dispatch")
    return count if count > 0 else UNAVAILABLE


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def render(
    state: dict,
    events: list[dict],
    *,
    task_id: str | None = None,
    host: str | None = None,
    models: dict | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    workspace_manifest_fingerprint: str | None = None,
    preserved_worktree_paths: list[str] | None = None,
    resume_instruction: str | None = None,
    partial_scan_or_impact_unknowns: list[str] | None = None,
    integration_checks_run: list[str] | None = None,
    missing_test_evidence: list[str] | None = None,
    metric_sources: dict | None = None,
    evidence_refs: list[str] | None = None,
    generated_at: str | None = None,
) -> dict:
    """Assembles one schema-conformant execution report purely from `state`
    (`osb/schemas/task-state.schema.json`) and `events` — deterministic and idempotent:
    re-rendering the same state/events (aside from `report_generated_at`, unless the
    caller pins it) produces the same meaningful fields, and this never dispatches a role,
    runs a test, or changes task acceptance status."""

    task_id = task_id or state["task_id"]
    quality = state["quality"]
    recovery = state.get("recovery", {})

    if state.get("phase") == "complete":
        final_status = "complete"
    elif state.get("phase") == "blocked" or recovery.get("status") == "blocked":
        final_status = "blocked"
    elif any(e.get("kind") in ("failed", "error") for e in events):
        final_status = "failed"
    else:
        final_status = "interrupted"

    required_ac_ids = sorted(quality.get("required_ac_ids", []))
    unverified_ac_ids = sorted(quality.get("unverified_ac_ids", []))
    verified_ac_ids = sorted(set(required_ac_ids) - set(unverified_ac_ids))

    elapsed_seconds: float | str = UNAVAILABLE
    if started_at and ended_at:
        try:
            start_dt = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ")
            end_dt = datetime.strptime(ended_at, "%Y-%m-%dT%H:%M:%SZ")
            elapsed_seconds = (end_dt - start_dt).total_seconds()
        except ValueError:
            elapsed_seconds = UNAVAILABLE

    units = []
    for unit_id, info in (state.get("units") or {}).items():
        units.append({"id": unit_id, "status": info.get("status"), "repository_id": info.get("repository_id")})
    units.sort(key=lambda u: u["id"])

    workspace = state.get("workspace") or {}
    repositories_affected = sorted(workspace.get("repositories", {}).keys()) if workspace else []

    unresolved_blockers = [str(r) for r in quality.get("unresolved_context_requests", [])]
    if recovery.get("last_blocker"):
        unresolved_blockers.append(str(recovery["last_blocker"]))

    report = {
        "task": {
            "task_id": task_id,
            "host": host,
            "models": models or {},
            "started_at": started_at,
            "ended_at": ended_at,
            "elapsed_seconds": elapsed_seconds,
            "final_status": final_status,
            "report_generated_at": generated_at or now_utc(),
        },
        "scope": {
            "repositories_affected": repositories_affected,
            "workspace_manifest_fingerprint": workspace_manifest_fingerprint,
            "changed_files_count": (
                sum(len(info.get("files", [])) for info in state["units"].values())
                if state.get("units") else UNAVAILABLE
            ),
            "units": units,
            "current_patch_fingerprint": quality.get("current_patch_fingerprint"),
            "workspace_fingerprint": workspace.get("workspace_fingerprint"),
            "local_changes_only": True,
        },
        "quality": {
            "required_ac_ids": required_ac_ids,
            "verified_ac_ids": verified_ac_ids,
            "unverified_ac_ids": unverified_ac_ids,
            "review_status": state.get("review", {}).get("status", "pending"),
            "review_scope": state.get("review", {}).get("scope"),
            "review_fingerprint": quality.get("final_review_fingerprint"),
            "qa_status": state.get("qa", {}).get("status", "pending"),
            "qa_fingerprint": quality.get("final_qa_fingerprint"),
            "integration_checks_run": integration_checks_run or [],
            "missing_test_evidence": missing_test_evidence or [],
        },
        "efficiency": {
            "elapsed_seconds": elapsed_seconds,
            "role_dispatches": _role_dispatch_count(events),
            "tool_calls": _sum_metric(events, "tool_calls"),
            "input_tokens": _sum_metric(events, "input_tokens"),
            "output_tokens": _sum_metric(events, "output_tokens"),
            "ragmonk_chars_retrieved": _sum_metric(events, "ragmonk_chars_retrieved"),
            "capsule_cache_hits": _sum_metric(events, "capsule_cache_hits"),
            "capsule_cache_misses": _sum_metric(events, "capsule_cache_misses"),
            "context_expansions": _sum_metric(events, "context_expansions"),
            "repair_attempts": _sum_metric(events, "repair_attempts"),
            "repeated_failure_blocks": _sum_metric(events, "repeated_failure_blocks"),
        },
        "recovery": {
            "unresolved_blockers": unresolved_blockers,
            "partial_scan_or_impact_unknowns": partial_scan_or_impact_unknowns or [],
            "preserved_worktree_paths": preserved_worktree_paths or [],
            "resume_instruction": resume_instruction,
        },
        "provenance": {
            "evidence_refs": evidence_refs or [],
            "metric_sources": metric_sources or {},
        },
    }
    return report


def summarize(report: dict) -> str:
    """Renders the concise, user-facing Markdown summary (osb/docs/EXECUTION_REPORTS.md
    §Example). Deterministic from the report alone — never re-derives anything from state
    or events."""

    task = report["task"]
    scope = report["scope"]
    quality = report["quality"]
    efficiency = report["efficiency"]
    recovery = report["recovery"]

    lines = [f"# OSB {task['task_id']} — {task['final_status'].upper()}"]

    if scope["repositories_affected"]:
        lines.append(f"Repositories: {', '.join(scope['repositories_affected'])}")
    if scope["units"]:
        counts: dict[str, int] = {}
        for unit in scope["units"]:
            counts[unit["status"]] = counts.get(unit["status"], 0) + 1
        lines.append("Units: " + ", ".join(f"{count} {status}" for status, count in sorted(counts.items())))

    lines.append(f"Review: {quality['review_status']} (scope: {quality.get('review_scope') or 'n/a'})")

    total_ac = len(quality["required_ac_ids"])
    verified_ac = len(quality["verified_ac_ids"])
    qa_line = f"QA: {verified_ac}/{total_ac} required AC(s) verified"
    if quality["unverified_ac_ids"]:
        qa_line += f" — unverified: {', '.join(quality['unverified_ac_ids'])}"
    lines.append(qa_line)

    if quality["missing_test_evidence"]:
        lines.append(f"Missing test evidence: {', '.join(quality['missing_test_evidence'])}")

    lines.append(f"Elapsed: {efficiency['elapsed_seconds']}")
    token_line = f"Tokens: in={efficiency['input_tokens']} out={efficiency['output_tokens']}"
    lines.append(token_line)

    if recovery["unresolved_blockers"]:
        lines.append("Blockers: " + "; ".join(recovery["unresolved_blockers"]))
    if recovery["resume_instruction"]:
        lines.append(f"Safe resume: {recovery['resume_instruction']}")

    lines.append(f"Report generated: {task['report_generated_at']}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _runs_dir(workspace_root: Path, task_id: str) -> Path:
    return workspace_root / ".osb" / "runs" / task_id


def cmd_record(args: argparse.Namespace) -> int:
    event = json.loads(Path(args.event).read_text(encoding="utf-8"))
    workspace_root = Path(args.workspace_root).resolve()
    append_event(_runs_dir(workspace_root, args.task_id) / "events.jsonl", event)
    print("recorded.")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    workspace_root = Path(args.workspace_root).resolve()
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    events = load_events(_runs_dir(workspace_root, state["task_id"]) / "events.jsonl")

    report = render(state, events, **request)

    errors = schema_validate.validate(report, EXECUTION_REPORT_SCHEMA)
    if errors:
        print(f"refusing to write an invalid report, {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1

    runs_dir = _runs_dir(workspace_root, state["task_id"])
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (runs_dir / "report.md").write_text(summarize(report), encoding="utf-8")
    print(f"wrote {runs_dir / 'report.json'} and {runs_dir / 'report.md'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_report", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_record = sub.add_parser("record", help="Append one concise execution event")
    p_record.add_argument("task_id")
    p_record.add_argument("event")
    p_record.add_argument("--workspace-root", default=".")
    p_record.set_defaults(func=cmd_record)

    p_render = sub.add_parser("render", help="Render report.json + report.md from state + events")
    p_render.add_argument("state")
    p_render.add_argument("request", help="JSON file of extra render() keyword arguments (host, models, ...)")
    p_render.add_argument("--workspace-root", default=".")
    p_render.set_defaults(func=cmd_render)

    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
