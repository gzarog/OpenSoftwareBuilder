package unit

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/gzarog/opensoftwarebuilder/internal/detection"
)

func TestDetectDotnet(t *testing.T) {
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "MyApp.sln"), []byte(""), 0644)
	os.WriteFile(filepath.Join(dir, "MyApp.csproj"), []byte(""), 0644)

	result, err := detection.Detect(dir)
	if err != nil {
		t.Fatalf("detection failed: %v", err)
	}
	found := false
	for _, tc := range result.Toolchains {
		if tc.ID == "dotnet" {
			found = true
			if tc.Confidence != detection.ConfidenceHigh {
				t.Errorf("expected high confidence for dotnet")
			}
		}
	}
	if !found {
		t.Error("expected to detect dotnet toolchain")
	}
}

func TestDetectNode(t *testing.T) {
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "package.json"), []byte("{}"), 0644)
	os.WriteFile(filepath.Join(dir, "pnpm-lock.yaml"), []byte(""), 0644)

	result, err := detection.Detect(dir)
	if err != nil {
		t.Fatalf("detection failed: %v", err)
	}
	foundToolchain := false
	foundBuildSystem := false
	for _, tc := range result.Toolchains {
		if tc.ID == "node" {
			foundToolchain = true
		}
	}
	for _, bs := range result.BuildSystems {
		if bs.ID == "pnpm" {
			foundBuildSystem = true
		}
	}
	if !foundToolchain {
		t.Error("expected to detect node toolchain")
	}
	if !foundBuildSystem {
		t.Error("expected to detect pnpm build system")
	}
}

func TestDetectPython(t *testing.T) {
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "pyproject.toml"), []byte(""), 0644)

	result, err := detection.Detect(dir)
	if err != nil {
		t.Fatalf("detection failed: %v", err)
	}
	found := false
	for _, tc := range result.Toolchains {
		if tc.ID == "python" {
			found = true
		}
	}
	if !found {
		t.Error("expected to detect python toolchain")
	}
}

func TestDetectGo(t *testing.T) {
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "go.mod"), []byte("module test"), 0644)

	result, err := detection.Detect(dir)
	if err != nil {
		t.Fatalf("detection failed: %v", err)
	}
	found := false
	for _, tc := range result.Toolchains {
		if tc.ID == "go" {
			found = true
		}
	}
	if !found {
		t.Error("expected to detect go toolchain")
	}
}

func TestDetectMultiple(t *testing.T) {
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "MyApp.sln"), []byte(""), 0644)
	os.WriteFile(filepath.Join(dir, "package.json"), []byte("{}"), 0644)
	os.WriteFile(filepath.Join(dir, "pyproject.toml"), []byte(""), 0644)

	result, err := detection.Detect(dir)
	if err != nil {
		t.Fatalf("detection failed: %v", err)
	}
	if len(result.Toolchains) < 3 {
		t.Errorf("expected at least 3 toolchains, got %d", len(result.Toolchains))
	}
}

func TestDetectEmpty(t *testing.T) {
	dir := t.TempDir()
	result, err := detection.Detect(dir)
	if err != nil {
		t.Fatalf("detection failed: %v", err)
	}
	if len(result.Toolchains) != 0 {
		t.Errorf("expected no toolchains in empty dir, got %d", len(result.Toolchains))
	}
}

func TestDetectRecursive(t *testing.T) {
	dir := t.TempDir()
	sub := filepath.Join(dir, "backend")
	os.MkdirAll(sub, 0755)
	os.WriteFile(filepath.Join(sub, "go.mod"), []byte("module test"), 0644)

	results, err := detection.DetectRecursive(dir, 1)
	if err != nil {
		t.Fatalf("recursive detection failed: %v", err)
	}
	found := false
	for _, r := range results {
		for _, tc := range r.Toolchains {
			if tc.ID == "go" {
				found = true
			}
		}
	}
	if !found {
		t.Error("expected to detect go toolchain in subdirectory")
	}
}
