package plugins

import (
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

type PluginType string

const (
	PluginToolchain   PluginType = "toolchain"
	PluginBuildSystem PluginType = "build-system"
	PluginAnalysis    PluginType = "analysis"
	PluginProvider    PluginType = "provider"
	PluginExecutor    PluginType = "executor"
)

type Plugin struct {
	ID      string     `yaml:"id"`
	Name    string     `yaml:"name"`
	Type    PluginType `yaml:"type"`
	Version string     `yaml:"version"`
	BuiltIn bool       `yaml:"built_in"`
	Path    string     `yaml:"-"`
}

type Registry struct {
	pluginDir string
	plugins   map[string]*Plugin
}

func NewRegistry(osbHome string) *Registry {
	return &Registry{
		pluginDir: filepath.Join(osbHome, "plugins"),
		plugins:   make(map[string]*Plugin),
	}
}

func (r *Registry) LoadBuiltIn(plugins []*Plugin) {
	for _, p := range plugins {
		p.BuiltIn = true
		r.plugins[p.ID] = p
	}
}

func (r *Registry) LoadExternal() error {
	if _, err := os.Stat(r.pluginDir); os.IsNotExist(err) {
		return nil
	}
	entries, err := os.ReadDir(r.pluginDir)
	if err != nil {
		return err
	}
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		pluginFile := filepath.Join(r.pluginDir, e.Name(), "plugin.yaml")
		data, err := os.ReadFile(pluginFile)
		if err != nil {
			continue
		}
		var p Plugin
		if err := yaml.Unmarshal(data, &p); err != nil {
			continue
		}
		p.Path = filepath.Join(r.pluginDir, e.Name())
		r.plugins[p.ID] = &p
	}
	return nil
}

func (r *Registry) List() []*Plugin {
	var plugins []*Plugin
	for _, p := range r.plugins {
		plugins = append(plugins, p)
	}
	return plugins
}

func (r *Registry) Get(id string) (*Plugin, error) {
	p, ok := r.plugins[id]
	if !ok {
		return nil, fmt.Errorf("plugin not found: %s", id)
	}
	return p, nil
}

func (r *Registry) ListByType(t PluginType) []*Plugin {
	var result []*Plugin
	for _, p := range r.plugins {
		if p.Type == t {
			result = append(result, p)
		}
	}
	return result
}
