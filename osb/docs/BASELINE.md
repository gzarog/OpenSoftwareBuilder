# OSB P0/P1/P2 baseline (Phase 0)

**Baseline commit:** `e458e265f81d7f5c50e2522bd6532951d764738d` (`origin/main`, "Merge pull
request #13 from gzarog/claude/quality-guardrails") — the commit this implementation
branch (`claude/plan-implementation-t0nt6l`) was created from.

This is a **measured** inventory of the repository at that commit, recorded before any
P0–P2 change, so later phases can be checked against a known starting point rather than
an assumption.

## Canonical references (12 role definitions + 7 shared references)

At baseline, the canonical workflow lived at `.agents/skills/osb/`:

- `SKILL.md` (coordinator)
- `references/{workflow,roles,handoff,knowledge,ragmonk,state,quality}.md` (7 files)

Twelve host-native role definitions existed, three per role across three hosts:

| Role | Claude Code | Codex | Copilot |
| --- | --- | --- | --- |
| Architect | `.claude/agents/architect.md` | `.codex/agents/architect.toml` | `.github/agents/architect.agent.md` |
| Implementer | `.claude/agents/implementer.md` | `.codex/agents/implementer.toml` | `.github/agents/implementer.agent.md` |
| Reviewer | `.claude/agents/reviewer.md` | `.codex/agents/reviewer.toml` | `.github/agents/reviewer.agent.md` |
| QA | `.claude/agents/qa.md` | `.codex/agents/qa.toml` | `.github/agents/qa.agent.md` |

Plus `.claude/skills/osb/SKILL.md` and `.github/copilot-instructions.md` (thin wrappers).

## Supported invocation methods (measured, from docs at baseline)

| Host | Documented invocation |
| --- | --- |
| Claude Code | `/osb <task>` |
| VS Code Copilot | `/osb <task>` |
| OpenAI Codex | `$osb <task>` (fallback: `/skills` → `osb`) |

**Not available at baseline:** no record of an actual live smoke test against a running
Claude Code, Codex, or Copilot session confirming these invocations resolve — the
documentation asserted them without a recorded verification run. Phase 0A/0A.3 and Phase 7
add the fixture/smoke-test layers that make this checkable; until a host-specific smoke
test actually runs, its result stays labelled **not run**, never assumed passing.

## Current config fields (`templates/osb.yaml` at baseline)

```yaml
version: 2
models:
  claude-code: {architect, implementer, reviewer, qa}
  codex: {architect, implementer, reviewer, qa}
  copilot: {architect, implementer, reviewer, qa}
execution: {max_parallel_implementers: 2, compact_handoffs: true, checkpoint_state: true, delta_repairs: true}
knowledge: {enabled: true, incremental: true, path: .osb/knowledge}
ragmonk: {enabled: true, required: true, retrieve_before_architecture: true, refresh_after_knowledge_change: true}
```

No `workspace` (multi-repo), `execution.isolation`, or task-classification fields existed.

## Actual CI checks at baseline

`.github/workflows/ci.yml` ran exactly one step: `python scripts/validate_osb.py` — a
structural/textual validator (frontmatter presence, required substrings, forbidden legacy
phrases). It does **not** execute `/osb`, does not run any role, and does not check
task-state schemas (`templates/state/task.json` predates the `quality.*` fields documented
in `references/state.md` — a known gap this plan's Phase 1 closes).

## Known baseline gaps this plan addresses

- `templates/state/task.json` lacked `quality.required_ac_ids`,
  `unresolved_context_requests`, `task_base_revision`, `current_patch_fingerprint`,
  `final_review_fingerprint`, `final_qa_fingerprint`, `unverified_ac_ids` — documented in
  `references/state.md` but not reflected in the template (closed in Phase 1).
- `scripts/validate_osb.py` validated structure/keywords, not schemas, and never executed
  `/osb` (partially closed in Phase 1 via `verify_task.py`; full live-agent execution
  remains a separate, explicitly-labelled smoke-test layer per Phase 0A.3/Phase 7 — never
  claimed as "passed" without an actual recorded run).
- Framework files were split across `.agents/`, `.claude/`, `.codex/`, `.github/`, `docs/`,
  `scripts/`, `templates/` at the workspace root — no single portable package (closed in
  Phase 0A).
- No task classification, multi-repo orchestration, worktree isolation, provenance
  metadata, benchmarking, or host preflight existed (closed in Phases 2–7).

## Fixture repository setup

Representative task fixtures are recorded as JSON specs (not live executions) under
`osb/tests/fixtures/tasks/`:

| Fixture | File | Exercises |
| --- | --- | --- |
| Single-file bug | `single-file-bug.json` | `small-fix` profile, one Implementer, minimal review/QA scope |
| Multi-file feature | `multi-file-feature.json` | `feature` profile, Architect-led units, component-level retrieval |
| Security-sensitive change | `security-sensitive.json` | `high-risk` flag, mandatory security/data-integrity evidence |
| Interrupted task | `interrupted-task.json` | resume logic, fingerprint recomputation on resume (`state.md`) |
| Changed working tree | `changed-working-tree.json` | staleness: an untracked/uncommitted edit invalidates prior review/QA verdicts |
| Two-repo shared-contract change | `two-repo-shared-contract.json` | `cross-service` profile, multi-repo dependency + combined workspace fingerprint |

These are consumed by the fixture-based validation harness in
`osb/scripts/verify_task.py` and its tests (Phase 1), the classifier tests (Phase 2), and
the multi-repo tests (Phase 3). They check **generated state and evidence artifacts** —
they do not themselves invoke a model or a coding host. Live-agent end-to-end execution
against these fixtures is a separate, explicitly labelled layer (see
`osb/docs/HOST_COMPATIBILITY.md`) and is recorded as **not run** wherever it hasn't
actually been executed against a live host in this environment.

## Metrics

See `osb/docs/METRICS.md` for the common metric definitions and how each is labelled
**measured**, **synthetic**, or **not available**.
