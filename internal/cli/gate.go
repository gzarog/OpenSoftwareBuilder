package cli

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/filesystem"
	"github.com/gzarog/opensoftwarebuilder/internal/gates"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var gateCmd = &cobra.Command{
	Use:   "gate <review|knowledge> <inspect|approve|skip> [reason]",
	Short: "Manage quality gates",
	Args:  cobra.MinimumNArgs(2),
	RunE:  runGate,
}

func runGate(cmd *cobra.Command, args []string) error {
	gateName := args[0]
	action := args[1]

	if gateName != "review" && gateName != "knowledge" {
		return fmt.Errorf("unknown gate: %s (expected: review, knowledge)", gateName)
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
