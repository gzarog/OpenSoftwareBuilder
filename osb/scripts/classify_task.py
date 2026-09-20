#!/usr/bin/env python3
"""Deterministic-first task classifier (P0-B, Phase 2).

Chooses a proportionate initial execution strategy (osb/references/workflow.md §Task
classification) from cheap, already-known signals. It never removes a mandatory
requirement: the caller (the coordinator) is responsible for keeping the full AC set,
independent Reviewer, and mandatory final review/QA regardless of the profile chosen here.
Uncertain input always defaults to the broader `feature` profile — this module never
guesses a narrower profile defensively.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VALID_PROFILES = ("small-fix", "feature", "cross-service", "high-risk")


def classify(scenario: dict) -> dict:
    """scenario keys (all optional except noted): files_estimate, repositories,
    cross_service_contracts, migrations, security_sensitive, touches_auth_or_payments,
    acceptance_criteria_count, uncertain. Returns {task_profile, rationale, risk_flags}.

    `high-risk` is an orthogonal flag layered onto whichever base profile applies, not a
    fifth mutually-exclusive category on top of the other three — see
    osb/references/workflow.md §Task classification.
    """

    files_estimate = scenario.get("files_estimate")
    repositories = scenario.get("repositories")
    cross_service = bool(scenario.get("cross_service_contracts", False))
    migrations = bool(scenario.get("migrations", False))
    security_sensitive = bool(scenario.get("security_sensitive", False)) or bool(
        scenario.get("touches_auth_or_payments", False)
    )
    ac_count = scenario.get("acceptance_criteria_count")
    uncertain = bool(scenario.get("uncertain", False))

    risk_flags: list[str] = []
    if migrations or security_sensitive:
        risk_flags.append("high-risk")

    if uncertain or files_estimate is None or repositories is None:
        return {
            "task_profile": "feature",
            "rationale": "uncertain classification defaults to broader discovery",
            "risk_flags": risk_flags,
        }

    if repositories > 1 or cross_service:
        return {
            "task_profile": "cross-service",
            "rationale": f"{repositories} repositories involved and/or a shared contract changes",
            "risk_flags": risk_flags,
        }

    if files_estimate <= 1 and (ac_count is None or ac_count <= 1) and not risk_flags:
        return {
            "task_profile": "small-fix",
            "rationale": "single file, minimal scope, no elevated risk",
            "risk_flags": risk_flags,
        }

    return {
        "task_profile": "feature",
        "rationale": "multi-file or elevated-risk change within one repository",
        "risk_flags": risk_flags,
    }


def reclassify_on_new_evidence(previous: dict, scenario_update: dict) -> dict:
    """Re-run classification after evidence expands scope mid-task (e.g. a second
    repository turns out to be affected). Never narrows an already-broader profile based
    on the same or less information — only widens or adds risk flags."""

    scope_rank = {"small-fix": 0, "feature": 1, "cross-service": 2}
    new = classify(scenario_update)
    if scope_rank.get(new["task_profile"], 0) < scope_rank.get(previous.get("task_profile", "small-fix"), 0):
        new["task_profile"] = previous["task_profile"]
        new["rationale"] = f"kept broader prior profile; new signals alone would suggest narrower ({new['rationale']})"
    new["risk_flags"] = sorted(set(previous.get("risk_flags", [])) | set(new["risk_flags"]))
    return new


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario_file", help="Path to a JSON file with a 'scenario' object, or the scenario object itself")
    args = parser.parse_args(argv)

    data = json.loads(Path(args.scenario_file).read_text(encoding="utf-8"))
    scenario = data.get("scenario", data)
    result = classify(scenario)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
