# Migration — Light Mode to Full OSB Mode

This guide covers upgrading an existing OSB project from `mode: light` (or no mode, which
defaults to light) to `mode: full`, where all historical project context goes through
RagMonk.

## Automated migration

Run the migration assistant:

```sh
osb migrate
```

It will:
1. Check whether RagMonk is installed and guide you through installation if not.
2. Register the project as a RagMonk source (`ragmonk source add .`).
3. Build the initial knowledge index (`ragmonk index`).
4. Update `osb.yaml` to set `mode: full`, `intelligence.provider: ragmonk`, and
   `auto_index: true`.

Existing `.osb/knowledge/` files are preserved and imported into the index automatically.

## Manual migration steps

If you prefer to migrate manually:

### 1. Install RagMonk

```sh
# Windows
irm https://raw.githubusercontent.com/gzarog/RagMonk/main/install.ps1 | iex

# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/gzarog/RagMonk/main/install.sh | sh
```

### 2. Register the project

```sh
ragmonk init
ragmonk source add .
```

### 3. Build the initial index

```sh
ragmonk index
```

This indexes all source files and any existing `.osb/knowledge/` Markdown records. The
first run may take several minutes depending on project size.

### 4. Update osb.yaml

```yaml
mode: full
intelligence:
  provider: ragmonk
  ragmonk:
    auto_index: true
    auto_watch: true   # optional: keep index current via daemon
```

### 5. Verify

```sh
osb intelligence doctor
osb gate intelligence inspect
```

Both should report `PASS` / `[OK]` for all items before you switch agents to full-mode
workflows.

## What changes after migration

| Before (light) | After (full) |
| -------------- | ------------ |
| Agents may scan `.osb/knowledge/` directly | Agents must use `osb context build` |
| Knowledge files are the authoritative source | RagMonk index is the authoritative source |
| `osb intelligence *` commands unavailable | All intelligence subcommands available |
| No intelligence gate | `osb gate intelligence inspect` enforced |

## Rollback

To revert to light mode:
```yaml
mode: light
```

The RagMonk index and registration are unaffected — you can re-enable full mode at any
time without re-indexing (unless the index has become stale).

## Keeping existing knowledge files

Existing records in `.osb/knowledge/` are not deleted. RagMonk indexes them alongside
source code, so their content is available through `osb context build`. You may continue
to add new records with `osb knowledge record task <name>` — they will be included in
the next incremental index.
