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

func (m *Manager) CreateTaskRecord(name string) (string, error) {
	if err := m.EnsureDirs(); err != nil {
		return "", err
	}
	date := time.Now().Format("2006-01-02")
	filename := fmt.Sprintf("%s-%s.md", date, name)
	path := filepath.Join(m.dir, "tasks", filename)
	content := fmt.Sprintf(`---
osb_type: task
task_id: %s
status: in-progress
date: %s
---

# %s

| Field | Value |
|---|---|
| Date | %s |
| Components | |
| Status | in-progress |
| Tier | |

## What & why

## Decisions

## Gotchas

## QA result

## Follow-ups
`, name, date, name, date)
	return path, os.WriteFile(path, []byte(content), 0644)
}

// IndexRows is kept for light-mode backward compatibility.
// In full mode, RagMonk is the index — do not call this for knowledge discovery.
