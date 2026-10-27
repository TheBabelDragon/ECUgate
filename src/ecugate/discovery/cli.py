"""Machine-readable discovery CLI.

Examples
--------
  # Simulation only (default — no host scan)
  python -m ecugate.discovery.cli --simulate

  # Opt-in host enumeration (serial + USB metadata, non-destructive)
  python -m ecugate.discovery.cli --host

  # Host + manifests directory
  python -m ecugate.discovery.cli --host --manifests manifests/devices
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from ecugate.discovery.host import HostEnumerator, optional_dependency_status
from ecugate.discovery.pipeline import DiscoveryEngine, InterfaceRecord


def build_engine(
    *,
    simulate: bool,
    host: bool,
    manifests: Optional[str],
    sim_vid: str = "SIMU",
    sim_pid: str = "ECU1",
    sim_device_id: str = "sim.ecu.v1",
) -> DiscoveryEngine:
    eng = DiscoveryEngine(manifest_dir=manifests)
    if simulate:
        eng.inject_simulated_interface(
            InterfaceRecord(
                interface_id="sim0",
                interface_type="simulated",
                vendor_id=sim_vid,
                product_id=sim_pid,
                metadata={"device_id": sim_device_id},
            )
        )
    if host:
        eng.set_enumerator(HostEnumerator(serial=True, usb=True))
    return eng


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ECUgate discovery — JSON capability report (never authorizes writes)."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--simulate",
        action="store_true",
        default=False,
        help="Inject the built-in simulated ECU interface (no host scan).",
    )
    mode.add_argument(
        "--host",
        action="store_true",
        default=False,
        help="Opt-in: enumerate real serial/USB interfaces on this host (non-destructive).",
    )
    parser.add_argument(
        "--simulate-and-host",
        action="store_true",
        help="Include both simulated interface and host enumeration.",
    )
    parser.add_argument(
        "--manifests",
        default=None,
        help="Directory of device manifest JSON files.",
    )
    parser.add_argument(
        "--deps",
        action="store_true",
        help="Print optional dependency status and exit.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact JSON (no indentation).",
    )
    args = parser.parse_args(argv)

    if args.deps:
        print(json.dumps(optional_dependency_status(), indent=2, sort_keys=True))
        return 0

    simulate = args.simulate or args.simulate_and_host
    host = args.host or args.simulate_and_host
    if not simulate and not host:
        simulate = True

    manifests = args.manifests
    if manifests is None:
        candidate = Path.cwd() / "manifests" / "devices"
        if candidate.is_dir():
            manifests = str(candidate)

    eng = build_engine(simulate=simulate, host=host, manifests=manifests)
    report = eng.discover()
    payload = report.to_dict()
    payload["cli"] = {
        "simulate": simulate,
        "host": host,
        "manifests": manifests,
        "optional_deps": optional_dependency_status(),
    }
    if args.compact:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    assert payload.get("authorized") is False
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
