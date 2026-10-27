"""Hardware discovery pipeline. Simulation-first. Discovery never authorizes writes."""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ecugate.discovery.manifests import (
    DeviceManifest,
    Evidence,
    EvidenceSource,
    FieldConfidence,
    FieldValue,
    PowerRequirements,
    load_manifests,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CapabilityLevel(str, enum.Enum):
    DETECTED = "detected"
    IDENTIFIED = "identified"
    DESCRIBED = "described"
    VALIDATED = "validated"
    AUTHORIZED = "authorized"


@dataclass
class InterfaceRecord:
    interface_id: str
    interface_type: str
    path: Optional[str] = None
    vendor_id: Optional[str] = None
    product_id: Optional[str] = None
    serial: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interface_id": self.interface_id,
            "interface_type": self.interface_type,
            "path": self.path,
            "vendor_id": self.vendor_id,
            "product_id": self.product_id,
            "serial": self.serial,
            "metadata": self.metadata,
        }


@dataclass
class AutocompleteSuggestion:
    field: str
    suggested_value: Any
    explanation: str
    evidence: List[Evidence]
    confidence: FieldConfidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "suggested_value": self.suggested_value,
            "explanation": self.explanation,
            "confidence": self.confidence.value,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class DiscoveryReport:
    report_id: str
    timestamp: str
    interfaces: List[InterfaceRecord]
    level: CapabilityLevel
    device_id: Optional[str]
    manufacturer: Optional[FieldValue]
    model: Optional[FieldValue]
    firmware_version: Optional[FieldValue]
    supported_protocols: List[str]
    supported_operations: List[str]
    power: PowerRequirements
    matched_manifest_id: Optional[str]
    suggestions: List[AutocompleteSuggestion]
    unknown_fields: List[str]
    conflicts: List[str]
    programming_ready: bool
    programming_blockers: List[str]
    evidence: List[Evidence]
    schema_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        def fv(x: Optional[FieldValue]) -> Optional[Dict[str, Any]]:
            return x.to_dict() if x else None

        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
            "interfaces": [i.to_dict() for i in self.interfaces],
            "capability_level": self.level.value,
            "device_id": self.device_id,
            "manufacturer": fv(self.manufacturer),
            "model": fv(self.model),
            "firmware_version": fv(self.firmware_version),
            "supported_protocols": list(self.supported_protocols),
            "supported_operations": list(self.supported_operations),
            "power": self.power.to_dict(),
            "matched_manifest_id": self.matched_manifest_id,
            "suggestions": [s.to_dict() for s in self.suggestions],
            "unknown_fields": list(self.unknown_fields),
            "conflicts": list(self.conflicts),
            "programming_ready": self.programming_ready,
            "programming_blockers": list(self.programming_blockers),
            "evidence": [e.to_dict() for e in self.evidence],
            "authorized": False,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


class DiscoveryEngine:
    def __init__(self, manifests: Optional[List[DeviceManifest]] = None, manifest_dir: Optional[str] = None) -> None:
        self._manifests: List[DeviceManifest] = list(manifests or [])
        if manifest_dir:
            self._manifests.extend(load_manifests(manifest_dir))
        self._simulated: List[InterfaceRecord] = []

    def register_manifest(self, manifest: DeviceManifest) -> None:
        self._manifests.append(manifest)

    def inject_simulated_interface(self, iface: InterfaceRecord) -> None:
        self._simulated.append(iface)

    def enumerate(self) -> List[InterfaceRecord]:
        return list(self._simulated)

    def discover(self, *, non_destructive: bool = True) -> DiscoveryReport:
        ts = utc_now_iso()
        evidence: List[Evidence] = []
        interfaces = self.enumerate()

        if not interfaces:
            return DiscoveryReport(
                report_id=str(uuid4()), timestamp=ts, interfaces=[],
                level=CapabilityLevel.DETECTED, device_id=None,
                manufacturer=None, model=None, firmware_version=None,
                supported_protocols=[], supported_operations=[],
                power=PowerRequirements(), matched_manifest_id=None,
                suggestions=[], unknown_fields=["device_id", "manufacturer", "model", "firmware_version", "power"],
                conflicts=[], programming_ready=False,
                programming_blockers=["no_interface_detected"], evidence=evidence,
            )

        primary = interfaces[0]
        evidence.append(Evidence(source=EvidenceSource.DESCRIPTOR, detail=f"enumerated {primary.interface_type} interface {primary.interface_id}", confidence=FieldConfidence.CONFIRMED, timestamp=ts, raw=primary.to_dict()))

        matches = self._match_manifests(primary)
        conflicts: List[str] = []
        if len(matches) > 1:
            conflicts.append(f"multiple manifests match interface: {[m.device_id for m in matches]}")

        level = CapabilityLevel.DETECTED
        matched: Optional[DeviceManifest] = matches[0] if len(matches) == 1 else None
        if matched:
            level = CapabilityLevel.IDENTIFIED
            evidence.append(Evidence(source=EvidenceSource.MANIFEST, detail=f"matched manifest {matched.device_id}", confidence=FieldConfidence.CONFIRMED, timestamp=ts))

        manufacturer = model = firmware = None
        protocols: List[str] = []
        operations: List[str] = []
        power = PowerRequirements()
        suggestions: List[AutocompleteSuggestion] = []
        unknown: List[str] = []

        if matched:
            level = CapabilityLevel.DESCRIBED
            if matched.manufacturer:
                manufacturer = FieldValue(matched.manufacturer, FieldConfidence.CONFIRMED, [Evidence(EvidenceSource.MANIFEST, "manifest.manufacturer", FieldConfidence.CONFIRMED, ts)])
            if matched.model:
                model = FieldValue(matched.model, FieldConfidence.CONFIRMED, [Evidence(EvidenceSource.MANIFEST, "manifest.model", FieldConfidence.CONFIRMED, ts)])
            if matched.firmware_version or primary.metadata.get("firmware"):
                firmware = FieldValue(matched.firmware_version or primary.metadata.get("firmware"), FieldConfidence.CONFIRMED if matched.firmware_version else FieldConfidence.UNKNOWN, [])
            protocols = list(matched.supported_protocols)
            operations = list(matched.supported_operations)
            power = matched.power
            if matched.model:
                suggestions.append(AutocompleteSuggestion(field="model", suggested_value=matched.model, explanation=f"From manifest {matched.device_id} matched by VID/PID or simulated id", evidence=[Evidence(EvidenceSource.MANIFEST, matched.device_id, FieldConfidence.CONFIRMED, ts)], confidence=FieldConfidence.CONFIRMED))
            if power.is_resolved():
                suggestions.append(AutocompleteSuggestion(field="power.voltage_range", suggested_value=[power.voltage_min, power.voltage_max], explanation="Authoritative voltage range from device manifest documentation", evidence=list(power.evidence), confidence=power.confidence))
        else:
            for m in self._manifests:
                if m.interface_type and m.interface_type == primary.interface_type:
                    suggestions.append(AutocompleteSuggestion(field="adapter_candidate", suggested_value=m.device_id, explanation=f"Compatible interface_type={m.interface_type}; identity not confirmed — do not auto-select programming protocol", evidence=[Evidence(EvidenceSource.INFERRED, f"interface_type match only for {m.device_id}", FieldConfidence.INFERRED, ts)], confidence=FieldConfidence.INFERRED))
            unknown.extend(["device_id", "manufacturer", "model", "firmware_version", "power"])

        blockers: List[str] = []
        if conflicts:
            blockers.append("conflicting_manifest_matches")
        if not power.is_resolved():
            blockers.append("power_requirements_unresolved")
            if "power" not in unknown:
                unknown.append("power")
        if not matched:
            blockers.append("device_identity_unconfirmed")

        programming_ready = matched is not None and power.is_resolved() and not conflicts and "write" in (matched.supported_operations if matched else [])
        if programming_ready:
            level = CapabilityLevel.VALIDATED
        elif matched:
            level = CapabilityLevel.DESCRIBED if protocols else CapabilityLevel.IDENTIFIED

        if not programming_ready and matched and "write" not in (matched.supported_operations or []):
            if "write_not_in_supported_operations" not in blockers:
                blockers.append("write_not_in_supported_operations")

        return DiscoveryReport(
            report_id=str(uuid4()), timestamp=ts, interfaces=interfaces, level=level,
            device_id=matched.device_id if matched else None, manufacturer=manufacturer, model=model,
            firmware_version=firmware, supported_protocols=protocols, supported_operations=operations,
            power=power, matched_manifest_id=matched.device_id if matched else None,
            suggestions=suggestions, unknown_fields=unknown, conflicts=conflicts,
            programming_ready=programming_ready, programming_blockers=blockers, evidence=evidence,
        )

    def _match_manifests(self, iface: InterfaceRecord) -> List[DeviceManifest]:
        hits: List[DeviceManifest] = []
        for m in self._manifests:
            if iface.vendor_id and iface.product_id:
                if m.vendor_id == iface.vendor_id and m.product_id == iface.product_id:
                    hits.append(m)
                    continue
            sim_id = iface.metadata.get("device_id")
            if sim_id and m.device_id == sim_id:
                hits.append(m)
        return hits
