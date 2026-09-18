package cli

import (
	"fmt"
	"os"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var intelligenceCmd = &cobra.Command{
	Use:   "intelligence",
	Short: "Manage and query the project intelligence provider",
}

var intelligenceStatusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show intelligence provider health",
	RunE:  runIntelligenceStatus,
}

var intelligenceIndexCmd = &cobra.Command{
	Use:   "index",
	Short: "Trigger a RagMonk index",
	RunE:  runIntelligenceIndex,
}

var intelligenceQueryCmd = &cobra.Command{
	Use:   "query <text>",
	Short: "Run a free-text knowledge query through RagMonk",
	Args:  cobra.MinimumNArgs(1),
	RunE:  runIntelligenceQuery,
}

func init() {
	intelligenceCmd.AddCommand(intelligenceStatusCmd)
	intelligenceCmd.AddCommand(intelligenceIndexCmd)
	intelligenceCmd.AddCommand(intelligenceQueryCmd)
}

func loadIntelligenceProvider() (intelligence.Provider, *config.Config, string, error) {
	cwd, _ := os.Getwd()
	root, err := config.FindRoot(cwd)
	if err != nil {
		return nil, nil, "", fmt.Errorf("osb.yaml not found — run osb init")
	}
	cfg, err := config.Load(root)
	if err != nil {
		return nil, nil, "", fmt.Errorf("loading config: %w", err)
	}
	if !cfg.IsFullMode() {
		return nil, cfg, root, fmt.Errorf("intelligence commands require full mode (current mode: light)")
	}
	provider := intelligence.NewProvider(cfg.GetIntelligence())
	return provider, cfg, root, nil
}

func runIntelligenceStatus(cmd *cobra.Command, args []string) error {
	provider, cfg, root, err := loadIntelligenceProvider()
	if err != nil {
		output.Error(err.Error())
		return nil
	}

	output.Header("Intelligence Status")

	mode := cfg.Mode
	if mode == "" {
		mode = "full"
	}
	output.Info(fmt.Sprintf("Mode:     %s", mode))
	output.Info(fmt.Sprintf("Provider: %s", cfg.GetIntelligence().Provider))

	if !provider.IsAvailable() {
		output.Error("RagMonk not installed")
		output.Println("  Install: irm https://raw.githubusercontent.com/gzarog/RagMonk/main/install.ps1 | iex")
		return nil
	}

	status, err := provider.GetStatus()
	if err != nil {
		output.Error(fmt.Sprintf("Status error: %s", err))
		return nil
	}

	if status.Version != "" {
		output.Success(fmt.Sprintf("RagMonk:  %s", status.Version))
	} else {
		output.Success("RagMonk:  installed")
	}

	if status.Healthy {
		output.Success("Health:   healthy")
	} else {
		output.Error("Health:   unhealthy")
	}

	registered, _ := provider.IsSourceRegistered(root)
	if registered {
		output.Success("Source:   registered")
	} else {
		output.Error("Source:   not registered — run: ragmonk source add .")
	}

	if status.IndexAvailable {
		output.Success("Index:    available")
	} else {
		output.Error("Index:    missing — run: osb intelligence index")
	}

	if status.DaemonRunning {
		output.Success("Daemon:   running")
	} else {
		output.Info("Daemon:   not running (ragmonk daemon start)")
	}

	output.Println("")
	return nil
}

func runIntelligenceIndex(cmd *cobra.Command, args []string) error {
	provider, _, root, err := loadIntelligenceProvider()
	if err != nil {
		output.Error(err.Error())
		return nil
	}

	if !provider.IsAvailable() {
		output.Error("RagMonk not installed")
		return nil
	}

	output.Println("Indexing project knowledge...")
	if err := provider.Index(root); err != nil {
		output.Error(fmt.Sprintf("Index failed: %s", err))
		return nil
	}
	output.Success("Index complete")
	return nil
}

func runIntelligenceQuery(cmd *cobra.Command, args []string) error {
	provider, cfg, _, err := loadIntelligenceProvider()
	if err != nil {
		output.Error(err.Error())
		return nil
	}

	if !provider.IsAvailable() {
		output.Error("RagMonk not installed")
		return nil
	}

	query := args[0]
	intel := cfg.GetIntelligence()
	rm := intel.RagMonk

	opts := intelligence.ExploreOptions{
		MaxResults:          rm.Retrieval.MaxResults,
		IncludeCode:         rm.Retrieval.IncludeCode,
		IncludeTests:        rm.Retrieval.IncludeTests,
		IncludeDocs:         rm.Retrieval.IncludeDocs,
		IncludeOSBKnowledge: rm.Retrieval.IncludeOSBKnowledge,
	}

	result, err := provider.Explore(query, opts)
	if err != nil {
		output.Error(fmt.Sprintf("Query failed: %s", err))
		return nil
	}

	for _, item := range result.Items {
		if item.File != "" {
			output.SubHeader(item.File)
		}
		output.Println(item.Content)
	}
	return nil
}
