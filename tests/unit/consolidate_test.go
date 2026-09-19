package unit

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/gzarog/opensoftwarebuilder/internal/event"
	"github.com/gzarog/opensoftwarebuilder/internal/knowledge"
)

func setupConsolidateFixture(t *testing.T) (string, *knowledge.Manager, *event.Store) {
	t.Helper()
	root := t.TempDir()
	mgr := knowledge.NewManager(root, ".osb/knowledge")
	store := event.NewStore(root, ".osb/progress", "OSB-CONS")
	return root, mgr, store
}

func TestConsolidate_EmptyEvents(t *testing.T) {
	root, mgr, _ := setupConsolidateFixture(t)

	result, err := mgr.Consolidate(knowledge.ConsolidateOptions{
		TaskID:      "OSB-CONS",
		ProgressDir: ".osb/progress",
	})
	if err != nil {
		t.Fatalf("Consolidate failed: %v", err)
	}
	if result.TaskRecordPath != "" {
		t.Error("expected no task record for zero events")
	}
	_ = root
}

func TestConsolidate_DryRun(t *testing.T) {
	root, mgr, store := setupConsolidateFixture(t)

	store.Append(&event.KnowledgeEvent{
		TaskID:  "OSB-CONS",
		Role:    "architect",
		Type:    "decision",
		Summary: "Use event-driven invalidation",
	})

	result, err := mgr.Consolidate(knowledge.ConsolidateOptions{
		TaskID:      "OSB-CONS",
		ProgressDir: ".osb/progress",
		DryRun:      true,
	})
	if err != nil {
		t.Fatalf("dry-run Consolidate failed: %v", err)
	}
	if !result.DryRun {
		t.Error("expected DryRun=true in result")
	}
	if result.TaskRecordPath != "" {
		t.Error("expected no task record path in dry-run")
	}

	// No files should have been written.
	tasksDir := filepath.Join(root, ".osb/knowledge/tasks")
	entries, _ := os.ReadDir(tasksDir)
	if len(entries) > 0 {
		t.Errorf("expected no task records in dry-run, found %d", len(entries))
	}
}

func TestConsolidate_ProducesTaskRecord(t *testing.T) {
	root, mgr, store := setupConsolidateFixture(t)

	store.Append(&event.KnowledgeEvent{
		TaskID:  "OSB-CONS",
		Role:    "architect",
		Type:    "decision",
		Summary: "Use event-driven cache invalidation",
		Scope:   "global",
	})
	store.Append(&event.KnowledgeEvent{
		TaskID:  "OSB-CONS",
		Role:    "implementer",
		Type:    "gotcha",
		Summary: "Lock timeout must be below provider SLA",
		Scope:   "component",
	})
	store.Append(&event.KnowledgeEvent{
		TaskID:  "OSB-CONS",
		Role:    "qa",
		Type:    "qa-result",
		Summary: "All acceptance tests pass with 0 failures",
	})

	result, err := mgr.Consolidate(knowledge.ConsolidateOptions{
		TaskID:      "OSB-CONS",
		ProgressDir: ".osb/progress",
	})
	if err != nil {
		t.Fatalf("Consolidate failed: %v", err)
	}

	if result.TaskRecordPath == "" {
		t.Fatal("expected a task record path")
	}
	if result.ActiveEvents != 3 {
		t.Errorf("expected 3 active events, got %d", result.ActiveEvents)
	}

	data, err := os.ReadFile(result.TaskRecordPath)
	if err != nil {
		t.Fatalf("reading task record: %v", err)
	}
	content := string(data)

	if !strings.Contains(content, "osb_type: task") {
		t.Error("expected osb_type: task in front matter")
	}
	if !strings.Contains(content, "task_id: OSB-CONS") {
		t.Error("expected task_id in front matter")
	}
	if !strings.Contains(content, "event-driven cache invalidation") {
		t.Error("expected architect decision in task record")
	}
	if !strings.Contains(content, "Lock timeout must be below provider SLA") {
		t.Error("expected implementer gotcha in task record")
	}
	if !strings.Contains(content, "All acceptance tests pass") {
		t.Error("expected QA result in task record")
	}
	if !strings.Contains(content, "## Decisions") {
		t.Error("expected ## Decisions section")
	}
	if !strings.Contains(content, "## Gotchas") {
		t.Error("expected ## Gotchas section")
	}
	if !strings.Contains(content, "## QA result") {
		t.Error("expected ## QA result section")
	}
	_ = root
}

func TestConsolidate_FiltersDiscarded(t *testing.T) {
	_, mgr, store := setupConsolidateFixture(t)

	store.Append(&event.KnowledgeEvent{
		TaskID:  "OSB-CONS",
		Role:    "implementer",
		Type:    "discovery",
		Summary: "Renamed variable x to request",
		Scope:   "discard",
	})
	store.Append(&event.KnowledgeEvent{
		TaskID:  "OSB-CONS",
		Role:    "implementer",
		Type:    "gotcha",
		Summary: "Real important gotcha to keep",
	})

	result, err := mgr.Consolidate(knowledge.ConsolidateOptions{
		TaskID:      "OSB-CONS",
		ProgressDir: ".osb/progress",
	})
	if err != nil {
		t.Fatalf("Consolidate failed: %v", err)
	}

	if result.Discarded != 1 {
		t.Errorf("expected 1 discarded event, got %d", result.Discarded)
	}
	if result.ActiveEvents != 1 {
		t.Errorf("expected 1 active event, got %d", result.ActiveEvents)
	}

	data, _ := os.ReadFile(result.TaskRecordPath)
	if strings.Contains(string(data), "Renamed variable x") {
		t.Error("expected discarded event to be excluded from task record")
	}
}

func TestConsolidate_HandlesSupersededAssumptions(t *testing.T) {
	_, mgr, store := setupConsolidateFixture(t)

	// Capture an assumption.
	e1 := &event.KnowledgeEvent{
		TaskID:  "OSB-CONS",
		Role:    "architect",
		Type:    "assumption",
		Summary: "Redis will be required for distributed locking",
	}
	store.Append(e1)

	// Capture an invalidating event.
	e2 := &event.KnowledgeEvent{
		TaskID:     "OSB-CONS",
		Role:       "implementer",
		Type:       "assumption-invalidated",
		Summary:    "PostgreSQL advisory locks already provide the required behavior",
		Supersedes: e1.ID,
	}
	store.Append(e2)

	result, err := mgr.Consolidate(knowledge.ConsolidateOptions{
		TaskID:      "OSB-CONS",
		ProgressDir: ".osb/progress",
	})
	if err != nil {
		t.Fatalf("Consolidate failed: %v", err)
	}

	if result.Superseded != 1 {
		t.Errorf("expected 1 superseded event, got %d", result.Superseded)
	}

	data, _ := os.ReadFile(result.TaskRecordPath)
	content := string(data)

	// The invalidated assumption should appear in the superseded section.
	if !strings.Contains(content, "Superseded assumptions") {
		t.Error("expected Superseded assumptions section")
	}
	// The invalidating event (assumption-invalidated) should appear in active content.
	if !strings.Contains(content, "PostgreSQL advisory locks") {
		t.Error("expected invalidating event in task record")
	}
}

func TestConsolidate_RequiresTaskID(t *testing.T) {
	_, mgr, _ := setupConsolidateFixture(t)

	_, err := mgr.Consolidate(knowledge.ConsolidateOptions{
		ProgressDir: ".osb/progress",
	})
	if err == nil {
		t.Error("expected error when task_id is empty")
	}
}

func TestConsolidate_TotalVsActive(t *testing.T) {
	_, mgr, store := setupConsolidateFixture(t)

	// 3 events: 1 none-marker (not counted), 1 discard, 1 active.
	store.Append(&event.KnowledgeEvent{
		TaskID: "OSB-CONS", Role: "architect", None: true, NoneReason: "no architecture decisions",
	})
	store.Append(&event.KnowledgeEvent{
		TaskID:  "OSB-CONS",
		Role:    "implementer",
		Type:    "discovery",
		Summary: "Trivial rename only",
		Scope:   "discard",
	})
	store.Append(&event.KnowledgeEvent{
		TaskID:  "OSB-CONS",
		Role:    "qa",
		Type:    "qa-result",
		Summary: "All tests pass",
	})

	result, err := mgr.Consolidate(knowledge.ConsolidateOptions{
		TaskID:      "OSB-CONS",
		ProgressDir: ".osb/progress",
	})
	if err != nil {
		t.Fatalf("Consolidate failed: %v", err)
	}

	// Total raw events from JSONL (none-marker + discard + active = 3).
	if result.TotalEvents != 3 {
		t.Errorf("expected TotalEvents=3, got %d", result.TotalEvents)
	}
	if result.Discarded != 1 {
		t.Errorf("expected Discarded=1, got %d", result.Discarded)
	}
	if result.ActiveEvents != 1 {
		t.Errorf("expected ActiveEvents=1, got %d", result.ActiveEvents)
	}
}
