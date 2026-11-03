# Compatibility Engine

Deterministic, fail-closed evaluation of vehicle, original/replacement controllers, modules, backup completeness, electrical/timing, safety and recovery requirements.

Results: `compatible` | `incompatible` | `incomplete` | `unknown`.

Unknown critical requirements fail closed. No inference from product names, processor families or connector shapes alone.

Stable blocker codes integrate with preflight conventions (e.g. `development_hardware_not_vehicle_qualified`, `backup_incomplete`, `can_fd_controller_missing`, `safety_supervisor_missing`).
