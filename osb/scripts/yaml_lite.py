#!/usr/bin/env python3
"""A minimal, dependency-free reader for the restricted YAML subset osb.yaml actually
uses: nested mappings, lists of scalars, lists of mappings (one mapping per list item,
continued by more-indented sibling keys), inline flow lists (`[a, b]`), and scalar
strings/ints/floats/bools/null. No anchors, multi-document streams, block scalars, or flow
mappings — OSB's own config never needs them, and a project that wants full YAML can parse
`osb.yaml` with PyYAML instead; this module exists so the deterministic validation scripts
don't require a third-party dependency to check the config OSB itself defines.
"""

from __future__ import annotations

import re

_COMMENT_RE = re.compile(r"(?<!\\)#.*$")


def _strip_comment(line: str) -> str:
    # Good enough for osb.yaml: no '#' appears inside a real value in this config format.
    return _COMMENT_RE.sub("", line).rstrip()


def _parse_scalar(text: str):
    s = text.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part) for part in inner.split(",")]
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if s in ("null", "~", ""):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


class _Lines:
    def __init__(self, raw: str) -> None:
        self.items: list[tuple[int, str]] = []
        for raw_line in raw.splitlines():
            line = _strip_comment(raw_line)
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip(" "))
            self.items.append((indent, line.strip()))
        self.pos = 0

    def peek(self) -> tuple[int, str] | None:
        return self.items[self.pos] if self.pos < len(self.items) else None

    def advance(self) -> tuple[int, str]:
        item = self.items[self.pos]
        self.pos += 1
        return item


def _parse_block(lines: _Lines, indent: int):
    peeked = lines.peek()
    if peeked is not None and peeked[0] == indent and peeked[1].startswith("- "):
        return _parse_list(lines, indent)
    return _parse_map(lines, indent)


def _parse_list(lines: _Lines, indent: int) -> list:
    items: list = []
    while True:
        peeked = lines.peek()
        if peeked is None or peeked[0] != indent or not peeked[1].startswith("- "):
            break
        _, content = lines.advance()
        rest = content[2:].strip()

        if not rest:
            nested = lines.peek()
            items.append(_parse_block(lines, nested[0]) if nested and nested[0] > indent else None)
            continue

        if ":" in rest and not (rest.startswith("[") or rest.startswith("'") or rest.startswith('"')):
            key, _, value = rest.partition(":")
            key = key.strip()
            value = value.strip()
            entry: dict = {}
            if value:
                entry[key] = _parse_scalar(value)
            else:
                nested = lines.peek()
                entry[key] = _parse_block(lines, nested[0]) if nested and nested[0] > indent else None
            child_indent = indent + 2
            while True:
                peeked = lines.peek()
                if peeked is None or peeked[0] != child_indent or peeked[1].startswith("- "):
                    break
                _, sub_content = lines.advance()
                sub_key, _, sub_value = sub_content.partition(":")
                sub_key = sub_key.strip()
                sub_value = sub_value.strip()
                if sub_value:
                    entry[sub_key] = _parse_scalar(sub_value)
                else:
                    nested = lines.peek()
                    entry[sub_key] = _parse_block(lines, nested[0]) if nested and nested[0] > child_indent else None
            items.append(entry)
        else:
            items.append(_parse_scalar(rest))
    return items


def _parse_map(lines: _Lines, indent: int) -> dict:
    result: dict = {}
    while True:
        peeked = lines.peek()
        if peeked is None or peeked[0] != indent or peeked[1].startswith("- "):
            break
        _, content = lines.advance()
        key, sep, value = content.partition(":")
        if not sep:
            continue  # malformed line, skip rather than raise on unrelated config prose
        key = key.strip()
        value = value.strip()
        if value:
            result[key] = _parse_scalar(value)
        else:
            nested = lines.peek()
            result[key] = _parse_block(lines, nested[0]) if nested and nested[0] > indent else None
    return result


def parse(text: str) -> dict:
    """Parse the restricted YAML subset described in the module docstring into plain
    dict/list/scalar Python values, starting at top-level indent 0."""

    lines = _Lines(text)
    return _parse_map(lines, 0)


def extract_key(text: str, key: str) -> object:
    """Convenience: parse the whole document and return one top-level key (or None)."""

    return parse(text).get(key)
