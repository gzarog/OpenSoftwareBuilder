# Upgrading OSB (P2-H, Phase 8)

OSB has no resident service to upgrade — "upgrading" means replacing the `osb/` package
directory with a newer version and regenerating the host-native adapters from it. Root
`osb.yaml`, `.osb/state/`, `.osb/knowledge/`, and every other workspace file survive an
upgrade untouched.

## 1. Replace the package

Copy the new `osb/` directory over the old one (or extract a new release archive over it).
This is the **only** step that changes the replaceable package; everything below only
reads it and writes to the generated-adapter locations and `osb/manifest.json`.

## 2. Check status first

```sh
bash ./osb/install.sh doctor
```

`doctor` reports, distinguishing **pass** / **warning** / **blocked**:

- whether `osb/manifest.json`'s recorded version matches the package now on disk (a
  mismatch after step 1 is expected and exactly what `upgrade` will resolve);
- whether every registered host's generated adapter file still exists and still matches
  its last-recorded hash (a hand-edited generated file is a **warning**, not silently
  overwritten later);
- `osb.yaml` presence and per-role model configuration for every registered host
  (`host_preflight.py` `models_configured`);
- the opt-in `workspace` block, if present (`workspace_validate.py`);
- per-host capability preflight (`host_preflight.py`) — Git/worktree availability,
  RagMonk CLI presence (MCP access can't be checked from a script, and is reported
  `unknown`, not `blocked`, so it never silently reads as failing).

A `blocked` result (e.g. a missing generated file, or a workspace config error) should be
fixed, or at least understood, before proceeding to `upgrade`.

## 3. Dry-run the upgrade

```sh
bash ./osb/install.sh upgrade --dry-run [--host <host>]
```

Prints the exact version transition (`installed version X -> package version Y`) and,
file by file, whether each generated adapter would be newly written or overwritten —
without modifying anything. `osb.yaml`, `.osb/state/`, and `.osb/knowledge/` are never
listed, because `upgrade` never touches them.

## 4. Upgrade

```sh
bash ./osb/install.sh upgrade [--host <host>] [--force]
```

- Backs up every generated file about to change, plus the current `osb/manifest.json`,
  to `osb/.backup/<timestamp>/` before writing anything.
- Regenerates the selected hosts' adapters from the current `osb/agents/` and
  `osb/hosts/` templates.
- Detects a **conflict**: a generated file whose current on-disk hash doesn't match the
  hash recorded at its last generation (i.e. someone hand-edited a file OSB generates).
  Without `--force`, a conflicting file is left untouched and reported — never silently
  overwritten. With `--force`, it's backed up like any other file, then replaced.
- Updates `osb/manifest.json` with the new package version and file hashes only after a
  successful regeneration.

If anything goes wrong, restore the specific files from the timestamped backup directory
under `osb/.backup/` — the backup for a given upgrade run is self-contained.

## Migration notes between schema-affecting versions

A package upgrade that changes `osb/schemas/*.json` may need existing `.osb/state/*.json`
files migrated. `osb/scripts/verify_task.py check` will report exactly which fields are
missing/invalid against the new schema — treat that as the migration checklist for each
in-flight task's state file rather than guessing. There is no automatic state migrator;
an in-flight task with genuinely incompatible state should finish (or be abandoned) on the
old package version before upgrading, since `verify_task.py` intentionally never invents a
value for a field it can't derive.

## Release checklist (for someone cutting a new `osb/` package version)

1. Bump `PACKAGE_VERSION` in `osb/scripts/install.py`.
2. Run `python osb/scripts/validate_osb.py` and the full test suite
   (`python -m unittest discover -s osb/tests -p 'test_*.py'`) — both must pass.
3. If a schema changed, update the affected templates (`osb/templates/`) to match and
   re-run the validator (it checks the state template against the schema).
4. Regenerate this repository's own adapters (`python osb/scripts/install.py init --host
   all`) so the dogfooded `.claude/`, `.codex/`, `.github/agents/`, and
   `.agents/skills/osb/` stay in sync with the new canonical sources.
5. Document any behavior change in the relevant `osb/references/*.md` and `osb/docs/*.md`
   files — a canonical policy change with no doc update is treated as incomplete.
6. Tag the release / commit as the immutable version other workspaces will copy.
