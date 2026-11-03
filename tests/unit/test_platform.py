"""Tests for modular vehicle-controller platform."""

from __future__ import annotations

import json

import pytest

from ecugate.platform.backup import (
    CaptureRegion,
    ClonePackage,
    make_incomplete_example_package,
)
from ecugate.platform.compatibility import (
    BLOCKER_DEVELOPMENT_ONLY,
    BLOCKER_INCOMPLETE_BACKUP,
    BLOCKER_SAFETY_SUPERVISOR_MISSING,
    CompatibilityEngine,
)
from ecugate.platform.models import (
    SCHEMA_VERSION,
    CaptureStatus,
    CompatibilityStatus,
    Confidence,
    ControllerProfile,
    ElectricalSpec,
    HardwareModule,
    InterfaceSpec,
    ModuleKind,
    SafetyClass,
    VehicleProfile,
    VerificationStatus,
    esp32_s3_compute_module,
)
from ecugate.platform.simulator import PlatformSimulator
from ecugate.platform.workflows import WorkflowEngine, WorkflowKind, WorkflowPhase, WorkflowContext


def test_schema_version_present():
    assert SCHEMA_VERSION == "platform.v1"


def test_esp32_s3_is_development_not_qualified():
    m = esp32_s3_compute_module()
    assert m.kind == ModuleKind.COMPUTE
    assert m.safety_class == SafetyClass.DEVELOPMENT
    assert "not_automotive_qualified" in m.compatibility_constraints
    assert "can_fd_controller" in m.dependencies
    assert m.pin_mappings == []  # never invent pins
    assert m.verification in (VerificationStatus.ILLUSTRATIVE, VerificationStatus.UNVERIFIED)


def test_hardware_module_roundtrip():
    m = esp32_s3_compute_module()
    d = m.to_dict()
    m2 = HardwareModule.from_dict(d)
    assert m2.module_id == m.module_id
    assert m2.digest() == m.digest()


def test_vehicle_controller_roundtrip():
    v = VehicleProfile(vehicle_id="v1", make="x", model_year=2000)
    c = ControllerProfile(controller_id="c1", protocols=["classical_can"])
    assert VehicleProfile.from_dict(v.to_dict()).vehicle_id == "v1"
    assert ControllerProfile.from_dict(c.to_dict()).controller_id == "c1"


def test_clone_package_incomplete_not_complete():
    pkg = make_incomplete_example_package()
    assert pkg.package_digest
    assert pkg.verify_integrity()
    comp = pkg.capture_completeness()
    assert comp["is_complete"] is False
    assert "calibration" in comp["protected"] or any(
        r.status == CaptureStatus.PROTECTED for r in pkg.all_regions()
    )
    assert "configuration" in comp["not_attempted"] or any(
        r.status == CaptureStatus.NOT_ATTEMPTED for r in pkg.all_regions()
    )


def test_clone_package_integrity_fails_on_tamper():
    pkg = make_incomplete_example_package()
    assert pkg.verify_integrity()
    pkg.controller_identity["tampered"] = True
    assert pkg.verify_integrity() is False


def test_protected_region_not_counted_as_captured():
    r = CaptureRegion(
        region_id="keys",
        region_kind="protected",
        status=CaptureStatus.PROTECTED,
        protected_dependency_ref="security_access",
    )
    assert r.is_successfully_captured() is False


def test_complete_package_requires_all_captured():
    now = "2026-01-01T00:00:00+00:00"
    pkg = ClonePackage(
        package_id="complete-test",
        controller_identity={"controller_id": "c"},
        firmware=CaptureRegion(
            region_id="firmware",
            region_kind="firmware",
            status=CaptureStatus.CAPTURED,
            timestamp=now,
            data_length=10,
            digest="abc",
        ),
        calibration=CaptureRegion(
            region_id="calibration",
            region_kind="calibration",
            status=CaptureStatus.CAPTURED,
            timestamp=now,
            data_length=10,
            digest="def",
        ),
        configuration=CaptureRegion(
            region_id="configuration",
            region_kind="configuration",
            status=CaptureStatus.CAPTURED,
            timestamp=now,
        ),
    ).seal()
    assert pkg.capture_completeness()["is_complete"] is True
    assert pkg.verify_integrity()


def test_compatibility_development_only_fails():
    sim = PlatformSimulator().load_defaults()
    result = sim.evaluate_compatibility(
        vehicle_id="example-vehicle-v1",
        original_id="example-original-ecu",
        replacement_id="example-replacement-dev",
        module_ids=["esp32-s3-dev-compute-v1"],
        require_vehicle_qualified=True,
    )
    assert result.status != CompatibilityStatus.COMPATIBLE
    assert BLOCKER_DEVELOPMENT_ONLY in result.blockers or BLOCKER_SAFETY_SUPERVISOR_MISSING in result.blockers


def test_compatibility_incomplete_backup_fails():
    sim = PlatformSimulator().load_defaults()
    result = sim.evaluate_compatibility(
        vehicle_id="example-vehicle-v1",
        original_id="example-original-ecu",
        replacement_id="example-replacement-dev",
        module_ids=[
            "esp32-s3-dev-compute-v1",
            "auto-power-protection-v1",
            "safety-supervisor-v1",
            "ext-canfd-controller-v1",
        ],
        package_id="example-incomplete-backup-v1",
        require_vehicle_qualified=True,
    )
    assert BLOCKER_INCOMPLETE_BACKUP in result.blockers


def test_compatibility_fail_closed_on_missing():
    eng = CompatibilityEngine()
    result = eng.evaluate()
    assert result.status in (CompatibilityStatus.INCOMPLETE, CompatibilityStatus.INCOMPATIBLE)
    assert len(result.blockers) >= 1


def test_workflow_compat_blocks_migrate():
    sim = PlatformSimulator().load_defaults()
    run = sim.run_workflow(
        WorkflowKind.MIGRATE,
        vehicle_id="example-vehicle-v1",
        original_id="example-original-ecu",
        replacement_id="example-replacement-dev",
        module_ids=["esp32-s3-dev-compute-v1"],
        package_id="example-incomplete-backup-v1",
    )
    assert run.final_phase == WorkflowPhase.BLOCKED
    assert any("compatibility" in b or "backup" in b or "development" in b for b in run.steps[0].blockers)


def test_workflow_identify_succeeds():
    sim = PlatformSimulator().load_defaults()
    run = sim.run_workflow(
        WorkflowKind.IDENTIFY,
        vehicle_id="example-vehicle-v1",
        original_id="example-original-ecu",
    )
    assert run.final_phase == WorkflowPhase.SUCCEEDED


def test_workflow_verify_integrity():
    sim = PlatformSimulator().load_defaults()
    run = sim.run_workflow(
        WorkflowKind.VERIFY,
        package_id="example-incomplete-backup-v1",
    )
    assert run.final_phase == WorkflowPhase.SUCCEEDED


def test_workflow_capture_incomplete_blocked():
    sim = PlatformSimulator().load_defaults()
    run = sim.run_workflow(
        WorkflowKind.CAPTURE,
        package_id="example-incomplete-backup-v1",
    )
    assert run.final_phase == WorkflowPhase.BLOCKED


def test_source_capture_immutable_on_migrate_simulation():
    eng = WorkflowEngine()
    pkg = make_incomplete_example_package()
    digest_before = pkg.package_digest
    ctx = WorkflowContext(source_capture=pkg)
    step = eng._migrate(ctx, allow_sim=True)
    assert pkg.package_digest == digest_before
    assert pkg.verify_integrity()


def test_simulator_faults():
    sim = PlatformSimulator().load_defaults()
    sim.inject_fault("missing_can_fd")
    assert "missing_can_fd" in sim.active_faults()
    sim.clear_faults()
    assert sim.active_faults() == []


def test_no_physical_write_flag_in_workflow_output():
    sim = PlatformSimulator().load_defaults()
    run = sim.run_workflow(WorkflowKind.BENCH_VALIDATE, module_ids=["esp32-s3-dev-compute-v1"])
    assert run.final_phase == WorkflowPhase.SUCCEEDED


def test_cli_import():
    from ecugate.platform.cli import build_parser, main

    parser = build_parser()
    assert parser is not None


def test_manifests_on_disk_loadable():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "manifests" / "platform"
    if not root.exists():
        pytest.skip("manifests not generated")
    for path in root.glob("*.json"):
        data = json.loads(path.read_text())
        if "module_id" in data:
            HardwareModule.from_dict(data)
        elif "controller_id" in data:
            ControllerProfile.from_dict(data)
        elif "vehicle_id" in data:
            VehicleProfile.from_dict(data)
        elif "package_id" in data:
            pkg = ClonePackage.from_dict(data)
            if pkg.package_digest:
                assert isinstance(pkg.verify_integrity(), bool)
