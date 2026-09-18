package unit

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
)

func TestDefaultConfig(t *testing.T) {
	cfg := config.DefaultConfig()
	if cfg.Version != 2 {
		t.Errorf("expected version 2, got %d", cfg.Version)
	}
	if cfg.Paths == nil {
		t.Fatal("expected default paths")
	}
	if len(cfg.Paths.Source) == 0 {
		t.Error("expected default source paths")
	}
}

func TestLoadConfig(t *testing.T) {
	dir := t.TempDir()
	content := `version: 2
paths:
  source:
    - src
    - lib
  generated:
    - dist
  checkpoints: .osb/progress
  knowledge: .osb/knowledge
  state: .osb/state
commands:
  build:
    argv: [go, build, ./...]
  test:
    argv: [go, test, ./...]
policy:
  require_independent_review: true
  require_fresh_qa: true
  sensitive_areas:
    - auth
`
	os.WriteFile(filepath.Join(dir, "osb.yaml"), []byte(content), 0644)

	cfg, err := config.Load(dir)
	if err != nil {
		t.Fatalf("failed to load config: %v", err)
	}
	if cfg.Version != 2 {
		t.Errorf("expected version 2, got %d", cfg.Version)
	}
	if len(cfg.Paths.Source) != 2 {
		t.Errorf("expected 2 source paths, got %d", len(cfg.Paths.Source))
	}
	if cfg.Commands == nil || cfg.Commands.Build == nil {
		t.Error("expected build command")
	}
	if cfg.Commands.Build.Argv[0] != "go" {
		t.Errorf("expected argv[0]=go, got %s", cfg.Commands.Build.Argv[0])
	}
}

func TestLoadConfigV1ShellString(t *testing.T) {
	dir := t.TempDir()
	content := `version: 1
commands:
  build: dotnet build
  test: dotnet test
`
	os.WriteFile(filepath.Join(dir, "osb.yaml"), []byte(content), 0644)

	cfg, err := config.Load(dir)
	if err != nil {
		t.Fatalf("failed to load config: %v", err)
	}
	if cfg.Version != 1 {
		t.Errorf("expected version 1, got %d", cfg.Version)
	}
	if cfg.Commands.Build.Shell != "dotnet build" {
		t.Errorf("expected shell command 'dotnet build', got '%s'", cfg.Commands.Build.Shell)
	}
}

func TestFindRoot(t *testing.T) {
	dir := t.TempDir()
	os.WriteFile(filepath.Join(dir, "osb.yaml"), []byte("version: 2\n"), 0644)
	subdir := filepath.Join(dir, "sub", "deep")
	os.MkdirAll(subdir, 0755)

	root, err := config.FindRoot(subdir)
	if err != nil {
		t.Fatalf("failed to find root: %v", err)
	}
	if root != dir {
		t.Errorf("expected root %s, got %s", dir, root)
	}
}

func TestFindRootNotFound(t *testing.T) {
	dir := t.TempDir()
	_, err := config.FindRoot(dir)
	if err == nil {
		t.Error("expected error when osb.yaml not found")
	}
}

func TestConfigValidate(t *testing.T) {
	cfg := &config.Config{Version: 99}
	errs := cfg.Validate()
	if len(errs) == 0 {
		t.Error("expected validation errors for version 99")
	}
}

func TestDefaultConfigMode(t *testing.T) {
	cfg := config.DefaultConfig()
	if cfg.Mode != "full" {
		t.Errorf("expected default mode 'full', got %q", cfg.Mode)
	}
	if !cfg.IsFullMode() {
		t.Error("expected IsFullMode() true for default config")
	}
	if cfg.Intelligence == nil {
		t.Fatal("expected default intelligence config")
	}
	if cfg.Intelligence.Provider != "ragmonk" {
		t.Errorf("expected provider 'ragmonk', got %q", cfg.Intelligence.Provider)
	}
}

func TestLightModeConfig(t *testing.T) {
	cfg := config.DefaultConfig()
	cfg.Mode = "light"
	cfg.Intelligence = nil
	if cfg.IsFullMode() {
		t.Error("expected IsFullMode() false for light mode")
	}
	errs := cfg.Validate()
	for _, e := range errs {
		t.Errorf("unexpected validation error: %s", e)
	}
}

func TestFullModeRequiresProvider(t *testing.T) {
	cfg := config.DefaultConfig()
	cfg.Mode = "full"
	cfg.Intelligence = &config.IntelligenceConfig{} // no provider
	errs := cfg.Validate()
	found := false
	for _, e := range errs {
		if e != "" {
			found = true
		}
	}
	if !found {
		t.Error("expected validation error when full mode has no provider")
	}
}

func TestInvalidModeConfig(t *testing.T) {
	cfg := config.DefaultConfig()
	cfg.Mode = "turbo"
	errs := cfg.Validate()
	if len(errs) == 0 {
		t.Error("expected validation error for unknown mode")
	}
}

func TestLoadConfigWithIntelligence(t *testing.T) {
	dir := t.TempDir()
	content := `version: 2
mode: full
intelligence:
  provider: ragmonk
  ragmonk:
    executable: ragmonk
    auto_index: true
    transport: cli
`
	os.WriteFile(filepath.Join(dir, "osb.yaml"), []byte(content), 0644)
	cfg, err := config.Load(dir)
	if err != nil {
		t.Fatalf("failed to load config: %v", err)
	}
	if cfg.Mode != "full" {
		t.Errorf("expected mode 'full', got %q", cfg.Mode)
	}
	if cfg.Intelligence == nil {
		t.Fatal("expected intelligence section")
	}
	if cfg.Intelligence.Provider != "ragmonk" {
		t.Errorf("expected provider 'ragmonk', got %q", cfg.Intelligence.Provider)
	}
	intel := cfg.GetIntelligence()
	if intel.RagMonk.Executable != "ragmonk" {
		t.Errorf("expected executable 'ragmonk', got %q", intel.RagMonk.Executable)
	}
}

func TestGetIntelligenceDefaults(t *testing.T) {
	cfg := &config.Config{Version: 2, Mode: "full"}
	intel := cfg.GetIntelligence()
	if intel == nil {
		t.Fatal("expected non-nil intelligence config")
	}
	if intel.RagMonk == nil {
		t.Fatal("expected non-nil ragmonk config")
	}
	if intel.RagMonk.Executable != "ragmonk" {
		t.Errorf("expected default executable 'ragmonk', got %q", intel.RagMonk.Executable)
	}
	if intel.RagMonk.Transport != "cli" {
		t.Errorf("expected default transport 'cli', got %q", intel.RagMonk.Transport)
	}
}

func TestSaveAndLoad(t *testing.T) {
	dir := t.TempDir()
	cfg := config.DefaultConfig()
	cfg.Commands = &config.CommandsConfig{
		Build: &config.CommandSpec{Argv: []string{"make", "build"}},
	}

	if err := config.Save(dir, cfg); err != nil {
		t.Fatalf("failed to save: %v", err)
	}

	loaded, err := config.Load(dir)
	if err != nil {
		t.Fatalf("failed to load: %v", err)
	}
	if loaded.Version != 2 {
		t.Errorf("expected version 2, got %d", loaded.Version)
	}
}
