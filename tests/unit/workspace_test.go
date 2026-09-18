package unit

import (
	"testing"

	"github.com/gzarog/opensoftwarebuilder/internal/workspace"
)

func TestTopologicalSort(t *testing.T) {
	workspaces := []workspace.WorkspaceInfo{
		{Name: "frontend", DependsOn: []string{"shared"}},
		{Name: "backend", DependsOn: []string{"shared"}},
		{Name: "shared"},
	}

	sorted, err := workspace.TopologicalSort(workspaces)
	if err != nil {
		t.Fatalf("sort failed: %v", err)
	}

	// shared must come before frontend and backend
	sharedIdx := -1
	for i, ws := range sorted {
		if ws.Name == "shared" {
			sharedIdx = i
		}
		if (ws.Name == "frontend" || ws.Name == "backend") && sharedIdx == -1 {
			t.Errorf("%s appeared before shared", ws.Name)
		}
	}
}

func TestCircularDependency(t *testing.T) {
	workspaces := []workspace.WorkspaceInfo{
		{Name: "a", DependsOn: []string{"b"}},
		{Name: "b", DependsOn: []string{"a"}},
	}

	_, err := workspace.TopologicalSort(workspaces)
	if err == nil {
		t.Error("expected circular dependency error")
	}
}

func TestParallelGroups(t *testing.T) {
	workspaces := []workspace.WorkspaceInfo{
		{Name: "frontend", DependsOn: []string{"shared"}},
		{Name: "backend", DependsOn: []string{"shared"}},
		{Name: "shared"},
	}

	groups := workspace.ParallelGroups(workspaces)
	if len(groups) < 2 {
		t.Errorf("expected at least 2 groups, got %d", len(groups))
	}
	// First group should be shared (no deps)
	if groups[0][0].Name != "shared" {
		t.Errorf("expected first group to be shared, got %s", groups[0][0].Name)
	}
	// Second group should have frontend and backend (parallel)
	if len(groups[1]) != 2 {
		t.Errorf("expected 2 items in second group, got %d", len(groups[1]))
	}
}
