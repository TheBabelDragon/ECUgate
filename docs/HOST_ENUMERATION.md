# Host hardware enumeration

ECUgate can **opt in** to non-destructive host interface discovery. Simulation remains the default; unit tests and the HorsePowerPoint demo never require physical hardware.

## Capability levels (unchanged)

| Level | Meaning |
|-------|---------|
| detected | An interface path or USB node is present |
| identified | VID/PID or simulated id matched a single manifest |
| described | Protocols/operations known from the matched manifest |
| validated | Constraints (including power) resolved for structural readiness |
| authorized | **Never set by discovery** — execution policy only |

## What is enumerated

* **Serial**: optional `pyserial` (`list_ports`), else Linux `/dev/ttyUSB*`, `/dev/ttyACM*`, and serial-by-id; macOS `/dev/tty.*` / `/dev/cu.*`
* **USB**: optional `pyusb`, else Linux sysfs `/sys/bus/usb/devices/*/idVendor|idProduct`

Descriptors are normalized to `InterfaceRecord` (path, vendor_id, product_id, serial, metadata).

## What is not done

* No ECU writes, flashing, or exclusive programming sessions
* No automatic protocol selection from a “similar” model name
* No assumption that a nominal 13 V supply is safe
* Device identity, programmer capabilities, power-supply limits, and ECU requirements stay separate entities

## Optional dependencies

```bash
python -m ecugate.discovery.cli --deps
```

| Package | Role | Required? |
|---------|------|-----------|
| (stdlib) | Path/sysfs scan on Linux | No |
| pyserial | Richer serial metadata | Optional |
| pyusb | USB descriptor walk | Optional |

## CLI

```bash
# Default: simulated interface only
python -m ecugate.discovery.cli

# Explicit simulation
python -m ecugate.discovery.cli --simulate --manifests manifests/devices

# Opt-in host scan
python -m ecugate.discovery.cli --host --manifests manifests/devices

# Both
python -m ecugate.discovery.cli --simulate-and-host --manifests manifests/devices
```

Output is JSON. The `authorized` field is always `false`.

## Platform limitations

* **Windows** without pyserial: serial enumeration returns empty (no stable COM list in stdlib).
* **macOS** USB without pyusb: USB list is empty; serial path scan still works for many adapters.
* **Permissions**: reading sysfs is usually allowed; opening ports is not performed by discovery.
* Incomplete descriptors leave fields in `unknown_fields` and add programming blockers.

## API

```python
from ecugate.discovery import DiscoveryEngine
from ecugate.discovery.host import HostEnumerator

eng = DiscoveryEngine(manifest_dir="manifests/devices")
eng.set_enumerator(HostEnumerator(serial=True, usb=True))
report = eng.discover()
assert report.to_dict()["authorized"] is False
```
