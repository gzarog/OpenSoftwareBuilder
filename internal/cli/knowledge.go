package cli

import (
	"fmt"
	"os"
	"strings"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/event"
	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
	knowledgePkg "github.com/gzarog/opensoftwarebuilder/internal/knowledge"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var knowledgeCmd = &cobra.Command{
	Use:   "knowledge",
	Short: "Knowledge recording and status",
}

var knowledgeStatusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show knowledge directory status and intelligence health",
	RunE:  runKnowledgeStatus,
}

var knowledgeRecordCmd = &cobra.Command{
	Use:   "record <task|component> <name>",
	Short: "Create a durable knowledge record",
	Args:  cobra.ExactArgs(2),
	RunE:  runKnowledgeRecord,
}

var knowledgeCaptureCmd = &cobra.Command{
	Use:   "capture",
	Short: "Capture an incremental knowledge event for the active task",
	RunE:  runKnowledgeCapture,
}

var knowledgePendingCmd = &cobra.Command{
	Use:   "pending",
	Short: "Show pending (uncaptured) knowledge for active tasks",
	RunE:  runKnowledgePending,
}

var knowledgeInspectCmd = &cobra.Command{
	Use:   "inspect",
	Short: "Show all captured events for a task",
	RunE:  runKnowledgeInspect,
}

var knowledgeConsolidateCmd = &cobra.Command{
	Use:   "consolidate",
	Short: "Consolidate captured events into durable knowledge records",
	RunE:  runKnowledgeConsolidate,
}

// Flags shared across knowledge subcommands.
var (
	// record flags
	knowledgeComponents []string
	knowledgeStatus     string
	knowledgeTier       int
	knowledgeSummary    string
	knowledgeDecisions  string
	knowledgeLanguage   string
	knowledgePurpose    string

	// capture / inspect / consolidate flags
	captureTaskID     string
	captureRole       string
	captureType       string
	captureScope      string
	captureSummaryVal string
	captureReason     string
	captureConfidence string
	captureSupersedes string
	captureNone       bool
	captureNoneReason string
	captureFromJSON   string
	captureFiles      []string

	consolidateDryRun bool
)

func init() {
	// record flags
	knowledgeRecordCmd.Flags().StringSliceVar(&knowledgeComponents, "component", nil,
		"Components touched (for task records; can be repeated)")
	knowledgeRecordCmd.Flags().StringVar(&knowledgeStatus, "status", "",
		"Status: in-progress|shipped|abandoned (task) or active|deprecated (component)")
	knowledgeRecordCmd.Flags().IntVar(&knowledgeTier, "tier", 0, "Effort tier 1-5")
	knowledgeRecordCmd.Flags().StringVar(&knowledgeSummary, "summary", "", "One-line summary of what was done")
	knowledgeRecordCmd.Flags().StringVar(&knowledgeDecisions, "decisions", "", "Key decisions (inline)")
	knowledgeRecordCmd.Flags().StringVar(&captureTaskID, "task-id", "", "Task ID (for task and component records)")
	knowledgeRecordCmd.Flags().StringVar(&knowledgeLanguage, "language", "", "Primary language of this component")
	knowledgeRecordCmd.Flags().StringVar(&knowledgePurpose, "purpose", "", "Brief purpose statement for component records")

	// capture flags
	knowledgeCaptureCmd.Flags().StringVar(&captureTaskID, "task-id", "",
		"Task identifier (required, or set OSB_TASK_ID env var)")
	knowledgeCaptureCmd.Flags().StringVar(&captureRole, "role", "",
		"Workflow role: architect|implementer|reviewer|qa (required)")
	knowledgeCaptureCmd.Flags().StringVar(&captureType, "type", "",
		"Event type: decision|constraint|discovery|gotcha|assumption|assumption-invalidated|review-finding|qa-result|follow-up")
	knowledgeCaptureCmd.Flags().StringVar(&captureScope, "scope", "",
		"Scope: temporary|task|component|global|discard")
	knowledgeCaptureCmd.Flags().StringVar(&captureSummaryVal, "summary", "",
		"One-sentence description of the finding")
	knowledgeCaptureCmd.Flags().StringVar(&captureReason, "reason", "",
		"Why this finding matters")
	knowledgeCaptureCmd.Flags().StringVar(&captureConfidence, "confidence", "",
		"Confidence level: confirmed|suspected|unverified")
	knowledgeCaptureCmd.Flags().StringVar(&captureSupersedes, "supersedes", "",
		"Event ID that this finding invalidates")
	knowledgeCaptureCmd.Flags().BoolVar(&captureNone, "none", false,
		"Explicitly record that this role has no reusable findings (zero-knowledge checkpoint)")
	knowledgeCaptureCmd.Flags().StringVar(&captureNoneReason, "reason-none", "",
		"Explanation for why no findings were recorded (used with --none)")
	knowledgeCaptureCmd.Flags().StringVar(&captureFromJSON, "from-json", "",
		"Path to a JSON file containing a pre-built KnowledgeEvent to capture")
	knowledgeCaptureCmd.Flags().StringSliceVar(&captureFiles, "file", nil,
		"Source file(s) that led to this finding (can be repeated)")

	// pending flags
	knowledgePendingCmd.Flags().StringVar(&captureTaskID, "task-id", "",
		"Show summary for a specific task only")

	// inspect flags
	knowledgeInspectCmd.Flags().StringVar(&captureTaskID, "task-id", "",
		"Task ID to inspect (required, or set OSB_TASK_ID env var)")

	// consolidate flags
	knowledgeConsolidateCmd.Flags().StringVar(&captureTaskID, "task-id", "",
		"Task ID to consolidate (required, or set OSB_TASK_ID env var)")
	knowledgeConsolidateCmd.Flags().BoolVar(&consolidateDryRun, "dry-run", false,
		"Show what would be consolidated without writing any files")

	knowledgeCmd.AddCommand(knowledgeStatusCmd)
	knowledgeCmd.AddCommand(knowledgeRecordCmd)
	knowledgeCmd.AddCommand(knowledgeCaptureCmd)
	knowledgeCmd.AddCommand(knowledgePendingCmd)
	knowledgeCmd.AddCommand(knowledgeInspectCmd)
	knowledgeCmd.AddCommand(knowledgeConsolidateCmd)
}

// loadKnowledgeContext is the shared loader for all knowledge subcommands.
func loadKnowledgeContext() (*knowledgePkg.Manager, *config.Config, string, error) {
	cwd, _ := os.Getwd()
	root, err := config.FindRoot(cwd)
	if err != nil {
		return nil, nil, "", err
	}
	cfg, err := config.Load(root)
	if err != nil {
		return nil, nil, "", err
	}
	paths := cfg.GetPaths()
	return knowledgePkg.NewManager(root, paths.Knowledge), cfg, root, nil
}

// resolveTaskID returns the task ID from the flag, then the env variable.
func resolveTaskID(flag string) (string, error) {
	if flag != "" {
		return flag, nil
	}
	if v := os.Getenv("OSB_TASK_ID"); v != "" {
		return v, nil
	}
	return "", fmt.Errorf("task ID is required — pass --task-id or set OSB_TASK_ID")
}

// ─── status ──────────────────────────────────────────────────────────────────

func runKnowledgeStatus(cmd *cobra.Command, args []string) error {
	mgr, cfg, _, err := loadKnowledgeContext()
	if err != nil {
		return err
	}

	output.Header("Knowledge Status")
	output.Println(fmt.Sprintf("\n  %s", mgr.RecordStatus()))

	if cfg.IsFullMode() {
		provider := intelligence.NewProvider(cfg.GetIntelligence())
		if !provider.IsAvailable() {
			output.Error("Full mode requires RagMonk — not installed")
			output.Println("  Install: irm https://raw.githubusercontent.com/gzarog/RagMonk/main/install.ps1 | iex")
			output.Println("")
			return nil
		}
		status, err := provider.GetStatus()
		if err != nil {
			output.Warning(fmt.Sprintf("RagMonk status error: %s", err))
		} else {
			output.Println("\n  Intelligence:")
			if status.Version != "" {
				output.Info(fmt.Sprintf("  Provider:  RagMonk %s", status.Version))
			} else {
				output.Info("  Provider:  RagMonk")
			}
			if status.IndexAvailable {
				output.Success("  Index:     available")
			} else {
				output.Warning("  Index:     missing — run: ragmonk index")
			}
			if status.DaemonRunning {
				output.Success("  Daemon:    running")
			} else {
				output.Info("  Daemon:    not running")
			}
		}
	} else {
		if mgr.HasIndex() {
			rows, _ := mgr.IndexRows(10)
			if len(rows) > 0 {
				output.Println("\n  Recent entries:")
				for _, row := range rows {
					output.Printf("    %s\n", row)
				}
			}
		}
	}

	output.Println("")
	return nil
}

// ─── record ──────────────────────────────────────────────────────────────────

func runKnowledgeRecord(cmd *cobra.Command, args []string) error {
	kind := strings.ToLower(args[0])
	name := args[1]

	mgr, cfg, root, err := loadKnowledgeContext()
	if err != nil {
		return err
	}

	if err := mgr.EnsureDirs(); err != nil {
		return err
	}

	output.Header("Knowledge Recording")

	var path string
	switch kind {
	case "task":
		opts := knowledgePkg.TaskRecordOptions{
			Components: knowledgeComponents,
			Status:     knowledgeStatus,
			Tier:       knowledgeTier,
			Summary:    knowledgeSummary,
			Decisions:  knowledgeDecisions,
		}
		path, err = mgr.CreateTaskRecord(name, opts)
		if err != nil {
			return fmt.Errorf("creating task record: %w", err)
		}
		output.Success(fmt.Sprintf("Task record: %s", path))
		if len(knowledgeComponents) > 0 {
			output.Info(fmt.Sprintf("Components: %s", strings.Join(knowledgeComponents, ", ")))
		}

	case "component":
		opts := knowledgePkg.ComponentRecordOptions{
			TaskID:   captureTaskID,
			Status:   knowledgeStatus,
			Tier:     knowledgeTier,
			Language: knowledgeLanguage,
			Purpose:  knowledgePurpose,
		}
		path, err = mgr.CreateComponentRecord(name, opts)
		if err != nil {
			return fmt.Errorf("creating component record: %w", err)
		}
		output.Success(fmt.Sprintf("Component record: %s", path))

	default:
		return fmt.Errorf("unknown record type %q — must be: task or component", kind)
	}

	// In full mode, trigger incremental index so the new record is immediately retrievable.
	if cfg.IsFullMode() {
		provider := intelligence.NewProvider(cfg.GetIntelligence())
		if provider.IsAvailable() {
			output.Println("Indexing new record with RagMonk...")
			if idxErr := provider.Index(root); idxErr != nil {
				output.Warning(fmt.Sprintf("Index update failed: %s", idxErr))
				output.Println("  Run manually: ragmonk index")
			} else {
				output.Success("Knowledge index updated")
			}
		} else {
			output.Error("RagMonk not available — record created but not indexed")
			output.Error("Full mode requires RagMonk: install ragmonk and run: ragmonk source add . && ragmonk index")
		}
	}

	_ = path
	output.Println("")
	return nil
}

// ─── capture ─────────────────────────────────────────────────────────────────

func runKnowledgeCapture(cmd *cobra.Command, args []string) error {
	_, cfg, root, err := loadKnowledgeContext()
	if err != nil {
		return err
	}

	taskID, err := resolveTaskID(captureTaskID)
	if err != nil {
		return err
	}

	paths := cfg.GetPaths()
	store := event.NewStore(root, paths.Checkpoints, taskID)

	var ev *event.KnowledgeEvent

	if captureFromJSON != "" {
		// Load event from a JSON file.
		ev, err = store.AppendFromJSON(captureFromJSON)
		if err != nil {
			return err
		}
	} else {
		// Build event from flags.
		if captureRole == "" {
			return fmt.Errorf("--role is required")
		}

		e := &event.KnowledgeEvent{
			TaskID:     taskID,
			Role:       captureRole,
			Type:       captureType,
			Scope:      captureScope,
			Summary:    captureSummaryVal,
			Reason:     captureReason,
			Confidence: captureConfidence,
			Supersedes: captureSupersedes,
			None:       captureNone,
			NoneReason: captureNoneReason,
		}

		if len(captureFiles) > 0 {
			e.Source = &event.Source{Files: captureFiles}
		}

		if err := store.Append(e); err != nil {
			return err
		}
		ev = e
	}

	output.Header("Knowledge Captured")
	output.Success(fmt.Sprintf("ID:    %s", ev.ID))
	output.Info(fmt.Sprintf("  Role:  %s", ev.Role))
	if ev.None {
		output.Info(fmt.Sprintf("  Type:  none (explicit zero-knowledge checkpoint)"))
		if ev.NoneReason != "" {
			output.Info(fmt.Sprintf("  Why:   %s", ev.NoneReason))
		}
	} else {
		output.Info(fmt.Sprintf("  Type:  %s", ev.Type))
		output.Info(fmt.Sprintf("  Scope: %s", ev.Scope))
		output.Info(fmt.Sprintf("  %s", ev.Summary))
	}

	// Release 4: trigger RagMonk incremental index so later agents can retrieve this event.
	rmCfg := cfg.GetIntelligence().RagMonk
	if cfg.IsFullMode() && rmCfg != nil && rmCfg.ActiveTaskKnowledge && rmCfg.RefreshOnCheckpoint {
		provider := intelligence.NewProvider(cfg.GetIntelligence())
		if provider.IsAvailable() {
			if idxErr := provider.Index(root); idxErr != nil {
				output.Warning(fmt.Sprintf("RagMonk refresh failed: %s — run: ragmonk index", idxErr))
			}
		}
	}

	output.Println("")
	return nil
}

// ─── pending ─────────────────────────────────────────────────────────────────

func runKnowledgePending(cmd *cobra.Command, args []string) error {
	_, cfg, root, err := loadKnowledgeContext()
	if err != nil {
		return err
	}

	paths := cfg.GetPaths()

	var taskIDs []string
	if captureTaskID != "" {
		taskIDs = []string{captureTaskID}
	} else if v := os.Getenv("OSB_TASK_ID"); v != "" {
		taskIDs = []string{v}
	} else {
		taskIDs, err = event.ListTaskIDs(root, paths.Checkpoints)
		if err != nil {
			return err
		}
	}

	if len(taskIDs) == 0 {
		output.Println("No active task knowledge found.")
		output.Println("  Start capturing with: osb knowledge capture --task-id <id> --role <role> --type <type> --summary \"...\"")
		output.Println("")
		return nil
	}

	for _, tid := range taskIDs {
		store := event.NewStore(root, paths.Checkpoints, tid)
		summary := store.Summary()

		output.Header(fmt.Sprintf("Task: %s", tid))
		output.Println("")

		for _, role := range event.AllRoles {
			rs := summary[role]
			roleName := strings.ToUpper(role[:1]) + role[1:]
			output.Printf("  %s\n", roleName)
			if rs.HasNone {
				output.Printf("    no reusable findings")
				if rs.NoneReason != "" {
					output.Printf(" (%s)", rs.NoneReason)
				}
				output.Println("")
			} else if rs.Count == 0 {
				output.Println("    no checkpoint yet")
			} else {
				for t, n := range rs.ByType {
					output.Printf("    %d %s\n", n, pluralise(t, n))
				}
			}
			output.Println("")
		}
	}

	return nil
}

// ─── inspect ─────────────────────────────────────────────────────────────────

func runKnowledgeInspect(cmd *cobra.Command, args []string) error {
	_, cfg, root, err := loadKnowledgeContext()
	if err != nil {
		return err
	}

	taskID, err := resolveTaskID(captureTaskID)
	if err != nil {
		return err
	}

	paths := cfg.GetPaths()
	store := event.NewStore(root, paths.Checkpoints, taskID)

	output.Header(fmt.Sprintf("Knowledge — Task: %s", taskID))
	output.Println("")

	for _, role := range event.AllRoles {
		events, err := store.ReadRole(role)
		if err != nil {
			return err
		}
		roleName := strings.ToUpper(role[:1]) + role[1:]
		output.Printf("  ── %s ──\n", roleName)

		if len(events) == 0 {
			output.Println("    (no checkpoint yet)")
			output.Println("")
			continue
		}

		for _, e := range events {
			if e.None {
				output.Printf("    [none] %s\n", valueOrDefault(e.NoneReason, "no reusable findings"))
				continue
			}
			output.Printf("    [%s] %s", e.Type, e.Summary)
			if e.Scope != "" {
				output.Printf("  (scope=%s)", e.Scope)
			}
			if e.Confidence != "" {
				output.Printf("  confidence=%s", e.Confidence)
			}
			output.Println("")
			if e.Reason != "" {
				output.Printf("      reason: %s\n", e.Reason)
			}
			if e.Supersedes != "" {
				output.Printf("      supersedes: %s\n", e.Supersedes)
			}
			output.Printf("      id=%s\n", e.ID)
		}
		output.Println("")
	}

	return nil
}

// ─── consolidate ─────────────────────────────────────────────────────────────

func runKnowledgeConsolidate(cmd *cobra.Command, args []string) error {
	mgr, cfg, root, err := loadKnowledgeContext()
	if err != nil {
		return err
	}

	taskID, err := resolveTaskID(captureTaskID)
	if err != nil {
		return err
	}

	paths := cfg.GetPaths()

	if consolidateDryRun {
		output.Header(fmt.Sprintf("Consolidation dry-run — Task: %s", taskID))
	} else {
		output.Header(fmt.Sprintf("Consolidating knowledge — Task: %s", taskID))
	}

	result, err := mgr.Consolidate(knowledgePkg.ConsolidateOptions{
		TaskID:      taskID,
		ProgressDir: paths.Checkpoints,
		DryRun:      consolidateDryRun,
	})
	if err != nil {
		return err
	}

	output.Println("")
	output.Info(fmt.Sprintf("  Total events captured: %d", result.TotalEvents))
	output.Info(fmt.Sprintf("  Active (to promote):   %d", result.ActiveEvents))
	if result.Discarded > 0 {
		output.Info(fmt.Sprintf("  Discarded (scope=discard): %d", result.Discarded))
	}
	if result.Superseded > 0 {
		output.Info(fmt.Sprintf("  Superseded (invalidated):  %d", result.Superseded))
	}

	if consolidateDryRun {
		output.Println("")
		output.Info("  Dry-run — no files written.")
	} else {
		output.Println("")
		if result.TaskRecordPath != "" {
			output.Success(fmt.Sprintf("Task record:  %s", result.TaskRecordPath))
		} else {
			output.Info("  No events to consolidate — no task record written.")
		}
		for _, p := range result.ComponentPaths {
			output.Success(fmt.Sprintf("Component:    %s", p))
		}

		// In full mode, refresh the durable index after consolidation.
		if cfg.IsFullMode() {
			provider := intelligence.NewProvider(cfg.GetIntelligence())
			if provider.IsAvailable() {
				output.Println("\nRefreshing RagMonk durable index...")
				if idxErr := provider.Index(root); idxErr != nil {
					output.Warning(fmt.Sprintf("Index refresh failed: %s — run: ragmonk index", idxErr))
				} else {
					output.Success("Durable knowledge index updated")
				}
			}
		}
	}

	output.Println("")
	return nil
}

// ─── helpers ─────────────────────────────────────────────────────────────────

func pluralise(word string, count int) string {
	if count == 1 {
		return word
	}
	return word + "s"
}

func valueOrDefault(s, d string) string {
	if s != "" {
		return s
	}
	return d
}
