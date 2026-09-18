# Full OSB Mode — Rules and Enforcement

## The invariant

> **In Full OSB Mode, all project knowledge discovery and historical context retrieval
> goes through RagMonk. There is no silent direct-filesystem fallback.**

This invariant is not a suggestion. It is the architectural contract that makes OSB
context packages trustworthy. Violating it produces agents that silently operate on stale
or incomplete context — the exact failure mode OSB was designed to prevent.

## What the rule covers

| Prohibited in full mode | Permitted |
| ----------------------- | --------- |
| Walking `.osb/knowledge/` to reconstruct project history | Reading source code to understand/modify it |
| Using `grep` / file-search to find past decisions | Running tests, lint, build commands |
| Using your provider's semantic search as a substitute for `osb context build` | Using `osb context build` |
| Assuming the absence of a knowledge file means "no prior work" | Checking `osb intelligence status` |

## How it is enforced

### 1. Intelligence gate

```sh
osb gate intelligence inspect
```

Returns `PASS` only when RagMonk is installed, the source is registered, and the index is
available. Any full-mode workflow should check this gate before dispatch. The gate cannot
be manually approved — health is derived from live RagMonk state.

### 2. FullModeError — hard stops in Go code

Every `intelligence.Provider` method returns a `*intelligence.FullModeError` (never `nil`
with a fallback result) when RagMonk is unavailable. Error codes:

| Code | Meaning |
| ---- | ------- |
| `FULL_MODE_RAGMONK_MISSING` | Executable not found on PATH |
| `FULL_MODE_SOURCE_NOT_REGISTERED` | Project not registered with RagMonk |
| `FULL_MODE_INDEX_MISSING` | No index exists |
| `FULL_MODE_INDEX_FAILED` | Indexing operation failed |
| `FULL_MODE_PROVIDER_UNHEALTHY` | Provider returned an error during retrieval |

### 3. Adapter rules

Each provider adapter (Claude, Codex, Copilot, VS Code, Generic) carries an explicit
**Full Mode — Intelligence Rules** section that instructs the agent:

- Call `osb context build` before any multi-step task.
- Do not substitute file-search or your provider's semantic search.
- Hard-stop and report if RagMonk is unavailable.

See `adapters/*/README.md`.

## Enabling full mode

```yaml
# osb.yaml
mode: full
intelligence:
  provider: ragmonk
```

Or run the migration assistant:
```sh
osb migrate
```

## Disabling full mode

Set `mode: light` in `osb.yaml`. In light mode the intelligence system is optional and
operations that fail silently are acceptable. Intelligence CLI subcommands are unavailable
in light mode.

## Checking mode

```sh
osb status              # shows mode and intelligence block
osb intelligence status # shows full provider health
```
