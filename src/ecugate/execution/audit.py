"""Append-only audit trail for authorization and execution decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuditEntry:
    entry_id: str
    timestamp: str
    event_type: str
    operation_id: Optional[str]
    tool_id: Optional[str]
    detail: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "operation_id": self.operation_id,
            "tool_id": self.tool_id,
            "detail": self.detail,
        }


class AuditLog:
    def __init__(self, path: Optional[str] = None) -> None:
        self._entries: List[AuditEntry] = []
        self._path = path
        if path:
            open(path, "a", encoding="utf-8").close()

    def append(
        self,
        event_type: str,
        *,
        operation_id: Optional[str] = None,
        tool_id: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            entry_id=str(uuid4()),
            timestamp=utc_now_iso(),
            event_type=event_type,
            operation_id=operation_id,
            tool_id=tool_id,
            detail=detail or {},
        )
        self._entries.append(entry)
        if self._path:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
        return entry

    def list(self, limit: int = 200) -> List[AuditEntry]:
        return list(self._entries[-limit:])

    def clear_memory(self) -> None:
        self._entries.clear()
