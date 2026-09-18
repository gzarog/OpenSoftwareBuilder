# Scenario: Tier 1 trivial edit

## Setup
- Initialize project with `osb init`
- Create a source file in configured source directory

## Steps
1. Lead classifies a comment typo fix as Tier 1
2. Lead makes the edit directly
3. Lead runs `osb gate knowledge skip "tier-1 comment typo"`
4. No pipeline, no knowledge record needed

## Expected
- No architect, reviewer, or QA dispatch
- Knowledge gate shows SKIPPED with reason
- Review gate not triggered (no logic change)
