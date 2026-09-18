# Context Packages — Building and Using Evidence

A *context package* (or *evidence package*) is the bounded set of knowledge items
assembled from RagMonk before an agent is dispatched. It replaces ad-hoc file exploration
as the means of giving an agent project history and context.

## Building a context package

```sh
osb context build "<task description>" --role <role>
```

**Roles:**

| Role | `--role` value | Gets |
| ---- | -------------- | ---- |
| Architect | `architect` | Code, docs, OSB knowledge (no tests) |
| Implementer | `implementer` | Code, tests, docs, OSB knowledge, symbol/impact data |
| Reviewer | `reviewer` | Code, tests, docs, OSB knowledge, symbol/impact data |
| QA tester | `qa` | Tests, docs, OSB knowledge (no code) |

**Options:**

```sh
--component auth,api     # filter evidence to specific components
--tier 3                 # informational tier (1-4)
--max-results 30         # cap number of evidence items (default 20)
```

**Examples:**

```sh
osb context build "refactor authentication layer" --role implementer --component auth
osb context build "review PR #42" --role reviewer
osb context build "design new billing API" --role architect --tier 2
```

## What the package contains

Each evidence item has:
- **File** — the source file or knowledge record the snippet comes from.
- **Kind** — `code`, `test`, `doc`, `task`, `component`, `symbol`, `impact`, or `raw`.
- **Content** — the relevant text excerpt.
- **Score** — semantic relevance score (higher is more relevant).

For `implementer` and `reviewer` roles, symbol definitions and impact (callers/dependents)
for each named component are appended as additional items.

## Freshness

When `auto_index: true` is set in `osb.yaml`, `osb context build` automatically triggers
an incremental index (`ragmonk index`) before retrieval if the source is dirty. You can
also trigger this manually:

```sh
osb intelligence refresh    # incremental update when dirty
osb intelligence index      # always re-index
```

## Programmatic access (Go)

```go
import "github.com/gzarog/opensoftwarebuilder/internal/intelligence"

provider := intelligence.NewProvider(cfg.GetIntelligence())
ctx, err := intelligence.BuildTaskContext(provider, query, intelligence.RoleImplementer,
    intelligence.ContextOptions{
        Components: []string{"auth"},
        MaxResults: 20,
        Root:       root,
    })
if err != nil {
    // In full mode this is always a *intelligence.FullModeError — hard stop.
    return err
}
for _, item := range ctx.Evidence {
    fmt.Printf("[%s] %s\n", item.Kind, item.Content)
}
```

## Free-text queries

For ad-hoc exploration without role filtering:

```sh
osb intelligence query "how does session expiry work"
```

This calls `ragmonk explore` directly and prints raw results.
