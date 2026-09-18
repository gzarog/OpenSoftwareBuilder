package intelligence

import "github.com/gzarog/opensoftwarebuilder/internal/config"

// NewProvider returns the appropriate Provider implementation based on the
// configured transport. When transport is "mcp" (or when the RagMonk config
// requests it), an MCPProvider is returned so that retrieval calls reuse a
// warm subprocess. All other values fall back to the CLI transport.
func NewProvider(intel *config.IntelligenceConfig) Provider {
	cfg := intel.RagMonk
	if cfg == nil {
		cfg = config.DefaultRagMonkConfig()
	}
	if cfg.Transport == "mcp" {
		return NewMCPProvider(intel)
	}
	return NewRagMonkProvider(intel)
}
