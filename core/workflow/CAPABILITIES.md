# Capability mapping

Check actual capability availability at dispatch time. A provider name, frontmatter
declaration, or installed-plugin example is not evidence that a tool is callable in the
current context.

| Obligation | Adapter requirement | Generic fallback / gap |
| --- | --- | --- |
| Structural code exploration | Available structural explorer (CodeGraph, LSP, language server, or equivalent) | No index or unresolved symbol: record the condition, use targeted source search and direct caller inspection. Index present but no explorer: explicit verification gap; text search cannot prove absence through dynamic dispatch. |
| Text/config/prose search | Grep, ripgrep, or equivalent text search | Plain text search is sufficient for non-structural claims. |
| Self-contained role dispatch | Provider-native agent/subagent with clean context and full neutral role | Use a clean context if the platform supports one. Conversation inheritance alone is not a handoff. |
| Independent reviewer | Fresh reviewer role/context | If independence cannot be established, source completion and gate approval are blocked. |
| Fresh independent QA | Fresh QA role/context after clean review | If fresh independent QA cannot be established, completion is blocked even if review was independent. |
| Shell source verification | Provider shell capability | Missing shell blocks required builds, tests, fitness, e2e, and deterministic gate operations; report blocked rather than infer a pass. |
| Browser/UI QA | An actually available browser/computer capability | Missing browser leaves a required UI flow unverified; report a gap, never a pass. |
| Gate lifecycle | Provider hooks or manual gate commands | Existing scripts remain authoritative. Without a shell capable of running them, required source approval or knowledge exception is blocked. |
| Checkpoints | Configured checkpoint directory | Write the canonical portable Markdown schema using ordinary file I/O. Missing file-write capability blocks resumable delegated work. |
| Durable knowledge | Knowledge adapter reads neutral procedure | Lead uses ordinary file I/O against the knowledge directory; no provider skill mechanism is required. |
| Permissions | Provider's real authorization model | Use the host's authorization model. One provider's permission store never grants another provider authority. |
| Models | Provider model/frontmatter choices | Canonical policy requires no model and invents no generic mapping. |

No adapter may claim a capability it lacks. Missing independent review and missing fresh
independent QA are separate blocking conditions. Provider tools, frontmatter, models,
lifecycle, and permission mechanics stay in adapters rather than neutral role bodies.
