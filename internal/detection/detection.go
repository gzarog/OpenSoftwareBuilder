package detection

import (
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type Confidence int

const (
	ConfidenceLow    Confidence = 1
	ConfidenceMedium Confidence = 2
	ConfidenceHigh   Confidence = 3
)

type DetectedToolchain struct {
	ID         string
	Name       string
	Confidence Confidence
	Evidence   []string
}

type DetectedBuildSystem struct {
	ID       string
	Name     string
	Evidence string
}

type DetectionResult struct {
	Toolchains   []DetectedToolchain
	BuildSystems []DetectedBuildSystem
	Path         string
}

// DetectRule maps file patterns to toolchain IDs
type DetectRule struct {
	ToolchainID string
	Name        string
	Files       []string
	Extensions  []string
	Confidence  Confidence
}

// BuildSystemRule maps lock/config files to build systems
type BuildSystemRule struct {
	BuildSystemID string
	Name          string
	ToolchainID   string
	Files         []string
}

var defaultDetectRules = []DetectRule{
	{ToolchainID: "dotnet", Name: ".NET", Files: []string{"*.sln", "*.slnx", "*.csproj", "*.fsproj", "*.vbproj"}, Confidence: ConfidenceHigh},
	{ToolchainID: "node", Name: "Node.js", Files: []string{"package.json"}, Confidence: ConfidenceHigh},
	{ToolchainID: "python", Name: "Python", Files: []string{"pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile"}, Confidence: ConfidenceHigh},
	{ToolchainID: "go", Name: "Go", Files: []string{"go.mod"}, Confidence: ConfidenceHigh},
	{ToolchainID: "rust", Name: "Rust", Files: []string{"Cargo.toml"}, Confidence: ConfidenceHigh},
	{ToolchainID: "java", Name: "Java", Files: []string{"pom.xml", "build.gradle", "build.gradle.kts"}, Confidence: ConfidenceHigh},
	{ToolchainID: "kotlin", Name: "Kotlin", Files: []string{"build.gradle.kts"}, Extensions: []string{".kt", ".kts"}, Confidence: ConfidenceMedium},
	{ToolchainID: "cpp", Name: "C/C++", Files: []string{"CMakeLists.txt", "meson.build", "Makefile"}, Confidence: ConfidenceHigh},
	{ToolchainID: "php", Name: "PHP", Files: []string{"composer.json"}, Confidence: ConfidenceHigh},
	{ToolchainID: "ruby", Name: "Ruby", Files: []string{"Gemfile"}, Confidence: ConfidenceHigh},
	{ToolchainID: "dart", Name: "Dart/Flutter", Files: []string{"pubspec.yaml"}, Confidence: ConfidenceHigh},
}

var defaultBuildSystemRules = []BuildSystemRule{
	{BuildSystemID: "pnpm", Name: "pnpm", ToolchainID: "node", Files: []string{"pnpm-lock.yaml", "pnpm-workspace.yaml"}},
	{BuildSystemID: "yarn", Name: "Yarn", ToolchainID: "node", Files: []string{"yarn.lock"}},
	{BuildSystemID: "bun", Name: "Bun", ToolchainID: "node", Files: []string{"bun.lock", "bun.lockb"}},
	{BuildSystemID: "npm", Name: "npm", ToolchainID: "node", Files: []string{"package-lock.json"}},
	{BuildSystemID: "maven", Name: "Maven", ToolchainID: "java", Files: []string{"pom.xml", "mvnw"}},
	{BuildSystemID: "gradle", Name: "Gradle", ToolchainID: "java", Files: []string{"build.gradle", "build.gradle.kts", "gradlew"}},
	{BuildSystemID: "cmake", Name: "CMake", ToolchainID: "cpp", Files: []string{"CMakeLists.txt"}},
	{BuildSystemID: "meson", Name: "Meson", ToolchainID: "cpp", Files: []string{"meson.build"}},
	{BuildSystemID: "uv", Name: "uv", ToolchainID: "python", Files: []string{"uv.lock"}},
	{BuildSystemID: "poetry", Name: "Poetry", ToolchainID: "python", Files: []string{"poetry.lock"}},
	{BuildSystemID: "pip", Name: "pip", ToolchainID: "python", Files: []string{"requirements.txt"}},
}

// Detect scans a directory for toolchains and build systems
func Detect(dir string) (*DetectionResult, error) {
	result := &DetectionResult{Path: dir}

	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}

	fileNames := make(map[string]bool)
	for _, e := range entries {
		fileNames[e.Name()] = true
	}

	// Check toolchain rules
	seen := map[string]bool{}
	for _, rule := range defaultDetectRules {
		for _, pattern := range rule.Files {
			matched := matchPattern(pattern, fileNames, dir)
			if len(matched) > 0 && !seen[rule.ToolchainID] {
				result.Toolchains = append(result.Toolchains, DetectedToolchain{
					ID:         rule.ToolchainID,
					Name:       rule.Name,
					Confidence: rule.Confidence,
					Evidence:   matched,
				})
				seen[rule.ToolchainID] = true
			}
		}
	}

	// Check build system rules
	for _, rule := range defaultBuildSystemRules {
		for _, file := range rule.Files {
			if fileNames[file] {
				result.BuildSystems = append(result.BuildSystems, DetectedBuildSystem{
					ID:       rule.BuildSystemID,
					Name:     rule.Name,
					Evidence: file,
				})
				break
			}
		}
	}

	// Sort by confidence (high first)
	sort.Slice(result.Toolchains, func(i, j int) bool {
		return result.Toolchains[i].Confidence > result.Toolchains[j].Confidence
	})

	return result, nil
}

func matchPattern(pattern string, fileNames map[string]bool, dir string) []string {
	var matched []string
	if strings.Contains(pattern, "*") {
		// Glob pattern
		matches, _ := filepath.Glob(filepath.Join(dir, pattern))
		for _, m := range matches {
			matched = append(matched, filepath.Base(m))
		}
	} else {
		if fileNames[pattern] {
			matched = append(matched, pattern)
		}
	}
	return matched
}

// DetectRecursive scans dir and immediate subdirs
func DetectRecursive(dir string, maxDepth int) ([]*DetectionResult, error) {
	var results []*DetectionResult

	// Check root
	result, err := Detect(dir)
	if err == nil && len(result.Toolchains) > 0 {
		results = append(results, result)
	}

	if maxDepth <= 0 {
		return results, nil
	}

	// Check subdirs
	entries, err := os.ReadDir(dir)
	if err != nil {
		return results, nil
	}
	for _, e := range entries {
		if !e.IsDir() || strings.HasPrefix(e.Name(), ".") || isGenerated(e.Name()) {
			continue
		}
		subDir := filepath.Join(dir, e.Name())
		subResults, _ := DetectRecursive(subDir, maxDepth-1)
		results = append(results, subResults...)
	}
	return results, nil
}

func isGenerated(name string) bool {
	generated := map[string]bool{
		"node_modules": true, "bin": true, "obj": true,
		"dist": true, "build": true, ".next": true,
		"out": true, "coverage": true, "target": true,
		"vendor": true, "__pycache__": true, ".venv": true,
	}
	return generated[name]
}
