"""Typed models for write preflight, authorization, and execution receipts."""

from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

POLICY_VERSION = "write_preflight.v1"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def digest_payload(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


class OperationClass(str, enum.Enum):
    READ = "read"
    DIAGNOSTIC = "diagnostic"
    WRITE = "write"
    FLASH = "flash"
    CODING = "coding"
    CLEAR = "clear"
    CONTROL = "control"


class Confidence(str, enum.Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    USER_PROVIDED = "user_provided"
    UNKNOWN = "unknown"


class PreflightDecision(str, enum.Enum):
    READY = "ready"
    BLOCKED = "blocked"


class ExecutionMode(str, enum.Enum):
    SIMULATOR = "simulator"
    PHYSICAL = "physical"
    DRY_RUN = "dry_run"


class ExecutionOutcome(str, enum.Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"
    DENIED = "denied"
    DISCONNECTED = "disconnected"


BLOCKER_CODES = (
    "target_identity_unverified",
    "unsupported_target_profile",
    "adapter_protocol_unverified",
    "bench_topology_incomplete",
    "power_requirements_unverified",
    "power_measurement_out_of_range",
    "evidence_stale",
    "artifact_incompatible",
    "artifact_integrity_unverified",
    "authorization_missing",
    "authorization_scope_mismatch",
    "authorization_expired",
    "session_invalid",
    "recovery_plan_missing",
    "operation_not_allowlisted",
    "physical_write_not_implemented",
    "grant_already_consumed",
    "precondition_changed",
)


@dataclass
class EvidenceRecord:
    source: str
    timestamp: str
    provenance: str
    verification_method: str
    confidence: Confidence = Confidence.UNKNOWN
    expires_at: Optional[str] = None
    detail: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    def is_fresh(self, *, now: Optional[datetime] = None) -> bool:
        if self.expires_at is None:
            return True
        try:
            exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        return (now or utc_now()) <= exp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "timestamp": self.timestamp,
            "provenance": self.provenance,
            "verification_method": self.verification_method,
            "confidence": self.confidence.value,
            "expires_at": self.expires_at,
            "detail": self.detail,
            "raw": self.raw,
        }


@dataclass
class TargetIdentity:
    ecu_id: Optional[str] = None
    hardware_id: Optional[str] = None
    software_id: Optional[str] = None
    calibration_id: Optional[str] = None
    family: Optional[str] = None
    verified: bool = False
    confidence: Confidence = Confidence.UNKNOWN
    evidence: List[EvidenceRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ecu_id": self.ecu_id,
            "hardware_id": self.hardware_id,
            "software_id": self.software_id,
            "calibration_id": self.calibration_id,
            "family": self.family,
            "verified": self.verified,
            "confidence": self.confidence.value,
            "evidence": [e.to_dict() for e in self.evidence],
        }

    def identity_digest(self) -> str:
        return digest_payload(
            {
                "ecu_id": self.ecu_id,
                "hardware_id": self.hardware_id,
                "software_id": self.software_id,
                "calibration_id": self.calibration_id,
                "family": self.family,
            }
        )


@dataclass
class OperationSpec:
    operation_id: str
    operation_class: OperationClass
    required_capabilities: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    permitted_target_families: List[str] = field(default_factory=list)
    changes_state: bool = False
    requires_artifact: bool = False
    requires_authorization: bool = True
    requires_recovery_plan: bool = False
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "operation_class": self.operation_class.value,
            "required_capabilities": list(self.required_capabilities),
            "preconditions": list(self.preconditions),
            "permitted_target_families": list(self.permitted_target_families),
            "changes_state": self.changes_state,
            "requires_artifact": self.requires_artifact,
            "requires_authorization": self.requires_authorization,
            "requires_recovery_plan": self.requires_recovery_plan,
            "description": self.description,
        }


@dataclass
class PowerEvidence:
    voltage_v: Optional[float] = None
    current_a: Optional[float] = None
    voltage_min: Optional[float] = None
    voltage_max: Optional[float] = None
    measured: bool = False
    evidence: List[EvidenceRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "voltage_v": self.voltage_v,
            "current_a": self.current_a,
            "voltage_min": self.voltage_min,
            "voltage_max": self.voltage_max,
            "measured": self.measured,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class BenchConfiguration:
    target: TargetIdentity
    adapter_id: Optional[str] = None
    programmer_id: Optional[str] = None
    power_source_id: Optional[str] = None
    protocol: Optional[str] = None
    relationships_confirmed: bool = False
    power: PowerEvidence = field(default_factory=PowerEvidence)
    session_id: Optional[str] = None
    session_valid: bool = False
    recovery_plan: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target.to_dict(),
            "adapter_id": self.adapter_id,
            "programmer_id": self.programmer_id,
            "power_source_id": self.power_source_id,
            "protocol": self.protocol,
            "relationships_confirmed": self.relationships_confirmed,
            "power": self.power.to_dict(),
            "session_id": self.session_id,
            "session_valid": self.session_valid,
            "recovery_plan": self.recovery_plan,
        }


@dataclass
class ArtifactSpec:
    artifact_id: Optional[str] = None
    digest: Optional[str] = None
    compatible_families: List[str] = field(default_factory=list)
    provenance: Optional[str] = None
    integrity_verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "digest": self.digest,
            "compatible_families": list(self.compatible_families),
            "provenance": self.provenance,
            "integrity_verified": self.integrity_verified,
        }


@dataclass
class OperationProposal:
    operation_id: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    bench: Optional[BenchConfiguration] = None
    artifact: Optional[ArtifactSpec] = None
    execution_mode: ExecutionMode = ExecutionMode.SIMULATOR
    proposal_id: str = field(default_factory=lambda: str(uuid4()))

    def operation_digest(self) -> str:
        return digest_payload(
            {
                "operation_id": self.operation_id,
                "arguments": self.arguments,
                "target": self.bench.target.to_dict() if self.bench else None,
                "artifact_digest": self.artifact.digest if self.artifact else None,
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "operation_id": self.operation_id,
            "arguments": self.arguments,
            "bench": self.bench.to_dict() if self.bench else None,
            "artifact": self.artifact.to_dict() if self.artifact else None,
            "execution_mode": self.execution_mode.value,
            "operation_digest": self.operation_digest(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OperationProposal":
        bench = None
        if data.get("bench"):
            b = data["bench"]
            t = b.get("target") or {}
            target = TargetIdentity(
                ecu_id=t.get("ecu_id"),
                hardware_id=t.get("hardware_id"),
                software_id=t.get("software_id"),
                calibration_id=t.get("calibration_id"),
                family=t.get("family"),
                verified=bool(t.get("verified", False)),
                confidence=Confidence(t.get("confidence", "unknown")),
                evidence=[
                    EvidenceRecord(
                        source=e.get("source", ""),
                        timestamp=e.get("timestamp", ""),
                        provenance=e.get("provenance", ""),
                        verification_method=e.get("verification_method", ""),
                        confidence=Confidence(e.get("confidence", "unknown")),
                        expires_at=e.get("expires_at"),
                        detail=e.get("detail"),
                        raw=e.get("raw"),
                    )
                    for e in (t.get("evidence") or [])
                ],
            )
            p = b.get("power") or {}
            power = PowerEvidence(
                voltage_v=p.get("voltage_v"),
                current_a=p.get("current_a"),
                voltage_min=p.get("voltage_min"),
                voltage_max=p.get("voltage_max"),
                measured=bool(p.get("measured", False)),
                evidence=[
                    EvidenceRecord(
                        source=e.get("source", ""),
                        timestamp=e.get("timestamp", ""),
                        provenance=e.get("provenance", ""),
                        verification_method=e.get("verification_method", ""),
                        confidence=Confidence(e.get("confidence", "unknown")),
                        expires_at=e.get("expires_at"),
                        detail=e.get("detail"),
                    )
                    for e in (p.get("evidence") or [])
                ],
            )
            bench = BenchConfiguration(
                target=target,
                adapter_id=b.get("adapter_id"),
                programmer_id=b.get("programmer_id"),
                power_source_id=b.get("power_source_id"),
                protocol=b.get("protocol"),
                relationships_confirmed=bool(b.get("relationships_confirmed", False)),
                power=power,
                session_id=b.get("session_id"),
                session_valid=bool(b.get("session_valid", False)),
                recovery_plan=b.get("recovery_plan"),
            )
        artifact = None
        if data.get("artifact"):
            a = data["artifact"]
            artifact = ArtifactSpec(
                artifact_id=a.get("artifact_id"),
                digest=a.get("digest"),
                compatible_families=list(a.get("compatible_families") or []),
                provenance=a.get("provenance"),
                integrity_verified=bool(a.get("integrity_verified", False)),
            )
        mode = ExecutionMode(data.get("execution_mode", "simulator"))
        return cls(
            operation_id=data["operation_id"],
            arguments=dict(data.get("arguments") or {}),
            bench=bench,
            artifact=artifact,
            execution_mode=mode,
            proposal_id=data.get("proposal_id") or str(uuid4()),
        )


@dataclass
class PreflightResult:
    decision: PreflightDecision
    blockers: List[str]
    warnings: List[str]
    satisfied: List[str]
    evidence_refs: List[str]
    policy_version: str = POLICY_VERSION
    operation_digest: Optional[str] = None
    proposal_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "satisfied": list(self.satisfied),
            "evidence_refs": list(self.evidence_refs),
            "policy_version": self.policy_version,
            "operation_digest": self.operation_digest,
            "proposal_id": self.proposal_id,
            "ready": self.decision == PreflightDecision.READY,
            "authorized": False,
        }


@dataclass
class AuthorizationGrant:
    grant_id: str
    issuer: str
    target_digest: str
    operation_digest: str
    artifact_digest: Optional[str]
    scope: str
    issued_at: str
    expires_at: str
    single_use: bool = True
    consumed: bool = False
    revoked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grant_id": self.grant_id,
            "issuer": self.issuer,
            "target_digest": self.target_digest,
            "operation_digest": self.operation_digest,
            "artifact_digest": self.artifact_digest,
            "scope": self.scope,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "single_use": self.single_use,
            "consumed": self.consumed,
            "revoked": self.revoked,
        }


@dataclass
class ExecutionReceipt:
    receipt_id: str
    operation_id: str
    authorization_ref: Optional[str]
    execution_mode: ExecutionMode
    outcome: ExecutionOutcome
    started_at: str
    finished_at: str
    audit_refs: List[str] = field(default_factory=list)
    message: Optional[str] = None
    preflight: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "operation_id": self.operation_id,
            "authorization_ref": self.authorization_ref,
            "execution_mode": self.execution_mode.value,
            "outcome": self.outcome.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "audit_refs": list(self.audit_refs),
            "message": self.message,
            "preflight": self.preflight,
            "authorized_write": False,
        }
