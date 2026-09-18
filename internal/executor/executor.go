package executor

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"time"
)

type Result struct {
	ExitCode int
	Stdout   string
	Stderr   string
	Duration time.Duration
}

type Executor interface {
	Run(ctx context.Context, opts RunOptions) (*Result, error)
	Name() string
}

type RunOptions struct {
	Argv    []string
	Shell   string // legacy: run via shell
	Dir     string
	Env     map[string]string
	Stdout  io.Writer
	Stderr  io.Writer
	Timeout time.Duration
}

// LocalExecutor runs commands directly on the host
type LocalExecutor struct{}

func NewLocal() *LocalExecutor { return &LocalExecutor{} }

func (e *LocalExecutor) Name() string { return "local" }

func (e *LocalExecutor) Run(ctx context.Context, opts RunOptions) (*Result, error) {
	if opts.Timeout > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, opts.Timeout)
		defer cancel()
	}

	var cmd *exec.Cmd
	if len(opts.Argv) > 0 {
		cmd = exec.CommandContext(ctx, opts.Argv[0], opts.Argv[1:]...)
	} else if opts.Shell != "" {
		// Legacy shell string support
		if isWindows() {
			cmd = exec.CommandContext(ctx, "cmd", "/c", opts.Shell)
		} else {
			cmd = exec.CommandContext(ctx, "sh", "-c", opts.Shell)
		}
	} else {
		return nil, fmt.Errorf("no command specified")
	}

	if opts.Dir != "" {
		cmd.Dir = opts.Dir
	}

	cmd.Env = os.Environ()
	for k, v := range opts.Env {
		cmd.Env = append(cmd.Env, k+"="+v)
	}

	var stdoutBuf, stderrBuf bytes.Buffer
	if opts.Stdout != nil {
		cmd.Stdout = io.MultiWriter(opts.Stdout, &stdoutBuf)
	} else {
		cmd.Stdout = &stdoutBuf
	}
	if opts.Stderr != nil {
		cmd.Stderr = io.MultiWriter(opts.Stderr, &stderrBuf)
	} else {
		cmd.Stderr = &stderrBuf
	}

	start := time.Now()
	err := cmd.Run()
	duration := time.Since(start)

	result := &Result{
		Stdout:   stdoutBuf.String(),
		Stderr:   stderrBuf.String(),
		Duration: duration,
	}

	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			result.ExitCode = exitErr.ExitCode()
		} else {
			return result, err
		}
	}

	return result, nil
}

func isWindows() bool { return runtime.GOOS == "windows" }

// DockerExecutor runs commands inside a Docker container
type DockerExecutor struct {
	Image      string
	WorkDir    string
	MountPoint string
}

func NewDocker(image, workDir string) *DockerExecutor {
	return &DockerExecutor{
		Image:      image,
		WorkDir:    workDir,
		MountPoint: "/workspace",
	}
}

func (e *DockerExecutor) Name() string { return "docker" }

func (e *DockerExecutor) Run(ctx context.Context, opts RunOptions) (*Result, error) {
	args := []string{
		"run", "--rm",
		"-v", fmt.Sprintf("%s:%s", e.WorkDir, e.MountPoint),
		"-w", e.MountPoint,
	}
	for k, v := range opts.Env {
		args = append(args, "-e", k+"="+v)
	}
	args = append(args, e.Image)

	if len(opts.Argv) > 0 {
		args = append(args, opts.Argv...)
	} else if opts.Shell != "" {
		args = append(args, "sh", "-c", opts.Shell)
	}

	dockerOpts := RunOptions{
		Argv:    append([]string{"docker"}, args...),
		Dir:     opts.Dir,
		Stdout:  opts.Stdout,
		Stderr:  opts.Stderr,
		Timeout: opts.Timeout,
	}

	local := NewLocal()
	return local.Run(ctx, dockerOpts)
}

// DevcontainerExecutor runs commands using devcontainer CLI
type DevcontainerExecutor struct {
	WorkDir string
}

func NewDevcontainer(workDir string) *DevcontainerExecutor {
	return &DevcontainerExecutor{WorkDir: workDir}
}

func (e *DevcontainerExecutor) Name() string { return "devcontainer" }

func (e *DevcontainerExecutor) Run(ctx context.Context, opts RunOptions) (*Result, error) {
	args := []string{"exec", "--workspace-folder", e.WorkDir}

	var cmdStr string
	if len(opts.Argv) > 0 {
		cmdStr = strings.Join(opts.Argv, " ")
	} else {
		cmdStr = opts.Shell
	}
	args = append(args, cmdStr)

	devOpts := RunOptions{
		Argv:    append([]string{"devcontainer"}, args...),
		Dir:     opts.Dir,
		Stdout:  opts.Stdout,
		Stderr:  opts.Stderr,
		Timeout: opts.Timeout,
	}

	local := NewLocal()
	return local.Run(ctx, devOpts)
}

// NewExecutor creates the appropriate executor based on config
func NewExecutor(mode, image, workDir string) Executor {
	switch mode {
	case "docker":
		return NewDocker(image, workDir)
	case "devcontainer":
		return NewDevcontainer(workDir)
	default:
		return NewLocal()
	}
}
