package intelligence

import "fmt"

// Role constants for task-context building.
const (
	RoleArchitect    = "architect"
	RoleImplementer  = "implementer"
	RoleReviewer     = "reviewer"
	RoleQA           = "qa"
)

// TaskContext is the bounded evidence package assembled before agent delegation.
type TaskContext struct {
	Query      string
	Role       string
	Evidence   []EvidenceItem
	RawOutput  string
}

// roleOpts returns retrieval options tuned for the given role.
func roleOpts(role string, baseOpts ExploreOptions) ExploreOptions {
	opts := baseOpts
	switch role {
	case RoleArchitect:
		opts.IncludeCode = true
		opts.IncludeDocs = true
		opts.IncludeTests = false
		opts.IncludeOSBKnowledge = true
	case RoleImplementer:
		opts.IncludeCode = true
		opts.IncludeTests = true
		opts.IncludeDocs = true
		opts.IncludeOSBKnowledge = true
	case RoleReviewer:
		opts.IncludeCode = true
		opts.IncludeTests = true
		opts.IncludeDocs = true
		opts.IncludeOSBKnowledge = true
	case RoleQA:
		opts.IncludeCode = false
		opts.IncludeTests = true
		opts.IncludeDocs = true
		opts.IncludeOSBKnowledge = true
	}
	return opts
}

// BuildTaskContext queries the provider and returns a role-specific evidence package.
// In full mode this must succeed — callers should treat a returned error as a hard stop.
func BuildTaskContext(provider Provider, query, role string, maxResults int) (*TaskContext, error) {
	if !provider.IsAvailable() {
		return nil, &FullModeError{
			Code:    ErrRagMonkMissing,
			Message: "RagMonk not available — cannot build task context in full mode",
			Remedy:  "Install RagMonk and run: ragmonk source add . && ragmonk index",
		}
	}

	baseOpts := ExploreOptions{
		MaxResults:          maxResults,
		IncludeCode:         true,
		IncludeTests:        true,
		IncludeDocs:         true,
		IncludeOSBKnowledge: true,
	}
	opts := roleOpts(role, baseOpts)

	augmented := query
	if role != "" {
		augmented = fmt.Sprintf("[role:%s] %s", role, query)
	}

	result, err := provider.Explore(augmented, opts)
	if err != nil {
		return nil, &FullModeError{
			Code:    ErrProviderUnhealthy,
			Message: fmt.Sprintf("RagMonk retrieval failed: %s", err),
			Remedy:  "Check ragmonk health: ragmonk doctor",
		}
	}

	return &TaskContext{
		Query:    query,
		Role:     role,
		Evidence: result.Items,
	}, nil
}
