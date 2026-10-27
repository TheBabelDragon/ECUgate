# Adapters

ECUgate talks to devices through adapters.

## Simulator (v0.1)

`examples/horsepowerpoint/simulator.py` — deterministic in-process ECU.

## Discovery manifests

`manifests/devices/*.json` describe device families. Discovery matches VID/PID or simulated id. Manifest capabilities are not proof a connected device supports them.

## Future

Physical adapters must enforce device limits, route state changes through ExecutionEngine authorization, and never grant privileges via tool output.
