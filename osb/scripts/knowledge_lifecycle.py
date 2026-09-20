#!/usr/bin/env python3
"""Provenance-aware knowledge dedup/supersession helpers (P1-E, Phase 5).

Knowledge files remain the authoritative source (osb/references/knowledge.md); RagMonk
only indexes them. This module never talks to RagMonk or a model — it is deterministic
bookkeeping over already-collected knowledge events: assigning stable ids, deduplicating
identical retrieval-derived entries, and marking (never deleting) an entry as superseded
when the source it was derived from has changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schema_validate  # noqa: E402

SCHEMA = json.loads((Path(__file__).resolve().parent.parent / "schemas/knowledge-event.schema.json").read_text())


def assign_id(entry: dict) -> str:
    basis = "|".join(
        str(entry.get(k, "")) for k in ("repository_id", "source_path", "summary", "type")
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]


def normalize(entry: dict) -> dict:
    """Fill in id/lifecycle_status defaults so a plain role-reported knowledge entry
    (osb/references/roles.md) becomes a valid knowledge-event without the role itself
    having to know about provenance bookkeeping."""

    normalized = dict(entry)
    normalized.setdefault("id", assign_id(entry))
    normalized.setdefault("lifecycle_status", "provisional")
    normalized.setdefault("repository_id", None)
    normalized.setdefault("source_path", None)
    normalized.setdefault("source_revision", None)
    normalized.setdefault("superseded_by", None)
    return normalized


def dedup_key(entry: dict) -> tuple:
    """Entries are deduplicated by repository + source path + source revision/content
    identity (P1-E) — the same excerpt retrieved twice for the same revision is one
    capsule, not two."""

    return (entry.get("repository_id"), entry.get("source_path"), entry.get("source_revision"))


def dedupe(entries: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    kept: list[dict] = []
    for raw in entries:
        entry = normalize(raw)
        key = dedup_key(entry)
        if key != (None, None, None) and key in seen:
            continue
        seen.add(key)
        kept.append(entry)
    return kept


def supersede_stale(
    existing_entries: list[dict], current_source_revisions: dict[str, str]
) -> list[dict]:
    """For every still-authoritative entry whose source_path has a known current revision
    that no longer matches source_revision, mark it 'superseded' (audit history is kept,
    never deleted) and append a fresh 'provisional' placeholder entry recording that the
    source has moved on. current_source_revisions: {source_path: current_revision}."""

    updated: list[dict] = []
    superseded_ids: dict[str, str] = {}

    for raw in existing_entries:
        entry = normalize(raw)
        source_path = entry.get("source_path")
        current_rev = current_source_revisions.get(source_path) if source_path else None

        if (
            entry["lifecycle_status"] != "superseded"
            and source_path is not None
            and current_rev is not None
            and entry.get("source_revision") not in (None, current_rev)
        ):
            replacement = dict(entry)
            replacement["source_revision"] = current_rev
            replacement["lifecycle_status"] = "provisional"
            replacement["summary"] = f"[needs re-verification after source change] {entry['summary']}"
            replacement["id"] = assign_id(replacement)

            entry = dict(entry)
            entry["lifecycle_status"] = "superseded"
            entry["superseded_by"] = replacement["id"]
            superseded_ids[entry["id"]] = replacement["id"]
            updated.append(entry)
            updated.append(replacement)
        else:
            updated.append(entry)

    return updated


def validate_events(entries: list[dict]) -> list[str]:
    errors: list[str] = []
    for i, entry in enumerate(entries):
        for e in schema_validate.validate(normalize(entry), SCHEMA):
            errors.append(f"event[{i}]: {e}")
    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_normalize = sub.add_parser("normalize", help="Fill in id/lifecycle_status defaults for one JSON entry")
    p_normalize.add_argument("entry_json", help="A single knowledge-event JSON object")

    p_dedupe = sub.add_parser("dedupe", help="Read a JSONL events file, print deduplicated JSON array")
    p_dedupe.add_argument("events_file")

    p_validate = sub.add_parser("validate", help="Validate a JSONL events file against the schema")
    p_validate.add_argument("events_file")

    args = parser.parse_args(argv)

    if args.command == "normalize":
        print(json.dumps(normalize(json.loads(args.entry_json))))
        return 0

    lines = [
        json.loads(line)
        for line in Path(args.events_file).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    if args.command == "dedupe":
        print(json.dumps(dedupe(lines), indent=2))
        return 0

    errors = validate_events(lines)
    if errors:
        print(f"{len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"{len(lines)} event(s) valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
