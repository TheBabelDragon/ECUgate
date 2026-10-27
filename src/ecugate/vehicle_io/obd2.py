"""SAE J1979 Mode 01/03/09 decoding for allowlisted PIDs only."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from ecugate.vehicle_io.models import DiagnosticOutcome


def _hex_bytes(payload: str) -> List[int]:
    clean = re.sub(r"[^0-9A-Fa-f]", "", payload)
    if len(clean) % 2:
        raise ValueError("odd-length hex payload")
    return [int(clean[i : i + 2], 16) for i in range(0, len(clean), 2)]


def strip_elm_noise(text: str) -> str:
    lines = []
    for line in text.replace("\r", "\n").split("\n"):
        s = line.strip()
        if not s or s == ">":
            continue
        up = s.upper()
        if up in ("SEARCHING...", "OK", "STOPPED") or up.startswith("SEARCHING"):
            continue
        lines.append(s)
    return " ".join(lines)


def parse_mode01_response(raw: str, pid: str) -> Tuple[DiagnosticOutcome, Any, Optional[str], Dict[str, Any]]:
    body = strip_elm_noise(raw)
    up = body.upper()
    if "NO DATA" in up:
        return DiagnosticOutcome.UNAVAILABLE, None, None, {"reason": "NO DATA", "raw": body}
    if "UNABLE TO CONNECT" in up or ("BUS INIT" in up and "ERROR" in up):
        return DiagnosticOutcome.FAILED, None, None, {"reason": "bus/error", "raw": body}
    if "?" in up and len(up) < 4:
        return DiagnosticOutcome.MALFORMED, None, None, {"reason": "adapter query error", "raw": body}

    pid_n = pid.lower().replace("0x", "").zfill(2)
    try:
        data = _hex_bytes(body)
    except ValueError:
        return DiagnosticOutcome.MALFORMED, None, None, {"reason": "non-hex payload", "raw": body}

    if len(data) < 3:
        return DiagnosticOutcome.MALFORMED, None, None, {"reason": "truncated", "raw": body}

    try:
        i = data.index(0x41)
    except ValueError:
        return DiagnosticOutcome.MALFORMED, None, None, {"reason": "no positive response 0x41", "raw": body, "bytes": data}

    if i + 1 >= len(data):
        return DiagnosticOutcome.MALFORMED, None, None, {"reason": "truncated after 41", "raw": body}

    resp_pid = f"{data[i + 1]:02x}"
    if resp_pid != pid_n:
        return DiagnosticOutcome.AMBIGUOUS, None, None, {"reason": f"PID mismatch expected {pid_n} got {resp_pid}", "raw": body}

    payload = data[i + 2 :]
    meta: Dict[str, Any] = {"service": "01", "pid": pid_n, "payload_bytes": payload, "formula": None}

    if pid_n == "00":
        if len(payload) < 4:
            return DiagnosticOutcome.MALFORMED, None, None, {**meta, "reason": "short support mask"}
        mask = (payload[0] << 24) | (payload[1] << 16) | (payload[2] << 8) | payload[3]
        supported = []
        for bit in range(32):
            if mask & (1 << (31 - bit)):
                supported.append(f"{bit + 1:02x}")
        meta["formula"] = "bitmask PIDs 01-20"
        return DiagnosticOutcome.SUCCEEDED, supported, None, meta

    if pid_n == "0c":
        if len(payload) < 2:
            return DiagnosticOutcome.MALFORMED, None, None, {**meta, "reason": "need 2 bytes"}
        value = ((payload[0] * 256) + payload[1]) / 4.0
        meta["formula"] = "((A*256)+B)/4"
        return DiagnosticOutcome.SUCCEEDED, value, "rpm", meta

    if pid_n == "0d":
        if len(payload) < 1:
            return DiagnosticOutcome.MALFORMED, None, None, {**meta, "reason": "need 1 byte"}
        meta["formula"] = "A"
        return DiagnosticOutcome.SUCCEEDED, float(payload[0]), "km/h", meta

    if pid_n == "05":
        if len(payload) < 1:
            return DiagnosticOutcome.MALFORMED, None, None, {**meta, "reason": "need 1 byte"}
        meta["formula"] = "A-40"
        return DiagnosticOutcome.SUCCEEDED, float(payload[0] - 40), "\u00b0C", meta

    if pid_n == "04":
        if len(payload) < 1:
            return DiagnosticOutcome.MALFORMED, None, None, {**meta, "reason": "need 1 byte"}
        meta["formula"] = "A*100/255"
        return DiagnosticOutcome.SUCCEEDED, (payload[0] * 100.0) / 255.0, "%", meta

    return DiagnosticOutcome.UNSUPPORTED, None, None, {**meta, "reason": "PID not decoded in this build"}


def parse_mode03_dtcs(raw: str) -> Tuple[DiagnosticOutcome, Any, Dict[str, Any]]:
    body = strip_elm_noise(raw)
    up = body.upper()
    if "NO DATA" in up:
        return DiagnosticOutcome.SUCCEEDED, [], {"raw": body, "note": "no stored DTCs or NO DATA"}
    try:
        data = _hex_bytes(body)
    except ValueError:
        return DiagnosticOutcome.MALFORMED, None, {"raw": body, "reason": "non-hex"}

    try:
        i = data.index(0x43)
    except ValueError:
        if not data:
            return DiagnosticOutcome.UNAVAILABLE, None, {"raw": body}
        return DiagnosticOutcome.MALFORMED, None, {"raw": body, "reason": "no 0x43"}

    payload = data[i + 1 :]
    if len(payload) and len(payload) % 2 == 1:
        payload = payload[1:]

    codes: List[str] = []
    for j in range(0, len(payload) - 1, 2):
        a, b = payload[j], payload[j + 1]
        if a == 0 and b == 0:
            continue
        type_bits = (a & 0xC0) >> 6
        prefix = "PCBU"[type_bits]
        codes.append(f"{prefix}{(a & 0x3F):02X}{b:02X}")
    return DiagnosticOutcome.SUCCEEDED, codes, {"raw": body, "service": "03"}


def parse_mode09_vin(raw: str) -> Tuple[DiagnosticOutcome, Any, Dict[str, Any]]:
    body = strip_elm_noise(raw)
    up = body.upper()
    if "NO DATA" in up:
        return DiagnosticOutcome.UNAVAILABLE, None, {"raw": body}
    try:
        data = _hex_bytes(body)
    except ValueError:
        m = re.search(r"[A-HJ-NPR-Z0-9]{17}", body.upper())
        if m:
            return DiagnosticOutcome.SUCCEEDED, m.group(0), {"raw": body, "method": "ascii_extract"}
        return DiagnosticOutcome.MALFORMED, None, {"raw": body, "reason": "non-hex"}

    vin_chars: List[str] = []
    i = 0
    while i < len(data) - 1:
        if data[i] == 0x49 and data[i + 1] == 0x02:
            rest = data[i + 2 :]
            if rest and rest[0] < 0x20:
                rest = rest[1:]
            for b in rest:
                if 32 <= b < 127:
                    vin_chars.append(chr(b))
            i += 2
        else:
            i += 1
    vin = "".join(vin_chars).strip()
    if len(vin) >= 17:
        vin = re.sub(r"[^A-HJ-NPR-Z0-9]", "", vin.upper())[:17]
        if len(vin) == 17:
            return DiagnosticOutcome.SUCCEEDED, vin, {"raw": body, "service": "09", "pid": "02"}
    if vin:
        return DiagnosticOutcome.AMBIGUOUS, vin, {"raw": body, "reason": "incomplete VIN"}
    return DiagnosticOutcome.UNAVAILABLE, None, {"raw": body}
