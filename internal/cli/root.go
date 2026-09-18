package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

var Version = "dev"

var rootCmd = &cobra.Command{
	Use:   "osb",
	Short: "Open Software Builder",
	Long: `Open Software Builder
An auditable, provider-neutral multi-agent software-delivery workflow.

Cross-platform CLI for multi-language development orchestration.`,
}

func Execute() error {
	return rootCmd.Execute()
}

func init() {
	rootCmd.AddCommand(initCmd)
	rootCmd.AddCommand(doctorCmd)
	rootCmd.AddCommand(statusCmd)
	rootCmd.AddCommand(changedCmd)
	rootCmd.AddCommand(validateCmd)
	rootCmd.AddCommand(gateCmd)
	rootCmd.AddCommand(knowledgeCmd)
	rootCmd.AddCommand(detectCmd)
	rootCmd.AddCommand(buildCmd)
	rootCmd.AddCommand(testCmd)
	rootCmd.AddCommand(lintCmd)
	rootCmd.AddCommand(formatCmd)
	rootCmd.AddCommand(pluginsCmd)
	rootCmd.AddCommand(workspaceCmd)
	rootCmd.AddCommand(intelligenceCmd)
	rootCmd.AddCommand(artifactCmd)
	rootCmd.AddCommand(contextCmd)
	rootCmd.AddCommand(migrateCmd)
	rootCmd.AddCommand(versionCmd)
}

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Print version information",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Printf("osb version %s\n", Version)
	},
}
