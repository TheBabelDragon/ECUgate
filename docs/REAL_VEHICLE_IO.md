# Real vehicle I/O (read-only)

ECUgate’s `vehicle_io` package provides **opt-in**, **read-only** OBD-II access
through ELM327-compatible serial adapters.

## Verified in this repository

| Item | Status |
|------|--------|
| Unit tests with `FakeSerialTransport` | **Passed** |
| ELM327 ATI / init sequence (mocked) | **Passed** |
| Mode 01 PID decode (RPM, speed, coolant, load, support) | **Passed** |
| Mode 03 DTC decode | **Passed** |
| Mode 04 / UDS / arbitrary command rejection | **Passed** |
| Physical vehicle + real adapter | **Not tested in CI** |

Do not treat mocked tests as vehicle validation.

## Scope

**Supported adapter class (software profile):** ELM327-compatible AT command set
over serial (typical 38400 baud). USB serial devices are **not** assumed to be
OBD adapters until ATI/init succeeds.

**Supported requests:** Mode 01 PIDs 00/04/05/0C/0D; Mode 03 DTCs; Mode 09 VIN (best-effort).

**Not implemented (rejected by policy):** Mode 04 clear, actuator/control, UDS programming,
flashing, coding, arbitrary CAN frames, generic raw agent tools.

## Procedure

```bash
python -m ecugate.vehicle_io.cli discover --host --json
python -m ecugate.vehicle_io.cli adapter-info --device /dev/ttyUSB0 --json
python -m ecugate.vehicle_io.cli diagnostics --device /dev/ttyUSB0 --read-only --json
python -m ecugate.vehicle_io.cli read-pids --device /dev/ttyUSB0 --pids rpm,speed,coolant --json
python -m ecugate.vehicle_io.cli read-dtcs --device /dev/ttyUSB0 --json

# Simulation (no hardware)
python -m ecugate.vehicle_io.cli adapter-info --simulate --json
```

`authorized_write` is always false. VIN/DTC logs may be sensitive — redact before sharing.
