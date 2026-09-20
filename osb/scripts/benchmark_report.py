#!/usr/bin/env python3
"""Before/after benchmark report (P1-F, Phase 6).

Compares two run-metrics records (osb/schemas/run-metrics.schema.json) for the *same*
fixture and the *same* task revision, and reports efficiency deltas alongside quality
metrics. This never fabricates a saving: a metric recorded as "unavailable" in either run
stays "unavailable" in the report rather than being treated as zero, and any quality
regression rejects the comparison outright regardless of how good the efficiency numbers
look (osb/references/quality.md — quality is a gate, not a number to trade away).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schema_validate  # noqa: E402

SCHEMA = json.loads((Path(__file__).resolve().parent.parent / "schemas/run-metrics.schema.json").read_text())

QUALITY_METRICS_LOWER_IS_BETTER = ("regressions_found", "unresolved_blockers")
QUALITY_METRICS_HIGHER_IS_BETTER = ("ac_coverage",)


def load_run(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = schema_validate.validate(data, SCHEMA)
    if errors:
        raise ValueError(f"{path}: does not conform to run-metrics.schema.json: {errors}")
    return data


def _delta(baseline, changed):
    if baseline == "unavailable" or changed == "unavailable":
        return "unavailable"
    if baseline is None or changed is None:
        return "unavailable"
    delta = changed - baseline
    pct = (delta / baseline * 100) if baseline else None
    return {"baseline": baseline, "changed": changed, "delta": delta, "pct": pct}


def detect_quality_regression(baseline_quality: dict, changed_quality: dict) -> list[str]:
    regressions: list[str] = []
    for key in QUALITY_METRICS_HIGHER_IS_BETTER:
        b, c = baseline_quality.get(key), changed_quality.get(key)
        if b == "unavailable" or c == "unavailable" or b is None or c is None:
            continue
        if c < b:
            regressions.append(f"{key} decreased ({b} -> {c})")
    for key in QUALITY_METRICS_LOWER_IS_BETTER:
        b, c = baseline_quality.get(key), changed_quality.get(key)
        if b == "unavailable" or c == "unavailable" or b is None or c is None:
            continue
        if c > b:
            regressions.append(f"{key} increased ({b} -> {c})")
    if baseline_quality.get("repeatable") is True and changed_quality.get("repeatable") is False:
        regressions.append("repeatable changed from true to false")
    return regressions


def compare(baseline: dict, changed: dict) -> dict:
    if baseline["fixture_id"] != changed["fixture_id"]:
        raise ValueError("cannot compare runs from different fixtures")
    if baseline["task_revision"] != changed["task_revision"]:
        raise ValueError(
            "cannot compare runs against different task revisions "
            f"({baseline['task_revision']!r} vs {changed['task_revision']!r}) — "
            "re-run both against the identical revision first"
        )

    quality_regressions = detect_quality_regression(baseline["quality"], changed["quality"])

    metric_deltas = {
        key: _delta(baseline["metrics"].get(key), changed["metrics"].get(key))
        for key in set(baseline["metrics"]) | set(changed["metrics"])
    }

    return {
        "fixture_id": baseline["fixture_id"],
        "task_revision": baseline["task_revision"],
        "quality_regressions": quality_regressions,
        "verdict": (
            "REJECTED: quality regressed — efficiency deltas below are informational only, "
            "not an endorsed optimization"
            if quality_regressions
            else "no quality regression detected"
        ),
        "metric_deltas": metric_deltas,
    }


def format_report(result: dict) -> str:
    lines = [
        f"Fixture: {result['fixture_id']}  Revision: {result['task_revision']}",
        f"Verdict: {result['verdict']}",
    ]
    if result["quality_regressions"]:
        lines.append("Quality regressions:")
        for r in result["quality_regressions"]:
            lines.append(f"  - {r}")
    lines.append("Metric deltas (baseline -> changed):")
    for key, delta in sorted(result["metric_deltas"].items()):
        if delta == "unavailable":
            lines.append(f"  - {key}: unavailable")
        else:
            pct = f", {delta['pct']:+.1f}%" if delta["pct"] is not None else ""
            lines.append(f"  - {key}: {delta['baseline']} -> {delta['changed']} ({delta['delta']:+}{pct})")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_run", help="Path to a baseline run-metrics JSON file")
    parser.add_argument("changed_run", help="Path to a changed run-metrics JSON file")
    args = parser.parse_args(argv)

    baseline = load_run(Path(args.baseline_run))
    changed = load_run(Path(args.changed_run))
    result = compare(baseline, changed)
    print(format_report(result))
    return 1 if result["quality_regressions"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
