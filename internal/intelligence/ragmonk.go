package intelligence

import (
	"bytes"
	"fmt"
	"os/exec"
	"strings"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
)

// RagMonkProvider implements Provider using the ragmonk CLI.
type RagMonkProvider struct {
	cfg *config.RagMonkConfig
}

// NewRagMonkProvider creates a RagMonk-backed intelligence provider.
func NewRagMonkProvider(intel *config.IntelligenceConfig) *RagMonkProvider {
	cfg := intel.RagMonk
	if cfg == nil {
		cfg = config.DefaultRagMonkConfig()
	}
	return &RagMonkProvider{cfg: cfg}
}

func (r *RagMonkProvider) exe() string {
	if r.cfg.Executable != "" {
		return r.cfg.Executable
	}
	return "ragmonk"
}

func (r *RagMonkProvider) run(args ...string) (string, error) {
	cmd := exec.Command(r.exe(), args...)
	var out, errBuf bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &errBuf
	if err := cmd.Run(); err != nil {
		msg := strings.TrimSpace(errBuf.String())
		if msg == "" {
			msg = err.Error()
		}
		return "", fmt.Errorf("%s", msg)
	}
	return strings.TrimSpace(out.String()), nil
}

// IsAvailable returns true if the ragmonk executable can be found on PATH.
func (r *RagMonkProvider) IsAvailable() bool {
	_, err := exec.LookPath(r.exe())
	return err == nil
}

// GetStatus queries ragmonk for a health snapshot.
func (r *RagMonkProvider) GetStatus() (*Status, error) {
	if !r.IsAvailable() {
		return &Status{Available: false}, nil
	}

	s := &Status{Available: true}

	ver, err := r.run("version", "--short")
	if err == nil {
		s.Version = ver
		s.Healthy = true
	}

	registered, _ := r.IsSourceRegistered("")
	s.SourceRegistered = registered

	indexed, _ := r.IsIndexed()
	s.IndexAvailable = indexed
	s.IndexHealthy = indexed

	// check daemon: ragmonk daemon status exits 0 when running
	_, daemonErr := r.run("daemon", "status")
	s.DaemonRunning = daemonErr == nil

	return s, nil
}

// IsSourceRegistered checks whether the project is registered with RagMonk.
func (r *RagMonkProvider) IsSourceRegistered(root string) (bool, error) {
	if !r.IsAvailable() {
		return false, &FullModeError{
			Code:    ErrRagMonkMissing,
			Message: "RagMonk executable not found",
			Remedy:  installInstructions(),
		}
	}
	out, err := r.run("source", "list")
	if err != nil {
		return false, err
	}
	name := r.cfg.Source
	if name == "" {
		name = "project"
	}
	// heuristic: any non-empty listing means at least one source is registered
	return strings.TrimSpace(out) != "" || strings.Contains(out, name), nil
}

// RegisterSource runs ragmonk source add <root>.
func (r *RagMonkProvider) RegisterSource(root string) error {
	if !r.IsAvailable() {
		return &FullModeError{
			Code:    ErrRagMonkMissing,
			Message: "RagMonk executable not found",
			Remedy:  installInstructions(),
		}
	}
	_, err := r.run("source", "add", root)
	return err
}

// IsIndexed returns true if ragmonk reports an available index.
func (r *RagMonkProvider) IsIndexed() (bool, error) {
	if !r.IsAvailable() {
		return false, nil
	}
	_, err := r.run("index", "status")
	return err == nil, nil
}

// Index triggers an incremental (or full) ragmonk index.
func (r *RagMonkProvider) Index(root string) error {
	if !r.IsAvailable() {
		return &FullModeError{
			Code:    ErrRagMonkMissing,
			Message: "RagMonk executable not found",
			Remedy:  installInstructions(),
		}
	}
	_, err := r.run("index")
	if err != nil {
		return &FullModeError{
			Code:    ErrIndexFailed,
			Message: fmt.Sprintf("RagMonk indexing failed: %s", err),
			Remedy:  "ragmonk source add .\nragmonk index",
		}
	}
	return nil
}

// Explore runs a free-text knowledge retrieval query via ragmonk explore.
func (r *RagMonkProvider) Explore(query string, opts ExploreOptions) (*ExploreResult, error) {
	if !r.IsAvailable() {
		return nil, &FullModeError{
			Code:    ErrRagMonkMissing,
			Message: "RagMonk executable not found",
			Remedy:  installInstructions(),
		}
	}

	cmd := r.cfg.Retrieval.Command
	if cmd == "" {
		cmd = "explore"
	}
	maxR := opts.MaxResults
	if maxR == 0 {
		maxR = r.cfg.Retrieval.MaxResults
	}
	if maxR == 0 {
		maxR = 20
	}

	args := []string{cmd, query, fmt.Sprintf("--max-results=%d", maxR)}
	if opts.IncludeCode {
		args = append(args, "--include=code")
	}
	if opts.IncludeTests {
		args = append(args, "--include=tests")
	}
	if opts.IncludeDocs {
		args = append(args, "--include=docs")
	}
	if opts.IncludeOSBKnowledge {
		args = append(args, "--include=osb-knowledge")
	}

	out, err := r.run(args...)
	if err != nil {
		return nil, fmt.Errorf("ragmonk %s: %w", cmd, err)
	}
	// Raw text result; structured parsing is left to higher-level consumers.
	return &ExploreResult{
		Items: []EvidenceItem{{Content: out, Kind: "raw"}},
	}, nil
}

func installInstructions() string {
	return "Install RagMonk:\n  irm https://raw.githubusercontent.com/gzarog/RagMonk/main/install.ps1 | iex\n\nThen run:\n  ragmonk init\n  ragmonk source add .\n  ragmonk index\n  osb doctor"
}
