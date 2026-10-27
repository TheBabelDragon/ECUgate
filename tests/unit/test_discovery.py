"""Hardware discovery acceptance tests. Simulation-first."""

from ecugate.discovery import DiscoveryEngine, CapabilityLevel
from ecugate.discovery.manifests import DeviceManifest, PowerRequirements, FieldConfidence
from ecugate.discovery.pipeline import InterfaceRecord


def _engine_with_sim_manifest():
    m = DeviceManifest(
        device_id="sim.ecu.v1",
        manufacturer="ECUgate Labs",
        model="HorsePowerPoint Simulator",
        firmware_version="1.0.0",
        interface_type="simulated",
        vendor_id="SIMU",
        product_id="ECU1",
        supported_protocols=["ecugate.sim.v1"],
        supported_operations=["read", "propose", "write"],
        power=PowerRequirements(
            voltage_min=11.5,
            voltage_max=14.5,
            voltage_nominal=13.8,
            current_max_a=2.0,
            confidence=FieldConfidence.CONFIRMED,
        ),
    )
    eng = DiscoveryEngine(manifests=[m])
    eng.inject_simulated_interface(
        InterfaceRecord(
            interface_id="sim0",
            interface_type="simulated",
            vendor_id="SIMU",
            product_id="ECU1",
            metadata={"device_id": "sim.ecu.v1", "firmware": "1.0.0"},
        )
    )
    return eng


def test_discover_without_manual_model():
    eng = _engine_with_sim_manifest()
    report = eng.discover()
    assert report.device_id == "sim.ecu.v1"
    assert report.model is not None
    assert report.model.value == "HorsePowerPoint Simulator"
    assert report.model.confidence.value == "confirmed"


def test_autocomplete_from_manifest():
    eng = _engine_with_sim_manifest()
    report = eng.discover()
    fields = {s.field for s in report.suggestions}
    assert "model" in fields
    model_s = next(s for s in report.suggestions if s.field == "model")
    assert model_s.suggested_value == "HorsePowerPoint Simulator"
    assert model_s.explanation


def test_confirmed_vs_unknown():
    eng = DiscoveryEngine(manifests=[])
    eng.inject_simulated_interface(
        InterfaceRecord(interface_id="x", interface_type="serial", vendor_id="????", product_id="????")
    )
    report = eng.discover()
    assert "device_id" in report.unknown_fields
    assert report.matched_manifest_id is None
    assert report.programming_ready is False


def test_conflicting_ids_no_unsafe_adapter():
    m1 = DeviceManifest(device_id="a", vendor_id="V", product_id="P", interface_type="usb")
    m2 = DeviceManifest(device_id="b", vendor_id="V", product_id="P", interface_type="usb")
    eng = DiscoveryEngine(manifests=[m1, m2])
    eng.inject_simulated_interface(
        InterfaceRecord(interface_id="u", interface_type="usb", vendor_id="V", product_id="P")
    )
    report = eng.discover()
    assert report.conflicts
    assert report.programming_ready is False
    assert "conflicting_manifest_matches" in report.programming_blockers


def test_unresolved_power_blocks_programming():
    m = DeviceManifest(
        device_id="weak",
        vendor_id="W",
        product_id="1",
        supported_operations=["write"],
        power=PowerRequirements(confidence=FieldConfidence.UNKNOWN),
    )
    eng = DiscoveryEngine(manifests=[m])
    eng.inject_simulated_interface(
        InterfaceRecord(interface_id="w", interface_type="usb", vendor_id="W", product_id="1")
    )
    report = eng.discover()
    assert report.programming_ready is False
    assert "power_requirements_unresolved" in report.programming_blockers


def test_discovery_never_authorizes():
    eng = _engine_with_sim_manifest()
    report = eng.discover()
    d = report.to_dict()
    assert d["authorized"] is False
    assert report.level != CapabilityLevel.AUTHORIZED


def test_deterministic_machine_readable_report():
    eng = _engine_with_sim_manifest()
    r1 = eng.discover().to_dict()
    r2 = eng.discover().to_dict()
    assert set(r1.keys()) == set(r2.keys())
    assert r1["device_id"] == r2["device_id"]
    assert r1["programming_ready"] == r2["programming_ready"]


def test_manifest_file_load(tmp_path):
    import json
    from ecugate.discovery.manifests import load_manifests

    p = tmp_path / "dev.json"
    p.write_text(
        json.dumps(
            {
                "device_id": "file.1",
                "vendor_id": "F",
                "product_id": "1",
                "interface_type": "simulated",
                "supported_operations": ["read"],
                "power": {"voltage_min": 12.0, "voltage_max": 14.0, "confidence": "confirmed"},
            }
        )
    )
    manifests = load_manifests(tmp_path)
    assert len(manifests) == 1
    eng = DiscoveryEngine(manifests=manifests)
    eng.inject_simulated_interface(
        InterfaceRecord(interface_id="f", interface_type="simulated", vendor_id="F", product_id="1")
    )
    report = eng.discover()
    assert report.device_id == "file.1"
