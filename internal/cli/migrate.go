package cli

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/filesystem"
	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var migrateCmd = &cobra.Command{
	Use:   "migrate",
	Short: "Migrate an existing project to Full OSB Mode (RagMonk intelligence)",
	Long: `Migrate guides you through upgrading an existing OSB project to Full Mode,
where all historical project context is managed by RagMonk instead of raw
Markdown files in .osb/knowledge/.

Existing .osb/knowledge/ files are preserved and imported into RagMonk.`,
	RunE: runMigrate,
}

var migrateAutoIndex bool

func init() {
	migrateCmd.Flags().BoolVar(&migrateAutoIndex, "auto-index", true,
		"Set auto_index: true in osb.yaml after migration")
}

func runMigrate(cmd *cobra.Command, args []string) error {
	cwd, _ := os.Getwd()
	root, err := config.FindRoot(cwd)
	if err != nil {
		return fmt.Errorf("osb.yaml not found — run osb init first")
	}
	cfg, err := config.Load(root)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	output.Header("OSB Migration — Full Mode / RagMonk")

	// Step 1: assess current state
	output.SubHeader("Step 1: Current state")
	if cfg.IsFullMode() {
		output.Success("  Mode: already full — nothing to change in osb.yaml")
	} else {
		output.Info(fmt.Sprintf("  Mode: %s → will be upgraded to full", cfg.Mode))
	}

	paths := cfg.GetPaths()
	knowledgeDir := filepath.Join(root, paths.Knowledge)
	knowledgeExists := filesystem.DirExists(knowledgeDir)
	if knowledgeExists {
		output.Info(fmt.Sprintf("  Knowledge dir: %s (will be preserved)", knowledgeDir))
	} else {
		output.Info("  Knowledge dir: not present")
	}

	// Step 2: ragmonk availability
	output.SubHeader("Step 2: RagMonk")
	intel := cfg.GetIntelligence()
	provider := intelligence.NewProvider(intel)

	if !provider.IsAvailable() {
		output.Error("  RagMonk not found on PATH")
		output.Println("")
		output.Println("  Install RagMonk first:")
		output.Println("")
		output.Println("    Windows (PowerShell):")
		output.Println("      irm https://raw.githubusercontent.com/gzarog/RagMonk/main/install.ps1 | iex")
		output.Println("")
		output.Println("    macOS / Linux:")
		output.Println("      curl -fsSL https://raw.githubusercontent.com/gzarog/RagMonk/main/install.sh | sh")
		output.Println("")
		output.Println("  Then re-run: osb migrate")
		output.Println("")
		return nil
	}
	output.Success("  RagMonk found")

	// Step 3: register source
	output.SubHeader("Step 3: Register project source")
	registered, _ := provider.IsSourceRegistered(root)
	if registered {
		output.Success("  Source already registered")
	} else {
		output.Println("  Registering project with RagMonk...")
		if err := provider.RegisterSource(root); err != nil {
			if !printFullModeError(err) {
				output.Error(fmt.Sprintf("  Registration failed: %s", err))
			}
			output.Println("")
			output.Println("  Manual command: ragmonk source add .")
			output.Println("")
			return nil
		}
		output.Success("  Source registered")
	}

	// Step 4: index
	output.SubHeader("Step 4: Build knowledge index")
	indexed, _ := provider.IsIndexed()
	if indexed {
		output.Info("  Index exists — running incremental update")
	} else {
		output.Println("  No index found — running full index (this may take a while)...")
	}
	if err := provider.Index(root); err != nil {
		if !printFullModeError(err) {
			output.Error(fmt.Sprintf("  Indexing failed: %s", err))
		}
		output.Println("")
		output.Println("  Manual command: ragmonk index")
		output.Println("")
		return nil
	}
	output.Success("  Index built")

	// Step 5: update osb.yaml
	output.SubHeader("Step 5: Update osb.yaml")
	changed := false
	if !cfg.IsFullMode() {
		cfg.Mode = "full"
		changed = true
	}
	if cfg.Intelligence == nil {
		cfg.Intelligence = &config.IntelligenceConfig{Provider: "ragmonk"}
		changed = true
	}
	if cfg.Intelligence.RagMonk == nil {
		cfg.Intelligence.RagMonk = config.DefaultRagMonkConfig()
		changed = true
	}
	if migrateAutoIndex && !cfg.Intelligence.RagMonk.AutoIndex {
		cfg.Intelligence.RagMonk.AutoIndex = true
		changed = true
	}
	if changed {
		if err := config.Save(root, cfg); err != nil {
			output.Error(fmt.Sprintf("  Failed to save osb.yaml: %s", err))
			return nil
		}
		output.Success("  osb.yaml updated")
	} else {
		output.Success("  osb.yaml already up to date")
	}

	// Summary
	output.Println("")
	output.Header("Migration complete")
	output.Success("Your project is now in Full OSB Mode.")
	output.Println("")
	output.Println("  Next steps:")
	output.Println("    osb intelligence status   — verify health")
	output.Println("    osb intelligence doctor   — detailed check")
	output.Println("    osb context build \"<task>\" --role implementer")
	output.Println("")
	output.Println("  Existing .osb/knowledge/ files are preserved and indexed.")
	output.Println("  In Full Mode, agents must use 'osb context build' for historical")
	output.Println("  project context rather than scanning the knowledge directory directly.")
	output.Println("")
	return nil
}
