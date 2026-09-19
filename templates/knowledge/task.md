<!--
Template for a per-task knowledge record. Copy to
.osb/knowledge/tasks/YYYY-MM-DD-short-slug.md after clean QA. This is written once and
never edited afterward -- it exists to save a future OSB run tokens, not to document
everything. Omit sections that have nothing worth saying.
-->

# <task title>

**Date:** YYYY-MM-DD
**Component(s):** <component names, or "cross-cutting">
**Status:** shipped | reverted | blocked

## What & why

One or two sentences: what changed, and the reason (not the diff -- that's in VCS).

## Decisions

Choices the Architect made and why, especially anything a future task might be tempted
to redo differently without knowing this was already considered.

## Gotchas

Non-obvious constraints hit during implementation, review, or QA -- things that cost time
and will cost time again if not written down. Skip if none.

## QA result

What was verified (commands run, acceptance criteria checked, flows exercised) and the
outcome. Should be self-sufficient without linking elsewhere.

## Follow-ups

Known gaps or deferred work, if any. Otherwise omit this section.
