package cli

import (
	"fmt"
	"os"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
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
		output.Println("\n  To record knowledge:")
		output.Println("    1. Create a task record in knowledge/tasks/")
		output.Println("    2. Update component records in knowledge/components/")
		output.Println("    3. Add entry to knowledge/INDEX.md")

		if len(args) > 1 {
			path, err := mgr.CreateTaskRecord(args[1])
			if err != nil {
				return err
			}
			output.Success(fmt.Sprintf("Created task record: %s", path))
		}
	case "status":
		output.Header("Knowledge Status")
		output.Println(fmt.Sprintf("\n  %s", mgr.RecordStatus()))
		if mgr.HasIndex() {
			rows, _ := mgr.IndexRows(10)
			if len(rows) > 0 {
				output.Println("\n  Recent entries:")
				for _, row := range rows {
					output.Printf("    %s\n", row)
				}
			}
		}
	default:
		return fmt.Errorf("unknown action: %s (expected: record, status)", action)
	}

	output.Println("")
	return nil
}
