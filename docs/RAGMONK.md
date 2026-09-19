# RagMonk Setup

RagMonk is OSB's knowledge-retrieval and code-intelligence dependency. It builds a
project-specific knowledge index and serves it over MCP (preferred) or its CLI
(fallback). OSB calls RagMonk directly — there is no generic "intelligence provider"
abstraction to configure.

## Installation

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/gzarog/RagMonk/main/install.ps1 | iex
```

**macOS / Linux:**

```sh
curl -fsSL https://raw.githubusercontent.com/gzarog/RagMonk/main/install.sh | sh
```

Verify: `ragmonk version`

## Initial project setup

```sh
ragmonk init            # initialize RagMonk in the project root
ragmonk source add .    # register this project as a source
ragmonk index           # build the initial knowledge index (may take a few minutes)
ragmonk status          # confirm the index is healthy
```

## `osb.yaml` configuration

```yaml
ragmonk:
  enabled: true
  required: true
  retrieve_before_architecture: true
  refresh_after_knowledge_change: true
```

| Field | Meaning |
| --- | --- |
| `enabled` | Whether OSB uses RagMonk at all. |
| `required` | If `true`, `/osb` stops before dispatching the Architect when RagMonk is unreachable or this repository isn't indexed, instead of silently continuing without it. |
| `retrieve_before_architecture` | Run bounded knowledge retrieval before the Architect stage. |
| `refresh_after_knowledge_change` | Ask RagMonk to refresh its index after a checkpoint actually appends new knowledge events, rather than relying solely on RagMonk's own watch mode. A checkpoint with no new knowledge never triggers this. (Previously named `refresh_after_checkpoint` — that name is deprecated.) |

Retrieval is also budgeted per role (Architect gets the widest budget, QA none by
default) and follows a progressive narrow-to-wide order — see
`.agents/skills/osb/references/ragmonk.md` §Retrieval budgets.

The shortest valid config (all other fields use their defaults):

```yaml
ragmonk:
  enabled: true
```

## Access preference: MCP over CLI

OSB prefers a RagMonk MCP server when one is available to the host coding assistant — it
gives lower-latency, structured access to the operations below. It falls back to
shelling out to the `ragmonk` CLI only when MCP access isn't available.

## Operations OSB uses

| Operation | Used for |
| --- | --- |
| `ragmonk_status` | Startup verification (`/osb` step 3) |
| `ragmonk_search` / `ragmonk_explore` | Bounded knowledge retrieval before architecture (`/osb` step 4) |
| `ragmonk_symbol` | Targeted symbol lookups during any role |
| `ragmonk_callers` / `ragmonk_callees` | Blast-radius checks during review |
| `ragmonk_impact` | Change-impact checks during architecture and review |

CLI equivalents follow the same naming with `ragmonk <command>`, e.g. `ragmonk status`,
`ragmonk search "<query>"`.

## Daemon / watch mode

RagMonk can watch source files and keep the index current in the background:

```sh
ragmonk daemon start
ragmonk daemon status
ragmonk daemon stop
```

With watch mode running, knowledge events OSB appends to
`.osb/knowledge/events/<task-id>.jsonl` are picked up automatically. Without it, set
`ragmonk.refresh_after_knowledge_change: true` so OSB requests an explicit refresh
whenever a checkpoint actually adds new knowledge (never on a checkpoint that adds none —
see `.agents/skills/osb/references/knowledge.md` §Watermark).

## Failure behavior

If `ragmonk.required: true` and RagMonk is unreachable or this repository is not indexed,
`/osb` stops before any role runs and reports what to fix (install RagMonk, `ragmonk
init`, `ragmonk source add .`, `ragmonk index`). It does not silently fall back to ad hoc
repository search — see `.agents/skills/osb/references/ragmonk.md` for the exact
verification procedure OSB follows.
