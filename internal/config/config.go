package config

import (
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// Config represents osb.yaml configuration (supports v1 and v2)
type Config struct {
	Version      int                   `yaml:"version"`
	Profile      string                `yaml:"profile,omitempty"`
	Workspaces   map[string]*Workspace `yaml:"workspaces,omitempty"`
	Paths        *PathsConfig          `yaml:"paths,omitempty"`
	Commands     *CommandsConfig       `yaml:"commands,omitempty"`
	Capabilities *CapabilitiesConfig   `yaml:"capabilities,omitempty"`
	Policy       *PolicyConfig         `yaml:"policy,omitempty"`
	Analysis     *AnalysisConfig       `yaml:"analysis,omitempty"`
	Execution    *ExecutionConfig      `yaml:"execution,omitempty"`
}

type Workspace struct {
	Path         string              `yaml:"path"`
	Toolchain    string              `yaml:"toolchain"`
	BuildSystem  string              `yaml:"build_system,omitempty"`
	Commands     *CommandsConfig     `yaml:"commands,omitempty"`
	Generated    []string            `yaml:"generated,omitempty"`
	DependsOn    []string            `yaml:"depends_on,omitempty"`
	Capabilities *CapabilitiesConfig `yaml:"capabilities,omitempty"`
	Execution    *ExecutionConfig    `yaml:"execution,omitempty"`
}

type PathsConfig struct {
	Source      []string `yaml:"source,omitempty"`
	Generated   []string `yaml:"generated,omitempty"`
	Checkpoints string   `yaml:"checkpoints,omitempty"`
	Knowledge   string   `yaml:"knowledge,omitempty"`
	State       string   `yaml:"state,omitempty"`
}

type CommandsConfig struct {
	Build   *CommandSpec `yaml:"build,omitempty"`
	Test    *CommandSpec `yaml:"test,omitempty"`
	Lint    *CommandSpec `yaml:"lint,omitempty"`
	Format  *CommandSpec `yaml:"format,omitempty"`
	Restore *CommandSpec `yaml:"restore,omitempty"`
	Fitness *CommandSpec `yaml:"fitness,omitempty"`
	E2E     *CommandSpec `yaml:"e2e,omitempty"`
	Changed *CommandSpec `yaml:"changed,omitempty"`
}

type CommandSpec struct {
	Argv  []string `yaml:"argv,omitempty"`
	Shell string   `yaml:"shell,omitempty"` // legacy v1 support
}

// UnmarshalYAML handles both string and structured command specs
func (c *CommandSpec) UnmarshalYAML(value *yaml.Node) error {
	if value.Kind == yaml.ScalarNode {
		c.Shell = value.Value
		return nil
	}
	type raw CommandSpec
	return value.Decode((*raw)(c))
}

type CapabilitiesConfig struct {
	StructuralExplorer string `yaml:"structural_explorer,omitempty"`
	BrowserQA          string `yaml:"browser_qa,omitempty"`
}

type PolicyConfig struct {
	RequireIndependentReview bool     `yaml:"require_independent_review"`
	RequireFreshQA           bool     `yaml:"require_fresh_qa"`
	SensitiveAreas           []string `yaml:"sensitive_areas,omitempty"`
}

type AnalysisConfig struct {
	Symbols    *AnalysisProviders `yaml:"symbols,omitempty"`
	References *AnalysisProviders `yaml:"references,omitempty"`
	Syntax     *AnalysisProviders `yaml:"syntax,omitempty"`
}

type AnalysisProviders struct {
	Providers []string `yaml:"providers,omitempty"`
}

type ExecutionConfig struct {
	Mode  string `yaml:"mode,omitempty"` // local, docker, devcontainer
	Image string `yaml:"image,omitempty"`
}

func DefaultPaths() *PathsConfig {
	return &PathsConfig{
		Source:      []string{"src"},
		Generated:   []string{"bin", "obj", "node_modules", "dist", "build", ".next", "out", "coverage"},
		Checkpoints: ".osb/progress",
		Knowledge:   ".osb/knowledge",
		State:       ".osb/state",
	}
}

func DefaultPolicy() *PolicyConfig {
	return &PolicyConfig{
		RequireIndependentReview: true,
		RequireFreshQA:           true,
		SensitiveAreas:           []string{"auth", "payments", "external-input"},
	}
}

func DefaultConfig() *Config {
	return &Config{
		Version: 2,
		Paths:   DefaultPaths(),
		Policy:  DefaultPolicy(),
	}
}

// FindRoot walks up from dir looking for osb.yaml or .osb/osb.yaml
func FindRoot(dir string) (string, error) {
	dir, err := filepath.Abs(dir)
	if err != nil {
		return "", err
	}
	for {
		if _, err := os.Stat(filepath.Join(dir, "osb.yaml")); err == nil {
			return dir, nil
		}
		if _, err := os.Stat(filepath.Join(dir, ".osb", "osb.yaml")); err == nil {
			return dir, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return "", fmt.Errorf("osb.yaml not found (searched from current directory upward)")
}

// Load reads and parses osb.yaml from root
func Load(root string) (*Config, error) {
	path := filepath.Join(root, "osb.yaml")
	if _, err := os.Stat(path); os.IsNotExist(err) {
		path = filepath.Join(root, ".osb", "osb.yaml")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("reading config: %w", err)
	}
	cfg := DefaultConfig()
	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, fmt.Errorf("parsing config: %w", err)
	}
	return cfg, nil
}

// Save writes config to osb.yaml
func Save(root string, cfg *Config) error {
	data, err := yaml.Marshal(cfg)
	if err != nil {
		return fmt.Errorf("marshaling config: %w", err)
	}
	path := filepath.Join(root, "osb.yaml")
	return os.WriteFile(path, data, 0644)
}

// Validate checks config for errors
func (c *Config) Validate() []string {
	var errs []string
	if c.Version != 1 && c.Version != 2 {
		errs = append(errs, fmt.Sprintf("unsupported config version: %d (expected 1 or 2)", c.Version))
	}
	if c.Paths == nil {
		errs = append(errs, "paths section is required")
	}
	return errs
}

// GetPaths returns paths config with defaults applied
func (c *Config) GetPaths() *PathsConfig {
	if c.Paths != nil {
		return c.Paths
	}
	return DefaultPaths()
}

// GetPolicy returns policy config with defaults applied
func (c *Config) GetPolicy() *PolicyConfig {
	if c.Policy != nil {
		return c.Policy
	}
	return DefaultPolicy()
}
