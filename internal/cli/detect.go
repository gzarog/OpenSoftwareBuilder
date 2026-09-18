package cli

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/gzarog/opensoftwarebuilder/internal/detection"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var detectCmd = &cobra.Command{
	Use:   "detect",
	Short: "Detect repository toolchains and build systems",
	RunE:  runDetect,
}

func runDetect(cmd *cobra.Command, args []string) error {
	cwd, _ := os.Getwd()

	output.Header("Detected repository capabilities")

	results, err := detection.DetectRecursive(cwd, 2)
	if err != nil {
		return err
	}

	if len(results) == 0 {
		output.Println("\n  No toolchains detected.")
		output.Println("")
		return nil
	}

	for _, result := range results {
		relPath := "."
		if result.Path != cwd {
			rel, err := filepath.Rel(cwd, result.Path)
			if err == nil {
				relPath = rel
			}
		}
		if relPath != "." {
			output.Printf("\n  [%s]\n", relPath)
		}

		for _, tc := range result.Toolchains {
			confidence := "unknown"
			switch tc.Confidence {
			case detection.ConfidenceHigh:
				confidence = "high"
			case detection.ConfidenceMedium:
				confidence = "medium"
			case detection.ConfidenceLow:
				confidence = "low"
			}
			output.Success(fmt.Sprintf("%s (confidence: %s)", tc.Name, confidence))
			for _, ev := range tc.Evidence {
				output.Info(ev)
			}
		}

		for _, bs := range result.BuildSystems {
			output.Info(fmt.Sprintf("Build system: %s (%s)", bs.Name, bs.Evidence))
		}
	}

	output.Println("")
	return nil
}
