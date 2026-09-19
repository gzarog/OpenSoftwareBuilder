package knowledge

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/gzarog/opensoftwarebuilder/internal/event"
)

// ConsolidateOptions controls how captured events are consolidated into durable records.
type ConsolidateOptions struct {
	TaskID      string
	ProgressDir string // e.g. ".osb/progress"
	DryRun      bool
}

// ConsolidateResult describes the outcome of a consolidation run.
type ConsolidateResult struct {
	TaskRecordPath string
	ComponentPaths []string
	TotalEvents    int
	ActiveEvents   int
	Discarded      int
	Superseded     int
	DryRun         bool
}

// Consolidate reads all captured events for a task, filters them, and produces
// durable knowledge records in .osb/knowledge/tasks/ and .osb/knowledge/components/.
func (m *Manager) Consolidate(opts ConsolidateOptions) (*ConsolidateResult, error) {
	if opts.TaskID == "" {
		return nil, fmt.Errorf("task_id is required for consolidation")
	}

	store := event.NewStore(m.root, opts.ProgressDir, opts.TaskID)

	all, err := store.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("reading events: %w", err)
	}

	result := &ConsolidateResult{
		TotalEvents: len(all),
		DryRun:      opts.DryRun,
	}

	if len(all) == 0 {
		return result, nil
	}

	// Build set of superseded event IDs.
	supersededIDs := map[string]bool{}
	for _, e := range all {
		if e.Supersedes != "" {
			supersededIDs[e.Supersedes] = true
		}
	}

	// Classify each event.
	var active []*event.KnowledgeEvent
	for _, e := range all {
		if e.None {
			continue
		}
		if e.Scope == "discard" {
			result.Discarded++
			continue
		}
		if supersededIDs[e.ID] {
			result.Superseded++
			continue
		}
		active = append(active, e)
	}
	result.ActiveEvents = len(active)

	if opts.DryRun {
		return result, nil
	}

	if err := m.EnsureDirs(); err != nil {
		return nil, err
	}

	taskPath, err := m.createConsolidatedTaskRecord(opts.TaskID, all, active)
	if err != nil {
		return nil, fmt.Errorf("creating task record: %w", err)
	}
	result.TaskRecordPath = taskPath

	compPaths, err := m.updateComponentRecords(opts.TaskID, active)
	if err != nil {
		return nil, fmt.Errorf("updating component records: %w", err)
	}
	result.ComponentPaths = compPaths

	return result, nil
}

func (m *Manager) createConsolidatedTaskRecord(taskID string, all, active []*event.KnowledgeEvent) (string, error) {
	byType := groupEventsByType(active)
	byRole := groupEventsByRole(all)

	date := time.Now().Format("2006-01-02")

	var sb strings.Builder

	// YAML front matter
	fmt.Fprintf(&sb, "---\nosb_type: task\ntask_id: %s\nstatus: shipped\ndate: %s\nsource: consolidated\nevents: %d\n---\n",
		taskID, date, len(active))

	fmt.Fprintf(&sb, "\n# %s\n\n", taskID)
	fmt.Fprintf(&sb, "| Field | Value |\n|---|---|\n")
	fmt.Fprintf(&sb, "| Date | %s |\n", date)
	fmt.Fprintf(&sb, "| Status | shipped |\n")
	fmt.Fprintf(&sb, "| Active events | %d of %d total |\n\n", len(active), len(all))

	sb.WriteString("## What & why\n\n")
	for _, e := range byRole["architect"] {
		if e.Type == "decision" || e.Type == "constraint" {
			fmt.Fprintf(&sb, "- %s\n", e.Summary)
		}
	}
	sb.WriteString("\n")

	sb.WriteString("## Decisions\n\n")
	for _, e := range byType["decision"] {
		fmt.Fprintf(&sb, "- **[%s]** %s", e.Role, e.Summary)
		if e.Reason != "" {
			fmt.Fprintf(&sb, " — %s", e.Reason)
		}
		sb.WriteString("\n")
	}
	sb.WriteString("\n")

	sb.WriteString("## Gotchas\n\n")
	for _, e := range byType["gotcha"] {
		fmt.Fprintf(&sb, "- **[%s]** %s\n", e.Role, e.Summary)
	}
	for _, e := range byType["constraint"] {
		fmt.Fprintf(&sb, "- **[constraint/%s]** %s\n", e.Role, e.Summary)
	}
	sb.WriteString("\n")

	sb.WriteString("## Discoveries\n\n")
	for _, e := range byType["discovery"] {
		fmt.Fprintf(&sb, "- **[%s]** %s\n", e.Role, e.Summary)
	}
	for _, e := range byType["review-finding"] {
		fmt.Fprintf(&sb, "- **[reviewer]** %s\n", e.Summary)
	}
	for _, e := range byType["assumption"] {
		fmt.Fprintf(&sb, "- **[assumption/%s]** %s\n", e.Role, e.Summary)
	}
	for _, e := range byType["assumption-invalidated"] {
		fmt.Fprintf(&sb, "- **[invalidated/%s]** %s\n", e.Role, e.Summary)
	}
	sb.WriteString("\n")

	sb.WriteString("## QA result\n\n")
	for _, e := range byType["qa-result"] {
		fmt.Fprintf(&sb, "- %s\n", e.Summary)
	}
	sb.WriteString("\n")

	sb.WriteString("## Follow-ups\n\n")
	for _, e := range byType["follow-up"] {
		fmt.Fprintf(&sb, "- %s\n", e.Summary)
	}
	sb.WriteString("\n")

	// Superseded assumptions section (historical evidence).
	var superseded []*event.KnowledgeEvent
	for _, e := range all {
		if e.Type == "assumption" {
			for _, other := range all {
				if other.Supersedes == e.ID {
					superseded = append(superseded, e)
					break
				}
			}
		}
	}
	if len(superseded) > 0 {
		sb.WriteString("## Superseded assumptions\n\n")
		sb.WriteString("*These were captured during the task but later invalidated — kept for historical context only.*\n\n")
		for _, e := range superseded {
			fmt.Fprintf(&sb, "- ~~%s~~ (id=%s)\n", e.Summary, e.ID)
		}
		sb.WriteString("\n")
	}

	filename := fmt.Sprintf("%s-%s.md", date, sanitizeFilename(taskID))
	path := filepath.Join(m.dir, "tasks", filename)
	return path, os.WriteFile(path, []byte(sb.String()), 0644)
}

func (m *Manager) updateComponentRecords(taskID string, active []*event.KnowledgeEvent) ([]string, error) {
	// Group component-scoped events by inferred component name (from source files).
	byComponent := map[string][]*event.KnowledgeEvent{}
	for _, e := range active {
		if e.Scope != "component" || e.Source == nil {
			continue
		}
		for _, f := range e.Source.Files {
			comp := inferComponent(f)
			if comp != "" {
				byComponent[comp] = append(byComponent[comp], e)
			}
		}
	}

	var paths []string
	for comp, evts := range byComponent {
		path, err := m.appendComponentKnowledge(comp, taskID, evts)
		if err != nil {
			return paths, err
		}
		if path != "" {
			paths = append(paths, path)
		}
	}
	return paths, nil
}

func (m *Manager) appendComponentKnowledge(name, taskID string, events []*event.KnowledgeEvent) (string, error) {
	compDir := filepath.Join(m.dir, "components")
	entries, _ := os.ReadDir(compDir)

	var target string
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(e.Name(), "-"+name+".md") {
			target = filepath.Join(compDir, e.Name())
			break
		}
	}

	if target == "" {
		// Create a stub component record.
		p, err := m.CreateComponentRecord(name, ComponentRecordOptions{
			TaskID: taskID,
			Status: "active",
		})
		if err != nil {
			return "", err
		}
		target = p
	}

	existing, err := os.ReadFile(target)
	if err != nil {
		return "", err
	}

	var additions strings.Builder
	fmt.Fprintf(&additions, "\n### From task %s (%s)\n\n", taskID, time.Now().Format("2006-01-02"))
	for _, e := range events {
		fmt.Fprintf(&additions, "- **[%s/%s]** %s\n", e.Role, e.Type, e.Summary)
	}

	content := string(existing)
	const notesMarker = "## Notes"
	notesIdx := strings.LastIndex(content, notesMarker)
	if notesIdx >= 0 {
		insertAt := notesIdx + len(notesMarker)
		content = content[:insertAt] + "\n" + additions.String() + content[insertAt:]
	} else {
		content += additions.String()
	}

	return target, os.WriteFile(target, []byte(content), 0644)
}

func groupEventsByType(events []*event.KnowledgeEvent) map[string][]*event.KnowledgeEvent {
	m := make(map[string][]*event.KnowledgeEvent)
	for _, e := range events {
		m[e.Type] = append(m[e.Type], e)
	}
	return m
}

func groupEventsByRole(events []*event.KnowledgeEvent) map[string][]*event.KnowledgeEvent {
	m := make(map[string][]*event.KnowledgeEvent)
	for _, e := range events {
		m[e.Role] = append(m[e.Role], e)
	}
	return m
}

func sanitizeFilename(s string) string {
	var b strings.Builder
	for _, r := range strings.ToLower(s) {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '-' {
			b.WriteRune(r)
		} else {
			b.WriteRune('-')
		}
	}
	return strings.Trim(b.String(), "-")
}

func inferComponent(filePath string) string {
	parts := strings.Split(filepath.ToSlash(filePath), "/")
	if len(parts) >= 2 {
		return parts[len(parts)-2]
	}
	return ""
}
