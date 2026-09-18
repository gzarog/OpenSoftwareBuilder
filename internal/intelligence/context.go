package intelligence

import "fmt"

// Role constants for task-context building.
const (
	RoleArchitect   = "architect"
	RoleImplementer = "implementer"
	RoleReviewer    = "reviewer"
	RoleQA          = "qa"
)

// TaskContext is the bounded evidence package assembled before agent delegation.
type TaskContext struct {
	Query      string
	Role       string
	Components []string
	Tier       int
	Evidence   []EvidenceItem
	RawOutput  string
}

// ContextOptions carries optional parameters for BuildTaskContext.
type ContextOptions struct {
	// Components restricts retrieval to specific component names.
	Components []string
	// Tier is used for informational classification; does not change retrieval.
	Tier int
	// MaxResults overrides the default result count.
	MaxResults int
	// Root is the repository root, used for EnsureFreshIndex.
	Root string
}

// roleOpts returns retrieval options tuned for the given role.
func roleOpts(role string, base ExploreOptions) ExploreOptions {
	opts := base
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

// BuildTaskContext assembles a role-specific evidence package from the provider.
//
// Phase 12 freshness gate: when auto_index is configured, EnsureFreshIndex is
// called first so agents never receive stale intelligence.
// Phase 9/10: Components and OsbType filters are forwarded to the retrieval query.
// In full mode a returned error must be treated as a hard stop.
func BuildTaskContext(provider Provider, query, role string, opts ContextOptions) (*TaskContext, error) {
	if !provider.IsAvailable() {
		return nil, &FullModeError{
			Code:    ErrRagMonkMissing,
			Message: "RagMonk not available — cannot build task context in full mode",
			Remedy:  "Install RagMonk and run: ragmonk source add . && ragmonk index",
		}
	}

	// Phase 12: ensure the index is fresh before retrieval.
	if err := provider.EnsureFreshIndex(opts.Root); err != nil {
		return nil, err
	}

	maxResults := opts.MaxResults
	if maxResults == 0 {
		maxResults = 20
	}

	baseOpts := ExploreOptions{
		MaxResults:          maxResults,
		IncludeCode:         true,
		IncludeTests:        true,
		IncludeDocs:         true,
		IncludeOSBKnowledge: true,
		Components:          opts.Components,
	}
	exploreOpts := roleOpts(role, baseOpts)

	augmented := query
	if role != "" {
		augmented = fmt.Sprintf("[role:%s] %s", role, query)
	}

	result, err := provider.Explore(augmented, exploreOpts)
	if err != nil {
		return nil, &FullModeError{
			Code:    ErrProviderUnhealthy,
			Message: fmt.Sprintf("RagMonk retrieval failed: %s", err),
			Remedy:  "Check ragmonk health: ragmonk doctor",
		}
	}

	ctx := &TaskContext{
		Query:      query,
		Role:       role,
		Components: opts.Components,
		Tier:       opts.Tier,
		Evidence:   result.Items,
	}

	// Phase 10: supplement with symbol/impact evidence for roles that benefit from it.
	switch role {
	case RoleImplementer, RoleReviewer:
		for _, comp := range opts.Components {
			if sym, err := provider.Symbol(comp); err == nil && sym != "" {
				ctx.Evidence = append(ctx.Evidence, EvidenceItem{
					Content: sym,
					Kind:    "symbol",
				})
			}
			if imp, err := provider.Impact(comp); err == nil && imp != "" {
				ctx.Evidence = append(ctx.Evidence, EvidenceItem{
					Content: imp,
					Kind:    "impact",
				})
			}
		}
	}

	return ctx, nil
}
