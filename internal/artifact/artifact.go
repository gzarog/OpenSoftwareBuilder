package artifact

import (
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// Type represents the kind of durable OSB artifact.
type Type string

const (
	TypeSpec     Type = "spec"
	TypeReview   Type = "review"
	TypeQA       Type = "qa"
	TypeDecision Type = "decision"
)

// Manager writes structured Markdown artifacts to the appropriate OSB dirs.
type Manager struct {
	root string
	dirs map[Type]string
}

// NewManager creates a Manager using explicit dir paths per artifact type.
func NewManager(root, specsDir, reviewsDir, qaDir, decisionsDir string) *Manager {
	return &Manager{
		root: root,
		dirs: map[Type]string{
			TypeSpec:     filepath.Join(root, specsDir),
			TypeReview:   filepath.Join(root, reviewsDir),
			TypeQA:       filepath.Join(root, qaDir),
			TypeDecision: filepath.Join(root, decisionsDir),
		},
	}
}

// Dir returns the absolute directory for the given artifact type.
func (m *Manager) Dir(t Type) string {
	return m.dirs[t]
}

// EnsureDir creates the artifact directory if it does not exist.
func (m *Manager) EnsureDir(t Type) error {
	return os.MkdirAll(m.dirs[t], 0755)
}

// RecordOptions carries optional metadata for a new artifact file.
type RecordOptions struct {
	TaskID    string
	Component string
	Status    string // defaults to "draft"
}

// Record creates a structured Markdown file for the given artifact type and name.
// Returns the absolute path of the created file.
func (m *Manager) Record(t Type, name string, opts RecordOptions) (string, error) {
	if err := m.EnsureDir(t); err != nil {
		return "", fmt.Errorf("creating artifact dir: %w", err)
	}

	date := time.Now().Format("2006-01-02")
	status := opts.Status
	if status == "" {
		status = "draft"
	}

	var content string
	switch t {
	case TypeSpec:
		content = specTemplate(name, opts.TaskID, opts.Component, status, date)
	case TypeReview:
		content = reviewTemplate(name, opts.TaskID, opts.Component, status, date)
	case TypeQA:
		content = qaTemplate(name, opts.TaskID, opts.Component, status, date)
	case TypeDecision:
		content = decisionTemplate(name, opts.TaskID, opts.Component, status, date)
	default:
		return "", fmt.Errorf("unknown artifact type: %s", t)
	}

	filename := fmt.Sprintf("%s-%s.md", date, name)
	path := filepath.Join(m.dirs[t], filename)
	return path, os.WriteFile(path, []byte(content), 0644)
}

func frontMatter(osbType, name, taskID, component, status, date string) string {
	fm := fmt.Sprintf("---\nosb_type: %s\nname: %s\nstatus: %s\ndate: %s\n", osbType, name, status, date)
	if taskID != "" {
		fm += fmt.Sprintf("task_id: %s\n", taskID)
	}
	if component != "" {
		fm += fmt.Sprintf("component: %s\n", component)
	}
	fm += "---\n"
	return fm
}

func specTemplate(name, taskID, component, status, date string) string {
	fm := frontMatter("spec", name, taskID, component, status, date)
	return fm + fmt.Sprintf(`
# Spec: %s

## Context

## Problem

## Proposed Solution

## Alternatives Considered

## Acceptance Criteria

## Open Questions
`, name)
}

func reviewTemplate(name, taskID, component, status, date string) string {
	fm := frontMatter("review", name, taskID, component, status, date)
	return fm + fmt.Sprintf(`
# Review: %s

## Summary

## Findings

| Severity | Finding | File | Line |
|---|---|---|---|
| | | | |

## Verdict

- [ ] Approved
- [ ] Changes requested
- [ ] Blocked

## Notes
`, name)
}

func qaTemplate(name, taskID, component, status, date string) string {
	fm := frontMatter("qa", name, taskID, component, status, date)
	return fm + fmt.Sprintf(`
# QA: %s

## Scope

## Test Cases

| Case | Steps | Expected | Result |
|---|---|---|---|
| | | | |

## Evidence

## Verdict

- [ ] Pass
- [ ] Fail
- [ ] Blocked
`, name)
}

func decisionTemplate(name, taskID, component, status, date string) string {
	fm := frontMatter("decision", name, taskID, component, status, date)
	return fm + fmt.Sprintf(`
# Decision: %s

## Status

%s

## Context

## Decision

## Consequences

## Alternatives
`, name, status)
}
