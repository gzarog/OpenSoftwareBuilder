package cli

import (
	"os"
	"path/filepath"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/filesystem"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/gzarog/opensoftwarebuilder/internal/workspace"
	"github.com/spf13/cobra"
)

var workspaceCmd = &cobra.Command{
	Use:   "workspace",
	Short: "Manage workspaces",
}

var workspaceListCmd = &cobra.Command{
	Use:   "list",
	Short: "List configured workspaces",
	RunE:  runWorkspaceList,
}

func init() {
	workspaceCmd.AddCommand(workspaceListCmd)
}

func runWorkspaceList(cmd *cobra.Command, args []string) error {
	cwd, _ := os.Getwd()
	root, err := config.FindRoot(cwd)
	if err != nil {
		return err
	}
	cfg, err := config.Load(root)
	if err != nil {
		return err
	}

	workspaces := workspace.ResolveWorkspaces(root, cfg)

	output.Header("Workspaces")
	for _, ws := range workspaces {
		exists := filesystem.DirExists(filepath.Join(root, ws.Path))
		status := "ok"
		if !exists {
			status = "missing"
		}
		tc := ws.Toolchain
		if tc == "" {
			tc = "auto"
		}
		bs := ws.BuildSystem
		if bs == "" {
			bs = "default"
		}
		output.Printf("  %-15s toolchain=%-10s build_system=%-8s path=%-20s [%s]\n",
			ws.Name, tc, bs, ws.Path, status)
		if len(ws.DependsOn) > 0 {
			output.Printf("                depends_on: %v\n", ws.DependsOn)
		}
	}
	output.Println("")
	return nil
}
