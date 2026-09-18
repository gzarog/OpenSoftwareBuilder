package cli

import (
	"fmt"

	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/gzarog/opensoftwarebuilder/internal/validation"
	"github.com/spf13/cobra"
)

var validateCmd = &cobra.Command{
	Use:   "validate <type> <file>",
	Short: "Validate an artifact (spec, checkpoint, config)",
	Args:  cobra.ExactArgs(2),
	RunE:  runValidate,
}

func runValidate(cmd *cobra.Command, args []string) error {
	artifactType := args[0]
	path := args[1]

	output.Header(fmt.Sprintf("Validating %s: %s", artifactType, path))

	var findings []validation.Finding
	var err error

	switch artifactType {
	case "spec":
		findings, err = validation.ValidateSpec(path)
	case "checkpoint":
		findings, err = validation.ValidateCheckpoint(path)
	case "config":
		findings, err = validation.ValidateConfig(path)
	default:
		return fmt.Errorf("unknown artifact type: %s (expected: spec, checkpoint, config)", artifactType)
	}
	if err != nil {
		return err
	}

	if len(findings) == 0 {
		output.Success("Valid")
	} else {
		for _, f := range findings {
			switch f.Level {
			case "error":
				output.Error(f.Message)
			case "warning":
				output.Warning(f.Message)
			default:
				output.Info(f.Message)
			}
		}
	}

	output.Println("")
	for _, f := range findings {
		if f.Level == "error" {
			return fmt.Errorf("validation failed with errors")
		}
	}
	return nil
}
