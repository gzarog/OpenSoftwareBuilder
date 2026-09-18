# OpenSoftwareBuilder Architecture

## Overview

OpenSoftwareBuilder (OSB) is a cross-platform, toolchain-agnostic build orchestration system written in Go. It detects project structure, resolves toolchains and build systems, and executes standardized build workflows across any combination of language ecosystem, AI coding provider, and execution environment.

### Design Principles

1. **Convention over configuration** -- Projects work out of the box through file-based detection; explicit configuration overrides when needed.
2. **Four-concern separation** -- Every component belongs to exactly one of four architectural concerns, described below.
3. **Descriptor-driven plugins** -- Toolchains, build systems, providers, analysis engines, and executors are declared in YAML descriptors, not compiled into the binary.
4. **Cross-platform by default** -- Path handling, shell invocation, and environment variables work identically on Windows, Linux, and macOS.
5. **Fail fast, fail clearly** -- Missing tools produce exit code 3 and a message naming the missing executable, not a stack trace.

---

## Four-Concern Separation

```
+---------------------+     +----------------------+
|   Workflow Core     |     |  Toolchain Plugins   |
|                     |     |                      |
|  Orchestration,     |     |  Language-specific   |
|  gate evaluation,   |<--->|  detection, commands, |
|  dependency order   |     |  source/generated    |
+---------------------+     +----------------------+
         |                            |
         v                            v
+---------------------+     +----------------------+
| Provider Adapters   |     | Platform / Executor  |
|                     |     |                      |
|  AI tool configs,   |     |  Command execution,  |
|  file generation    |     |  isolation, shells   |
+---------------------+     +----------------------+
```

### 1. Workflow Core (`core/`, `internal/workflow/`)

The orchestration engine. It reads the project configuration, resolves which toolchains and build systems apply, evaluates quality gates, and drives the command pipeline (restore -> build -> test -> lint -> format). It knows nothing about any specific language or tool.

### 2. Toolchain Plugins (`toolchains/`)

Each toolchain is a YAML descriptor (`toolchain.yaml`) declaring:
- **Detection rules** -- glob patterns for files that identify the toolchain (e.g., `*.csproj` for .NET).
- **Source extensions** -- which file extensions contain authored code.
- **Generated directories** -- paths to exclude from analysis and source control.
- **Required executables** -- tools that must be on PATH before commands run.
- **Commands** -- argv arrays for restore, build, test, lint, and format.
- **Analysis** -- LSP server and tree-sitter grammar names.

Supported toolchains: dotnet, node, python, go, rust, java, kotlin, cpp, php, ruby, dart, generic.

### 3. Provider Adapters (`providers/`, `adapters/`)

Each AI coding provider (Claude Code, Codex CLI, GitHub Copilot, VS Code) has a descriptor declaring which files it reads and writes, which directories it owns, and what capabilities it supports. OSB generates provider-specific configuration files from a single canonical project model.

Supported providers: claude, codex, copilot, vscode, generic.

### 4. Platform / Executor (`executors/`, `internal/executor/`, `internal/platform/`)

Executors abstract where commands run. Each executor descriptor declares its isolation level, requirements, and capabilities. The local executor runs commands on the host; docker and devcontainer executors run them in containers.

Supported executors: local, docker, devcontainer.

---

## Domain Model

### Core Entities

| Entity | Description |
|---|---|
| **Project** | The root aggregate. Contains one or more workspaces, a resolved set of toolchains, and a provider configuration. |
| **Workspace** | A buildable unit within a project (e.g., a solution, a package.json root, a go.mod directory). A monorepo has multiple workspaces. |
| **Toolchain** | A language ecosystem descriptor loaded from `toolchains/<id>/toolchain.yaml`. |
| **BuildSystem** | A package/build manager descriptor loaded from `buildsystems/<id>/buildsystem.yaml`. Refines a toolchain's commands (e.g., pnpm vs npm for node). |
| **Command** | A single executable step, represented as an argv array with optional working directory and environment overrides. |
| **Capability** | A named feature a provider supports (e.g., `memory`, `hooks`, `mcp`). Used to decide which files to generate. |
| **Provider** | An AI coding tool descriptor loaded from `providers/<id>/provider.yaml`. |
| **Platform** | The detected OS and shell. Drives path normalization and shell command wrapping. |
| **ExecutionEnvironment** | A resolved executor instance. Combines an executor descriptor with project-specific configuration (image, mounts, env vars). |

### Entity Relationships

```
Project
 +-- Workspace[]
 |    +-- Toolchain
 |    +-- BuildSystem (optional, refines Toolchain)
 |    +-- Command[] (resolved from Toolchain + BuildSystem)
 +-- Provider
 |    +-- Capability[]
 |    +-- File[] (source/target pairs)
 +-- ExecutionEnvironment
 |    +-- Executor
 +-- AnalysisProvider[]
      +-- LSP
      +-- TreeSitter
      +-- CodeGraph
```

---

## Configuration Model

### v1 -- Single-Workspace (Current)

A project with a single detected toolchain and build system. Configuration is implicit through file detection, with optional overrides in a project-level config file.

```yaml
# osb.yaml (optional)
version: 1
toolchain: dotnet
buildsystem: null  # auto-detected
provider: claude
executor: local
```

### v2 -- Multi-Workspace (Planned)

Supports monorepos with heterogeneous toolchains. Each workspace declares its own toolchain and can override commands.

```yaml
# osb.yaml
version: 2
workspaces:
  - path: src/api
    toolchain: dotnet
  - path: src/frontend
    toolchain: node
    buildsystem: pnpm
  - path: scripts
    toolchain: python
provider: claude
executor: local
```

### Configuration Precedence

1. CLI flags (highest priority)
2. Environment variables (`OSB_TOOLCHAIN`, `OSB_PROVIDER`, etc.)
3. Project config file (`osb.yaml`)
4. Auto-detection from file patterns
5. Descriptor defaults (lowest priority)

---

## Plugin Boundaries and Interfaces

### Toolchain Interface

Every toolchain descriptor must provide:

```
detect.files     -> []string    # Glob patterns that identify this toolchain
source_extensions -> []string   # File extensions for authored source code
generated        -> []string    # Directories/files to exclude
requires         -> []Require   # Executables that must exist on PATH
commands         -> CommandMap  # Named argv arrays
analysis         -> AnalysisRef # LSP and tree-sitter identifiers
```

The workflow core never imports toolchain-specific code. It loads descriptors at startup, matches detection patterns against the filesystem, and invokes commands through the executor.

### BuildSystem Interface

Build system descriptors refine a toolchain's commands:

```
toolchain  -> string     # Which toolchain this build system belongs to
detect.files -> []string # Files that identify this build system
commands   -> CommandMap # Overrides for the toolchain's commands
```

When a build system is detected, its commands replace the parent toolchain's commands for matching keys. Unmatched keys fall through to the toolchain.

### Provider Interface

Provider descriptors declare file mappings and capabilities:

```
files        -> []FilePair    # Source template -> target path
directories  -> []string      # Directories this provider owns
capabilities -> []string      # Named features
```

The adapter layer reads these descriptors and generates provider-specific files from the canonical project model.

### Executor Interface

Executor descriptors declare how commands are run:

```
isolation     -> string        # none | container
requirements  -> []Require     # What must be installed
capabilities  -> []string      # What the executor can do
configuration -> ExecutorConf  # Executor-specific settings
```

---

## CLI Command Contract

```
osb init [--provider NAME] [--toolchain NAME]
    Initialize a new project. Detects toolchain, writes osb.yaml and provider files.

osb detect
    Print detected toolchains, build systems, and project structure as YAML.

osb restore
    Run the restore/install command for each workspace.

osb build
    Run the build command for each workspace (implies restore if needed).

osb test
    Run the test command for each workspace (implies build if needed).

osb lint
    Run the lint command for each workspace.

osb format
    Run the format command for each workspace.

osb run <command>
    Run a named command from the resolved command map.

osb check
    Run all quality gates: build, test, lint.

osb generate [--provider NAME]
    Regenerate provider-specific files from the current project model.

osb info
    Print project metadata: toolchains, build systems, provider, executor.
```

### Global Flags

```
--config PATH       Path to osb.yaml (default: auto-discover)
--executor NAME     Override executor (local, docker, devcontainer)
--verbose           Print commands before execution
--dry-run           Print commands without executing them
--workspace PATH    Restrict to a single workspace
```

---

## Exit Codes

| Code | Meaning | Example |
|------|---------|---------|
| **0** | Success | Build completed, all tests passed |
| **1** | Runtime failure | Build failed, tests failed, command returned non-zero |
| **2** | Usage error | Unknown flag, invalid configuration, bad YAML |
| **3** | Missing tool | Required executable not found on PATH |

Exit code 3 is distinct from 1 because a missing tool is an environment problem, not a code problem. CI systems and scripts can branch on this to install prerequisites before retrying.

---

## Cross-Platform Path Handling

OSB normalizes all paths to forward slashes internally. Platform-specific conversion happens at two boundaries:

1. **Filesystem operations** -- The `internal/filesystem` package converts paths to the OS-native separator before calling `os.Open`, `os.Stat`, etc.
2. **Command execution** -- The executor converts paths in argv arrays when constructing shell commands for Windows (`cmd.exe` or PowerShell).

### Rules

- Descriptors always use forward slashes.
- Configuration files (`osb.yaml`) always use forward slashes.
- Glob patterns always use forward slashes.
- The only code that touches `filepath.Separator` lives in `internal/filesystem` and `internal/executor`.

---

## Analysis Subsystem

The `analysis/` directory contains descriptors for three analysis providers:

1. **LSP** -- Language Server Protocol servers provide rich code intelligence (completions, diagnostics, go-to-definition). Each toolchain names its LSP server.
2. **Tree-sitter** -- Incremental parsers provide fast syntax analysis and structural queries. Each toolchain names its grammar.
3. **Code Graph** -- Builds dependency and call graphs from tree-sitter parse trees and LSP data. Used for impact analysis and dead code detection.

Analysis providers are optional. They enhance the workflow (e.g., lint can delegate to an LSP server's diagnostics) but are not required for basic build/test operations.

---

## Migration Strategy from PowerShell

OSB replaces a prior PowerShell-based build system. The migration follows these phases:

### Phase 0 -- Architecture and Descriptors
Define the domain model, write all YAML descriptors, and document the architecture. No executable code yet. This phase validates that the descriptor schema can express all existing build configurations.

### Phase 1 -- Core Detection and CLI Skeleton
Implement toolchain detection (`internal/detection`), configuration loading (`internal/config`), and the CLI entry point (`cmd/osb`). The `osb detect` and `osb info` commands work. No commands are executed yet.

### Phase 2 -- Command Execution
Implement the local executor (`internal/executor`), the workflow engine (`internal/workflow`), and the standard commands (restore, build, test, lint, format). The `osb build` and `osb test` commands work on single-workspace projects.

### Phase 3 -- Provider Generation
Implement provider adapters (`adapters/`) that read the canonical project model and write provider-specific files. The `osb init` and `osb generate` commands work.

### Phase 4 -- Multi-Workspace and v2 Config
Implement workspace resolution for monorepos, dependency ordering between workspaces, and the v2 configuration schema. The `--workspace` flag works.

### Phase 5 -- Container Executors
Implement docker and devcontainer executors. The `--executor docker` flag works.

### Phase 6 -- Analysis Integration
Wire up LSP, tree-sitter, and code graph analysis providers. Enhanced lint and check commands can use analysis data.

### PowerShell Compatibility

During migration, the PowerShell scripts remain functional. OSB does not wrap or call them. Instead, it reimplements the same behavior from descriptors, ensuring identical command sequences. Integration tests in `tests/` compare OSB output against known-good PowerShell runs.
