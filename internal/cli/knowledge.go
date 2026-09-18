package cli

import (
	"fmt"
	"os"
	"strings"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
	knowledgePkg "github.com/gzarog/opensoftwarebuilder/internal/knowledge"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var knowledgeCmd = &cobra.Command{
	Use:   "knowledge",
	Short: "Knowledge recording and status",
}

var knowledgeStatusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show knowledge directory status and intelligence health",
	RunE:  runKnowledgeStatus,
}

var knowledgeRecordCmd = &cobra.Command{
	Use:   "record <task|component> <name>",
	Short: "Create a durable knowledge record",
	Args:  cobra.ExactArgs(2),
	RunE:  runKnowledgeRecord,
}

var knowledgeComponents []string
var knowledgeStatus string
var knowledgeTier int
var knowledgeSummary string
var knowledgeDecisions string
var knowledgeTaskID string
var knowledgeLanguage string
var knowledgePurpose string

func init() {
	knowledgeRecordCmd.Flags().StringSliceVar(&knowledgeComponents, "component", nil,
		"Components touched (for task records; can be repeated)")
	knowledgeRecordCmd.Flags().StringVar(&knowledgeStatus, "status", "",
		"Status: in-progress|shipped|abandoned (task) or active|deprecated (component)")
	knowledgeRecordCmd.Flags().IntVar(&knowledgeTier, "tier", 0, "Effort tier 1-5")
	knowledgeRecordCmd.Flags().StringVar(&knowledgeSummary, "summary", "", "One-line summary of what was done")
	knowledgeRecordCmd.Flags().StringVar(&knowledgeDecisions, "decisions", "", "Key decisions (inline)")
	knowledgeRecordCmd.Flags().StringVar(&knowledgeTaskID, "task-id", "", "Task that prompted this component record")
	knowledgeRecordCmd.Flags().StringVar(&knowledgeLanguage, "language", "", "Primary language of this component")
	knowledgeRecordCmd.Flags().StringVar(&knowledgePurpose, "purpose", "", "Brief purpose statement for component records")

	knowledgeCmd.AddCommand(knowledgeStatusCmd)
	knowledgeCmd.AddCommand(knowledgeRecordCmd)
}

func loadKnowledgeManager() (*knowledgePkg.Manager, *config.Config, string, error) {
	cwd, _ := os.Getwd()
	root, err := config.FindRoot(cwd)
	if err != nil {
		return nil, nil, "", err
	}
	cfg, err := config.Load(root)
	if err != nil {
		return nil, nil, "", err
	}
	paths := cfg.GetPaths()
	return knowledgePkg.NewManager(root, paths.Knowledge), cfg, root, nil
}

func runKnowledgeStatus(cmd *cobra.Command, args []string) error {
	mgr, cfg, _, err := loadKnowledgeManager()
	if err != nil {
		return err
	}

	output.Header("Knowledge Status")
	output.Println(fmt.Sprintf("\n  %s", mgr.RecordStatus()))

	if cfg.IsFullMode() {
		provider := intelligence.NewProvider(cfg.GetIntelligence())
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

	output.Println("")
	return nil
}

func runKnowledgeRecord(cmd *cobra.Command, args []string) error {
	kind := strings.ToLower(args[0])
	name := args[1]

	mgr, cfg, root, err := loadKnowledgeManager()
	if err != nil {
		return err
	}

	if err := mgr.EnsureDirs(); err != nil {
		return err
	}

	output.Header("Knowledge Recording")

	var path string
	switch kind {
	case "task":
		opts := knowledgePkg.TaskRecordOptions{
			Components: knowledgeComponents,
			Status:     knowledgeStatus,
			Tier:       knowledgeTier,
			Summary:    knowledgeSummary,
			Decisions:  knowledgeDecisions,
		}
		path, err = mgr.CreateTaskRecord(name, opts)
		if err != nil {
			return fmt.Errorf("creating task record: %w", err)
		}
		output.Success(fmt.Sprintf("Task record: %s", path))
		if len(knowledgeComponents) > 0 {
			output.Info(fmt.Sprintf("Components: %s", strings.Join(knowledgeComponents, ", ")))
		}

	case "component":
		opts := knowledgePkg.ComponentRecordOptions{
			TaskID:   knowledgeTaskID,
			Status:   knowledgeStatus,
			Tier:     knowledgeTier,
			Language: knowledgeLanguage,
			Purpose:  knowledgePurpose,
		}
		path, err = mgr.CreateComponentRecord(name, opts)
		if err != nil {
			return fmt.Errorf("creating component record: %w", err)
		}
		output.Success(fmt.Sprintf("Component record: %s", path))

	default:
		return fmt.Errorf("unknown record type %q — must be: task or component", kind)
	}

	// Phase 14: in full mode, trigger incremental index so the new record is
	// immediately retrievable by RagMonk.
	if cfg.IsFullMode() {
		provider := intelligence.NewProvider(cfg.GetIntelligence())
		if provider.IsAvailable() {
			output.Println("Indexing new record with RagMonk...")
			if idxErr := provider.Index(root); idxErr != nil {
				output.Warning(fmt.Sprintf("Index update failed: %s", idxErr))
				output.Println("  Run manually: ragmonk index")
			} else {
				output.Success("Knowledge index updated")
			}
		} else {
			output.Error("RagMonk not available — record created but not indexed")
			output.Error("Full mode requires RagMonk: install ragmonk and run: ragmonk source add . && ragmonk index")
		}
	}

	_ = path
	output.Println("")
	return nil
}
