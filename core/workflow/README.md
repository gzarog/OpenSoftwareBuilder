# Open Software Builder workflow

This is the canonical workflow policy. It is repository policy for any project that
adopts Open Software Builder. Provider adapters add only provider mechanics; they do
not override this policy.

## Triage and discovery

Classify before work. **Tier 1** is a single-line/config/comment edit with no logic
change: handle directly, with no pipeline or knowledge record. **Tier 2** is a
mechanical, already-decided implementation: implement then independently review; auth,
data, money, settlement, and external input always require review. **Tier 3** needs a
design decision, changes a public contract, or crosses components: knowledge,
architecture, implementation, review, QA, knowledge. When the behavior is genuinely
undecided, use Tier 3; proximity to a sensitive area alone does not make it Tier 3.

For symbols, callers, or blast radius, first check whether the project has a structural
index (e.g. CodeGraph, LSP, or equivalent), then use an available structural explorer.
If there is no index, or the index cannot resolve the symbol, record that condition and
fall back to targeted source search plus direct caller inspection. If an index exists but
every mapped explorer is unavailable, record an explicit verification gap; grep cannot
establish an authoritative absence of dynamic-dispatch callers. Use text search for prose,
config, literals, and TODOs. Reuse discovery only with provenance (claim, command/query,
content anchor, and observation); invalidate and revalidate after relevant edits,
dependency/scope changes, interruption, contradictory evidence, or watcher gaps.

Text-search results cannot prove the absence of interface-dispatch callers. Share
still-valid structural output with later briefs instead of re-querying; do not re-read
an unchanged canonical policy in the same context. Quote code by distinctive content
rather than unstable coordinates.

## Pipeline and handoffs

Read this unchanged policy once per fresh context. Every dispatch is focused and
self-contained: goal; tier and reason; owned/excluded files; full relevant
acceptance-criteria block; milestone; relevant policy/knowledge evidence; and required
return. Do not say "above". Returns state outcome, file/behavior delta, AC status, exact
commands/results, evidence added/invalidated, and blockers. On interruption, read the
physical checkpoint first, inventory changes with the project's change-detection command,
state verified/missing work, then resume from the recorded milestone. For a repair, issue
a fresh delta brief with retained scope, the full relevant AC block, findings, verified
state, and invalidated evidence; it must not rely on earlier context. After a long or
interrupted call or review loop, synchronize the structural index before relying on it
where a watcher gap is possible.

Knowledge query means skim the knowledge index and relevant component records, then put
only useful excerpts in the next brief; no existing record is a normal result. If
architecture splits an epic, follow declared dependency waves and file ownership. Each
wave can batch only mechanical/standard review; sensitive work stays individual. Its
full-suite QA happens once after clean review and covers every AC. A finding loops back
only to its affected unit; return to architecture when the specification itself is wrong.

Tier 3 stages are: query relevant knowledge; architect; dependency-ordered implementers;
independent reviewer and repair loop; fresh independent QA and repair/design loop; then
lead-owned knowledge update. A reviewer's clean result never substitutes for QA. No
independent reviewer capability is a blocked gap, never lead self-review. Sensitive
subtasks (auth, money, settlement, external-provider boundaries) are reviewed
individually; only mechanical/standard disjoint slices may be batched. Serial work and
parallel work cost similar work tokens; parallelism only buys time, while extra agents
duplicate context. Fan out only for disjoint files and interfaces when speed justifies it,
normally capped at 3-4. Dispatch dependency-ordered waves. Review mechanical/standard
units once per wave and sensitive units individually. QA runs the affected suite once per
cleared wave and checks every unit's AC. A blocking finding returns only its unit to
implementation, or architecture when the spec is wrong. Record one knowledge task per epic
and update every touched component in place.

Architect specs use five ordered sections: **Interfaces**, **Acceptance criteria**,
**Milestones**, **Tradeoffs**, and **Risks**. They give exact interfaces, concrete AC,
and resumable milestones ending in a green build. Split work only into independently
shippable units. Define a shared type, message, or API once in a preceding **Shared
contracts** block. Every unit then declares, in order, `Files: <exact paths>`,
`Depends on: none|<unit names>`, `Parallel-safe: yes|no`, and
`Risk tier: mechanical|standard|sensitive`. `yes` requires disjoint files and no
dependency or in-flight shared interface. Risk tier guides review isolation and does not
replace Tier 1/2/3 task triage.

Implementers follow the spec, checkpoint early and before long work, stay scoped, and
build/test their scope. For guarantee tests, deliberately break the guarantee, rebuild
before each test, observe failure, restore byte-identically, rebuild, and observe pass;
report both directions or an explicit inability. A hand-built harness must match
production wiring.

Reviewers report, do not fix: independently inspect callers/tests and report file,
problem, severity, and concrete repair. Only a reviewer with no blocking findings may
approve the review gate. QA reports, does not fix: independently runs affected build,
test, and fitness; adds e2e for multi-component/contract changes; checks every AC; and
drives a real golden and edge browser flow for UI changes. Skips are gaps, never passes.

For source work, a clean independent reviewer pass and reviewer-gate approval are
mandatory before QA; fresh clean QA is mandatory before completion. Neither implementer
evidence nor a scope-only documentation review can satisfy either requirement. QA records
what was run or clicked, expected and actual results, severity, and every AC verdict.
Browser QA reads real content after the golden path and an edge case, rather than merely
observing no crash.

## Commands, checkpoints, and documentation-only work

Use the project's configured build, test, fitness, and e2e commands from `osb.yaml`.
Use the project's change-detection method after delegation: in a VCS work tree it is
content-authoritative; without VCS its timestamp scan is only a lead and misses old or
byte-identical changes. It also identifies leftover checkpoints. Physical checkpoint and
state paths are configured in `osb.yaml` (default `.osb/progress/` and `.osb/state/`).

The no-VCS scan is a timestamp lead, not a content comparison: old changes can be
invisible and byte-identical writes can appear changed. It is useful for re-inventory
only. A source gate is mandatory after a clean independent source review; no reviewer is
an explicit block. Before closure, fresh QA must pass. A scope-only documentation review
is never a global source approval.

Gate scripts are authoritative. Only a clean independent reviewer may record source
approval, and must never do so with a blocking finding. Only a genuine Tier-1 direct
trivial edit may skip the knowledge record.

Checkpoints are portable Markdown stored at the configured checkpoint path
(`<checkpoint_dir>/<sub-task>.md`, `<checkpoint_dir>/review-<subject>.md`, and
`<checkpoint_dir>/qa-<subject>.md`). They state subject, tier, milestone, done and
verified, in progress, remaining or not yet examined, decisions, invalidated evidence,
and blockers. An implementer writes early, after every milestone, and before long work; a
reviewer updates per confirmed finding and before long verification; QA updates per
acceptance-criterion verdict and before long verification. Delete one only after its
successful completed report; the reviewer approves first when source approval is required.
Retain incomplete checkpoints so a replacement can resume from verified state.

For documentation/policy-only milestones, inspect prose, links, and stated scenario
instead of runtime build/test/fitness/e2e/browser checks. This excludes source and
runtime configuration. Independent policy review and QA still apply, and this scope must
never approve unrelated source work. No global approval is implied while unrelated source
work is underway.

## Knowledge

The lead queries durable knowledge before non-trivial dispatch and, after clean review
and QA, creates an immutable task record, updates the index, and updates each touched
component in place. Every task record has `Tier: 1|2|3` and a reason. See
[KNOWLEDGE.md](../knowledge/KNOWLEDGE.md).
