#!/usr/bin/env python3
"""Bounded failure recovery without weakening quality gates (Next Improvements, Phase 4).

Tracks retry/context-expansion counters keyed by **task + role + finding/AC/question +
source fingerprint** — never a global attempt counter that could block resolution of an
unrelated failure. This module never dispatches a role, never fixes anything, and never
turns a `blocked`/`needs-evidence` result into a pass; it only decides whether another
targeted attempt is authorized, and appends the append-only audit trail at
`.osb/runs/<task-id>/recovery.jsonl` (`osb/schemas/recovery-event.schema.json`). See
`osb/docs/RECOVERY.md`.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schema_validate  # noqa: E402

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "recovery-event.schema.json"
RECOVERY_EVENT_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

DEFAULT_MAX_REPAIR_ATTEMPTS_PER_FINDING = 3
DEFAULT_MAX_IDENTICAL_FAILURE_REPEATS = 2
DEFAULT_MAX_CONTEXT_EXPANSIONS_PER_QUESTION = 5

RETRY = "retry"
STOP_IDENTICAL_FAILURE = "stop-identical-failure"
ATTEMPTS_EXHAUSTED = "attempts-exhausted"
EXPAND_CONTEXT = "expand-context"
QUESTION_UNRESOLVED = "question-unresolved"


class RecoveryPolicyError(RuntimeError):
    pass


def normalize_failure_signature(text: str) -> str:
    """Deterministic normalization so trivially reworded identical failures are still
    recognized as the same signature (whitespace/case collapse only — never a fuzzy or
    semantic match, which could wrongly conflate two different root causes)."""

    return " ".join((text or "").lower().split())


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Event log (append-only JSONL)
# ---------------------------------------------------------------------------


def load_events(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_event(path: Path, event: dict) -> list[str]:
    """Validates then appends one event as a new line. Returns schema errors (empty on
    success) and never writes an invalid event — an append-only log must stay
    machine-checkable end to end."""

    errors = schema_validate.validate(event, RECOVERY_EVENT_SCHEMA)
    if errors:
        return errors
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")
    return []


def filter_events(events: list[dict], *, task_id: str, role: str, target_kind: str, target_id: str) -> list[dict]:
    return [
        e for e in events
        if e["task_id"] == task_id and e["role"] == role
        and e["target_kind"] == target_kind and e["target_id"] == target_id
    ]


# ---------------------------------------------------------------------------
# Repair-attempt policy
# ---------------------------------------------------------------------------


def evaluate_repair_attempt(
    events: list[dict],
    *,
    task_id: str,
    role: str,
    target_kind: str,
    target_id: str,
    implementation_fingerprint: str,
    failure_signature: str,
    root_cause_id: str | None = None,
    max_repair_attempts: int = DEFAULT_MAX_REPAIR_ATTEMPTS_PER_FINDING,
    max_identical_repeats: int = DEFAULT_MAX_IDENTICAL_FAILURE_REPEATS,
) -> dict:
    """Decides whether another repair attempt is authorized for one finding/AC. A
    `root_cause_id` scopes the attempt budget: passing a new one is a coordinator's
    explicit re-authorization of a fresh retry series once a genuinely new root cause is
    established (osb/docs/RECOVERY.md §Re-authorization) — it is never inferred
    automatically from a changed fingerprint alone."""

    scoped = [
        e for e in filter_events(events, task_id=task_id, role=role, target_kind=target_kind, target_id=target_id)
        if e["event_type"] == "repair-attempt" and e.get("root_cause_id") == root_cause_id
    ]
    attempt_number = len(scoped) + 1
    normalized = normalize_failure_signature(failure_signature)

    identical_prior = sum(
        1 for e in scoped
        if e.get("implementation_fingerprint") == implementation_fingerprint
        and normalize_failure_signature(e.get("failure_signature") or "") == normalized
    )
    if identical_prior > 0 and identical_prior + 1 >= max_identical_repeats:
        return {
            "decision": STOP_IDENTICAL_FAILURE,
            "attempt_number": attempt_number,
            "reason": (
                f"same failure signature on unchanged implementation fingerprint "
                f"'{implementation_fingerprint}' repeated {identical_prior + 1} time(s) "
                f"(budget: {max_identical_repeats}) — route a concise blocker to the "
                "Architect/coordinator instead of retrying blindly"
            ),
        }

    if attempt_number > max_repair_attempts:
        return {
            "decision": ATTEMPTS_EXHAUSTED,
            "attempt_number": attempt_number,
            "reason": (
                f"{attempt_number - 1} repair attempt(s) already made against a budget of "
                f"{max_repair_attempts} for this finding/root-cause"
            ),
        }

    return {
        "decision": RETRY,
        "attempt_number": attempt_number,
        "reason": "within repair-attempt and identical-failure budgets",
    }


def evaluate_context_expansion(
    events: list[dict],
    *,
    task_id: str,
    role: str,
    question_id: str,
    max_expansions: int = DEFAULT_MAX_CONTEXT_EXPANSIONS_PER_QUESTION,
) -> dict:
    """Decides whether another context expansion is authorized for one unanswered
    question. Reaching the limit reports the question unresolved with the next required
    source/action — it never truncates a mandatory requirement or silently bypasses QA."""

    scoped = [
        e for e in filter_events(events, task_id=task_id, role=role, target_kind="question", target_id=question_id)
        if e["event_type"] == "context-expansion"
    ]
    attempt_number = len(scoped) + 1
    if attempt_number > max_expansions:
        return {
            "decision": QUESTION_UNRESOLVED,
            "attempt_number": attempt_number,
            "reason": (
                f"{attempt_number - 1} context expansion(s) already made against a budget "
                f"of {max_expansions} for this question — report it unresolved with the "
                "next required source/action rather than expanding further"
            ),
        }
    return {
        "decision": EXPAND_CONTEXT,
        "attempt_number": attempt_number,
        "reason": "within context-expansion budget",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _events_path(workspace_root: Path, task_id: str) -> Path:
    return workspace_root / ".osb" / "runs" / task_id / "recovery.jsonl"


def cmd_evaluate(args: argparse.Namespace) -> int:
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    workspace_root = Path(args.workspace_root).resolve()
    events = load_events(_events_path(workspace_root, request["task_id"]))

    if request["event_type"] == "repair-attempt":
        result = evaluate_repair_attempt(
            events,
            task_id=request["task_id"],
            role=request["role"],
            target_kind=request["target_kind"],
            target_id=request["target_id"],
            implementation_fingerprint=request["implementation_fingerprint"],
            failure_signature=request["failure_signature"],
            root_cause_id=request.get("root_cause_id"),
            max_repair_attempts=request.get("max_repair_attempts", DEFAULT_MAX_REPAIR_ATTEMPTS_PER_FINDING),
            max_identical_repeats=request.get("max_identical_repeats", DEFAULT_MAX_IDENTICAL_FAILURE_REPEATS),
        )
    elif request["event_type"] == "context-expansion":
        result = evaluate_context_expansion(
            events,
            task_id=request["task_id"],
            role=request["role"],
            question_id=request["target_id"],
            max_expansions=request.get("max_expansions", DEFAULT_MAX_CONTEXT_EXPANSIONS_PER_QUESTION),
        )
    else:
        print(f"unsupported event_type for evaluate: {request['event_type']!r}")
        return 1

    print(json.dumps(result))

    if args.record:
        event = {
            "task_id": request["task_id"],
            "role": request["role"],
            "event_type": request["event_type"],
            "target_kind": request["target_kind"],
            "target_id": request["target_id"],
            "implementation_fingerprint": request.get("implementation_fingerprint"),
            "failure_signature": request.get("failure_signature"),
            "root_cause_id": request.get("root_cause_id"),
            "blocker_kind": request.get("blocker_kind"),
            "decision": result["decision"],
            "reason": result["reason"],
            "timestamp": now_utc(),
        }
        errors = append_event(_events_path(workspace_root, request["task_id"]), event)
        if errors:
            print("failed to record event:")
            for error in errors:
                print(f"  - {error}")
            return 1

    return 0


def cmd_record(args: argparse.Namespace) -> int:
    event = json.loads(Path(args.event).read_text(encoding="utf-8"))
    event.setdefault("timestamp", now_utc())
    workspace_root = Path(args.workspace_root).resolve()
    errors = append_event(_events_path(workspace_root, event["task_id"]), event)
    if errors:
        print(f"refusing to record an invalid event, {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("recorded.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace_root).resolve()
    events = load_events(_events_path(workspace_root, args.task_id))
    if not events:
        print(f"no recovery events recorded for task '{args.task_id}'.")
        return 0
    for event in events:
        print(
            f"{event['timestamp']} [{event['role']}] {event['event_type']} "
            f"{event['target_kind']}={event['target_id']} -> {event.get('decision')}: {event.get('reason')}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recovery_policy", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_eval = sub.add_parser("evaluate", help="Decide whether another attempt/expansion is authorized")
    p_eval.add_argument("request")
    p_eval.add_argument("--workspace-root", default=".")
    p_eval.add_argument("--record", action="store_true", help="Also append the evaluated event to the log")
    p_eval.set_defaults(func=cmd_evaluate)

    p_record = sub.add_parser("record", help="Append a pre-built recovery event (e.g. a blocker) to the log")
    p_record.add_argument("event")
    p_record.add_argument("--workspace-root", default=".")
    p_record.set_defaults(func=cmd_record)

    p_status = sub.add_parser("status", help="Print a task's recorded recovery events (read-only)")
    p_status.add_argument("task_id")
    p_status.add_argument("--workspace-root", default=".")
    p_status.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
