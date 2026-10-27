"""Simulator-only executor. Physical writes always denied at this boundary."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from ecugate.preflight.authorization import AuthorizationStore
from ecugate.preflight.engine import PreflightEngine
from ecugate.preflight.models import (
    AuthorizationGrant,
    ExecutionMode,
    ExecutionOutcome,
    ExecutionReceipt,
    OperationProposal,
    PreflightDecision,
    utc_now_iso,
)


class SimulatorExecutor:
    def __init__(
        self,
        engine: Optional[PreflightEngine] = None,
        auth_store: Optional[AuthorizationStore] = None,
    ) -> None:
        self.engine = engine or PreflightEngine()
        self.auth_store = auth_store or AuthorizationStore()
        self.audit: List[Dict[str, Any]] = []

    def _log(self, event: str, **kwargs: Any) -> str:
        ref = str(uuid4())
        safe = {k: v for k, v in kwargs.items() if "secret" not in k.lower() and "key" not in k.lower()}
        self.audit.append({"ref": ref, "event": event, "ts": utc_now_iso(), **safe})
        return ref

    def preflight(self, proposal: OperationProposal, grant: Optional[AuthorizationGrant] = None) -> Dict[str, Any]:
        result = self.engine.evaluate(proposal, grant=grant)
        self._log(
            "preflight",
            proposal_id=proposal.proposal_id,
            decision=result.decision.value,
            blockers=result.blockers,
            operation_digest=result.operation_digest,
            policy_version=result.policy_version,
        )
        return result.to_dict()

    def execute(
        self,
        proposal: OperationProposal,
        *,
        grant: Optional[AuthorizationGrant] = None,
        scenario: str = "success",
    ) -> ExecutionReceipt:
        started = utc_now_iso()
        audit_refs: List[str] = []

        if proposal.execution_mode == ExecutionMode.PHYSICAL:
            spec = self.engine.registry.get(proposal.operation_id)
            if spec and spec.changes_state:
                ref = self._log("physical_write_denied", operation_id=proposal.operation_id)
                return ExecutionReceipt(
                    receipt_id=str(uuid4()),
                    operation_id=proposal.operation_id,
                    authorization_ref=grant.grant_id if grant else None,
                    execution_mode=ExecutionMode.PHYSICAL,
                    outcome=ExecutionOutcome.DENIED,
                    started_at=started,
                    finished_at=utc_now_iso(),
                    audit_refs=[ref],
                    message="physical_write_not_implemented",
                )

        if proposal.execution_mode == ExecutionMode.DRY_RUN:
            pf = self.engine.evaluate(proposal, grant=grant)
            ref = self._log("dry_run", decision=pf.decision.value, blockers=pf.blockers)
            return ExecutionReceipt(
                receipt_id=str(uuid4()),
                operation_id=proposal.operation_id,
                authorization_ref=None,
                execution_mode=ExecutionMode.DRY_RUN,
                outcome=ExecutionOutcome.SUCCEEDED if pf.decision == PreflightDecision.READY else ExecutionOutcome.DENIED,
                started_at=started,
                finished_at=utc_now_iso(),
                audit_refs=[ref],
                message="dry_run_no_mutation",
                preflight=pf.to_dict(),
            )

        pf = self.engine.evaluate(proposal, grant=grant)
        audit_refs.append(self._log("revalidate", decision=pf.decision.value, blockers=pf.blockers))

        if pf.decision != PreflightDecision.READY:
            return ExecutionReceipt(
                receipt_id=str(uuid4()),
                operation_id=proposal.operation_id,
                authorization_ref=grant.grant_id if grant else None,
                execution_mode=proposal.execution_mode,
                outcome=ExecutionOutcome.DENIED,
                started_at=started,
                finished_at=utc_now_iso(),
                audit_refs=audit_refs,
                message="preflight_blocked",
                preflight=pf.to_dict(),
            )

        if grant is not None:
            ok = self.auth_store.consume(grant.grant_id)
            if not ok:
                audit_refs.append(self._log("grant_consume_failed", grant_id=grant.grant_id))
                return ExecutionReceipt(
                    receipt_id=str(uuid4()),
                    operation_id=proposal.operation_id,
                    authorization_ref=grant.grant_id,
                    execution_mode=ExecutionMode.SIMULATOR,
                    outcome=ExecutionOutcome.DENIED,
                    started_at=started,
                    finished_at=utc_now_iso(),
                    audit_refs=audit_refs,
                    message="grant_already_consumed_or_invalid",
                    preflight=pf.to_dict(),
                )
            audit_refs.append(self._log("grant_consumed", grant_id=grant.grant_id))

        mapping = {
            "success": ExecutionOutcome.SUCCEEDED,
            "failed": ExecutionOutcome.FAILED,
            "timeout": ExecutionOutcome.TIMEOUT,
            "interrupted": ExecutionOutcome.INTERRUPTED,
            "disconnect": ExecutionOutcome.DISCONNECTED,
            "stale_evidence": ExecutionOutcome.FAILED,
        }
        outcome = mapping.get(scenario, ExecutionOutcome.FAILED)
        audit_refs.append(self._log("execute", scenario=scenario, outcome=outcome.value))
        return ExecutionReceipt(
            receipt_id=str(uuid4()),
            operation_id=proposal.operation_id,
            authorization_ref=grant.grant_id if grant else None,
            execution_mode=ExecutionMode.SIMULATOR,
            outcome=outcome,
            started_at=started,
            finished_at=utc_now_iso(),
            audit_refs=audit_refs,
            message=f"simulator:{scenario}",
            preflight=pf.to_dict(),
        )
