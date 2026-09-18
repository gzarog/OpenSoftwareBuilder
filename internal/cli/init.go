package cli

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/detection"
	"github.com/gzarog/opensoftwarebuilder/internal/filesystem"
	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var initProfile string
var initProviders []string
var initMode string

var initCmd = &cobra.Command{
	Use:   "init",
	Short: "Initialize a project with OSB",
	RunE:  runInit,
}

func init() {
	initCmd.Flags().StringVar(&initProfile, "profile", "", "Project profile (dotnet-services, node-web, python-api, generic)")
	initCmd.Flags().StringSliceVar(&initProviders, "providers", nil, "Provider adapters to set up (claude, codex, copilot, vscode)")
	initCmd.Flags().StringVar(&initMode, "mode", "full", "Operating mode: full (requires RagMonk) or light")
}

func runInit(cmd *cobra.Command, args []string) error {
	cwd, _ := os.Getwd()

	if filesystem.FileExists(filepath.Join(cwd, "osb.yaml")) {
		return fmt.Errorf("osb.yaml already exists — use osb doctor to validate")
	}

	output.Header("Open Software Builder — Init")

	cfg := config.DefaultConfig()

	// Apply mode from flag.
	if initMode == "light" {
		cfg.Mode = "light"
		cfg.Intelligence = nil
	} else {
		cfg.Mode = "full"
		cfg.Intelligence = config.DefaultIntelligenceConfig()
	}

	if initProfile == "" {
		output.Println("\nDetecting repository...")
		result, err := detection.Detect(cwd)
		if err == nil && len(result.Toolchains) > 0 {
			output.Println("")
			for _, tc := range result.Toolchains {
				output.Success(fmt.Sprintf("%s (detected: %s)", tc.Name, strings.Join(tc.Evidence, ", ")))
			}
			for _, bs := range result.BuildSystems {
				output.Info(fmt.Sprintf("%s package manager (%s)", bs.Name, bs.Evidence))
			}
			if len(result.Toolchains) == 1 {
				applyToolchainDefaults(cfg, result.Toolchains[0].ID, result.BuildSystems)
			} else {
				cfg.Workspaces = make(map[string]*config.Workspace)
				for _, tc := range result.Toolchains {
					ws := &config.Workspace{Path: ".", Toolchain: tc.ID}
					for _, bs := range result.BuildSystems {
						ws.BuildSystem = bs.ID
						break
					}
					cfg.Workspaces[tc.ID] = ws
				}
			}
		} else {
			output.Info("No toolchains detected — using generic profile")
		}
	} else {
		applyProfile(cfg, initProfile)
	}

	paths := cfg.GetPaths()
	dirs := []string{
		paths.Checkpoints,
		filepath.Join(paths.Knowledge, "tasks"),
		filepath.Join(paths.Knowledge, "components"),
		paths.State,
	}
	for _, d := range dirs {
		if err := os.MkdirAll(filepath.Join(cwd, d), 0755); err != nil {
			return fmt.Errorf("creating directory %s: %w", d, err)
		}
	}

	if err := config.Save(cwd, cfg); err != nil {
		return fmt.Errorf("writing osb.yaml: %w", err)
	}
	output.Success("Created osb.yaml")

	if cfg.IsFullMode() {
		runRagMonkSetup(cfg, cwd)
	}

	gitignorePath := filepath.Join(cwd, ".osb", ".gitignore")
	os.MkdirAll(filepath.Dir(gitignorePath), 0755)
	os.WriteFile(gitignorePath, []byte("state/\n"), 0644)

	templates := map[string]string{
		".osb/progress/.gitkeep":    "",
		".osb/knowledge/INDEX.md":   "# Knowledge Index\n\n| Date | Task | Components | Tier |\n|---|---|---|---|\n",
	}
	for relPath, content := range templates {
		fullPath := filepath.Join(cwd, relPath)
		os.MkdirAll(filepath.Dir(fullPath), 0755)
		os.WriteFile(fullPath, []byte(content), 0644)
	}

	for _, provider := range initProviders {
		if err := setupProvider(cwd, provider); err != nil {
			output.Warning(fmt.Sprintf("Provider %s setup: %s", provider, err))
		} else {
			output.Success(fmt.Sprintf("Provider adapter: %s", provider))
		}
	}

	output.Println("")
	output.Success("Project initialized")
	output.Println("\n  Next steps:")
	output.Println("    osb doctor              — verify environment")
	output.Println("    osb status              — check project state")
	if cfg.IsFullMode() {
		output.Println("    osb intelligence status — check RagMonk health")
	}
	output.Println("")
	return nil
}

func runRagMonkSetup(cfg *config.Config, root string) {
	output.SubHeader("Intelligence Setup")

	provider := intelligence.NewRagMonkProvider(cfg.GetIntelligence())

	if !provider.IsAvailable() {
		output.Warning("RagMonk not found — full mode requires RagMonk")
		output.Println("  Install: irm https://raw.githubusercontent.com/gzarog/RagMonk/main/install.ps1 | iex")
		output.Println("  Then:    ragmonk init && ragmonk source add . && ragmonk index")
		output.Println("  Run osb doctor after installing to verify the setup.")
		return
	}

	output.Success("RagMonk found")

	registered, _ := provider.IsSourceRegistered(root)
	if registered {
		output.Info("Project already registered as RagMonk source")
	} else {
		output.Println("  Registering project with RagMonk...")
		if err := provider.RegisterSource(root); err != nil {
			output.Warning(fmt.Sprintf("Source registration failed: %s", err))
			output.Println("  Run manually: ragmonk source add .")
			return
		}
		output.Success("Project registered as RagMonk source")
	}

	indexed, _ := provider.IsIndexed()
	if indexed {
		output.Info("Knowledge index already available")
	} else {
		output.Println("  Building knowledge index (this may take a moment)...")
		if err := provider.Index(root); err != nil {
			output.Warning(fmt.Sprintf("Indexing failed: %s", err))
			output.Println("  Run manually: ragmonk index")
			return
		}
		output.Success("Knowledge index built")
	}
}

func applyToolchainDefaults(cfg *config.Config, toolchainID string, buildSystems []detection.DetectedBuildSystem) {
	switch toolchainID {
	case "dotnet":
		cfg.Paths.Source = []string{"src", "services", "apps", "packages", "contracts"}
		cfg.Paths.Generated = []string{"bin", "obj", "TestResults", "coverage", ".artifacts"}
		cfg.Commands = &config.CommandsConfig{
			Build: &config.CommandSpec{Argv: []string{"dotnet", "build"}},
			Test:  &config.CommandSpec{Argv: []string{"dotnet", "test"}},
		}
	case "node":
		cfg.Paths.Source = []string{"src", "apps", "packages"}
		cfg.Paths.Generated = []string{"node_modules", "dist", "build", ".next", "out", "coverage"}
		runner := "npm"
		for _, bs := range buildSystems {
			if bs.ID == "pnpm" || bs.ID == "yarn" || bs.ID == "bun" {
				runner = bs.ID
				break
			}
		}
		cfg.Commands = &config.CommandsConfig{
			Build: &config.CommandSpec{Argv: []string{runner, "run", "build"}},
			Test:  &config.CommandSpec{Argv: []string{runner, "test"}},
		}
	case "python":
		cfg.Paths.Source = []string{"src", "."}
		cfg.Paths.Generated = []string{"__pycache__", ".venv", "venv", "dist", "build", ".pytest_cache", ".mypy_cache"}
		cfg.Commands = &config.CommandsConfig{
			Test: &config.CommandSpec{Argv: []string{"pytest"}},
		}
	case "go":
		cfg.Paths.Source = []string{"."}
		cfg.Paths.Generated = []string{"vendor", "bin"}
		cfg.Commands = &config.CommandsConfig{
			Build: &config.CommandSpec{Argv: []string{"go", "build", "./..."}},
			Test:  &config.CommandSpec{Argv: []string{"go", "test", "./..."}},
		}
	case "rust":
		cfg.Paths.Source = []string{"src"}
		cfg.Paths.Generated = []string{"target"}
		cfg.Commands = &config.CommandsConfig{
			Build: &config.CommandSpec{Argv: []string{"cargo", "build"}},
			Test:  &config.CommandSpec{Argv: []string{"cargo", "test"}},
		}
	case "java":
		cfg.Paths.Source = []string{"src"}
		cfg.Paths.Generated = []string{"target", "build", ".gradle", "out"}
		for _, bs := range buildSystems {
			switch bs.ID {
			case "maven":
				cfg.Commands = &config.CommandsConfig{
					Build: &config.CommandSpec{Argv: []string{"mvn", "compile"}},
					Test:  &config.CommandSpec{Argv: []string{"mvn", "test"}},
				}
			case "gradle":
				cfg.Commands = &config.CommandsConfig{
					Build: &config.CommandSpec{Argv: []string{"gradle", "build"}},
					Test:  &config.CommandSpec{Argv: []string{"gradle", "test"}},
				}
			}
		}
	}
}

func applyProfile(cfg *config.Config, profile string) {
	switch profile {
	case "dotnet-services":
		cfg.Paths.Source = []string{"services", "apps", "packages", "contracts"}
		cfg.Paths.Generated = []string{"bin", "obj", "node_modules", "dist", "build", ".artifacts", "TestResults", "coverage", ".next", "out"}
		cfg.Commands = &config.CommandsConfig{
			Build: &config.CommandSpec{Argv: []string{"dotnet", "build"}},
			Test:  &config.CommandSpec{Argv: []string{"dotnet", "test"}},
		}
		cfg.Capabilities = &config.CapabilitiesConfig{StructuralExplorer: "codegraph", BrowserQA: "optional"}
		cfg.Policy.SensitiveAreas = []string{"auth", "payments", "settlement", "external-input"}
	case "node-web":
		cfg.Paths.Source = []string{"src", "apps", "packages"}
		cfg.Paths.Generated = []string{"node_modules", "dist", "build", ".next", "out", "coverage"}
		cfg.Commands = &config.CommandsConfig{
			Build: &config.CommandSpec{Argv: []string{"npm", "run", "build"}},
			Test:  &config.CommandSpec{Argv: []string{"npm", "test"}},
		}
		cfg.Capabilities = &config.CapabilitiesConfig{StructuralExplorer: "codegraph", BrowserQA: "required"}
	case "python-api":
		cfg.Paths.Source = []string{"src", "."}
		cfg.Paths.Generated = []string{"__pycache__", ".venv", "venv", "dist", "build", ".pytest_cache", ".mypy_cache"}
		cfg.Commands = &config.CommandsConfig{
			Test: &config.CommandSpec{Argv: []string{"pytest"}},
		}
	}
}

func setupProvider(root string, provider string) error {
	switch provider {
	case "claude":
		return writeProviderFiles(root, map[string]string{
			"CLAUDE.md": `# Project Instructions

This project uses Open Software Builder in **full mode**.
See core/workflow/README.md for the canonical workflow.
See core/roles/ for role definitions.

Run ` + "`osb doctor`" + ` to check environment health.
Run ` + "`osb status`" + ` to see project state.
Run ` + "`osb intelligence status`" + ` to verify RagMonk is healthy.

## Full OSB Mode — Intelligence Rules

In full OSB mode, all project knowledge discovery and historical context
retrieval goes through RagMonk.

**Do not** independently scan the repository to discover historical project context.

**Use** the OSB-provided RagMonk context package supplied in your task prompt.

**Request additional context** through ` + "`osb intelligence query`" + ` when evidence is insufficient.

You may still open specific source files when implementing or reviewing them.
The restriction applies to knowledge discovery, not to reading files
that are already the subject of your current task.
`,
			".claude/agents/architect.md": "---\nmodel: opus\n---\n# Architect\nYou are the Architect role. See core/roles/architect.md.\n\nContext for this task is provided via the OSB RagMonk context package.\nDo not independently scan the repository for historical context.\n",
			".claude/agents/implementer.md": "---\nmodel: opus\n---\n# Implementer\nYou are the Implementer role. See core/roles/implementer.md.\n\nContext for this task is provided via the OSB RagMonk context package.\nDo not independently scan the repository for historical context.\n",
			".claude/agents/reviewer.md": "---\nmodel: opus\n---\n# Reviewer\nYou are the Reviewer role. See core/roles/reviewer.md.\n\nContext for this task is provided via the OSB RagMonk context package.\nDo not independently scan the repository for historical context.\n",
			".claude/agents/qa-tester.md": "---\nmodel: opus\n---\n# QA Tester\nYou are the QA Tester role. See core/roles/qa-tester.md.\n\nContext for this task is provided via the OSB RagMonk context package.\nDo not independently scan the repository for historical context.\n",
		})
	case "codex":
		return writeProviderFiles(root, map[string]string{
			"AGENTS.md": "# Project Instructions\n\nThis project uses Open Software Builder.\nSee core/workflow/README.md for the canonical workflow.\n",
		})
	case "copilot":
		return writeProviderFiles(root, map[string]string{
			".github/copilot-instructions.md": "# Copilot Instructions\n\nThis project uses Open Software Builder.\nSee core/workflow/README.md for the canonical workflow.\n",
		})
	case "vscode":
		return writeProviderFiles(root, map[string]string{
			".vscode/tasks.json": "{\n  \"version\": \"2.0.0\",\n  \"tasks\": [\n    {\"label\": \"osb: doctor\", \"type\": \"shell\", \"command\": \"osb doctor\"},\n    {\"label\": \"osb: status\", \"type\": \"shell\", \"command\": \"osb status\"},\n    {\"label\": \"osb: build\", \"type\": \"shell\", \"command\": \"osb build\"},\n    {\"label\": \"osb: test\", \"type\": \"shell\", \"command\": \"osb test\"}\n  ]\n}",
		})
	default:
		return fmt.Errorf("unknown provider: %s", provider)
	}
}

func writeProviderFiles(root string, files map[string]string) error {
	for relPath, content := range files {
		fullPath := filepath.Join(root, relPath)
		if err := os.MkdirAll(filepath.Dir(fullPath), 0755); err != nil {
			return err
		}
		if err := os.WriteFile(fullPath, []byte(content), 0644); err != nil {
			return err
		}
	}
	return nil
}
