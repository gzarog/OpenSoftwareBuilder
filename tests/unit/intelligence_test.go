package unit

import (
	"errors"
	"testing"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
)

// --- FullModeError structure tests ---

func TestFullModeErrorImplementsError(t *testing.T) {
	err := &intelligence.FullModeError{
		Code:    intelligence.ErrRagMonkMissing,
		Message: "RagMonk not found",
		Remedy:  "install ragmonk",
	}
	var e error = err
	if e.Error() != "RagMonk not found" {
		t.Errorf("unexpected Error() output: %q", e.Error())
	}
}

func TestFullModeErrorCodes(t *testing.T) {
	codes := []string{
		intelligence.ErrRagMonkMissing,
		intelligence.ErrSourceNotRegistered,
		intelligence.ErrIndexMissing,
		intelligence.ErrIndexFailed,
		intelligence.ErrProviderUnhealthy,
	}
	for _, c := range codes {
		if c == "" {
			t.Errorf("expected non-empty error code constant")
		}
	}
}

func TestFullModeErrorAsTarget(t *testing.T) {
	err := &intelligence.FullModeError{
		Code:    intelligence.ErrIndexMissing,
		Message: "index missing",
		Remedy:  "run osb intelligence index",
	}
	var fme *intelligence.FullModeError
	if !errors.As(err, &fme) {
		t.Error("errors.As should unwrap FullModeError")
	}
	if fme.Code != intelligence.ErrIndexMissing {
		t.Errorf("expected code %s, got %s", intelligence.ErrIndexMissing, fme.Code)
	}
}

// --- Provider creation tests ---

func TestNewProviderReturnsCLIProvider(t *testing.T) {
	intel := &config.IntelligenceConfig{
		Provider: "ragmonk",
		RagMonk:  &config.RagMonkConfig{Transport: "cli"},
	}
	p := intelligence.NewProvider(intel)
	if p == nil {
		t.Fatal("expected non-nil provider for cli transport")
	}
}

func TestNewProviderReturnsMCPProvider(t *testing.T) {
	intel := &config.IntelligenceConfig{
		Provider: "ragmonk",
		RagMonk:  &config.RagMonkConfig{Transport: "mcp"},
	}
	p := intelligence.NewProvider(intel)
	if p == nil {
		t.Fatal("expected non-nil provider for mcp transport")
	}
}

func TestNewProviderNilRagMonkUsesDefaults(t *testing.T) {
	intel := &config.IntelligenceConfig{Provider: "ragmonk"}
	p := intelligence.NewProvider(intel)
	if p == nil {
		t.Fatal("expected non-nil provider when RagMonk config is nil")
	}
}

// --- Unavailable provider — no silent fallback ---

// providerWithFakePath creates a RagMonk provider whose executable is set to a
// name that will never exist on PATH, simulating "RagMonk not installed".
func providerWithFakePath() intelligence.Provider {
	intel := &config.IntelligenceConfig{
		Provider: "ragmonk",
		RagMonk: &config.RagMonkConfig{
			Executable: "__osb_test_ragmonk_does_not_exist__",
			Transport:  "cli",
		},
	}
	return intelligence.NewProvider(intel)
}

func TestIsAvailableFalseWhenMissing(t *testing.T) {
	p := providerWithFakePath()
	if p.IsAvailable() {
		t.Error("expected IsAvailable() false for missing executable")
	}
}

func TestIndexReturnsFullModeErrorWhenMissing(t *testing.T) {
	p := providerWithFakePath()
	err := p.Index("/tmp")
	if err == nil {
		t.Fatal("expected error from Index when provider missing")
	}
	var fme *intelligence.FullModeError
	if !errors.As(err, &fme) {
		t.Errorf("expected FullModeError, got %T: %v", err, err)
	}
	if fme.Code != intelligence.ErrRagMonkMissing {
		t.Errorf("expected code %s, got %s", intelligence.ErrRagMonkMissing, fme.Code)
	}
}

func TestExploreReturnsFullModeErrorWhenMissing(t *testing.T) {
	p := providerWithFakePath()
	_, err := p.Explore("anything", intelligence.ExploreOptions{})
	if err == nil {
		t.Fatal("expected error from Explore when provider missing")
	}
	var fme *intelligence.FullModeError
	if !errors.As(err, &fme) {
		t.Errorf("expected FullModeError, got %T: %v", err, err)
	}
}

func TestSymbolReturnsFullModeErrorWhenMissing(t *testing.T) {
	p := providerWithFakePath()
	_, err := p.Symbol("SomeFunc")
	if err == nil {
		t.Fatal("expected error from Symbol when provider missing")
	}
	var fme *intelligence.FullModeError
	if !errors.As(err, &fme) {
		t.Errorf("expected FullModeError, got %T: %v", err, err)
	}
}

func TestImpactReturnsFullModeErrorWhenMissing(t *testing.T) {
	p := providerWithFakePath()
	_, err := p.Impact("internal/auth/auth.go")
	if err == nil {
		t.Fatal("expected error from Impact when provider missing")
	}
	var fme *intelligence.FullModeError
	if !errors.As(err, &fme) {
		t.Errorf("expected FullModeError, got %T: %v", err, err)
	}
}

func TestRegisterSourceReturnsFullModeErrorWhenMissing(t *testing.T) {
	p := providerWithFakePath()
	err := p.RegisterSource("/tmp/project")
	if err == nil {
		t.Fatal("expected error from RegisterSource when provider missing")
	}
	var fme *intelligence.FullModeError
	if !errors.As(err, &fme) {
		t.Errorf("expected FullModeError, got %T: %v", err, err)
	}
}

func TestBuildTaskContextReturnsFullModeErrorWhenMissing(t *testing.T) {
	p := providerWithFakePath()
	_, err := intelligence.BuildTaskContext(p, "implement auth", intelligence.RoleImplementer, intelligence.ContextOptions{})
	if err == nil {
		t.Fatal("expected error from BuildTaskContext when provider missing")
	}
	var fme *intelligence.FullModeError
	if !errors.As(err, &fme) {
		t.Errorf("expected FullModeError, got %T: %v", err, err)
	}
	if fme.Code != intelligence.ErrRagMonkMissing {
		t.Errorf("expected code %s, got %s", intelligence.ErrRagMonkMissing, fme.Code)
	}
}

// --- No result returned alongside FullModeError (no silent fallback) ---

func TestExploreReturnsNilResultOnError(t *testing.T) {
	p := providerWithFakePath()
	result, err := p.Explore("anything", intelligence.ExploreOptions{})
	if err == nil {
		t.Fatal("expected error")
	}
	if result != nil {
		t.Error("expected nil result alongside FullModeError — no silent fallback")
	}
}

func TestSymbolReturnsEmptyOnError(t *testing.T) {
	p := providerWithFakePath()
	sym, err := p.Symbol("SomeFunc")
	if err == nil {
		t.Fatal("expected error")
	}
	if sym != "" {
		t.Errorf("expected empty string alongside error — no fallback data, got %q", sym)
	}
}

func TestImpactReturnsEmptyOnError(t *testing.T) {
	p := providerWithFakePath()
	impact, err := p.Impact("file.go")
	if err == nil {
		t.Fatal("expected error")
	}
	if impact != "" {
		t.Errorf("expected empty string alongside error — no fallback data, got %q", impact)
	}
}

// --- DaemonStarter interface ---

func TestDaemonStarterInterface(t *testing.T) {
	p := providerWithFakePath()
	// StartDaemon must be a no-op (not panic) when the executable is missing.
	if ds, ok := p.(intelligence.DaemonStarter); ok {
		defer func() {
			if r := recover(); r != nil {
				t.Errorf("StartDaemon panicked: %v", r)
			}
		}()
		ds.StartDaemon()
	}
	// If the provider does not implement DaemonStarter that is also acceptable.
}

// --- Status snapshot ---

func TestGetStatusWhenMissingReturnsAvailableFalse(t *testing.T) {
	p := providerWithFakePath()
	status, err := p.GetStatus()
	if err != nil {
		// Some providers return an error; either is acceptable.
		return
	}
	if status == nil {
		t.Fatal("expected non-nil status")
	}
	if status.Available {
		t.Error("expected Available=false when executable is missing")
	}
}
