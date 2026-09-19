package cli

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/gzarog/opensoftwarebuilder/internal/config"
	"github.com/gzarog/opensoftwarebuilder/internal/event"
	"github.com/gzarog/opensoftwarebuilder/internal/filesystem"
	"github.com/gzarog/opensoftwarebuilder/internal/gates"
	"github.com/gzarog/opensoftwarebuilder/internal/intelligence"
	"github.com/gzarog/opensoftwarebuilder/internal/output"
	"github.com/spf13/cobra"
)

var gateCmd = &cobra.Command{
	Use:   "gate <review|knowledge|intelligence> <inspect|approve|skip> [reason]",
	Short: "Manage quality gates",
	Args:  cobra.MinimumNArgs(2),
	RunE:  runGate,
}

var gateTaskID string

func init() {
	gateCmd.Flags().StringVar(&gateTaskID, "task-id", "",
		"Task ID for role-aware knowledge gate inspection (or set OSB_TASK_ID)")
}

func runGate(cmd *cobra.Command, args []string) error {
	gateName := args[0]
	action := args[1]

	// Phase 15: intelligence gate is provider-based, not mtime-based.
	if gateName == "intelligence" {
		return runIntelligenceGate(action)
	}

	if gateName != "review" && gateName != "knowledge" {
		return fmt.Errorf("unknown gate: %s (expected: review, knowledge, intelligence)", gateName)
	}

	cwd, _ := os.Getwd()
	root, err := config.FindRoot(cwd)
	if err != nil {
		return err
	}
	cfg, err := config.Load(root)
	if err != nil {
		return err
	}

	paths := cfg.GetPaths()
	gm := gates.NewManager(root, paths.State)

	var sourceDirs []string
	for _, src := range paths.Source {
		fullPath := filepath.Join(root, src)
		if filesystem.DirExists(fullPath) {
			sourceDirs = append(sourceDirs, fullPath)
		}
	}
	latestMtime, _ := filesystem.LatestMtime(sourceDirs, paths.Generated)

	switch action {
	case "inspect":
		if gateName == "knowledge" {
			return runKnowledgeGateInspect(root, cfg, gm, latestMtime)
		}
		gate, err := gm.Inspect(gateName, latestMtime)
		if err != nil {
			return err
		}
		output.Header(fmt.Sprintf("Gate: %s", gateName))
		output.Printf("  State: %s\n", formatGateState(gate))
		if gate.SkipReason != "" {
			output.Printf("  Reason: %s\n", gate.SkipReason)
		}
	case "approve":
		if gateName == "knowledge" {
			return fmt.Errorf("knowledge gate cannot be directly approved — it is derived from knowledge mtime or role checkpoints")
		}
		if err := gm.Approve(gateName); err != nil {
			return err
		}
		output.Success(fmt.Sprintf("%s gate approved", gateName))
	case "skip":
		reason := "no reason provided"
		if len(args) > 2 {
			reason = strings.Join(args[2:], " ")
		}
		if err := gm.Skip(gateName, reason); err != nil {
			return err
		}
		output.Success(fmt.Sprintf("%s gate skipped: %s", gateName, reason))
	default:
		return fmt.Errorf("unknown action: %s (expected: inspect, approve, skip)", action)
	}

	output.Println("")
	return nil
}

// runIntelligenceGate handles the intelligence gate: it queries the provider
// directly rather than using mtime-based state files.
func runIntelligenceGate(action string) error {
	if action != "inspect" {
		return fmt.Errorf("intelligence gate only supports 'inspect' — health is derived from RagMonk state, not manually approved")
	}

	cwd, _ := os.Getwd()
	root, err := config.FindRoot(cwd)
	if err != nil {
		return fmt.Errorf("osb.yaml not found — run osb init")
	}
	cfg, err := config.Load(root)
	if err != nil {
		return err
	}
	if !cfg.IsFullMode() {
		output.Info("Intelligence gate: N/A (light mode)")
		output.Println("")
		return nil
	}

	output.Header("Gate: intelligence")
	provider := intelligence.NewProvider(cfg.GetIntelligence())

	healthy := true

	if !provider.IsAvailable() {
		output.Error("  RagMonk:  NOT FOUND")
		output.Println("  Remedy:   install ragmonk and run: ragmonk init && ragmonk source add . && ragmonk index")
		healthy = false
	} else {
		output.Success("  RagMonk:  available")

		registered, _ := provider.IsSourceRegistered(root)
		if registered {
			output.Success("  Source:   registered")
		} else {
			output.Error("  Source:   NOT REGISTERED — run: ragmonk source add .")
			healthy = false
		}

		status, err := provider.GetStatus()
		if err != nil {
			output.Error(fmt.Sprintf("  Status:   error — %s", err))
			healthy = false
		} else {
			if status.IndexAvailable {
				output.Success("  Index:    available")
			} else {
				output.Error("  Index:    MISSING — run: osb intelligence index")
				healthy = false
			}
			if status.DaemonRunning {
				output.Success("  Daemon:   running")
			} else {
				output.Info("  Daemon:   not running (ragmonk daemon start)")
			}
		}
	}

	output.Println("")
	if healthy {
		output.Success("Intelligence gate: PASS")
	} else {
		output.Error("Intelligence gate: FAIL — resolve issues above before running full-mode workflows")
	}
	output.Println("")
	return nil
}

// runKnowledgeGateInspect shows a role-aware knowledge gate status. When a task
// ID is provided (via --task-id or OSB_TASK_ID), it checks that each required
// role has completed its knowledge checkpoint. Without a task ID it falls back
// to the legacy mtime-based gate.
func runKnowledgeGateInspect(root string, cfg *config.Config, gm *gates.Manager, latestMtime float64) error {
	// Resolve optional task ID.
	taskID := gateTaskID
	if taskID == "" {
		taskID = os.Getenv("OSB_TASK_ID")
	}

	output.Header("Gate: knowledge")
	output.Println("")

	if taskID == "" {
		// Legacy mode: mtime-based gate only.
		gate, err := gm.Inspect("knowledge", latestMtime)
		if err != nil {
			return err
		}
		output.Printf("  State: %s\n", formatGateState(gate))
		if gate.SkipReason != "" {
			output.Printf("  Reason: %s\n", gate.SkipReason)
		}
		output.Println("")
		output.Info("  Tip: pass --task-id <id> for role-aware checkpoint verification.")
		output.Println("")
		return nil
	}

	paths := cfg.GetPaths()
	store := event.NewStore(root, paths.Checkpoints, taskID)
	summary := store.Summary()

	output.Printf("  Task: %s\n\n", taskID)

	policy := cfg.GetPolicy()
	blocked := false

	// Check each role.
	for _, role := range event.AllRoles {
		rs := summary[role]
		roleName := strings.ToUpper(role[:1]) + role[1:]

		// Determine whether this role is required.
		required := isRoleRequired(role, policy)

		if !required {
			output.Printf("  %s\n    (not required by policy)\n\n", roleName)
			continue
		}

		if rs.HasCheckpoint() {
			if rs.HasNone {
				output.Printf("  ✓ %s\n    no reusable findings", roleName)
				if rs.NoneReason != "" {
					output.Printf(" — %s", rs.NoneReason)
				}
				output.Println("")
			} else {
				output.Printf("  ✓ %s\n", roleName)
				for t, n := range rs.ByType {
					output.Printf("    %d %s\n", n, t)
				}
			}
		} else {
			output.Printf("  ✗ %s\n    checkpoint missing\n", roleName)
			blocked = true
		}
		output.Println("")
	}

	// Check durable consolidation: task record exists in .osb/knowledge/tasks/.
	taskRecordExists := knowledgeTaskRecordExists(root, paths.Knowledge, taskID)
	if taskRecordExists {
		output.Success("Consolidation: complete")
	} else {
		output.Error("Consolidation: pending — run: osb knowledge consolidate --task-id " + taskID)
		blocked = true
	}

	output.Println("")
	if blocked {
		output.Error("Knowledge gate: BLOCKED")
	} else {
		output.Success("Knowledge gate: PASS")
	}
	output.Println("")
	return nil
}

// isRoleRequired returns whether the role must complete a knowledge checkpoint.
// Architect is always required; reviewer and QA follow the policy config.
func isRoleRequired(role string, policy *config.PolicyConfig) bool {
	switch role {
	case "architect":
		return true
	case "implementer":
		return true
	case "reviewer":
		return policy == nil || policy.RequireIndependentReview
	case "qa":
		return policy == nil || policy.RequireFreshQA
	}
	return false
}

// knowledgeTaskRecordExists reports whether a consolidated task record has been
// written to .osb/knowledge/tasks/ for the given task ID.
func knowledgeTaskRecordExists(root, knowledgeDir, taskID string) bool {
	tasksDir := filepath.Join(root, knowledgeDir, "tasks")
	entries, err := os.ReadDir(tasksDir)
	if err != nil {
		return false
	}
	slug := strings.ToLower(taskID)
	for _, e := range entries {
		if strings.Contains(strings.ToLower(e.Name()), slug) {
			return true
		}
	}
	return false
}
