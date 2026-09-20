# Host capability preflight (P1-G, Phase 7)

Catches unsupported host/model/tool configurations **before dispatch**, without adding a
provider runtime. This document is the honest capability matrix; `osb/scripts/host_preflight.py`
is the deterministic, local part of it (config/file checks only — it never calls a host
API, because no such generic API exists).

## Two layers, never conflated

1. **Deterministic preflight** (`osb/scripts/host_preflight.py <host>`) — config presence,
   generated-adapter presence, Git/worktree availability, RagMonk CLI presence. Fully
   automatable, runs in CI, and reports `pass` / `blocked` / `not-applicable` / `unknown`.
   `unknown` is not a soft pass — a mandatory capability that comes back `unknown` blocks
   dispatch for that capability the same as `blocked` would.
2. **Live-host smoke test** — actually dispatching a role on a running Claude Code, Codex,
   or Copilot session and observing the result. This is not automatable from a standalone
   script; each row below is `verified` only once such a run has actually happened and is
   `not run` otherwise (see the `osb/tests/fixtures/host_capability/*.json` fixtures,
   which record `verified: "not run"` as a fixture default, not a claim).

Never present a `pass` from layer 1 as proof of layer 2. Never claim a `/osb` or `$osb`
invocation is supported on a host/version that hasn't actually had layer 2 run against it.

## Capability matrix

| Capability | Claude Code | Codex | Copilot |
| --- | --- | --- | --- |
| Native invocation (documented) | `/osb <task>` | `$osb <task>` (fallback: `/skills` → `osb`) | `/osb <task>` |
| Per-role model resolution | `osb.yaml` → `models.claude-code.*` | `models.codex.*` | `models.copilot.*` |
| Role dispatch mechanism | native subagent tool (Agent tool, `subagent_type`) | native agent config (`.codex/agents/*.toml`, per-role `sandbox_mode`) | Agent Skills + `.github/agents/*.agent.md` |
| Sandbox/permission mode | host-managed tool permission prompts | `sandbox_mode` per role (architect/reviewer/qa: read-only; implementer: workspace-write) | host-managed |
| Git/worktree capability | via Bash/Git tool access | via shell tool access | via VS Code Git integration |
| Test-command capability | project-specific | project-specific | project-specific |
| RagMonk access | MCP preferred, CLI fallback | MCP if environment supports it, else CLI | MCP if configured in VS Code, else CLI |
| Independent Reviewer/QA context | native subagent = independent context | native agent dispatch = independent context | depends on Copilot agent-mode configuration — **see caveat below** |

"Project-specific" test-command capability is intentional: OSB does not introduce a custom
toolchain/build-system abstraction (`osb/docs/OSB_V2_CONTRACT.md` §What OSB v2 deliberately
does not have). Each project's own build/test commands are what QA actually runs.

## The independent-context caveat

Where a host configuration **cannot guarantee** the Reviewer and QA each run in a context
independent of the Implementer's (e.g. a degraded single-context role-switch fallback),
that limitation must be **documented explicitly** for that configuration — never presented
as equivalent to true subagent independence. `host_preflight.py` reports
`independent_role_contexts` as `unknown` for every host, precisely because a standalone
script cannot confirm which dispatch mode is actually in effect at runtime; the host
itself (or a human operator) must confirm this before treating Reviewer/QA independence as
established for a given session.

## Missing/unavailable models

A missing or unavailable model for one role prompts the user for **that role only**
(`SKILL.md` §Model resolution). `host_preflight.py`'s `models_configured` check reports
exactly which role(s) are missing — it never invents a "best model" ranking or falls back
to another role's model.

## Platform notes (Windows PowerShell / Linux / macOS / WSL)

`osb/install.sh` and `osb/install.ps1` are thin launchers over the same Python
implementation (`osb/scripts/install.py`), so behavior is identical across platforms
provided Python 3.11+ is on `PATH`. `host_preflight.py` uses only `pathlib`, `shutil.which`,
and `subprocess` — no shell-specific syntax — so it runs the same way under PowerShell,
bash/zsh, and WSL. Git worktree support (`git worktree list`) requires a Git version that
supports worktrees (Git 2.5+, ubiquitous today) on every platform; `host_preflight.py`
checks this by actually running the command rather than parsing a version string.

## Wrapper-drift validation

Self-contained role instructions across host wrappers are validated against the canonical
`osb/agents/*.md` contract by `osb/scripts/validate_osb.py`'s `check_role_agents_no_drift`
— every push to this repository re-checks that `.claude/agents/*.md` is byte-identical to
its canonical source, and that `.github/agents/*.agent.md` / `.codex/agents/*.toml`
reproduce the same body content. A quality/schema/role-policy change that isn't reflected
in a regenerated adapter fails CI rather than silently drifting.
