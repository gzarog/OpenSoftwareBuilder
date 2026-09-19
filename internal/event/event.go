package event

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"sort"
	"strings"
	"time"
)

// Valid controlled-vocabulary sets.
var (
	ValidTypes = map[string]bool{
		"decision":               true,
		"constraint":             true,
		"discovery":              true,
		"gotcha":                 true,
		"assumption":             true,
		"assumption-invalidated": true,
		"review-finding":         true,
		"qa-result":              true,
		"follow-up":              true,
	}

	ValidRoles = map[string]bool{
		"architect":   true,
		"implementer": true,
		"reviewer":    true,
		"qa":          true,
	}

	ValidScopes = map[string]bool{
		"temporary": true,
		"task":      true,
		"component": true,
		"global":    true,
		"discard":   true,
	}

	ValidConfidence = map[string]bool{
		"confirmed":  true,
		"suspected":  true,
		"unverified": true,
	}

	// AllRoles is the canonical role order for display.
	AllRoles = []string{"architect", "implementer", "reviewer", "qa"}
)

// Source identifies source files that led to a finding.
type Source struct {
	Files []string `json:"files,omitempty"`
}

// KnowledgeEvent is a single incremental knowledge capture record.
type KnowledgeEvent struct {
	ID         string    `json:"id"`
	Timestamp  time.Time `json:"timestamp"`
	TaskID     string    `json:"task_id"`
	Role       string    `json:"role"`
	Type       string    `json:"type,omitempty"`
	Scope      string    `json:"scope,omitempty"`
	Summary    string    `json:"summary,omitempty"`
	Reason     string    `json:"reason,omitempty"`
	Confidence string    `json:"confidence,omitempty"`
	Supersedes string    `json:"supersedes,omitempty"`
	None       bool      `json:"none,omitempty"`
	NoneReason string    `json:"none_reason,omitempty"`
	Source     *Source   `json:"source,omitempty"`
}

// GenerateID creates a stable event ID from role+type+summary.
func GenerateID(role, eventType, summary string) string {
	h := sha256.Sum256([]byte(role + ":" + eventType + ":" + strings.TrimSpace(summary)))
	return fmt.Sprintf("event-%x", h[:4])
}

// Validate checks that the event has all required fields with valid values.
func (e *KnowledgeEvent) Validate() error {
	if e.Role == "" {
		return fmt.Errorf("role is required")
	}
	if !ValidRoles[e.Role] {
		return fmt.Errorf("invalid role %q — must be one of: %s", e.Role, sortedKeys(ValidRoles))
	}
	if e.TaskID == "" {
		return fmt.Errorf("task_id is required")
	}

	if e.None {
		// None-marker: no type or summary required.
		return nil
	}

	if e.Type == "" {
		return fmt.Errorf("type is required")
	}
	if !ValidTypes[e.Type] {
		return fmt.Errorf("invalid type %q — must be one of: %s", e.Type, sortedKeys(ValidTypes))
	}
	if strings.TrimSpace(e.Summary) == "" {
		return fmt.Errorf("summary is required and must not be blank")
	}
	if e.Scope != "" && !ValidScopes[e.Scope] {
		return fmt.Errorf("invalid scope %q — must be one of: %s", e.Scope, sortedKeys(ValidScopes))
	}
	if e.Confidence != "" && !ValidConfidence[e.Confidence] {
		return fmt.Errorf("invalid confidence %q — must be one of: %s", e.Confidence, sortedKeys(ValidConfidence))
	}
	return nil
}

// ContentHash returns a stable hex string for deduplication (role+type+summary).
func (e *KnowledgeEvent) ContentHash() string {
	h := sha256.Sum256([]byte(e.Role + ":" + e.Type + ":" + strings.TrimSpace(e.Summary)))
	return fmt.Sprintf("%x", h[:8])
}

// Marshal serializes the event as JSON for a single JSONL line.
func (e *KnowledgeEvent) Marshal() ([]byte, error) {
	return json.Marshal(e)
}

// Unmarshal deserializes a single JSONL line into a KnowledgeEvent.
func Unmarshal(data []byte) (*KnowledgeEvent, error) {
	var e KnowledgeEvent
	if err := json.Unmarshal(data, &e); err != nil {
		return nil, err
	}
	return &e, nil
}

// RoleSummary describes the captured state for one role.
type RoleSummary struct {
	Count      int
	HasNone    bool
	NoneReason string
	ByType     map[string]int // type → count
}

// HasCheckpoint returns true when the role has either real events or a none marker.
func (r RoleSummary) HasCheckpoint() bool {
	return r.Count > 0 || r.HasNone
}

func sortedKeys(m map[string]bool) string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return strings.Join(keys, ", ")
}
