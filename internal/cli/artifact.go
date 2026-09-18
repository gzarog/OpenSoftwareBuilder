package cli

import (
	"fmt"
	"os"

	"github.com/gzarog/opensoftwarebuilder/internal/artifact"
	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var artifactCmd = &cobra.Command{
	Use:   "artifact",
	Short: "Manage durable OSB artifact records (specs, reviews, QA, decisions)",
}

var artifactRecordCmd = &cobra.Command{
	Use:   "record <type> <name>",
	Short: "Create a new artifact record (type: spec|review|qa|decision)",
	Args:  cobra.ExactArgs(2),
	RunE:  runArtifactRecord,
}

var artifactTaskID string
var artifactComponent string
var artifactStatus string

func init() {
	artifactRecordCmd.Flags().StringVar(&artifactTaskID, "task-id", "", "Associate with a task ID")
	artifactRecordCmd.Flags().StringVar(&artifactComponent, "component", "", "Component this artifact belongs to")
	artifactRecordCmd.Flags().StringVar(&artifactStatus, "status", "draft", "Initial status (draft|approved|rejected)")
	artifactCmd.AddCommand(artifactRecordCmd)
}

func runArtifactRecord(cmd *cobra.Command, args []string) error {
	typeName := args[0]
	name := args[1]

	var atype artifact.Type
	switch typeName {
	case "spec":
		atype = artifact.TypeSpec
	case "review":
		atype = artifact.TypeReview
	case "qa":
		atype = artifact.TypeQA
	case "decision":
		atype = artifact.TypeDecision
	default:
		return fmt.Errorf("unknown artifact type %q — must be one of: spec, review, qa, decision", typeName)
	}

	cwd, _ := os.Getwd()
	root, err := config.FindRoot(cwd)
	if err != nil {
		return fmt.Errorf("osb.yaml not found — run osb init")
	}
	cfg, err := config.Load(root)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	paths := cfg.GetPaths()
	mgr := artifact.NewManager(root, paths.Specs, paths.Reviews, paths.QA, paths.Decisions)

	opts := artifact.RecordOptions{
		TaskID:    artifactTaskID,
		Component: artifactComponent,
		Status:    artifactStatus,
	}

	path, err := mgr.Record(atype, name, opts)
	if err != nil {
		return fmt.Errorf("creating artifact: %w", err)
	}

	output.Success(fmt.Sprintf("Created %s: %s", typeName, path))

	if cfg.IsFullMode() {
		provider := intelligence.NewProvider(cfg.GetIntelligence())
		if provider.IsAvailable() {
			output.Println("Indexing artifact with RagMonk...")
			if idxErr := provider.Index(root); idxErr != nil {
				output.Warning(fmt.Sprintf("RagMonk index failed: %s", idxErr))
			} else {
				output.Success("Indexed")
			}
		} else {
			output.Error("RagMonk not available — artifact created but not indexed")
			output.Error("Full mode requires RagMonk: install ragmonk and run: ragmonk source add . && ragmonk index")
		}
	}

	return nil
}
