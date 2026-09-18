# RagMonk — Setup and Configuration

RagMonk is the default intelligence provider for Full OSB Mode. It builds a local,
project-specific knowledge index and serves it through a CLI or MCP transport.

## Installation

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/gzarog/RagMonk/main/install.ps1 | iex
```

**macOS / Linux:**
```sh
curl -fsSL https://raw.githubusercontent.com/gzarog/RagMonk/main/install.sh | sh
```

Verify: `ragmonk version`

## Initial setup

```sh
# 1. Initialise RagMonk in the project root
ragmonk init

# 2. Register the project as a source
ragmonk source add .

# 3. Build the knowledge index (first run may take several minutes)
ragmonk index

# 4. Verify everything is healthy
osb intelligence doctor
```

## osb.yaml configuration

```yaml
mode: full
intelligence:
  provider: ragmonk
  ragmonk:
    executable: ragmonk          # path to binary; default: ragmonk (from PATH)
    source: project              # source name; default: project
    require_healthy_index: true  # fail if index is degraded
    auto_index: true             # run incremental index before retrieval
    auto_watch: true             # start daemon automatically on osb init
    transport: cli               # cli (default) or mcp
    retrieval:
      command: explore           # ragmonk subcommand for retrieval
      max_results: 20
      include_code: true
      include_tests: true
      include_docs: true
      include_osb_knowledge: true
```

The shortest valid config (all other fields use defaults):
```yaml
mode: full
intelligence:
  provider: ragmonk
```

## Transports

### CLI transport (default)

OSB invokes `ragmonk <subcommand>` as a child process for each operation. Simple and
requires no long-running process, but has per-call startup cost.

```yaml
ragmonk:
  transport: cli
```

### MCP transport

OSB starts a persistent `ragmonk mcp serve` subprocess and communicates with it over
JSON-RPC on stdin/stdout. Lower latency for intensive tasks.

```yaml
ragmonk:
  transport: mcp
```

## Daemon

The RagMonk daemon watches source files and keeps the index current in the background.

```sh
ragmonk daemon start    # start in background
ragmonk daemon status   # check if running
ragmonk daemon stop     # stop
```

With `auto_watch: true` in `osb.yaml`, `osb init` starts the daemon automatically if it
is not already running.

## Key CLI commands

| Command | Purpose |
| ------- | ------- |
| `osb intelligence status` | Health snapshot (mode, provider, transport, index, daemon) |
| `osb intelligence doctor` | Detailed step-by-step health check with remediation hints |
| `osb intelligence index` | Trigger a full or incremental index |
| `osb intelligence refresh` | Incremental update only when dirty |
| `osb intelligence query <text>` | Free-text knowledge query |
| `osb gate intelligence inspect` | Provider-based readiness gate |
| `osb context build "<query>" --role <role>` | Build bounded evidence package |
