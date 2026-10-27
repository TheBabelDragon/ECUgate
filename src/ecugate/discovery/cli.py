"""Machine-readable discovery CLI.

Examples
--------
  python -m ecugate.discovery.cli --simulate
  python -m ecugate.discovery.cli --host
  python -m ecugate.discovery.cli --simulate --inventory --save /tmp/bench.json
"""

from __future__ import annotations

import argparse
import json
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
    mode.add_argument("--simulate", action="store_true", default=False, help="Simulated ECU interface.")
    mode.add_argument("--host", action="store_true", default=False, help="Opt-in host serial/USB scan.")
    parser.add_argument("--simulate-and-host", action="store_true", help="Simulated + host enumeration.")
    parser.add_argument("--manifests", default=None, help="Device manifest directory.")
    parser.add_argument("--deps", action="store_true", help="Print optional dependency status.")
    parser.add_argument("--inventory", action="store_true", help="Emit schema v2 multi-device inventory.")
    parser.add_argument("--save", default=None, help="Write report JSON to this path.")
    parser.add_argument("--compact", action="store_true", help="Compact JSON.")
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
    if args.inventory:
        payload = eng.discover_inventory().to_dict()
    else:
        payload = eng.discover().to_dict()
    payload["cli"] = {
        "simulate": simulate,
        "host": host,
        "manifests": manifests,
        "inventory": bool(args.inventory),
        "optional_deps": optional_dependency_status(),
    }
    text = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if args.compact
        else json.dumps(payload, indent=2, sort_keys=True)
    )
    print(text)
    if args.save:
        Path(args.save).write_text(text)
    assert payload.get("authorized") is False
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
