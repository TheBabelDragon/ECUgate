"""Preflight policy engine tests — no hardware."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ecugate.preflight.authorization import AuthorizationStore
from ecugate.preflight.engine import PreflightEngine
from ecugate.preflight.models import (
    ArtifactSpec,
    BenchConfiguration,
    Confidence,
    EvidenceRecord,
    ExecutionMode,
    ExecutionOutcome,
    OperationProposal,
    PowerEvidence,
    PreflightDecision,
    TargetIdentity,
    utc_now_iso,
)
from ecugate.preflight.simulator import SimulatorExecutor


def _fresh_evidence(**kwargs):
    defaults = dict(
        source="test",
        timestamp=utc_now_iso(),
        provenance="unit_test",
        verification_method="fixture",
        confidence=Confidence.CONFIRMED,
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )
    defaults.update(kwargs)
    return EvidenceRecord(**defaults)


def _complete_write_bench() -> BenchConfiguration:
    return BenchConfiguration(
        target=TargetIdentity(
            ecu_id="sim-ecu-1",
            hardware_id="hw1",
            software_id="sw1",
            calibration_id="cal1",
            family="sim.ecu",
            verified=True,
            confidence=Confidence.CONFIRMED,
            evidence=[_fresh_evidence(source="bench")],
        ),
        adapter_id="sim-adapter",
        programmer_id="sim-prog",
        power_source_id="sim-psu",
        protocol="sim.v1",
        relationships_confirmed=True,
        power=PowerEvidence(
            voltage_v=13.5,
            voltage_min=11.5,
            voltage_max=14.5,
            measured=True,
            evidence=[_fresh_evidence(source="dmm")],
        ),
        session_id="sess-1",
        session_valid=True,
        recovery_plan="restore prior calibration from backup",
    )


def test_complete_write_preflight_ready_with_grant():
    proposal = OperationProposal(
        operation_id="sim.write_param",
        arguments={"param": "timing", "value": 12},
        bench=_complete_write_bench(),
        execution_mode=ExecutionMode.SIMULATOR,
    )
    store = AuthorizationStore()
    grant = store.issue(proposal)
    result = PreflightEngine().evaluate(proposal, grant=grant)
    assert result.decision == PreflightDecision.READY
    assert result.blockers == []
    assert result.to_dict()["authorized"] is False


def test_missing_target_blocks():
    proposal = OperationProposal(
        operation_id="sim.write_param",
        arguments={},
        bench=BenchConfiguration(target=TargetIdentity(verified=False), session_valid=True, session_id="s"),
    )
    r = PreflightEngine().evaluate(proposal)
    assert "target_identity_unverified" in r.blockers
    assert "authorization_missing" in r.blockers


def test_stale_evidence():
    bench = _complete_write_bench()
    bench.target.evidence = [
        _fresh_evidence(expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
    ]
    proposal = OperationProposal(operation_id="sim.write_param", arguments={}, bench=bench)
    store = AuthorizationStore()
    grant = store.issue(proposal)
    r = PreflightEngine().evaluate(proposal, grant=grant)
    assert "evidence_stale" in r.blockers


def test_unsupported_profile():
    bench = _complete_write_bench()
    bench.target.family = "real.unknown"
    proposal = OperationProposal(operation_id="sim.write_param", arguments={}, bench=bench)
    r = PreflightEngine().evaluate(proposal)
    assert "unsupported_target_profile" in r.blockers


def test_bench_topology_incomplete():
    bench = _complete_write_bench()
    bench.relationships_confirmed = False
    proposal = OperationProposal(operation_id="sim.write_param", arguments={}, bench=bench)
    r = PreflightEngine().evaluate(proposal)
    assert "bench_topology_incomplete" in r.blockers


def test_power_out_of_range():
    bench = _complete_write_bench()
    bench.power.voltage_v = 9.0
    proposal = OperationProposal(operation_id="sim.write_param", arguments={}, bench=bench)
    store = AuthorizationStore()
    grant = store.issue(proposal)
    r = PreflightEngine().evaluate(proposal, grant=grant)
    assert "power_measurement_out_of_range" in r.blockers


def test_operation_not_allowlisted():
    r = PreflightEngine().evaluate(OperationProposal(operation_id="flash_real_ecu", arguments={}))
    assert r.blockers == ["operation_not_allowlisted"]


def test_authorization_scope_mismatch_on_arg_change():
    bench = _complete_write_bench()
    proposal = OperationProposal(operation_id="sim.write_param", arguments={"param": "a", "value": 1}, bench=bench)
    store = AuthorizationStore()
    grant = store.issue(proposal)
    proposal2 = OperationProposal(operation_id="sim.write_param", arguments={"param": "a", "value": 2}, bench=bench)
    r = PreflightEngine().evaluate(proposal2, grant=grant)
    assert "authorization_scope_mismatch" in r.blockers


def test_expired_grant():
    bench = _complete_write_bench()
    proposal = OperationProposal(operation_id="sim.write_param", arguments={}, bench=bench)
    store = AuthorizationStore()
    grant = store.issue(proposal, ttl_seconds=-1)
    r = PreflightEngine().evaluate(proposal, grant=grant)
    assert "authorization_expired" in r.blockers


def test_single_use_grant_replay():
    bench = _complete_write_bench()
    proposal = OperationProposal(operation_id="sim.write_param", arguments={"x": 1}, bench=bench)
    store = AuthorizationStore()
    grant = store.issue(proposal)
    ex = SimulatorExecutor(auth_store=store)
    assert ex.execute(proposal, grant=grant, scenario="success").outcome == ExecutionOutcome.SUCCEEDED
    assert ex.execute(proposal, grant=grant, scenario="success").outcome == ExecutionOutcome.DENIED


def test_physical_write_denied():
    bench = _complete_write_bench()
    proposal = OperationProposal(
        operation_id="sim.write_param", arguments={}, bench=bench, execution_mode=ExecutionMode.PHYSICAL
    )
    store = AuthorizationStore()
    grant = store.issue(proposal)
    r = PreflightEngine().evaluate(proposal, grant=grant)
    assert "physical_write_not_implemented" in r.blockers
    receipt = SimulatorExecutor(auth_store=store).execute(proposal, grant=grant)
    assert receipt.outcome == ExecutionOutcome.DENIED
    assert receipt.message == "physical_write_not_implemented"


def test_read_does_not_require_auth():
    proposal = OperationProposal(
        operation_id="sim.read_state",
        arguments={},
        bench=BenchConfiguration(
            target=TargetIdentity(ecu_id="sim-1", family="sim.ecu", verified=True, confidence=Confidence.CONFIRMED)
        ),
    )
    r = PreflightEngine().evaluate(proposal)
    assert "authorization_missing" not in r.blockers
    assert r.decision == PreflightDecision.READY


def test_artifact_integrity():
    bench = _complete_write_bench()
    proposal = OperationProposal(
        operation_id="sim.flash_image",
        arguments={},
        bench=bench,
        artifact=ArtifactSpec(artifact_id="img1", digest="abc", compatible_families=["sim.ecu"], integrity_verified=False),
    )
    r = PreflightEngine().evaluate(proposal)
    assert "artifact_integrity_unverified" in r.blockers


def test_dry_run_no_mutation():
    proposal = OperationProposal(
        operation_id="sim.read_state",
        arguments={},
        bench=BenchConfiguration(
            target=TargetIdentity(ecu_id="s", family="sim.ecu", verified=True, confidence=Confidence.CONFIRMED)
        ),
        execution_mode=ExecutionMode.DRY_RUN,
    )
    receipt = SimulatorExecutor().execute(proposal)
    assert receipt.message == "dry_run_no_mutation"


def test_preflight_not_auto_grant():
    proposal = OperationProposal(operation_id="sim.write_param", arguments={}, bench=_complete_write_bench())
    r = PreflightEngine().evaluate(proposal)
    assert "authorization_missing" in r.blockers
    assert r.to_dict()["authorized"] is False


def test_bypass_executor_still_checks_policy():
    proposal = OperationProposal(operation_id="sim.write_param", arguments={}, bench=_complete_write_bench())
    receipt = SimulatorExecutor().execute(proposal, grant=None)
    assert receipt.outcome == ExecutionOutcome.DENIED


def test_cli_capabilities():
    from ecugate.preflight.cli import main

    assert main(["capabilities", "--compact"]) == 0
