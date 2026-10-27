"""CLI for opt-in host discovery and read-only vehicle diagnostics."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from ecugate.vehicle_io.models import DiagnosticOutcome
from ecugate.vehicle_io.session import VehicleSession
from ecugate.vehicle_io.transport import FakeSerialTransport, PyserialTransport, TransportError


def _print(obj: Any, compact: bool = False) -> None:
    if compact:
        print(json.dumps(obj, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(obj, indent=2, sort_keys=True))


def cmd_discover(args: argparse.Namespace) -> int:
    from ecugate.discovery.host import HostEnumerator, optional_dependency_status

    if not args.host and not args.simulate:
        print("error: specify --host and/or --simulate (refusing to open devices implicitly)", file=sys.stderr)
        return 2
    interfaces: List[Dict[str, Any]] = []
    if args.simulate:
        interfaces.append(
            {
                "interface_id": "sim:obd0",
                "interface_type": "simulated",
                "path": "sim:obd0",
                "note": "simulation only — no vehicle traffic",
            }
        )
    if args.host:
        for iface in HostEnumerator(serial=True, usb=True).enumerate():
            interfaces.append(iface.to_dict())
    payload = {
        "interfaces": interfaces,
        "count": len(interfaces),
        "vehicle_commands_sent": False,
        "authorized_write": False,
        "optional_deps": optional_dependency_status(),
        "selection_required": len(interfaces) > 1,
    }
    _print(payload, args.compact)
    return 0


def _make_transport(args: argparse.Namespace):
    if args.simulate:
        responses = [
            b"ELM327 v1.5\r\r>",
            b"OK\r>",
            b"OK\r>",
            b"OK\r>",
            b"OK\r>",
            b"OK\r>",
            b"A\r>",
        ]
        return FakeSerialTransport(responses), "sim:obd0"
    if not args.device:
        raise SystemExit("error: --device PATH required unless --simulate")
    return PyserialTransport(args.device, baudrate=args.baud), args.device


def cmd_adapter_info(args: argparse.Namespace) -> int:
    try:
        transport, path = _make_transport(args)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2
    session = VehicleSession(transport, path)
    try:
        info = session.open()
        payload = info.to_dict()
        payload["authorized_write"] = False
        _print(payload, args.compact)
        return 0
    except Exception as e:
        _print({"error": str(e), "authorized_write": False}, args.compact)
        return 1
    finally:
        session.close()


def cmd_diagnostics(args: argparse.Namespace) -> int:
    if not args.read_only:
        print("error: --read-only is required", file=sys.stderr)
        return 2
    try:
        transport, path = _make_transport(args)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.simulate and isinstance(transport, FakeSerialTransport):
        transport.queue_response(b"41 00 BE 1F A8 13\r>")
        transport.queue_response(b"41 0C 1A F8\r>")
        transport.queue_response(b"43 01 33 00 00 00 00\r>")
    session = VehicleSession(transport, path)
    try:
        info = session.open()
        support = session.read_pid("00")
        results = {
            "session": info.to_dict(),
            "pid_support": support.to_dict(),
            "authorized_write": False,
            "read_only": True,
        }
        _print(results, args.compact)
        return 0 if support.outcome != DiagnosticOutcome.DENIED else 1
    except Exception as e:
        _print({"error": str(e), "authorized_write": False}, args.compact)
        return 1
    finally:
        session.close()


def cmd_read_pids(args: argparse.Namespace) -> int:
    try:
        transport, path = _make_transport(args)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2
    pid_map = {"rpm": "0c", "speed": "0d", "coolant": "05", "load": "04"}
    names = [p.strip().lower() for p in args.pids.split(",") if p.strip()]
    if args.simulate and isinstance(transport, FakeSerialTransport):
        samples = {
            "0c": b"41 0C 1A F8\r>",
            "0d": b"41 0D 32\r>",
            "05": b"41 05 64\r>",
            "04": b"41 04 7F\r>",
        }
        for n in names:
            transport.queue_response(samples.get(pid_map.get(n, n), b"NO DATA\r>"))
    session = VehicleSession(transport, path)
    try:
        session.open()
        out = []
        for n in names:
            pid = pid_map.get(n, n.replace("0x", "").zfill(2))
            out.append(session.read_pid(pid).to_dict())
        _print({"results": out, "authorized_write": False}, args.compact)
        return 0
    except Exception as e:
        _print({"error": str(e), "authorized_write": False}, args.compact)
        return 1
    finally:
        session.close()


def cmd_read_dtcs(args: argparse.Namespace) -> int:
    try:
        transport, path = _make_transport(args)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.simulate and isinstance(transport, FakeSerialTransport):
        transport.queue_response(b"43 01 33 00 00\r>")
    session = VehicleSession(transport, path)
    try:
        session.open()
        res = session.read_dtcs()
        _print(res.to_dict(), args.compact)
        return 0
    except Exception as e:
        _print({"error": str(e), "authorized_write": False}, args.compact)
        return 1
    finally:
        session.close()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="ecugate-vehicle", description="Read-only OBD-II vehicle I/O")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--device", default=None)
        p.add_argument("--simulate", action="store_true")
        p.add_argument("--baud", type=int, default=38400)
        p.add_argument("--json", action="store_true", default=True)
        p.add_argument("--compact", action="store_true")

    p_disc = sub.add_parser("discover", help="Enumerate interfaces; no vehicle commands")
    p_disc.add_argument("--host", action="store_true")
    p_disc.add_argument("--simulate", action="store_true")
    p_disc.add_argument("--compact", action="store_true")
    p_disc.set_defaults(func=cmd_discover)

    p_ai = sub.add_parser("adapter-info", help="Identify adapter")
    add_common(p_ai)
    p_ai.set_defaults(func=cmd_adapter_info)

    p_diag = sub.add_parser("diagnostics", help="Read-only diagnostic discovery")
    add_common(p_diag)
    p_diag.add_argument("--read-only", action="store_true", required=True)
    p_diag.set_defaults(func=cmd_diagnostics)

    p_pids = sub.add_parser("read-pids", help="Read allowlisted Mode 01 PIDs")
    add_common(p_pids)
    p_pids.add_argument("--pids", default="rpm,speed,coolant")
    p_pids.set_defaults(func=cmd_read_pids)

    p_dtc = sub.add_parser("read-dtcs", help="Read stored DTCs (Mode 03)")
    add_common(p_dtc)
    p_dtc.set_defaults(func=cmd_read_dtcs)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
