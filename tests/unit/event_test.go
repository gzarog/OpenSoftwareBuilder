package unit

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/gzarog/opensoftwarebuilder/internal/event"
)

// ─── event validation ────────────────────────────────────────────────────────

func TestEventValidate_Valid(t *testing.T) {
	e := &event.KnowledgeEvent{
		TaskID:  "OSB-1",
		Role:    "architect",
		Type:    "decision",
		Summary: "Use event-driven invalidation instead of polling",
	}
	if err := e.Validate(); err != nil {
		t.Errorf("expected valid event, got error: %v", err)
	}
}

func TestEventValidate_MissingTaskID(t *testing.T) {
	e := &event.KnowledgeEvent{
		Role:    "architect",
		Type:    "decision",
		Summary: "something",
	}
	if err := e.Validate(); err == nil {
		t.Error("expected error for missing task_id")
	}
}

func TestEventValidate_MissingRole(t *testing.T) {
	e := &event.KnowledgeEvent{
		TaskID:  "OSB-1",
		Type:    "decision",
		Summary: "something",
	}
	if err := e.Validate(); err == nil {
		t.Error("expected error for missing role")
	}
}

func TestEventValidate_InvalidRole(t *testing.T) {
	e := &event.KnowledgeEvent{
		TaskID:  "OSB-1",
		Role:    "lead",
		Type:    "decision",
		Summary: "something",
	}
	if err := e.Validate(); err == nil {
		t.Error("expected error for invalid role")
	}
}

func TestEventValidate_InvalidType(t *testing.T) {
	e := &event.KnowledgeEvent{
		TaskID:  "OSB-1",
		Role:    "implementer",
		Type:    "observation", // not in vocab
		Summary: "something",
	}
	if err := e.Validate(); err == nil {
		t.Error("expected error for invalid event type")
	}
}

func TestEventValidate_BlankSummary(t *testing.T) {
	e := &event.KnowledgeEvent{
		TaskID:  "OSB-1",
		Role:    "implementer",
		Type:    "discovery",
		Summary: "   ",
	}
	if err := e.Validate(); err == nil {
		t.Error("expected error for blank summary")
	}
}

func TestEventValidate_InvalidScope(t *testing.T) {
	e := &event.KnowledgeEvent{
		TaskID:  "OSB-1",
		Role:    "implementer",
		Type:    "discovery",
		Summary: "something",
		Scope:   "module", // not in vocab
	}
	if err := e.Validate(); err == nil {
		t.Error("expected error for invalid scope")
	}
}

func TestEventValidate_NoneMarker(t *testing.T) {
	e := &event.KnowledgeEvent{
		TaskID:     "OSB-1",
		Role:       "reviewer",
		None:       true,
		NoneReason: "no reusable findings in this trivial change",
	}
	if err := e.Validate(); err != nil {
		t.Errorf("expected valid none event, got: %v", err)
	}
}

func TestEventValidate_AllTypes(t *testing.T) {
	types := []string{
		"decision", "constraint", "discovery", "gotcha",
		"assumption", "assumption-invalidated", "review-finding", "qa-result", "follow-up",
	}
	for _, typ := range types {
		e := &event.KnowledgeEvent{
			TaskID:  "OSB-1",
			Role:    "implementer",
			Type:    typ,
			Summary: "test summary for " + typ,
		}
		if err := e.Validate(); err != nil {
			t.Errorf("type %q should be valid, got: %v", typ, err)
		}
	}
}

// ─── event ID generation ─────────────────────────────────────────────────────

func TestGenerateID_Deterministic(t *testing.T) {
	id1 := event.GenerateID("architect", "decision", "Use JWT")
	id2 := event.GenerateID("architect", "decision", "Use JWT")
	if id1 != id2 {
		t.Errorf("expected deterministic IDs, got %q and %q", id1, id2)
	}
}

func TestGenerateID_DifferentInputs(t *testing.T) {
	id1 := event.GenerateID("architect", "decision", "Use JWT")
	id2 := event.GenerateID("implementer", "discovery", "Use JWT")
	if id1 == id2 {
		t.Error("expected different IDs for different role/type")
	}
}

func TestGenerateID_HasPrefix(t *testing.T) {
	id := event.GenerateID("qa", "qa-result", "All tests pass")
	if !strings.HasPrefix(id, "event-") {
		t.Errorf("expected id to start with 'event-', got %q", id)
	}
}

// ─── content hash (dedup) ────────────────────────────────────────────────────

func TestContentHash_SameSummaryDifferentRole(t *testing.T) {
	e1 := &event.KnowledgeEvent{Role: "architect", Type: "decision", Summary: "Use JWT"}
	e2 := &event.KnowledgeEvent{Role: "implementer", Type: "decision", Summary: "Use JWT"}
	if e1.ContentHash() == e2.ContentHash() {
		t.Error("expected different hashes for different roles")
	}
}

func TestContentHash_TrimsSummaryWhitespace(t *testing.T) {
	e1 := &event.KnowledgeEvent{Role: "architect", Type: "decision", Summary: "Use JWT"}
	e2 := &event.KnowledgeEvent{Role: "architect", Type: "decision", Summary: "  Use JWT  "}
	if e1.ContentHash() != e2.ContentHash() {
		t.Error("expected same hash when summary differs only by surrounding whitespace")
	}
}

// ─── store: basic append + read ──────────────────────────────────────────────

func newTestStore(t *testing.T) (*event.Store, string) {
	t.Helper()
	root := t.TempDir()
	store := event.NewStore(root, ".osb/progress", "OSB-TEST")
	return store, root
}

func TestStoreAppend_AssignsIDAndTimestamp(t *testing.T) {
	store, root := newTestStore(t)
	_ = root

	e := &event.KnowledgeEvent{
		TaskID:  "OSB-TEST",
		Role:    "architect",
		Type:    "decision",
		Summary: "Use event-driven invalidation",
	}
	if err := store.Append(e); err != nil {
		t.Fatalf("append failed: %v", err)
	}
	if e.ID == "" {
		t.Error("expected ID to be assigned")
	}
	if e.Timestamp.IsZero() {
		t.Error("expected Timestamp to be assigned")
	}
}

func TestStoreAppend_CreatesJSONLFile(t *testing.T) {
	store, root := newTestStore(t)
	e := &event.KnowledgeEvent{
		TaskID:  "OSB-TEST",
		Role:    "implementer",
		Type:    "gotcha",
		Summary: "JWT must be validated before tenant resolution",
	}
	if err := store.Append(e); err != nil {
		t.Fatalf("append failed: %v", err)
	}

	path := filepath.Join(root, ".osb/progress", "OSB-TEST", "knowledge", "implementer.jsonl")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("reading JSONL file: %v", err)
	}
	if !strings.Contains(string(data), "JWT must be validated") {
		t.Error("expected summary in JSONL file")
	}
}

func TestStoreReadRole_ReturnsEvents(t *testing.T) {
	store, _ := newTestStore(t)

	for i := 0; i < 3; i++ {
		store.Append(&event.KnowledgeEvent{
			TaskID:  "OSB-TEST",
			Role:    "reviewer",
			Type:    "review-finding",
			Summary: fmt.Sprintf("finding %d", i),
		})
	}

	events, err := store.ReadRole("reviewer")
	if err != nil {
		t.Fatalf("ReadRole failed: %v", err)
	}
	if len(events) != 3 {
		t.Errorf("expected 3 events, got %d", len(events))
	}
}

func TestStoreReadRole_EmptyWhenNoFile(t *testing.T) {
	store, _ := newTestStore(t)
	events, err := store.ReadRole("qa")
	if err != nil {
		t.Fatalf("ReadRole failed: %v", err)
	}
	if events != nil {
		t.Errorf("expected nil for missing file, got %v", events)
	}
}

// ─── deduplication ───────────────────────────────────────────────────────────

func TestStoreAppend_RejectsDuplicate(t *testing.T) {
	store, _ := newTestStore(t)

	e := &event.KnowledgeEvent{
		TaskID:  "OSB-TEST",
		Role:    "architect",
		Type:    "decision",
		Summary: "Use event-driven invalidation",
	}
	if err := store.Append(e); err != nil {
		t.Fatalf("first append failed: %v", err)
	}

	e2 := &event.KnowledgeEvent{
		TaskID:  "OSB-TEST",
		Role:    "architect",
		Type:    "decision",
		Summary: "Use event-driven invalidation", // same content
	}
	if err := store.Append(e2); err == nil {
		t.Error("expected error for duplicate event")
	}
}

func TestStoreAppend_AllowsDifferentType(t *testing.T) {
	store, _ := newTestStore(t)

	store.Append(&event.KnowledgeEvent{
		TaskID:  "OSB-TEST",
		Role:    "architect",
		Type:    "decision",
		Summary: "Use JWT",
	})

	// Same summary but different type — not a duplicate.
	if err := store.Append(&event.KnowledgeEvent{
		TaskID:  "OSB-TEST",
		Role:    "architect",
		Type:    "constraint",
		Summary: "Use JWT",
	}); err != nil {
		t.Errorf("expected success for different type, got: %v", err)
	}
}

// ─── none marker ─────────────────────────────────────────────────────────────

func TestStoreAppend_NoneMarker(t *testing.T) {
	store, _ := newTestStore(t)

	e := &event.KnowledgeEvent{
		TaskID:     "OSB-TEST",
		Role:       "reviewer",
		None:       true,
		NoneReason: "no architectural risks found",
	}
	if err := store.Append(e); err != nil {
		t.Fatalf("none append failed: %v", err)
	}
	if !strings.HasPrefix(e.ID, "none-") {
		t.Errorf("expected ID to start with 'none-', got %q", e.ID)
	}
}

// ─── store summary ───────────────────────────────────────────────────────────

func TestStoreSummary_CountsAndNone(t *testing.T) {
	store, _ := newTestStore(t)

	store.Append(&event.KnowledgeEvent{TaskID: "OSB-TEST", Role: "architect", Type: "decision", Summary: "d1"})
	store.Append(&event.KnowledgeEvent{TaskID: "OSB-TEST", Role: "architect", Type: "constraint", Summary: "c1"})
	store.Append(&event.KnowledgeEvent{TaskID: "OSB-TEST", Role: "implementer", Type: "gotcha", Summary: "g1"})
	store.Append(&event.KnowledgeEvent{TaskID: "OSB-TEST", Role: "reviewer", None: true, NoneReason: "ok"})

	summary := store.Summary()

	archSum := summary["architect"]
	if archSum.Count != 2 {
		t.Errorf("expected 2 architect events, got %d", archSum.Count)
	}
	if archSum.ByType["decision"] != 1 {
		t.Error("expected 1 architect decision")
	}

	implSum := summary["implementer"]
	if implSum.Count != 1 {
		t.Errorf("expected 1 implementer event, got %d", implSum.Count)
	}

	revSum := summary["reviewer"]
	if !revSum.HasNone {
		t.Error("expected reviewer to have none marker")
	}
	if revSum.NoneReason != "ok" {
		t.Errorf("expected none reason 'ok', got %q", revSum.NoneReason)
	}

	qaSum := summary["qa"]
	if qaSum.Count != 0 || qaSum.HasNone {
		t.Error("expected empty qa summary")
	}
}

func TestRoleSummary_HasCheckpoint(t *testing.T) {
	withEvents := event.RoleSummary{Count: 3}
	withNone := event.RoleSummary{HasNone: true}
	empty := event.RoleSummary{}

	if !withEvents.HasCheckpoint() {
		t.Error("expected HasCheckpoint true for role with events")
	}
	if !withNone.HasCheckpoint() {
		t.Error("expected HasCheckpoint true for role with none marker")
	}
	if empty.HasCheckpoint() {
		t.Error("expected HasCheckpoint false for empty role")
	}
}

// ─── store.ReadAll ───────────────────────────────────────────────────────────

func TestStoreReadAll_AllRoles(t *testing.T) {
	store, _ := newTestStore(t)

	store.Append(&event.KnowledgeEvent{TaskID: "OSB-TEST", Role: "architect", Type: "decision", Summary: "a1"})
	store.Append(&event.KnowledgeEvent{TaskID: "OSB-TEST", Role: "implementer", Type: "discovery", Summary: "i1"})
	store.Append(&event.KnowledgeEvent{TaskID: "OSB-TEST", Role: "qa", Type: "qa-result", Summary: "q1"})

	all, err := store.ReadAll()
	if err != nil {
		t.Fatalf("ReadAll failed: %v", err)
	}
	if len(all) != 3 {
		t.Errorf("expected 3 events across all roles, got %d", len(all))
	}
}

// ─── store.AppendFromJSON ────────────────────────────────────────────────────

func TestStoreAppendFromJSON(t *testing.T) {
	store, root := newTestStore(t)

	ev := event.KnowledgeEvent{
		TaskID:  "OSB-TEST",
		Role:    "implementer",
		Type:    "constraint",
		Summary: "Lock timeout must stay below provider timeout",
		Scope:   "component",
	}
	data, _ := json.Marshal(ev)
	jsonFile := filepath.Join(root, "event.json")
	os.WriteFile(jsonFile, data, 0644)

	got, err := store.AppendFromJSON(jsonFile)
	if err != nil {
		t.Fatalf("AppendFromJSON failed: %v", err)
	}
	if got.Summary != ev.Summary {
		t.Errorf("expected summary %q, got %q", ev.Summary, got.Summary)
	}
}

// ─── store.ListTaskIDs ───────────────────────────────────────────────────────

func TestListTaskIDs(t *testing.T) {
	root := t.TempDir()

	for _, id := range []string{"OSB-1", "OSB-2"} {
		dir := filepath.Join(root, ".osb/progress", id, "knowledge")
		os.MkdirAll(dir, 0755)
		os.WriteFile(filepath.Join(dir, "architect.jsonl"), []byte{}, 0644)
	}

	ids, err := event.ListTaskIDs(root, ".osb/progress")
	if err != nil {
		t.Fatalf("ListTaskIDs failed: %v", err)
	}
	if len(ids) != 2 {
		t.Errorf("expected 2 task IDs, got %d", len(ids))
	}
}

func TestListTaskIDs_EmptyWhenNone(t *testing.T) {
	root := t.TempDir()
	os.MkdirAll(filepath.Join(root, ".osb/progress"), 0755)

	ids, err := event.ListTaskIDs(root, ".osb/progress")
	if err != nil {
		t.Fatalf("ListTaskIDs failed: %v", err)
	}
	if len(ids) != 0 {
		t.Errorf("expected 0 task IDs, got %d", len(ids))
	}
}

// ─── store.Exists ────────────────────────────────────────────────────────────

func TestStoreExists_FalseWhenEmpty(t *testing.T) {
	store, _ := newTestStore(t)
	if store.Exists() {
		t.Error("expected Exists=false before any events are captured")
	}
}

func TestStoreExists_TrueAfterCapture(t *testing.T) {
	store, _ := newTestStore(t)
	store.Append(&event.KnowledgeEvent{
		TaskID:  "OSB-TEST",
		Role:    "architect",
		Type:    "decision",
		Summary: "First decision",
	})
	if !store.Exists() {
		t.Error("expected Exists=true after capturing an event")
	}
}

// ─── marshal / unmarshal ─────────────────────────────────────────────────────

func TestEventMarshalUnmarshal(t *testing.T) {
	original := &event.KnowledgeEvent{
		ID:         "event-abc123",
		Timestamp:  time.Now().UTC().Truncate(time.Second),
		TaskID:     "OSB-42",
		Role:       "reviewer",
		Type:       "review-finding",
		Scope:      "global",
		Summary:    "All timestamps must use UTC",
		Confidence: "confirmed",
	}

	data, err := original.Marshal()
	if err != nil {
		t.Fatalf("Marshal failed: %v", err)
	}

	recovered, err := event.Unmarshal(data)
	if err != nil {
		t.Fatalf("Unmarshal failed: %v", err)
	}

	if recovered.ID != original.ID {
		t.Errorf("ID mismatch: %q vs %q", recovered.ID, original.ID)
	}
	if recovered.Summary != original.Summary {
		t.Errorf("Summary mismatch")
	}
	if recovered.Scope != original.Scope {
		t.Errorf("Scope mismatch")
	}
}

