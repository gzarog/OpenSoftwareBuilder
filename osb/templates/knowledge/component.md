<!--
Template for a per-component rollup. Copy to
.osb/knowledge/components/<component-name>.md the first time that component is touched.
This file is EDITED IN PLACE on every subsequent task (not appended to) -- it reflects
current state, not history. History lives in tasks/.
-->

# <component-name>

**Last updated:** YYYY-MM-DD (task: tasks/YYYY-MM-DD-short-slug.md)
**Repository:** <repository-id, or omit in single-repo mode>

## Current shape

What this component owns, its key interfaces/endpoints, and its data store. Enough for
an Architect to orient without re-reading the whole codebase.

## Standing gotchas

Constraints that keep being relevant -- quirks of this component's domain, integration
points, or infra that a new task should know before touching it. When a source change
makes an entry here stale, remove it from this section but mark the underlying knowledge
event `superseded` (never delete it) in `.osb/knowledge/events/` -- see
`osb/references/knowledge.md` §Provenance and freshness. This section holds only entries
currently believed true; audit history lives in the event log and task records.

## Open follow-ups

Deferred work or known gaps still outstanding for this component. Remove once resolved.
