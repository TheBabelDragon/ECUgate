# Bench topology and readiness

Schema **v2** inventory models a full bench: multiple interfaces, device roles,
explicit relationships, and structured programming readiness.

## Roles

| Role | Meaning |
|------|---------|
| `host_interface` | Enumerated serial/USB/sim path |
| `programmer` | Programming adapter |
| `power_supply` | Bench supply |
| `target_ecu` | ECU under test |
| `unknown_device` | Unresolved identity |

USB/serial presence **never** proves which ECU is attached to which programmer.

## Relationships

Edges (`connected_via`, `powers`, `programs`, `user_confirmed`) are stored
separately from identity. Operators confirm links that metadata cannot prove:

```python
topo.confirm_relationship(programmer_id, ecu_id, RelationshipType.PROGRAMS, note="...")
```

## Readiness (not authorization)

Requirements evaluated independently:

* Target ECU identity
* Programmer identity + protocol
* Protocol compatibility
* ECU-specific power (not a nominal 13 V default)
* Supply capability vs ECU
* Transient/stability notes
* Recovery procedure
* Write authorization — **always unsatisfied** in discovery

`authorized` is always `false` on inventory and readiness payloads.

## CLI

```bash
# v1 single-focus report (backward compatible)
python -m ecugate.discovery.cli --simulate --manifests manifests/devices

# v2 multi-device inventory
python -m ecugate.discovery.cli --simulate --inventory --manifests manifests/devices

# Save locally
python -m ecugate.discovery.cli --simulate --inventory --save /tmp/bench.json
```

## API

```python
from ecugate.discovery import DiscoveryEngine, DeviceRole

eng = DiscoveryEngine(manifest_dir="manifests/devices")
eng.inject_simulated_interface(...)
inv = eng.discover_inventory()
assert inv.to_dict()["authorized"] is False
for d in inv.devices:
    print(d.role, d.matched_manifest_id, d.unknown_fields)
```
