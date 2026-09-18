package cli

import (
	"context"
	"fmt"
	"os"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/executor"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/gzarog/opensoftwarebuilder/internal/workspace"
	"github.com/spf13/cobra"
)

var cmdWorkspace string

var buildCmd = &cobra.Command{
	Use:   "build",
	Short: "Build project or workspaces",
	RunE:  func(cmd *cobra.Command, args []string) error { return runCommand("build") },
}

var testCmd = &cobra.Command{
	Use:   "test",
	Short: "Run tests for project or workspaces",
	RunE:  func(cmd *cobra.Command, args []string) error { return runCommand("test") },
}

var lintCmd = &cobra.Command{
	Use:   "lint",
	Short: "Run linter for project or workspaces",
	RunE:  func(cmd *cobra.Command, args []string) error { return runCommand("lint") },
}

var formatCmd = &cobra.Command{
	Use:   "format",
	Short: "Run formatter for project or workspaces",
	RunE:  func(cmd *cobra.Command, args []string) error { return runCommand("format") },
}

func init() {
	for _, cmd := range []*cobra.Command{buildCmd, testCmd, lintCmd, formatCmd} {
		cmd.Flags().StringVar(&cmdWorkspace, "workspace", "", "Run only for specific workspace")
	}
}

func runCommand(commandName string) error {
	cwd, _ := os.Getwd()
	root, err := config.FindRoot(cwd)
	if err != nil {
		return err
	}
	cfg, err := config.Load(root)
	if err != nil {
		return err
	}

	output.Header(fmt.Sprintf("OSB %s", commandName))

	workspaces := workspace.ResolveWorkspaces(root, cfg)

	if cmdWorkspace != "" {
		var filtered []workspace.WorkspaceInfo
		for _, ws := range workspaces {
			if ws.Name == cmdWorkspace {
				filtered = append(filtered, ws)
			}
		}
		if len(filtered) == 0 {
			return fmt.Errorf("workspace not found: %s", cmdWorkspace)
		}
		workspaces = filtered
	}

	groups := workspace.ParallelGroups(workspaces)
	ctx := context.Background()

	results := workspace.RunParallel(groups, 2, func(ws workspace.WorkspaceInfo) workspace.RunResult {
		cmdSpec := getCommandSpec(cfg, ws, commandName)
		if cmdSpec == nil {
			return workspace.RunResult{
				Workspace: ws.Name,
				Success:   true,
				Output:    "no " + commandName + " command configured",
			}
		}

		execMode := "local"
		execImage := ""
		if cfg.Execution != nil {
			execMode = cfg.Execution.Mode
			execImage = cfg.Execution.Image
		}
		if wsCfg, ok := cfg.Workspaces[ws.Name]; ok && wsCfg.Execution != nil {
			execMode = wsCfg.Execution.Mode
			execImage = wsCfg.Execution.Image
		}

		e := executor.NewExecutor(execMode, execImage, ws.AbsPath)
		opts := executor.RunOptions{
			Dir:    ws.AbsPath,
			Stdout: os.Stdout,
			Stderr: os.Stderr,
		}
		if len(cmdSpec.Argv) > 0 {
			opts.Argv = cmdSpec.Argv
		} else if cmdSpec.Shell != "" {
			opts.Shell = cmdSpec.Shell
		}

		result, runErr := e.Run(ctx, opts)
		if runErr != nil {
			return workspace.RunResult{Workspace: ws.Name, Error: runErr}
		}
		r := workspace.RunResult{Workspace: ws.Name, Success: result.ExitCode == 0, Output: result.Stdout}
		if result.ExitCode != 0 {
			r.Error = fmt.Errorf("exit code %d", result.ExitCode)
		}
		return r
	})

	output.Println("")
	hasFailure := false
	for _, r := range results {
		if r.Error != nil {
			output.Error(fmt.Sprintf("%-15s %s", r.Workspace, r.Error))
			hasFailure = true
		} else {
			msg := "ok"
			if r.Output != "" && len(r.Output) < 60 {
				msg = r.Output
			}
			output.Success(fmt.Sprintf("%-15s %s", r.Workspace, msg))
		}
	}

	output.Println("")
	if hasFailure {
		return fmt.Errorf("%s failed", commandName)
	}
	return nil
}

func getCommandSpec(cfg *config.Config, ws workspace.WorkspaceInfo, commandName string) *config.CommandSpec {
	if wsCfg, ok := cfg.Workspaces[ws.Name]; ok && wsCfg.Commands != nil {
		if spec := specFromCommands(wsCfg.Commands, commandName); spec != nil {
			return spec
		}
	}
	if cfg.Commands != nil {
		return specFromCommands(cfg.Commands, commandName)
	}
	return nil
}

func specFromCommands(cmds *config.CommandsConfig, name string) *config.CommandSpec {
	switch name {
	case "build":
		return cmds.Build
	case "test":
		return cmds.Test
	case "lint":
		return cmds.Lint
	case "format":
		return cmds.Format
	case "restore":
		return cmds.Restore
	case "fitness":
		return cmds.Fitness
	case "e2e":
		return cmds.E2E
	}
	return nil
}
