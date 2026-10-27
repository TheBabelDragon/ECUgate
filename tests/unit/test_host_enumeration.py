"""Host enumerator and discovery integration tests (mocked — no real hardware)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ecugate.discovery.enumerator import (
    CompositeEnumerator,
    EmptyEnumerator,
    StaticEnumerator,
)
from ecugate.discovery.host import (
    HostEnumerator,
    HostSerialEnumerator,
    HostUSBEnumerator,
    optional_dependency_status,
)
from ecugate.discovery.manifests import DeviceManifest, FieldConfidence, PowerRequirements
from ecugate.discovery.pipeline import CapabilityLevel, DiscoveryEngine, InterfaceRecord


def test_empty_enumerator():
    assert EmptyEnumerator().enumerate() == []


def test_static_enumerator():
    iface = InterfaceRecord(interface_id="a", interface_type="serial", path="/dev/ttyUSB0")
    s = StaticEnumerator([iface])
    assert len(s.enumerate()) == 1
    s.inject(InterfaceRecord(interface_id="b", interface_type="usb"))
    assert len(s.enumerate()) == 2
    s.clear()
    assert s.enumerate() == []


def test_composite_dedupes():
    a = InterfaceRecord(interface_id="x", interface_type="serial")
    b = InterfaceRecord(interface_id="x", interface_type="serial")
    c = InterfaceRecord(interface_id="y", interface_type="usb")
    comp = CompositeEnumerator(StaticEnumerator([a]), StaticEnumerator([b, c]))
    ids = [i.interface_id for i in comp.enumerate()]
    assert ids == ["x", "y"]


def test_host_serial_without_pyserial_path_scan():
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("serial"):
            raise ImportError("mocked missing pyserial")
        return real_import(name, *args, **kwargs)

    with patch.object(builtins, "__import__", fake_import):
        with patch("ecugate.discovery.host.platform.system", return_value="Linux"):
            with patch("ecugate.discovery.host.glob.glob", return_value=["/dev/ttyUSB0"]):
                with patch("ecugate.discovery.host.os.path.exists", return_value=True):
                    with patch("ecugate.discovery.host.os.path.realpath", side_effect=lambda p: p):
                        with patch.object(
                            HostSerialEnumerator, "_linux_usb_ids_for_tty", return_value=("0403", "6001")
                        ):
                            ports = HostSerialEnumerator().enumerate()
    assert len(ports) == 1
    assert ports[0].interface_type == "serial"
    assert ports[0].vendor_id == "0403"
    assert ports[0].product_id == "6001"
    assert ports[0].metadata.get("enumerator") == "path_scan"


def test_host_serial_pyserial_mocked():
    enum = HostSerialEnumerator()
    with patch.object(HostSerialEnumerator, "_enumerate_pyserial", return_value=None):
        with patch.object(
            HostSerialEnumerator,
            "_enumerate_paths",
            return_value=[
                InterfaceRecord(
                    interface_id="serial:/dev/ttyUSB1",
                    interface_type="serial",
                    path="/dev/ttyUSB1",
                    vendor_id="0403",
                    product_id="6001",
                    metadata={"enumerator": "path_scan"},
                )
            ],
        ):
            ports = enum.enumerate()
    assert len(ports) == 1
    assert ports[0].path == "/dev/ttyUSB1"
    fake = [
        InterfaceRecord(
            interface_id="serial:/dev/ttyUSB1",
            interface_type="serial",
            path="/dev/ttyUSB1",
            vendor_id="0403",
            product_id="6001",
            metadata={"enumerator": "pyserial"},
        )
    ]
    with patch.object(HostSerialEnumerator, "_enumerate_pyserial", return_value=fake):
        ports2 = HostSerialEnumerator().enumerate()
    assert ports2[0].metadata.get("enumerator") == "pyserial"


def test_host_usb_sysfs_mocked():
    with patch.object(HostUSBEnumerator, "_enumerate_pyusb", return_value=None):
        with patch.object(
            HostUSBEnumerator,
            "_enumerate_sysfs",
            return_value=[
                InterfaceRecord(
                    interface_id="usb:sysfs:1-1:0403:6001",
                    interface_type="usb",
                    path="/sys/bus/usb/devices/1-1",
                    vendor_id="0403",
                    product_id="6001",
                    serial="SN1",
                    metadata={"enumerator": "sysfs"},
                )
            ],
        ):
            result = HostUSBEnumerator().enumerate()
    assert len(result) == 1
    assert result[0].vendor_id == "0403"


def test_optional_dependency_status():
    st = optional_dependency_status()
    assert "platform" in st
    assert "pyserial" in st
    assert "pyusb" in st
    assert isinstance(st["pyserial"], bool)


def test_discovery_with_host_enumerator_unknown_device():
    host_iface = InterfaceRecord(
        interface_id="serial:/dev/ttyUSB9",
        interface_type="serial",
        path="/dev/ttyUSB9",
        vendor_id="1234",
        product_id="5678",
    )
    eng = DiscoveryEngine(manifests=[], enumerator=StaticEnumerator([host_iface]))
    report = eng.discover()
    assert report.device_id is None
    assert report.programming_ready is False
    assert "device_identity_unconfirmed" in report.programming_blockers
    assert report.to_dict()["authorized"] is False


def test_discovery_host_match_manifest():
    m = DeviceManifest(
        device_id="ft232.example",
        manufacturer="Example",
        model="FT232 Adapter",
        interface_type="serial",
        vendor_id="0403",
        product_id="6001",
        supported_operations=["read"],
        power=PowerRequirements(
            voltage_min=4.5, voltage_max=5.5, confidence=FieldConfidence.CONFIRMED
        ),
    )
    host_iface = InterfaceRecord(
        interface_id="serial:/dev/ttyUSB0",
        interface_type="serial",
        path="/dev/ttyUSB0",
        vendor_id="0403",
        product_id="6001",
    )
    eng = DiscoveryEngine(manifests=[m], enumerator=StaticEnumerator([host_iface]))
    report = eng.discover()
    assert report.device_id == "ft232.example"
    assert report.matched_manifest_id == "ft232.example"
    assert report.programming_ready is False
    assert report.to_dict()["authorized"] is False


def test_discovery_never_authorizes_with_host():
    eng = DiscoveryEngine(
        enumerator=StaticEnumerator(
            [InterfaceRecord(interface_id="u", interface_type="usb", vendor_id="0001", product_id="0001")]
        )
    )
    d = eng.discover().to_dict()
    assert d["authorized"] is False
    assert eng.discover().level != CapabilityLevel.AUTHORIZED


def test_incomplete_descriptor_unknown_fields():
    iface = InterfaceRecord(interface_id="serial:/dev/ttyS0", interface_type="serial", path="/dev/ttyS0")
    eng = DiscoveryEngine(manifests=[], enumerator=StaticEnumerator([iface]))
    report = eng.discover()
    assert "device_id" in report.unknown_fields
    assert report.matched_manifest_id is None


def test_conflicting_manifests_with_host_iface():
    m1 = DeviceManifest(device_id="a", vendor_id="aaaa", product_id="bbbb", interface_type="usb")
    m2 = DeviceManifest(device_id="b", vendor_id="aaaa", product_id="bbbb", interface_type="usb")
    iface = InterfaceRecord(
        interface_id="usb:1", interface_type="usb", vendor_id="aaaa", product_id="bbbb"
    )
    eng = DiscoveryEngine(manifests=[m1, m2], enumerator=StaticEnumerator([iface]))
    report = eng.discover()
    assert report.conflicts
    assert report.programming_ready is False
    assert "conflicting_manifest_matches" in report.programming_blockers


def test_host_enumerator_composite_with_sim():
    sim = InterfaceRecord(
        interface_id="sim0",
        interface_type="simulated",
        vendor_id="SIMU",
        product_id="ECU1",
        metadata={"device_id": "sim.ecu.v1"},
    )
    host = InterfaceRecord(
        interface_id="serial:/dev/ttyUSB0",
        interface_type="serial",
        vendor_id="0403",
        product_id="6001",
    )
    eng = DiscoveryEngine(enumerator=StaticEnumerator([host]))
    eng.inject_simulated_interface(sim)
    ifaces = eng.enumerate()
    assert len(ifaces) == 2
    report = eng.discover()
    assert report.interfaces[0].interface_id == "sim0"


def test_missing_driver_graceful():
    class BoomEnumerator:
        def enumerate(self):
            raise OSError("driver not loaded")

    eng = DiscoveryEngine(enumerator=BoomEnumerator())
    report = eng.discover()
    assert report.programming_ready is False
    assert "no_interface_detected" in report.programming_blockers or report.interfaces == []
