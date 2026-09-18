# OSB Intelligence Provider Contract

OSB separates two concerns:

```
OpenSoftwareBuilder  =  execution intelligence  (workflow, roles, gates)
RagMonk              =  repository intelligence  (code, docs, history)
```

In **full mode** all project knowledge discovery and historical context
retrieval must go through the intelligence provider.  There is no silent
direct-filesystem fallback.

---

## Interface

The Go interface is defined in `internal/intelligence/intelligence.go`.

Conceptual operations:

| Operation            | Description                                         |
|----------------------|-----------------------------------------------------|
| `IsAvailable`        | Provider binary/service is reachable                |
| `GetStatus`          | Health snapshot (version, index, daemon)            |
| `IsSourceRegistered` | Repository root is registered with the provider     |
| `RegisterSource`     | Register the repository root                        |
| `IsIndexed`          | Knowledge index exists and is available             |
| `Index`              | Trigger incremental or full indexing                |
| `Explore`            | Free-text knowledge retrieval query                 |

---

## Full-Mode Invariant

> In full OSB mode, all project knowledge discovery and historical context
> retrieval goes through the intelligence provider.  Agents must not
> independently scan the repository to discover historical project context.

Agents may still open specific source files when implementing or reviewing
them.  The restriction applies to **knowledge discovery**, not to reading
files that are already the subject of the current task.

---

## Error Codes

| Code                           | Meaning                                  |
|--------------------------------|------------------------------------------|
| `FULL_MODE_RAGMONK_MISSING`    | RagMonk binary not found                 |
| `FULL_MODE_SOURCE_NOT_REGISTERED` | Repository not registered as a source |
| `FULL_MODE_INDEX_MISSING`      | No knowledge index exists                |
| `FULL_MODE_INDEX_FAILED`       | Indexing was attempted but failed        |
| `FULL_MODE_PROVIDER_UNHEALTHY` | Provider is reachable but unhealthy      |

---

## Current Providers

| Provider   | Module                                   | Transport |
|------------|------------------------------------------|-----------|
| `ragmonk`  | `internal/intelligence/ragmonk.go`       | CLI       |

MCP transport is planned (Phase 11) but not yet implemented.
