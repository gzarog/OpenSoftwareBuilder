#!/usr/bin/env python3
"""OSB installer: init / doctor / upgrade for the portable osb/ package.

This is deterministic, one-shot registration tooling — never a daemon, never a model
runtime. It resolves the workspace root from its own location, generates only the
host-native discovery/agent files the workspace asks for, and never touches root
`osb.yaml`, `.osb/state/`, or `.osb/knowledge/` once they exist (see `cmd_init`).

Invoked by ../install.sh and ../install.ps1 — those are thin cross-platform launchers;
all logic lives here so it runs identically on Windows PowerShell, Linux/macOS, and WSL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_hosts  # noqa: E402
import host_preflight  # noqa: E402
import yaml_lite  # noqa: E402
import workspace_validate  # noqa: E402

PACKAGE_VERSION = "2.1.0"
ALL_HOSTS = ("claude", "codex", "copilot")

SCRIPT_PATH = Path(__file__).resolve()
OSB_DIR = SCRIPT_PATH.parent.parent
WORKSPACE_ROOT = OSB_DIR.parent

MANIFEST_PATH = OSB_DIR / "manifest.json"

GENERATED_PATHS_BY_HOST = {
    "claude": [".claude/skills/osb/SKILL.md", ".claude/agents/architect.md",
               ".claude/agents/implementer.md", ".claude/agents/reviewer.md", ".claude/agents/qa.md"],
    "codex": [".agents/skills/osb/SKILL.md", ".codex/agents/architect.toml",
              ".codex/agents/implementer.toml", ".codex/agents/reviewer.toml", ".codex/agents/qa.toml"],
    "copilot": [".agents/skills/osb/SKILL.md", ".github/copilot-instructions.md",
                ".github/agents/architect.agent.md", ".github/agents/implementer.agent.md",
                ".github/agents/reviewer.agent.md", ".github/agents/qa.agent.md"],
}

PACKAGE_HASH_EXCLUDE = {"manifest.json"}
PACKAGE_HASH_EXCLUDE_DIRS = {"__pycache__", ".backup"}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return sha256_text(path.read_text(encoding="utf-8"))


def load_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        return {"package_version": PACKAGE_VERSION, "hosts_registered": [], "generated_files": {}, "package_files": {}}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def collect_package_file_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in OSB_DIR.rglob("*"):
        if path.is_dir():
            continue
        rel_parts = path.relative_to(OSB_DIR).parts
        if any(part in PACKAGE_HASH_EXCLUDE_DIRS for part in rel_parts):
            continue
        rel = str(path.relative_to(OSB_DIR))
        if rel in PACKAGE_HASH_EXCLUDE:
            continue
        hashes[f"osb/{rel}"] = sha256_file(path)
    return hashes


def record_generated_hashes(manifest: dict, hosts: list[str]) -> None:
    for host in hosts:
        for rel in GENERATED_PATHS_BY_HOST[host]:
            path = WORKSPACE_ROOT / rel
            digest = sha256_file(path)
            if digest is not None:
                manifest["generated_files"][rel] = {"sha256": digest, "package_version": PACKAGE_VERSION}


def ensure_workspace_scaffold() -> list[str]:
    created = []
    osb_yaml = WORKSPACE_ROOT / "osb.yaml"
    if not osb_yaml.is_file():
        template = OSB_DIR / "templates" / "osb.yaml"
        osb_yaml.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        created.append("osb.yaml")

    for rel in (".osb/state", ".osb/knowledge/events", ".osb/knowledge/tasks", ".osb/knowledge/components"):
        d = WORKSPACE_ROOT / rel
        if not d.is_dir():
            d.mkdir(parents=True, exist_ok=True)
            keep = d / ".gitkeep"
            if not keep.exists():
                keep.write_text("", encoding="utf-8")
            created.append(rel)

    return created


def resolve_hosts(requested: list[str] | None, manifest: dict) -> list[str]:
    if requested:
        if "all" in requested:
            return list(ALL_HOSTS)
        unknown = sorted(set(requested) - set(ALL_HOSTS))
        if unknown:
            raise SystemExit(f"unknown host(s): {', '.join(unknown)} (choose from {', '.join(ALL_HOSTS)}, or 'all')")
        return list(dict.fromkeys(requested))
    if manifest.get("hosts_registered"):
        return list(manifest["hosts_registered"])
    raise SystemExit(
        "no host specified and no prior registration found; pass --host "
        f"{{{','.join(ALL_HOSTS)},all}} (repeatable)"
    )


def cmd_init(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    hosts = resolve_hosts(args.host, manifest)

    created = ensure_workspace_scaffold()
    generate_hosts.generate(WORKSPACE_ROOT, hosts, PACKAGE_VERSION)

    manifest["package_version"] = PACKAGE_VERSION
    manifest["hosts_registered"] = sorted(set(manifest.get("hosts_registered", [])) | set(hosts))
    manifest.setdefault("generated_files", {})
    manifest.setdefault("package_files", {})
    record_generated_hashes(manifest, hosts)
    manifest["package_files"] = collect_package_file_hashes()
    save_manifest(manifest)

    print(f"OSB {PACKAGE_VERSION} registered for host(s): {', '.join(hosts)}")
    if created:
        print("Created: " + ", ".join(created))
    print("Fill in models.<host>.* in osb.yaml, then invoke the workflow per osb/docs/<HOST>.md.")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    blocked = []
    warnings = []

    if not manifest.get("hosts_registered"):
        print("blocked: workspace not initialized — run `install init --host <host>` first")
        return 1

    for host in manifest["hosts_registered"]:
        for rel in GENERATED_PATHS_BY_HOST[host]:
            path = WORKSPACE_ROOT / rel
            current = sha256_file(path)
            recorded = manifest.get("generated_files", {}).get(rel, {}).get("sha256")
            if current is None:
                blocked.append(f"{rel}: missing generated file for registered host '{host}'")
            elif recorded and current != recorded:
                warnings.append(f"{rel}: modified since generation — re-run `upgrade` to review/regenerate")

    osb_yaml = WORKSPACE_ROOT / "osb.yaml"
    if not osb_yaml.is_file():
        blocked.append("osb.yaml: missing at workspace root")
    else:
        text = osb_yaml.read_text(encoding="utf-8")
        for host in manifest["hosts_registered"]:
            host_key = {"claude": "claude-code", "codex": "codex", "copilot": "copilot"}[host]
            for role in generate_hosts.ROLES:
                # best-effort textual check only — a real YAML parse happens in verify_task.py
                if f"{host_key}:" not in text:
                    warnings.append(f"osb.yaml: missing models.{host_key} block")
                    break

    for rel in (".osb/state", ".osb/knowledge/events", ".osb/knowledge/tasks", ".osb/knowledge/components"):
        if not (WORKSPACE_ROOT / rel).is_dir():
            warnings.append(f"{rel}: missing (created automatically on first use)")

    current_package_hashes = collect_package_file_hashes()
    package_version_current = manifest.get("package_version")
    if package_version_current and package_version_current != PACKAGE_VERSION:
        warnings.append(
            f"osb/ package version is {PACKAGE_VERSION}, last recorded install was "
            f"{package_version_current} — run `upgrade` to regenerate adapters for the current package"
        )
    elif manifest.get("package_files") and manifest["package_files"] != current_package_hashes:
        warnings.append("osb/ package contents differ from the last recorded install — run `upgrade` to sync generated adapters")

    if osb_yaml.is_file():
        workspace_cfg = yaml_lite.extract_key(osb_yaml.read_text(encoding="utf-8"), "workspace")
        if workspace_cfg:
            for err in workspace_validate.validate_workspace(workspace_cfg, WORKSPACE_ROOT):
                blocked.append(f"workspace: {err}")

    # Per-host capability preflight (Phase 7) — 'unknown' for a mandatory capability is
    # folded in as a warning here (doctor is advisory), never silently treated as pass.
    for host in manifest["hosts_registered"]:
        report = host_preflight.run_preflight(WORKSPACE_ROOT, host)
        for name, result in report["checks"].items():
            if result["status"] == "blocked":
                blocked.append(f"{host}/{name}: {result['detail']}")
            elif result["status"] == "unknown":
                warnings.append(f"{host}/{name}: unknown/unverified — {result['detail']}")

    print(f"OSB doctor — package {manifest.get('package_version', 'unknown')} (installed py: {PACKAGE_VERSION}), hosts: {', '.join(manifest['hosts_registered'])}")
    for w in warnings:
        print(f"  warning: {w}")
    for b in blocked:
        print(f"  blocked: {b}")
    if not warnings and not blocked:
        print("  pass: no issues found")
    return 1 if blocked else 0


def cmd_upgrade(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    if not manifest.get("hosts_registered"):
        print("blocked: workspace not initialized — run `install init --host <host>` first")
        return 1

    hosts = resolve_hosts(args.host, manifest)
    conflicts = []
    changes = []

    for host in hosts:
        for rel in GENERATED_PATHS_BY_HOST[host]:
            path = WORKSPACE_ROOT / rel
            current = sha256_file(path)
            recorded = manifest.get("generated_files", {}).get(rel, {}).get("sha256")
            if current is not None and recorded is not None and current != recorded and not args.force:
                conflicts.append(rel)
            else:
                changes.append(rel)

    if conflicts and not args.force:
        print("Modified generated file(s) detected — not overwriting without --force:")
        for c in conflicts:
            print(f"  conflict: {c}")
        hosts = [h for h in hosts if not any(rel in conflicts for rel in GENERATED_PATHS_BY_HOST[h])]
        if not hosts:
            print("No hosts left to upgrade after excluding conflicts.")
            return 1

    recorded_version = manifest.get("package_version", "unknown")
    if args.dry_run:
        print(f"Dry run: installed version {recorded_version} -> package version {PACKAGE_VERSION}")
        print(f"Would regenerate for host(s) {', '.join(hosts)}:")
        for rel in changes:
            path = WORKSPACE_ROOT / rel
            verb = "write (new)" if not path.exists() else "overwrite"
            print(f"  would {verb}: {rel}")
        if conflicts:
            print("Would skip (conflicting, pass --force to include): " + ", ".join(conflicts))
        print("No files were modified (--dry-run). osb.yaml, .osb/state/, and .osb/knowledge/ are never touched by upgrade.")
        return 0

    backup_dir = OSB_DIR / ".backup" / time.strftime("%Y%m%dT%H%M%S")
    for rel in changes:
        path = WORKSPACE_ROOT / rel
        if path.is_file():
            dest = backup_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
    if MANIFEST_PATH.is_file():
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MANIFEST_PATH, backup_dir / "manifest.json")

    generate_hosts.generate(WORKSPACE_ROOT, hosts, PACKAGE_VERSION)

    manifest["package_version"] = PACKAGE_VERSION
    record_generated_hashes(manifest, hosts)
    manifest["package_files"] = collect_package_file_hashes()
    save_manifest(manifest)

    print(f"Upgraded {recorded_version} -> {PACKAGE_VERSION} for host(s): {', '.join(hosts)} (backup: {backup_dir})")
    if conflicts:
        print("Skipped (conflicting, unforced): " + ", ".join(conflicts))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="osb-install", description=__doc__)
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Register selected host(s) and initialize the workspace (default action)")
    p_init.add_argument("--host", action="append", choices=[*ALL_HOSTS, "all"])
    p_init.set_defaults(func=cmd_init)

    p_doctor = sub.add_parser("doctor", help="Validate the current installation")
    p_doctor.set_defaults(func=cmd_doctor)

    p_upgrade = sub.add_parser("upgrade", help="Regenerate host adapters from the current osb/ package")
    p_upgrade.add_argument("--host", action="append", choices=[*ALL_HOSTS, "all"])
    p_upgrade.add_argument("--dry-run", action="store_true")
    p_upgrade.add_argument("--force", action="store_true", help="Overwrite generated files even if hand-modified")
    p_upgrade.set_defaults(func=cmd_upgrade)

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    if not argv or argv[0] not in ("init", "doctor", "upgrade"):
        argv = ["init", *argv]
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
