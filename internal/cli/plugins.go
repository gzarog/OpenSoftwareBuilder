package cli

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/gzarog/opensoftwarebuilder/internal/plugins"
	"github.com/spf13/cobra"
)

var pluginsCmd = &cobra.Command{
	Use:   "plugins",
	Short: "Manage plugins",
}

var pluginsListCmd = &cobra.Command{
	Use:   "list",
	Short: "List installed plugins",
	RunE:  runPluginsList,
}

var pluginsInfoCmd = &cobra.Command{
	Use:   "info <plugin>",
	Short: "Show plugin details",
	Args:  cobra.ExactArgs(1),
	RunE:  runPluginsInfo,
}

func init() {
	pluginsCmd.AddCommand(pluginsListCmd)
	pluginsCmd.AddCommand(pluginsInfoCmd)
}

func runPluginsList(cmd *cobra.Command, args []string) error {
	home, _ := os.UserHomeDir()
	registry := plugins.NewRegistry(filepath.Join(home, ".osb"))
	registry.LoadBuiltIn(builtInPlugins())
	registry.LoadExternal()

	all := registry.List()
	sort.Slice(all, func(i, j int) bool {
		if all[i].Type != all[j].Type {
			return all[i].Type < all[j].Type
		}
		return all[i].ID < all[j].ID
	})

	output.Header("Plugins")
	currentType := plugins.PluginType("")
	for _, p := range all {
		if p.Type != currentType {
			currentType = p.Type
			output.SubHeader(string(currentType))
		}
		source := "external"
		if p.BuiltIn {
			source = "built-in"
		}
		output.Printf("  %-20s %s\n", p.ID, source)
	}
	output.Println("")
	return nil
}

func runPluginsInfo(cmd *cobra.Command, args []string) error {
	home, _ := os.UserHomeDir()
	registry := plugins.NewRegistry(filepath.Join(home, ".osb"))
	registry.LoadBuiltIn(builtInPlugins())
	registry.LoadExternal()

	p, err := registry.Get(args[0])
	if err != nil {
		return err
	}

	output.Header(fmt.Sprintf("Plugin: %s", p.Name))
	output.Printf("  ID:       %s\n", p.ID)
	output.Printf("  Type:     %s\n", p.Type)
	output.Printf("  Built-in: %v\n", p.BuiltIn)
	output.Println("")
	return nil
}

func builtInPlugins() []*plugins.Plugin {
	return []*plugins.Plugin{
		{ID: "dotnet", Name: ".NET", Type: plugins.PluginToolchain},
		{ID: "node", Name: "Node.js", Type: plugins.PluginToolchain},
		{ID: "python", Name: "Python", Type: plugins.PluginToolchain},
		{ID: "go", Name: "Go", Type: plugins.PluginToolchain},
		{ID: "rust", Name: "Rust", Type: plugins.PluginToolchain},
		{ID: "java", Name: "Java", Type: plugins.PluginToolchain},
		{ID: "kotlin", Name: "Kotlin", Type: plugins.PluginToolchain},
		{ID: "cpp", Name: "C/C++", Type: plugins.PluginToolchain},
		{ID: "php", Name: "PHP", Type: plugins.PluginToolchain},
		{ID: "ruby", Name: "Ruby", Type: plugins.PluginToolchain},
		{ID: "dart", Name: "Dart/Flutter", Type: plugins.PluginToolchain},
		{ID: "generic", Name: "Generic", Type: plugins.PluginToolchain},
		{ID: "npm", Name: "npm", Type: plugins.PluginBuildSystem},
		{ID: "pnpm", Name: "pnpm", Type: plugins.PluginBuildSystem},
		{ID: "yarn", Name: "Yarn", Type: plugins.PluginBuildSystem},
		{ID: "bun", Name: "Bun", Type: plugins.PluginBuildSystem},
		{ID: "maven", Name: "Maven", Type: plugins.PluginBuildSystem},
		{ID: "gradle", Name: "Gradle", Type: plugins.PluginBuildSystem},
		{ID: "cmake", Name: "CMake", Type: plugins.PluginBuildSystem},
		{ID: "meson", Name: "Meson", Type: plugins.PluginBuildSystem},
		{ID: "claude", Name: "Claude Code", Type: plugins.PluginProvider},
		{ID: "codex", Name: "OpenAI Codex", Type: plugins.PluginProvider},
		{ID: "copilot", Name: "GitHub Copilot", Type: plugins.PluginProvider},
		{ID: "vscode", Name: "VS Code", Type: plugins.PluginProvider},
		{ID: "lsp", Name: "LSP", Type: plugins.PluginAnalysis},
		{ID: "tree-sitter", Name: "Tree-sitter", Type: plugins.PluginAnalysis},
		{ID: "codegraph", Name: "CodeGraph", Type: plugins.PluginAnalysis},
	}
}
