package intelligence

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os/exec"
	"sync"
	"sync/atomic"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
)

// MCPProvider implements Provider by communicating with ragmonk via MCP/JSON-RPC
// over a persistent stdin/stdout subprocess. This avoids the per-call startup cost
// of the CLI transport and keeps database + index connections warm.
type MCPProvider struct {
	cfg     *config.RagMonkConfig
	mu      sync.Mutex
	cmd     *exec.Cmd
	stdin   io.WriteCloser
	stdout  *json.Decoder
	started bool
	seq     atomic.Int64
}

// NewMCPProvider creates an MCP-transport intelligence provider.
func NewMCPProvider(intel *config.IntelligenceConfig) *MCPProvider {
	cfg := intel.RagMonk
	if cfg == nil {
		cfg = config.DefaultRagMonkConfig()
	}
	return &MCPProvider{cfg: cfg}
}

func (m *MCPProvider) exe() string {
	if m.cfg.Executable != "" {
		return m.cfg.Executable
	}
	return "ragmonk"
}

// IsAvailable returns true if the ragmonk executable can be found on PATH.
func (m *MCPProvider) IsAvailable() bool {
	_, err := exec.LookPath(m.exe())
	return err == nil
}

// start launches ragmonk mcp serve if not already running. Caller must hold m.mu.
func (m *MCPProvider) start() error {
	if m.started {
		return nil
	}
	cmd := exec.Command(m.exe(), "mcp", "serve")
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return fmt.Errorf("mcp pipe: %w", err)
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("mcp pipe: %w", err)
	}
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("starting ragmonk mcp serve: %w", err)
	}
	m.cmd = cmd
	m.stdin = stdin
	m.stdout = json.NewDecoder(stdout)
	m.started = true
	return nil
}

type jsonRPCRequest struct {
	JSONRPC string      `json:"jsonrpc"`
	ID      int64       `json:"id"`
	Method  string      `json:"method"`
	Params  interface{} `json:"params"`
}

type jsonRPCResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      int64           `json:"id"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *jsonRPCError   `json:"error,omitempty"`
}

type jsonRPCError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

type mcpToolCall struct {
	Name      string      `json:"name"`
	Arguments interface{} `json:"arguments"`
}

func (m *MCPProvider) call(toolName string, arguments interface{}) (string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if err := m.start(); err != nil {
		return "", err
	}

	id := m.seq.Add(1)
	req := jsonRPCRequest{
		JSONRPC: "2.0",
		ID:      id,
		Method:  "tools/call",
		Params:  mcpToolCall{Name: toolName, Arguments: arguments},
	}

	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(req); err != nil {
		return "", fmt.Errorf("encoding mcp request: %w", err)
	}
	if _, err := m.stdin.Write(buf.Bytes()); err != nil {
		return "", fmt.Errorf("writing mcp request: %w", err)
	}

	var resp jsonRPCResponse
	if err := m.stdout.Decode(&resp); err != nil {
		return "", fmt.Errorf("reading mcp response: %w", err)
	}
	if resp.Error != nil {
		return "", fmt.Errorf("mcp error %d: %s", resp.Error.Code, resp.Error.Message)
	}

	// Unwrap text content from MCP tool result.
	var result struct {
		Content []struct {
			Type string `json:"type"`
			Text string `json:"text"`
		} `json:"content"`
	}
	if err := json.Unmarshal(resp.Result, &result); err != nil {
		return string(resp.Result), nil
	}
	var parts []string
	for _, c := range result.Content {
		if c.Type == "text" && c.Text != "" {
			parts = append(parts, c.Text)
		}
	}
	if len(parts) > 0 {
		return joinStrings(parts, "\n"), nil
	}
	return string(resp.Result), nil
}

func joinStrings(ss []string, sep string) string {
	result := ""
	for i, s := range ss {
		if i > 0 {
			result += sep
		}
		result += s
	}
	return result
}

// GetStatus queries ragmonk for a health snapshot. Uses CLI for status commands.
func (m *MCPProvider) GetStatus() (*Status, error) {
	cli := &RagMonkProvider{cfg: m.cfg}
	return cli.GetStatus()
}

// StartDaemon delegates to the CLI provider.
func (m *MCPProvider) StartDaemon() {
	cli := &RagMonkProvider{cfg: m.cfg}
	cli.StartDaemon()
}

// IsSourceRegistered delegates to CLI.
func (m *MCPProvider) IsSourceRegistered(root string) (bool, error) {
	cli := &RagMonkProvider{cfg: m.cfg}
	return cli.IsSourceRegistered(root)
}

// RegisterSource delegates to CLI.
func (m *MCPProvider) RegisterSource(root string) error {
	cli := &RagMonkProvider{cfg: m.cfg}
	return cli.RegisterSource(root)
}

// IsIndexed delegates to CLI.
func (m *MCPProvider) IsIndexed() (bool, error) {
	cli := &RagMonkProvider{cfg: m.cfg}
	return cli.IsIndexed()
}

// Index delegates to CLI (indexing is a management operation, not retrieval).
func (m *MCPProvider) Index(root string) error {
	cli := &RagMonkProvider{cfg: m.cfg}
	return cli.Index(root)
}

// EnsureFreshIndex delegates to CLI.
func (m *MCPProvider) EnsureFreshIndex(root string) error {
	cli := &RagMonkProvider{cfg: m.cfg}
	return cli.EnsureFreshIndex(root)
}

// Explore queries via MCP tools/call for warm-connection retrieval.
func (m *MCPProvider) Explore(query string, opts ExploreOptions) (*ExploreResult, error) {
	if !m.IsAvailable() {
		return nil, &FullModeError{
			Code:    ErrRagMonkMissing,
			Message: "RagMonk executable not found",
			Remedy:  installInstructions(),
		}
	}

	maxR := opts.MaxResults
	if maxR == 0 {
		maxR = 20
	}

	arguments := map[string]interface{}{
		"query":      query,
		"maxResults": maxR,
	}
	if len(opts.OsbTypes) > 0 {
		arguments["osbTypes"] = opts.OsbTypes
	}
	if len(opts.Components) > 0 {
		arguments["components"] = opts.Components
	}
	includes := []string{}
	if opts.IncludeCode {
		includes = append(includes, "code")
	}
	if opts.IncludeTests {
		includes = append(includes, "tests")
	}
	if opts.IncludeDocs {
		includes = append(includes, "docs")
	}
	if opts.IncludeOSBKnowledge {
		includes = append(includes, "osb-knowledge")
	}
	if len(includes) > 0 {
		arguments["include"] = includes
	}

	out, err := m.call("explore", arguments)
	if err != nil {
		return nil, fmt.Errorf("mcp explore: %w", err)
	}
	return &ExploreResult{
		Items: []EvidenceItem{{Content: out, Kind: "raw"}},
	}, nil
}

// Symbol queries via MCP.
func (m *MCPProvider) Symbol(name string) (string, error) {
	if !m.IsAvailable() {
		return "", &FullModeError{Code: ErrRagMonkMissing, Message: "RagMonk not found", Remedy: installInstructions()}
	}
	return m.call("symbol", map[string]interface{}{"name": name})
}

// Impact queries via MCP.
func (m *MCPProvider) Impact(target string) (string, error) {
	if !m.IsAvailable() {
		return "", &FullModeError{Code: ErrRagMonkMissing, Message: "RagMonk not found", Remedy: installInstructions()}
	}
	return m.call("impact", map[string]interface{}{"target": target})
}

// Close shuts down the MCP subprocess if it was started.
func (m *MCPProvider) Close() {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.started && m.cmd != nil {
		_ = m.stdin.Close()
		_ = m.cmd.Wait()
		m.started = false
	}
}
