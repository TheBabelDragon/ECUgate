"""Versioned device and adapter manifests. Confirmed vs inferred vs unknown."""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


class EvidenceSource(str, enum.Enum):
    DESCRIPTOR = "descriptor"
    FIRMWARE = "firmware"
    PROTOCOL_QUERY = "protocol_query"
    MANIFEST = "manifest"
    USER = "user"
    INFERRED = "inferred"


class FieldConfidence(str, enum.Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    USER_PROVIDED = "user_provided"
    UNKNOWN = "unknown"


@dataclass
class Evidence:
    source: EvidenceSource
    detail: str
    confidence: FieldConfidence
    timestamp: str
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "source": self.source.value,
            "detail": self.detail,
            "confidence": self.confidence.value,
            "timestamp": self.timestamp,
        }
        if self.raw is not None:
            d["raw"] = self.raw
        return d


@dataclass
class FieldValue:
    value: Any
    confidence: FieldConfidence
    evidence: List[Evidence] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence.value,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class PowerRequirements:
    voltage_min: Optional[float] = None
    voltage_max: Optional[float] = None
    voltage_nominal: Optional[float] = None
    current_max_a: Optional[float] = None
    transient_notes: Optional[str] = None
    confidence: FieldConfidence = FieldConfidence.UNKNOWN
    evidence: List[Evidence] = field(default_factory=list)

    def is_resolved(self) -> bool:
        return (
            self.voltage_min is not None
            and self.voltage_max is not None
            and self.confidence in (FieldConfidence.CONFIRMED, FieldConfidence.USER_PROVIDED)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "voltage_min": self.voltage_min,
            "voltage_max": self.voltage_max,
            "voltage_nominal": self.voltage_nominal,
            "current_max_a": self.current_max_a,
            "transient_notes": self.transient_notes,
            "confidence": self.confidence.value,
            "resolved": self.is_resolved(),
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class DeviceManifest:
    device_id: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    interface_type: Optional[str] = None
    supported_protocols: List[str] = field(default_factory=list)
    supported_operations: List[str] = field(default_factory=list)
    power: PowerRequirements = field(default_factory=PowerRequirements)
    programming_requirements: List[str] = field(default_factory=list)
    recovery_capabilities: List[str] = field(default_factory=list)
    vendor_id: Optional[str] = None
    product_id: Optional[str] = None
    schema_version: str = "1.0"
    adapter_id: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "firmware_version": self.firmware_version,
            "interface_type": self.interface_type,
            "supported_protocols": list(self.supported_protocols),
            "supported_operations": list(self.supported_operations),
            "power": self.power.to_dict(),
            "programming_requirements": list(self.programming_requirements),
            "recovery_capabilities": list(self.recovery_capabilities),
            "vendor_id": self.vendor_id,
            "product_id": self.product_id,
            "schema_version": self.schema_version,
            "adapter_id": self.adapter_id,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DeviceManifest":
        power_d = d.get("power") or {}
        power = PowerRequirements(
            voltage_min=power_d.get("voltage_min"),
            voltage_max=power_d.get("voltage_max"),
            voltage_nominal=power_d.get("voltage_nominal"),
            current_max_a=power_d.get("current_max_a"),
            transient_notes=power_d.get("transient_notes"),
            confidence=FieldConfidence(power_d.get("confidence", "unknown")),
        )
        return cls(
            device_id=d["device_id"],
            manufacturer=d.get("manufacturer"),
            model=d.get("model"),
            firmware_version=d.get("firmware_version"),
            interface_type=d.get("interface_type"),
            supported_protocols=list(d.get("supported_protocols") or []),
            supported_operations=list(d.get("supported_operations") or []),
            power=power,
            programming_requirements=list(d.get("programming_requirements") or []),
            recovery_capabilities=list(d.get("recovery_capabilities") or []),
            vendor_id=d.get("vendor_id"),
            product_id=d.get("product_id"),
            schema_version=d.get("schema_version", "1.0"),
            adapter_id=d.get("adapter_id"),
            notes=d.get("notes"),
        )


def load_manifests(directory: str | Path) -> List[DeviceManifest]:
    path = Path(directory)
    if not path.exists():
        return []
    out: List[DeviceManifest] = []
    for f in sorted(path.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(data, list):
            for item in data:
                out.append(DeviceManifest.from_dict(item))
        else:
            out.append(DeviceManifest.from_dict(data))
    return out
