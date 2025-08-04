"""Cache management for C++ analyzer."""

import json
import hashlib
import time
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict
from .symbol_info import SymbolInfo


class CacheManager:
    """Manages caching for the C++ analyzer."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.cache_dir = self._get_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_cache_dir(self) -> Path:
        """Get the cache directory for this project"""
        # Use the MCP server directory for cache, not the project being analyzed
        mcp_server_root = Path(__file__).parent.parent  # Go up from mcp_server/cache_manager.py to root
        cache_base = mcp_server_root / ".mcp_cache"
        
        # Use a hash of the project path to create a unique cache directory
        project_hash = hashlib.md5(str(self.project_root).encode()).hexdigest()[:8]
        cache_dir = cache_base / f"{self.project_root.name}_{project_hash}"
        return cache_dir
    
    def get_file_hash(self, file_path: str) -> str:
        """Calculate hash of a file"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return ""
    
    def save_cache(self, class_index: Dict[str, List[SymbolInfo]], 
                   function_index: Dict[str, List[SymbolInfo]],
                   file_hashes: Dict[str, str],
                   indexed_file_count: int,
                   include_dependencies: bool = False) -> bool:
        """Save indexes to cache file"""
        try:
            cache_file = self.cache_dir / "cache_info.json"
            
            # Convert to serializable format
            cache_data = {
                "version": "2.0",  # Cache version
                "include_dependencies": include_dependencies,
                "class_index": {},
                "function_index": {},
                "file_hashes": file_hashes,
                "indexed_file_count": indexed_file_count,
                "timestamp": time.time()
            }
            
            # Convert class index
            for name, infos in class_index.items():
                cache_data["class_index"][name] = [info.to_dict() for info in infos]
            
            # Convert function index
            for name, infos in function_index.items():
                cache_data["function_index"][name] = [info.to_dict() for info in infos]
            
            # Save to file
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving cache: {e}", file=sys.stderr)
            return False
    
    def load_cache(self, include_dependencies: bool = False) -> Optional[Dict[str, Any]]:
        """Load cache if it exists and is valid"""
        cache_file = self.cache_dir / "cache_info.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Check cache version
            if cache_data.get("version") != "2.0":
                print("Cache version mismatch, rebuilding...", file=sys.stderr)
                return None
            
            # Check if dependencies setting matches
            cached_include_deps = cache_data.get("include_dependencies", False)
            if cached_include_deps != include_dependencies:
                print(f"Cache dependencies setting mismatch (cached={cached_include_deps}, current={include_dependencies})", 
                      file=sys.stderr)
                return None
            
            return cache_data
            
        except Exception as e:
            print(f"Error loading cache: {e}", file=sys.stderr)
            return None
    
    def get_file_cache_path(self, file_path: str) -> Path:
        """Get the cache file path for a given source file"""
        files_dir = self.cache_dir / "files"
        cache_filename = hashlib.md5(file_path.encode()).hexdigest() + ".json"
        return files_dir / cache_filename
    
    def save_file_cache(self, file_path: str, symbols: List[SymbolInfo], 
                       file_hash: str) -> bool:
        """Save parsed symbols for a single file"""
        try:
            # Create files subdirectory
            files_dir = self.cache_dir / "files"
            files_dir.mkdir(exist_ok=True)
            
            # Use hash of file path as cache filename
            cache_file = self.get_file_cache_path(file_path)
            
            # Prepare cache data
            cache_data = {
                "file_path": file_path,
                "file_hash": file_hash,
                "timestamp": time.time(),
                "symbols": [s.to_dict() for s in symbols]
            }
            
            # Save to file
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            return True
        except Exception as e:
            # Silently fail for individual file caches
            return False
    
    def load_file_cache(self, file_path: str, current_hash: str) -> Optional[List[SymbolInfo]]:
        """Load cached symbols for a file if hash matches"""
        try:
            cache_file = self.get_file_cache_path(file_path)
            
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Check if file hash matches
            if cache_data.get("file_hash") != current_hash:
                return None
            
            # Reconstruct SymbolInfo objects
            symbols = []
            for s in cache_data.get("symbols", []):
                symbols.append(SymbolInfo(**s))
            
            return symbols
        except:
            return None
    
    def save_progress(self, total_files: int, indexed_files: int, 
                     failed_files: int, cache_hits: int,
                     last_index_time: float, class_count: int, 
                     function_count: int, status: str = "in_progress"):
        """Save indexing progress"""
        try:
            progress_file = self.cache_dir / "indexing_progress.json"
            progress_data = {
                "project_root": str(self.project_root),
                "total_files": total_files,
                "indexed_files": indexed_files,
                "failed_files": failed_files,
                "cache_hits": cache_hits,
                "last_index_time": last_index_time,
                "timestamp": time.time(),
                "class_count": class_count,
                "function_count": function_count,
                "status": status
            }
            
            with open(progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
        except:
            pass  # Silently fail for progress tracking
    
    def load_progress(self) -> Optional[Dict[str, Any]]:
        """Load indexing progress if available"""
        try:
            progress_file = self.cache_dir / "indexing_progress.json"
            if not progress_file.exists():
                return None
                
            with open(progress_file, 'r') as f:
                return json.load(f)
        except:
            return None