package knowledge

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type Manager struct {
	root string
	dir  string
}

func NewManager(root string, knowledgeDir string) *Manager {
	return &Manager{
		root: root,
		dir:  filepath.Join(root, knowledgeDir),
	}
}

// TaskRecordOptions carries optional metadata for automated task recording (Phase 14).
type TaskRecordOptions struct {
	Components []string // component names touched by this task
	Status     string   // in-progress | shipped | abandoned
	Tier       int      // 1-5 effort tier
	Summary    string   // brief one-line summary of what was done
	Decisions  string   // key decisions captured inline
}

// ComponentRecordOptions carries optional metadata for component records (Phase 14).
type ComponentRecordOptions struct {
	TaskID   string // task that prompted this record
	Status   string // active | deprecated | removed
	Tier     int
	Language string
	Purpose  string
}

func (m *Manager) EnsureDirs() error {
	dirs := []string{
		m.dir,
		filepath.Join(m.dir, "tasks"),
		filepath.Join(m.dir, "components"),
	}
	for _, d := range dirs {
		if err := os.MkdirAll(d, 0755); err != nil {
			return err
		}
	}
	return nil
}

func (m *Manager) TaskCount() int {
	entries, _ := os.ReadDir(filepath.Join(m.dir, "tasks"))
	count := 0
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(e.Name(), ".md") {
			count++
		}
	}
	return count
}

func (m *Manager) ComponentCount() int {
	entries, _ := os.ReadDir(filepath.Join(m.dir, "components"))
	count := 0
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(e.Name(), ".md") {
			count++
		}
	}
	return count
}

func (m *Manager) IndexPath() string {
	return filepath.Join(m.dir, "INDEX.md")
}

func (m *Manager) HasIndex() bool {
	_, err := os.Stat(m.IndexPath())
	return err == nil
}

func (m *Manager) LatestMtime() (float64, error) {
	var latest float64
	err := filepath.Walk(m.dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		mtime := float64(info.ModTime().Unix())
		if mtime > latest {
			latest = mtime
		}
		return nil
	})
	return latest, err
}

func (m *Manager) RecordStatus() string {
	tasks := m.TaskCount()
	components := m.ComponentCount()
	return fmt.Sprintf("%d task records, %d component records", tasks, components)
}

func (m *Manager) IndexRows(limit int) ([]string, error) {
	data, err := os.ReadFile(m.IndexPath())
	if err != nil {
		return nil, err
	}
	lines := strings.Split(string(data), "\n")
	var rows []string
	inTable := false
	for _, line := range lines {
		if strings.HasPrefix(line, "| Date") {
			inTable = true
			continue
		}
		if inTable && strings.HasPrefix(line, "|---") {
			continue
		}
		if inTable && strings.HasPrefix(line, "|") {
			rows = append(rows, strings.TrimSpace(line))
			if len(rows) >= limit {
				break
			}
		}
	}
	return rows, nil
}

func (m *Manager) Dir() string { return m.dir }

// CreateTaskRecord creates a structured task Markdown file with YAML front matter.
// An optional TaskRecordOptions enables automated recording from workflow artifacts.
func (m *Manager) CreateTaskRecord(name string, opts ...TaskRecordOptions) (string, error) {
	if err := m.EnsureDirs(); err != nil {
		return "", err
	}

	var o TaskRecordOptions
	if len(opts) > 0 {
		o = opts[0]
	}

	date := time.Now().Format("2006-01-02")
	status := o.Status
	if status == "" {
		status = "in-progress"
	}

	// Build YAML front matter
	fm := fmt.Sprintf("---\nosb_type: task\ntask_id: %s\nstatus: %s\ndate: %s\n", name, status, date)
	if o.Tier > 0 {
		fm += fmt.Sprintf("tier: %d\n", o.Tier)
	}
	if len(o.Components) > 0 {
		fm += "component:\n"
		for _, c := range o.Components {
			fm += fmt.Sprintf("  - %s\n", c)
		}
	}
	fm += "---\n"

	componentStr := strings.Join(o.Components, ", ")
	if componentStr == "" {
		componentStr = ""
	}

	tierStr := ""
	if o.Tier > 0 {
		tierStr = fmt.Sprintf("%d", o.Tier)
	}

	summarySection := o.Summary
	if summarySection == "" {
		summarySection = ""
	}
	decisionsSection := o.Decisions
	if decisionsSection == "" {
		decisionsSection = ""
	}

	content := fm + fmt.Sprintf(`
# %s

| Field | Value |
|---|---|
| Date | %s |
| Components | %s |
| Status | %s |
| Tier | %s |

## What & why

%s

## Decisions

%s

## Gotchas

## QA result

## Follow-ups
`, name, date, componentStr, status, tierStr, summarySection, decisionsSection)

	filename := fmt.Sprintf("%s-%s.md", date, name)
	path := filepath.Join(m.dir, "tasks", filename)
	return path, os.WriteFile(path, []byte(content), 0644)
}

// CreateComponentRecord creates a structured component Markdown file with YAML front matter.
// An optional ComponentRecordOptions enables automated recording from workflow artifacts.
func (m *Manager) CreateComponentRecord(name string, opts ...ComponentRecordOptions) (string, error) {
	if err := m.EnsureDirs(); err != nil {
		return "", err
	}

	var o ComponentRecordOptions
	if len(opts) > 0 {
		o = opts[0]
	}

	date := time.Now().Format("2006-01-02")
	status := o.Status
	if status == "" {
		status = "active"
	}

	fm := fmt.Sprintf("---\nosb_type: component\nname: %s\nstatus: %s\ndate: %s\n", name, status, date)
	if o.Tier > 0 {
		fm += fmt.Sprintf("tier: %d\n", o.Tier)
	}
	if o.TaskID != "" {
		fm += fmt.Sprintf("task_id: %s\n", o.TaskID)
	}
	if o.Language != "" {
		fm += fmt.Sprintf("language: %s\n", o.Language)
	}
	fm += "---\n"

	tierStr := ""
	if o.Tier > 0 {
		tierStr = fmt.Sprintf("%d", o.Tier)
	}

	purposeSection := o.Purpose

	content := fm + fmt.Sprintf(`
# %s

| Field | Value |
|---|---|
| Date | %s |
| Status | %s |
| Tier | %s |
| Language | %s |

## Purpose

%s

## Interfaces

## Dependencies

## Notes
`, name, date, status, tierStr, o.Language, purposeSection)

	filename := fmt.Sprintf("%s-%s.md", date, name)
	path := filepath.Join(m.dir, "components", filename)
	return path, os.WriteFile(path, []byte(content), 0644)
}

// IndexRows is kept for light-mode backward compatibility.
// In full mode, RagMonk is the index — do not call this for knowledge discovery.
