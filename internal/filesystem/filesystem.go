package filesystem

import (
	"os"
	"path/filepath"
	"strings"
)

// FileExists checks if a file exists
func FileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}

// DirExists checks if a directory exists
func DirExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}

// LatestMtime returns the latest modification time (as unix float) across directories,
// excluding generated directories
func LatestMtime(dirs []string, generatedPatterns []string) (float64, error) {
	genSet := make(map[string]bool)
	for _, g := range generatedPatterns {
		genSet[g] = true
	}

	var latest float64
	for _, dir := range dirs {
		err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return nil
			}
			if info.IsDir() {
				name := info.Name()
				if genSet[name] || strings.HasPrefix(name, ".") {
					return filepath.SkipDir
				}
				return nil
			}
			mtime := float64(info.ModTime().Unix())
			if mtime > latest {
				latest = mtime
			}
			return nil
		})
		if err != nil {
			return latest, err
		}
	}
	return latest, nil
}

// ActiveCheckpoints returns checkpoint files that don't have a corresponding -done marker
func ActiveCheckpoints(cpDir string) ([]string, error) {
	if _, err := os.Stat(cpDir); os.IsNotExist(err) {
		return nil, nil
	}
	entries, err := os.ReadDir(cpDir)
	if err != nil {
		return nil, err
	}

	doneSet := make(map[string]bool)
	var candidates []string
	for _, e := range entries {
		name := e.Name()
		if strings.HasSuffix(name, ".done") {
			doneSet[strings.TrimSuffix(name, ".done")] = true
		} else if strings.HasSuffix(name, ".md") {
			candidates = append(candidates, name)
		}
	}

	var active []string
	for _, c := range candidates {
		base := strings.TrimSuffix(c, ".md")
		if !doneSet[base] && c != ".gitkeep" {
			active = append(active, c)
		}
	}
	return active, nil
}
