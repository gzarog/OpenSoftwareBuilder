package validation

import (
	"fmt"
	"os"
	"strings"
)

type Finding struct {
	Level   string // error, warning
	Message string
}

// ValidateSpec validates an architecture spec markdown file
func ValidateSpec(path string) ([]Finding, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	content := string(data)
	var findings []Finding

	required := []string{
		"## Interfaces",
		"## Acceptance criteria",
		"## Milestones",
		"## Tradeoffs",
		"## Risks",
	}
	for _, section := range required {
		if !strings.Contains(content, section) {
			findings = append(findings, Finding{
				Level:   "error",
				Message: fmt.Sprintf("missing required section: %s", section),
			})
		}
	}
	return findings, nil
}

// ValidateCheckpoint validates a checkpoint markdown file
func ValidateCheckpoint(path string) ([]Finding, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	content := string(data)
	var findings []Finding

	required := []string{
		"## Done and verified",
		"## Remaining",
	}
	for _, section := range required {
		if !strings.Contains(content, section) {
			findings = append(findings, Finding{
				Level:   "error",
				Message: fmt.Sprintf("missing required section: %s", section),
			})
		}
	}

	fields := []string{"Tier", "Role", "Milestone"}
	for _, f := range fields {
		if !strings.Contains(content, "| "+f+" |") && !strings.Contains(content, f+":") {
			findings = append(findings, Finding{
				Level:   "warning",
				Message: fmt.Sprintf("missing field: %s", f),
			})
		}
	}
	return findings, nil
}

// ValidateConfig validates osb.yaml structure
func ValidateConfig(path string) ([]Finding, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	content := string(data)
	var findings []Finding

	if !strings.Contains(content, "version:") {
		findings = append(findings, Finding{
			Level:   "error",
			Message: "missing required field: version",
		})
	}
	return findings, nil
}
