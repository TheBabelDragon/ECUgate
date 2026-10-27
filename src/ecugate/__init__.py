"""ECUgate

Model-agnostic layer for typed tool execution, persistent structured memory,
observed outcomes, and enforceable permissions.
"""

from ecugate.registry import ToolRegistry, ToolDefinition, ToolPermission
from ecugate.memory import MemoryStore, MemoryRecord, RecordType
from ecugate.execution import ExecutionEngine, Operation, OperationStatus

__version__ = "0.1.0"

__all__ = [
    "ToolRegistry",
    "ToolDefinition",
    "ToolPermission",
    "MemoryStore",
    "MemoryRecord",
    "RecordType",
    "ExecutionEngine",
    "Operation",
    "OperationStatus",
    "__version__",
]
