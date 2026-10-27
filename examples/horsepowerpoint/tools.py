"""Register HorsePowerPoint tools against the shared ToolRegistry."""

from __future__ import annotations

from typing import Any, Dict

from ecugate.registry.models import (
    ExecutionPolicy,
    ToolDefinition,
    ToolPermission,
)
from ecugate.registry.registry import ToolRegistry
from examples.horsepowerpoint.simulator import SimulatedECU


def register_horsepowerpoint_tools(registry: ToolRegistry, ecu: SimulatedECU) -> None:
    def read_state() -> Dict[str, Any]:
        return ecu.read_state()

    def set_parameter(parameter: str, value: float) -> Dict[str, Any]:
        return ecu.apply_parameter(parameter, value, dry_run=False)

    registry.register(
        ToolDefinition(
            tool_id="engine.read_state",
            version="1.0.0",
            description="Read current simulated ECU parameters and telemetry.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={
                "type": "object",
                "required": ["vehicle_id", "parameters", "telemetry", "limits"],
                "properties": {
                    "vehicle_id": {"type": "string"},
                    "parameters": {"type": "object"},
                    "telemetry": {"type": "object"},
                    "limits": {"type": "object"},
                },
            },
            permissions=[ToolPermission.READ],
            policy=ExecutionPolicy(
                timeout_seconds=5.0,
                requires_authorization=False,
                idempotent=True,
            ),
            handler=read_state,
        )
    )

    registry.register(
        ToolDefinition(
            tool_id="engine.set_parameter",
            version="1.0.0",
            description="Set a single engine parameter on the simulated ECU.",
            input_schema={
                "type": "object",
                "required": ["parameter", "value"],
                "additionalProperties": False,
                "properties": {
                    "parameter": {
                        "type": "string",
                        "enum": [
                            "spark_advance_deg",
                            "fuel_trim_pct",
                            "boost_target_psi",
                            "idle_rpm",
                        ],
                    },
                    "value": {"type": "number"},
                },
            },
            output_schema={
                "type": "object",
                "required": ["parameter", "accepted"],
                "properties": {
                    "parameter": {"type": "string"},
                    "before": {"type": "number"},
                    "after": {"type": "number"},
                    "accepted": {"type": "boolean"},
                    "telemetry": {"type": "object"},
                    "dry_run": {"type": "boolean"},
                },
            },
            permissions=[ToolPermission.EXECUTE, ToolPermission.PROPOSE],
            policy=ExecutionPolicy(
                timeout_seconds=5.0,
                requires_authorization=True,
                idempotent=False,
                allow_dry_run=True,
            ),
            handler=set_parameter,
        )
    )
