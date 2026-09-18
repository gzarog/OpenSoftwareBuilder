# Durable knowledge

The project's knowledge directory is the lead-owned durable memory across workflow runs.
It exists to avoid rediscovering settled decisions and gotchas. The lead reads and writes
it; other roles receive only the relevant excerpts in their self-contained briefs.

## Layout

```text
<knowledge_dir>/
  INDEX.md              chronological one-line-per-task index, newest first
  tasks/                completed-task history, never edited after creation
    _TEMPLATE.md
    YYYY-MM-DD-slug.md
  components/           current state, edited in place
    _TEMPLATE.md
    <component-name>.md
```

## Query before delegation

1. Skim `<knowledge_dir>/INDEX.md` for completed work in the same area.
2. For every named component, read `<knowledge_dir>/components/<component-name>.md`
   when present.
3. Extract only decisions, standing gotchas, and open follow-ups relevant to the task;
   do not copy whole records into a role brief.
4. State when no relevant record exists and proceed. An empty knowledge base is normal.

## Record after clean review and QA

1. Copy `<knowledge_dir>/tasks/_TEMPLATE.md` to
   `<knowledge_dir>/tasks/YYYY-MM-DD-short-slug.md`. Fill it from the architecture,
   implementation, review, and QA evidence. Keep it concise, omit empty sections, and
   include `Tier: 1|2|3 — <one-clause reason>`.
2. Add one newest-first row to `<knowledge_dir>/INDEX.md` linking the dated task record.
3. For each touched component, create a missing
   `<knowledge_dir>/components/<component-name>.md` from
   `<knowledge_dir>/components/_TEMPLATE.md`, then edit it in place. Keep **Current
   shape** accurate, add or remove **Standing gotchas**, and update **Open follow-ups**
   so the file describes the component now rather than accumulating history.
4. Use one task record for an epic and update every touched component record. Skip
   recording only for a genuine Tier-1 direct trivial edit, using the knowledge-gate
   exception command.

Completed task records are immutable history. Never put in-progress checkpoint state in
them. Do not transcribe code structure or signatures that current source already provides,
and do not store diff or version-control history when the version-control tools are
authoritative. Point to the current source or authoritative artifact instead.
