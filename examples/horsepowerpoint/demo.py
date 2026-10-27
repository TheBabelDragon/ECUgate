#!/usr/bin/env python3
"""HorsePowerPoint end-to-end demonstration. No network, API keys, or real vehicle."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ecugate.execution import ExecutionEngine
from ecugate.execution.audit import AuditLog
from ecugate.memory import MemoryStore, RecordType
from ecugate.memory.sqlite_backend import SQLiteMemoryBackend
from ecugate.registry import ToolRegistry
from examples.horsepowerpoint.simulator import SimulatedECU
from examples.horsepowerpoint.tools import register_horsepowerpoint_tools

SUBJECT = "vehicle:sim-1"


def build_stack(db_path: str, audit_path: str | None = None):
    registry = ToolRegistry()
    ecu = SimulatedECU(vehicle_id=SUBJECT)
    register_horsepowerpoint_tools(registry, ecu)
    memory = MemoryStore(SQLiteMemoryBackend(db_path))
    audit = AuditLog(audit_path)
    engine = ExecutionEngine(registry, memory, audit, agent_id="horsepowerpoint")
    return engine, ecu, memory, audit


def cycle(engine: ExecutionEngine, label: str, param: str, value: float, allow: bool) -> dict:
    print(f"\n=== {label} ===")
    tools = engine.discover()
    print(f"Discovered {len(tools)} tools: {[t['tool_id'] for t in tools]}")
    read_op = engine.run_read("engine.read_state", {}, subject=SUBJECT)
    state = read_op.result.output if read_op.result else {}
    print(f"Current parameters: {json.dumps(state.get('parameters', {}), indent=2)}")
    op = engine.new_operation(tool_id="engine.set_parameter", subject=SUBJECT)
    prior = engine.recall(op, subject=SUBJECT, record_type=RecordType.OUTCOME, limit=10)
    print(f"Recalled {len(prior)} prior outcomes")
    rationale = f"Adjust {param} toward {value} based on prior outcomes and current state"
    result_op = engine.run_execute(
        "engine.set_parameter",
        {"parameter": param, "value": value},
        subject=SUBJECT,
        rationale=rationale,
        allow=allow,
        observation={"cycle": label, "requested": {param: value}},
    )
    print(f"Status: {result_op.status.value}")
    if result_op.authorization:
        print(f"Authorization: allowed={result_op.authorization.allowed} ({result_op.authorization.reason})")
    if result_op.result:
        print(f"Result: {json.dumps(result_op.result.to_dict(), indent=2)}")
    return result_op.to_dict()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HorsePowerPoint demo")
    parser.add_argument("--db", default=None, help="SQLite memory path (default: temp)")
    parser.add_argument("--audit", default=None, help="JSONL audit path")
    parser.add_argument("--reject-first", action="store_true", help="Deny first execute to demo recovery")
    args = parser.parse_args(argv)

    tmp = None
    db_path = args.db
    if not db_path:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = tmp.name
        tmp.close()

    engine, ecu, memory, audit = build_stack(db_path, args.audit)
    print(f"Memory DB: {db_path}")
    print(f"Subject: {SUBJECT}")

    allow1 = not args.reject_first
    cycle(engine, "cycle-1", "spark_advance_deg", 18.0, allow=allow1)
    cycle(engine, "cycle-2", "spark_advance_deg", 20.0, allow=True)

    print("\n=== cycle-3 (unsafe value — simulator must reject) ===")
    op = engine.run_execute(
        "engine.set_parameter",
        {"parameter": "spark_advance_deg", "value": 99.0},
        subject=SUBJECT,
        rationale="deliberately unsafe",
        allow=True,
    )
    print(f"Status: {op.status.value}")
    if op.result and op.result.error:
        print(f"Error: {op.result.error.to_dict()}")

    before = ecu.read_state()["parameters"]["fuel_trim_pct"]
    dry = engine.run_execute(
        "engine.set_parameter",
        {"parameter": "fuel_trim_pct", "value": 5.0},
        subject=SUBJECT,
        allow=True,
        dry_run=True,
    )
    after = ecu.read_state()["parameters"]["fuel_trim_pct"]
    print(f"\nDry-run status={dry.status.value}; fuel_trim before={before} after={after} (must match)")

    print(f"\nMemory records: {memory.backend.count(SUBJECT)}")
    print(f"Audit entries: {len(audit.list())}")
    print("\nDone. Restart with --db", db_path, "to reuse memory.")
    memory.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
