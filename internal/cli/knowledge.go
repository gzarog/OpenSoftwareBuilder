package cli

import (
	"fmt"
	"os"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
	knowledgePkg "github.com/gzarog/opensoftwarebuilder/internal/knowledge"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var knowledgeCmd = &cobra.Command{
	Use:   "knowledge <record|status>",
	Short: "Knowledge recording helper",
	Args:  cobra.MinimumNArgs(1),
	RunE:  runKnowledge,
}

func runKnowledge(cmd *cobra.Command, args []string) error {
	action := args[0]

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
	mgr := knowledgePkg.NewManager(root, paths.Knowledge)

	switch action {
	case "record":
		if err := mgr.EnsureDirs(); err != nil {
			return err
		}
		output.Header("Knowledge Recording")
		output.Println(fmt.Sprintf("\n  Directory: %s", mgr.Dir()))
		output.Println(fmt.Sprintf("  %s", mgr.RecordStatus()))

		if len(args) > 1 {
			path, err := mgr.CreateTaskRecord(args[1])
			if err != nil {
				return err
			}
			output.Success(fmt.Sprintf("Created task record: %s", path))

			// In full mode: trigger RagMonk incremental index so the new
			// record is immediately retrievable.
			if cfg.IsFullMode() {
				provider := intelligence.NewRagMonkProvider(cfg.GetIntelligence())
				if provider.IsAvailable() {
					output.Println("  Indexing new knowledge record...")
					if err := provider.Index(root); err != nil {
						output.Warning(fmt.Sprintf("Index update failed: %s", err))
						output.Println("  Run manually: ragmonk index")
					} else {
						output.Success("Knowledge index updated")
					}
				}
			}
		} else {
			output.Println("\n  To record knowledge:")
			output.Println("    osb knowledge record <task-name>   — create a task record")
			output.Println("    Edit knowledge/tasks/<file>.md     — fill in decisions, gotchas, follow-ups")
			output.Println("    Edit knowledge/components/<file>.md — update component rollup")
			if cfg.IsFullMode() {
				output.Println("\n  In full mode RagMonk indexes new records automatically.")
				output.Println("  Run 'osb intelligence status' to verify index health.")
			}
		}

	case "status":
		output.Header("Knowledge Status")
		output.Println(fmt.Sprintf("\n  %s", mgr.RecordStatus()))

		if cfg.IsFullMode() {
			// Full mode: show RagMonk intelligence status rather than INDEX.md rows.
			provider := intelligence.NewRagMonkProvider(cfg.GetIntelligence())
			if !provider.IsAvailable() {
				output.Error("Full mode requires RagMonk — not installed")
				output.Println("  Install: irm https://raw.githubusercontent.com/gzarog/RagMonk/main/install.ps1 | iex")
				output.Println("")
				return nil
			}
			status, err := provider.GetStatus()
			if err != nil {
				output.Warning(fmt.Sprintf("RagMonk status error: %s", err))
			} else {
				output.Println("\n  Intelligence:")
				if status.Version != "" {
					output.Info(fmt.Sprintf("  Provider:  RagMonk %s", status.Version))
				} else {
					output.Info("  Provider:  RagMonk")
				}
				if status.IndexAvailable {
					output.Success("  Index:     available")
				} else {
					output.Warning("  Index:     missing — run: ragmonk index")
				}
				if status.DaemonRunning {
					output.Success("  Daemon:    running")
				} else {
					output.Info("  Daemon:    not running")
				}
			}
		} else {
			// Light mode: show INDEX.md rows if available (legacy behaviour).
			if mgr.HasIndex() {
				rows, _ := mgr.IndexRows(10)
				if len(rows) > 0 {
					output.Println("\n  Recent entries:")
					for _, row := range rows {
						output.Printf("    %s\n", row)
					}
				}
			}
		}

	default:
		return fmt.Errorf("unknown action: %s (expected: record, status)", action)
	}

	output.Println("")
	return nil
}
