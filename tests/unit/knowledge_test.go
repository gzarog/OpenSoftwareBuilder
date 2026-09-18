package unit

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/gzarog/opensoftwarebuilder/internal/knowledge"
)

func TestCreateTaskRecordHasFrontMatter(t *testing.T) {
	dir := t.TempDir()
	mgr := knowledge.NewManager(dir, "knowledge")

	path, err := mgr.CreateTaskRecord("auth-refactor")
	if err != nil {
		t.Fatalf("CreateTaskRecord failed: %v", err)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("reading task record: %v", err)
	}
	content := string(data)

	if !strings.HasPrefix(content, "---\n") {
		t.Error("expected YAML front matter starting with ---")
	}
	if !strings.Contains(content, "osb_type: task") {
		t.Error("expected osb_type: task in front matter")
	}
	if !strings.Contains(content, "task_id: auth-refactor") {
		t.Error("expected task_id in front matter")
	}
	if !strings.Contains(content, "## What & why") {
		t.Error("expected ## What & why section")
	}
	if !strings.Contains(content, "## Decisions") {
		t.Error("expected ## Decisions section")
	}
}

func TestTaskRecordFilename(t *testing.T) {
	dir := t.TempDir()
	mgr := knowledge.NewManager(dir, "knowledge")

	path, err := mgr.CreateTaskRecord("my-feature")
	if err != nil {
		t.Fatalf("CreateTaskRecord failed: %v", err)
	}

	base := filepath.Base(path)
	if !strings.HasSuffix(base, "-my-feature.md") {
		t.Errorf("expected filename ending in -my-feature.md, got %q", base)
	}
}

func TestTaskCount(t *testing.T) {
	dir := t.TempDir()
	mgr := knowledge.NewManager(dir, "knowledge")

	if mgr.TaskCount() != 0 {
		t.Error("expected 0 task count before any records")
	}

	mgr.CreateTaskRecord("task-one")
	mgr.CreateTaskRecord("task-two")

	if mgr.TaskCount() != 2 {
		t.Errorf("expected 2 task records, got %d", mgr.TaskCount())
	}
}
