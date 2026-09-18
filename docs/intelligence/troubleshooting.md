# Intelligence — Troubleshooting

Run `osb intelligence doctor` first. It performs a step-by-step check and prints a
`[OK]`, `[FAIL]`, `[WARN]`, or `[INFO]` line for each item with inline remediation hints.

## Quick-reference

| Symptom | Most likely cause | Fix |
| ------- | ----------------- | --- |
| `RagMonk not installed` | Binary not on PATH | Install RagMonk (see below) |
| `Source: not registered` | `ragmonk source add` not run | `ragmonk source add .` |
| `Index: missing` | Never indexed | `osb intelligence index` |
| `Index: degraded` | Partial or corrupt index | `osb intelligence index` |
| `Intelligence gate: FAIL` | One of the above | Resolve the listed items |
| `intelligence commands require full mode` | `mode: light` in osb.yaml | Set `mode: full` and run `osb migrate` |
| `osb context build` returns no evidence | Index empty or query too narrow | `osb intelligence index`, then broaden query |

## RagMonk not found

**Windows:**
```powershell
irm https://raw.githubusercontent.com/gzarog/RagMonk/main/install.ps1 | iex
```

**macOS / Linux:**
```sh
curl -fsSL https://raw.githubusercontent.com/gzarog/RagMonk/main/install.sh | sh
```

After installation:
```sh
ragmonk version                  # verify
ragmonk init
ragmonk source add .
ragmonk index
osb intelligence doctor
```

If the binary is in a non-standard location, set `executable:` in `osb.yaml`:
```yaml
intelligence:
  ragmonk:
    executable: /opt/ragmonk/bin/ragmonk
```

## Source not registered

```sh
ragmonk source add .
```

Run from the project root (where `osb.yaml` lives). Verify with:
```sh
ragmonk source list
```

## Index missing or degraded

```sh
osb intelligence index
```

For a forced full re-index:
```sh
ragmonk index --full
```

## Daemon not running

The daemon is optional but recommended for large projects. It watches source files and
keeps the index current without requiring manual `ragmonk index` runs.

```sh
ragmonk daemon start
ragmonk daemon status
```

Enable automatic startup on `osb init`:
```yaml
intelligence:
  ragmonk:
    auto_watch: true
```

## MCP transport issues

If you use `transport: mcp` and see connection errors:

1. Verify `ragmonk mcp serve` starts cleanly: `ragmonk mcp serve` (Ctrl-C to stop).
2. Check for port conflicts or permission issues in stderr output.
3. Fall back to CLI transport while debugging: `transport: cli`.

## Context packages return stale or missing evidence

1. Check index freshness: `osb intelligence refresh`
2. If `auto_index: true` is not set, run `osb intelligence index` before each task.
3. Verify the source file types are covered by RagMonk's indexing configuration.

## Error codes

| Code | Meaning | Fix |
| ---- | ------- | --- |
| `FULL_MODE_RAGMONK_MISSING` | Binary not on PATH | Install RagMonk |
| `FULL_MODE_SOURCE_NOT_REGISTERED` | `ragmonk source add` not run | `ragmonk source add .` |
| `FULL_MODE_INDEX_MISSING` | No index | `osb intelligence index` |
| `FULL_MODE_INDEX_FAILED` | Index operation failed | Check RagMonk logs |
| `FULL_MODE_PROVIDER_UNHEALTHY` | Retrieval error | `ragmonk doctor` |
