# Scenario: Interrupted agent recovery

## Setup
- Project mid-implementation with existing checkpoint
- Checkpoint records milestone 2 of 3 completed

## Steps
1. New agent reads checkpoint at configured path
2. Agent runs `osb changed` to inventory since last checkpoint
3. Agent identifies verified work (milestones 1-2) vs remaining (milestone 3)
4. Agent resumes from milestone 3
5. Agent completes, updates checkpoint, then deletes it

## Expected
- Checkpoint read before any work
- Change detection used to verify state
- No re-implementation of completed milestones
- Checkpoint updated at each milestone during recovery
- Checkpoint deleted only after successful report
