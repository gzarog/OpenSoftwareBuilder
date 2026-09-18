# Scenario: Tier 3 full pipeline with sensitive subtask

## Setup
- Initialize project with `osb init`
- Configure build, test, and e2e commands
- Source files in multiple configured directories

## Steps
1. Lead queries knowledge index (no relevant records found)
2. Lead dispatches architect
3. Architect returns spec with:
   - Shared contracts block
   - Two units: one mechanical, one sensitive (auth)
   - Five-section format per unit
   - Dependency declared (sensitive depends on mechanical)
4. Lead dispatches implementer for mechanical unit (wave 1)
5. Implementer checkpoints and completes
6. Lead dispatches implementer for sensitive unit (wave 2)
7. Implementer checkpoints and completes with falsification evidence
8. Lead dispatches reviewer for mechanical unit
9. Reviewer reports one blocking finding
10. Lead dispatches repair to implementer with delta brief
11. Implementer fixes and rebuilds
12. Lead dispatches reviewer again — clean pass
13. Lead dispatches reviewer for sensitive unit individually
14. Reviewer — clean pass
15. Reviewer runs `osb gate review approve`
16. Lead dispatches fresh QA
17. QA runs build, test, fitness, e2e
18. QA checks every AC — all pass
19. Lead records knowledge (one task record, updates both component records)

## Expected
- Architecture spec validates with `osb validate spec`
- Dependency waves respected (mechanical before sensitive)
- Sensitive unit reviewed individually (not batched)
- Blocking finding returns only the affected unit
- Fresh QA runs after clean review, not before
- Review gate APPROVED before QA
- Knowledge index updated with new row
- Two component records created/updated
- All checkpoints deleted after completion
