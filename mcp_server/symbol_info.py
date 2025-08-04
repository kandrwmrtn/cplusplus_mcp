"""Symbol information data structure for C++ analysis."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SymbolInfo:
    """Information about a C++ symbol (class, function, etc.)"""
    name: str
    kind: str  # "class", "function", "method", etc.
    file: str
    line: int
    column: int
    signature: str = ""
    is_project: bool = True
    namespace: str = ""
    access: str = "public"  # public, private, protected
    parent_class: str = ""  # For methods, the containing class
    base_classes: List[str] = field(default_factory=list)  # For classes
    usr: str = ""  # Unified Symbol Resolution - unique identifier
    calls: List[str] = field(default_factory=list)  # USRs of functions this function calls
    called_by: List[str] = field(default_factory=list)  # USRs of functions that call this
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "kind": self.kind,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "signature": self.signature,
            "is_project": self.is_project,
            "namespace": self.namespace,
            "access": self.access,
            "parent_class": self.parent_class,
            "base_classes": self.base_classes,
            "usr": self.usr,
            "calls": self.calls,
            "called_by": self.called_by
        }