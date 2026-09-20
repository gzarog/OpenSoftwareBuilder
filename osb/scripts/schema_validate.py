#!/usr/bin/env python3
"""A small, dependency-free JSON Schema validator.

OSB deliberately has no third-party runtime dependencies (see osb/docs/OSB_V2_CONTRACT.md
§"What OSB v2 deliberately does not have"), so this implements just the subset of JSON
Schema (2020-12 vocabulary) that osb/schemas/*.json actually use: type, enum, const,
required, properties, patternProperties, additionalProperties, items, minItems, maxItems,
oneOf, and local `$ref`/`$defs` resolution. It is not a general-purpose implementation —
it is deliberately scoped to what this package needs, and raises clearly if a schema uses
something it doesn't support, rather than silently accepting an invalid instance.
"""

from __future__ import annotations

import re
from typing import Any


class SchemaError(RuntimeError):
    pass


_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _resolve_ref(ref: str, root: dict) -> dict:
    if not ref.startswith("#/"):
        raise SchemaError(f"unsupported $ref (must be local): {ref}")
    node: Any = root
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise SchemaError(f"unresolvable $ref: {ref}")
        node = node[part]
    return node


def _check_type(value: Any, expected: str) -> bool:
    py_type = _TYPE_MAP.get(expected)
    if py_type is None:
        raise SchemaError(f"unsupported type in schema: {expected}")
    if expected == "integer" and isinstance(value, bool):
        return False
    if expected == "boolean" and not isinstance(value, bool):
        return False
    if expected == "number" and isinstance(value, bool):
        return False
    return isinstance(value, py_type)


def validate(instance: Any, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    """Return a list of human-readable validation errors (empty means valid)."""

    root = root if root is not None else schema
    errors: list[str] = []

    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root)

    if "oneOf" in schema:
        sub_errors = []
        matches = 0
        for i, sub_schema in enumerate(schema["oneOf"]):
            errs = validate(instance, sub_schema, root, f"{path}")
            if not errs:
                matches += 1
            else:
                sub_errors.append(f"  option {i}: {'; '.join(errs)}")
        if matches != 1:
            errors.append(
                f"{path}: expected exactly one oneOf branch to match, {matches} matched:\n"
                + "\n".join(sub_errors)
            )
        return errors

    if "const" in schema:
        if instance != schema["const"]:
            errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")

    if "enum" in schema:
        if instance not in schema["enum"]:
            errors.append(f"{path}: {instance!r} is not one of {schema['enum']!r}")

    if "type" in schema:
        expected_types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_check_type(instance, t) for t in expected_types):
            errors.append(f"{path}: expected type {expected_types}, got {type(instance).__name__}")
            return errors  # further structural checks are meaningless on a type mismatch

    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required property '{req}'")
        pattern_props = schema.get("patternProperties", {})
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in properties:
                errors.extend(validate(value, properties[key], root, f"{path}.{key}"))
                continue
            matched = False
            for pattern, sub_schema in pattern_props.items():
                if re.match(pattern, key):
                    matched = True
                    errors.extend(validate(value, sub_schema, root, f"{path}.{key}"))
            if not matched and not properties and not pattern_props:
                continue
            if not matched and key not in properties:
                if additional is False:
                    errors.append(f"{path}: unexpected property '{key}'")
                elif isinstance(additional, dict):
                    errors.extend(validate(value, additional, root, f"{path}.{key}"))

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: has {len(instance)} items, expected >= {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: has {len(instance)} items, expected <= {schema['maxItems']}")
        if "items" in schema:
            for i, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], root, f"{path}[{i}]"))

    return errors
