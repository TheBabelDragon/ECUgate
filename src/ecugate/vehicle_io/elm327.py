"""ELM327-compatible initialization and command helpers."""

from __future__ import annotations

from typing import List, Optional, Tuple

from ecugate.vehicle_io.models import AdapterIdentity
from ecugate.vehicle_io.transport import SerialTransport, TransportError


class ELM327Error(Exception):
    pass


def _cmd(transport: SerialTransport, command: str, timeout: float = 2.0) -> str:
    payload = (command.strip() + "\r").encode("ascii", errors="ignore")
    transport.write(payload)
    raw = transport.read_until(b">", timeout=timeout)
    return raw.decode("ascii", errors="replace")


def identify_adapter(transport: SerialTransport, device_path: str, *, timeout: float = 2.0) -> AdapterIdentity:
    raws: List[str] = []
    evidence = []
    try:
        r = _cmd(transport, "ATI", timeout=timeout)
        raws.append(r)
        evidence.append({"cmd": "ATI", "response": r.strip()})
    except TransportError as e:
        return AdapterIdentity(
            device_path=device_path,
            firmware=None,
            evidence=[{"error": str(e)}],
            raw_responses=raws,
        )

    text = r.upper()
    firmware = None
    for line in r.replace("\r", "\n").split("\n"):
        s = line.strip()
        if "ELM" in s.upper():
            firmware = s
            break
    if firmware is None and "ELM" in text:
        firmware = r.strip().split(">")[0].strip()

    adapter_class = "elm327_compatible" if firmware and "ELM" in firmware.upper() else "unknown_serial"
    if "?" in text and not firmware:
        adapter_class = "unknown_serial"

    return AdapterIdentity(
        device_path=device_path,
        adapter_class=adapter_class,
        firmware=firmware,
        raw_responses=raws,
        evidence=evidence,
    )


def initialize_elm(transport: SerialTransport, *, timeout: float = 2.0) -> Tuple[List[str], Optional[str]]:
    seq = ["ATZ", "ATE0", "ATL0", "ATS0", "ATH0", "ATSP0"]
    raws: List[str] = []
    for c in seq:
        try:
            raws.append(_cmd(transport, c, timeout=timeout if c != "ATZ" else max(timeout, 3.0)))
        except TransportError as e:
            raise ELM327Error(f"init failed at {c}: {e}") from e

    protocol = None
    try:
        dpn = _cmd(transport, "ATDPN", timeout=timeout)
        raws.append(dpn)
        for ch in dpn:
            if ch.isalnum() and ch.upper() not in "ATDPN>\r\n ":
                protocol = ch
                break
    except TransportError:
        pass
    return raws, protocol


def send_obd(transport: SerialTransport, mode: str, pid: str = "", *, timeout: float = 3.0) -> str:
    m = mode.lower().replace("0x", "").zfill(2)
    if pid:
        p = pid.lower().replace("0x", "").zfill(2)
        cmd = f"{m}{p}"
    else:
        cmd = m
    return _cmd(transport, cmd, timeout=timeout)
