package unit

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/gzarog/opensoftwarebuilder/internal/artifact"
	"github.com/gzarog/opensoftwarebuilder/internal/knowledge"
)

func newTestManager(t *testing.T) (*artifact.Manager, string) {
	t.Helper()
	root := t.TempDir()
	mgr := artifact.NewManager(root, "specs", "reviews", "qa", "decisions")
	return mgr, root
}

func TestArtifactRecordCreatesFile(t *testing.T) {
	mgr, _ := newTestManager(t)
	for _, at := range []artifact.Type{artifact.TypeSpec, artifact.TypeReview, artifact.TypeQA, artifact.TypeDecision} {
		path, err := mgr.Record(at, "my-feature", artifact.RecordOptions{})
		if err != nil {
			t.Fatalf("Record(%s) failed: %v", at, err)
		}
		if _, err := os.Stat(path); err != nil {
			t.Errorf("expected file at %s, got: %v", path, err)
		}
	}
}

func TestArtifactRecordHasFrontMatter(t *testing.T) {
	mgr, _ := newTestManager(t)

	cases := []struct {
		atype    artifact.Type
		osbType  string
	}{
		{artifact.TypeSpec, "spec"},
		{artifact.TypeReview, "review"},
		{artifact.TypeQA, "qa"},
		{artifact.TypeDecision, "decision"},
	}

	for _, tc := range cases {
		path, err := mgr.Record(tc.atype, "auth-flow", artifact.RecordOptions{TaskID: "t-1", Component: "auth"})
		if err != nil {
			t.Fatalf("Record(%s): %v", tc.atype, err)
		}
		data, _ := os.ReadFile(path)
		content := string(data)

		if !strings.HasPrefix(content, "---\n") {
			t.Errorf("%s: expected YAML front matter", tc.atype)
		}
		if !strings.Contains(content, "osb_type: "+tc.osbType) {
			t.Errorf("%s: expected osb_type: %s", tc.atype, tc.osbType)
		}
		if !strings.Contains(content, "task_id: t-1") {
			t.Errorf("%s: expected task_id", tc.atype)
		}
		if !strings.Contains(content, "component: auth") {
			t.Errorf("%s: expected component", tc.atype)
		}
		if !strings.Contains(content, "status: draft") {
			t.Errorf("%s: expected status: draft", tc.atype)
		}
	}
}

func TestArtifactFilenameContainsName(t *testing.T) {
	mgr, _ := newTestManager(t)
	path, err := mgr.Record(artifact.TypeSpec, "my-spec", artifact.RecordOptions{})
	if err != nil {
		t.Fatalf("Record failed: %v", err)
	}
	base := filepath.Base(path)
	if !strings.HasSuffix(base, "-my-spec.md") {
		t.Errorf("expected filename ending in -my-spec.md, got %q", base)
	}
}

func TestArtifactUnknownTypeErrors(t *testing.T) {
	mgr, _ := newTestManager(t)
	_, err := mgr.Record("unknown", "foo", artifact.RecordOptions{})
	if err == nil {
		t.Error("expected error for unknown artifact type")
	}
}

func TestArtifactDirCreatedOnRecord(t *testing.T) {
	mgr, root := newTestManager(t)
	_, err := mgr.Record(artifact.TypeDecision, "use-postgres", artifact.RecordOptions{})
	if err != nil {
		t.Fatalf("Record failed: %v", err)
	}
	decisionsDir := filepath.Join(root, "decisions")
	if _, err := os.Stat(decisionsDir); err != nil {
		t.Errorf("expected decisions dir to be created: %v", err)
	}
}

func TestComponentRecordHasFrontMatter(t *testing.T) {
	dir := t.TempDir()
	mgr := knowledge.NewManager(dir, "knowledge")
	path, err := mgr.CreateComponentRecord("auth-service")
	if err != nil {
		t.Fatalf("CreateComponentRecord failed: %v", err)
	}
	data, _ := os.ReadFile(path)
	content := string(data)
	if !strings.HasPrefix(content, "---\n") {
		t.Error("expected YAML front matter")
	}
	if !strings.Contains(content, "osb_type: component") {
		t.Error("expected osb_type: component")
	}
	if !strings.Contains(content, "name: auth-service") {
		t.Error("expected name field")
	}
}
