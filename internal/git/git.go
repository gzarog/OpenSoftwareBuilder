package git

import (
	"fmt"
	"os/exec"
	"strings"
	"time"
)

type Git struct {
	root string
}

func New(root string) *Git {
	return &Git{root: root}
}

func IsRepo(dir string) bool {
	cmd := exec.Command("git", "-C", dir, "rev-parse", "--git-dir")
	return cmd.Run() == nil
}

func IsAvailable() bool {
	_, err := exec.LookPath("git")
	return err == nil
}

func (g *Git) run(args ...string) (string, error) {
	cmd := exec.Command("git", append([]string{"-C", g.root}, args...)...)
	out, err := cmd.Output()
	return strings.TrimSpace(string(out)), err
}

func (g *Git) HasUncommittedChanges() (bool, error) {
	out, err := g.run("status", "--porcelain")
	if err != nil {
		return false, err
	}
	return len(out) > 0, nil
}

func (g *Git) ChangedFilesSince(since time.Time) ([]string, error) {
	sinceStr := since.Format("2006-01-02T15:04:05")
	out, err := g.run("log", "--since="+sinceStr, "--name-only", "--pretty=format:")
	if err != nil {
		return nil, err
	}
	var files []string
	seen := map[string]bool{}
	for _, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if line != "" && !seen[line] {
			files = append(files, line)
			seen[line] = true
		}
	}
	return files, nil
}

func (g *Git) UncommittedFiles() ([]string, error) {
	out, err := g.run("status", "--porcelain")
	if err != nil {
		return nil, err
	}
	var files []string
	for _, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if len(line) > 3 {
			files = append(files, line[3:])
		}
	}
	return files, nil
}

func (g *Git) Version() (string, error) {
	cmd := exec.Command("git", "--version")
	out, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

func (g *Git) RecentCommits(n int) ([]string, error) {
	out, err := g.run("log", fmt.Sprintf("-%d", n), "--oneline")
	if err != nil {
		return nil, err
	}
	if out == "" {
		return nil, nil
	}
	return strings.Split(out, "\n"), nil
}

func (g *Git) Root() string { return g.root }

// FindGitRoot finds the git root from dir
func FindGitRoot(dir string) (string, error) {
	cmd := exec.Command("git", "-C", dir, "rev-parse", "--show-toplevel")
	out, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("not a git repository")
	}
	return strings.TrimSpace(string(out)), nil
}
