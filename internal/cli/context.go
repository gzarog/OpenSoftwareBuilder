package cli

import (
	"fmt"
	"os"
	"strings"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var contextCmd = &cobra.Command{
	Use:   "context",
	Short: "Manage and retrieve task context packages via RagMonk",
}

var contextBuildCmd = &cobra.Command{
	Use:   "build <query>",
	Short: "Build a role-specific evidence package from RagMonk",
	Args:  cobra.MinimumNArgs(1),
	RunE:  runContextBuild,
}

var contextRole string
var contextComponents []string
var contextTier int
var contextMaxResults int

func init() {
	contextBuildCmd.Flags().StringVar(&contextRole, "role", intelligence.RoleImplementer,
		"Agent role: architect|implementer|reviewer|qa")
	contextBuildCmd.Flags().StringSliceVar(&contextComponents, "component", nil,
		"Component names to filter context (can be specified multiple times)")
	contextBuildCmd.Flags().IntVar(&contextTier, "tier", 0, "Task tier (informational)")
	contextBuildCmd.Flags().IntVar(&contextMaxResults, "max-results", 20, "Maximum evidence items")
	contextCmd.AddCommand(contextBuildCmd)
}

func runContextBuild(cmd *cobra.Command, args []string) error {
	query := strings.Join(args, " ")

	cwd, _ := os.Getwd()
	root, err := config.FindRoot(cwd)
	if err != nil {
		return fmt.Errorf("osb.yaml not found — run osb init")
	}
	cfg, err := config.Load(root)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}
	if !cfg.IsFullMode() {
		output.Warning("Context packages require full mode. Current mode: light")
		output.Info("Switch to full mode by setting mode: full in osb.yaml")
		return nil
	}

	provider := intelligence.NewProvider(cfg.GetIntelligence())
	if !provider.IsAvailable() {
		output.Error("RagMonk not available — full mode requires RagMonk")
		output.Println("Install: irm https://raw.githubusercontent.com/gzarog/RagMonk/main/install.ps1 | iex")
		output.Println("Then:    ragmonk init && ragmonk source add . && ragmonk index")
		return nil
	}

	output.Header(fmt.Sprintf("Context: %s [%s]", query, contextRole))
	if len(contextComponents) > 0 {
		output.Info(fmt.Sprintf("Components: %s", strings.Join(contextComponents, ", ")))
	}

	opts := intelligence.ContextOptions{
		Components: contextComponents,
		Tier:       contextTier,
		MaxResults: contextMaxResults,
		Root:       root,
	}

	ctx, err := intelligence.BuildTaskContext(provider, query, contextRole, opts)
	if err != nil {
		if fme, ok := err.(*intelligence.FullModeError); ok {
			output.Error(fmt.Sprintf("[%s] %s", fme.Code, fme.Message))
			output.Println(fme.Remedy)
		} else {
			output.Error(err.Error())
		}
		return nil
	}

	output.SubHeader("Evidence")
	for i, item := range ctx.Evidence {
		if item.File != "" {
			output.SubHeader(fmt.Sprintf("[%d] %s (%s)", i+1, item.File, item.Kind))
		} else if item.Kind != "" {
			output.SubHeader(fmt.Sprintf("[%d] %s", i+1, item.Kind))
		}
		if item.Content != "" {
			output.Println(item.Content)
		}
	}
	if len(ctx.Evidence) == 0 {
		output.Info("No evidence returned")
	}

	output.Println("")
	return nil
}
