package gates

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

type GateState string

const (
	GateApproved    GateState = "APPROVED"
	GateNeedsAction GateState = "NEEDS_ACTION"
	GateSkipped     GateState = "SKIPPED"
)

type Gate struct {
	Name       string
	State      GateState
	Timestamp  time.Time
	SkipReason string
}

type Manager struct {
	stateDir string
}

func NewManager(root string, stateDir string) *Manager {
	dir := filepath.Join(root, stateDir)
	return &Manager{stateDir: dir}
}

func (m *Manager) Inspect(name string, latestSourceMtime float64) (*Gate, error) {
	gate := &Gate{Name: name}

	// Check skip marker
	skipFile := filepath.Join(m.stateDir, name+"-skip")
	if data, err := os.ReadFile(skipFile); err == nil {
		parts := strings.SplitN(strings.TrimSpace(string(data)), "\n", 2)
		ts, _ := strconv.ParseFloat(parts[0], 64)
		gate.Timestamp = time.Unix(int64(ts), 0)
		if len(parts) > 1 {
			gate.SkipReason = parts[1]
		}
		if ts >= latestSourceMtime {
			gate.State = GateSkipped
			return gate, nil
		}
	}

	// Check approval marker
	approveFile := filepath.Join(m.stateDir, name+"-approved")
	if data, err := os.ReadFile(approveFile); err == nil {
		ts, _ := strconv.ParseFloat(strings.TrimSpace(string(data)), 64)
		gate.Timestamp = time.Unix(int64(ts), 0)
		if ts >= latestSourceMtime {
			gate.State = GateApproved
			return gate, nil
		}
	}

	gate.State = GateNeedsAction
	return gate, nil
}

func (m *Manager) Approve(name string) error {
	if err := os.MkdirAll(m.stateDir, 0755); err != nil {
		return err
	}
	ts := fmt.Sprintf("%.6f", float64(time.Now().Unix()))
	path := filepath.Join(m.stateDir, name+"-approved")
	return os.WriteFile(path, []byte(ts), 0644)
}

func (m *Manager) Skip(name string, reason string) error {
	if err := os.MkdirAll(m.stateDir, 0755); err != nil {
		return err
	}
	ts := fmt.Sprintf("%.6f", float64(time.Now().Unix()))
	content := ts + "\n" + reason
	path := filepath.Join(m.stateDir, name+"-skip")
	return os.WriteFile(path, []byte(content), 0644)
}
