"""Allowlist enforcement for vehicle I/O — read-only boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional

BLOCKED_MODES: FrozenSet[str] = frozenset(
    {
        "04",
        "05",
        "06",
        "07",
        "08",
        "0a",
        "10",
        "11",
        "27",
        "2e",
        "31",
        "34",
        "35",
        "36",
        "37",
        "3d",
    }
)

ALLOWED_OPERATIONS: FrozenSet[str] = frozenset(
    {
        "adapter_identify",
        "adapter_init",
        "protocol_discover",
        "pid_support",
        "read_pid",
        "read_dtcs",
        "read_vin",
        "session_open",
        "session_close",
    }
)

ALLOWED_MODE01_PIDS: FrozenSet[str] = frozenset({"00", "0c", "0d", "05", "04"})

POLICY_VERSION = "vehicle_io.read_only.v1"


@dataclass
class PolicyDecision:
    allowed: bool
    operation: str
    reason: str
    policy_version: str = POLICY_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "operation": self.operation,
            "reason": self.reason,
            "policy_version": self.policy_version,
        }


def check_operation(operation: str, *, mode: Optional[str] = None, pid: Optional[str] = None) -> PolicyDecision:
    op = (operation or "").strip().lower()
    if op not in ALLOWED_OPERATIONS:
        return PolicyDecision(False, op, f"operation not in allowlist: {op}")

    if mode is not None:
        m = mode.strip().lower().replace("0x", "")
        if m in BLOCKED_MODES:
            return PolicyDecision(False, op, f"blocked service mode {m}")
        if m not in ("01", "03", "09") and op not in (
            "adapter_identify",
            "adapter_init",
            "protocol_discover",
            "session_open",
            "session_close",
        ):
            return PolicyDecision(False, op, f"mode {m} not permitted in read-only vehicle_io")

    if op == "read_pid" and pid is not None:
        p = pid.strip().lower().replace("0x", "").zfill(2)
        if p not in ALLOWED_MODE01_PIDS:
            return PolicyDecision(False, op, f"PID {p} not in read-only allowlist")

    return PolicyDecision(True, op, "allowlisted read-only operation")
