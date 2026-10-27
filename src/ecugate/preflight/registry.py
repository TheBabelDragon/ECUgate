"""Registered operation capability profiles (simulator-oriented)."""

from __future__ import annotations

from typing import Dict, List, Optional

from ecugate.preflight.models import OperationClass, OperationSpec


def default_operations() -> Dict[str, OperationSpec]:
    ops = [
        OperationSpec(
            operation_id="sim.read_state",
            operation_class=OperationClass.READ,
            required_capabilities=["sim.ecu"],
            preconditions=["target_identity"],
            permitted_target_families=["sim.ecu", "sim.*"],
            changes_state=False,
            requires_artifact=False,
            requires_authorization=False,
            requires_recovery_plan=False,
            description="Simulator read of engine/ECU state",
        ),
        OperationSpec(
            operation_id="sim.write_param",
            operation_class=OperationClass.WRITE,
            required_capabilities=["sim.ecu", "sim.write"],
            preconditions=[
                "target_identity",
                "bench_topology",
                "power",
                "session",
                "authorization",
            ],
            permitted_target_families=["sim.ecu"],
            changes_state=True,
            requires_artifact=False,
            requires_authorization=True,
            requires_recovery_plan=True,
            description="Simulator-only parameter write (no physical path)",
        ),
        OperationSpec(
            operation_id="sim.flash_image",
            operation_class=OperationClass.FLASH,
            required_capabilities=["sim.ecu", "sim.flash"],
            preconditions=[
                "target_identity",
                "bench_topology",
                "power",
                "session",
                "artifact",
                "authorization",
                "recovery",
            ],
            permitted_target_families=["sim.ecu"],
            changes_state=True,
            requires_artifact=True,
            requires_authorization=True,
            requires_recovery_plan=True,
            description="Simulator-only flash (physical denied)",
        ),
        OperationSpec(
            operation_id="vehicle.read_pid",
            operation_class=OperationClass.READ,
            required_capabilities=["obd.read"],
            preconditions=["session"],
            permitted_target_families=["vehicle.obd", "unknown"],
            changes_state=False,
            requires_authorization=False,
            description="Read-only OBD PID (delegates to vehicle_io)",
        ),
    ]
    return {o.operation_id: o for o in ops}


class CapabilityRegistry:
    def __init__(self, operations: Optional[Dict[str, OperationSpec]] = None) -> None:
        self._ops = dict(operations or default_operations())

    def get(self, operation_id: str) -> Optional[OperationSpec]:
        return self._ops.get(operation_id)

    def list_operations(self) -> List[OperationSpec]:
        return [self._ops[k] for k in sorted(self._ops)]

    def register(self, spec: OperationSpec) -> None:
        self._ops[spec.operation_id] = spec
