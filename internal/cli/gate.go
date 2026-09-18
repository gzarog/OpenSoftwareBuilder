package cli

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/filesystem"
	"github.com/gzarog/opensoftwarebuilder/internal/gates"
	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var gateCmd = &cobra.Command{
	Use:   "gate <review|knowledge|intelligence> <inspect|approve|skip> [reason]",
	Short: "Manage quality gates",
	Args:  cobra.MinimumNArgs(2),
	RunE:  runGate,
}

func runGate(cmd *cobra.Command, args []string) error {
	gateName := args[0]
	action := args[1]

	// Phase 15: intelligence gate is provider-based, not mtime-based.
	if gateName == "intelligence" {
		return runIntelligenceGate(action)
	}

	if gateName != "review" && gateName != "knowledge" {
		return fmt.Errorf("unknown gate: %s (expected: review, knowledge, intelligence)", gateName)
	}

	cwd, _ := os.Getwd()
	root, err := config.FindRoot(cwd)
	if err != nil {
		return err
	}
	cfg, err := config.Load(root)
	if err != nil {
		return err
	}

	paths := cfg.GetPaths()
	gm := gates.NewManager(root, paths.State)

	var sourceDirs []string
	for _, src := range paths.Source {
		fullPath := filepath.Join(root, src)
		if filesystem.DirExists(fullPath) {
			sourceDirs = append(sourceDirs, fullPath)
		}
	}
	latestMtime, _ := filesystem.LatestMtime(sourceDirs, paths.Generated)

	switch action {
	case "inspect":
		gate, err := gm.Inspect(gateName, latestMtime)
		if err != nil {
			return err
		}
		output.Header(fmt.Sprintf("Gate: %s", gateName))
		output.Printf("  State: %s\n", formatGateState(gate))
		if gate.SkipReason != "" {
			output.Printf("  Reason: %s\n", gate.SkipReason)
		}
	case "approve":
		if gateName == "knowledge" {
			return fmt.Errorf("knowledge gate cannot be directly approved — it is derived from knowledge mtime")
		}
		if err := gm.Approve(gateName); err != nil {
			return err
		}
		output.Success(fmt.Sprintf("%s gate approved", gateName))
	case "skip":
		reason := "no reason provided"
		if len(args) > 2 {
			reason = strings.Join(args[2:], " ")
		}
		if err := gm.Skip(gateName, reason); err != nil {
			return err
		}
		output.Success(fmt.Sprintf("%s gate skipped: %s", gateName, reason))
	default:
		return fmt.Errorf("unknown action: %s (expected: inspect, approve, skip)", action)
	}

	output.Println("")
	return nil
}

// runIntelligenceGate handles the intelligence gate: it queries the provider
// directly rather than using mtime-based state files.
func runIntelligenceGate(action string) error {
	if action != "inspect" {
		return fmt.Errorf("intelligence gate only supports 'inspect' — health is derived from RagMonk state, not manually approved")
	}

	cwd, _ := os.Getwd()
	root, err := config.FindRoot(cwd)
	if err != nil {
		return fmt.Errorf("osb.yaml not found — run osb init")
	}
	cfg, err := config.Load(root)
	if err != nil {
		return err
	}
	if !cfg.IsFullMode() {
		output.Info("Intelligence gate: N/A (light mode)")
		output.Println("")
		return nil
	}

	output.Header("Gate: intelligence")
	provider := intelligence.NewProvider(cfg.GetIntelligence())

	healthy := true

	if !provider.IsAvailable() {
		output.Error("  RagMonk:  NOT FOUND")
		output.Println("  Remedy:   install ragmonk and run: ragmonk init && ragmonk source add . && ragmonk index")
		healthy = false
	} else {
		output.Success("  RagMonk:  available")

		registered, _ := provider.IsSourceRegistered(root)
		if registered {
			output.Success("  Source:   registered")
		} else {
			output.Error("  Source:   NOT REGISTERED — run: ragmonk source add .")
			healthy = false
		}

		status, err := provider.GetStatus()
		if err != nil {
			output.Error(fmt.Sprintf("  Status:   error — %s", err))
			healthy = false
		} else {
			if status.IndexAvailable {
				output.Success("  Index:    available")
			} else {
				output.Error("  Index:    MISSING — run: osb intelligence index")
				healthy = false
			}
			if status.DaemonRunning {
				output.Success("  Daemon:   running")
			} else {
				output.Info("  Daemon:   not running (ragmonk daemon start)")
			}
		}
	}

	output.Println("")
	if healthy {
		output.Success("Intelligence gate: PASS")
	} else {
		output.Error("Intelligence gate: FAIL — resolve issues above before running full-mode workflows")
	}
	output.Println("")
	return nil
}
