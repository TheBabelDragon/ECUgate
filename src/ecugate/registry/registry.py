"""Typed tool registry with discovery, validation, and policy enforcement."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ecugate.registry.models import (
    ExecutionPolicy,
    OperationStatus,
    ToolDefinition,
    ToolError,
    ToolPermission,
    ToolResult,
    new_operation_id,
    utc_now_iso,
)
from ecugate.registry.schema_validate import SchemaValidationError, validate


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._idempotency_cache: Dict[str, ToolResult] = {}

    def register(self, tool: ToolDefinition) -> None:
        if not tool.tool_id:
            raise ValueError("tool_id is required")
        if not tool.version:
            raise ValueError("version is required")
        if tool.handler is None:
            raise ValueError(f"tool {tool.tool_id} has no handler")
        key = self._key(tool.tool_id, tool.version)
        if key in self._tools:
            raise ValueError(f"tool already registered: {key}")
        self._tools[key] = tool

    def unregister(self, tool_id: str, version: str) -> None:
        self._tools.pop(self._key(tool_id, version), None)

    def discover(self, permission: Optional[ToolPermission] = None) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for tool in self._tools.values():
            if permission is not None and not tool.supports(permission):
                continue
            out.append(tool.discovery_dict())
        return sorted(out, key=lambda d: (d["tool_id"], d["version"]))

    def get(self, tool_id: str, version: Optional[str] = None) -> Optional[ToolDefinition]:
        if version:
            return self._tools.get(self._key(tool_id, version))
        matches = [t for t in self._tools.values() if t.tool_id == tool_id]
        if not matches:
            return None
        return sorted(matches, key=lambda t: t.version)[-1]

    def invoke(
        self,
        tool_id: str,
        arguments: Dict[str, Any],
        *,
        permission: ToolPermission,
        version: Optional[str] = None,
        dry_run: bool = False,
        authorized: bool = False,
        idempotency_key: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> ToolResult:
        op_id = operation_id or new_operation_id()
        started = utc_now_iso()

        if idempotency_key and idempotency_key in self._idempotency_cache:
            cached = self._idempotency_cache[idempotency_key]
            return ToolResult(
                operation_id=cached.operation_id,
                tool_id=cached.tool_id,
                status=cached.status,
                output=cached.output,
                error=cached.error,
                started_at=cached.started_at,
                finished_at=cached.finished_at,
                dry_run=cached.dry_run,
                idempotency_key=idempotency_key,
            )

        tool = self.get(tool_id, version)
        if tool is None:
            return self._fail(op_id, tool_id, started, "unknown_tool", f"unknown tool: {tool_id}", dry_run)

        if not tool.supports(permission):
            return self._fail(
                op_id, tool_id, started, "permission_denied",
                f"tool {tool_id} does not support permission {permission.value}", dry_run,
            )

        if permission == ToolPermission.EXECUTE and tool.policy.requires_authorization and not authorized:
            return self._fail(
                op_id, tool_id, started, "authorization_required",
                "EXECUTE requires explicit authorization", dry_run,
            )

        if dry_run and not tool.policy.allow_dry_run:
            return self._fail(op_id, tool_id, started, "dry_run_not_allowed", "dry-run not allowed", dry_run)

        try:
            raw = json.dumps(arguments, separators=(",", ":"), sort_keys=True)
        except (TypeError, ValueError) as e:
            return self._fail(op_id, tool_id, started, "invalid_input", f"not JSON-serializable: {e}", dry_run)
        if len(raw.encode("utf-8")) > tool.policy.max_input_bytes:
            return self._fail(op_id, tool_id, started, "input_too_large", "input exceeds max_input_bytes", dry_run)

        try:
            validate(arguments, tool.input_schema)
        except SchemaValidationError as e:
            return self._fail(
                op_id, tool_id, started, "schema_validation_failed", e.message, dry_run,
                details={"path": e.path},
            )

        if dry_run:
            return ToolResult(
                operation_id=op_id, tool_id=tool_id, status=OperationStatus.DRY_RUN,
                output={"dry_run": True, "would_execute": True, "arguments": arguments},
                started_at=started, finished_at=utc_now_iso(), dry_run=True,
                idempotency_key=idempotency_key,
            )

        try:
            assert tool.handler is not None
            output = tool.handler(**arguments) if arguments else tool.handler()
            if not isinstance(output, dict):
                output = {"result": output}
            out_raw = json.dumps(output, separators=(",", ":"), sort_keys=True)
            if len(out_raw.encode("utf-8")) > tool.policy.max_output_bytes:
                return self._fail(op_id, tool_id, started, "output_too_large", "output exceeds max_output_bytes", dry_run)
            if tool.output_schema:
                try:
                    validate(output, tool.output_schema)
                except SchemaValidationError as e:
                    return self._fail(
                        op_id, tool_id, started, "output_schema_failed", e.message, dry_run,
                        details={"path": e.path},
                    )
            result = ToolResult(
                operation_id=op_id, tool_id=tool_id, status=OperationStatus.SUCCEEDED,
                output=output, started_at=started, finished_at=utc_now_iso(),
                dry_run=False, idempotency_key=idempotency_key,
            )
        except Exception as e:
            result = self._fail(op_id, tool_id, started, "handler_error", str(e), dry_run)

        if tool.policy.idempotent and idempotency_key and result.status == OperationStatus.SUCCEEDED:
            self._idempotency_cache[idempotency_key] = result
        return result

    def _fail(
        self, op_id: str, tool_id: str, started: str, code: str, message: str, dry_run: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> ToolResult:
        status = OperationStatus.DENIED if code in ("permission_denied", "authorization_required") else OperationStatus.FAILED
        return ToolResult(
            operation_id=op_id, tool_id=tool_id, status=status,
            error=ToolError(code=code, message=message, details=details),
            started_at=started, finished_at=utc_now_iso(), dry_run=dry_run,
        )

    @staticmethod
    def _key(tool_id: str, version: str) -> str:
        return f"{tool_id}@{version}"
