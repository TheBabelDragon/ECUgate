"""Host serial/USB enumeration (non-destructive, optional deps).

Platform notes
--------------
* Linux: serial ports via /dev and optional pyserial; USB via sysfs.
* macOS: serial via /dev/tty.* and /dev/cu.*; USB limited without pyusb.
* Windows: serial via optional pyserial; USB requires optional pyusb.

No module here opens a programming session or writes to an ECU.
Optional packages (pyserial, pyusb) are never required for import or tests.
"""

from __future__ import annotations

import glob
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ecugate.discovery.pipeline import InterfaceRecord


def _norm_hex_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().lower().replace("0x", "")
    if not s:
        return None
    try:
        return f"{int(s, 16):04x}"
    except ValueError:
        return s


class HostSerialEnumerator:
    """Enumerate serial-like interfaces without exclusive open when possible."""

    def __init__(self, *, include_bluetooth: bool = False) -> None:
        self.include_bluetooth = include_bluetooth

    def enumerate(self) -> List[InterfaceRecord]:
        records = self._enumerate_pyserial()
        if records is not None:
            return records
        return self._enumerate_paths()

    def _enumerate_pyserial(self) -> Optional[List[InterfaceRecord]]:
        try:
            from serial.tools import list_ports  # type: ignore
        except ImportError:
            return None
        out: List[InterfaceRecord] = []
        try:
            ports = list(list_ports.comports())
        except Exception:
            return []
        for p in ports:
            path = getattr(p, "device", None) or ""
            if not path:
                continue
            if not self.include_bluetooth and self._looks_bluetooth(path, p):
                continue
            vid = None
            if hasattr(p, "vid") and p.vid is not None:
                vid = f"{int(p.vid):04x}"
            pid = None
            if hasattr(p, "pid") and p.pid is not None:
                pid = f"{int(p.pid):04x}"
            serial = getattr(p, "serial_number", None) or None
            meta: Dict[str, Any] = {
                "enumerator": "pyserial",
                "description": getattr(p, "description", None),
                "manufacturer": getattr(p, "manufacturer", None),
                "product": getattr(p, "product", None),
                "hwid": getattr(p, "hwid", None),
                "location": getattr(p, "location", None),
            }
            meta = {k: v for k, v in meta.items() if v is not None}
            out.append(
                InterfaceRecord(
                    interface_id=f"serial:{path}",
                    interface_type="serial",
                    path=path,
                    vendor_id=vid,
                    product_id=pid,
                    serial=serial,
                    metadata=meta,
                )
            )
        return out

    def _enumerate_paths(self) -> List[InterfaceRecord]:
        system = platform.system()
        paths: List[str] = []
        if system == "Linux":
            for pat in ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyS*", "/dev/serial/by-id/*"):
                paths.extend(glob.glob(pat))
        elif system == "Darwin":
            paths.extend(glob.glob("/dev/tty.*"))
            paths.extend(glob.glob("/dev/cu.*"))
        elif system == "Windows":
            return []
        else:
            return []

        out: List[InterfaceRecord] = []
        seen: set[str] = set()
        for path in sorted(set(paths)):
            if not os.path.exists(path):
                continue
            real = os.path.realpath(path)
            if real in seen and path != real:
                continue
            seen.add(real)
            if not self.include_bluetooth and self._looks_bluetooth(path, None):
                continue
            meta: Dict[str, Any] = {"enumerator": "path_scan", "platform": system, "realpath": real}
            vid, pid = self._linux_usb_ids_for_tty(path) if system == "Linux" else (None, None)
            out.append(
                InterfaceRecord(
                    interface_id=f"serial:{path}",
                    interface_type="serial",
                    path=path,
                    vendor_id=vid,
                    product_id=pid,
                    serial=None,
                    metadata=meta,
                )
            )
        return out

    @staticmethod
    def _looks_bluetooth(path: str, port_obj: Any) -> bool:
        low = path.lower()
        if "bluetooth" in low or "rfcomm" in low:
            return True
        if port_obj is not None:
            desc = (getattr(port_obj, "description", None) or "").lower()
            if "bluetooth" in desc:
                return True
        return False

    @staticmethod
    def _linux_usb_ids_for_tty(path: str) -> tuple[Optional[str], Optional[str]]:
        try:
            real = Path(path).resolve()
            name = real.name
            sys_tty = Path("/sys/class/tty") / name / "device"
            if not sys_tty.exists():
                return None, None
            cur = sys_tty.resolve()
            for _ in range(8):
                vend = cur / "idVendor"
                prod = cur / "idProduct"
                if vend.is_file() and prod.is_file():
                    return _norm_hex_id(vend.read_text().strip()), _norm_hex_id(prod.read_text().strip())
                parent = cur.parent
                if parent == cur:
                    break
                cur = parent
        except OSError:
            return None, None
        return None, None


class HostUSBEnumerator:
    """Enumerate USB device descriptors (read-only metadata)."""

    def enumerate(self) -> List[InterfaceRecord]:
        records = self._enumerate_pyusb()
        if records is not None:
            return records
        if platform.system() == "Linux":
            return self._enumerate_sysfs()
        return []

    def _enumerate_pyusb(self) -> Optional[List[InterfaceRecord]]:
        try:
            import usb.core  # type: ignore
        except ImportError:
            return None
        out: List[InterfaceRecord] = []
        try:
            devices = list(usb.core.find(find_all=True))  # type: ignore
        except Exception:
            return []
        for i, dev in enumerate(devices):
            try:
                vid = f"{int(dev.idVendor):04x}"
                pid = f"{int(dev.idProduct):04x}"
            except Exception:
                continue
            serial = None
            try:
                if dev.iSerialNumber:
                    import usb.util  # type: ignore

                    serial = usb.util.get_string(dev, dev.iSerialNumber)
            except Exception:
                serial = None
            bus = getattr(dev, "bus", None)
            addr = getattr(dev, "address", None)
            out.append(
                InterfaceRecord(
                    interface_id=f"usb:{vid}:{pid}:{bus}:{addr}:{i}",
                    interface_type="usb",
                    path=None,
                    vendor_id=vid,
                    product_id=pid,
                    serial=serial,
                    metadata={"enumerator": "pyusb", "bus": bus, "address": addr},
                )
            )
        return out

    def _enumerate_sysfs(self) -> List[InterfaceRecord]:
        out: List[InterfaceRecord] = []
        root = Path("/sys/bus/usb/devices")
        if not root.is_dir():
            return out
        for entry in sorted(root.iterdir()):
            vend_f = entry / "idVendor"
            prod_f = entry / "idProduct"
            if not vend_f.is_file() or not prod_f.is_file():
                continue
            try:
                vid = _norm_hex_id(vend_f.read_text().strip())
                pid = _norm_hex_id(prod_f.read_text().strip())
            except OSError:
                continue
            if not vid or not pid:
                continue
            serial = None
            serial_f = entry / "serial"
            if serial_f.is_file():
                try:
                    serial = serial_f.read_text().strip() or None
                except OSError:
                    serial = None
            manufacturer = product = None
            for attr, target in (("manufacturer", "manufacturer"), ("product", "product")):
                f = entry / attr
                if f.is_file():
                    try:
                        val = f.read_text().strip()
                        if attr == "manufacturer":
                            manufacturer = val
                        else:
                            product = val
                    except OSError:
                        pass
            out.append(
                InterfaceRecord(
                    interface_id=f"usb:sysfs:{entry.name}:{vid}:{pid}",
                    interface_type="usb",
                    path=str(entry),
                    vendor_id=vid,
                    product_id=pid,
                    serial=serial,
                    metadata={
                        "enumerator": "sysfs",
                        "sysfs_name": entry.name,
                        "manufacturer": manufacturer,
                        "product": product,
                    },
                )
            )
        return out


class HostEnumerator:
    """Combined host serial + USB enumerator (opt-in for real hardware)."""

    def __init__(self, *, serial: bool = True, usb: bool = True, include_bluetooth: bool = False) -> None:
        self._serial = HostSerialEnumerator(include_bluetooth=include_bluetooth) if serial else None
        self._usb = HostUSBEnumerator() if usb else None

    def enumerate(self) -> List[InterfaceRecord]:
        out: List[InterfaceRecord] = []
        seen: set[str] = set()
        for src in (self._serial, self._usb):
            if src is None:
                continue
            for iface in src.enumerate():
                if iface.interface_id in seen:
                    continue
                seen.add(iface.interface_id)
                out.append(iface)
        return out


def optional_dependency_status() -> Dict[str, Any]:
    """Report which optional host libraries are available."""
    status: Dict[str, Any] = {
        "platform": platform.system(),
        "python": sys.version.split()[0],
        "pyserial": False,
        "pyusb": False,
    }
    try:
        import serial  # noqa: F401

        status["pyserial"] = True
    except ImportError:
        pass
    try:
        import usb.core  # noqa: F401

        status["pyusb"] = True
    except ImportError:
        pass
    return status
