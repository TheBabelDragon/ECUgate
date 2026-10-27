"""CLI for preflight validation and simulator-only execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Optional

from ecugate.preflight.authorization import AuthorizationStore
from ecugate.preflight.engine import PreflightEngine
from ecugate.preflight.models import ExecutionMode, OperationProposal
from ecugate.preflight.registry import CapabilityRegistry
from ecugate.preflight.simulator import SimulatorExecutor


def _print(obj: Any, compact: bool = False) -> None:
    if compact:
        print(json.dumps(obj, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(obj, indent=2, sort_keys=True))


def _load_proposal(path: str) -> OperationProposal:
    data = json.loads(Path(path).read_text())
    return OperationProposal.from_dict(data)


def cmd_preflight(args: argparse.Namespace) -> int:
    proposal = _load_proposal(args.proposal)
    if args.physical:
        proposal.execution_mode = ExecutionMode.PHYSICAL
    engine = PreflightEngine()
    grant = None
    store = AuthorizationStore()
    if args.with_grant:
        try:
            grant = store.issue(proposal, issuer="cli_demo", ttl_seconds=600)
        except ValueError as e:
            _print({"error": str(e), "authorized": False}, args.compact)
            return 1
    result = engine.evaluate(proposal, grant=grant)
    payload = result.to_dict()
    if grant:
        payload["grant_id"] = grant.grant_id
    _print(payload, args.compact)
    return 0 if result.decision.value == "ready" else 1


def cmd_capabilities(args: argparse.Namespace) -> int:
    reg = CapabilityRegistry()
    ops = [o.to_dict() for o in reg.list_operations()]
    _print({"operations": ops, "policy_note": "preflight readiness is not authorization"}, args.compact)
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    proposal = _load_proposal(args.proposal)
    if args.physical:
        proposal.execution_mode = ExecutionMode.PHYSICAL
    store = AuthorizationStore()
    executor = SimulatorExecutor(auth_store=store)
    grant = None
    if args.with_grant:
        try:
            grant = store.issue(proposal)
        except ValueError as e:
            _print({"error": str(e)}, args.compact)
            return 1
    receipt = executor.execute(proposal, grant=grant, scenario=args.scenario)
    _print(receipt.to_dict(), args.compact)
    return 0 if receipt.outcome.value == "succeeded" else 1


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="ecugate-preflight", description="Write preflight & simulator policy")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("preflight", help="Validate proposal without executing")
    p.add_argument("--proposal", required=True)
    p.add_argument("--with-grant", action="store_true")
    p.add_argument("--physical", action="store_true")
    p.add_argument("--compact", action="store_true")
    p.set_defaults(func=cmd_preflight)

    c = sub.add_parser("capabilities", help="List registered operations")
    c.add_argument("--compact", action="store_true")
    c.set_defaults(func=cmd_capabilities)

    s = sub.add_parser("simulate-operation", help="Simulator-only execution")
    s.add_argument("--proposal", required=True)
    s.add_argument("--scenario", default="success", choices=["success", "failed", "timeout", "interrupted", "disconnect"])
    s.add_argument("--with-grant", action="store_true")
    s.add_argument("--physical", action="store_true")
    s.add_argument("--compact", action="store_true")
    s.set_defaults(func=cmd_simulate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
