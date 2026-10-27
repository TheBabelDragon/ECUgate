"""Minimal JSON-Schema-like validator (subset sufficient for tool I/O).

Supports: type, properties, required, additionalProperties, enum, minimum,
maximum, minLength, maxLength, items, minItems, maxItems.
No $ref, no format, no oneOf/anyOf for the first release.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


class SchemaValidationError(Exception):
    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


def validate(instance: Any, schema: Dict[str, Any], path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise SchemaValidationError(path, "schema must be an object")

    expected = schema.get("type")
    if expected is not None:
        _check_type(instance, expected, path)

    if "enum" in schema:
        if instance not in schema["enum"]:
            raise SchemaValidationError(path, f"value not in enum {schema['enum']}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise SchemaValidationError(path, f"value {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            raise SchemaValidationError(path, f"value {instance} > maximum {schema['maximum']}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise SchemaValidationError(path, f"string shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            raise SchemaValidationError(path, f"string longer than maxLength {schema['maxLength']}")

    if expected == "object" or (expected is None and isinstance(instance, dict)):
        if not isinstance(instance, dict):
            raise SchemaValidationError(path, "expected object")
        props = schema.get("properties") or {}
        required = schema.get("required") or []
        for key in required:
            if key not in instance:
                raise SchemaValidationError(f"{path}.{key}", "required property missing")
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in props:
                validate(value, props[key], f"{path}.{key}")
            elif additional is False:
                raise SchemaValidationError(f"{path}.{key}", "additional property not allowed")
            elif isinstance(additional, dict):
                validate(value, additional, f"{path}.{key}")

    if expected == "array" or (expected is None and isinstance(instance, list)):
        if not isinstance(instance, list):
            raise SchemaValidationError(path, "expected array")
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise SchemaValidationError(path, f"array shorter than minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise SchemaValidationError(path, f"array longer than maxItems {schema['maxItems']}")
        items_schema = schema.get("items")
        if items_schema is not None:
            for i, item in enumerate(instance):
                validate(item, items_schema, f"{path}[{i}]")


def _check_type(instance: Any, expected: Any, path: str) -> None:
    type_map = {
        "null": type(None),
        "boolean": bool,
        "integer": int,
        "number": (int, float),
        "string": str,
        "array": list,
        "object": dict,
    }
    if isinstance(expected, list):
        ok = False
        for t in expected:
            try:
                _check_type(instance, t, path)
                ok = True
                break
            except SchemaValidationError:
                continue
        if not ok:
            raise SchemaValidationError(path, f"type not in {expected}")
        return
    py = type_map.get(expected)
    if py is None:
        raise SchemaValidationError(path, f"unknown type {expected}")
    if expected == "integer" and isinstance(instance, bool):
        raise SchemaValidationError(path, "expected integer, got boolean")
    if expected == "number" and isinstance(instance, bool):
        raise SchemaValidationError(path, "expected number, got boolean")
    if not isinstance(instance, py):
        raise SchemaValidationError(path, f"expected {expected}, got {type(instance).__name__}")


def validate_or_error(
    instance: Any, schema: Dict[str, Any]
) -> Optional[Tuple[str, str]]:
    try:
        validate(instance, schema)
        return None
    except SchemaValidationError as e:
        return e.path, e.message
