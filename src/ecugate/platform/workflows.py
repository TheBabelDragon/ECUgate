"""Typed replacement and recovery workflow contracts.

Software-level simulation only. Physical state-changing operations remain denied.
Migration never silently overwrites the original capture.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ecugate.platform.backup import ClonePackage
from ecugate.platform.compatibility import CompatibilityEngine
from ecugate.platform.models import (
    CompatibilityResult,
    CompatibilityStatus,
    ControllerProfile,
    HardwareModule,
    VehicleProfile,
    utc_now_iso,
)


class WorkflowKind(str, enum.Enum):
    IDENTIFY = "IDENTIFY"
    CAPTURE = "CAPTURE"
    VERIFY = "VERIFY"
    COMPARE = "COMPARE"
    COMPATIBILITY_CHECK = "COMPATIBILITY_CHECK"
    MIGRATE = "MIGRATE"
    BENCH_VALIDATE = "BENCH_VALIDATE"
    RESTORE = "RESTORE"
    RECOVER = "RECOVER"


class WorkflowPhase(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"


STATE_CHANGING = {
    WorkflowKind.MIGRATE,
    WorkflowKind.RESTORE,
    WorkflowKind.RECOVER,
}


@dataclass
class WorkflowContext:
    vehicle: Optional[VehicleProfile] = None
    original: Optional[ControllerProfile] = None
    replacement: Optional[ControllerProfile] = None
    modules: List[HardwareModule] = field(default_factory=list)
    source_capture: Optional[ClonePackage] = None
    working_capture: Optional[ClonePackage] = None
    compatibility: Optional[CompatibilityResult] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowStepResult:
    kind: WorkflowKind
    phase: WorkflowPhase
    message: str
    blockers: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    output: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=utc_now_iso)
    finished_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "phase": self.phase.value,
            "message": self.message,
            "blockers": list(self.blockers),
            "evidence_refs": list(self.evidence_refs),
            "output": dict(self.output),
            "provenance": dict(self.provenance),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class WorkflowRun:
    run_id: str
    kind: WorkflowKind
    steps: List[WorkflowStepResult] = field(default_factory=list)
    final_phase: WorkflowPhase = WorkflowPhase.PENDING
    source_capture_ref: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "kind": self.kind.value,
            "steps": [s.to_dict() for s in self.steps],
            "final_phase": self.final_phase.value,
            "source_capture_ref": self.source_capture_ref,
            "created_at": self.created_at,
        }


class WorkflowEngine:
    """Simulate platform workflows. No physical writes."""

    def __init__(self, compatibility_engine: Optional[CompatibilityEngine] = None) -> None:
        self._compat = compatibility_engine or CompatibilityEngine()

    def run(
        self,
        kind: WorkflowKind,
        ctx: WorkflowContext,
        *,
        allow_state_changing_simulation: bool = True,
    ) -> WorkflowRun:
        run = WorkflowRun(
            run_id=str(uuid4()),
            kind=kind,
            source_capture_ref=ctx.source_capture.package_id if ctx.source_capture else None,
        )

        if kind == WorkflowKind.IDENTIFY:
            step = self._identify(ctx)
        elif kind == WorkflowKind.CAPTURE:
            step = self._capture(ctx)
        elif kind == WorkflowKind.VERIFY:
            step = self._verify(ctx)
        elif kind == WorkflowKind.COMPARE:
            step = self._compare(ctx)
        elif kind == WorkflowKind.COMPATIBILITY_CHECK:
            step = self._compatibility_check(ctx)
        elif kind == WorkflowKind.MIGRATE:
            step = self._migrate(ctx, allow_state_changing_simulation)
        elif kind == WorkflowKind.BENCH_VALIDATE:
            step = self._bench_validate(ctx)
        elif kind == WorkflowKind.RESTORE:
            step = self._restore(ctx, allow_state_changing_simulation)
        elif kind == WorkflowKind.RECOVER:
            step = self._recover(ctx, allow_state_changing_simulation)
        else:
            step = WorkflowStepResult(
                kind=kind,
                phase=WorkflowPhase.FAILED,
                message=f"unknown workflow kind: {kind}",
            )

        step.finished_at = utc_now_iso()
        run.steps.append(step)
        run.final_phase = step.phase
        return run

    def _identify(self, ctx: WorkflowContext) -> WorkflowStepResult:
        ids = {}
        if ctx.vehicle:
            ids["vehicle_id"] = ctx.vehicle.vehicle_id
        if ctx.original:
            ids["original_controller_id"] = ctx.original.controller_id
        if ctx.replacement:
            ids["replacement_controller_id"] = ctx.replacement.controller_id
        if not ids:
            return WorkflowStepResult(
                kind=WorkflowKind.IDENTIFY,
                phase=WorkflowPhase.BLOCKED,
                message="no identities available",
                blockers=["identity_missing"],
            )
        return WorkflowStepResult(
            kind=WorkflowKind.IDENTIFY,
            phase=WorkflowPhase.SUCCEEDED,
            message="identities recorded",
            output=ids,
            evidence_refs=list(ids.values()),
            provenance={"source": "workflow.identify"},
        )

    def _capture(self, ctx: WorkflowContext) -> WorkflowStepResult:
        if ctx.source_capture is None:
            return WorkflowStepResult(
                kind=WorkflowKind.CAPTURE,
                phase=WorkflowPhase.BLOCKED,
                message="no capture package supplied (simulation requires fixture)",
                blockers=["capture_fixture_missing"],
            )
        completeness = ctx.source_capture.capture_completeness()
        phase = WorkflowPhase.SUCCEEDED if completeness["is_complete"] else WorkflowPhase.BLOCKED
        return WorkflowStepResult(
            kind=WorkflowKind.CAPTURE,
            phase=phase,
            message="capture package inspected",
            blockers=[] if completeness["is_complete"] else ["backup_incomplete"],
            output={"completeness": completeness, "package_id": ctx.source_capture.package_id},
            evidence_refs=[ctx.source_capture.package_id],
            provenance={"source": "workflow.capture", "immutable": True},
        )

    def _verify(self, ctx: WorkflowContext) -> WorkflowStepResult:
        pkg = ctx.source_capture or ctx.working_capture
        if pkg is None:
            return WorkflowStepResult(
                kind=WorkflowKind.VERIFY,
                phase=WorkflowPhase.BLOCKED,
                message="no package to verify",
                blockers=["package_missing"],
            )
        ok = pkg.verify_integrity()
        return WorkflowStepResult(
            kind=WorkflowKind.VERIFY,
            phase=WorkflowPhase.SUCCEEDED if ok else WorkflowPhase.FAILED,
            message="integrity verified" if ok else "integrity check failed",
            blockers=[] if ok else ["backup_integrity_failed"],
            output={"package_digest": pkg.package_digest, "verified": ok},
            evidence_refs=[pkg.package_id],
        )

    def _compare(self, ctx: WorkflowContext) -> WorkflowStepResult:
        if not ctx.original or not ctx.replacement:
            return WorkflowStepResult(
                kind=WorkflowKind.COMPARE,
                phase=WorkflowPhase.BLOCKED,
                message="original and replacement required",
                blockers=["compare_inputs_missing"],
            )
        return WorkflowStepResult(
            kind=WorkflowKind.COMPARE,
            phase=WorkflowPhase.SUCCEEDED,
            message="controller profiles compared (metadata only)",
            output={
                "original_id": ctx.original.controller_id,
                "replacement_id": ctx.replacement.controller_id,
                "original_digest": ctx.original.digest(),
                "replacement_digest": ctx.replacement.digest(),
            },
        )

    def _compatibility_check(self, ctx: WorkflowContext) -> WorkflowStepResult:
        result = self._compat.evaluate(
            vehicle=ctx.vehicle,
            original=ctx.original,
            replacement=ctx.replacement,
            modules=ctx.modules,
            backup=ctx.source_capture,
        )
        ctx.compatibility = result
        phase = (
            WorkflowPhase.SUCCEEDED
            if result.status == CompatibilityStatus.COMPATIBLE
            else WorkflowPhase.BLOCKED
        )
        return WorkflowStepResult(
            kind=WorkflowKind.COMPATIBILITY_CHECK,
            phase=phase,
            message=f"compatibility: {result.status.value}",
            blockers=list(result.blockers),
            output=result.to_dict(),
            evidence_refs=list(result.evidence_refs),
        )

    def _require_compat(self, ctx: WorkflowContext) -> Optional[WorkflowStepResult]:
        if ctx.compatibility is None:
            check = self._compatibility_check(ctx)
            if check.phase != WorkflowPhase.SUCCEEDED:
                return WorkflowStepResult(
                    kind=WorkflowKind.MIGRATE,
                    phase=WorkflowPhase.BLOCKED,
                    message="compatibility check failed; state-changing phase denied",
                    blockers=list(check.blockers) + ["compatibility_required"],
                    output=check.output,
                )
        elif ctx.compatibility.status != CompatibilityStatus.COMPATIBLE:
            return WorkflowStepResult(
                kind=WorkflowKind.MIGRATE,
                phase=WorkflowPhase.BLOCKED,
                message="prior compatibility result not compatible; state-changing phase denied",
                blockers=list(ctx.compatibility.blockers) + ["compatibility_required"],
            )
        return None

    def _migrate(self, ctx: WorkflowContext, allow_sim: bool) -> WorkflowStepResult:
        blocked = self._require_compat(ctx)
        if blocked:
            blocked.kind = WorkflowKind.MIGRATE
            return blocked
        if not allow_sim:
            return WorkflowStepResult(
                kind=WorkflowKind.MIGRATE,
                phase=WorkflowPhase.DENIED,
                message="physical migration is not implemented and is hard-denied",
                blockers=["physical_write_not_implemented"],
            )
        source_ref = ctx.source_capture.package_id if ctx.source_capture else None
        return WorkflowStepResult(
            kind=WorkflowKind.MIGRATE,
            phase=WorkflowPhase.SUCCEEDED,
            message="migration simulated; original capture left immutable",
            output={
                "simulated": True,
                "source_capture_ref": source_ref,
                "overwrote_source": False,
            },
            provenance={"mode": "simulator", "authorized_write": False},
        )

    def _bench_validate(self, ctx: WorkflowContext) -> WorkflowStepResult:
        return WorkflowStepResult(
            kind=WorkflowKind.BENCH_VALIDATE,
            phase=WorkflowPhase.SUCCEEDED,
            message="bench validation simulated (no physical hardware required)",
            output={"simulated": True, "modules": [m.module_id for m in ctx.modules]},
            provenance={"mode": "simulator"},
        )

    def _restore(self, ctx: WorkflowContext, allow_sim: bool) -> WorkflowStepResult:
        blocked = self._require_compat(ctx)
        if blocked:
            blocked.kind = WorkflowKind.RESTORE
            return blocked
        if not allow_sim:
            return WorkflowStepResult(
                kind=WorkflowKind.RESTORE,
                phase=WorkflowPhase.DENIED,
                message="physical restore is not implemented and is hard-denied",
                blockers=["physical_write_not_implemented"],
            )
        return WorkflowStepResult(
            kind=WorkflowKind.RESTORE,
            phase=WorkflowPhase.SUCCEEDED,
            message="restore simulated; original capture not overwritten",
            output={
                "simulated": True,
                "source_capture_ref": ctx.source_capture.package_id if ctx.source_capture else None,
            },
            provenance={"mode": "simulator", "authorized_write": False},
        )

    def _recover(self, ctx: WorkflowContext, allow_sim: bool) -> WorkflowStepResult:
        if not allow_sim:
            return WorkflowStepResult(
                kind=WorkflowKind.RECOVER,
                phase=WorkflowPhase.DENIED,
                message="physical recovery is not implemented and is hard-denied",
                blockers=["physical_write_not_implemented"],
            )
        reqs = []
        if ctx.source_capture:
            reqs = list(ctx.source_capture.recovery_requirements)
        return WorkflowStepResult(
            kind=WorkflowKind.RECOVER,
            phase=WorkflowPhase.SUCCEEDED,
            message="recovery plan simulated",
            output={"simulated": True, "recovery_requirements": reqs},
            provenance={"mode": "simulator", "authorized_write": False},
        )
