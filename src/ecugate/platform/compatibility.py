"""Deterministic, fail-closed compatibility evaluation.

Unknown or unverified critical requirements fail closed.
No inference from similar names, processor families or connector shapes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from ecugate.platform.backup import ClonePackage
from ecugate.platform.models import (
    CompatibilityResult,
    CompatibilityStatus,
    ControllerProfile,
    HardwareModule,
    ModuleKind,
    SafetyClass,
    VehicleProfile,
    VerificationStatus,
)


BLOCKER_MISSING_VEHICLE_PROFILE = "missing_vehicle_profile"
BLOCKER_MISSING_ORIGINAL_CONTROLLER = "missing_original_controller"
BLOCKER_MISSING_REPLACEMENT = "missing_replacement_controller"
BLOCKER_PROCESSOR_INCOMPATIBLE = "processor_target_incompatible"
BLOCKER_PROTOCOL_MISMATCH = "protocol_mismatch"
BLOCKER_ELECTRICAL_UNKNOWN = "electrical_requirements_unknown"
BLOCKER_ELECTRICAL_MISMATCH = "electrical_requirements_mismatch"
BLOCKER_MISSING_MODULE = "required_module_missing"
BLOCKER_MODULE_SAFETY = "module_safety_class_insufficient"
BLOCKER_CAN_FD_MISSING = "can_fd_controller_missing"
BLOCKER_SAFETY_SUPERVISOR_MISSING = "safety_supervisor_missing"
BLOCKER_POWER_MODULE_MISSING = "power_protection_module_missing"
BLOCKER_INCOMPLETE_BACKUP = "backup_incomplete"
BLOCKER_BACKUP_INTEGRITY = "backup_integrity_failed"
BLOCKER_CALIBRATION_SCHEMA = "calibration_schema_incompatible"
BLOCKER_RECOVERY_MISSING = "recovery_procedure_missing"
BLOCKER_UNVERIFIED_CRITICAL = "unverified_critical_requirement"
BLOCKER_DEVELOPMENT_ONLY = "development_hardware_not_vehicle_qualified"


class CompatibilityEngine:
    """Evaluate vehicle + original + replacement + modules + backup."""

    def evaluate(
        self,
        *,
        vehicle: Optional[VehicleProfile] = None,
        original: Optional[ControllerProfile] = None,
        replacement: Optional[ControllerProfile] = None,
        modules: Optional[Sequence[HardwareModule]] = None,
        backup: Optional[ClonePackage] = None,
        require_vehicle_qualified: bool = True,
    ) -> CompatibilityResult:
        modules = list(modules or [])
        blockers: List[str] = []
        warnings: List[str] = []
        satisfied: List[str] = []
        evidence_refs: List[str] = []
        details: Dict[str, Any] = {}

        if vehicle is None:
            blockers.append(BLOCKER_MISSING_VEHICLE_PROFILE)
        else:
            satisfied.append("vehicle_profile_present")
            evidence_refs.append(f"vehicle:{vehicle.vehicle_id}")

        if original is None:
            blockers.append(BLOCKER_MISSING_ORIGINAL_CONTROLLER)
        else:
            satisfied.append("original_controller_present")
            evidence_refs.append(f"controller:{original.controller_id}")

        if replacement is None:
            blockers.append(BLOCKER_MISSING_REPLACEMENT)
        else:
            satisfied.append("replacement_controller_present")
            evidence_refs.append(f"controller:{replacement.controller_id}")

        by_kind: Dict[ModuleKind, List[HardwareModule]] = {}
        for m in modules:
            by_kind.setdefault(m.kind, []).append(m)
            evidence_refs.append(f"module:{m.module_id}")

        compute_modules = by_kind.get(ModuleKind.COMPUTE, [])
        power_modules = by_kind.get(ModuleKind.POWER_PROTECTION, [])
        comm_modules = by_kind.get(ModuleKind.COMMUNICATIONS, [])
        safety_modules = by_kind.get(ModuleKind.SAFETY_SUPERVISION, [])
        output_modules = by_kind.get(ModuleKind.OUTPUT_DRIVER, [])

        if original and replacement:
            oa = (original.processor_architecture or "").lower()
            ra = (replacement.processor_architecture or "").lower()
            if oa and ra and oa != ra:
                warnings.append(
                    f"processor_architecture_differs:{oa}->{ra}; require explicit migration path"
                )
            if not ra:
                blockers.append(BLOCKER_UNVERIFIED_CRITICAL)
                details["processor"] = "replacement processor_architecture unknown"

            op = set(p.lower() for p in original.protocols)
            rp = set(p.lower() for p in replacement.protocols)
            if op and rp and not (op & rp):
                blockers.append(BLOCKER_PROTOCOL_MISMATCH)
                details["protocols"] = {"original": list(op), "replacement": list(rp)}
            elif op and rp and (op & rp):
                satisfied.append("protocol_overlap")

            oe = original.electrical
            re = replacement.electrical
            if oe.verification == VerificationStatus.UNKNOWN or re.verification == VerificationStatus.UNKNOWN:
                if oe.voltage_nominal_v is None or re.voltage_nominal_v is None:
                    blockers.append(BLOCKER_ELECTRICAL_UNKNOWN)
                elif (
                    oe.voltage_nominal_v is not None
                    and re.voltage_nominal_v is not None
                    and abs(oe.voltage_nominal_v - re.voltage_nominal_v) > 0.5
                ):
                    blockers.append(BLOCKER_ELECTRICAL_MISMATCH)
            elif (
                oe.voltage_nominal_v is not None
                and re.voltage_nominal_v is not None
                and abs(oe.voltage_nominal_v - re.voltage_nominal_v) > 0.5
            ):
                blockers.append(BLOCKER_ELECTRICAL_MISMATCH)
            else:
                satisfied.append("electrical_nominal_compatible_or_unknown_non_critical")

        if require_vehicle_qualified:
            if not power_modules:
                blockers.append(BLOCKER_POWER_MODULE_MISSING)
            else:
                satisfied.append("power_protection_present")

            if not safety_modules:
                blockers.append(BLOCKER_SAFETY_SUPERVISOR_MISSING)
            else:
                for sm in safety_modules:
                    if sm.safety_class in (SafetyClass.DEVELOPMENT, SafetyClass.UNKNOWN):
                        blockers.append(BLOCKER_MODULE_SAFETY)
                        details.setdefault("safety_modules", []).append(sm.module_id)
                    else:
                        satisfied.append(f"safety_module:{sm.module_id}")

            if not output_modules:
                warnings.append("no_output_driver_module_declared")

            needs_can_fd = False
            if vehicle:
                for iface in vehicle.network_interfaces:
                    if "can_fd" in iface.protocol.lower() or "canfd" in iface.protocol.lower():
                        needs_can_fd = True
            if original:
                for iface in original.interfaces:
                    if "can_fd" in iface.protocol.lower() or "canfd" in iface.protocol.lower():
                        needs_can_fd = True
                for p in original.protocols:
                    if "can_fd" in p.lower() or "canfd" in p.lower():
                        needs_can_fd = True

            if needs_can_fd:
                has_can_fd = False
                for m in modules:
                    for iface in m.interfaces:
                        if "can_fd" in iface.protocol.lower() and not iface.external_hardware_required:
                            has_can_fd = True
                    if "can_fd" in " ".join(m.capabilities).lower():
                        has_can_fd = True
                for m in comm_modules:
                    for iface in m.interfaces:
                        if "can_fd" in iface.protocol.lower():
                            has_can_fd = True
                if not has_can_fd:
                    blockers.append(BLOCKER_CAN_FD_MISSING)

            for cm in compute_modules:
                if cm.safety_class == SafetyClass.DEVELOPMENT:
                    blockers.append(BLOCKER_DEVELOPMENT_ONLY)
                    details.setdefault("development_compute", []).append(cm.module_id)
                if "not_automotive_qualified" in cm.compatibility_constraints:
                    blockers.append(BLOCKER_DEVELOPMENT_ONLY)

        if backup is not None:
            evidence_refs.append(f"package:{backup.package_id}")
            if not backup.verify_integrity():
                blockers.append(BLOCKER_BACKUP_INTEGRITY)
            completeness = backup.capture_completeness()
            details["backup_completeness"] = completeness
            if not completeness["is_complete"]:
                blockers.append(BLOCKER_INCOMPLETE_BACKUP)
            else:
                satisfied.append("backup_complete")
            if backup.recovery_requirements:
                satisfied.append("recovery_requirements_declared")
            elif not completeness["is_complete"]:
                blockers.append(BLOCKER_RECOVERY_MISSING)

        if blockers:
            soft = {
                BLOCKER_MISSING_VEHICLE_PROFILE,
                BLOCKER_MISSING_ORIGINAL_CONTROLLER,
                BLOCKER_MISSING_REPLACEMENT,
                BLOCKER_ELECTRICAL_UNKNOWN,
                BLOCKER_UNVERIFIED_CRITICAL,
                BLOCKER_INCOMPLETE_BACKUP,
                BLOCKER_RECOVERY_MISSING,
            }
            if all(b in soft or b.startswith("missing") for b in blockers) and not any(
                b
                in {
                    BLOCKER_PROTOCOL_MISMATCH,
                    BLOCKER_ELECTRICAL_MISMATCH,
                    BLOCKER_PROCESSOR_INCOMPATIBLE,
                    BLOCKER_DEVELOPMENT_ONLY,
                    BLOCKER_MODULE_SAFETY,
                }
                for b in blockers
            ):
                status = CompatibilityStatus.INCOMPLETE
            else:
                status = CompatibilityStatus.INCOMPATIBLE
        else:
            status = CompatibilityStatus.COMPATIBLE

        return CompatibilityResult(
            status=status,
            blockers=blockers,
            warnings=warnings,
            satisfied=satisfied,
            evidence_refs=evidence_refs,
            details=details,
        )
