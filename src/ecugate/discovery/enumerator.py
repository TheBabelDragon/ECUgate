"""Interface enumerator protocol and composite helpers.

Real host enumeration is opt-in. Default discovery remains simulation-first
with no mandatory hardware dependencies.
"""

from __future__ import annotations

from typing import List, Protocol, runtime_checkable

from ecugate.discovery.pipeline import InterfaceRecord


@runtime_checkable
class InterfaceEnumerator(Protocol):
    """Non-destructive interface enumeration source."""

    def enumerate(self) -> List[InterfaceRecord]:
        """Return available interfaces without opening exclusive device sessions."""
        ...


class EmptyEnumerator:
    """Always returns no interfaces (safe default for unit tests)."""

    def enumerate(self) -> List[InterfaceRecord]:
        return []


class StaticEnumerator:
    """Returns a fixed list — used for tests and simulation injection."""

    def __init__(self, interfaces: List[InterfaceRecord] | None = None) -> None:
        self._interfaces = list(interfaces or [])

    def inject(self, iface: InterfaceRecord) -> None:
        self._interfaces.append(iface)

    def clear(self) -> None:
        self._interfaces.clear()

    def enumerate(self) -> List[InterfaceRecord]:
        return list(self._interfaces)


class CompositeEnumerator:
    """Merge results from multiple enumerators; later sources append."""

    def __init__(self, *sources: InterfaceEnumerator) -> None:
        self._sources = list(sources)

    def enumerate(self) -> List[InterfaceRecord]:
        out: List[InterfaceRecord] = []
        seen: set[str] = set()
        for src in self._sources:
            for iface in src.enumerate():
                key = iface.interface_id
                if key in seen:
                    continue
                seen.add(key)
                out.append(iface)
        return out
