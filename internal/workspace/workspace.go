package workspace

import (
	"fmt"
	"path/filepath"
	"sort"
	"sync"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
)

type WorkspaceInfo struct {
	Name        string
	Path        string
	AbsPath     string
	Toolchain   string
	BuildSystem string
	DependsOn   []string
}

// ResolveWorkspaces returns workspace list from config
func ResolveWorkspaces(root string, cfg *config.Config) []WorkspaceInfo {
	if len(cfg.Workspaces) > 0 {
		var ws []WorkspaceInfo
		for name, w := range cfg.Workspaces {
			ws = append(ws, WorkspaceInfo{
				Name:        name,
				Path:        w.Path,
				AbsPath:     filepath.Join(root, w.Path),
				Toolchain:   w.Toolchain,
				BuildSystem: w.BuildSystem,
				DependsOn:   w.DependsOn,
			})
		}
		// Sort by name for determinism
		sort.Slice(ws, func(i, j int) bool {
			return ws[i].Name < ws[j].Name
		})
		return ws
	}

	// Single-workspace fallback (v1 config)
	return []WorkspaceInfo{{
		Name:    "default",
		Path:    ".",
		AbsPath: root,
	}}
}

// TopologicalSort sorts workspaces respecting depends_on
func TopologicalSort(workspaces []WorkspaceInfo) ([]WorkspaceInfo, error) {
	nameMap := map[string]*WorkspaceInfo{}
	for i := range workspaces {
		nameMap[workspaces[i].Name] = &workspaces[i]
	}

	visited := map[string]bool{}
	inStack := map[string]bool{}
	var result []WorkspaceInfo

	var visit func(name string) error
	visit = func(name string) error {
		if inStack[name] {
			return fmt.Errorf("circular dependency detected: %s", name)
		}
		if visited[name] {
			return nil
		}
		inStack[name] = true
		ws := nameMap[name]
		if ws != nil {
			for _, dep := range ws.DependsOn {
				if err := visit(dep); err != nil {
					return err
				}
			}
			result = append(result, *ws)
		}
		visited[name] = true
		inStack[name] = false
		return nil
	}

	for _, ws := range workspaces {
		if err := visit(ws.Name); err != nil {
			return nil, err
		}
	}
	return result, nil
}

// ParallelGroups returns groups of workspaces that can run concurrently
func ParallelGroups(workspaces []WorkspaceInfo) [][]WorkspaceInfo {
	sorted, err := TopologicalSort(workspaces)
	if err != nil {
		// Fallback: sequential
		var groups [][]WorkspaceInfo
		for _, ws := range workspaces {
			groups = append(groups, []WorkspaceInfo{ws})
		}
		return groups
	}

	// Group workspaces with no unmet deps
	completed := map[string]bool{}
	var groups [][]WorkspaceInfo
	remaining := sorted

	for len(remaining) > 0 {
		var group []WorkspaceInfo
		var next []WorkspaceInfo
		for _, ws := range remaining {
			ready := true
			for _, dep := range ws.DependsOn {
				if !completed[dep] {
					ready = false
					break
				}
			}
			if ready {
				group = append(group, ws)
			} else {
				next = append(next, ws)
			}
		}
		if len(group) == 0 {
			// Shouldn't happen after topo sort, but safety
			groups = append(groups, remaining)
			break
		}
		groups = append(groups, group)
		for _, ws := range group {
			completed[ws.Name] = true
		}
		remaining = next
	}
	return groups
}

// RunResult tracks results per workspace
type RunResult struct {
	Workspace string
	Success   bool
	Output    string
	Error     error
}

// RunParallel runs a function on each workspace in dependency order, parallelizing within groups
func RunParallel(groups [][]WorkspaceInfo, maxConcurrency int, fn func(WorkspaceInfo) RunResult) []RunResult {
	var allResults []RunResult
	for _, group := range groups {
		if maxConcurrency <= 1 || len(group) == 1 {
			for _, ws := range group {
				allResults = append(allResults, fn(ws))
			}
		} else {
			results := make([]RunResult, len(group))
			sem := make(chan struct{}, maxConcurrency)
			var wg sync.WaitGroup
			for i, ws := range group {
				wg.Add(1)
				sem <- struct{}{}
				go func(idx int, w WorkspaceInfo) {
					defer wg.Done()
					defer func() { <-sem }()
					results[idx] = fn(w)
				}(i, ws)
			}
			wg.Wait()
			allResults = append(allResults, results...)
		}
	}
	return allResults
}
