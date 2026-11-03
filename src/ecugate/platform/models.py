"""Typed models for modular vehicle-controller platform.

All electrical limits, pin maps and capabilities that are not verified remain
explicitly unknown. No manufacturer specifications are invented.
"""

from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


SCHEMA_VERSION = "platform.v1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def digest_payload(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


class Confidence(str, enum.Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    USER_PROVIDED = "user_provided"
    ILLUSTRATIVE = "illustrative"
    UNKNOWN = "unknown"


class CaptureStatus(str, enum.Enum):
    CAPTURED = "captured"
    PROTECTED = "protected"
    UNSUPPORTED = "unsupported"
    UNREADABLE = "unreadable"
    NOT_ATTEMPTED = "not_attempted"


class CompatibilityStatus(str, enum.Enum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    INCOMPLETE = "incomplete"
    UNKNOWN = "unknown"


class ModuleKind(str, enum.Enum):
    COMPUTE = "compute"
    POWER_PROTECTION = "power_protection"
    ANALOG_ACQUISITION = "analog_acquisition"
    CRANK_CAM_CONDITIONING = "crank_cam_conditioning"
    DIGITAL_INPUT = "digital_input"
    OUTPUT_DRIVER = "output_driver"
    COMMUNICATIONS = "communications"
    STORAGE = "storage"
    SAFETY_SUPERVISION = "safety_supervision"
    OTHER = "other"


class SafetyClass(str, enum.Enum):
    DEVELOPMENT = "development"
    SUPERVISORY = "supervisory"
    AUTOMOTIVE_QUALIFIED = "automotive_qualified"
    UNKNOWN = "unknown"


class VerificationStatus(str, enum.Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    ILLUSTRATIVE = "illustrative"
    UNKNOWN = "unknown"


@dataclass
class EvidenceRef:
    source: str
    timestamp: str
    provenance: str
    verification_method: str
    confidence: Confidence = Confidence.UNKNOWN
    detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "timestamp": self.timestamp,
            "provenance": self.provenance,
            "verification_method": self.verification_method,
            "confidence": self.confidence.value,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceRef":
        return cls(
            source=data.get("source", ""),
            timestamp=data.get("timestamp", ""),
            provenance=data.get("provenance", ""),
            verification_method=data.get("verification_method", ""),
            confidence=Confidence(data.get("confidence", "unknown")),
            detail=data.get("detail"),
        )


@dataclass
class ElectricalSpec:
    """Electrical characteristics. Unknown values stay None / unknown."""

    voltage_nominal_v: Optional[float] = None
    voltage_min_v: Optional[float] = None
    voltage_max_v: Optional[float] = None
    current_max_a: Optional[float] = None
    isolation: Optional[str] = None
    protection: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    verification: VerificationStatus = VerificationStatus.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "voltage_nominal_v": self.voltage_nominal_v,
            "voltage_min_v": self.voltage_min_v,
            "voltage_max_v": self.voltage_max_v,
            "current_max_a": self.current_max_a,
            "isolation": self.isolation,
            "protection": list(self.protection),
            "notes": self.notes,
            "verification": self.verification.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ElectricalSpec":
        return cls(
            voltage_nominal_v=data.get("voltage_nominal_v"),
            voltage_min_v=data.get("voltage_min_v"),
            voltage_max_v=data.get("voltage_max_v"),
            current_max_a=data.get("current_max_a"),
            isolation=data.get("isolation"),
            protection=list(data.get("protection") or []),
            notes=data.get("notes"),
            verification=VerificationStatus(data.get("verification", "unknown")),
        )


@dataclass
class InterfaceSpec:
    name: str
    protocol: str
    direction: str = "bidirectional"
    required: bool = False
    external_hardware_required: bool = False
    notes: Optional[str] = None
    verification: VerificationStatus = VerificationStatus.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "protocol": self.protocol,
            "direction": self.direction,
            "required": self.required,
            "external_hardware_required": self.external_hardware_required,
            "notes": self.notes,
            "verification": self.verification.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterfaceSpec":
        return cls(
            name=data["name"],
            protocol=data["protocol"],
            direction=data.get("direction", "bidirectional"),
            required=bool(data.get("required", False)),
            external_hardware_required=bool(data.get("external_hardware_required", False)),
            notes=data.get("notes"),
            verification=VerificationStatus(data.get("verification", "unknown")),
        )


@dataclass
class PinMapping:
    """Pin / signal mapping. Only populate when verified; never invent."""

    signal: str
    pin: Optional[str] = None
    connector: Optional[str] = None
    notes: Optional[str] = None
    verification: VerificationStatus = VerificationStatus.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal": self.signal,
            "pin": self.pin,
            "connector": self.connector,
            "notes": self.notes,
            "verification": self.verification.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PinMapping":
        return cls(
            signal=data["signal"],
            pin=data.get("pin"),
            connector=data.get("connector"),
            notes=data.get("notes"),
            verification=VerificationStatus(data.get("verification", "unknown")),
        )


@dataclass
class HardwareModule:
    """Independently replaceable hardware module manifest."""

    module_id: str
    kind: ModuleKind
    name: str
    hardware_revision: str = "unknown"
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    electrical: ElectricalSpec = field(default_factory=ElectricalSpec)
    interfaces: List[InterfaceSpec] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    pin_mappings: List[PinMapping] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    compatibility_constraints: List[str] = field(default_factory=list)
    required_safety_properties: List[str] = field(default_factory=list)
    safety_class: SafetyClass = SafetyClass.UNKNOWN
    evidence: List[EvidenceRef] = field(default_factory=list)
    verification: VerificationStatus = VerificationStatus.UNKNOWN
    notes: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "module_id": self.module_id,
            "kind": self.kind.value,
            "name": self.name,
            "hardware_revision": self.hardware_revision,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "electrical": self.electrical.to_dict(),
            "interfaces": [i.to_dict() for i in self.interfaces],
            "capabilities": list(self.capabilities),
            "pin_mappings": [p.to_dict() for p in self.pin_mappings],
            "dependencies": list(self.dependencies),
            "compatibility_constraints": list(self.compatibility_constraints),
            "required_safety_properties": list(self.required_safety_properties),
            "safety_class": self.safety_class.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "verification": self.verification.value,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HardwareModule":
        return cls(
            module_id=data["module_id"],
            kind=ModuleKind(data["kind"]),
            name=data["name"],
            hardware_revision=data.get("hardware_revision", "unknown"),
            manufacturer=data.get("manufacturer"),
            model=data.get("model"),
            electrical=ElectricalSpec.from_dict(data.get("electrical") or {}),
            interfaces=[InterfaceSpec.from_dict(i) for i in (data.get("interfaces") or [])],
            capabilities=list(data.get("capabilities") or []),
            pin_mappings=[PinMapping.from_dict(p) for p in (data.get("pin_mappings") or [])],
            dependencies=list(data.get("dependencies") or []),
            compatibility_constraints=list(data.get("compatibility_constraints") or []),
            required_safety_properties=list(data.get("required_safety_properties") or []),
            safety_class=SafetyClass(data.get("safety_class", "unknown")),
            evidence=[EvidenceRef.from_dict(e) for e in (data.get("evidence") or [])],
            verification=VerificationStatus(data.get("verification", "unknown")),
            notes=data.get("notes"),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )

    def digest(self) -> str:
        return digest_payload(self.to_dict())


@dataclass
class ControllerProfile:
    """Original or replacement controller identity and capabilities."""

    controller_id: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    hardware_revision: Optional[str] = None
    processor_architecture: Optional[str] = None
    processor_variant: Optional[str] = None
    firmware_id: Optional[str] = None
    bootloader_id: Optional[str] = None
    protocols: List[str] = field(default_factory=list)
    interfaces: List[InterfaceSpec] = field(default_factory=list)
    electrical: ElectricalSpec = field(default_factory=ElectricalSpec)
    timing_requirements: Dict[str, Any] = field(default_factory=dict)
    safety_class: SafetyClass = SafetyClass.UNKNOWN
    known_restrictions: List[str] = field(default_factory=list)
    unsupported_features: List[str] = field(default_factory=list)
    evidence: List[EvidenceRef] = field(default_factory=list)
    verification: VerificationStatus = VerificationStatus.UNKNOWN
    notes: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "controller_id": self.controller_id,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "hardware_revision": self.hardware_revision,
            "processor_architecture": self.processor_architecture,
            "processor_variant": self.processor_variant,
            "firmware_id": self.firmware_id,
            "bootloader_id": self.bootloader_id,
            "protocols": list(self.protocols),
            "interfaces": [i.to_dict() for i in self.interfaces],
            "electrical": self.electrical.to_dict(),
            "timing_requirements": dict(self.timing_requirements),
            "safety_class": self.safety_class.value,
            "known_restrictions": list(self.known_restrictions),
            "unsupported_features": list(self.unsupported_features),
            "evidence": [e.to_dict() for e in self.evidence],
            "verification": self.verification.value,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ControllerProfile":
        return cls(
            controller_id=data["controller_id"],
            manufacturer=data.get("manufacturer"),
            model=data.get("model"),
            hardware_revision=data.get("hardware_revision"),
            processor_architecture=data.get("processor_architecture"),
            processor_variant=data.get("processor_variant"),
            firmware_id=data.get("firmware_id"),
            bootloader_id=data.get("bootloader_id"),
            protocols=list(data.get("protocols") or []),
            interfaces=[InterfaceSpec.from_dict(i) for i in (data.get("interfaces") or [])],
            electrical=ElectricalSpec.from_dict(data.get("electrical") or {}),
            timing_requirements=dict(data.get("timing_requirements") or {}),
            safety_class=SafetyClass(data.get("safety_class", "unknown")),
            known_restrictions=list(data.get("known_restrictions") or []),
            unsupported_features=list(data.get("unsupported_features") or []),
            evidence=[EvidenceRef.from_dict(e) for e in (data.get("evidence") or [])],
            verification=VerificationStatus(data.get("verification", "unknown")),
            notes=data.get("notes"),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )

    def digest(self) -> str:
        return digest_payload(self.to_dict())


@dataclass
class VehicleProfile:
    """Vehicle identity, topology and dependencies."""

    vehicle_id: str
    make: Optional[str] = None
    model: Optional[str] = None
    model_year: Optional[int] = None
    engine_family: Optional[str] = None
    engine_configuration: Optional[str] = None
    transmission: Optional[str] = None
    original_controller_id: Optional[str] = None
    network_interfaces: List[InterfaceSpec] = field(default_factory=list)
    sensor_topology: List[str] = field(default_factory=list)
    actuator_topology: List[str] = field(default_factory=list)
    module_dependencies: List[str] = field(default_factory=list)
    evidence: List[EvidenceRef] = field(default_factory=list)
    verification: VerificationStatus = VerificationStatus.UNKNOWN
    notes: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "vehicle_id": self.vehicle_id,
            "make": self.make,
            "model": self.model,
            "model_year": self.model_year,
            "engine_family": self.engine_family,
            "engine_configuration": self.engine_configuration,
            "transmission": self.transmission,
            "original_controller_id": self.original_controller_id,
            "network_interfaces": [i.to_dict() for i in self.network_interfaces],
            "sensor_topology": list(self.sensor_topology),
            "actuator_topology": list(self.actuator_topology),
            "module_dependencies": list(self.module_dependencies),
            "evidence": [e.to_dict() for e in self.evidence],
            "verification": self.verification.value,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VehicleProfile":
        return cls(
            vehicle_id=data["vehicle_id"],
            make=data.get("make"),
            model=data.get("model"),
            model_year=data.get("model_year"),
            engine_family=data.get("engine_family"),
            engine_configuration=data.get("engine_configuration"),
            transmission=data.get("transmission"),
            original_controller_id=data.get("original_controller_id"),
            network_interfaces=[InterfaceSpec.from_dict(i) for i in (data.get("network_interfaces") or [])],
            sensor_topology=list(data.get("sensor_topology") or []),
            actuator_topology=list(data.get("actuator_topology") or []),
            module_dependencies=list(data.get("module_dependencies") or []),
            evidence=[EvidenceRef.from_dict(e) for e in (data.get("evidence") or [])],
            verification=VerificationStatus(data.get("verification", "unknown")),
            notes=data.get("notes"),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )

    def digest(self) -> str:
        return digest_payload(self.to_dict())


@dataclass
class CompatibilityResult:
    status: CompatibilityStatus
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    satisfied: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "satisfied": list(self.satisfied),
            "evidence_refs": list(self.evidence_refs),
            "details": dict(self.details),
            "evaluated_at": self.evaluated_at,
            "compatible": self.status == CompatibilityStatus.COMPATIBLE,
        }


ESP32_S3_NATIVE_CAPABILITIES = (
    "gpio",
    "adc",
    "pwm",
    "rmt",
    "spi",
    "i2c",
    "uart",
    "usb",
    "twai_classical_can",
    "wifi",
    "bluetooth_le",
)

ESP32_S3_EXTERNAL_REQUIRED = (
    "can_transceiver",
    "can_fd_controller",
    "signal_conditioning",
    "protected_output_drivers",
    "power_protection_supervision",
    "independent_watchdog_safety",
)

ESP32_S3_UNSUPPORTED = (
    "native_can_fd",
    "automotive_qualified_package",
    "asil_rated_safety",
    "direct_injector_drive",
    "direct_ignition_coil_drive",
)


def esp32_s3_compute_module(
    *,
    module_id: str = "esp32-s3-dev-compute-v1",
    hardware_revision: str = "dev-board",
    illustrative: bool = True,
) -> HardwareModule:
    """Declarative ESP32-S3 development compute module profile.

    Development / supervisory target only. NOT an automotive-qualified ECU.
    """
    conf = Confidence.ILLUSTRATIVE if illustrative else Confidence.USER_PROVIDED
    ver = VerificationStatus.ILLUSTRATIVE if illustrative else VerificationStatus.UNVERIFIED
    return HardwareModule(
        module_id=module_id,
        kind=ModuleKind.COMPUTE,
        name="ESP32-S3 Development Compute Module",
        hardware_revision=hardware_revision,
        manufacturer="Espressif (development board class)",
        model="ESP32-S3",
        electrical=ElectricalSpec(
            voltage_nominal_v=3.3,
            voltage_min_v=3.0,
            voltage_max_v=3.6,
            notes="MCU core voltage. Board-level 5 V / 12 V automotive supply requires external regulation and protection.",
            verification=ver,
        ),
        interfaces=[
            InterfaceSpec(
                name="twai",
                protocol="classical_can",
                external_hardware_required=True,
                notes="TWAI controller present; external CAN transceiver required for bus attachment.",
                verification=ver,
            ),
            InterfaceSpec(
                name="can_fd",
                protocol="can_fd",
                external_hardware_required=True,
                notes="No native CAN FD. External CAN FD controller required.",
                verification=ver,
            ),
            InterfaceSpec(name="uart0", protocol="uart", verification=ver),
            InterfaceSpec(name="usb", protocol="usb", verification=ver),
            InterfaceSpec(name="spi", protocol="spi", verification=ver),
            InterfaceSpec(name="i2c", protocol="i2c", verification=ver),
        ],
        capabilities=list(ESP32_S3_NATIVE_CAPABILITIES),
        pin_mappings=[],
        dependencies=list(ESP32_S3_EXTERNAL_REQUIRED),
        compatibility_constraints=[
            "not_automotive_qualified",
            "requires_external_can_transceiver",
            "requires_external_can_fd_for_can_fd",
            "requires_external_protected_drivers",
            "requires_external_power_protection",
            "requires_independent_safety_supervisor_for_vehicle_use",
        ],
        required_safety_properties=[
            "independent_watchdog",
            "power_supervision",
            "output_driver_protection",
        ],
        safety_class=SafetyClass.DEVELOPMENT,
        evidence=[
            EvidenceRef(
                source="platform.esp32_s3_profile",
                timestamp=utc_now_iso(),
                provenance="declarative_hardware_strategy",
                verification_method="documentation_review",
                confidence=conf,
                detail="ESP32-S3 public datasheet capabilities; not vehicle-qualified.",
            )
        ],
        verification=ver,
        notes=(
            "Development and supervisory compute only. Do not treat an ESP32-S3 "
            "development board as an automotive-qualified engine controller. "
            "A complete replacement platform requires modular external acquisition, "
            "protected drivers, power management and independent safety supervision."
        ),
    )
