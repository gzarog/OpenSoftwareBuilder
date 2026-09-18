# OSB Intelligence System — Overview

The OSB intelligence system connects the workflow engine to a project knowledge index so
that every agent dispatch is grounded in accurate, up-to-date context about the
repository's history, decisions, components, and prior work.

## Why a separate intelligence layer?

AI agents receive context through a context window. Without a managed knowledge layer,
agents either receive too little context (missing critical past decisions) or too much
(entire file trees that waste tokens and distort retrieval). The intelligence system
provides a *bounded evidence package* — exactly the knowledge relevant to the current task,
no more.

## Modes

| Mode | Intelligence | Source |
| ---- | ------------ | ------ |
| `full` | **Mandatory** — all historical context goes through RagMonk | `mode: full` in `osb.yaml` |
| `light` | Optional — knowledge files in `.osb/knowledge/` only | `mode: light` or no mode key |

**Full Mode invariant**: In Full OSB Mode, no agent may independently scan the repository
to discover historical project context. Context discovery must go through RagMonk. This is
enforced by the `intelligence` gate and by every provider adapter's instructions.

## Architecture

```
osb context build          osb intelligence status/index/doctor/refresh
        |                              |
        v                              v
  intelligence.Provider  <------  intelligence.NewProvider(cfg)
        |                               \
        |  cli transport                 mcp transport
        v                                    v
  ragmonk CLI              ragmonk mcp serve (persistent subprocess)
        |
        v
  RagMonk knowledge index
  (vector + keyword, project-local)
```

## Core components

| Component | Location | Purpose |
| --------- | -------- | ------- |
| `Provider` interface | `internal/intelligence/intelligence.go` | All intelligence operations |
| `RagMonkProvider` | `internal/intelligence/ragmonk.go` | CLI transport |
| `MCPProvider` | `internal/intelligence/mcp.go` | MCP (JSON-RPC) transport |
| `NewProvider` factory | `internal/intelligence/provider.go` | Selects transport at startup |
| `BuildTaskContext` | `internal/intelligence/context.go` | Assembles role-specific evidence |
| `FullModeError` | `internal/intelligence/intelligence.go` | Hard-stop errors in full mode |
| `osb intelligence *` | `internal/cli/intelligence.go` | CLI management subcommands |
| `osb context build` | `internal/cli/context.go` | Evidence package CLI |
| `osb gate intelligence inspect` | `internal/cli/gate.go` | Provider-based health gate |
| `osb migrate` | `internal/cli/migrate.go` | Upgrade project to full mode |

## See also

- [RagMonk setup and configuration](ragmonk.md)
- [Full Mode — rules and enforcement](full-mode.md)
- [Context packages — building and using evidence](context-packages.md)
- [Troubleshooting](troubleshooting.md)
- [Migration from light mode](migration.md)
