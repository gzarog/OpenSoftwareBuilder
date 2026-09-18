# Open Software Builder

An auditable, provider-neutral multi-agent software-delivery workflow that takes
repository work from architecture through implementation, independent review, QA, and
durable project memory.

Open Software Builder is a local repository toolkit — not another agent runtime. Claude
Code, OpenAI Codex, GitHub Copilot, and future systems supply the agents; Open Software
Builder supplies the organization, contracts, state machine, evidence, and quality gates.

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
    +-- Knowledge query
    |
    v
  Architect
    |  specification + acceptance criteria
    v
  Implementer(s)
    |  implementation + tests + checkpoints
    v
  Independent Reviewer
    |  findings or approval
    v
  Fresh QA Tester
    |  build + tests + fitness + e2e/browser
    v
  Durable Knowledge
```

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

## CLI commands

| Command | Description |
| --- | --- |
| `osb init` | Initialize a project with OSB |
| `osb doctor` | Validate configuration and health |
| `osb status` | Show gates, checkpoints, recent knowledge |
| `osb changed [min]` | Detect changes (git or mtime fallback) |
| `osb validate spec <file>` | Validate architecture spec format |
| `osb validate checkpoint <file>` | Validate checkpoint format |
| `osb gate review inspect` | Check review gate state |
| `osb gate review approve` | Record reviewer approval |
| `osb gate review skip "<reason>"` | Auditable review skip |
| `osb gate knowledge inspect` | Check knowledge gate state |
| `osb gate knowledge skip "<reason>"` | Auditable knowledge skip |
| `osb knowledge record` | Knowledge recording helper |

## License

Apache-2.0
