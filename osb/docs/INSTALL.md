# Installing OSB in a workspace

OSB v2 ships as a **single portable `osb/` package**. There is no compiled runtime and no
separate framework directories to copy by hand.

## 1. Copy the package

```text
workspace/
└── osb/     ← copy this whole directory, unmodified, from a release or this repo
```

Never edit files under `osb/` per-project — if a project needs different behavior, that
belongs in root `osb.yaml` or project-specific `.osb/knowledge/`, not in a fork of the
package. `osb/` is meant to be replaced wholesale on upgrade (see `osb/docs/UPGRADE.md`).

## 2. Run the one-time setup

macOS/Linux/WSL:

```sh
bash ./osb/install.sh init
```

Windows PowerShell:

```powershell
./osb/install.ps1 init
```

`init` is the default action, so `bash ./osb/install.sh` alone is equivalent. The
installer:

- resolves the workspace root as `osb/`'s parent directory,
- asks which coding host(s) to register (Claude Code, Codex, Copilot — pick any subset),
- generates only the host-native discovery/agent files those hosts need,
  reproducing the canonical role contract from `osb/agents/` and `osb/SKILL.md`,
- creates root `osb.yaml` from `osb/templates/osb.yaml` if one doesn't already exist
  (an existing `osb.yaml` is never overwritten),
- creates `.osb/state/` and `.osb/knowledge/` if missing,
- writes/updates `osb/manifest.json` recording the installed package version and the
  hash of every generated file, so a later `doctor`/`upgrade` can detect drift.

It never installs or uninstalls external tools, never invents a missing per-role model,
and never starts a background process — registration is one-shot.

## 3. Fill in models

Edit root `osb.yaml` and set a model for every role, for every host you registered:

```yaml
models:
  claude-code:
    architect: <model id>
    implementer: <model id>
    reviewer: <model id>
    qa: <model id>
```

If you leave a role blank, `/osb` (or the host's documented equivalent) will ask for it
the first time it's needed and can persist the answer back into `osb.yaml`.

## 4. Set up RagMonk

See `osb/docs/RAGMONK.md`. If you don't want to require it, set `ragmonk.required: false`
in `osb.yaml` (OSB still uses it opportunistically when reachable).

## 5. Run it

| Host | Verified invocation |
| --- | --- |
| Claude Code | `/osb <task>` |
| VS Code Copilot | `/osb <task>` |
| OpenAI Codex | `$osb <task>` (fallback: `/skills` → `osb`) |

Do not assume `/osb` works on a host or host version that hasn't been smoke-tested — see
`osb/docs/HOST_COMPATIBILITY.md`. Run `bash ./osb/install.sh doctor` at any time to check
that registration, models, and RagMonk are still in a working state.

## What lives where after setup

```text
workspace/
├── osb/                          # the replaceable package — never hand-edited
├── .agents/skills/osb/SKILL.md   # generated, only if Codex and/or Copilot registered
├── .claude/skills/osb/SKILL.md   # generated, only if Claude Code registered
├── .claude/agents/...            # generated, only if Claude Code registered
├── .codex/agents/...             # generated, only if Codex registered
├── .github/agents/...            # generated, only if Copilot registered
├── .github/copilot-instructions.md  # generated, only if Copilot registered
├── osb.yaml                      # project-owned, never silently overwritten
└── .osb/
    ├── state/                    # ephemeral per-task execution state
    └── knowledge/                # durable project memory, commit this
```

Everything outside `osb/` other than the generated host-discovery files is workspace-owned
data that upgrading or replacing `osb/` must never touch — see `osb/docs/UPGRADE.md`.
