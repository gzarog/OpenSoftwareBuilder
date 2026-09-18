package cli

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/filesystem"
	"github.com/gzarog/opensoftwarebuilder/internal/gates"
	"github.com/gzarog/opensoftwarebuilder/internal/knowledge"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var statusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show project state (gates, checkpoints, knowledge)",
	RunE:  runStatus,
}

func runStatus(cmd *cobra.Command, args []string) error {
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
	output.Header("Open Software Builder — Status")

	var sourceDirs []string
	for _, src := range paths.Source {
		fullPath := filepath.Join(root, src)
		if filesystem.DirExists(fullPath) {
			sourceDirs = append(sourceDirs, fullPath)
		}
	}
	latestMtime, _ := filesystem.LatestMtime(sourceDirs, paths.Generated)

	output.SubHeader("Gates")
	gm := gates.NewManager(root, paths.State)

	reviewGate, _ := gm.Inspect("review", latestMtime)
	if reviewGate != nil {
		output.Printf("  Review:    %s\n", formatGateState(reviewGate))
	}

	knowledgeMgr := knowledge.NewManager(root, paths.Knowledge)
	knowledgeMtime, _ := knowledgeMgr.LatestMtime()
	knowledgeGate, _ := gm.Inspect("knowledge", latestMtime)
	if knowledgeGate != nil {
		if knowledgeGate.State == gates.GateNeedsAction && knowledgeMtime >= latestMtime {
			output.Printf("  Knowledge: UP TO DATE\n")
		} else {
			output.Printf("  Knowledge: %s\n", formatGateState(knowledgeGate))
		}
	}

	cpDir := filepath.Join(root, paths.Checkpoints)
	checkpoints, _ := filesystem.ActiveCheckpoints(cpDir)
	if len(checkpoints) > 0 {
		output.SubHeader("Active Checkpoints")
		for _, cp := range checkpoints {
			info, _ := os.Stat(filepath.Join(cpDir, cp))
			if info != nil {
				output.Printf("  - %s (%s)\n", cp, formatAge(info.ModTime()))
			} else {
				output.Printf("  - %s\n", cp)
			}
		}
	}

	output.SubHeader("Knowledge")
	output.Println(fmt.Sprintf("  %s", knowledgeMgr.RecordStatus()))
	if knowledgeMgr.HasIndex() {
		rows, _ := knowledgeMgr.IndexRows(5)
		if len(rows) > 0 {
			output.Println("\n  Recent:")
			for _, row := range rows {
				output.Printf("    %s\n", row)
			}
		}
	}

	if len(cfg.Workspaces) > 0 {
		output.SubHeader("Workspaces")
		for name, ws := range cfg.Workspaces {
			exists := filesystem.DirExists(filepath.Join(root, ws.Path))
			status := "ok"
			if !exists {
				status = "path not found"
			}
			output.Printf("  %-15s %s @ %s (%s)\n", name, ws.Toolchain, ws.Path, status)
		}
	}

	output.Println("")
	return nil
}

func formatGateState(g *gates.Gate) string {
	switch g.State {
	case gates.GateApproved:
		return fmt.Sprintf("APPROVED (%s)", g.Timestamp.Format("2006-01-02 15:04"))
	case gates.GateSkipped:
		reason := g.SkipReason
		if reason == "" {
			reason = "no reason"
		}
		return fmt.Sprintf("SKIPPED (%s)", reason)
	default:
		return "NEEDS ACTION"
	}
}

func formatAge(t time.Time) string {
	d := time.Since(t)
	switch {
	case d < time.Minute:
		return "just now"
	case d < time.Hour:
		return fmt.Sprintf("%dm ago", int(d.Minutes()))
	case d < 24*time.Hour:
		return fmt.Sprintf("%dh ago", int(d.Hours()))
	default:
		return fmt.Sprintf("%dd ago", int(d.Hours()/24))
	}
}
