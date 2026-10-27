"""Full HorsePowerPoint vertical slice tests. No network, no API keys."""

from __future__ import annotations

import os
import tempfile

from ecugate.execution import ExecutionEngine
from ecugate.execution.lifecycle import OperationStatus
from ecugate.memory import MemoryStore, RecordType
from ecugate.memory.sqlite_backend import SQLiteMemoryBackend
from ecugate.registry import ToolRegistry
from examples.horsepowerpoint.simulator import SimulatedECU
from examples.horsepowerpoint.tools import register_horsepowerpoint_tools

SUBJECT = "vehicle:sim-1"


def _stack(db_path: str = ":memory:"):
    reg = ToolRegistry()
    ecu = SimulatedECU(vehicle_id=SUBJECT)
    register_horsepowerpoint_tools(reg, ecu)
    mem = MemoryStore(SQLiteMemoryBackend(db_path))
    eng = ExecutionEngine(reg, mem, agent_id="hpp-test")
    return eng, ecu, mem


def test_discover_tools():
    eng, _, _ = _stack()
    tools = eng.discover()
    ids = {t["tool_id"] for t in tools}
    assert "engine.read_state" in ids
    assert "engine.set_parameter" in ids


def test_full_tuning_cycle_and_memory_reuse():
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "hpp.db")
        eng, ecu, mem = _stack(db)

        read1 = eng.run_read("engine.read_state", {}, subject=SUBJECT)
        assert read1.status == OperationStatus.RECORDED

        op1 = eng.run_execute(
            "engine.set_parameter",
            {"parameter": "spark_advance_deg", "value": 18.0},
            subject=SUBJECT,
            rationale="first tune",
            allow=True,
            observation={"cycle": 1},
        )
        assert op1.status == OperationStatus.RECORDED
        assert ecu.read_state()["parameters"]["spark_advance_deg"] == 18.0

        outcomes = mem.retrieve(subject=SUBJECT, record_type=RecordType.OUTCOME)
        assert len(outcomes) >= 1
        mem.close()

        eng2, ecu2, mem2 = _stack(db)
        prior = eng2.memory.retrieve(subject=SUBJECT, record_type=RecordType.OUTCOME)
        assert len(prior) >= 1
        assert prior[-1].content.get("observation", {}).get("cycle") == 1

        op2 = eng2.run_execute(
            "engine.set_parameter",
            {"parameter": "spark_advance_deg", "value": 20.0},
            subject=SUBJECT,
            rationale="second tune using prior outcome",
            allow=True,
            observation={"cycle": 2, "prior_count": len(prior)},
        )
        assert op2.status == OperationStatus.RECORDED
        assert ecu2.read_state()["parameters"]["spark_advance_deg"] == 20.0
        prior2 = mem2.retrieve(subject=SUBJECT, record_type=RecordType.OUTCOME)
        assert len(prior2) >= 2
        mem2.close()


def test_authorization_denial_recorded():
    eng, ecu, mem = _stack()
    op = eng.run_execute(
        "engine.set_parameter",
        {"parameter": "spark_advance_deg", "value": 18.0},
        subject=SUBJECT,
        allow=False,
    )
    assert op.status == OperationStatus.DENIED
    assert ecu.read_state()["parameters"]["spark_advance_deg"] == 15.0
    fails = mem.retrieve(subject=SUBJECT, record_type=RecordType.FAILURE)
    assert any("authorization" in (f.tags or []) or "authorization_denied" in str(f.content) for f in fails)


def test_simulator_rejects_unsafe_even_when_authorized():
    eng, ecu, mem = _stack()
    op = eng.run_execute(
        "engine.set_parameter",
        {"parameter": "spark_advance_deg", "value": 99.0},
        subject=SUBJECT,
        allow=True,
    )
    assert op.result is not None
    assert op.result.error is not None
    assert "outside hard limits" in op.result.error.message
    assert ecu.read_state()["parameters"]["spark_advance_deg"] == 15.0
    fails = mem.retrieve(subject=SUBJECT, record_type=RecordType.FAILURE)
    assert len(fails) >= 1


def test_dry_run_no_mutation():
    eng, ecu, _ = _stack()
    before = ecu.read_state()["parameters"]["fuel_trim_pct"]
    op = eng.run_execute(
        "engine.set_parameter",
        {"parameter": "fuel_trim_pct", "value": 5.0},
        subject=SUBJECT,
        allow=True,
        dry_run=True,
    )
    assert op.result is not None
    assert op.result.dry_run is True
    assert ecu.read_state()["parameters"]["fuel_trim_pct"] == before


def test_invalid_schema_rejected():
    eng, _, mem = _stack()
    op = eng.run_execute(
        "engine.set_parameter",
        {"parameter": "not_a_param", "value": 1.0},
        subject=SUBJECT,
        allow=True,
    )
    assert op.result is not None
    assert op.result.error is not None
    assert op.result.error.code == "schema_validation_failed"
    fails = mem.retrieve(subject=SUBJECT, record_type=RecordType.FAILURE)
    assert len(fails) >= 1
