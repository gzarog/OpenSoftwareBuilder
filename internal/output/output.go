package output

import (
	"fmt"
	"io"
	"os"
	"strings"
)

var (
	writer    io.Writer = os.Stdout
	errWriter io.Writer = os.Stderr
)

func SetWriter(w io.Writer) { writer = w }

func Print(msg string) {
	fmt.Fprint(writer, msg)
}

func Println(msg string) {
	fmt.Fprintln(writer, msg)
}

func Printf(format string, args ...interface{}) {
	fmt.Fprintf(writer, format, args...)
}

func Success(msg string) {
	fmt.Fprintf(writer, "  ✓ %s\n", msg)
}

func Warning(msg string) {
	fmt.Fprintf(writer, "  ! %s\n", msg)
}

func Error(msg string) {
	fmt.Fprintf(writer, "  ✗ %s\n", msg)
}

func Info(msg string) {
	fmt.Fprintf(writer, "  - %s\n", msg)
}

func Header(msg string) {
	fmt.Fprintf(writer, "\n%s\n", msg)
}

func SubHeader(msg string) {
	fmt.Fprintf(writer, "\n  %s\n", msg)
}

func Divider() {
	fmt.Fprintln(writer, strings.Repeat("─", 60))
}

func Table(rows [][]string) {
	if len(rows) == 0 {
		return
	}
	// Calculate column widths
	widths := make([]int, len(rows[0]))
	for _, row := range rows {
		for i, cell := range row {
			if i < len(widths) && len(cell) > widths[i] {
				widths[i] = len(cell)
			}
		}
	}
	for _, row := range rows {
		fmt.Fprint(writer, "  ")
		for i, cell := range row {
			if i < len(widths) {
				fmt.Fprintf(writer, "%-*s  ", widths[i], cell)
			}
		}
		fmt.Fprintln(writer)
	}
}

func Errorf(format string, args ...interface{}) {
	fmt.Fprintf(errWriter, format, args...)
}
