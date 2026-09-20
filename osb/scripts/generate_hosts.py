#!/usr/bin/env python3
"""Generate host-native OSB entry points from the canonical package sources.

This module is deterministic templating only — it never invents policy, never contacts a
network, and never runs a model. It reads:

  - osb/SKILL.md                  (canonical coordinator)
  - osb/agents/<role>.md          (canonical, self-contained per-role prompt bodies)
  - osb/hosts/<host>/*.tmpl       (host-specific wrapper templates)

and writes the generated, host-native files a coding assistant discovers natively. Callers
(osb/scripts/install.py) are responsible for deciding *which* hosts to generate and for
recording the resulting file hashes in osb/manifest.json.
"""

from __future__ import annotations

import re
from pathlib import Path
from string import Template

ROLES = ("architect", "implementer", "reviewer", "qa")
ROLE_TITLES = {"architect": "Architect", "implementer": "Implementer", "reviewer": "Reviewer", "qa": "QA"}
CODEX_SANDBOX_BY_ROLE = {
    "architect": "read-only",
    "implementer": "workspace-write",
    "reviewer": "read-only",
    "qa": "read-only",
}


class GenerationError(RuntimeError):
    pass


def _osb_dir(workspace_root: Path) -> Path:
    return workspace_root / "osb"


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise GenerationError("canonical role file is missing --- frontmatter")
    end = text.find("\n---", 4)
    if end == -1:
        raise GenerationError("canonical role file has an unterminated frontmatter block")
    fm_text = text[4:end]
    body = text[end + 4 :].lstrip("\n")
    fields: dict[str, str] = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, body


def load_canonical_role(workspace_root: Path, role: str) -> tuple[dict[str, str], str]:
    path = _osb_dir(workspace_root) / "agents" / f"{role}.md"
    if not path.is_file():
        raise GenerationError(f"missing canonical role source: {path}")
    return split_frontmatter(path.read_text(encoding="utf-8"))


def markdown_to_plain(body: str) -> str:
    """Strip Markdown emphasis/fences for hosts (Codex) that want plain prose.

    Deterministic and reversible in spirit: bold markers and code fences are removed,
    fenced content is kept verbatim so the compact YAML schema block still reads clearly.
    """

    text = body.replace("**", "")
    lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
    return "\n".join(lines).strip("\n")


def render_template(workspace_root: Path, host: str, name: str, mapping: dict[str, str]) -> str:
    tmpl_path = _osb_dir(workspace_root) / "hosts" / host / name
    if not tmpl_path.is_file():
        raise GenerationError(f"missing host template: {tmpl_path}")
    template = Template(tmpl_path.read_text(encoding="utf-8"))
    return template.substitute(mapping)


def write_generated(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_claude(workspace_root: Path, version: str = "0.0.0-dev") -> list[Path]:
    written: list[Path] = []

    skill_content = render_template(
        workspace_root, "claude", "skill.md.tmpl", {"PACKAGE_VERSION": version}
    )
    skill_path = workspace_root / ".claude" / "skills" / "osb" / "SKILL.md"
    write_generated(skill_path, skill_content)
    written.append(skill_path)

    for role in ROLES:
        fields, body = load_canonical_role(workspace_root, role)
        content = render_template(
            workspace_root,
            "claude",
            "agent.md.tmpl",
            {
                "ROLE": role,
                "DESCRIPTION": fields.get("description", ""),
                "TOOLS": fields.get("tools", ""),
                "BODY": body.rstrip("\n"),
            },
        )
        agent_path = workspace_root / ".claude" / "agents" / f"{role}.md"
        write_generated(agent_path, content)
        written.append(agent_path)

    return written


def generate_native_skill_pointer(workspace_root: Path) -> Path:
    """The verbatim copy of osb/SKILL.md used by Codex/Copilot Agent Skills discovery."""

    src = _osb_dir(workspace_root) / "SKILL.md"
    if not src.is_file():
        raise GenerationError(f"missing canonical skill: {src}")
    dst = workspace_root / ".agents" / "skills" / "osb" / "SKILL.md"
    write_generated(dst, src.read_text(encoding="utf-8"))
    return dst


def generate_codex(workspace_root: Path, version: str = "0.0.0-dev") -> list[Path]:
    written = [generate_native_skill_pointer(workspace_root)]

    for role in ROLES:
        fields, body = load_canonical_role(workspace_root, role)
        plain_body = markdown_to_plain(body)
        content = render_template(
            workspace_root,
            "codex",
            "agent.toml.tmpl",
            {
                "ROLE": role,
                "ROLE_TITLE": ROLE_TITLES[role],
                "DESCRIPTION": fields.get("description", "").replace('"', "'"),
                "SANDBOX_MODE": CODEX_SANDBOX_BY_ROLE[role],
                "BODY": plain_body,
                "PACKAGE_VERSION": version,
            },
        )
        agent_path = workspace_root / ".codex" / "agents" / f"{role}.toml"
        write_generated(agent_path, content)
        written.append(agent_path)

    return written


def generate_copilot(workspace_root: Path, version: str = "0.0.0-dev") -> list[Path]:
    written = [generate_native_skill_pointer(workspace_root)]

    instructions = render_template(
        workspace_root, "copilot", "copilot-instructions.md.tmpl", {"PACKAGE_VERSION": version}
    )
    instructions_path = workspace_root / ".github" / "copilot-instructions.md"
    write_generated(instructions_path, instructions)
    written.append(instructions_path)

    for role in ROLES:
        fields, body = load_canonical_role(workspace_root, role)
        content = render_template(
            workspace_root,
            "copilot",
            "agent.md.tmpl",
            {
                "ROLE": role,
                "ROLE_TITLE": ROLE_TITLES[role],
                "DESCRIPTION": fields.get("description", ""),
                "BODY": body.rstrip("\n"),
            },
        )
        agent_path = workspace_root / ".github" / "agents" / f"{role}.agent.md"
        write_generated(agent_path, content)
        written.append(agent_path)

    return written


GENERATORS = {
    "claude": generate_claude,
    "codex": generate_codex,
    "copilot": generate_copilot,
}


def generate(workspace_root: Path, hosts: list[str], version: str = "0.0.0-dev") -> dict[str, list[Path]]:
    unknown = sorted(set(hosts) - set(GENERATORS))
    if unknown:
        raise GenerationError(f"unknown host(s): {', '.join(unknown)}")
    result: dict[str, list[Path]] = {}
    for host in hosts:
        result[host] = GENERATORS[host](workspace_root, version)
    return result
