"""Versioned controller clone / backup packages with explicit capture completeness.

Never report a complete clone merely because a firmware binary was copied.
Protected security material is represented as requirements, not extracted data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ecugate.platform.models import (
    SCHEMA_VERSION,
    CaptureStatus,
    Confidence,
    EvidenceRef,
    VerificationStatus,
    canonical_json,
    digest_payload,
    utc_now_iso,
)


PACKAGE_SCHEMA = "clone_package.v1"


@dataclass
class CaptureRegion:
    """One independently captured (or non-captured) region of controller state."""

    region_id: str
    region_kind: str
    status: CaptureStatus
    capture_method: Optional[str] = None
    source_controller_id: Optional[str] = None
    timestamp: Optional[str] = None
    data_length: Optional[int] = None
    digest: Optional[str] = None
    verification: VerificationStatus = VerificationStatus.UNKNOWN
    provenance: Optional[str] = None
    limitations: List[str] = field(default_factory=list)
    evidence: List[EvidenceRef] = field(default_factory=list)
    protected_dependency_ref: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "region_id": self.region_id,
            "region_kind": self.region_kind,
            "status": self.status.value,
            "capture_method": self.capture_method,
            "source_controller_id": self.source_controller_id,
            "timestamp": self.timestamp,
            "data_length": self.data_length,
            "digest": self.digest,
            "verification": self.verification.value,
            "provenance": self.provenance,
            "limitations": list(self.limitations),
            "evidence": [e.to_dict() for e in self.evidence],
            "protected_dependency_ref": self.protected_dependency_ref,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CaptureRegion":
        return cls(
            region_id=data["region_id"],
            region_kind=data["region_kind"],
            status=CaptureStatus(data["status"]),
            capture_method=data.get("capture_method"),
            source_controller_id=data.get("source_controller_id"),
            timestamp=data.get("timestamp"),
            data_length=data.get("data_length"),
            digest=data.get("digest"),
            verification=VerificationStatus(data.get("verification", "unknown")),
            provenance=data.get("provenance"),
            limitations=list(data.get("limitations") or []),
            evidence=[EvidenceRef.from_dict(e) for e in (data.get("evidence") or [])],
            protected_dependency_ref=data.get("protected_dependency_ref"),
        )

    def is_successfully_captured(self) -> bool:
        return self.status == CaptureStatus.CAPTURED


@dataclass
class ClonePackage:
    """Versioned, integrity-verifiable controller backup package."""

    package_id: str
    controller_identity: Dict[str, Any]
    hardware_identity: Dict[str, Any] = field(default_factory=dict)
    firmware: Optional[CaptureRegion] = None
    calibration: Optional[CaptureRegion] = None
    configuration: Optional[CaptureRegion] = None
    diagnostic_metadata: Optional[CaptureRegion] = None
    other_regions: List[CaptureRegion] = field(default_factory=list)
    compatibility_constraints: List[str] = field(default_factory=list)
    provenance: List[EvidenceRef] = field(default_factory=list)
    recovery_requirements: List[str] = field(default_factory=list)
    schema_version: str = PACKAGE_SCHEMA
    created_at: str = field(default_factory=utc_now_iso)
    package_digest: Optional[str] = None

    def all_regions(self) -> List[CaptureRegion]:
        regions: List[CaptureRegion] = []
        for r in (self.firmware, self.calibration, self.configuration, self.diagnostic_metadata):
            if r is not None:
                regions.append(r)
        regions.extend(self.other_regions)
        return regions

    def capture_completeness(self) -> Dict[str, Any]:
        regions = self.all_regions()
        by_status: Dict[str, List[str]] = {s.value: [] for s in CaptureStatus}
        for r in regions:
            by_status[r.status.value].append(r.region_id)
        captured = by_status[CaptureStatus.CAPTURED.value]
        protected = by_status[CaptureStatus.PROTECTED.value]
        unsupported = by_status[CaptureStatus.UNSUPPORTED.value]
        unreadable = by_status[CaptureStatus.UNREADABLE.value]
        not_attempted = by_status[CaptureStatus.NOT_ATTEMPTED.value]
        critical_missing = [
            rid
            for rid in (protected + unsupported + unreadable + not_attempted)
            if rid in {"firmware", "calibration", "configuration"}
            or any(
                r.region_id == rid and r.region_kind in ("firmware", "calibration", "configuration")
                for r in regions
            )
        ]
        is_complete = (
            len(regions) > 0
            and len(protected) == 0
            and len(unsupported) == 0
            and len(unreadable) == 0
            and len(not_attempted) == 0
            and any(r.region_kind == "firmware" and r.is_successfully_captured() for r in regions)
            and any(r.region_kind == "calibration" and r.is_successfully_captured() for r in regions)
        )
        return {
            "region_count": len(regions),
            "captured": captured,
            "protected": protected,
            "unsupported": unsupported,
            "unreadable": unreadable,
            "not_attempted": not_attempted,
            "critical_missing_or_incomplete": critical_missing,
            "is_complete": is_complete,
            "notes": (
                "A complete clone requires successful capture of all required regions. "
                "Protected, unsupported, unreadable and not_attempted regions prevent completeness."
                if not is_complete
                else "All registered regions report captured status."
            ),
        }

    def content_for_digest(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "controller_identity": self.controller_identity,
            "hardware_identity": self.hardware_identity,
            "firmware": self.firmware.to_dict() if self.firmware else None,
            "calibration": self.calibration.to_dict() if self.calibration else None,
            "configuration": self.configuration.to_dict() if self.configuration else None,
            "diagnostic_metadata": self.diagnostic_metadata.to_dict() if self.diagnostic_metadata else None,
            "other_regions": [r.to_dict() for r in self.other_regions],
            "compatibility_constraints": list(self.compatibility_constraints),
            "provenance": [e.to_dict() for e in self.provenance],
            "recovery_requirements": list(self.recovery_requirements),
            "created_at": self.created_at,
        }

    def compute_digest(self) -> str:
        return digest_payload(self.content_for_digest())

    def seal(self) -> "ClonePackage":
        self.package_digest = self.compute_digest()
        return self

    def verify_integrity(self) -> bool:
        if not self.package_digest:
            return False
        return self.package_digest == self.compute_digest()

    def to_dict(self) -> Dict[str, Any]:
        d = self.content_for_digest()
        d["package_digest"] = self.package_digest
        d["capture_completeness"] = self.capture_completeness()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClonePackage":
        def region(key: str) -> Optional[CaptureRegion]:
            raw = data.get(key)
            return CaptureRegion.from_dict(raw) if raw else None

        return cls(
            package_id=data["package_id"],
            controller_identity=dict(data.get("controller_identity") or {}),
            hardware_identity=dict(data.get("hardware_identity") or {}),
            firmware=region("firmware"),
            calibration=region("calibration"),
            configuration=region("configuration"),
            diagnostic_metadata=region("diagnostic_metadata"),
            other_regions=[CaptureRegion.from_dict(r) for r in (data.get("other_regions") or [])],
            compatibility_constraints=list(data.get("compatibility_constraints") or []),
            provenance=[EvidenceRef.from_dict(e) for e in (data.get("provenance") or [])],
            recovery_requirements=list(data.get("recovery_requirements") or []),
            schema_version=data.get("schema_version", PACKAGE_SCHEMA),
            created_at=data.get("created_at") or utc_now_iso(),
            package_digest=data.get("package_digest"),
        )

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, default=str)

    @classmethod
    def from_json(cls, text: str) -> "ClonePackage":
        return cls.from_dict(json.loads(text))


def compute_package_digest(package: ClonePackage) -> str:
    return package.compute_digest()


def make_incomplete_example_package(
    package_id: str = "example-incomplete-backup-v1",
    controller_id: str = "example-controller-illustrative",
) -> ClonePackage:
    """Illustrative incomplete backup: firmware captured, calibration protected, config not attempted."""
    now = utc_now_iso()
    pkg = ClonePackage(
        package_id=package_id,
        controller_identity={
            "controller_id": controller_id,
            "manufacturer": "illustrative",
            "model": "example-ecu",
            "note": "Illustrative only; not a real vehicle controller.",
        },
        hardware_identity={"revision": "unknown"},
        firmware=CaptureRegion(
            region_id="firmware",
            region_kind="firmware",
            status=CaptureStatus.CAPTURED,
            capture_method="illustrative_read",
            source_controller_id=controller_id,
            timestamp=now,
            data_length=262144,
            digest=hashlib.sha256(b"illustrative-firmware-bytes").hexdigest(),
            verification=VerificationStatus.ILLUSTRATIVE,
            provenance="example",
            limitations=["illustrative data only"],
        ),
        calibration=CaptureRegion(
            region_id="calibration",
            region_kind="calibration",
            status=CaptureStatus.PROTECTED,
            source_controller_id=controller_id,
            timestamp=now,
            verification=VerificationStatus.ILLUSTRATIVE,
            limitations=["calibration region is security-protected on source"],
            protected_dependency_ref="immobilizer_or_security_access_required",
        ),
        configuration=CaptureRegion(
            region_id="configuration",
            region_kind="configuration",
            status=CaptureStatus.NOT_ATTEMPTED,
            source_controller_id=controller_id,
            verification=VerificationStatus.ILLUSTRATIVE,
            limitations=["capture not attempted in this example"],
        ),
        other_regions=[
            CaptureRegion(
                region_id="security_keys",
                region_kind="protected",
                status=CaptureStatus.PROTECTED,
                source_controller_id=controller_id,
                verification=VerificationStatus.ILLUSTRATIVE,
                limitations=["keys and credentials are never extracted"],
                protected_dependency_ref="security_access_required",
            )
        ],
        compatibility_constraints=["incomplete_capture"],
        provenance=[
            EvidenceRef(
                source="platform.example",
                timestamp=now,
                provenance="illustrative",
                verification_method="constructed",
                confidence=Confidence.ILLUSTRATIVE,
                detail="Example incomplete package for tests and documentation.",
            )
        ],
        recovery_requirements=[
            "security_access_for_calibration",
            "re-capture_configuration",
            "verify_firmware_digest_on_restore",
        ],
    )
    return pkg.seal()
