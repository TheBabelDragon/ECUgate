"""Tool registry models: definitions, permissions, results, policies."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4


class ToolPermission(str, enum.Enum):
    READ = "read"
    PROPOSE = "propose"
    EXECUTE = "execute"


class OperationStatus(str, enum.Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    AUTHORIZED = "authorized"
    DENIED = "denied"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DRY_RUN = "dry_run"


@dataclass(frozen=True)
class ExecutionPolicy:
    timeout_seconds: float = 30.0
    max_input_bytes: int = 65_536
    max_output_bytes: int = 65_536
    allow_dry_run: bool = True
    idempotent: bool = False
    requires_authorization: bool = True


@dataclass
class ToolDefinition:
    tool_id: str
    version: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    permissions: List[ToolPermission]
    policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)
    handler: Optional[Callable[..., Any]] = field(default=None, repr=False, compare=False)

    def supports(self, permission: ToolPermission) -> bool:
        return permission in self.permissions

    def discovery_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "version": self.version,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "permissions": [p.value for p in self.permissions],
            "policy": {
                "timeout_seconds": self.policy.timeout_seconds,
                "max_input_bytes": self.policy.max_input_bytes,
                "max_output_bytes": self.policy.max_output_bytes,
                "allow_dry_run": self.policy.allow_dry_run,
                "idempotent": self.policy.idempotent,
                "requires_authorization": self.policy.requires_authorization,
            },
        }


@dataclass
class ToolError:
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class ToolResult:
    operation_id: str
    tool_id: str
    status: OperationStatus
    output: Optional[Dict[str, Any]] = None
    error: Optional[ToolError] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    dry_run: bool = False
    idempotency_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "tool_id": self.tool_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error.to_dict() if self.error else None,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "dry_run": self.dry_run,
            "idempotency_key": self.idempotency_key,
        }


def new_operation_id() -> str:
    return str(uuid4())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
