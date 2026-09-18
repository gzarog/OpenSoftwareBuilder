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

func TestTaskRecordWithOptions(t *testing.T) {
	dir := t.TempDir()
	mgr := knowledge.NewManager(dir, "knowledge")

	opts := knowledge.TaskRecordOptions{
		Components: []string{"auth", "api"},
		Status:     "shipped",
		Tier:       3,
		Summary:    "Refactored auth layer",
		Decisions:  "Chose JWT over session cookies",
	}
	path, err := mgr.CreateTaskRecord("auth-refactor", opts)
	if err != nil {
		t.Fatalf("CreateTaskRecord with opts failed: %v", err)
	}

	data, _ := os.ReadFile(path)
	content := string(data)

	if !strings.Contains(content, "status: shipped") {
		t.Error("expected status: shipped in front matter")
	}
	if !strings.Contains(content, "tier: 3") {
		t.Error("expected tier: 3 in front matter")
	}
	if !strings.Contains(content, "- auth") {
		t.Error("expected component auth in front matter")
	}
	if !strings.Contains(content, "- api") {
		t.Error("expected component api in front matter")
	}
	if !strings.Contains(content, "Refactored auth layer") {
		t.Error("expected summary in content")
	}
	if !strings.Contains(content, "Chose JWT over session cookies") {
		t.Error("expected decisions in content")
	}
}

func TestTaskRecordDefaultStatus(t *testing.T) {
	dir := t.TempDir()
	mgr := knowledge.NewManager(dir, "knowledge")

	path, err := mgr.CreateTaskRecord("no-status-task")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	data, _ := os.ReadFile(path)
	if !strings.Contains(string(data), "status: in-progress") {
		t.Error("expected default status in-progress")
	}
}

func TestCreateComponentRecord(t *testing.T) {
	dir := t.TempDir()
	mgr := knowledge.NewManager(dir, "knowledge")

	opts := knowledge.ComponentRecordOptions{
		TaskID:   "auth-refactor",
		Status:   "active",
		Tier:     2,
		Language: "Go",
		Purpose:  "Handles authentication and session management",
	}
	path, err := mgr.CreateComponentRecord("auth-service", opts)
	if err != nil {
		t.Fatalf("CreateComponentRecord failed: %v", err)
	}

	data, _ := os.ReadFile(path)
	content := string(data)

	if !strings.Contains(content, "osb_type: component") {
		t.Error("expected osb_type: component in front matter")
	}
	if !strings.Contains(content, "name: auth-service") {
		t.Error("expected name in front matter")
	}
	if !strings.Contains(content, "task_id: auth-refactor") {
		t.Error("expected task_id in front matter")
	}
	if !strings.Contains(content, "language: Go") {
		t.Error("expected language in front matter")
	}
	if !strings.Contains(content, "tier: 2") {
		t.Error("expected tier in front matter")
	}
	if !strings.Contains(content, "Handles authentication and session management") {
		t.Error("expected purpose in content")
	}
	if !strings.Contains(content, "## Purpose") {
		t.Error("expected ## Purpose section")
	}
}

func TestComponentRecordDefaultStatus(t *testing.T) {
	dir := t.TempDir()
	mgr := knowledge.NewManager(dir, "knowledge")

	path, err := mgr.CreateComponentRecord("my-component")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	data, _ := os.ReadFile(path)
	if !strings.Contains(string(data), "status: active") {
		t.Error("expected default status active")
	}
}

func TestComponentCount(t *testing.T) {
	dir := t.TempDir()
	mgr := knowledge.NewManager(dir, "knowledge")

	if mgr.ComponentCount() != 0 {
		t.Error("expected 0 component count before any records")
	}

	mgr.CreateComponentRecord("comp-a")
	mgr.CreateComponentRecord("comp-b")
	mgr.CreateComponentRecord("comp-c")

	if mgr.ComponentCount() != 3 {
		t.Errorf("expected 3 component records, got %d", mgr.ComponentCount())
	}
}
