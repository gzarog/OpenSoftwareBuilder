# OpenSoftwareBuilder

OpenSoftwareBuilder is a reusable Architect → Implement → Review → QA agent workflow with
RagMonk-backed project memory.

```text
/osb <task>
```

That single command drives a task through four independent roles — **Architect**,
**Implementer** (one or more), **Reviewer**, and **QA** — with durable, incrementally
captured knowledge feeding both the current task and every future one.

OSB is not an agent runtime. It has no compiled binary, no provider abstraction, no
build-system or toolchain catalog, and no daemon. The host coding assistant — Claude
Code, OpenAI Codex, or GitHub Copilot — provides execution; OSB provides the workflow
policy, role contracts, model configuration, and knowledge conventions on top of it.

## How it works

```text
                    /osb <task>
                         │
                         ▼
                  ┌─────────────┐
                  │  OSB Skill  │
                  └──────┬──────┘
                         │
              ┌──────────┴──────────┐
              │                     │
         model config          RagMonk
              │                     │
              └──────────┬──────────┘
                         ▼
                    Architect
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        Implementer A         Implementer B
              │                     │
              └──────────┬──────────┘
                         ▼
                     Reviewer (delta)
                         │
                  findings?
                   │     │
                  yes    no
                   │     │
                   ▼     ▼
             Implementer  Reviewer (MANDATORY final combined-change review)
                                        │
                                        ▼
                                        QA (every AC, final revision)
                                        │
                                      fail?
                                   │          │
                                  yes         no
                                   │          │
                             repair/design    ▼
                                   │      consolidate
                                   └───────► knowledge
                                              │
                                              ▼
                                           RagMonk
```

1. **Architect** understands the task, retrieves relevant existing knowledge, defines
   architecture, interfaces, and acceptance criteria, and splits the work into
   implementation units — without writing any production code.
2. **Implementer(s)** implement one unit each — code, tests, and verification. Units
   with disjoint files, fixed interfaces, and no unmet dependency can run in parallel.
3. **Reviewer** independently checks the diff against the acceptance criteria and reports
   structured findings. Blocking findings loop back to an Implementer as a delta until
   that check is clean — then a **mandatory final combined-change review** over every unit
   and repair since the task began must also come back clean before QA runs.
4. **QA** independently validates **every** acceptance criterion — including ones that
   previously passed — by actually running build/test/behavior, never by trusting an
   Implementer's or Reviewer's word for it, and never reporting an unrun or inconclusive
   check as passing. Implementation defects loop back to an Implementer; design problems
   loop back to the Architect — either loop re-runs the final review and QA in full, since
   a repair can invalidate previously-clean results.
5. **Knowledge** discovered by any role along the way is captured incrementally and, once
   QA passes, consolidated into durable task and component records that RagMonk indexes
   for the next `/osb` run.

Any role may pause with a `needs-evidence` request instead of guessing over a truncated
retrieval, a missing constraint, or an unclear dependency — see
`.agents/skills/osb/references/quality.md`.

See `docs/OSB_V2_CONTRACT.md` for the full provider-neutral specification, and
`.agents/skills/osb/SKILL.md` for the workflow itself.

## Supported hosts

All three hosts run the same logical workflow; only the invocation syntax and launch
mechanics differ:

| Host | Invocation | Setup |
| --- | --- | --- |
| Claude Code | `/osb <task>` | `docs/CLAUDE.md` |
| GitHub Copilot / VS Code | `/osb <task>` | `docs/COPILOT.md` |
| OpenAI Codex | `$osb <task>` | `docs/CODEX.md` |

Provider-specific files under `.claude/`, `.codex/`, and `.github/` are thin wrappers —
they bind models and launch mechanics, they never redefine the workflow.

## Getting started

See `docs/INSTALL.md` for the full setup steps. In short: copy `.agents/skills/osb/`,
the provider files for your host(s), and `templates/osb.yaml` (as `osb.yaml`) into your
project, fill in a model per role per host, and run `/osb <task>`.

## Configuration

A project needs only one small `osb.yaml` (see `templates/osb.yaml`):

```yaml
version: 2

models:
  claude-code:
    architect: <model id>
    implementer: <model id>
    reviewer: <model id>
    qa: <model id>

execution:
  max_parallel_implementers: 2
  compact_handoffs: true
  checkpoint_state: true
  delta_repairs: true

knowledge:
  enabled: true
  incremental: true
  path: .osb/knowledge

ragmonk:
  enabled: true
  required: true
  retrieve_before_architecture: true
  refresh_after_knowledge_change: true
```

OSB never invents a model for a role left blank — it asks once and can persist the
answer. There are no language profiles, build-system catalogs, or toolchain definitions
to configure: agents detect those from the repository itself.

## Knowledge

OSB treats plain files as the authoritative source of project memory and RagMonk as the
index/retrieval layer over them:

```text
.osb/knowledge/
├── events/        incremental JSONL knowledge events captured during a task
├── tasks/         one immutable record per completed task
└── components/    current-state record per touched component, edited in place
```

See `docs/RAGMONK.md` and `.agents/skills/osb/references/knowledge.md`.

## Execution state

Task progress — current phase, unit status, open findings, failed acceptance criteria —
is persisted separately as compact JSON at `.osb/state/<task-id>.json`. It is never
treated as knowledge or indexed by RagMonk, and it's what lets an interrupted `/osb` run
resume from its current phase instead of restarting. See
`.agents/skills/osb/references/state.md`.

## Quality gate

Token budgets, compact handoffs, and delta repair loops are starting points for the cheap
case, not evidence caps. A delta review pass is always intermediate; a mandatory final
combined-change review and independent, per-AC QA on the final revision are required
before completion, and any later repair — including one discovered on resume — invalidates
prior verdicts until both are re-run. See
`.agents/skills/osb/references/quality.md`.

## License

See `LICENSE`.
