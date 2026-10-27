"""Typed models for read-only vehicle I/O results and identities."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DiagnosticOutcome(str, enum.Enum):
    SUCCEEDED = "succeeded"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    MALFORMED = "malformed"
    TIMEOUT = "timeout"
    DENIED = "denied"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"


class ProtocolFamily(str, enum.Enum):
    UNKNOWN = "unknown"
    ISO_9141 = "iso_9141"
    ISO_14230 = "iso_14230"
    ISO_15765 = "iso_15765"
    SAE_J1850_PWM = "sae_j1850_pwm"
    SAE_J1850_VPW = "sae_j1850_vpw"
    AUTO = "auto"


@dataclass
class AdapterIdentity:
    device_path: str
    adapter_class: str = "elm327_compatible"
    firmware: Optional[str] = None
    protocol: Optional[str] = None
    vendor_id: Optional[str] = None
    product_id: Optional[str] = None
    serial: Optional[str] = None
    raw_responses: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_path": self.device_path,
            "adapter_class": self.adapter_class,
            "firmware": self.firmware,
            "protocol": self.protocol,
            "vendor_id": self.vendor_id,
            "product_id": self.product_id,
            "serial": self.serial,
            "raw_responses": list(self.raw_responses),
            "evidence": list(self.evidence),
        }


@dataclass
class VehicleIdentity:
    vin: Optional[str] = None
    vin_outcome: DiagnosticOutcome = DiagnosticOutcome.UNAVAILABLE
    protocol: Optional[str] = None
    evidence: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vin": self.vin,
            "vin_outcome": self.vin_outcome.value,
            "protocol": self.protocol,
            "evidence": list(self.evidence),
        }


@dataclass
class DiagnosticResult:
    operation: str
    outcome: DiagnosticOutcome
    session_id: str
    device_path: Optional[str] = None
    value: Any = None
    unit: Optional[str] = None
    pid: Optional[str] = None
    mode: Optional[str] = None
    raw: Optional[str] = None
    message: Optional[str] = None
    started_at: str = field(default_factory=utc_now_iso)
    finished_at: Optional[str] = None
    permission: Optional[Dict[str, Any]] = None
    decoding: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "outcome": self.outcome.value,
            "session_id": self.session_id,
            "device_path": self.device_path,
            "value": self.value,
            "unit": self.unit,
            "pid": self.pid,
            "mode": self.mode,
            "raw": self.raw,
            "message": self.message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "permission": self.permission,
            "decoding": self.decoding,
            "authorized_write": False,
        }


@dataclass
class SessionInfo:
    session_id: str
    device_path: str
    read_only: bool = True
    adapter: Optional[AdapterIdentity] = None
    opened_at: str = field(default_factory=utc_now_iso)
    closed_at: Optional[str] = None
    protocol: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "device_path": self.device_path,
            "read_only": self.read_only,
            "adapter": self.adapter.to_dict() if self.adapter else None,
            "opened_at": self.opened_at,
            "closed_at": self.closed_at,
            "protocol": self.protocol,
            "authorized_write": False,
        }


def new_session_id() -> str:
    return str(uuid4())
