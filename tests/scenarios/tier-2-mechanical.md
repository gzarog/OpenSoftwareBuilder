# Scenario: Tier 2 mechanical implementation

## Setup
- Initialize project with `osb init`
- Configure build and test commands in osb.yaml
- Create source files in configured directories

## Steps
1. Lead classifies adding a new helper function as Tier 2
2. Lead dispatches implementer with self-contained brief
3. Implementer checkpoints at configured path
4. Implementer builds and tests owned scope
5. Lead dispatches independent reviewer
6. Reviewer reports no blocking findings
7. Reviewer runs `osb gate review approve`
8. Lead records knowledge

## Expected
- No architect dispatch (behavior already decided)
- Checkpoint file created and deleted after completion
- Review gate shows APPROVED after step 7
- Knowledge gate shows UP TO DATE after step 8
- Build and test commands from osb.yaml used
