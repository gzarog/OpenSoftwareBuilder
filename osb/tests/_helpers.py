"""Shared test helpers: build an isolated fake workspace with a copy of the real osb/
package, so package/discovery tests never touch the actual repository."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REAL_OSB_DIR = REPO_ROOT / "osb"


def make_fake_workspace(dest: Path, *, existing_files: dict[str, str] | None = None) -> Path:
    """Copy the real osb/ package into dest/osb, returning dest (the fake workspace root).

    A freshly copied osb/ package must behave like a never-installed release, not like
    this dogfooding repo's own already-registered workspace — so any hosts_registered /
    generated_files this repo's checked-in manifest.json carries are stripped, leaving
    only package_version and the package's own source-file hashes.

    existing_files: optional {relative_path: content} to pre-create in the workspace,
    e.g. to simulate an "existing single-repo project" fixture with its own osb.yaml.
    """

    dest.mkdir(parents=True, exist_ok=True)
    target_osb = dest / "osb"
    shutil.copytree(
        REAL_OSB_DIR,
        target_osb,
        ignore=shutil.ignore_patterns("__pycache__", ".backup", "tests"),
    )

    manifest_path = target_osb / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["hosts_registered"] = []
        manifest["generated_files"] = {}
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for rel, content in (existing_files or {}).items():
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return dest


def run_install(workspace: Path, *args: str) -> subprocess.CompletedProcess:
    script = workspace / "osb" / "scripts" / "install.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
