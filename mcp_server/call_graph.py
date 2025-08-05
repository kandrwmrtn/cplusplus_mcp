"""Call graph analysis for C++ code."""

import re
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict
from .symbol_info import SymbolInfo


class CallGraphAnalyzer:
    """Manages call graph analysis for C++ code."""
    
    def __init__(self):
        self.call_graph: Dict[str, Set[str]] = defaultdict(set)  # Function USR -> Set of called USRs
        self.reverse_call_graph: Dict[str, Set[str]] = defaultdict(set)  # Function USR -> Set of caller USRs
    
    def add_call(self, caller_usr: str, callee_usr: str):
        """Add a function call relationship"""
        if caller_usr and callee_usr:
            self.call_graph[caller_usr].add(callee_usr)
            self.reverse_call_graph[callee_usr].add(caller_usr)
    
    def clear(self):
        """Clear all call graph data"""
        self.call_graph.clear()
        self.reverse_call_graph.clear()
    
    def remove_symbol(self, usr: str):
        """Remove a symbol from the call graph completely"""
        if usr in self.call_graph:
            # Remove all calls made by this function
            called_functions = self.call_graph[usr].copy()
            for called_usr in called_functions:
                self.reverse_call_graph[called_usr].discard(usr)
                # Clean up empty sets
                if not self.reverse_call_graph[called_usr]:
                    del self.reverse_call_graph[called_usr]
            del self.call_graph[usr]
        
        if usr in self.reverse_call_graph:
            # Remove all calls to this function
            calling_functions = self.reverse_call_graph[usr].copy()
            for caller_usr in calling_functions:
                self.call_graph[caller_usr].discard(usr)
                # Clean up empty sets
                if not self.call_graph[caller_usr]:
                    del self.call_graph[caller_usr]
            del self.reverse_call_graph[usr]
    
    def rebuild_from_symbols(self, symbols: List[SymbolInfo]):
        """Rebuild call graph from symbol list"""
        self.clear()
        for symbol in symbols:
            if symbol.usr and symbol.calls:
                for called_usr in symbol.calls:
                    self.add_call(symbol.usr, called_usr)
    
    def find_callers(self, function_usr: str) -> Set[str]:
        """Find all functions that call the specified function"""
        return self.reverse_call_graph.get(function_usr, set())
    
    def find_callees(self, function_usr: str) -> Set[str]:
        """Find all functions called by the specified function"""
        return self.call_graph.get(function_usr, set())
    
    def get_call_paths(self, from_usr: str, to_usr: str, max_depth: int = 10) -> List[List[str]]:
        """Find all call paths from one function to another"""
        if from_usr == to_usr:
            return [[from_usr]]
        
        if max_depth <= 0:
            return []
        
        paths = []
        
        # Get direct callees
        callees = self.find_callees(from_usr)
        
        for callee in callees:
            if callee == to_usr:
                # Direct call found
                paths.append([from_usr, to_usr])
            else:
                # Recursively search for paths
                sub_paths = self.get_call_paths(callee, to_usr, max_depth - 1)
                for sub_path in sub_paths:
                    paths.append([from_usr] + sub_path)
        
        return paths
    
    def get_call_statistics(self) -> Dict[str, Any]:
        """Get statistics about the call graph"""
        return {
            "total_functions_with_calls": len(self.call_graph),
            "total_functions_being_called": len(self.reverse_call_graph),
            "total_unique_calls": sum(len(calls) for calls in self.call_graph.values()),
            "most_called_functions": self._get_most_called_functions(10),
            "functions_with_most_calls": self._get_functions_with_most_calls(10)
        }
    
    def _get_most_called_functions(self, limit: int) -> List[tuple]:
        """Get the most frequently called functions"""
        call_counts = [(usr, len(callers)) for usr, callers in self.reverse_call_graph.items()]
        return sorted(call_counts, key=lambda x: x[1], reverse=True)[:limit]
    
    def _get_functions_with_most_calls(self, limit: int) -> List[tuple]:
        """Get functions that make the most calls"""
        call_counts = [(usr, len(callees)) for usr, callees in self.call_graph.items()]
        return sorted(call_counts, key=lambda x: x[1], reverse=True)[:limit]