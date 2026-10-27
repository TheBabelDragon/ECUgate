from ecugate.registry import (
    ToolRegistry,
    ToolDefinition,
    ToolPermission,
    ExecutionPolicy,
)
from ecugate.registry.models import OperationStatus


def _echo_tool():
    return ToolDefinition(
        tool_id="echo",
        version="1.0.0",
        description="echo",
        input_schema={
            "type": "object",
            "required": ["msg"],
            "properties": {"msg": {"type": "string"}},
            "additionalProperties": False,
        },
        output_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
        permissions=[ToolPermission.READ, ToolPermission.EXECUTE],
        policy=ExecutionPolicy(requires_authorization=True, idempotent=True),
        handler=lambda msg: {"msg": msg},
    )


def test_discover_and_invoke():
    reg = ToolRegistry()
    reg.register(_echo_tool())
    tools = reg.discover()
    assert len(tools) == 1
    assert tools[0]["tool_id"] == "echo"

    r = reg.invoke("echo", {"msg": "hi"}, permission=ToolPermission.READ, authorized=True)
    assert r.status == OperationStatus.SUCCEEDED
    assert r.output == {"msg": "hi"}


def test_unknown_tool():
    reg = ToolRegistry()
    r = reg.invoke("nope", {}, permission=ToolPermission.READ)
    assert r.status == OperationStatus.FAILED
    assert r.error.code == "unknown_tool"


def test_schema_reject():
    reg = ToolRegistry()
    reg.register(_echo_tool())
    r = reg.invoke("echo", {"msg": 1}, permission=ToolPermission.READ, authorized=True)
    assert r.status == OperationStatus.FAILED
    assert r.error.code == "schema_validation_failed"


def test_authorization_required():
    reg = ToolRegistry()
    reg.register(_echo_tool())
    r = reg.invoke("echo", {"msg": "x"}, permission=ToolPermission.EXECUTE, authorized=False)
    assert r.status == OperationStatus.DENIED
    assert r.error.code == "authorization_required"


def test_idempotency():
    reg = ToolRegistry()
    reg.register(_echo_tool())
    r1 = reg.invoke(
        "echo", {"msg": "once"}, permission=ToolPermission.EXECUTE, authorized=True, idempotency_key="k1"
    )
    r2 = reg.invoke(
        "echo", {"msg": "once"}, permission=ToolPermission.EXECUTE, authorized=True, idempotency_key="k1"
    )
    assert r1.operation_id == r2.operation_id
    assert r2.status == OperationStatus.SUCCEEDED


def test_dry_run():
    reg = ToolRegistry()
    reg.register(_echo_tool())
    r = reg.invoke(
        "echo", {"msg": "x"}, permission=ToolPermission.EXECUTE, authorized=True, dry_run=True
    )
    assert r.status == OperationStatus.DRY_RUN
    assert r.dry_run is True
