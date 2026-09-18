package platform

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
)

type Platform struct {
	os   string
	arch string
}

func New() *Platform {
	return &Platform{os: runtime.GOOS, arch: runtime.GOARCH}
}

func (p *Platform) OS() string   { return p.os }
func (p *Platform) Arch() string { return p.arch }

func (p *Platform) FindExecutable(name string) (string, error) {
	return exec.LookPath(name)
}

func (p *Platform) UserHome() string {
	home, _ := os.UserHomeDir()
	return home
}

func (p *Platform) TempDir() string {
	return os.TempDir()
}

func (p *Platform) NormalizePath(path string) string {
	return filepath.Clean(path)
}

func (p *Platform) IsWindows() bool { return p.os == "windows" }
func (p *Platform) IsLinux() bool   { return p.os == "linux" }
func (p *Platform) IsDarwin() bool  { return p.os == "darwin" }
