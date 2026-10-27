import pytest
from ecugate.registry.schema_validate import validate, SchemaValidationError


def test_object_required():
    schema = {
        "type": "object",
        "required": ["a"],
        "properties": {"a": {"type": "integer"}},
        "additionalProperties": False,
    }
    validate({"a": 1}, schema)
    with pytest.raises(SchemaValidationError):
        validate({}, schema)
    with pytest.raises(SchemaValidationError):
        validate({"a": 1, "b": 2}, schema)


def test_number_bounds():
    schema = {"type": "number", "minimum": 0, "maximum": 10}
    validate(5, schema)
    with pytest.raises(SchemaValidationError):
        validate(-1, schema)
    with pytest.raises(SchemaValidationError):
        validate(11, schema)


def test_enum():
    schema = {"type": "string", "enum": ["x", "y"]}
    validate("x", schema)
    with pytest.raises(SchemaValidationError):
        validate("z", schema)


def test_bool_not_int():
    schema = {"type": "integer"}
    with pytest.raises(SchemaValidationError):
        validate(True, schema)
