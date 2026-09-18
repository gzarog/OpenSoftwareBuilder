package unit

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/gzarog/opensoftwarebuilder/internal/gates"
)

func TestGateApprove(t *testing.T) {
	dir := t.TempDir()
	stateDir := ".osb/state"
	os.MkdirAll(filepath.Join(dir, stateDir), 0755)

	gm := gates.NewManager(dir, stateDir)

	if err := gm.Approve("review"); err != nil {
		t.Fatalf("approve failed: %v", err)
	}

	// Latest source mtime is older than approval
	gate, err := gm.Inspect("review", float64(time.Now().Unix()-100))
	if err != nil {
		t.Fatalf("inspect failed: %v", err)
	}
	if gate.State != gates.GateApproved {
		t.Errorf("expected APPROVED, got %s", gate.State)
	}
}

func TestGateInvalidatedByNewChange(t *testing.T) {
	dir := t.TempDir()
	stateDir := ".osb/state"
	os.MkdirAll(filepath.Join(dir, stateDir), 0755)

	gm := gates.NewManager(dir, stateDir)
	gm.Approve("review")

	// Source mtime is newer than approval
	gate, _ := gm.Inspect("review", float64(time.Now().Unix()+100))
	if gate.State != gates.GateNeedsAction {
		t.Errorf("expected NEEDS_ACTION after new change, got %s", gate.State)
	}
}

func TestGateSkip(t *testing.T) {
	dir := t.TempDir()
	stateDir := ".osb/state"
	os.MkdirAll(filepath.Join(dir, stateDir), 0755)

	gm := gates.NewManager(dir, stateDir)
	gm.Skip("review", "tier-1 trivial change")

	gate, _ := gm.Inspect("review", float64(time.Now().Unix()-100))
	if gate.State != gates.GateSkipped {
		t.Errorf("expected SKIPPED, got %s", gate.State)
	}
	if gate.SkipReason != "tier-1 trivial change" {
		t.Errorf("expected skip reason, got '%s'", gate.SkipReason)
	}
}

func TestGateNeedsAction(t *testing.T) {
	dir := t.TempDir()
	stateDir := ".osb/state"

	gm := gates.NewManager(dir, stateDir)
	gate, _ := gm.Inspect("review", float64(time.Now().Unix()))
	if gate.State != gates.GateNeedsAction {
		t.Errorf("expected NEEDS_ACTION for fresh gate, got %s", gate.State)
	}
}
