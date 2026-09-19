# Open Software Builder

An auditable, provider-neutral multi-agent software-delivery workflow that takes
repository work from architecture through implementation, independent review, QA, and
durable project memory — with **incremental knowledge capture** at every step.

Open Software Builder is a local repository toolkit — not another agent runtime. Claude
Code, OpenAI Codex, GitHub Copilot, and future systems supply the agents; Open Software
Builder supplies the organization, contracts, state machine, evidence, quality gates, and
knowledge management.

## Quick start

```powershell
# Initialize a project
pwsh cli/osb.ps1 init -Profile generic -Providers claude,codex,copilot,vscode

# Validate configuration
pwsh cli/osb.ps1 doctor

# Check project state
pwsh cli/osb.ps1 status
```

## Architecture

```
open-software-builder/
  core/                    Neutral workflow kernel
    workflow/              Canonical policy and capability mapping
    roles/                 Four neutral role definitions
    schemas/               Configuration and artifact schemas
    knowledge/             Knowledge system design
  cli/                     Cross-platform CLI (PowerShell)
    osb.ps1                Entry point
    osb-init.ps1           Initialize a project
    osb-doctor.ps1         Validate configuration
    osb-status.ps1         Show project state
    osb-changed.ps1        Detect source changes
    osb-gate.ps1           Manage quality gates
    osb-validate.ps1       Validate artifacts
    osb-knowledge.ps1      Knowledge recording
  adapters/                Provider-specific adapters
    claude/                Claude Code (CLAUDE.md, agents, skills, hooks)
    codex/                 OpenAI Codex (AGENTS.md, skills)
    copilot/               GitHub Copilot (copilot-instructions.md, agents)
    vscode/                VS Code (tasks.json, settings)
    generic/               Documentation for other providers
  profiles/                Project type defaults
    generic/               Minimal defaults
    dotnet-services/       .NET microservice workspace
    node-web/              Node.js/TypeScript web project
  templates/               Reusable templates
    checkpoints/           Agent checkpoint schema
    knowledge/             Task record, component record, index
  tests/                   Validation scenarios
    scenarios/             End-to-end workflow scenarios
    adapters/              Per-adapter instruction tracing
    gates/                 Gate behavior tests
```

## Workflow

```
Lead / Orchestrator
    |
    +-- RagMonk context (existing durable knowledge)
    |
    v
  Architect
    |  specification + acceptance criteria
    |  └── knowledge checkpoint (decisions, constraints, assumptions)
    v
  Implementer(s)
    |  implementation + tests + checkpoints
    |  └── knowledge checkpoint(s) (discoveries, gotchas, changed assumptions)
    v
  Independent Reviewer
    |  findings or approval
    |  └── knowledge checkpoint (recurring patterns, risks)
    v
  Fresh QA Tester
    |  build + tests + fitness + e2e/browser
    |  └── knowledge checkpoint (verified behavior, failure conditions)
    v
  Knowledge Consolidation
    |  osb knowledge consolidate --task-id <id>
    v
  Durable Knowledge
    (tasks/ + components/ + INDEX.md + RagMonk index refresh)
```

**Core principle:** capture facts immediately; consolidate them later.

### Triage

| Tier | Description | Pipeline |
| --- | --- | --- |
| 1 | Single-line/config/comment, no logic change | Direct edit, no pipeline |
| 2 | Mechanical, already-decided implementation | Implement + independent review |
| 3 | Design decision, public contract, cross-component | Full pipeline |

### Roles

- **Lead/Orchestrator** — triages, creates assignments, controls sequencing, handles
  repair loops, owns knowledge recording.
- **Architect** — designs but does not implement. Produces interfaces, acceptance
  criteria, milestones, tradeoffs, risks.
- **Implementer** — works from unambiguous specs, checkpoints progress, builds and tests.
- **Independent Reviewer** — never fixes code. Reports findings with file, problem,
  severity, and repair.
- **Fresh QA Tester** — independently checks every acceptance criterion. Never approves
  review or edits implementation.

## Provider adapters

| Provider | Entry file | Agent dispatch | Browser QA | Hooks |
| --- | --- | --- | --- | --- |
| Claude Code | `CLAUDE.md` | Agent tool with role wrappers | Built-in browser | Stop hooks |
| OpenAI Codex | `AGENTS.md` | `fork_turns=none` subagent | If available | Manual CLI |
| GitHub Copilot | `.github/copilot-instructions.md` | Agent mode (@workspace) | Manual (gap) | Manual CLI |
| VS Code | `.vscode/tasks.json` | Depends on AI provider | Depends on AI provider | VS Code tasks |
| Generic | Documentation only | Provider-specific | Provider-specific | Manual CLI |

## Configuration

Projects configure OSB through `osb.yaml` at the repository root:

```yaml
version: 1

paths:
  source: [src, apps]
  generated: [node_modules, dist, build]
  checkpoints: .osb/progress
  knowledge: .osb/knowledge
  state: .osb/state

commands:
  build: npm run build
  test: npm test
  fitness: null
  e2e: npx playwright test

capabilities:
  structural_explorer: codegraph
  browser_qa: required

policy:
  require_independent_review: true
  require_fresh_qa: true
  sensitive_areas: [auth, payments]
```

## Full Mode — RagMonk intelligence

OSB supports two modes:

| Mode | Intelligence | Use when |
| ---- | ------------ | -------- |
| `light` | Optional — knowledge files only | Quick start, no RagMonk |
| `full` | **Mandatory** — all context through RagMonk | Production workflows |

In **Full Mode**, every agent dispatch is grounded in a bounded evidence package from the
RagMonk knowledge index. Agents must not scan the repository independently for historical
context — this is enforced by the `intelligence` gate and by each adapter's instructions.

```yaml
# osb.yaml — enable full mode
mode: full
intelligence:
  provider: ragmonk
  ragmonk:
    auto_index: true
    auto_watch: true
```

**Quick setup:**
```sh
osb migrate                              # guided setup (installs, registers, indexes)
osb gate intelligence inspect            # verify readiness
osb context build "my task" --role implementer  # build evidence package
```

See [`docs/intelligence/`](docs/intelligence/) for full documentation.

## CLI commands

### Core workflow

| Command | Description |
| --- | --- |
| `osb init` | Initialize a project with OSB |
| `osb doctor` | Validate configuration and health |
| `osb status` | Show gates, checkpoints, knowledge, and intelligence |
| `osb changed [min]` | Detect changes (git or mtime fallback) |
| `osb validate spec <file>` | Validate architecture spec format |
| `osb validate checkpoint <file>` | Validate checkpoint format |
| `osb migrate` | Upgrade project to Full OSB Mode |

### Gates

| Command | Description |
| --- | --- |
| `osb gate review inspect` | Check review gate state |
| `osb gate review approve` | Record reviewer approval |
| `osb gate review skip "<reason>"` | Auditable review skip |
| `osb gate knowledge inspect` | Check knowledge gate state |
| `osb gate knowledge skip "<reason>"` | Auditable knowledge skip |
| `osb gate intelligence inspect` | Check intelligence readiness (full mode) |

### Knowledge

#### Incremental capture (during active tasks)

| Command | Description |
| --- | --- |
| `osb knowledge capture --task-id <id> --role <role> --type <type> --summary "<text>"` | Capture a knowledge event (decision, discovery, gotcha, …) |
| `osb knowledge capture --none --role <role> --reason-none "<text>"` | Explicit zero-knowledge checkpoint |
| `osb knowledge capture --from-json event.json` | Capture from a pre-built JSON event file |
| `osb knowledge pending [--task-id <id>]` | Show pending checkpoint status for active tasks |
| `osb knowledge inspect --task-id <id>` | Show all captured events for a task |
| `osb knowledge consolidate --task-id <id>` | Consolidate captured events into durable records |
| `osb knowledge consolidate --task-id <id> --dry-run` | Preview consolidation without writing files |

**Event types:** `decision`, `constraint`, `discovery`, `gotcha`, `assumption`,
`assumption-invalidated`, `review-finding`, `qa-result`, `follow-up`

**Scopes:** `temporary`, `task`, `component`, `global`, `discard`

**Set `OSB_TASK_ID` as an environment variable to avoid repeating `--task-id` on every command.**

#### Role-aware knowledge gate

```sh
# Check all role checkpoints and consolidation status for a task.
osb gate knowledge inspect --task-id <id>
```

#### Durable records

| Command | Description |
| --- | --- |
| `osb knowledge record task <name>` | Create a task knowledge record manually |
| `osb knowledge record component <name>` | Create a component knowledge record manually |
| `osb knowledge status` | Show durable knowledge directory status |

#### Example workflow

```sh
# Architect captures a design decision.
osb knowledge capture --task-id OSB-124 --role architect \
  --type decision --scope global \
  --summary "Use event-driven cache invalidation instead of polling"

# Implementer captures a gotcha.
osb knowledge capture --task-id OSB-124 --role implementer \
  --type gotcha --scope component \
  --summary "Lock timeout must stay below provider SLA" \
  --file src/Cache/Invalidator.cs

# Reviewer explicitly records no reusable findings.
osb knowledge capture --task-id OSB-124 --role reviewer \
  --none --reason-none "Trivial change — no recurring patterns found"

# QA captures verified behavior.
osb knowledge capture --task-id OSB-124 --role qa \
  --type qa-result --summary "All 142 tests pass; invalidation latency < 50ms"

# Check knowledge gate status.
osb gate knowledge inspect --task-id OSB-124

# Consolidate into durable records (auto-refreshes RagMonk in full mode).
osb knowledge consolidate --task-id OSB-124
```

#### Full Mode — active-task knowledge via RagMonk

When `intelligence.ragmonk.active_task_knowledge: true` (the default), each capture
event triggers a RagMonk incremental index so later agents in the same task can query
discoveries made by earlier agents through `osb context build`.

```yaml
intelligence:
  provider: ragmonk
  ragmonk:
    active_task_knowledge: true   # index events for in-task retrieval
    refresh_on_checkpoint: true   # index immediately on each capture
```

### Intelligence (full mode)

| Command | Description |
| --- | --- |
| `osb intelligence status` | Health snapshot |
| `osb intelligence doctor` | Detailed step-by-step check |
| `osb intelligence index` | Trigger full/incremental index |
| `osb intelligence refresh` | Incremental update when dirty |
| `osb intelligence query <text>` | Free-text knowledge query |
| `osb context build "<query>" --role <role>` | Build bounded evidence package |

## License

Apache-2.0
