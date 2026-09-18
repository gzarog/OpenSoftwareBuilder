package unit

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/gzarog/opensoftwarebuilder/internal/validation"
)

func TestValidateSpec(t *testing.T) {
	dir := t.TempDir()

	// Valid spec
	validSpec := `# My Spec
## Interfaces
Some interfaces.
## Acceptance criteria
Some criteria.
## Milestones
Some milestones.
## Tradeoffs
Some tradeoffs.
## Risks
Some risks.
`
	path := filepath.Join(dir, "spec.md")
	os.WriteFile(path, []byte(validSpec), 0644)

	findings, err := validation.ValidateSpec(path)
	if err != nil {
		t.Fatalf("validation failed: %v", err)
	}
	if len(findings) != 0 {
		t.Errorf("expected no findings for valid spec, got %d", len(findings))
	}
}

func TestValidateSpecMissingSections(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "bad-spec.md")
	os.WriteFile(path, []byte("# My Spec\n## Interfaces\n"), 0644)

	findings, _ := validation.ValidateSpec(path)
	if len(findings) < 4 {
		t.Errorf("expected at least 4 findings for incomplete spec, got %d", len(findings))
	}
}

func TestValidateCheckpoint(t *testing.T) {
	dir := t.TempDir()
	valid := `# Checkpoint
| Field | Value |
| Tier | 2 |
| Role | implementer |
| Milestone | 1 |

## Done and verified
- Something done.

## Remaining
- Something remaining.
`
	path := filepath.Join(dir, "cp.md")
	os.WriteFile(path, []byte(valid), 0644)

	findings, err := validation.ValidateCheckpoint(path)
	if err != nil {
		t.Fatalf("validation failed: %v", err)
	}
	if len(findings) != 0 {
		t.Errorf("expected no findings, got %d", len(findings))
	}
}
