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
verification in `SKILL.md`. Use `ragmonk_search` / `ragmonk_explore` for the bounded
knowledge retrieval before architecture. Use `ragmonk_symbol` / `ragmonk_callers` /
`ragmonk_callees` / `ragmonk_impact` for targeted structural queries during architecture,
implementation, and review (in place of a custom code-analysis engine).

## Startup verification (`osb.yaml` → `ragmonk`)

```yaml
ragmonk:
  enabled: true
  required: true
  retrieve_before_architecture: true
  refresh_after_knowledge_change: true
```

| Field | Effect |
| --- | --- |
| `enabled: false` | RagMonk is not used at all; skip verification and retrieval. |
| `enabled: true, required: false` | Attempt verification; on failure, warn once and continue without RagMonk-backed retrieval. |
| `enabled: true, required: true` | Attempt verification; on failure, **stop the OSB workflow before Architect is dispatched.** |
| `retrieve_before_architecture: true` | Run bounded knowledge retrieval before dispatching the Architect. |
| `refresh_after_knowledge_change: true` | After a checkpoint appends durable knowledge events, request a RagMonk index refresh rather than waiting for watch-mode. A checkpoint with no new knowledge never triggers this — see `knowledge.md` §Watermark. |

This field was previously named `refresh_after_checkpoint`; that name is deprecated and
must not be reintroduced — refreshing on every checkpoint (rather than only when durable
knowledge actually changed) causes unnecessary indexing overhead.

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

## Retrieval budgets (per role) — initial defaults, not ceilings

These role-specific budgets are **starting points for the cheap, common case, not evidence
caps**. RagMonk already supports `max_chars`, `max_files`, `max_graph_nodes`, `limit`, and
`max_depth` — apply these internal defaults without exposing every knob in `osb.yaml`:

| Role | Initial retrieval | Expand when necessary |
| --- | --- | --- |
| Architect | `ragmonk_explore(max_chars=6000, max_files=6, max_graph_nodes=25)` when broad context is needed | Query a named subsystem, contract, decision, or linked file; widen only the relevant dimension. |
| Implementer | prefer `ragmonk_symbol` / `ragmonk_search(limit=3)`; bounded explore only if needed (`max_chars=2500, max_files=3, max_graph_nodes=10`) | Retrieve the exact caller/interface/behavior needed to safely implement its unit. |
| Reviewer | targeted `ragmonk_impact` / `ragmonk_callers` / `ragmonk_callees` first (`max_depth=2, limit=20`) | Widen dependency scope when a changed public symbol or relevant edge lies outside the initial results. |
| QA | no routine RagMonk lookup | Retrieve exact spec/source evidence only when an AC requires it. |

See `quality.md` §Context expansion triggers for exactly when expansion is required — do
not expand solely because more data exists.

## Adaptive retrieval: escalation

```text
initial: ragmonk_explore(query, max_chars=6000, max_files=6)
result:  evidence truncated / a critical interface is still unclear
next:    ragmonk_symbol(precise_interface)
         OR ragmonk_explore(narrow_query, max_chars=12000, max_files=10)
stop:    once the needed requirement/contract is established, or a blocker is reported
```

The numbers above are illustrative, not a fixed second-stage default. Never repeatedly
double the whole budget, and never repeatedly retrieve the same snippet — deduplicate by
source path + location/content identity and keep useful source references, not a pasted
retrieval transcript.

`ragmonk_explore`'s response may include truncation **warnings** — inspect the actual
returned warning/result rather than assuming every tool exposes a `truncated` boolean. For
lexical/graph tools, hitting a requested limit is a cue to check adequacy, not proof that
information is missing.

If `ragmonk.required: true` and the required MCP/CLI access fails mid-task, block the
affected phase — do not silently treat missing indexed evidence as adequate. Direct file
inspection may supplement an available required RagMonk service; it does not replace a
failed required one.

## Progressive retrieval policy

Every role follows this order, stopping as soon as it has what it needs:

```text
1. current task state (state.md)
2. exact symbol lookup
3. lexical search
4. targeted graph/impact query
5. bounded explore
6. full file read only if necessary
```

Avoid opening many full files first, and avoid a broad explore for every question — start
narrow and widen only when the narrow query comes back empty or insufficient, or a
`quality.md` §Context expansion trigger applies.

## Multi-repository queries

When `osb.yaml` → `workspace.mode: multi-repo` is set (`osb/docs/MULTI_REPO.md`), every
RagMonk query names the repository id it targets, and results are not merged across
repositories without that identifier — see `knowledge.md` §Provenance and freshness for
how retrieved excerpts carry `repository_id`.

## During the task

Any role may issue targeted RagMonk queries beyond the initial pre-architecture retrieval
— e.g. an Implementer checking callers of a function it's about to change, or a Reviewer
checking blast radius — within its role's budget above.

## After the task

Per `knowledge.md`, append incremental knowledge events only when a checkpoint produces
new durable knowledge, and let RagMonk index them (via watch mode or an explicit refresh
per `refresh_after_knowledge_change`). On final consolidation, ensure RagMonk indexes the
new task and component records so future `/osb` runs can retrieve them.
