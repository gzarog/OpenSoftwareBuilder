package cli

import (
	"fmt"

	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
)

// printFullModeError prints a FullModeError with its error code, message, and
// remedy in a structured format. Returns true when err was a FullModeError.
func printFullModeError(err error) bool {
	fme, ok := err.(*intelligence.FullModeError)
	if !ok {
		return false
	}
	output.Error(fmt.Sprintf("[%s] %s", fme.Code, fme.Message))
	if fme.Remedy != "" {
		output.Println("")
		output.Println("  Remedy:")
		for _, line := range splitLines(fme.Remedy) {
			output.Printf("    %s\n", line)
		}
	}
	return true
}

func splitLines(s string) []string {
	var lines []string
	cur := ""
	for _, ch := range s {
		if ch == '\n' {
			lines = append(lines, cur)
			cur = ""
		} else {
			cur += string(ch)
		}
	}
	if cur != "" {
		lines = append(lines, cur)
	}
	return lines
}
