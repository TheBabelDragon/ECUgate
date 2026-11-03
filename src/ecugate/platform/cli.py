"""ecugate-platform CLI — software-only inspection and simulation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from ecugate.platform.backup import ClonePackage, make_incomplete_example_package
from ecugate.platform.compatibility import CompatibilityEngine
from ecugate.platform.models import (
    ControllerProfile,
    HardwareModule,
    VehicleProfile,
    esp32_s3_compute_module,
)
from ecugate.platform.simulator import PlatformSimulator
from ecugate.platform.workflows import WorkflowKind


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def cmd_profiles(args: argparse.Namespace) -> int:
    sim = PlatformSimulator().load_defaults()
    if args.kind == "vehicle":
        _print({k: v.to_dict() for k, v in sim.vehicles.items()})
    elif args.kind == "controller":
        _print({k: v.to_dict() for k, v in sim.controllers.items()})
    else:
        _print(
            {
                "vehicles": list(sim.vehicles.keys()),
                "controllers": list(sim.controllers.keys()),
            }
        )
    return 0


def cmd_modules(args: argparse.Namespace) -> int:
    sim = PlatformSimulator().load_defaults()
    if args.module_id:
        m = sim.modules.get(args.module_id)
        if not m:
            print(f"module not found: {args.module_id}", file=sys.stderr)
            return 1
        _print(m.to_dict())
    else:
        _print({k: {"kind": v.kind.value, "name": v.name, "safety_class": v.safety_class.value} for k, v in sim.modules.items()})
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = _load_json(path)
    if "module_id" in data:
        obj = HardwareModule.from_dict(data)
    elif "controller_id" in data:
        obj = ControllerProfile.from_dict(data)
    elif "vehicle_id" in data:
        obj = VehicleProfile.from_dict(data)
    elif "package_id" in data:
        obj = ClonePackage.from_dict(data)
    else:
        print("unrecognized manifest shape", file=sys.stderr)
        return 1
    _print(obj.to_dict() if hasattr(obj, "to_dict") else data)
    return 0


def cmd_validate_manifest(args: argparse.Namespace) -> int:
    path = Path(args.path)
    data = _load_json(path)
    try:
        if "module_id" in data:
            HardwareModule.from_dict(data)
        elif "controller_id" in data:
            ControllerProfile.from_dict(data)
        elif "vehicle_id" in data:
            VehicleProfile.from_dict(data)
        elif "package_id" in data:
            pkg = ClonePackage.from_dict(data)
            if args.check_integrity and pkg.package_digest and not pkg.verify_integrity():
                print("integrity check failed", file=sys.stderr)
                return 1
        else:
            print("unrecognized manifest", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"validation failed: {e}", file=sys.stderr)
        return 1
    print("ok")
    return 0


def cmd_capture_report(args: argparse.Namespace) -> int:
    if args.path:
        pkg = ClonePackage.from_dict(_load_json(Path(args.path)))
    else:
        pkg = make_incomplete_example_package()
    _print(
        {
            "package_id": pkg.package_id,
            "package_digest": pkg.package_digest,
            "integrity_ok": pkg.verify_integrity(),
            "completeness": pkg.capture_completeness(),
            "recovery_requirements": pkg.recovery_requirements,
        }
    )
    return 0


def cmd_verify_backup(args: argparse.Namespace) -> int:
    pkg = ClonePackage.from_dict(_load_json(Path(args.path)))
    ok = pkg.verify_integrity()
    _print({"package_id": pkg.package_id, "package_digest": pkg.package_digest, "verified": ok})
    return 0 if ok else 1


def cmd_compatibility(args: argparse.Namespace) -> int:
    sim = PlatformSimulator().load_defaults()
    module_ids = args.modules.split(",") if args.modules else []
    result = sim.evaluate_compatibility(
        vehicle_id=args.vehicle,
        original_id=args.original,
        replacement_id=args.replacement,
        module_ids=module_ids,
        package_id=args.package,
        require_vehicle_qualified=not args.allow_development,
    )
    _print(result.to_dict())
    return 0 if result.status.value == "compatible" else 2


def cmd_simulate_workflow(args: argparse.Namespace) -> int:
    sim = PlatformSimulator().load_defaults()
    kind = WorkflowKind(args.workflow)
    module_ids = args.modules.split(",") if args.modules else []
    run = sim.run_workflow(
        kind,
        vehicle_id=args.vehicle,
        original_id=args.original,
        replacement_id=args.replacement,
        module_ids=module_ids,
        package_id=args.package,
    )
    _print(run.to_dict())
    return 0 if run.final_phase.value == "succeeded" else 2


def cmd_esp32_s3(args: argparse.Namespace) -> int:
    mod = esp32_s3_compute_module()
    _print(mod.to_dict())
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ecugate-platform",
        description="ECUgate modular vehicle-controller platform (software contracts only)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("profiles", help="List example vehicle/controller profiles")
    sp.add_argument("--kind", choices=["vehicle", "controller", "all"], default="all")
    sp.set_defaults(func=cmd_profiles)

    sp = sub.add_parser("modules", help="List or show hardware modules")
    sp.add_argument("--module-id", default=None)
    sp.set_defaults(func=cmd_modules)

    sp = sub.add_parser("inspect", help="Inspect a manifest JSON file")
    sp.add_argument("path")
    sp.set_defaults(func=cmd_inspect)

    sp = sub.add_parser("validate-manifest", help="Validate a manifest JSON file")
    sp.add_argument("path")
    sp.add_argument("--check-integrity", action="store_true")
    sp.set_defaults(func=cmd_validate_manifest)

    sp = sub.add_parser("capture-report", help="Report capture completeness")
    sp.add_argument("--path", default=None, help="Path to clone package JSON (default: example)")
    sp.set_defaults(func=cmd_capture_report)

    sp = sub.add_parser("verify-backup", help="Verify package digest")
    sp.add_argument("path")
    sp.set_defaults(func=cmd_verify_backup)

    sp = sub.add_parser("compatibility", help="Run compatibility evaluation")
    sp.add_argument("--vehicle", default="example-vehicle-v1")
    sp.add_argument("--original", default="example-original-ecu")
    sp.add_argument("--replacement", default="example-replacement-dev")
    sp.add_argument("--modules", default="")
    sp.add_argument("--package", default=None)
    sp.add_argument("--allow-development", action="store_true", help="Do not require vehicle-qualified stack")
    sp.set_defaults(func=cmd_compatibility)

    sp = sub.add_parser("simulate-workflow", help="Simulate a replacement workflow")
    sp.add_argument(
        "workflow",
        choices=[k.value for k in WorkflowKind],
    )
    sp.add_argument("--vehicle", default=None)
    sp.add_argument("--original", default=None)
    sp.add_argument("--replacement", default=None)
    sp.add_argument("--modules", default="")
    sp.add_argument("--package", default=None)
    sp.set_defaults(func=cmd_simulate_workflow)

    sp = sub.add_parser("esp32-s3", help="Show ESP32-S3 development compute profile")
    sp.set_defaults(func=cmd_esp32_s3)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
