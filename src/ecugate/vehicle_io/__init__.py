"""Read-only vehicle I/O (ELM327-compatible OBD-II). Never authorizes writes."""

from ecugate.vehicle_io.models import (
    AdapterIdentity,
    DiagnosticOutcome,
    DiagnosticResult,
    SessionInfo,
)
from ecugate.vehicle_io.session import VehicleSession
from ecugate.vehicle_io.transport import FakeSerialTransport, PyserialTransport, TransportError
from ecugate.vehicle_io.policy import check_operation, POLICY_VERSION

__all__ = [
    "AdapterIdentity",
    "DiagnosticOutcome",
    "DiagnosticResult",
    "SessionInfo",
    "VehicleSession",
    "FakeSerialTransport",
    "PyserialTransport",
    "TransportError",
    "check_operation",
    "POLICY_VERSION",
]
