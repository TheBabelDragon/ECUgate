"""Bounded serial transport with timeouts and injectable test doubles."""

from __future__ import annotations

import time
from typing import List, Optional, Protocol, runtime_checkable


class TransportError(Exception):
    """Transport-level failure (timeout, disconnect, open error)."""


@runtime_checkable
class SerialTransport(Protocol):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def write(self, data: bytes) -> None: ...
    def read_until(self, terminator: bytes = b">", timeout: float = 2.0) -> bytes: ...
    def is_open(self) -> bool: ...


class FakeSerialTransport:
    """In-memory transport for unit tests — never touches hardware."""

    def __init__(
        self,
        responses: Optional[List[bytes]] = None,
        *,
        fail_open: bool = False,
        read_delay: float = 0.0,
        timeout_after: Optional[int] = None,
    ) -> None:
        self._responses = list(responses or [])
        self._fail_open = fail_open
        self._read_delay = read_delay
        self._timeout_after = timeout_after
        self._open = False
        self.written: List[bytes] = []
        self._read_count = 0

    def open(self) -> None:
        if self._fail_open:
            raise TransportError("simulated open failure")
        self._open = True

    def close(self) -> None:
        self._open = False

    def is_open(self) -> bool:
        return self._open

    def write(self, data: bytes) -> None:
        if not self._open:
            raise TransportError("transport not open")
        self.written.append(data)

    def read_until(self, terminator: bytes = b">", timeout: float = 2.0) -> bytes:
        if not self._open:
            raise TransportError("transport not open")
        if self._read_delay:
            time.sleep(self._read_delay)
        self._read_count += 1
        if self._timeout_after is not None and self._read_count > self._timeout_after:
            raise TransportError("simulated timeout")
        if not self._responses:
            raise TransportError("no response available")
        return self._responses.pop(0)

    def queue_response(self, data: bytes) -> None:
        self._responses.append(data)


class PyserialTransport:
    """Optional real serial transport. Only used when explicitly opened by caller."""

    def __init__(self, port: str, baudrate: int = 38400, timeout: float = 2.0) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._ser = None

    def open(self) -> None:
        try:
            import serial  # type: ignore
        except ImportError as e:
            raise TransportError(
                "pyserial is required for real hardware; install ecugate[vehicle] or pyserial"
            ) from e
        try:
            self._ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout,
            )
        except Exception as e:
            raise TransportError(f"failed to open {self.port}: {e}") from e

    def close(self) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            finally:
                self._ser = None

    def is_open(self) -> bool:
        return bool(self._ser and getattr(self._ser, "is_open", False))

    def write(self, data: bytes) -> None:
        if not self._ser:
            raise TransportError("transport not open")
        self._ser.write(data)
        self._ser.flush()

    def read_until(self, terminator: bytes = b">", timeout: float = 2.0) -> bytes:
        if not self._ser:
            raise TransportError("transport not open")
        deadline = time.monotonic() + timeout
        buf = bytearray()
        while time.monotonic() < deadline:
            chunk = self._ser.read(1)
            if not chunk:
                continue
            buf.extend(chunk)
            if terminator in buf:
                return bytes(buf)
        raise TransportError(f"timeout waiting for {terminator!r} on {self.port}")
