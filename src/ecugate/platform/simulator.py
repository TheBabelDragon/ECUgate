"""Hardware-independent simulation boundary and HIL adapter contract.

Physical hardware is not required for tests. Future HIL adapters implement
the same observation / fault injection surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from ecugate.platform.backup import ClonePackage, make_incomplete_example_package
from ecugate.platform.compatibility import CompatibilityEngine
from ecugate.platform.models import (
    Confidence,
    ControllerProfile,
    ElectricalSpec,
    EvidenceRef,
    HardwareModule,
    InterfaceSpec,
    ModuleKind,
    SafetyClass,
    VehicleProfile,
    VerificationStatus,
    esp32_s3_compute_module,
    utc_now_iso,
)
from ecugate.platform.workflows import WorkflowContext, WorkflowEngine, WorkflowKind, WorkflowRun


class HILAdapter(Protocol):
    """Future hardware-in-the-loop adapter contract."""

    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def read_observation(self, channel: str) -> Dict[str, Any]: ...
    def inject_fault(self, fault_id: str, params: Dict[str, Any]) -> None: ...
    def clear_faults(self) -> None: ...


@dataclass
class SimulatedFault:
    fault_id: str
    description: str
    active: bool = False
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformSimulator:
    """In-process simulator for profiles, modules, captures and workflows."""

    vehicles: Dict[str, VehicleProfile] = field(default_factory=dict)
    controllers: Dict[str, ControllerProfile] = field(default_factory=dict)
    modules: Dict[str, HardwareModule] = field(default_factory=dict)
    packages: Dict[str, ClonePackage] = field(default_factory=dict)
    faults: Dict[str, SimulatedFault] = field(default_factory=dict)
    _compat: CompatibilityEngine = field(default_factory=CompatibilityEngine)
    _workflows: WorkflowEngine = field(default_factory=WorkflowEngine)

    def load_defaults(self) -> "PlatformSimulator":
        """Load illustrative example fixtures (clearly marked)."""
        now = utc_now_iso()
        evid = EvidenceRef(
            source="platform.simulator",
            timestamp=now,
            provenance="illustrative",
            verification_method="constructed",
            confidence=Confidence.ILLUSTRATIVE,
            detail="Example fixture only.",
        )

        self.modules["esp32-s3-dev-compute-v1"] = esp32_s3_compute_module()

        self.modules["ext-canfd-controller-v1"] = HardwareModule(
            module_id="ext-canfd-controller-v1",
            kind=ModuleKind.COMMUNICATIONS,
            name="External CAN FD Controller (illustrative)",
            hardware_revision="illust-1",
            interfaces=[
                InterfaceSpec(
                    name="can_fd",
                    protocol="can_fd",
                    external_hardware_required=False,
                    notes="Illustrative external CAN FD controller module.",
                    verification=VerificationStatus.ILLUSTRATIVE,
                )
            ],
            capabilities=["can_fd", "classical_can"],
            safety_class=SafetyClass.SUPERVISORY,
            evidence=[evid],
            verification=VerificationStatus.ILLUSTRATIVE,
            notes="Illustrative. Not a verified commercial part.",
        )

        self.modules["auto-power-protection-v1"] = HardwareModule(
            module_id="auto-power-protection-v1",
            kind=ModuleKind.POWER_PROTECTION,
            name="Protected Automotive Power Module (illustrative)",
            electrical=ElectricalSpec(
                voltage_nominal_v=12.0,
                voltage_min_v=9.0,
                voltage_max_v=16.0,
                protection=["reverse_polarity", "overvoltage", "load_dump_illustrative"],
                verification=VerificationStatus.ILLUSTRATIVE,
            ),
            capabilities=["regulated_5v", "regulated_3v3", "power_supervision"],
            safety_class=SafetyClass.SUPERVISORY,
            evidence=[evid],
            verification=VerificationStatus.ILLUSTRATIVE,
            notes="Illustrative power module. Not a verified automotive design.",
        )

        self.modules["sensor-acq-v1"] = HardwareModule(
            module_id="sensor-acq-v1",
            kind=ModuleKind.ANALOG_ACQUISITION,
            name="Sensor Acquisition Module (illustrative)",
            capabilities=["analog_input", "filtered_adc"],
            safety_class=SafetyClass.SUPERVISORY,
            evidence=[evid],
            verification=VerificationStatus.ILLUSTRATIVE,
            notes="Illustrative.",
        )

        self.modules["safety-supervisor-v1"] = HardwareModule(
            module_id="safety-supervisor-v1",
            kind=ModuleKind.SAFETY_SUPERVISION,
            name="Independent Safety Supervisor (illustrative)",
            capabilities=["independent_watchdog", "output_disable", "fault_latch"],
            required_safety_properties=["independent_watchdog", "safe_state"],
            safety_class=SafetyClass.SUPERVISORY,
            evidence=[evid],
            verification=VerificationStatus.ILLUSTRATIVE,
            notes="Illustrative independent supervisor. Not ASIL-rated evidence.",
        )

        self.controllers["example-original-ecu"] = ControllerProfile(
            controller_id="example-original-ecu",
            manufacturer="illustrative",
            model="example-ecu",
            processor_architecture="unknown",
            protocols=["classical_can", "uds"],
            interfaces=[
                InterfaceSpec(
                    name="can0",
                    protocol="classical_can",
                    verification=VerificationStatus.ILLUSTRATIVE,
                )
            ],
            electrical=ElectricalSpec(
                voltage_nominal_v=12.0, verification=VerificationStatus.ILLUSTRATIVE
            ),
            safety_class=SafetyClass.UNKNOWN,
            evidence=[evid],
            verification=VerificationStatus.ILLUSTRATIVE,
            notes="Illustrative original controller profile.",
        )

        self.controllers["example-replacement-dev"] = ControllerProfile(
            controller_id="example-replacement-dev",
            manufacturer="illustrative",
            model="esp32-s3-modular-stack",
            processor_architecture="xtensa",
            processor_variant="esp32-s3",
            protocols=["classical_can"],
            interfaces=[
                InterfaceSpec(
                    name="twai",
                    protocol="classical_can",
                    external_hardware_required=True,
                    verification=VerificationStatus.ILLUSTRATIVE,
                )
            ],
            electrical=ElectricalSpec(
                voltage_nominal_v=3.3, verification=VerificationStatus.ILLUSTRATIVE
            ),
            safety_class=SafetyClass.DEVELOPMENT,
            known_restrictions=["development_only", "not_vehicle_qualified"],
            evidence=[evid],
            verification=VerificationStatus.ILLUSTRATIVE,
            notes="Illustrative replacement based on ESP32-S3 development compute.",
        )

        self.vehicles["example-vehicle-v1"] = VehicleProfile(
            vehicle_id="example-vehicle-v1",
            make="illustrative",
            model="example",
            model_year=2010,
            engine_family="illustrative",
            original_controller_id="example-original-ecu",
            network_interfaces=[
                InterfaceSpec(
                    name="powertrain_can",
                    protocol="classical_can",
                    verification=VerificationStatus.ILLUSTRATIVE,
                )
            ],
            sensor_topology=["crank", "cam", "map", "tps"],
            actuator_topology=["injectors", "coils", "idle"],
            evidence=[evid],
            verification=VerificationStatus.ILLUSTRATIVE,
            notes="Illustrative vehicle profile only.",
        )

        incomplete = make_incomplete_example_package()
        self.packages[incomplete.package_id] = incomplete

        for fid, desc in [
            ("missing_sensor", "Required sensor channel absent"),
            ("electrical_out_of_range", "Supply voltage outside declared range"),
            ("unsupported_controller_revision", "Controller hardware revision not in matrix"),
            ("incompatible_processor", "Replacement processor target unsupported"),
            ("missing_can_fd", "CAN FD required but external controller absent"),
            ("missing_safety_supervisor", "Independent safety supervisor absent"),
            ("incomplete_backup", "Capture package incomplete"),
            ("corrupted_backup_digest", "Package digest mismatch"),
            ("incompatible_calibration_schema", "Calibration schema not migratable"),
            ("missing_recovery", "Recovery procedure not declared"),
            ("module_disconnect", "Replacement module reported disconnected"),
            ("power_mismatch", "Power module requirements not met"),
        ]:
            self.faults[fid] = SimulatedFault(fault_id=fid, description=desc)

        return self

    def inject_fault(self, fault_id: str, **params: Any) -> None:
        if fault_id not in self.faults:
            self.faults[fault_id] = SimulatedFault(fault_id=fault_id, description=fault_id)
        self.faults[fault_id].active = True
        self.faults[fault_id].params.update(params)

    def clear_faults(self) -> None:
        for f in self.faults.values():
            f.active = False
            f.params.clear()

    def active_faults(self) -> List[str]:
        return [f.fault_id for f in self.faults.values() if f.active]

    def evaluate_compatibility(
        self,
        vehicle_id: Optional[str] = None,
        original_id: Optional[str] = None,
        replacement_id: Optional[str] = None,
        module_ids: Optional[List[str]] = None,
        package_id: Optional[str] = None,
        require_vehicle_qualified: bool = True,
    ):
        modules = [self.modules[m] for m in (module_ids or []) if m in self.modules]
        return self._compat.evaluate(
            vehicle=self.vehicles.get(vehicle_id) if vehicle_id else None,
            original=self.controllers.get(original_id) if original_id else None,
            replacement=self.controllers.get(replacement_id) if replacement_id else None,
            modules=modules,
            backup=self.packages.get(package_id) if package_id else None,
            require_vehicle_qualified=require_vehicle_qualified,
        )

    def run_workflow(
        self,
        kind: WorkflowKind,
        *,
        vehicle_id: Optional[str] = None,
        original_id: Optional[str] = None,
        replacement_id: Optional[str] = None,
        module_ids: Optional[List[str]] = None,
        package_id: Optional[str] = None,
    ) -> WorkflowRun:
        ctx = WorkflowContext(
            vehicle=self.vehicles.get(vehicle_id) if vehicle_id else None,
            original=self.controllers.get(original_id) if original_id else None,
            replacement=self.controllers.get(replacement_id) if replacement_id else None,
            modules=[self.modules[m] for m in (module_ids or []) if m in self.modules],
            source_capture=self.packages.get(package_id) if package_id else None,
        )
        return self._workflows.run(kind, ctx)
