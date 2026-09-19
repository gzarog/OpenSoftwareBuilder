package event

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Store manages the JSONL event files for a single active task.
// Layout: <root>/<progressDir>/<taskID>/knowledge/<role>.jsonl
type Store struct {
	dir string
}

// NewStore creates a Store scoped to the given task.
func NewStore(root, progressDir, taskID string) *Store {
	return &Store{
		dir: filepath.Join(root, progressDir, taskID, "knowledge"),
	}
}

// Dir returns the absolute path of the task knowledge directory.
func (s *Store) Dir() string { return s.dir }

// EnsureDir creates the knowledge directory for this task if it does not exist.
func (s *Store) EnsureDir() error {
	return os.MkdirAll(s.dir, 0755)
}

// rolePath returns the absolute JSONL file path for the given role.
func (s *Store) rolePath(role string) string {
	return filepath.Join(s.dir, role+".jsonl")
}

// Append validates and appends a knowledge event to the role-specific JSONL file.
// Returns an error if the event fails validation or is a duplicate of an existing entry.
func (s *Store) Append(e *KnowledgeEvent) error {
	if err := e.Validate(); err != nil {
		return fmt.Errorf("invalid event: %w", err)
	}

	// Assign ID if not already set.
	if e.ID == "" {
		if e.None {
			e.ID = fmt.Sprintf("none-%s", e.Role)
		} else {
			e.ID = GenerateID(e.Role, e.Type, e.Summary)
		}
	}

	// Assign timestamp if not already set.
	if e.Timestamp.IsZero() {
		e.Timestamp = time.Now().UTC()
	}

	// Deduplication: reject events with the same content hash.
	if !e.None {
		existing, err := s.ReadRole(e.Role)
		if err != nil {
			return fmt.Errorf("reading existing events for dedup: %w", err)
		}
		hash := e.ContentHash()
		for _, ex := range existing {
			if ex.ContentHash() == hash {
				return fmt.Errorf("duplicate event: same role+type+summary already captured (existing id=%s)", ex.ID)
			}
		}
	}

	if err := s.EnsureDir(); err != nil {
		return fmt.Errorf("creating knowledge dir: %w", err)
	}

	data, err := e.Marshal()
	if err != nil {
		return fmt.Errorf("marshaling event: %w", err)
	}

	path := s.rolePath(e.Role)
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("opening event file: %w", err)
	}
	defer f.Close()

	if _, err := fmt.Fprintf(f, "%s\n", data); err != nil {
		return fmt.Errorf("writing event: %w", err)
	}
	return nil
}

// AppendFromJSON reads a KnowledgeEvent from a JSON file and appends it.
func (s *Store) AppendFromJSON(path string) (*KnowledgeEvent, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("reading JSON file: %w", err)
	}
	var e KnowledgeEvent
	if err := json.Unmarshal(data, &e); err != nil {
		return nil, fmt.Errorf("parsing JSON: %w", err)
	}
	if err := s.Append(&e); err != nil {
		return nil, err
	}
	return &e, nil
}

// ReadRole returns all events captured by the given role. Returns nil (not an error)
// when no events have been captured yet for this role.
func (s *Store) ReadRole(role string) ([]*KnowledgeEvent, error) {
	path := s.rolePath(role)
	f, err := os.Open(path)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("opening %s events: %w", role, err)
	}
	defer f.Close()

	var events []*KnowledgeEvent
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		e, err := Unmarshal([]byte(line))
		if err != nil {
			return nil, fmt.Errorf("parsing event line in %s.jsonl: %w", role, err)
		}
		events = append(events, e)
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("reading %s events: %w", role, err)
	}
	return events, nil
}

// ReadAll returns all events from all roles in the canonical role order.
func (s *Store) ReadAll() ([]*KnowledgeEvent, error) {
	var all []*KnowledgeEvent
	for _, role := range AllRoles {
		events, err := s.ReadRole(role)
		if err != nil {
			return nil, err
		}
		all = append(all, events...)
	}
	return all, nil
}

// Summary builds a per-role RoleSummary map covering all four roles.
func (s *Store) Summary() map[string]RoleSummary {
	result := make(map[string]RoleSummary, len(AllRoles))
	for _, role := range AllRoles {
		events, _ := s.ReadRole(role)
		sum := RoleSummary{ByType: make(map[string]int)}
		for _, e := range events {
			if e.None {
				sum.HasNone = true
				sum.NoneReason = e.NoneReason
			} else {
				sum.Count++
				sum.ByType[e.Type]++
			}
		}
		result[role] = sum
	}
	return result
}

// Exists returns true when the task knowledge directory already contains at
// least one JSONL file (i.e. the task has some captured events).
func (s *Store) Exists() bool {
	for _, role := range AllRoles {
		if _, err := os.Stat(s.rolePath(role)); err == nil {
			return true
		}
	}
	return false
}

// ListTaskIDs returns all task IDs under progressDir that contain a knowledge
// sub-directory. Used by `osb knowledge pending` when no --task-id is given.
func ListTaskIDs(root, progressDir string) ([]string, error) {
	base := filepath.Join(root, progressDir)
	entries, err := os.ReadDir(base)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("reading progress dir: %w", err)
	}

	var ids []string
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		knDir := filepath.Join(base, e.Name(), "knowledge")
		if stat, err := os.Stat(knDir); err == nil && stat.IsDir() {
			ids = append(ids, e.Name())
		}
	}
	return ids, nil
}
