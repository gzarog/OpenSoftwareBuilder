package cli

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/gzarog/opensoftwarebuilder/internal/analysis"
	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/detection"
	"github.com/gzarog/opensoftwarebuilder/internal/filesystem"
	"github.com/gzarog/opensoftwarebuilder/internal/git"
	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/gzarog/opensoftwarebuilder/internal/platform"
	"github.com/spf13/cobra"
)

var doctorCmd = &cobra.Command{
	Use:   "doctor",
	Short: "Validate configuration and environment health",
	RunE:  runDoctor,
}

func runDoctor(cmd *cobra.Command, args []string) error {
	output.Header("Open Software Builder Doctor")

	plat := platform.New()

	output.SubHeader("Platform")
	output.Success(fmt.Sprintf("%s %s", strings.ToUpper(plat.OS()[:1])+plat.OS()[1:], plat.Arch()))

	output.SubHeader("Repository")
	if git.IsAvailable() {
		ver, err := git.New(".").Version()
		if err == nil {
			output.Success(ver)
		}
	} else {
		output.Warning("Git not found")
	}

	cwd, _ := os.Getwd()
	if git.IsRepo(cwd) {
		output.Success("Git repository")
	} else {
		output.Info("Not a git repository")
	}

	output.SubHeader("Configuration")
	root, err := config.FindRoot(cwd)
	if err != nil {
		output.Warning("osb.yaml not found — run osb init")
	} else {
		cfg, err := config.Load(root)
		if err != nil {
			output.Error(fmt.Sprintf("Config error: %s", err))
		} else {
			output.Success(fmt.Sprintf("osb.yaml (version %d)", cfg.Version))
			for _, e := range cfg.Validate() {
				output.Error(e)
			}

			paths := cfg.GetPaths()
			for _, src := range paths.Source {
				if filesystem.DirExists(filepath.Join(root, src)) {
					output.Success(fmt.Sprintf("Source: %s", src))
				} else {
					output.Info(fmt.Sprintf("Source: %s (not found)", src))
				}
			}
			if filesystem.DirExists(filepath.Join(root, paths.Checkpoints)) {
				output.Success(fmt.Sprintf("Checkpoints: %s", paths.Checkpoints))
			}
			if filesystem.DirExists(filepath.Join(root, paths.Knowledge)) {
				output.Success(fmt.Sprintf("Knowledge: %s", paths.Knowledge))
			}

			if cfg.Commands != nil {
				if cfg.Commands.Build != nil {
					output.Success("Build command configured")
				} else {
					output.Info("No build command")
				}
				if cfg.Commands.Test != nil {
					output.Success("Test command configured")
				} else {
					output.Info("No test command")
				}
			}

			if len(cfg.Workspaces) > 0 {
				output.SubHeader("Workspaces")
				for name, ws := range cfg.Workspaces {
					if filesystem.DirExists(filepath.Join(root, ws.Path)) {
						output.Success(fmt.Sprintf("%s (%s @ %s)", name, ws.Toolchain, ws.Path))
					} else {
						output.Warning(fmt.Sprintf("%s (%s @ %s — path not found)", name, ws.Toolchain, ws.Path))
					}
				}
			}
		}
	}

	output.SubHeader("Toolchains")
	detected, err := detection.Detect(cwd)
	if err == nil {
		for _, tc := range detected.Toolchains {
			exe := toolchainExecutable(tc.ID)
			if exe != "" {
				if _, err := plat.FindExecutable(exe); err == nil {
					output.Success(tc.Name)
				} else {
					output.Warning(fmt.Sprintf("%s (%s not found)", tc.Name, exe))
				}
			} else {
				output.Info(tc.Name)
			}
		}
		if len(detected.Toolchains) == 0 {
			output.Info("No toolchains detected")
		}
	}

	output.SubHeader("Analysis")
	if detected != nil {
		for _, tc := range detected.Toolchains {
			lang := toolchainToLanguage(tc.ID)
			if lang != "" {
				available, name := analysis.CheckLSPAvailability(lang)
				if available {
					output.Success(fmt.Sprintf("%s: %s available", lang, name))
				} else {
					output.Info(fmt.Sprintf("%s: LSP unavailable", lang))
				}
			}
		}
	}

	output.SubHeader("Providers")
	providerFiles := map[string]string{
		"Claude":  "CLAUDE.md",
		"Codex":   "AGENTS.md",
		"Copilot": ".github/copilot-instructions.md",
		"VS Code": ".vscode/tasks.json",
	}
	anyProvider := false
	for name, file := range providerFiles {
		if filesystem.FileExists(filepath.Join(cwd, file)) {
			output.Success(name)
			anyProvider = true
		}
	}
	if !anyProvider {
		output.Info("No provider adapters detected")
	}

	if root != "" {
		cfg, _ := config.Load(root)
		if cfg != nil {
			cpDir := filepath.Join(root, cfg.GetPaths().Checkpoints)
			checkpoints, _ := filesystem.ActiveCheckpoints(cpDir)
			if len(checkpoints) > 0 {
				output.SubHeader("Active Checkpoints")
				output.Warning(fmt.Sprintf("%d active checkpoint(s)", len(checkpoints)))
			}

			runIntelligenceDoctor(cfg, root)
		}
	}

	output.Println("")
	return nil
}

func runIntelligenceDoctor(cfg *config.Config, root string) {
	output.SubHeader("Intelligence")

	mode := cfg.Mode
	if mode == "" {
		mode = "full"
	}
	output.Info(fmt.Sprintf("Mode: %s", mode))

	if !cfg.IsFullMode() {
		output.Info("Provider: none (light mode)")
		return
	}

	intel := cfg.GetIntelligence()
	output.Info(fmt.Sprintf("Provider: %s", intel.Provider))

	if intel.Provider != "ragmonk" {
		output.Warning(fmt.Sprintf("Unknown provider: %s", intel.Provider))
		return
	}

	provider := intelligence.NewRagMonkProvider(intel)

	if !provider.IsAvailable() {
		output.Error("RagMonk not installed")
		output.Println("  Install: irm https://raw.githubusercontent.com/gzarog/RagMonk/main/install.ps1 | iex")
		output.Println("  Then:    ragmonk init && ragmonk source add . && ragmonk index")
		return
	}

	status, err := provider.GetStatus()
	if err != nil {
		output.Error(fmt.Sprintf("RagMonk status error: %s", err))
		return
	}

	if status.Version != "" {
		output.Success(fmt.Sprintf("RagMonk installed: %s", status.Version))
	} else {
		output.Success("RagMonk installed")
	}

	if status.Healthy {
		output.Success("RagMonk runtime healthy")
	} else {
		output.Error("RagMonk runtime unhealthy — run: ragmonk doctor")
	}

	registered, _ := provider.IsSourceRegistered(root)
	if registered {
		output.Success("Project registered as source")
	} else {
		output.Error("Project not registered — run: ragmonk source add .")
	}

	if status.IndexAvailable {
		output.Success("Knowledge index available")
		if status.IndexHealthy {
			output.Success("Index healthy")
		} else {
			output.Warning("Index degraded — run: ragmonk index")
		}
	} else {
		output.Error("Knowledge index missing — run: ragmonk index")
	}

	if status.DaemonRunning {
		output.Success("RagMonk daemon active")
	} else {
		output.Info("RagMonk daemon not running (optional — ragmonk daemon start)")
	}
}

func toolchainExecutable(id string) string {
	m := map[string]string{
		"dotnet": "dotnet", "node": "node", "python": "python3",
		"go": "go", "rust": "cargo", "java": "java", "kotlin": "kotlin",
		"cpp": "gcc", "php": "php", "ruby": "ruby", "dart": "dart",
	}
	return m[id]
}

func toolchainToLanguage(id string) string {
	m := map[string]string{
		"dotnet": "C#", "node": "TypeScript", "python": "Python",
		"go": "Go", "rust": "Rust", "java": "Java", "kotlin": "Kotlin",
		"cpp": "C/C++", "php": "PHP", "ruby": "Ruby", "dart": "Dart",
	}
	return m[id]
}
