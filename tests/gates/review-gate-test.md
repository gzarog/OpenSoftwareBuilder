# Review gate behavior tests

## Test: fresh project has no approval
1. Run `osb init`
2. Create a source file in configured source directory
3. Run `osb gate review inspect`
4. Expected: "NEEDS REVIEW"

## Test: approval records correctly
1. From above state
2. Run `osb gate review approve`
3. Run `osb gate review inspect`
4. Expected: "APPROVED"

## Test: new source change invalidates approval
1. From above state (APPROVED)
2. Modify a source file
3. Run `osb gate review inspect`
4. Expected: "NEEDS REVIEW"

## Test: skip records with reason
1. From above state (NEEDS REVIEW)
2. Run `osb gate review skip "paused work"`
3. Run `osb gate review inspect`
4. Expected: "SKIPPED: paused work"

## Test: new change after skip requires fresh skip/approval
1. From above state (SKIPPED)
2. Modify a source file
3. Run `osb gate review inspect`
4. Expected: "NEEDS REVIEW"

## Test: no source files = no gate
1. Empty project with no source in configured paths
2. Run `osb gate review inspect`
3. Expected: "No source files in configured paths."
