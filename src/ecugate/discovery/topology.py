"""Bench topology: multi-device inventory, relationships, and programming readiness.

Roles and relationships are explicit. USB presence never implies which ECU is
attached to which programmer. Discovery never grants write authorization.
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ecugate.discovery.manifests import (
    DeviceManifest,
    Evidence,
    EvidenceSource,
    FieldConfidence,
    FieldValue,
    PowerRequirements,
)
from ecugate.discovery.pipeline import (
    AutocompleteSuggestion,
    CapabilityLevel,
    InterfaceRecord,
    utc_now_iso,
)


class DeviceRole(str, enum.Enum):
    HOST_INTERFACE = "host_interface"
    PROGRAMMER = "programmer"
    POWER_SUPPLY = "power_supply"
    TARGET_ECU = "target_ecu"
    UNKNOWN_DEVICE = "unknown_device"


class RelationshipType(str, enum.Enum):
    CONNECTED_VIA = "connected_via"
    POWERS = "powers"
    PROGRAMS = "programs"
    USER_CONFIRMED = "user_confirmed"


@dataclass
class BenchDevice:
    device_record_id: str
    role: DeviceRole
    interface: InterfaceRecord
    level: CapabilityLevel
    matched_manifest_id: Optional[str] = None
    candidate_manifest_ids: List[str] = field(default_factory=list)
    manufacturer: Optional[FieldValue] = None
    model: Optional[FieldValue] = None
    firmware_version: Optional[FieldValue] = None
    supported_protocols: List[str] = field(default_factory=list)
    supported_operations: List[str] = field(default_factory=list)
    power: PowerRequirements = field(default_factory=PowerRequirements)
    suggestions: List[AutocompleteSuggestion] = field(default_factory=list)
    unknown_fields: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        def fv(x: Optional[FieldValue]) -> Optional[Dict[str, Any]]:
            return x.to_dict() if x else None

        return {
            "device_record_id": self.device_record_id,
            "role": self.role.value,
            "interface": self.interface.to_dict(),
            "capability_level": self.level.value,
            "matched_manifest_id": self.matched_manifest_id,
            "candidate_manifest_ids": list(self.candidate_manifest_ids),
            "manufacturer": fv(self.manufacturer),
            "model": fv(self.model),
            "firmware_version": fv(self.firmware_version),
            "supported_protocols": list(self.supported_protocols),
            "supported_operations": list(self.supported_operations),
            "power": self.power.to_dict(),
            "suggestions": [s.to_dict() for s in self.suggestions],
            "unknown_fields": list(self.unknown_fields),
            "conflicts": list(self.conflicts),
            "evidence": [e.to_dict() for e in self.evidence],
            "next_steps": list(self.next_steps),
            "timestamp": self.timestamp,
        }


@dataclass
class TopologyRelationship:
    relationship_id: str
    relationship_type: RelationshipType
    from_id: str
    to_id: str
    confidence: FieldConfidence
    evidence: List[Evidence] = field(default_factory=list)
    user_confirmed: bool = False
    note: Optional[str] = None
    timestamp: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relationship_id": self.relationship_id,
            "relationship_type": self.relationship_type.value,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "confidence": self.confidence.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "user_confirmed": self.user_confirmed,
            "note": self.note,
            "timestamp": self.timestamp,
        }


@dataclass
class ReadinessRequirement:
    requirement_id: str
    description: str
    satisfied: bool
    unresolved: List[str] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "description": self.description,
            "satisfied": self.satisfied,
            "unresolved": list(self.unresolved),
            "evidence": [e.to_dict() for e in self.evidence],
            "detail": self.detail,
        }


@dataclass
class ReadinessAssessment:
    ready: bool
    requirements: List[ReadinessRequirement]
    blockers: List[str]
    unresolved_fields: List[str]
    schema_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ready": self.ready,
            "requirements": [r.to_dict() for r in self.requirements],
            "blockers": list(self.blockers),
            "unresolved_fields": list(self.unresolved_fields),
            "schema_version": self.schema_version,
            "authorized": False,
        }


@dataclass
class BenchInventory:
    inventory_id: str
    timestamp: str
    devices: List[BenchDevice]
    relationships: List[TopologyRelationship]
    readiness: ReadinessAssessment
    suggestions: List[AutocompleteSuggestion] = field(default_factory=list)
    schema_version: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inventory_id": self.inventory_id,
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
            "devices": [d.to_dict() for d in self.devices],
            "relationships": [r.to_dict() for r in self.relationships],
            "readiness": self.readiness.to_dict(),
            "suggestions": [s.to_dict() for s in self.suggestions],
            "authorized": False,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


def infer_role(iface: InterfaceRecord, matched: Optional[DeviceManifest]) -> DeviceRole:
    meta_role = (iface.metadata or {}).get("role")
    if meta_role:
        try:
            return DeviceRole(str(meta_role))
        except ValueError:
            pass
    if matched:
        ops = set(matched.supported_operations or [])
        notes = (matched.notes or "").lower()
        if "power" in notes or "psu" in notes:
            return DeviceRole.POWER_SUPPLY
        if "programmer" in notes or "adapter" in notes:
            return DeviceRole.PROGRAMMER
        if "write" in ops or "read" in ops:
            did = (matched.device_id or "").lower()
            if "ecu" in did or "sim" in did:
                return DeviceRole.TARGET_ECU
            if "prog" in did or "adapter" in did:
                return DeviceRole.PROGRAMMER
    if iface.interface_type in ("serial", "usb", "simulated"):
        return DeviceRole.HOST_INTERFACE
    return DeviceRole.UNKNOWN_DEVICE


def _match_manifests(iface: InterfaceRecord, manifests: List[DeviceManifest]) -> List[DeviceManifest]:
    hits: List[DeviceManifest] = []
    for m in manifests:
        if iface.vendor_id and iface.product_id:
            if m.vendor_id == iface.vendor_id and m.product_id == iface.product_id:
                hits.append(m)
                continue
        sim_id = iface.metadata.get("device_id")
        if sim_id and m.device_id == sim_id:
            hits.append(m)
    return hits


def assess_interface(
    iface: InterfaceRecord,
    manifests: List[DeviceManifest],
    *,
    ts: Optional[str] = None,
) -> BenchDevice:
    ts = ts or utc_now_iso()
    evidence: List[Evidence] = [
        Evidence(
            source=EvidenceSource.DESCRIPTOR,
            detail=f"enumerated {iface.interface_type} interface {iface.interface_id}",
            confidence=FieldConfidence.CONFIRMED,
            timestamp=ts,
            raw=iface.to_dict(),
        )
    ]
    matches = _match_manifests(iface, manifests)
    conflicts: List[str] = []
    candidate_ids = [m.device_id for m in matches]
    if len(matches) > 1:
        conflicts.append(f"multiple manifests match interface: {candidate_ids}")

    matched = matches[0] if len(matches) == 1 else None
    level = CapabilityLevel.DETECTED
    if matched:
        level = CapabilityLevel.IDENTIFIED
        evidence.append(
            Evidence(
                source=EvidenceSource.MANIFEST,
                detail=f"matched manifest {matched.device_id}",
                confidence=FieldConfidence.CONFIRMED,
                timestamp=ts,
            )
        )

    manufacturer = model = firmware = None
    protocols: List[str] = []
    operations: List[str] = []
    power = PowerRequirements()
    suggestions: List[AutocompleteSuggestion] = []
    unknown: List[str] = []
    next_steps: List[str] = []

    if matched:
        level = CapabilityLevel.DESCRIBED
        if matched.manufacturer:
            manufacturer = FieldValue(
                matched.manufacturer,
                FieldConfidence.CONFIRMED,
                [Evidence(EvidenceSource.MANIFEST, "manifest.manufacturer", FieldConfidence.CONFIRMED, ts)],
            )
        if matched.model:
            model = FieldValue(
                matched.model,
                FieldConfidence.CONFIRMED,
                [Evidence(EvidenceSource.MANIFEST, "manifest.model", FieldConfidence.CONFIRMED, ts)],
            )
            suggestions.append(
                AutocompleteSuggestion(
                    field="model",
                    suggested_value=matched.model,
                    explanation=f"Manifest {matched.device_id} matched by VID/PID or device_id",
                    evidence=[Evidence(EvidenceSource.MANIFEST, matched.device_id, FieldConfidence.CONFIRMED, ts)],
                    confidence=FieldConfidence.CONFIRMED,
                )
            )
        if matched.firmware_version or iface.metadata.get("firmware"):
            fw = matched.firmware_version or iface.metadata.get("firmware")
            conf = FieldConfidence.CONFIRMED if matched.firmware_version else FieldConfidence.UNKNOWN
            firmware = FieldValue(fw, conf, [])
        protocols = list(matched.supported_protocols)
        operations = list(matched.supported_operations)
        power = matched.power
        if power.is_resolved():
            suggestions.append(
                AutocompleteSuggestion(
                    field="power.voltage_range",
                    suggested_value=[power.voltage_min, power.voltage_max],
                    explanation="Authoritative range from device manifest — not a generic automotive default",
                    evidence=list(power.evidence),
                    confidence=power.confidence,
                )
            )
        if not power.is_resolved():
            unknown.append("power")
            next_steps.append("Resolve power requirements from manufacturer documentation for the matched device")
    else:
        for m in manifests:
            if m.interface_type and m.interface_type == iface.interface_type:
                suggestions.append(
                    AutocompleteSuggestion(
                        field="adapter_candidate",
                        suggested_value=m.device_id,
                        explanation=(
                            f"interface_type={m.interface_type} only — identity not confirmed; "
                            "do not auto-select programming protocol"
                        ),
                        evidence=[
                            Evidence(
                                EvidenceSource.INFERRED,
                                f"interface_type match only for {m.device_id}",
                                FieldConfidence.INFERRED,
                                ts,
                            )
                        ],
                        confidence=FieldConfidence.INFERRED,
                    )
                )
        unknown.extend(["device_id", "manufacturer", "model", "firmware_version", "power"])
        next_steps.append("Provide device identity or connect a known adapter with documented VID/PID")
        if iface.vendor_id and iface.product_id:
            next_steps.append(
                f"Look up VID:PID {iface.vendor_id}:{iface.product_id} in authoritative documentation"
            )

    if conflicts:
        next_steps.append("Resolve conflicting manifest matches before selecting a protocol")
        level = CapabilityLevel.DETECTED

    if matched and power.is_resolved() and not conflicts:
        level = CapabilityLevel.VALIDATED if "write" in operations else CapabilityLevel.DESCRIBED

    role = infer_role(iface, matched)
    return BenchDevice(
        device_record_id=str(uuid4()),
        role=role,
        interface=iface,
        level=level,
        matched_manifest_id=matched.device_id if matched else None,
        candidate_manifest_ids=candidate_ids,
        manufacturer=manufacturer,
        model=model,
        firmware_version=firmware,
        supported_protocols=protocols,
        supported_operations=operations,
        power=power,
        suggestions=suggestions,
        unknown_fields=unknown,
        conflicts=conflicts,
        evidence=evidence,
        next_steps=next_steps,
        timestamp=ts,
    )


def evaluate_readiness(
    devices: List[BenchDevice],
    relationships: List[TopologyRelationship],
) -> ReadinessAssessment:
    requirements: List[ReadinessRequirement] = []

    def req(rid: str, desc: str, ok: bool, unres: List[str], detail: str = "") -> None:
        requirements.append(
            ReadinessRequirement(
                requirement_id=rid,
                description=desc,
                satisfied=ok,
                unresolved=unres,
                detail=detail or None,
            )
        )

    target = next((d for d in devices if d.role == DeviceRole.TARGET_ECU and d.matched_manifest_id), None)
    if target is None:
        candidates = [
            d
            for d in devices
            if d.matched_manifest_id and "write" in (d.supported_operations or []) and not d.conflicts
        ]
        if len(candidates) == 1:
            target = candidates[0]

    req(
        "target_ecu_identity",
        "Target ECU identity confirmed via single manifest match",
        target is not None and target.matched_manifest_id is not None and not target.conflicts,
        [] if target and target.matched_manifest_id else ["target_ecu.device_id"],
        detail=target.matched_manifest_id if target else "no unique target ECU identified",
    )

    programmer = next((d for d in devices if d.role == DeviceRole.PROGRAMMER and d.matched_manifest_id), None)
    req(
        "programmer_identity",
        "Programmer identity and supported protocol known",
        programmer is not None and bool(programmer.supported_protocols),
        [] if programmer and programmer.supported_protocols else ["programmer.device_id", "programmer.protocol"],
        detail=(programmer.matched_manifest_id if programmer else "no programmer identified"),
    )

    compat_ok = False
    compat_detail = "programmer and/or target protocol unknown"
    if programmer and target:
        shared = set(programmer.supported_protocols) & set(target.supported_protocols)
        if shared:
            compat_ok = True
            compat_detail = f"shared protocols: {sorted(shared)}"
        else:
            compat_detail = "no shared protocol between programmer and target manifests"
    req(
        "programmer_target_protocol_compatibility",
        "Programmer protocol compatible with target ECU",
        compat_ok,
        [] if compat_ok else ["protocol.compatibility"],
        detail=compat_detail,
    )

    power_ok = bool(target and target.power.is_resolved())
    req(
        "ecu_power_requirements",
        "ECU-specific power requirements documented (not a nominal 13 V assumption)",
        power_ok,
        [] if power_ok else ["target_ecu.power"],
        detail=(
            f"target voltage range {target.power.voltage_min}–{target.power.voltage_max}"
            if power_ok and target
            else "target power requirements unresolved"
        ),
    )

    psu = next((d for d in devices if d.role == DeviceRole.POWER_SUPPLY), None)
    psu_ok = False
    psu_detail = "power supply capability not confirmed"
    if psu and psu.power.is_resolved() and target and target.power.is_resolved():
        if (
            psu.power.voltage_min is not None
            and psu.power.voltage_max is not None
            and target.power.voltage_min is not None
            and target.power.voltage_max is not None
            and psu.power.voltage_min <= target.power.voltage_min
            and psu.power.voltage_max >= target.power.voltage_max
        ):
            psu_ok = True
            psu_detail = "supply range covers target range"
        else:
            psu_detail = "supply range does not cover target ECU range"
    elif psu and not psu.power.is_resolved():
        psu_detail = "power supply present but capability unresolved"
    req(
        "supply_voltage_current",
        "Supply voltage/current capabilities verified against ECU requirements",
        psu_ok,
        [] if psu_ok else ["power_supply.capability", "power_supply.vs_ecu"],
        detail=psu_detail,
    )

    transient_ok = bool(target and target.power.transient_notes)
    req(
        "transient_stability",
        "Relevant transient/stability requirements documented",
        transient_ok,
        [] if transient_ok else ["target_ecu.power.transient_notes"],
        detail=(target.power.transient_notes if target and target.power.transient_notes else "missing"),
    )

    req(
        "recovery_procedure",
        "Recovery procedure known before programming",
        False,
        ["target_ecu.recovery"],
        detail="recovery procedure must be confirmed from device documentation",
    )

    req(
        "write_authorization",
        "Explicit write authorization (outside discovery) — never granted here",
        False,
        ["authorization.execute"],
        detail="Readiness is not authorization; ExecutionEngine must authorize separately",
    )

    has_programs = any(
        r.relationship_type == RelationshipType.PROGRAMS
        and (r.user_confirmed or r.confidence == FieldConfidence.CONFIRMED)
        for r in relationships
    )
    req(
        "topology_programs_link",
        "Explicit programmer→target relationship (user-confirmed or documented)",
        has_programs,
        [] if has_programs else ["topology.programs"],
        detail="USB/serial presence alone does not prove attachment",
    )

    structural_ready = all(r.satisfied for r in requirements if r.requirement_id != "write_authorization")
    blockers = [r.requirement_id for r in requirements if not r.satisfied]
    unresolved: List[str] = []
    for r in requirements:
        if not r.satisfied:
            unresolved.extend(r.unresolved)

    return ReadinessAssessment(
        ready=structural_ready,
        requirements=requirements,
        blockers=blockers,
        unresolved_fields=sorted(set(unresolved)),
    )


class BenchTopology:
    def __init__(self, manifests: Optional[List[DeviceManifest]] = None) -> None:
        self._manifests = list(manifests or [])
        self._relationships: List[TopologyRelationship] = []
        self._user_role_overrides: Dict[str, DeviceRole] = {}

    def confirm_relationship(
        self,
        from_id: str,
        to_id: str,
        relationship_type: RelationshipType = RelationshipType.PROGRAMS,
        *,
        note: Optional[str] = None,
    ) -> TopologyRelationship:
        ts = utc_now_iso()
        rel = TopologyRelationship(
            relationship_id=str(uuid4()),
            relationship_type=relationship_type,
            from_id=from_id,
            to_id=to_id,
            confidence=FieldConfidence.USER_PROVIDED,
            evidence=[
                Evidence(
                    source=EvidenceSource.USER,
                    detail=f"user confirmed {relationship_type.value} {from_id} → {to_id}",
                    confidence=FieldConfidence.USER_PROVIDED,
                    timestamp=ts,
                )
            ],
            user_confirmed=True,
            note=note,
            timestamp=ts,
        )
        self._relationships.append(rel)
        return rel

    def set_role(self, interface_id: str, role: DeviceRole) -> None:
        self._user_role_overrides[interface_id] = role

    def build(self, interfaces: List[InterfaceRecord]) -> BenchInventory:
        ts = utc_now_iso()
        devices: List[BenchDevice] = []
        seen: set[str] = set()
        unique: List[InterfaceRecord] = []
        for iface in interfaces:
            if iface.interface_id in seen:
                continue
            seen.add(iface.interface_id)
            unique.append(iface)

        all_suggestions: List[AutocompleteSuggestion] = []
        for iface in unique:
            dev = assess_interface(iface, self._manifests, ts=ts)
            if iface.interface_id in self._user_role_overrides:
                dev.role = self._user_role_overrides[iface.interface_id]
                dev.evidence.append(
                    Evidence(
                        source=EvidenceSource.USER,
                        detail=f"user set role={dev.role.value}",
                        confidence=FieldConfidence.USER_PROVIDED,
                        timestamp=ts,
                    )
                )
            devices.append(dev)
            all_suggestions.extend(dev.suggestions)

        readiness = evaluate_readiness(devices, self._relationships)
        return BenchInventory(
            inventory_id=str(uuid4()),
            timestamp=ts,
            devices=devices,
            relationships=list(self._relationships),
            readiness=readiness,
            suggestions=all_suggestions,
        )
