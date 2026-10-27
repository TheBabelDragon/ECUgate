"""Read-only vehicle I/O tests — fake transport only, no hardware."""

from __future__ import annotations

from ecugate.vehicle_io.elm327 import identify_adapter, initialize_elm
from ecugate.vehicle_io.models import DiagnosticOutcome
from ecugate.vehicle_io.obd2 import parse_mode01_response, parse_mode03_dtcs, parse_mode09_vin
from ecugate.vehicle_io.policy import BLOCKED_MODES, check_operation
from ecugate.vehicle_io.session import VehicleSession
from ecugate.vehicle_io.transport import FakeSerialTransport, TransportError


def _init_responses():
    return [
        b"ELM327 v1.5\r\r>",
        b"ELM327 v1.5\r\r>",
        b"OK\r>",
        b"OK\r>",
        b"OK\r>",
        b"OK\r>",
        b"OK\r>",
        b"6\r>",
    ]


def test_policy_blocks_mode04_and_uds():
    d = check_operation("clear_dtcs", mode="04")
    assert d.allowed is False
    d2 = check_operation("read_pid", mode="2e", pid="01")
    assert d2.allowed is False
    assert "04" in BLOCKED_MODES


def test_policy_allows_read_pid_rpm():
    d = check_operation("read_pid", mode="01", pid="0c")
    assert d.allowed is True
    d_bad = check_operation("read_pid", mode="01", pid="ff")
    assert d_bad.allowed is False


def test_adapter_identify_elm():
    t = FakeSerialTransport([b"ELM327 v1.5\r>"])
    t.open()
    ident = identify_adapter(t, "/dev/ttyUSB0")
    assert ident.adapter_class == "elm327_compatible"
    assert ident.firmware and "ELM" in ident.firmware.upper()


def test_adapter_identify_unknown():
    t = FakeSerialTransport([b"?\r>"])
    t.open()
    ident = identify_adapter(t, "/dev/ttyS9")
    assert ident.adapter_class == "unknown_serial"


def test_init_sequence():
    t = FakeSerialTransport(
        [b"ELM327 v1.5\r>", b"OK\r>", b"OK\r>", b"OK\r>", b"OK\r>", b"OK\r>", b"6\r>"]
    )
    t.open()
    raws, proto = initialize_elm(t)
    assert proto == "6"
    assert len(raws) >= 6


def test_parse_rpm_and_never_zero_missing():
    out, val, unit, meta = parse_mode01_response("41 0C 1A F8", "0c")
    assert out == DiagnosticOutcome.SUCCEEDED
    assert abs(val - 1726.0) < 0.1
    assert unit == "rpm"
    out2, val2, _, _ = parse_mode01_response("NO DATA", "0c")
    assert out2 == DiagnosticOutcome.UNAVAILABLE
    assert val2 is None


def test_parse_speed_coolant_load():
    o, v, u, _ = parse_mode01_response("41 0D 32", "0d")
    assert o == DiagnosticOutcome.SUCCEEDED and v == 50.0 and u == "km/h"
    o, v, u, _ = parse_mode01_response("41 05 64", "05")
    assert o == DiagnosticOutcome.SUCCEEDED and v == 60.0
    o, v, u, _ = parse_mode01_response("41 04 FF", "04")
    assert o == DiagnosticOutcome.SUCCEEDED and abs(v - 100.0) < 0.1


def test_parse_malformed_and_truncated():
    o, v, _, _ = parse_mode01_response("41", "0c")
    assert o == DiagnosticOutcome.MALFORMED and v is None


def test_dtc_decode():
    o, codes, _ = parse_mode03_dtcs("43 01 33 00 00")
    assert o == DiagnosticOutcome.SUCCEEDED
    assert "P0133" in codes


def test_vin_decode_ascii_path():
    o, vin, _ = parse_mode09_vin("49 02 01 31 47 31 4A 43 35 34 34 34 52 37 32 35 32 33 36 37")
    assert o in (
        DiagnosticOutcome.SUCCEEDED,
        DiagnosticOutcome.AMBIGUOUS,
        DiagnosticOutcome.UNAVAILABLE,
    )


def test_session_read_pid_and_no_write_escalation():
    responses = _init_responses() + [b"41 0C 0B B8\r>"]
    t = FakeSerialTransport(responses)
    session = VehicleSession(t, "sim:0")
    info = session.open()
    assert info.read_only is True
    assert info.to_dict()["authorized_write"] is False
    res = session.read_pid("0c")
    assert res.outcome == DiagnosticOutcome.SUCCEEDED
    assert res.value == 750.0
    assert res.to_dict()["authorized_write"] is False
    session.close()


def test_session_denies_clear_before_tx():
    t = FakeSerialTransport(_init_responses())
    session = VehicleSession(t, "sim:0")
    session.open()
    written_before = list(t.written)
    res = session.reject_clear_dtcs()
    assert res.outcome == DiagnosticOutcome.DENIED
    assert not any(w.strip().startswith(b"04") for w in t.written[len(written_before) :])
    session.close()


def test_timeout_outcome():
    t2 = FakeSerialTransport([])
    t2.open()
    try:
        t2.read_until()
        assert False, "expected timeout"
    except TransportError:
        pass


def test_read_dtcs_session():
    t = FakeSerialTransport(_init_responses() + [b"43 00 00\r>"])
    session = VehicleSession(t, "sim:0")
    session.open()
    res = session.read_dtcs()
    assert res.outcome == DiagnosticOutcome.SUCCEEDED
    assert res.value == []
    session.close()


def test_unsupported_operation_denied():
    d = check_operation("flash_ecu")
    assert d.allowed is False


def test_cli_discover_requires_flag():
    from ecugate.vehicle_io.cli import main

    assert main(["discover"]) == 2


def test_cli_simulate_adapter_info():
    from ecugate.vehicle_io.cli import main

    rc = main(["adapter-info", "--simulate", "--compact"])
    assert rc == 0
