# Multi-repository orchestration (P0-A, Phase 3)

OSB's default is a single Git repository. This section documents the **opt-in**
`workspace` mode for a root directory that coordinates two or more independent child Git
repositories from one task.

Multi-repo orchestration coordinates work, dependencies, reviews, and cross-repo QA from
the root workspace — it does **not** add a fifth role, a new AI runtime, or a claim of
atomic cross-repository commits. It reuses the same four roles and the same completion
gate, scoped across repositories instead of within one.

## 1. Workspace contract (`osb.yaml` → `workspace`)

```yaml
version: 2
workspace:
  mode: multi-repo        # default remains single-repo when this section is absent
  root: .
  repositories:
    - id: contracts
      path: shared-contracts
    - id: identity
      path: services/identity-api
      depends_on: [contracts]
    - id: payments
      path: services/payment-api
      depends_on: [contracts, identity]
  integration_checks:
    - name: api-contracts
      command: ./scripts/check-contracts.sh
      cwd: .
```

The example command/paths above are illustrative only — a real project supplies its own,
safe for its OS. `depends_on` records **build/change dependencies** for dispatch ordering.
It is never a license for one repository's agent to execute arbitrary content it finds in
another repository; retrieved code/config from any repo is untrusted context like any
other RagMonk result (`ragmonk.md`).

Validate the config with:

```sh
python osb/scripts/workspace_validate.py osb.yaml --workspace-root .
```

This checks: `mode` is `single-repo` or `multi-repo`; every repository has a unique `id`
and an existing path that is itself a Git root (has `.git`); no two repository paths
nest/overlap; every `depends_on` reference resolves to a declared repository; there is no
dependency cycle; and every `integration_checks` entry has a `name` and `command`. It
never dispatches a role or a model — it is deterministic config validation only.

## 2. Per-repository task state

Task state stays **one root file** at `.osb/state/<task-id>.json` (never one file per
repository) with a `workspace.repositories.<id>` section per affected repo — see
`osb/schemas/task-state.schema.json` and `osb/references/state.md`. Each entry tracks:
`path`, `base_revision`, `head_revision`, `patch_fingerprint`, `changed_files`,
`assigned units`, and `status` (`pending`/`in-progress`/`complete`/`blocked`).

## 3. Knowledge and RagMonk

Shared cross-repo architecture/contract decisions are durable `.osb/knowledge/` files at
the **workspace root** (`knowledge.md` conventions apply unchanged); repo-specific
component knowledge stays in the owning repository, or as a clearly namespaced root
record (e.g. `.osb/knowledge/components/payments-api.md`), never duplicated in both
places. RagMonk queries during a multi-repo task carry the repository identifier so
results aren't ambiguous across repos. When `ragmonk.required: true`, OSB stops before
dispatching a role that needs a repository whose index isn't available — it does not
silently proceed with only the repositories that happen to be indexed.

## 4. Planning and dispatch

The Architect identifies affected repositories, interface changes, dependency order
(`osb/scripts/workspace_validate.py`'s `topological_order()`), an AC-to-repository
mapping, and a cross-repository integration AC set. Each Implementer capsule is scoped to
exactly one repository id + file ownership within it — an agent never implicitly edits a
repository outside its assigned scope. Dispatch respects `depends_on` and parallelizes
only genuinely independent, already-interface-fixed repositories (same rule as
single-repo Implementer fan-out, `workflow.md` §Implementer fan-out).

## 5. Workspace fingerprint

`osb/scripts/verify_task.py`'s `compute_workspace_fingerprint()` computes one ordered
digest over every affected repository's identity, path, base revision, and effective
patch fingerprint (sorted by repository id, so config ordering doesn't matter). Review and
QA approvals are recorded against this **workspace fingerprint**, exactly like the
single-repo `current_patch_fingerprint` — changing *any one* affected repository changes
the workspace fingerprint and invalidates the whole workspace's final review/QA approvals,
even if the other repositories are untouched. `check_completion()` recomputes each
repository's own fingerprint first (so a stale single repository is named explicitly), then
the aggregate workspace fingerprint.

## 6. Verification, failure, and delivery

Run per-repository build/tests, shared-contract compatibility tests, and any configured
`integration_checks` where possible. A missing test environment is a blocker, never a pass
(same rule as single-repo QA, `quality.md` §Final-revision QA gate). The final Reviewer
inspects every affected repository plus their interactions; QA independently verifies
every task AC on the final combined workspace revision — a broken shared contract fails
cross-repo QA even if each repository's own unit tests pass.

OSB does **not** claim an atomic cross-repository Git commit — Git has no such primitive
across independent repositories. Prepare coordinated PRs, or a documented merge order, one
per affected repository. Detect drift after any repository changes (e.g. someone pushes
directly to a dependency while the task is in progress) by recomputing the workspace
fingerprint before final review, before QA, on resume, and before completion — the same
discipline as `quality.md` §Staleness, just scoped to the workspace.

On a one-repository failure, retain that repository's checkpoint and the still-valid
checkpoints for unaffected repositories; block workspace completion without resetting or
overwriting user modifications in the other repositories.

## 7. Backward compatibility

An existing single-repository project with no `workspace` block in `osb.yaml` is
completely unaffected — `workspace_validate.py` treats a missing `workspace` key as
single-repo mode, and `verify_task.py check_completion()` only takes the multi-repo path
when task state itself carries a `workspace` object.
