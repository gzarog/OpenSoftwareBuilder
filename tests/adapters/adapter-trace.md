# Adapter instruction trace

Validates that each adapter correctly routes to the neutral workflow. This is a static
instruction trace, not a live execution test.

## Trace template

For each adapter, trace a Tier 3 scenario through:

1. **Entry** — adapter project file -> neutral workflow
2. **Knowledge query** — adapter skill -> neutral knowledge procedure
3. **Architecture** — adapter agent/dispatch -> neutral architect role
4. **Implementation** — adapter agent/dispatch -> neutral implementer role
5. **Review** — adapter agent/dispatch -> neutral reviewer role
6. **Gate** — adapter gate mechanism -> CLI gate command
7. **QA** — adapter agent/dispatch -> neutral QA role
8. **Knowledge record** — adapter skill -> neutral knowledge procedure

Each step is PASS (instruction path reaches neutral policy), GAP (capability missing,
correctly reported), or FAIL (instruction path broken or capability falsely claimed).

## Expected results per adapter

### Claude Code
Steps 1-8: all PASS (full capability)

### OpenAI Codex
Steps 1-5, 7-8: PASS
Step 6: PASS (manual CLI commands documented)

### GitHub Copilot
Steps 1-5, 8: PASS
Step 6: PASS (manual CLI commands documented)
Step 7: PARTIAL — browser QA is a documented GAP

### VS Code
Not an agent provider — validates that tasks.json maps to CLI commands.

### Generic
Documentation only — validates that integration checklist covers all obligations.
