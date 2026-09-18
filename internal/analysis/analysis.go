package analysis

import (
	"context"
	"fmt"
	"os/exec"
)

type ProviderType string

const (
	ProviderLSP        ProviderType = "lsp"
	ProviderTreeSitter ProviderType = "tree-sitter"
	ProviderCodeGraph  ProviderType = "codegraph"
)

type Symbol struct {
	Name     string
	Kind     string // function, class, method, interface, etc
	File     string
	Line     int
	Language string
}

type Reference struct {
	File string
	Line int
	Kind string // definition, reference, implementation
}

type Provider interface {
	Name() ProviderType
	Available() bool
	FindSymbols(ctx context.Context, query string) ([]Symbol, error)
	FindReferences(ctx context.Context, file string, line int) ([]Reference, error)
}

type Manager struct {
	providers []Provider
}

func NewManager() *Manager {
	return &Manager{}
}

func (m *Manager) Register(p Provider) {
	m.providers = append(m.providers, p)
}

func (m *Manager) Available() []Provider {
	var available []Provider
	for _, p := range m.providers {
		if p.Available() {
			available = append(available, p)
		}
	}
	return available
}

func (m *Manager) FindSymbols(ctx context.Context, query string) ([]Symbol, error) {
	for _, p := range m.providers {
		if p.Available() {
			symbols, err := p.FindSymbols(ctx, query)
			if err == nil && len(symbols) > 0 {
				return symbols, nil
			}
		}
	}
	return nil, fmt.Errorf("no provider returned results for symbol query: %s", query)
}

// LSPInfo checks for language server availability
type LSPInfo struct {
	Language   string
	ServerCmd  string
	ServerName string
}

var KnownLSPServers = []LSPInfo{
	{Language: "C#", ServerCmd: "OmniSharp", ServerName: "OmniSharp"},
	{Language: "TypeScript", ServerCmd: "typescript-language-server", ServerName: "TypeScript Language Server"},
	{Language: "JavaScript", ServerCmd: "typescript-language-server", ServerName: "TypeScript Language Server"},
	{Language: "Python", ServerCmd: "pyright", ServerName: "Pyright"},
	{Language: "Go", ServerCmd: "gopls", ServerName: "gopls"},
	{Language: "Rust", ServerCmd: "rust-analyzer", ServerName: "rust-analyzer"},
	{Language: "Java", ServerCmd: "jdtls", ServerName: "Eclipse JDT.LS"},
	{Language: "Kotlin", ServerCmd: "kotlin-language-server", ServerName: "Kotlin Language Server"},
	{Language: "C/C++", ServerCmd: "clangd", ServerName: "clangd"},
	{Language: "PHP", ServerCmd: "phpactor", ServerName: "Phpactor"},
	{Language: "Ruby", ServerCmd: "solargraph", ServerName: "Solargraph"},
	{Language: "Dart", ServerCmd: "dart", ServerName: "Dart Analysis Server"},
}

func CheckLSPAvailability(language string) (bool, string) {
	for _, lsp := range KnownLSPServers {
		if lsp.Language == language {
			_, err := exec.LookPath(lsp.ServerCmd)
			return err == nil, lsp.ServerName
		}
	}
	return false, ""
}
