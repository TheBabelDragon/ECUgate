"""Read-only vehicle diagnostic session lifecycle."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ecugate.vehicle_io import elm327, obd2
from ecugate.vehicle_io.models import (
    AdapterIdentity,
    DiagnosticOutcome,
    DiagnosticResult,
    SessionInfo,
    new_session_id,
    utc_now_iso,
)
from ecugate.vehicle_io.policy import check_operation
from ecugate.vehicle_io.transport import SerialTransport, TransportError


class VehicleSession:
    """Bounded read-only session. Writes/clears/programming are rejected before TX."""

    def __init__(self, transport: SerialTransport, device_path: str) -> None:
        self.transport = transport
        self.device_path = device_path
        self.session_id = new_session_id()
        self._open = False
        self.adapter: Optional[AdapterIdentity] = None
        self.protocol: Optional[str] = None
        self.audit: List[Dict[str, Any]] = []

    def _audit(self, event: str, **detail: Any) -> None:
        self.audit.append({"event": event, "session_id": self.session_id, "ts": utc_now_iso(), **detail})

    def open(self) -> SessionInfo:
        decision = check_operation("session_open")
        if not decision.allowed:
            raise PermissionError(decision.reason)
        self.transport.open()
        self._open = True
        d = check_operation("adapter_identify")
        self.adapter = elm327.identify_adapter(self.transport, self.device_path)
        self._audit("adapter_identify", adapter=self.adapter.to_dict(), permission=d.to_dict())
        d2 = check_operation("adapter_init")
        raws, proto = elm327.initialize_elm(self.transport)
        self.protocol = proto
        if self.adapter:
            self.adapter.protocol = proto
            self.adapter.raw_responses.extend(raws)
        self._audit("adapter_init", protocol=proto, permission=d2.to_dict())
        return SessionInfo(
            session_id=self.session_id,
            device_path=self.device_path,
            read_only=True,
            adapter=self.adapter,
            protocol=proto,
        )

    def close(self) -> None:
        check_operation("session_close")
        try:
            self.transport.close()
        finally:
            self._open = False
            self._audit("session_close")

    def read_pid(self, pid: str) -> DiagnosticResult:
        started = utc_now_iso()
        decision = check_operation("read_pid", mode="01", pid=pid)
        if not decision.allowed:
            return DiagnosticResult(
                operation="read_pid",
                outcome=DiagnosticOutcome.DENIED,
                session_id=self.session_id,
                device_path=self.device_path,
                pid=pid,
                mode="01",
                message=decision.reason,
                started_at=started,
                finished_at=utc_now_iso(),
                permission=decision.to_dict(),
            )
        if not self._open:
            return DiagnosticResult(
                operation="read_pid",
                outcome=DiagnosticOutcome.FAILED,
                session_id=self.session_id,
                message="session not open",
                started_at=started,
                finished_at=utc_now_iso(),
                permission=decision.to_dict(),
            )
        try:
            raw = elm327.send_obd(self.transport, "01", pid)
        except TransportError as e:
            res = DiagnosticResult(
                operation="read_pid",
                outcome=DiagnosticOutcome.TIMEOUT if "timeout" in str(e).lower() else DiagnosticOutcome.FAILED,
                session_id=self.session_id,
                device_path=self.device_path,
                pid=pid,
                mode="01",
                message=str(e),
                started_at=started,
                finished_at=utc_now_iso(),
                permission=decision.to_dict(),
            )
            self._audit("read_pid", result=res.to_dict())
            return res
        outcome, value, unit, meta = obd2.parse_mode01_response(raw, pid)
        res = DiagnosticResult(
            operation="read_pid",
            outcome=outcome,
            session_id=self.session_id,
            device_path=self.device_path,
            value=value,
            unit=unit,
            pid=pid.lower().replace("0x", "").zfill(2),
            mode="01",
            raw=raw,
            started_at=started,
            finished_at=utc_now_iso(),
            permission=decision.to_dict(),
            decoding=meta,
        )
        self._audit("read_pid", result=res.to_dict())
        return res

    def read_dtcs(self) -> DiagnosticResult:
        started = utc_now_iso()
        decision = check_operation("read_dtcs", mode="03")
        if not decision.allowed:
            return DiagnosticResult(
                operation="read_dtcs",
                outcome=DiagnosticOutcome.DENIED,
                session_id=self.session_id,
                message=decision.reason,
                started_at=started,
                finished_at=utc_now_iso(),
                permission=decision.to_dict(),
            )
        try:
            raw = elm327.send_obd(self.transport, "03", "")
        except TransportError as e:
            return DiagnosticResult(
                operation="read_dtcs",
                outcome=DiagnosticOutcome.FAILED,
                session_id=self.session_id,
                message=str(e),
                started_at=started,
                finished_at=utc_now_iso(),
                permission=decision.to_dict(),
            )
        outcome, value, meta = obd2.parse_mode03_dtcs(raw)
        res = DiagnosticResult(
            operation="read_dtcs",
            outcome=outcome,
            session_id=self.session_id,
            device_path=self.device_path,
            value=value,
            mode="03",
            raw=raw,
            started_at=started,
            finished_at=utc_now_iso(),
            permission=decision.to_dict(),
            decoding=meta,
        )
        self._audit("read_dtcs", result=res.to_dict())
        return res

    def read_vin(self) -> DiagnosticResult:
        started = utc_now_iso()
        decision = check_operation("read_vin", mode="09")
        if not decision.allowed:
            return DiagnosticResult(
                operation="read_vin",
                outcome=DiagnosticOutcome.DENIED,
                session_id=self.session_id,
                message=decision.reason,
                started_at=started,
                finished_at=utc_now_iso(),
                permission=decision.to_dict(),
            )
        try:
            raw = elm327.send_obd(self.transport, "09", "02")
        except TransportError as e:
            return DiagnosticResult(
                operation="read_vin",
                outcome=DiagnosticOutcome.FAILED,
                session_id=self.session_id,
                message=str(e),
                started_at=started,
                finished_at=utc_now_iso(),
                permission=decision.to_dict(),
            )
        outcome, value, meta = obd2.parse_mode09_vin(raw)
        res = DiagnosticResult(
            operation="read_vin",
            outcome=outcome,
            session_id=self.session_id,
            device_path=self.device_path,
            value=value,
            mode="09",
            pid="02",
            raw=raw,
            started_at=started,
            finished_at=utc_now_iso(),
            permission=decision.to_dict(),
            decoding=meta,
        )
        self._audit("read_vin", result=res.to_dict())
        return res

    def reject_clear_dtcs(self) -> DiagnosticResult:
        decision = check_operation("clear_dtcs", mode="04")
        return DiagnosticResult(
            operation="clear_dtcs",
            outcome=DiagnosticOutcome.DENIED,
            session_id=self.session_id,
            mode="04",
            message=decision.reason,
            permission=decision.to_dict(),
            finished_at=utc_now_iso(),
        )
