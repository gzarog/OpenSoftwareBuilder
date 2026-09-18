package intelligence

// Provider is the intelligence interface OSB uses. All project knowledge
// discovery in full mode must go through an implementation of this interface.
type Provider interface {
	// IsAvailable returns true if the provider binary/service can be found.
	IsAvailable() bool

	// GetStatus returns the current health snapshot.
	GetStatus() (*Status, error)

	// IsSourceRegistered checks whether the repository root is registered.
	IsSourceRegistered(root string) (bool, error)

	// RegisterSource registers the repository root with the provider.
	RegisterSource(root string) error

	// IsIndexed checks whether a knowledge index exists and is available.
	IsIndexed() (bool, error)

	// Index triggers a full or incremental index of the registered source.
	Index(root string) error

	// EnsureFreshIndex checks whether the index is current and triggers an
	// incremental index when the source is dirty. No-op when already fresh.
	EnsureFreshIndex(root string) error

	// Explore runs a free-text knowledge retrieval query.
	Explore(query string, opts ExploreOptions) (*ExploreResult, error)

	// Symbol resolves a named symbol (function, type, variable) and returns
	// its definition context from the intelligence provider.
	Symbol(name string) (string, error)

	// Impact returns the set of callers and dependents for a given file or symbol.
	Impact(target string) (string, error)
}

// Status is a health snapshot of the intelligence provider.
type Status struct {
	Available        bool
	Version          string
	Healthy          bool
	SourceRegistered bool
	IndexAvailable   bool
	IndexHealthy     bool
	DaemonRunning    bool
}

// ExploreOptions controls what the retrieval query returns.
type ExploreOptions struct {
	MaxResults          int
	IncludeCode         bool
	IncludeTests        bool
	IncludeDocs         bool
	IncludeOSBKnowledge bool
	// OsbTypes filters results to specific osb_type values (e.g. task, component, architecture).
	OsbTypes []string
	// Components filters results to specific component names.
	Components []string
}

// ExploreResult holds the evidence package returned by a retrieval query.
type ExploreResult struct {
	Items []EvidenceItem
}

// EvidenceItem is a single piece of evidence from the intelligence provider.
type EvidenceItem struct {
	File    string
	Content string
	Score   float64
	Kind    string // code, test, doc, task, component
}

// DaemonStarter is an optional capability a Provider may expose to start
// the intelligence daemon in the background when auto_watch is configured.
type DaemonStarter interface {
	StartDaemon()
}

// FullModeError is returned when full mode requirements are not met.
type FullModeError struct {
	Code    string
	Message string
	Remedy  string
}

func (e *FullModeError) Error() string { return e.Message }

const (
	ErrRagMonkMissing         = "FULL_MODE_RAGMONK_MISSING"
	ErrSourceNotRegistered    = "FULL_MODE_SOURCE_NOT_REGISTERED"
	ErrIndexMissing           = "FULL_MODE_INDEX_MISSING"
	ErrIndexFailed            = "FULL_MODE_INDEX_FAILED"
	ErrProviderUnhealthy      = "FULL_MODE_PROVIDER_UNHEALTHY"
)
