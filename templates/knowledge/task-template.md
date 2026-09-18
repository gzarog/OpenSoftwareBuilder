<!--
Template for a per-task knowledge record. Copy to tasks/YYYY-MM-DD-short-slug.md.
Keep it tight -- this exists to save the NEXT pipeline run tokens, not to document
everything. Omit sections that have nothing worth saying.
-->

# <task title>

**Date:** YYYY-MM-DD
**Component(s):** <component names, or "cross-cutting">
**Status:** shipped | reverted | blocked
**Tier:** 1 | 2 | 3 -- <one-clause reason>

## What & why

One or two sentences: what changed, and the reason (not the diff -- that's in VCS).

## Decisions

Choices the architect made and why, especially anything a future task might be tempted
to redo differently without knowing this was already considered.

## Gotchas

Non-obvious constraints hit during implementation or QA -- things that cost time and
will cost time again if not written down. Skip if none.

## QA result

What was verified (commands run, criteria checked, flows exercised) and the outcome.
Link to nothing else -- this should be self-sufficient.

## Follow-ups

Known gaps or deferred work, if any. Otherwise omit this section.
