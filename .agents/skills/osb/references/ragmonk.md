# OSB × RagMonk (Reference)

OSB does not implement its own repository-intelligence engine. It delegates knowledge
retrieval and project memory indexing to **RagMonk**. OSB does not introduce a generic
`IntelligenceProvider` abstraction — it calls RagMonk directly.

## Access preference

1. **MCP** — preferred. If a RagMonk MCP server is available to the host, use its tools
   directly.
2. **CLI** — fallback, used only when MCP access is unavailable but the `ragmonk`
   executable is present.

## Useful RagMonk operations

```text
ragmonk_explore
ragmonk_search
ragmonk_symbol
ragmonk_callers
ragmonk_callees
ragmonk_impact
ragmonk_status
```

Use `ragmonk_status` (or CLI equivalent, e.g. `ragmonk status`) for the startup
verification in `SKILL.md` step 3. Use `ragmonk_search` / `ragmonk_explore` for the
bounded knowledge retrieval in step 4. Use `ragmonk_symbol` / `ragmonk_callers` /
`ragmonk_callees` / `ragmonk_impact` for targeted structural queries during architecture,
implementation, and review (in place of a custom code-analysis engine).

## Startup verification (`osb.yaml` → `ragmonk`)

```yaml
ragmonk:
  enabled: true
  required: true
  retrieve_before_architecture: true
  refresh_after_checkpoint: true
```

| Field | Effect |
| --- | --- |
| `enabled: false` | RagMonk is not used at all; skip verification and retrieval. |
| `enabled: true, required: false` | Attempt verification; on failure, warn once and continue without RagMonk-backed retrieval. |
| `enabled: true, required: true` | Attempt verification; on failure, **stop the OSB workflow before Architect is dispatched.** |
| `retrieve_before_architecture: true` | Run the step-4 knowledge retrieval before dispatching the Architect. |
| `refresh_after_checkpoint: true` | After appending knowledge events, request a RagMonk index refresh rather than waiting for watch-mode. |

## Verification procedure

1. Call `ragmonk_status` (MCP) or `ragmonk status` (CLI).
2. Confirm RagMonk is running/reachable.
3. Confirm the current repository is registered and indexed (not just that RagMonk itself
   is alive).
4. If either check fails and `required: true`, stop and report, e.g.:

   ```text
   OSB requires RagMonk for this project (ragmonk.required: true), but RagMonk is not
   reachable / this repository is not indexed.

   To fix:
     1. Install RagMonk if not already installed.
     2. Run `ragmonk init` and `ragmonk source add .` in the project root.
     3. Run `ragmonk index` to build the initial index.
     4. Re-run /osb <task>.
   ```

5. Do not silently fall back to ad hoc repository search when `required: true` — that
   defeats the point of requiring RagMonk (consistent, indexed project memory).

## During the task

Any role may issue targeted RagMonk queries beyond the initial step-4 retrieval — e.g. an
Implementer checking callers of a function it's about to change, or a Reviewer checking
blast radius. These use the same MCP/CLI access rules above.

## After the task

Per `knowledge.md`, append incremental knowledge events as the task proceeds and let
RagMonk index them (via watch mode or an explicit refresh per `refresh_after_checkpoint`).
On final consolidation, ensure RagMonk indexes the new task and component records so future
`/osb` runs can retrieve them.
