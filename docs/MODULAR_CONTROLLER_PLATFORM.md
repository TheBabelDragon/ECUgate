# Modular Controller Platform

ECUgate platform package (`ecugate.platform`) defines the software architecture and contracts for a **universal modular vehicle-controller replacement ecosystem**.

This increment is **architecture and contracts only**. It does **not** implement physical engine control, actuator operation, ECU flashing, or vehicle writes.

## Goals

- Identify an existing vehicle controller and preserve recoverable configuration.
- Describe electrical and communication requirements.
- Evaluate replacement hardware (including modular boards).
- Support eventual migration to a compatible replacement controller.
- Keep discovery, authorization, auditing and recovery under ECUgate policy.

## Package layout

```
src/ecugate/platform/
  models.py          # Vehicle, controller, hardware module profiles
  backup.py          # Versioned clone packages + capture completeness
  compatibility.py   # Fail-closed compatibility engine
  workflows.py       # IDENTIFY … RECOVER workflow contracts
  simulator.py       # Hardware-independent simulation + HIL contract
  cli.py             # ecugate-platform CLI
```

## Profile types

| Type | Role |
|------|------|
| **VehicleProfile** | Vehicle identity, year, engine/transmission, network and sensor/actuator topology, original controller reference |
| **ControllerProfile** | Manufacturer/model, processor, firmware/bootloader ids, protocols, electrical/timing, safety class, restrictions |
| **HardwareModule** | Independently replaceable board: compute, power, acquisition, drivers, communications, storage, safety supervision |

Every asserted specification carries **evidence** and a **verification** status. Unknown electrical limits and pin maps stay **explicitly unknown**. Pin assignments are never invented.

## Safety classes

- `development` — lab / prototype (e.g. ESP32-S3 dev board)
- `supervisory` — monitoring or non-ASIL helper roles
- `automotive_qualified` — requires evidence of qualification (not claimed by examples)
- `unknown`

## Policy boundary (unchanged)

- Discovery never grants authorization.
- Preflight readiness never grants authorization.
- Simulator execution stays separate from physical execution.
- Physical state-changing operations remain **hard-denied**.
- `authorized_write` remains false.
- No raw arbitrary CAN, UDS programming, flashing or actuator control is added in this increment.

## Related docs

- [CONTROLLER_CLONING.md](CONTROLLER_CLONING.md)
- [COMPATIBILITY_ENGINE.md](COMPATIBILITY_ENGINE.md)
- [ESP32_HARDWARE_STRATEGY.md](ESP32_HARDWARE_STRATEGY.md)
- [REPLACEMENT_AND_RECOVERY.md](REPLACEMENT_AND_RECOVERY.md)
