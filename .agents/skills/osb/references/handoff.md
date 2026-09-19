# OSB Handoff Contract (Reference)

All providers use the same conceptual result contract between roles. Provider-specific
files may adapt syntax (e.g. a TOML-launched Codex agent returning plain markdown, or a
Claude Code subagent returning its Task-tool result) but must not change the semantics
below.

## Common result shape

```markdown
## Outcome

Completed | Blocked | Findings | Pass | Fail

## Changes

## Acceptance Criteria

## Verification

## Knowledge Discovered

## Blockers
```

Each role's exact output format (in `roles.md`) is a specialization of this shape:

| Role | Outcome values | Notes |
| --- | --- | --- |
| Architect | (no Outcome header; produces a spec, not an outcome) | Uses `Goal` / `Implementation Units` instead of `Changes` |
| Implementer | Completed \| Blocked | `Changes` → `Changed Files` + `Implementation Summary` |
| Reviewer | Clean \| Findings | `Changes` → `Findings`; no `Verification`/`Blockers` sections |
| QA | Pass \| Fail | `Changes` → `Acceptance Criteria` detail; `Verification` → `Commands / Actions Performed`; `Blockers` → `Defects` |

## Dispatch brief (what a role receives)

Every role dispatch (subagent call, provider agent invocation, or context handoff) must
include:

- the user's original task statement,
- the specific unit of work this role is responsible for right now,
- relevant acceptance criteria,
- file scope, when applicable (Implementer, Reviewer),
- dependencies already resolved (interfaces, contracts, prior unit outputs),
- relevant RagMonk knowledge excerpts (bounded, not the whole knowledge base),
- what verification is required before reporting Completed/Pass.

## Return contract (what a role must produce)

A role's response is not accepted as final until it matches its required output format in
`roles.md`. If a role returns an incomplete or malformed result, the OSB skill asks it to
resubmit in the correct format rather than guessing at missing fields.

## Knowledge Discovered section

Every role's output includes a `## Knowledge Discovered` section. It is optional content
— if the role found nothing reusable, it may state "None" or omit entries. It is never
required to contain an entry. See `knowledge.md` for the entry format.

## Blockers

A `Blocked` Implementer, or a QA `Fail` routed to the Architect, must state precisely what
is blocking and what decision or information is needed to unblock — never just "stuck."
