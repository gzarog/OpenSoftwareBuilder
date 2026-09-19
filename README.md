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
                     Reviewer
                         │
                  findings?
                   │     │
                  yes    no
                   │     │
                   ▼     ▼
             Implementer  QA
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
   structured findings. Blocking findings loop back to an Implementer until the review is
   clean.
4. **QA** independently validates every acceptance criterion by actually running
   build/test/behavior — never by trusting an Implementer's or Reviewer's word for it.
   Implementation defects loop back to an Implementer; design problems loop back to the
   Architect.
5. **Knowledge** discovered by any role along the way is captured incrementally and, once
   QA passes, consolidated into durable task and component records that RagMonk indexes
   for the next `/osb` run.

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

knowledge:
  enabled: true
  incremental: true
  path: .osb/knowledge

ragmonk:
  enabled: true
  required: true
  retrieve_before_architecture: true
  refresh_after_checkpoint: true
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

## License

See `LICENSE`.
