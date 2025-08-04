"""Search functionality for C++ symbols."""

import re
from typing import Dict, List, Optional, Any
from collections import defaultdict
from .symbol_info import SymbolInfo


class SearchEngine:
    """Handles searching for C++ symbols."""
    
    def __init__(self, class_index: Dict[str, List[SymbolInfo]], 
                 function_index: Dict[str, List[SymbolInfo]],
                 file_index: Dict[str, List[SymbolInfo]],
                 usr_index: Dict[str, SymbolInfo]):
        self.class_index = class_index
        self.function_index = function_index
        self.file_index = file_index
        self.usr_index = usr_index
    
    def search_classes(self, pattern: str, project_only: bool = True) -> List[Dict[str, Any]]:
        """Search for classes matching a pattern"""
        results = []
        regex = re.compile(pattern, re.IGNORECASE)
        
        for name, infos in self.class_index.items():
            if regex.search(name):
                for info in infos:
                    if not project_only or info.is_project:
                        results.append({
                            "name": info.name,
                            "kind": info.kind,
                            "file": info.file,
                            "line": info.line,
                            "is_project": info.is_project,
                            "base_classes": info.base_classes
                        })
        
        return results
    
    def search_functions(self, pattern: str, project_only: bool = True, 
                        class_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for functions matching a pattern"""
        results = []
        regex = re.compile(pattern, re.IGNORECASE)
        
        for name, infos in self.function_index.items():
            if regex.search(name):
                for info in infos:
                    if not project_only or info.is_project:
                        # Filter by class name if specified
                        if class_name and info.parent_class != class_name:
                            continue
                        
                        results.append({
                            "name": info.name,
                            "kind": info.kind,
                            "file": info.file,
                            "line": info.line,
                            "signature": info.signature,
                            "is_project": info.is_project,
                            "parent_class": info.parent_class
                        })
        
        return results
    
    def search_symbols(self, pattern: str, project_only: bool = True,
                      symbol_types: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Search for any symbols matching a pattern"""
        results = {"classes": [], "functions": []}
        
        # Filter symbol types
        search_classes = not symbol_types or any(t in ["class", "struct"] for t in symbol_types)
        search_functions = not symbol_types or any(t in ["function", "method"] for t in symbol_types)
        
        if search_classes:
            results["classes"] = self.search_classes(pattern, project_only)
        
        if search_functions:
            results["functions"] = self.search_functions(pattern, project_only)
        
        return results
    
    def get_symbols_in_file(self, file_path: str) -> List[SymbolInfo]:
        """Get all symbols in a specific file"""
        return self.file_index.get(file_path, [])
    
    def get_class_info(self, class_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a class"""
        infos = self.class_index.get(class_name, [])
        if not infos:
            return None
        
        # Return the first match (could be enhanced to handle multiple matches)
        info = infos[0]
        
        # Find all methods of this class
        methods = []
        for name, func_infos in self.function_index.items():
            for func_info in func_infos:
                if func_info.parent_class == class_name:
                    methods.append({
                        "name": func_info.name,
                        "signature": func_info.signature,
                        "access": func_info.access,
                        "line": func_info.line
                    })
        
        return {
            "name": info.name,
            "kind": info.kind,
            "file": info.file,
            "line": info.line,
            "base_classes": info.base_classes,
            "methods": sorted(methods, key=lambda x: x["line"]),
            "is_project": info.is_project
        }
    
    def get_function_signature(self, function_name: str, 
                             class_name: Optional[str] = None) -> List[str]:
        """Get function signatures matching the name"""
        signatures = []
        
        for info in self.function_index.get(function_name, []):
            if class_name is None or info.parent_class == class_name:
                if info.parent_class:
                    signatures.append(f"{info.parent_class}::{info.name}{info.signature}")
                else:
                    signatures.append(f"{info.name}{info.signature}")
        
        return signatures