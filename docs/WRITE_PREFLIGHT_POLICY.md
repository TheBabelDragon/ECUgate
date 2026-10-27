# Write preflight & policy engine

This package determines whether a **proposed** ECU operation meets required
conditions. **Preflight readiness is not authorization.** Authorization is a
separate, explicit step and is never inferred from discovery, memory, or model
confidence.

## What this increment does

* Typed proposals, evidence, grants, and execution receipts
* Deterministic blocker codes
* Simulator-only execution with fault injection
* Single-use, digest-bound authorization grants
* Hard denial of physical state-changing operations

## What this increment does **not** do

* Write to a real vehicle or ECU
* Issue trusted cryptographic operator certificates
* Auto-create grants when preflight passes
* Expose raw CAN / UDS programming / flashing on hardware

## CLI

```bash
python -m ecugate.preflight.cli capabilities
python -m ecugate.preflight.cli preflight --proposal examples/preflight/write_param_proposal.json --with-grant
python -m ecugate.preflight.cli simulate-operation --proposal examples/preflight/write_param_proposal.json --with-grant --scenario success
python -m ecugate.preflight.cli simulate-operation --proposal examples/preflight/write_param_proposal.json --physical --with-grant
```

Physical mode for state-changing ops returns `physical_write_not_implemented`.

## Future physical executor requirements

Trusted issuer, vehicle-specific power limits, recovery procedures, HIL evidence,
and a separate security review of the physical boundary.
