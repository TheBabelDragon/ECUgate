"""Auditable execution lifecycle (core)."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ecugate.memory.models import MemoryRecord, Provenance, RecordType
from ecugate.memory.store import MemoryStore
from ecugate.registry.models import ToolPermission, ToolResult, OperationStatus as ToolOpStatus
from ecugate.registry.registry import ToolRegistry
from ecugate.execution.audit import AuditLog


class OperationStatus(str, enum.Enum):
    DISCOVERED = "discovered"
    READ = "read"
    RECALLED = "recalled"
    PROPOSED = "proposed"
    VALIDATED = "validated"
    AUTHORIZED = "authorized"
    DENIED = "denied"
    EXECUTED = "executed"
    OBSERVED = "observed"
    RECORDED = "recorded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AuthorizationDecision:
    allowed: bool
    reason: str
    decided_by: str = "policy"
    constraints: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"allowed": self.allowed, "reason": self.reason, "decided_by": self.decided_by, "constraints": self.constraints}


@dataclass
class Operation:
    operation_id: str
    tool_id: Optional[str] = None
    permission: Optional[ToolPermission] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    status: OperationStatus = OperationStatus.DISCOVERED
    proposal: Optional[Dict[str, Any]] = None
    validation_errors: List[str] = field(default_factory=list)
    authorization: Optional[AuthorizationDecision] = None
    result: Optional[ToolResult] = None
    memory_ids: List[str] = field(default_factory=list)
    dry_run: bool = False
    idempotency_key: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    subject: Optional[str] = None
    rationale: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "tool_id": self.tool_id,
            "permission": self.permission.value if self.permission else None,
            "arguments": self.arguments,
            "status": self.status.value,
            "proposal": self.proposal,
            "validation_errors": self.validation_errors,
            "authorization": self.authorization.to_dict() if self.authorization else None,
            "result": self.result.to_dict() if self.result else None,
            "memory_ids": list(self.memory_ids),
            "dry_run": self.dry_run,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at,
            "subject": self.subject,
            "rationale": self.rationale,
        }


class ExecutionEngine:
    def __init__(self, registry: ToolRegistry, memory: MemoryStore, audit: Optional[AuditLog] = None, *, agent_id: str = "default-agent", auto_authorize_read: bool = True) -> None:
        self.registry = registry
        self.memory = memory
        self.audit = audit or AuditLog()
        self.agent_id = agent_id
        self.auto_authorize_read = auto_authorize_read
        self._ops: Dict[str, Operation] = {}

    def discover(self, permission: Optional[ToolPermission] = None) -> List[Dict[str, Any]]:
        tools = self.registry.discover(permission)
        self.audit.append("discover", detail={"count": len(tools)})
        return tools

    def new_operation(self, *, tool_id: Optional[str] = None, subject: Optional[str] = None, dry_run: bool = False, idempotency_key: Optional[str] = None) -> Operation:
        op = Operation(operation_id=str(uuid4()), tool_id=tool_id, subject=subject, dry_run=dry_run, idempotency_key=idempotency_key)
        self._ops[op.operation_id] = op
        return op

    def recall(self, op: Operation, *, subject: Optional[str] = None, record_type: Optional[RecordType] = None, limit: int = 50) -> List[MemoryRecord]:
        subj = subject or op.subject
        records = self.memory.retrieve(subject=subj, record_type=record_type, limit=limit, active_only=True)
        op.status = OperationStatus.RECALLED
        op.memory_ids.extend(r.record_id for r in records)
        self.audit.append("recall", operation_id=op.operation_id, detail={"subject": subj, "count": len(records)})
        return records

    def propose(self, op: Operation, tool_id: str, arguments: Dict[str, Any], *, permission: ToolPermission = ToolPermission.EXECUTE, rationale: Optional[str] = None) -> Operation:
        op.tool_id = tool_id
        op.arguments = arguments
        op.permission = permission
        op.rationale = rationale
        op.proposal = {"tool_id": tool_id, "arguments": arguments, "permission": permission.value, "rationale": rationale}
        op.status = OperationStatus.PROPOSED
        self.audit.append("propose", operation_id=op.operation_id, tool_id=tool_id, detail={"permission": permission.value})
        if op.subject:
            rec = self.memory.record(RecordType.DECISION, op.subject, {"proposal": op.proposal, "operation_id": op.operation_id}, Provenance(source=f"agent:{self.agent_id}", operation_id=op.operation_id, is_observed=False, agent_id=self.agent_id), related_ids=[op.operation_id], tags=["proposal"])
            op.memory_ids.append(rec.record_id)
        return op

    def validate(self, op: Operation) -> Operation:
        errors: List[str] = []
        if not op.tool_id:
            errors.append("tool_id required")
        if op.permission is None:
            errors.append("permission required")
        tool = self.registry.get(op.tool_id) if op.tool_id else None
        if tool is None and op.tool_id:
            errors.append(f"unknown tool: {op.tool_id}")
        elif tool is not None and op.permission is not None and not tool.supports(op.permission):
            errors.append(f"tool does not support {op.permission.value}")
        op.validation_errors = errors
        if errors:
            op.status = OperationStatus.FAILED
            self.audit.append("validate_failed", operation_id=op.operation_id, tool_id=op.tool_id, detail={"errors": errors})
        else:
            op.status = OperationStatus.VALIDATED
            self.audit.append("validate_ok", operation_id=op.operation_id, tool_id=op.tool_id)
        return op

    def authorize(self, op: Operation, *, decision: Optional[AuthorizationDecision] = None, allow: Optional[bool] = None, reason: str = "") -> Operation:
        if decision is None:
            if allow is None:
                if op.permission == ToolPermission.READ and self.auto_authorize_read:
                    decision = AuthorizationDecision(allowed=True, reason=reason or "auto-authorize READ")
                elif op.permission == ToolPermission.PROPOSE:
                    decision = AuthorizationDecision(allowed=True, reason=reason or "PROPOSE is non-mutating")
                else:
                    decision = AuthorizationDecision(allowed=False, reason=reason or "EXECUTE requires explicit authorization")
            else:
                decision = AuthorizationDecision(allowed=bool(allow), reason=reason or ("explicit allow" if allow else "explicit deny"), decided_by="caller")
        op.authorization = decision
        if decision.allowed:
            op.status = OperationStatus.AUTHORIZED
            self.audit.append("authorize_allow", operation_id=op.operation_id, tool_id=op.tool_id, detail=decision.to_dict())
        else:
            op.status = OperationStatus.DENIED
            self.audit.append("authorize_deny", operation_id=op.operation_id, tool_id=op.tool_id, detail=decision.to_dict())
            if op.subject:
                rec = self.memory.record(RecordType.FAILURE, op.subject, {"reason": "authorization_denied", "authorization": decision.to_dict(), "proposal": op.proposal, "operation_id": op.operation_id}, Provenance(source="execution:authorize", operation_id=op.operation_id, is_observed=True, agent_id=self.agent_id), related_ids=[op.operation_id], tags=["authorization_denied"])
                op.memory_ids.append(rec.record_id)
        return op

    def execute(self, op: Operation) -> Operation:
        if op.status == OperationStatus.DENIED:
            return op
        if op.permission == ToolPermission.EXECUTE:
            if not op.authorization or not op.authorization.allowed:
                op.status = OperationStatus.DENIED
                self.audit.append("execute_blocked", operation_id=op.operation_id, tool_id=op.tool_id, detail={"reason": "not authorized"})
                return op
        authorized = bool(op.authorization and op.authorization.allowed)
        if op.permission == ToolPermission.READ and self.auto_authorize_read:
            authorized = True
        assert op.tool_id is not None and op.permission is not None
        result = self.registry.invoke(op.tool_id, op.arguments, permission=op.permission, dry_run=op.dry_run, authorized=authorized, idempotency_key=op.idempotency_key, operation_id=op.operation_id)
        op.result = result
        if result.status in (ToolOpStatus.SUCCEEDED, ToolOpStatus.DRY_RUN):
            op.status = OperationStatus.EXECUTED
            self.audit.append("execute_ok", operation_id=op.operation_id, tool_id=op.tool_id, detail={"status": result.status.value})
        else:
            op.status = OperationStatus.FAILED
            self.audit.append("execute_failed", operation_id=op.operation_id, tool_id=op.tool_id, detail=result.to_dict())
            if op.subject and result.error:
                rec = self.memory.record(RecordType.FAILURE, op.subject, {"error": result.error.to_dict(), "operation_id": op.operation_id, "arguments": op.arguments}, Provenance(source=f"tool:{op.tool_id}", operation_id=op.operation_id, is_observed=True, agent_id=self.agent_id), related_ids=[op.operation_id], tags=["tool_failure"])
                op.memory_ids.append(rec.record_id)
        return op

    def observe_and_record(self, op: Operation, *, observation: Optional[Dict[str, Any]] = None, confidence: Optional[float] = None) -> Operation:
        if op.subject is None:
            op.status = OperationStatus.OBSERVED
            return op
        content: Dict[str, Any] = {"operation_id": op.operation_id, "tool_id": op.tool_id, "status": op.status.value, "dry_run": op.dry_run}
        if op.result:
            content["result"] = op.result.to_dict()
        if observation:
            content["observation"] = observation
        if op.rationale:
            content["rationale"] = op.rationale
        is_failure = op.status == OperationStatus.FAILED or (op.result and op.result.status not in (ToolOpStatus.SUCCEEDED, ToolOpStatus.DRY_RUN))
        rtype = RecordType.FAILURE if is_failure else RecordType.OUTCOME
        if op.dry_run:
            rtype = RecordType.EVENT
        rec = self.memory.record(rtype, op.subject, content, Provenance(source=f"tool:{op.tool_id}" if op.tool_id else "execution", operation_id=op.operation_id, confidence=confidence, is_observed=True, agent_id=self.agent_id), related_ids=[op.operation_id] + list(op.memory_ids[:5]), tags=["outcome" if not is_failure else "failure"])
        op.memory_ids.append(rec.record_id)
        op.status = OperationStatus.RECORDED
        self.audit.append("record", operation_id=op.operation_id, tool_id=op.tool_id, detail={"record_id": rec.record_id, "record_type": rtype.value})
        return op

    def run_read(self, tool_id: str, arguments: Dict[str, Any], *, subject: Optional[str] = None) -> Operation:
        op = self.new_operation(tool_id=tool_id, subject=subject)
        self.propose(op, tool_id, arguments, permission=ToolPermission.READ)
        self.validate(op)
        self.authorize(op)
        self.execute(op)
        self.observe_and_record(op)
        return op

    def run_execute(self, tool_id: str, arguments: Dict[str, Any], *, subject: Optional[str] = None, rationale: Optional[str] = None, allow: bool = False, dry_run: bool = False, idempotency_key: Optional[str] = None, observation: Optional[Dict[str, Any]] = None) -> Operation:
        op = self.new_operation(tool_id=tool_id, subject=subject, dry_run=dry_run, idempotency_key=idempotency_key)
        self.propose(op, tool_id, arguments, permission=ToolPermission.EXECUTE, rationale=rationale)
        self.validate(op)
        if op.status == OperationStatus.FAILED:
            return op
        self.authorize(op, allow=allow, reason="caller decision" if allow else "caller denied")
        if op.status == OperationStatus.DENIED:
            return op
        self.execute(op)
        self.observe_and_record(op, observation=observation)
        return op

    def get_operation(self, operation_id: str) -> Optional[Operation]:
        return self._ops.get(operation_id)
