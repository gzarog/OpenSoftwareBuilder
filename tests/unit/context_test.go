package unit

import (
	"errors"
	"testing"

	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
	"github.com/gzarog/opensoftwarebuilder/internal/knowledge"
)

// mockProvider is a test double implementing intelligence.Provider.
type mockProvider struct {
	available    bool
	freshErr     error
	exploreErr   error
	exploreItems []intelligence.EvidenceItem
	symbolOut    string
	impactOut    string
	indexCalled  int
	freshCalled  int
}

func (m *mockProvider) IsAvailable() bool { return m.available }
func (m *mockProvider) GetStatus() (*intelligence.Status, error) {
	return &intelligence.Status{Available: m.available}, nil
}
func (m *mockProvider) IsSourceRegistered(root string) (bool, error) { return true, nil }
func (m *mockProvider) RegisterSource(root string) error             { return nil }
func (m *mockProvider) IsIndexed() (bool, error)                     { return true, nil }
func (m *mockProvider) Index(root string) error {
	m.indexCalled++
	return nil
}
func (m *mockProvider) EnsureFreshIndex(root string) error {
	m.freshCalled++
	return m.freshErr
}
func (m *mockProvider) Explore(query string, opts intelligence.ExploreOptions) (*intelligence.ExploreResult, error) {
	if m.exploreErr != nil {
		return nil, m.exploreErr
	}
	items := m.exploreItems
	if items == nil {
		items = []intelligence.EvidenceItem{{Content: "evidence for: " + query, Kind: "raw"}}
	}
	return &intelligence.ExploreResult{Items: items}, nil
}
func (m *mockProvider) Symbol(name string) (string, error) { return m.symbolOut, nil }
func (m *mockProvider) Impact(target string) (string, error) { return m.impactOut, nil }

// newKnowledgeManager is a test helper for knowledge.Manager.
func newKnowledgeManager(t *testing.T, dir string) *knowledge.Manager {
	t.Helper()
	return knowledge.NewManager(dir, "knowledge")
}

func TestBuildTaskContextUnavailable(t *testing.T) {
	p := &mockProvider{available: false}
	_, err := intelligence.BuildTaskContext(p, "auth refactor", intelligence.RoleImplementer, intelligence.ContextOptions{})
	if err == nil {
		t.Fatal("expected error when provider unavailable")
	}
	fme, ok := err.(*intelligence.FullModeError)
	if !ok {
		t.Fatalf("expected FullModeError, got %T", err)
	}
	if fme.Code != intelligence.ErrRagMonkMissing {
		t.Errorf("expected %s, got %s", intelligence.ErrRagMonkMissing, fme.Code)
	}
}

func TestBuildTaskContextCallsFreshIndex(t *testing.T) {
	p := &mockProvider{available: true}
	_, err := intelligence.BuildTaskContext(p, "add feature", intelligence.RoleArchitect, intelligence.ContextOptions{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if p.freshCalled != 1 {
		t.Errorf("expected EnsureFreshIndex called once, got %d", p.freshCalled)
	}
}

func TestBuildTaskContextFreshnessGateBlocks(t *testing.T) {
	p := &mockProvider{available: true, freshErr: &intelligence.FullModeError{
		Code:    intelligence.ErrIndexFailed,
		Message: "index failed",
	}}
	_, err := intelligence.BuildTaskContext(p, "query", intelligence.RoleImplementer, intelligence.ContextOptions{})
	if err == nil {
		t.Fatal("expected error when freshness gate fails")
	}
}

func TestBuildTaskContextReturnsEvidence(t *testing.T) {
	p := &mockProvider{available: true}
	ctx, err := intelligence.BuildTaskContext(p, "how does auth work", intelligence.RoleQA, intelligence.ContextOptions{MaxResults: 5})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(ctx.Evidence) == 0 {
		t.Error("expected at least one evidence item")
	}
	if ctx.Query != "how does auth work" {
		t.Errorf("query not preserved: %s", ctx.Query)
	}
	if ctx.Role != intelligence.RoleQA {
		t.Errorf("role not preserved: %s", ctx.Role)
	}
}

func TestBuildTaskContextImplementerGetsSymbolImpact(t *testing.T) {
	p := &mockProvider{
		available: true,
		symbolOut: "func Auth() {...}",
		impactOut: "callers: main.go:42",
	}
	ctx, err := intelligence.BuildTaskContext(p, "auth refactor", intelligence.RoleImplementer, intelligence.ContextOptions{
		Components: []string{"auth"},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	kindsFound := map[string]bool{}
	for _, e := range ctx.Evidence {
		kindsFound[e.Kind] = true
	}
	if !kindsFound["symbol"] {
		t.Error("expected symbol evidence for implementer role")
	}
	if !kindsFound["impact"] {
		t.Error("expected impact evidence for implementer role")
	}
}

func TestBuildTaskContextArchitectNoSymbolImpact(t *testing.T) {
	p := &mockProvider{available: true, symbolOut: "sym", impactOut: "imp"}
	ctx, err := intelligence.BuildTaskContext(p, "design auth", intelligence.RoleArchitect, intelligence.ContextOptions{
		Components: []string{"auth"},
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	for _, e := range ctx.Evidence {
		if e.Kind == "symbol" || e.Kind == "impact" {
			t.Errorf("architect should not receive symbol/impact evidence, got kind=%s", e.Kind)
		}
	}
}

func TestBuildTaskContextExploreError(t *testing.T) {
	p := &mockProvider{available: true, exploreErr: errors.New("ragmonk offline")}
	_, err := intelligence.BuildTaskContext(p, "query", intelligence.RoleReviewer, intelligence.ContextOptions{})
	if err == nil {
		t.Fatal("expected error on explore failure")
	}
	fme, ok := err.(*intelligence.FullModeError)
	if !ok {
		t.Fatalf("expected FullModeError, got %T", err)
	}
	if fme.Code != intelligence.ErrProviderUnhealthy {
		t.Errorf("expected %s, got %s", intelligence.ErrProviderUnhealthy, fme.Code)
	}
}

func TestExploreOptionsFilters(t *testing.T) {
	// Verify that Components and OsbTypes are accepted in ExploreOptions.
	opts := intelligence.ExploreOptions{
		MaxResults:  10,
		IncludeCode: true,
		OsbTypes:    []string{"task", "architecture"},
		Components:  []string{"auth", "build-system"},
	}
	if len(opts.OsbTypes) != 2 {
		t.Errorf("expected 2 OsbTypes, got %d", len(opts.OsbTypes))
	}
	if len(opts.Components) != 2 {
		t.Errorf("expected 2 Components, got %d", len(opts.Components))
	}
}
