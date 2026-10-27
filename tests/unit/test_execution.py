from ecugate.execution import ExecutionEngine
from ecugate.memory import MemoryStore, RecordType
from ecugate.registry import (
    ToolRegistry,
    ToolDefinition,
    ToolPermission,
    ExecutionPolicy,
)
from ecugate.execution.lifecycle import OperationStatus


def _setup():
    reg = ToolRegistry()
    state = {"n": 0}

    def inc(by: int = 1):
        state["n"] += by
        return {"n": state["n"]}

    def read():
        return {"n": state["n"]}

    reg.register(
        ToolDefinition(
            tool_id="counter.read",
            version="1.0.0",
            description="read",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object"},
            permissions=[ToolPermission.READ],
            policy=ExecutionPolicy(requires_authorization=False),
            handler=read,
        )
    )
    reg.register(
        ToolDefinition(
            tool_id="counter.inc",
            version="1.0.0",
            description="inc",
            input_schema={
                "type": "object",
                "properties": {"by": {"type": "integer", "minimum": 1}},
                "required": ["by"],
                "additionalProperties": False,
            },
            output_schema={"type": "object"},
            permissions=[ToolPermission.EXECUTE],
            policy=ExecutionPolicy(requires_authorization=True, idempotent=True),
            handler=inc,
        )
    )
    mem = MemoryStore()
    eng = ExecutionEngine(reg, mem, agent_id="test")
    return eng, state


def test_read_auto_authorize():
    eng, state = _setup()
    op = eng.run_read("counter.read", {}, subject="c:1")
    assert op.status == OperationStatus.RECORDED
    assert op.result is not None
    assert op.result.output["n"] == 0


def test_execute_denied_without_allow():
    eng, state = _setup()
    op = eng.run_execute("counter.inc", {"by": 1}, subject="c:1", allow=False)
    assert op.status == OperationStatus.DENIED
    assert state["n"] == 0
    fails = eng.memory.retrieve(subject="c:1", record_type=RecordType.FAILURE)
    assert len(fails) >= 1


def test_execute_allowed():
    eng, state = _setup()
    op = eng.run_execute("counter.inc", {"by": 2}, subject="c:1", allow=True)
    assert op.status == OperationStatus.RECORDED
    assert state["n"] == 2
    outcomes = eng.memory.retrieve(subject="c:1", record_type=RecordType.OUTCOME)
    assert len(outcomes) >= 1


def test_dry_run_no_mutation():
    eng, state = _setup()
    op = eng.run_execute("counter.inc", {"by": 5}, subject="c:1", allow=True, dry_run=True)
    assert op.result is not None
    assert op.result.dry_run is True
    assert state["n"] == 0
