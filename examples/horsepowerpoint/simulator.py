"""Deterministic simulated ECU. No real hardware. Enforces its own limits."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


LIMITS = {
    "spark_advance_deg": (0.0, 40.0),
    "fuel_trim_pct": (-20.0, 20.0),
    "boost_target_psi": (0.0, 25.0),
    "idle_rpm": (600, 1200),
}

DEFAULT_STATE = {
    "spark_advance_deg": 15.0,
    "fuel_trim_pct": 0.0,
    "boost_target_psi": 8.0,
    "idle_rpm": 800,
    "engine_temp_c": 90.0,
    "rpm": 2000,
    "load_pct": 40.0,
    "fault_codes": [],
}


@dataclass
class SimulatedECU:
    vehicle_id: str = "vehicle:sim-1"
    state: Dict[str, Any] = field(default_factory=lambda: deepcopy(DEFAULT_STATE))
    history: List[Dict[str, Any]] = field(default_factory=list)
    _fault_mode: Optional[str] = None

    def read_state(self) -> Dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id,
            "parameters": {
                k: self.state[k]
                for k in ("spark_advance_deg", "fuel_trim_pct", "boost_target_psi", "idle_rpm")
            },
            "telemetry": {
                k: self.state[k]
                for k in ("engine_temp_c", "rpm", "load_pct", "fault_codes")
            },
            "limits": {k: list(v) for k, v in LIMITS.items()},
        }

    def apply_parameter(
        self, name: str, value: float, *, dry_run: bool = False
    ) -> Dict[str, Any]:
        if name not in LIMITS:
            raise ValueError(f"unknown parameter: {name}")
        lo, hi = LIMITS[name]
        if value < lo or value > hi:
            raise ValueError(
                f"parameter {name}={value} outside hard limits [{lo}, {hi}]"
            )
        before = self.state[name]
        if dry_run:
            return {
                "dry_run": True,
                "parameter": name,
                "before": before,
                "would_be": value,
                "accepted": True,
            }
        self.state[name] = float(value)
        self._apply_physics(name, before, float(value))
        entry = {
            "parameter": name,
            "before": before,
            "after": self.state[name],
            "telemetry_after": {
                "engine_temp_c": self.state["engine_temp_c"],
                "rpm": self.state["rpm"],
                "load_pct": self.state["load_pct"],
            },
        }
        self.history.append(entry)
        return {
            "dry_run": False,
            "parameter": name,
            "before": before,
            "after": self.state[name],
            "telemetry": {
                "engine_temp_c": self.state["engine_temp_c"],
                "rpm": self.state["rpm"],
                "load_pct": self.state["load_pct"],
                "fault_codes": list(self.state["fault_codes"]),
            },
            "accepted": True,
        }

    def _apply_physics(self, name: str, before: float, after: float) -> None:
        delta = after - before
        if name == "spark_advance_deg":
            self.state["rpm"] = max(600, min(7000, self.state["rpm"] + delta * 15))
            self.state["engine_temp_c"] = max(70.0, self.state["engine_temp_c"] - delta * 0.2)
        elif name == "fuel_trim_pct":
            self.state["engine_temp_c"] = max(70.0, self.state["engine_temp_c"] + delta * 0.3)
        elif name == "boost_target_psi":
            self.state["load_pct"] = max(0.0, min(100.0, self.state["load_pct"] + delta * 2))
            self.state["engine_temp_c"] = max(70.0, self.state["engine_temp_c"] + delta * 0.5)
        elif name == "idle_rpm":
            if self.state["rpm"] < 1500:
                self.state["rpm"] = after

        if self._fault_mode == "overheat" or self.state["engine_temp_c"] > 110:
            if "P0217" not in self.state["fault_codes"]:
                self.state["fault_codes"].append("P0217")

    def inject_fault(self, code: str) -> None:
        if code not in self.state["fault_codes"]:
            self.state["fault_codes"].append(code)

    def clear_faults(self) -> None:
        self.state["fault_codes"] = []

    def reset(self) -> None:
        self.state = deepcopy(DEFAULT_STATE)
        self.history.clear()
        self._fault_mode = None
