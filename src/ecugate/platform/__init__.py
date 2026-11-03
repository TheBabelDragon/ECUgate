"""ECUgate modular vehicle-controller platform.

Architecture and software contracts for universal modular vehicle-controller
replacement. No physical engine control, actuator operation, ECU flashing or
vehicle writes are implemented in this package.
"""

from ecugate.platform.models import (
    SCHEMA_VERSION,
    CaptureStatus,
    CompatibilityResult,
    CompatibilityStatus,
    ControllerProfile,
    HardwareModule,
    ModuleKind,
    VehicleProfile,
)
from ecugate.platform.backup import ClonePackage, CaptureRegion, compute_package_digest
from ecugate.platform.compatibility import CompatibilityEngine
from ecugate.platform.workflows import WorkflowEngine, WorkflowKind
from ecugate.platform.simulator import PlatformSimulator

__all__ = [
    "SCHEMA_VERSION",
    "CaptureStatus",
    "CompatibilityResult",
    "CompatibilityStatus",
    "ControllerProfile",
    "HardwareModule",
    "ModuleKind",
    "VehicleProfile",
    "ClonePackage",
    "CaptureRegion",
    "compute_package_digest",
    "CompatibilityEngine",
    "WorkflowEngine",
    "WorkflowKind",
    "PlatformSimulator",
]
