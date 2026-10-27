"""Deterministic preflight evaluation — fail closed."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Set

from ecugate.preflight.models import (
    BLOCKER_CODES,
    POLICY_VERSION,
    AuthorizationGrant,
    ExecutionMode,
    OperationClass,
    OperationProposal,
    PreflightDecision,
    PreflightResult,
    utc_now,
)
from ecugate.preflight.registry import CapabilityRegistry


def _family_match(family: Optional[str], permitted: List[str]) -> bool:
    if not family or not permitted:
        return False
    for p in permitted:
        if p.endswith(".*"):
            if family.startswith(p[:-2]):
                return True
        elif family == p:
            return True
    return False


class PreflightEngine:
    """Evaluates proposals against explicit requirements. Never grants authorization."""

    def __init__(self, registry: Optional[CapabilityRegistry] = None) -> None:
        self.registry = registry or CapabilityRegistry()

    def evaluate(
        self,
        proposal: OperationProposal,
        *,
        grant: Optional[AuthorizationGrant] = None,
        now: Optional[datetime] = None,
        skip_authorization_check: bool = False,
    ) -> PreflightResult:
        now = now or utc_now()
        blockers: Set[str] = set()
        warnings: List[str] = []
        satisfied: List[str] = []
        evidence_refs: List[str] = []

        spec = self.registry.get(proposal.operation_id)
        if spec is None:
            blockers.add("operation_not_allowlisted")
            return self._result(proposal, blockers, warnings, satisfied, evidence_refs)

        satisfied.append("operation_allowlisted")

        if proposal.execution_mode == ExecutionMode.PHYSICAL and spec.changes_state:
            blockers.add("physical_write_not_implemented")

        bench = proposal.bench
        target = bench.target if bench else None

        if "target_identity" in spec.preconditions or spec.changes_state:
            if target is None or not target.verified or target.confidence.value == "unknown":
                blockers.add("target_identity_unverified")
            elif not target.ecu_id:
                blockers.add("target_identity_unverified")
            else:
                satisfied.append("target_identity_verified")
                for e in target.evidence:
                    evidence_refs.append(f"target:{e.source}")
                    if not e.is_fresh(now=now):
                        blockers.add("evidence_stale")

        if target and spec.permitted_target_families:
            if not _family_match(target.family, spec.permitted_target_families):
                blockers.add("unsupported_target_profile")
            else:
                satisfied.append("target_profile_supported")
        elif spec.changes_state and (not target or not target.family):
            blockers.add("unsupported_target_profile")

        if bench and ("bench_topology" in spec.preconditions or spec.changes_state):
            if not bench.adapter_id or not bench.protocol:
                blockers.add("adapter_protocol_unverified")
            else:
                satisfied.append("adapter_protocol_present")

        if "bench_topology" in spec.preconditions or (
            spec.changes_state and spec.operation_class in (OperationClass.WRITE, OperationClass.FLASH)
        ):
            if not bench or not bench.relationships_confirmed:
                blockers.add("bench_topology_incomplete")
            elif not bench.programmer_id and spec.operation_class == OperationClass.FLASH:
                blockers.add("bench_topology_incomplete")
            else:
                if bench and bench.relationships_confirmed:
                    satisfied.append("bench_topology_resolved")

        if "power" in spec.preconditions or (
            spec.changes_state and spec.operation_class in (OperationClass.WRITE, OperationClass.FLASH)
        ):
            if not bench or not bench.power:
                blockers.add("power_requirements_unverified")
            else:
                p = bench.power
                if p.voltage_min is None or p.voltage_max is None:
                    blockers.add("power_requirements_unverified")
                else:
                    satisfied.append("power_limits_documented")
                    for e in p.evidence:
                        evidence_refs.append(f"power:{e.source}")
                        if not e.is_fresh(now=now):
                            blockers.add("evidence_stale")
                    if p.measured and p.voltage_v is not None:
                        if p.voltage_v < p.voltage_min or p.voltage_v > p.voltage_max:
                            blockers.add("power_measurement_out_of_range")
                        else:
                            satisfied.append("power_measurement_in_range")
                    elif spec.changes_state and not p.measured:
                        blockers.add("power_requirements_unverified")
                        warnings.append("power voltage not measured")

        if spec.requires_artifact:
            art = proposal.artifact
            if art is None or not art.digest:
                blockers.add("artifact_integrity_unverified")
            else:
                if not art.integrity_verified:
                    blockers.add("artifact_integrity_unverified")
                else:
                    satisfied.append("artifact_integrity_ok")
                if target and target.family and art.compatible_families:
                    if not _family_match(target.family, art.compatible_families):
                        blockers.add("artifact_incompatible")
                    else:
                        satisfied.append("artifact_compatible")
                elif art.compatible_families and (not target or not target.family):
                    blockers.add("artifact_incompatible")

        if "session" in spec.preconditions or spec.changes_state:
            if not bench or not bench.session_valid or not bench.session_id:
                blockers.add("session_invalid")
            else:
                satisfied.append("session_valid")

        if spec.requires_recovery_plan or "recovery" in spec.preconditions:
            if not bench or not bench.recovery_plan:
                blockers.add("recovery_plan_missing")
            else:
                satisfied.append("recovery_plan_defined")

        if not skip_authorization_check and spec.requires_authorization:
            if grant is None:
                blockers.add("authorization_missing")
            else:
                self._check_grant(proposal, grant, blockers, satisfied, now=now)

        ordered = [c for c in BLOCKER_CODES if c in blockers]
        for c in sorted(blockers):
            if c not in ordered:
                ordered.append(c)

        return self._result(proposal, ordered, warnings, satisfied, evidence_refs)

    def _check_grant(self, proposal, grant, blockers, satisfied, *, now):
        if grant.revoked:
            blockers.add("authorization_scope_mismatch")
            return
        if grant.consumed and grant.single_use:
            blockers.add("grant_already_consumed")
            return
        try:
            exp = datetime.fromisoformat(grant.expires_at.replace("Z", "+00:00"))
        except ValueError:
            blockers.add("authorization_expired")
            return
        if now > exp:
            blockers.add("authorization_expired")
            return
        if grant.operation_digest != proposal.operation_digest():
            blockers.add("authorization_scope_mismatch")
            return
        if proposal.bench:
            if grant.target_digest != proposal.bench.target.identity_digest():
                blockers.add("authorization_scope_mismatch")
                return
        art_digest = proposal.artifact.digest if proposal.artifact else None
        if grant.artifact_digest != art_digest:
            blockers.add("authorization_scope_mismatch")
            return
        satisfied.append("authorization_grant_valid")

    def _result(self, proposal, blockers, warnings, satisfied, evidence_refs):
        bl = list(blockers) if isinstance(blockers, list) else [c for c in BLOCKER_CODES if c in blockers]
        decision = PreflightDecision.READY if not bl else PreflightDecision.BLOCKED
        return PreflightResult(
            decision=decision,
            blockers=bl,
            warnings=warnings,
            satisfied=satisfied,
            evidence_refs=evidence_refs,
            policy_version=POLICY_VERSION,
            operation_digest=proposal.operation_digest(),
            proposal_id=proposal.proposal_id,
        )
