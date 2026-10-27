"""Bench topology, multi-interface inventory, and readiness tests (mocked)."""

from __future__ import annotations

from ecugate.discovery.enumerator import StaticEnumerator
from ecugate.discovery.manifests import DeviceManifest, FieldConfidence, PowerRequirements
from ecugate.discovery.pipeline import DiscoveryEngine, InterfaceRecord
from ecugate.discovery.topology import (
    BenchTopology,
    DeviceRole,
    RelationshipType,
    assess_interface,
)


def _ecu_manifest(**kwargs):
    defaults = dict(
        device_id="sim.ecu.v1",
        manufacturer="ECUgate Labs",
        model="Sim ECU",
        interface_type="simulated",
        vendor_id="SIMU",
        product_id="ECU1",
        supported_protocols=["ecugate.sim.v1"],
        supported_operations=["read", "write"],
        power=PowerRequirements(
            voltage_min=11.5,
            voltage_max=14.5,
            voltage_nominal=13.8,
            current_max_a=2.0,
            transient_notes="hold within range during programming",
            confidence=FieldConfidence.CONFIRMED,
        ),
    )
    defaults.update(kwargs)
    return DeviceManifest(**defaults)


def _prog_manifest():
    return DeviceManifest(
        device_id="prog.adapter.v1",
        manufacturer="AdapterCo",
        model="Bench Programmer",
        interface_type="usb",
        vendor_id="0a1b",
        product_id="2c3d",
        supported_protocols=["ecugate.sim.v1"],
        supported_operations=["read"],
        notes="programmer adapter",
        power=PowerRequirements(confidence=FieldConfidence.UNKNOWN),
    )


def _psu_manifest():
    return DeviceManifest(
        device_id="psu.bench.v1",
        manufacturer="PSUCo",
        model="Bench Supply",
        interface_type="usb",
        vendor_id="aaaa",
        product_id="bbbb",
        supported_operations=["read"],
        notes="bench power supply",
        power=PowerRequirements(
            voltage_min=10.0,
            voltage_max=15.0,
            current_max_a=5.0,
            confidence=FieldConfidence.CONFIRMED,
        ),
    )


def test_multiple_interfaces_assessed_independently():
    eng = DiscoveryEngine(manifests=[_ecu_manifest(), _prog_manifest()])
    eng.inject_simulated_interface(
        InterfaceRecord(
            interface_id="sim0",
            interface_type="simulated",
            vendor_id="SIMU",
            product_id="ECU1",
            metadata={"device_id": "sim.ecu.v1"},
        )
    )
    eng.set_enumerator(
        StaticEnumerator(
            [
                InterfaceRecord(
                    interface_id="usb:prog",
                    interface_type="usb",
                    vendor_id="0a1b",
                    product_id="2c3d",
                )
            ]
        )
    )
    inv = eng.discover_inventory()
    assert len(inv.devices) == 2
    ids = {d.interface.interface_id for d in inv.devices}
    assert "sim0" in ids and "usb:prog" in ids
    assert inv.to_dict()["authorized"] is False
    assert inv.schema_version == "2.0"


def test_usb_and_serial_same_vid_not_merged():
    m = DeviceManifest(
        device_id="chip.x",
        vendor_id="0403",
        product_id="6001",
        interface_type="serial",
        supported_operations=["read"],
    )
    topo = BenchTopology(manifests=[m])
    inv = topo.build(
        [
            InterfaceRecord(
                interface_id="serial:/dev/ttyUSB0",
                interface_type="serial",
                path="/dev/ttyUSB0",
                vendor_id="0403",
                product_id="6001",
            ),
            InterfaceRecord(
                interface_id="usb:sysfs:1-1:0403:6001",
                interface_type="usb",
                vendor_id="0403",
                product_id="6001",
            ),
        ]
    )
    assert len(inv.devices) == 2
    assert inv.devices[0].device_record_id != inv.devices[1].device_record_id


def test_unknown_and_conflicting_identities():
    m1 = DeviceManifest(device_id="a", vendor_id="1111", product_id="2222")
    m2 = DeviceManifest(device_id="b", vendor_id="1111", product_id="2222")
    iface = InterfaceRecord(
        interface_id="usb:x", interface_type="usb", vendor_id="1111", product_id="2222"
    )
    dev = assess_interface(iface, [m1, m2])
    assert dev.conflicts
    assert dev.matched_manifest_id is None
    assert len(dev.candidate_manifest_ids) == 2

    unknown = assess_interface(
        InterfaceRecord(interface_id="s", interface_type="serial", path="/dev/ttyS9"),
        [],
    )
    assert "device_id" in unknown.unknown_fields


def test_separate_programmer_ecu_power_roles():
    topo = BenchTopology(manifests=[_ecu_manifest(), _prog_manifest(), _psu_manifest()])
    inv = topo.build(
        [
            InterfaceRecord(
                interface_id="sim0",
                interface_type="simulated",
                vendor_id="SIMU",
                product_id="ECU1",
                metadata={"device_id": "sim.ecu.v1", "role": "target_ecu"},
            ),
            InterfaceRecord(
                interface_id="usb:prog",
                interface_type="usb",
                vendor_id="0a1b",
                product_id="2c3d",
                metadata={"role": "programmer"},
            ),
            InterfaceRecord(
                interface_id="usb:psu",
                interface_type="usb",
                vendor_id="aaaa",
                product_id="bbbb",
                metadata={"role": "power_supply"},
            ),
        ]
    )
    roles = {d.role for d in inv.devices}
    assert DeviceRole.TARGET_ECU in roles
    assert DeviceRole.PROGRAMMER in roles
    assert DeviceRole.POWER_SUPPLY in roles


def test_incomplete_power_blocks_readiness():
    weak = _ecu_manifest(
        power=PowerRequirements(confidence=FieldConfidence.UNKNOWN),
        supported_operations=["write"],
    )
    topo = BenchTopology(manifests=[weak])
    inv = topo.build(
        [
            InterfaceRecord(
                interface_id="sim0",
                interface_type="simulated",
                vendor_id="SIMU",
                product_id="ECU1",
                metadata={"device_id": "sim.ecu.v1", "role": "target_ecu"},
            )
        ]
    )
    assert inv.readiness.ready is False
    assert "ecu_power_requirements" in inv.readiness.blockers
    assert inv.readiness.to_dict()["authorized"] is False


def test_autocomplete_provenance_and_confidence():
    m = _ecu_manifest()
    dev = assess_interface(
        InterfaceRecord(
            interface_id="sim0",
            interface_type="simulated",
            vendor_id="SIMU",
            product_id="ECU1",
            metadata={"device_id": "sim.ecu.v1"},
        ),
        [m],
    )
    model_s = next(s for s in dev.suggestions if s.field == "model")
    assert model_s.confidence == FieldConfidence.CONFIRMED
    assert model_s.evidence

    weak_iface = InterfaceRecord(interface_id="s1", interface_type="serial", path="/dev/ttyUSB0")
    other = DeviceManifest(
        device_id="maybe.adapter",
        interface_type="serial",
        supported_operations=["read"],
    )
    dev2 = assess_interface(weak_iface, [other])
    cand = next(s for s in dev2.suggestions if s.field == "adapter_candidate")
    assert cand.confidence == FieldConfidence.INFERRED


def test_user_confirmed_topology_relationship():
    topo = BenchTopology(manifests=[_ecu_manifest(), _prog_manifest()])
    topo.set_role("usb:prog", DeviceRole.PROGRAMMER)
    topo.set_role("sim0", DeviceRole.TARGET_ECU)
    ifaces = [
        InterfaceRecord(
            interface_id="sim0",
            interface_type="simulated",
            vendor_id="SIMU",
            product_id="ECU1",
            metadata={"device_id": "sim.ecu.v1"},
        ),
        InterfaceRecord(
            interface_id="usb:prog",
            interface_type="usb",
            vendor_id="0a1b",
            product_id="2c3d",
        ),
    ]
    inv_partial = topo.build(ifaces)
    prog2 = next(d for d in inv_partial.devices if d.interface.interface_id == "usb:prog")
    ecu2 = next(d for d in inv_partial.devices if d.interface.interface_id == "sim0")
    rel = topo.confirm_relationship(
        prog2.device_record_id, ecu2.device_record_id, RelationshipType.PROGRAMS, note="confirmed"
    )
    assert rel.user_confirmed is True
    assert rel.confidence == FieldConfidence.USER_PROVIDED
    inv2 = topo.build(ifaces)
    assert any(r.user_confirmed for r in inv2.relationships)


def test_readiness_false_when_mandatory_unresolved():
    inv = BenchTopology(manifests=[]).build([])
    assert inv.readiness.ready is False
    assert inv.readiness.blockers
    assert inv.to_dict()["authorized"] is False


def test_discovery_never_authorizes_inventory():
    eng = DiscoveryEngine(manifests=[_ecu_manifest()])
    eng.inject_simulated_interface(
        InterfaceRecord(
            interface_id="sim0",
            interface_type="simulated",
            vendor_id="SIMU",
            product_id="ECU1",
            metadata={"device_id": "sim.ecu.v1"},
        )
    )
    inv = eng.discover_inventory()
    d = inv.to_dict()
    assert d["authorized"] is False
    assert d["readiness"]["authorized"] is False
    write_req = next(
        r for r in inv.readiness.requirements if r.requirement_id == "write_authorization"
    )
    assert write_req.satisfied is False


def test_backward_compat_discover_report():
    eng = DiscoveryEngine(manifests=[_ecu_manifest()])
    eng.inject_simulated_interface(
        InterfaceRecord(
            interface_id="sim0",
            interface_type="simulated",
            vendor_id="SIMU",
            product_id="ECU1",
            metadata={"device_id": "sim.ecu.v1"},
        )
    )
    report = eng.discover()
    assert report.device_id == "sim.ecu.v1"
    assert report.to_dict()["authorized"] is False
    assert report.schema_version == "1.0"


def test_nominal_13v_not_sufficient():
    ecu = _ecu_manifest(
        power=PowerRequirements(confidence=FieldConfidence.UNKNOWN),
        supported_operations=["write"],
    )
    psu = DeviceManifest(
        device_id="psu.weak",
        vendor_id="cccc",
        product_id="dddd",
        interface_type="usb",
        notes="power supply",
        power=PowerRequirements(voltage_nominal=13.0, confidence=FieldConfidence.INFERRED),
    )
    topo = BenchTopology(manifests=[ecu, psu])
    topo.set_role("sim0", DeviceRole.TARGET_ECU)
    topo.set_role("usb:psu", DeviceRole.POWER_SUPPLY)
    inv = topo.build(
        [
            InterfaceRecord(
                interface_id="sim0",
                interface_type="simulated",
                vendor_id="SIMU",
                product_id="ECU1",
                metadata={"device_id": "sim.ecu.v1"},
            ),
            InterfaceRecord(
                interface_id="usb:psu",
                interface_type="usb",
                vendor_id="cccc",
                product_id="dddd",
            ),
        ]
    )
    assert "ecu_power_requirements" in inv.readiness.blockers
    assert inv.readiness.ready is False
