package cli

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/filesystem"
	"github.com/gzarog/opensoftwarebuilder/internal/git"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var changedCmd = &cobra.Command{
	Use:   "changed [minutes]",
	Short: "Detect recent source changes (default: 90 minutes)",
	RunE:  runChanged,
}

func runChanged(cmd *cobra.Command, args []string) error {
	minutes := 90
	if len(args) > 0 {
		if m, err := strconv.Atoi(args[0]); err == nil {
			minutes = m
		}
	}

	cwd, _ := os.Getwd()
	root, err := config.FindRoot(cwd)
	if err != nil {
		return err
	}
	cfg, err := config.Load(root)
	if err != nil {
		return err
	}

	paths := cfg.GetPaths()
	since := time.Now().Add(-time.Duration(minutes) * time.Minute)

	output.Header(fmt.Sprintf("Changes in last %d minutes", minutes))

	if git.IsAvailable() && git.IsRepo(root) {
		g := git.New(root)
		uncommitted, _ := g.UncommittedFiles()
		if len(uncommitted) > 0 {
			output.SubHeader("Uncommitted changes")
			for _, f := range uncommitted {
				output.Printf("  %s\n", f)
			}
		}
		changed, _ := g.ChangedFilesSince(since)
		if len(changed) > 0 {
			output.SubHeader("Recently committed")
			for _, f := range changed {
				output.Printf("  %s\n", f)
			}
		}
		if len(uncommitted) == 0 && len(changed) == 0 {
			output.Println("\n  No changes detected.")
		}
	} else {
		output.SubHeader("Modified files (mtime)")
		genSet := make(map[string]bool)
		for _, g := range paths.Generated {
			genSet[g] = true
		}
		count := 0
		for _, src := range paths.Source {
			dir := filepath.Join(root, src)
			if !filesystem.DirExists(dir) {
				continue
			}
			filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
				if err != nil {
					return nil
				}
				if info.IsDir() && genSet[info.Name()] {
					return filepath.SkipDir
				}
				if !info.IsDir() && info.ModTime().After(since) {
					rel, _ := filepath.Rel(root, path)
					output.Printf("  %s\n", rel)
					count++
				}
				return nil
			})
		}
		if count == 0 {
			output.Println("\n  No changes detected.")
		}
	}

	cpDir := filepath.Join(root, paths.Checkpoints)
	checkpoints, _ := filesystem.ActiveCheckpoints(cpDir)
	if len(checkpoints) > 0 {
		output.SubHeader("Active checkpoints")
		for _, cp := range checkpoints {
			output.Printf("  %s\n", cp)
		}
	}

	output.Println("")
	return nil
}
