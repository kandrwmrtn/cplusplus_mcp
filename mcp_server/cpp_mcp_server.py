#!/usr/bin/env python3
"""
C++ Code Analysis MCP Server

Provides tools for analyzing C++ codebases using libclang.
Focused on specific queries rather than bulk data dumps.
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import threading
import multiprocessing
import tempfile
import subprocess
import shutil

try:
    import clang.cindex
    from clang.cindex import Index, CursorKind, TypeKind, Config
except ImportError:
    print("Error: clang package not found. Install with: pip install libclang", file=sys.stderr)
    sys.exit(1)

from mcp.server import Server
from mcp.types import (
    Tool,
    TextContent,
)

def find_and_configure_libclang():
    """Find and configure libclang library"""
    import platform
    import glob
    
    system = platform.system()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one directory to find lib folder (since we're in mcp_server subfolder)
    parent_dir = os.path.dirname(script_dir)
    
    # First, try bundled libraries (self-contained)
    bundled_paths = []
    if system == "Windows":
        bundled_paths = [
            os.path.join(parent_dir, "lib", "windows", "libclang.dll"),
            os.path.join(parent_dir, "lib", "windows", "clang.dll"),
        ]
    elif system == "Darwin":  # macOS
        bundled_paths = [
            os.path.join(parent_dir, "lib", "macos", "libclang.dylib"),
        ]
    else:  # Linux
        bundled_paths = [
            os.path.join(parent_dir, "lib", "linux", "libclang.so.1"),
            os.path.join(parent_dir, "lib", "linux", "libclang.so"),
        ]
    
    # Try bundled libraries first
    for path in bundled_paths:
        if os.path.exists(path):
            print(f"Using bundled libclang at: {path}", file=sys.stderr)
            Config.set_library_file(path)
            return True
    
    print("No bundled libclang found, searching system...", file=sys.stderr)
    
    # Fallback to system-installed libraries
    if system == "Windows":
        system_paths = [
            # LLVM official installer paths
            r"C:\Program Files\LLVM\bin\libclang.dll",
            r"C:\Program Files (x86)\LLVM\bin\libclang.dll",
            # vcpkg paths
            r"C:\vcpkg\installed\x64-windows\bin\clang.dll",
            r"C:\vcpkg\installed\x86-windows\bin\clang.dll",
            # Conda paths
            r"C:\ProgramData\Anaconda3\Library\bin\libclang.dll",
        ]
        
        # Try to find in system PATH
        import shutil
        llvm_config = shutil.which("llvm-config")
        if llvm_config:
            try:
                import subprocess
                result = subprocess.run([llvm_config, "--libdir"], capture_output=True, text=True)
                if result.returncode == 0:
                    lib_dir = result.stdout.strip()
                    system_paths.insert(0, os.path.join(lib_dir, "libclang.dll"))
            except:
                pass
    
    elif system == "Darwin":  # macOS
        system_paths = [
            "/usr/local/lib/libclang.dylib",
            "/opt/homebrew/lib/libclang.dylib",
            "/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/libclang.dylib",
        ]
    
    else:  # Linux
        system_paths = [
            "/usr/lib/llvm-*/lib/libclang.so.1",
            "/usr/lib/x86_64-linux-gnu/libclang-*.so.1",
            "/usr/lib/libclang.so.1",
            "/usr/lib/libclang.so",
        ]
    
    # Try each system path
    for path_pattern in system_paths:
        if "*" in path_pattern:
            # Handle glob patterns
            matches = glob.glob(path_pattern)
            if matches:
                path = matches[0]  # Use first match
            else:
                continue
        else:
            path = path_pattern
        
        if os.path.exists(path):
            print(f"Found system libclang at: {path}", file=sys.stderr)
            Config.set_library_file(path)
            return True
    
    return False

# Try to find and configure libclang
if not find_and_configure_libclang():
    print("Error: Could not find libclang library.", file=sys.stderr)
    print("Please install LLVM/Clang:", file=sys.stderr)
    print("  Windows: Download from https://releases.llvm.org/", file=sys.stderr)
    print("  macOS: brew install llvm", file=sys.stderr)
    print("  Linux: sudo apt install libclang-dev", file=sys.stderr)
    sys.exit(1)

class CppAnalyzer:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.index = Index.create()
        self.translation_units = {}
        self.file_timestamps = {}  # Track file modification times
        self.last_refresh_check = 0.0  # Timestamp of last refresh check
        self.refresh_interval = 2.0  # Only check for changes every 2 seconds
        
        # Pre-built indexes for fast searching
        self.class_index = {}  # name -> list of class info
        self.function_index = {}  # name -> list of function info
        self.indexes_built = False
        
        # Lazy initialization to avoid tool timeouts
        self.initialization_started = False
        self.initialization_complete = False
        
        # Threading for parallel parsing
        self.parse_lock = threading.Lock()
        # Cap at 16 threads - libclang parsing is mostly I/O bound
        self.max_workers = min(16, (os.cpu_count() or 1) * 2)  # Cap at 16 threads
        
        self.vcpkg_root = self._find_vcpkg_root()
        self.vcpkg_triplet = self._detect_vcpkg_triplet()
        self.vcpkg_dependencies = self._read_vcpkg_dependencies()
        
        # Don't parse immediately - do it on first search to avoid timeout
        print("CppAnalyzer ready for lazy initialization", file=sys.stderr)
    
    def _find_vcpkg_root(self) -> Optional[Path]:
        """Find vcpkg installation directory by reading project configuration"""
        
        # Method 1: Check for vcpkg.json in project (vcpkg manifest mode)
        vcpkg_json = self.project_root / "vcpkg.json"
        if vcpkg_json.exists():
            print(f"Found vcpkg.json manifest at: {vcpkg_json}", file=sys.stderr)
            
            # In manifest mode, vcpkg installs to ./vcpkg_installed
            vcpkg_installed = self.project_root / "vcpkg_installed"
            if vcpkg_installed.exists():
                print(f"Using manifest mode vcpkg at: {vcpkg_installed}", file=sys.stderr)
                return vcpkg_installed
        
        # Method 2: Parse CMakeLists.txt for CMAKE_TOOLCHAIN_FILE
        cmake_file = self.project_root / "CMakeLists.txt"
        if cmake_file.exists():
            try:
                with open(cmake_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Look for vcpkg toolchain file path
                import re
                toolchain_match = re.search(r'CMAKE_TOOLCHAIN_FILE["\s]*([^"\s)]+vcpkg\.cmake)', content)
                if toolchain_match:
                    toolchain_path = Path(toolchain_match.group(1).strip('"'))
                    # vcpkg.cmake is typically at /scripts/buildsystems/vcpkg.cmake
                    vcpkg_root = toolchain_path.parent.parent.parent
                    if (vcpkg_root / "installed").exists():
                        print(f"Found vcpkg via CMakeLists.txt at: {vcpkg_root}", file=sys.stderr)
                        return vcpkg_root
            except Exception as e:
                print(f"Could not parse CMakeLists.txt: {e}", file=sys.stderr)
        
        # Method 3: Check environment variables
        import os
        vcpkg_root_env = os.environ.get('VCPKG_ROOT')
        if vcpkg_root_env:
            vcpkg_path = Path(vcpkg_root_env)
            if vcpkg_path.exists() and (vcpkg_path / "installed").exists():
                print(f"Found vcpkg via VCPKG_ROOT: {vcpkg_path}", file=sys.stderr)
                return vcpkg_path
        
        # Method 4: Common installation paths (fallback)
        common_paths = [
            Path("C:/vcpkg"),
            Path("C:/dev/vcpkg"),
            Path("C:/tools/vcpkg"),
            self.project_root / "vcpkg",
            self.project_root / ".." / "vcpkg"
        ]
        
        for path in common_paths:
            if path.exists() and (path / "installed").exists():
                print(f"Found vcpkg at common path: {path}", file=sys.stderr)
                return path
        
        print("vcpkg not found - using basic include paths", file=sys.stderr)
        return None
    
    def _detect_vcpkg_triplet(self) -> str:
        """Detect the vcpkg triplet to use"""
        import platform
        
        # Try to read from CMakeLists.txt first
        cmake_file = self.project_root / "CMakeLists.txt"
        if cmake_file.exists():
            try:
                with open(cmake_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    import re
                    triplet_match = re.search(r'VCPKG_TARGET_TRIPLET["\s]*([^"\s)]+)', content)
                    if triplet_match:
                        triplet = triplet_match.group(1).strip('"')
                        print(f"Found vcpkg triplet in CMakeLists.txt: {triplet}", file=sys.stderr)
                        return triplet
            except Exception:
                pass
        
        # Default based on platform
        system = platform.system()
        if system == "Windows":
            return "x64-windows"
        elif system == "Darwin":
            return "x64-osx"
        else:
            return "x64-linux"
    
    def _read_vcpkg_dependencies(self) -> List[str]:
        """Read vcpkg dependencies from vcpkg.json"""
        vcpkg_json = self.project_root / "vcpkg.json"
        if not vcpkg_json.exists():
            return []
        
        try:
            import json
            with open(vcpkg_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                deps = data.get('dependencies', [])
                
                # Handle both string deps and object deps (with features)
                dep_names = []
                for dep in deps:
                    if isinstance(dep, str):
                        dep_names.append(dep)
                    elif isinstance(dep, dict) and 'name' in dep:
                        dep_names.append(dep['name'])
                
                print(f"Found {len(dep_names)} vcpkg dependencies: {', '.join(dep_names[:5])}{'...' if len(dep_names) > 5 else ''}", file=sys.stderr)
                return dep_names
        except Exception as e:
            print(f"Could not read vcpkg.json: {e}", file=sys.stderr)
            return []
    
    def _scan_project(self):
        """Scan project for C++ files and create translation units (multithreaded)"""
        cpp_extensions = {'.cpp', '.cc', '.cxx', '.c++', '.h', '.hpp', '.hxx', '.h++'}
        
        # Collect all files to parse
        files_to_parse = []
        for ext in cpp_extensions:
            for file_path in self.project_root.rglob(f"*{ext}"):
                if self._should_include_file(file_path):
                    files_to_parse.append(file_path)
        
        if not files_to_parse:
            print("No C++ files found to parse", file=sys.stderr)
            return
        
        print(f"Found {len(files_to_parse)} C++ files, parsing with {self.max_workers} threads...", file=sys.stderr)
        start_time = time.time()
        
        # Parse files in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all parsing tasks
            future_to_file = {
                executor.submit(self._parse_file_safe, file_path): file_path 
                for file_path in files_to_parse
            }
            
            # Process completed tasks and show progress
            completed = 0
            for future in as_completed(future_to_file):
                completed += 1
                if completed % 20 == 0 or completed == len(files_to_parse):
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    print(f"Parsed {completed}/{len(files_to_parse)} files ({rate:.1f} files/sec)", file=sys.stderr)
        
        elapsed = time.time() - start_time
        successful = len(self.translation_units)
        print(f"Parsing complete: {successful}/{len(files_to_parse)} files in {elapsed:.2f}s", file=sys.stderr)
        print(f"Search indexes built during parsing: {len(self.class_index)} class names, {len(self.function_index)} function names", file=sys.stderr)
        self.indexes_built = True
    
    def _should_include_file(self, file_path: Path) -> bool:
        """Filter out unwanted files"""
        exclude_dirs = {
            'build', 'cmake-build', '.git', 'third_party', 'external', 'deps', 'thirdparty',
            'mcp_env', 'venv', '.venv', 'env', '.env',  # Python virtual environments
            'vcpkg_installed', 'vcpkg', 'node_modules',  # Package managers
            'bin', 'obj', 'Debug', 'Release', 'x64', 'Win32'  # Build outputs
        }
        return not any(part in exclude_dirs for part in file_path.parts)
    
    def _is_project_file(self, file_path: str) -> bool:
        """Check if a file belongs to the project (vs external dependencies)"""
        file_path_obj = Path(file_path)
        
        # File is part of the project if it's under the project root
        try:
            file_path_obj.relative_to(self.project_root)
            return True
        except ValueError:
            # File is outside project root (e.g., vcpkg dependencies, system headers)
            return False
    
    def _get_file_timestamp(self, file_path: Path) -> float:
        """Get file modification timestamp"""
        try:
            return file_path.stat().st_mtime
        except OSError:
            return 0.0
    
    def _is_file_modified(self, file_path: Path) -> bool:
        """Check if file has been modified since last parse"""
        file_str = str(file_path)
        current_time = self._get_file_timestamp(file_path)
        last_time = self.file_timestamps.get(file_str, 0.0)
        return current_time > last_time
    
    def refresh_if_needed(self):
        """Check for file changes and re-parse if needed"""
        modified_files = []
        
        # Check all currently tracked files for modifications
        for file_path_str in list(self.translation_units.keys()):
            file_path = Path(file_path_str)
            if file_path.exists() and self._is_file_modified(file_path):
                modified_files.append(file_path)
            elif not file_path.exists():
                # File was deleted, remove from indexes
                del self.translation_units[file_path_str]
                del self.file_timestamps[file_path_str]
        
        # Use the file scanner to find all current C++ files
        from .file_scanner import FileScanner
        scanner = FileScanner(self.project_root, include_dependencies=True)
        scanner.EXCLUDE_DIRS = self.exclude_dirs
        scanner.DEPENDENCY_DIRS = self.dependency_dirs
        
        current_files = set(scanner.find_cpp_files())
        tracked_files = set(self.translation_units.keys())
        
        # Find new files
        new_files = current_files - tracked_files
        for file_path_str in new_files:
            file_path = Path(file_path_str)
            if self._should_include_file(file_path):
                modified_files.append(file_path)
        
        if modified_files:
            print(f"Detected {len(modified_files)} modified/new files, re-parsing...", file=sys.stderr)
            for file_path in modified_files:
                self._parse_file(file_path)  # Indexes updated during parsing
        
        return len(modified_files)
    
    def _build_indexes(self):
        """Build search indexes for fast lookups (multithreaded)"""
        print("Building search indexes...", file=sys.stderr)
        start_time = time.time()
        
        self.class_index.clear()
        self.function_index.clear()
        
        # Use thread-safe collections for building indexes
        from collections import defaultdict
        temp_class_index = defaultdict(list)
        temp_function_index = defaultdict(list)
        
        # Build lists of files to process
        files_to_process = list(self.translation_units.items())
        
        # Process files in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all indexing tasks
            future_to_file = {
                executor.submit(self._index_file_safe, file_path, tu): file_path 
                for file_path, tu in files_to_process
            }
            
            # Process completed tasks and show progress
            completed = 0
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    class_entries, func_entries = future.result()
                    
                    # Safely merge results
                    with self.parse_lock:
                        for name, entries in class_entries.items():
                            temp_class_index[name].extend(entries)
                        for name, entries in func_entries.items():
                            temp_function_index[name].extend(entries)
                    
                    completed += 1
                    if completed % 20 == 0 or completed == len(files_to_process):
                        elapsed = time.time() - start_time
                        rate = completed / elapsed if elapsed > 0 else 0
                        print(f"Indexed {completed}/{len(files_to_process)} files ({rate:.1f} files/sec)", file=sys.stderr)
                        
                except Exception as e:
                    print(f"Warning: Failed to index {file_path}: {e}", file=sys.stderr)
        
        # Convert to regular dicts
        self.class_index = dict(temp_class_index)
        self.function_index = dict(temp_function_index)
        
        elapsed = time.time() - start_time
        print(f"Search indexes built in {elapsed:.2f}s: {len(self.class_index)} class names, {len(self.function_index)} function names", file=sys.stderr)
        self.indexes_built = True
    
    def _index_file_safe(self, file_path: str, tu) -> Tuple[Dict[str, List], Dict[str, List]]:
        """Thread-safe file indexing for building search indexes"""
        from collections import defaultdict
        
        class_entries = defaultdict(list)
        func_entries = defaultdict(list)
        
        try:
            for cursor in tu.cursor.walk_preorder():
                if cursor.kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL]:
                    if cursor.spelling:
                        class_info = {
                            'name': cursor.spelling,
                            'kind': cursor.kind.name,
                            'file': file_path,
                            'line': cursor.location.line,
                            'column': cursor.location.column,
                            'is_project': self._is_project_file(file_path)
                        }
                        class_entries[cursor.spelling].append(class_info)
                
                elif cursor.kind in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD]:
                    if cursor.spelling:
                        func_info = {
                            'name': cursor.spelling,
                            'kind': cursor.kind.name,
                            'file': file_path,
                            'line': cursor.location.line,
                            'column': cursor.location.column,
                            'signature': self._get_function_signature(cursor),
                            'is_project': self._is_project_file(file_path)
                        }
                        func_entries[cursor.spelling].append(func_info)
        
        except Exception as e:
            print(f"Warning: Failed to index {file_path}: {e}", file=sys.stderr)
        
        return dict(class_entries), dict(func_entries)
    
    def _parse_file_safe(self, file_path: Path):
        """Thread-safe wrapper for parsing a single file"""
        try:
            result = self._parse_file_internal(file_path)
            if result:
                file_str, tu, timestamp, class_entries, func_entries = result
                with self.parse_lock:
                    self.translation_units[file_str] = tu
                    self.file_timestamps[file_str] = timestamp
                    
                    # Merge index entries during parsing
                    for name, entries in class_entries.items():
                        if name not in self.class_index:
                            self.class_index[name] = []
                        self.class_index[name].extend(entries)
                    
                    for name, entries in func_entries.items():
                        if name not in self.function_index:
                            self.function_index[name] = []
                        self.function_index[name].extend(entries)
        except Exception as e:
            print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
    
    def _parse_file_internal(self, file_path: Path) -> Optional[Tuple[str, Any, float, Dict[str, List], Dict[str, List]]]:
        """Internal file parsing logic (called from thread)"""
        try:
            # Build comprehensive compile args for vcpkg project
            args = [
                '-std=c++17',
                '-I.',
                f'-I{self.project_root}',
                f'-I{self.project_root}/src',
                # Preprocessor defines for common libraries
                '-DWIN32',
                '-D_WIN32',
                '-D_WINDOWS',
                '-DNOMINMAX',
                # Common warnings to suppress
                '-Wno-pragma-once-outside-header',
                '-Wno-unknown-pragmas',
                '-Wno-deprecated-declarations',
                # Parse as C++
                '-x', 'c++',
            ]
            
            # Add vcpkg includes if found
            if self.vcpkg_root and self.vcpkg_triplet:
                vcpkg_include = self.vcpkg_root / "installed" / self.vcpkg_triplet / "include"
                if vcpkg_include.exists():
                    args.append(f'-I{vcpkg_include}')
                    
                    # Add include paths for specific dependencies found in vcpkg.json
                    common_subdir_mappings = {
                        'sdl2': 'SDL2',
                        'bgfx': 'bgfx',
                        'bx': 'bx', 
                        'bimg': 'bimg',
                        'imgui': 'imgui',
                        'assimp': 'assimp',
                        'joltphysics': 'Jolt',
                        'openssl': 'openssl',
                        'protobuf': 'google/protobuf',
                        'nlohmann-json': 'nlohmann',
                        'sol2': 'sol'
                    }
                    
                    for dep in self.vcpkg_dependencies:
                        # Check if this dependency has a known subdirectory
                        if dep in common_subdir_mappings:
                            subdir = common_subdir_mappings[dep]
                            lib_path = vcpkg_include / subdir
                            if lib_path.exists():
                                args.append(f'-I{lib_path}')
                        
                        # Also check for exact directory match
                        dep_path = vcpkg_include / dep
                        if dep_path.exists() and dep_path.is_dir():
                            args.append(f'-I{dep_path}')
            
            # Add Windows SDK includes (try to find current version)
            import glob
            winsdk_patterns = [
                "C:/Program Files (x86)/Windows Kits/10/Include/*/ucrt",
                "C:/Program Files (x86)/Windows Kits/10/Include/*/um",
                "C:/Program Files (x86)/Windows Kits/10/Include/*/shared"
            ]
            for pattern in winsdk_patterns:
                matches = glob.glob(pattern)
                if matches:
                    args.append(f'-I{matches[-1]}')  # Use latest version
            
            tu = self.index.parse(str(file_path), args=args)
            if tu:
                timestamp = self._get_file_timestamp(file_path)
                file_str = str(file_path)
                
                # Build indexes during parsing (single AST traversal)
                from collections import defaultdict
                class_entries = defaultdict(list)
                func_entries = defaultdict(list)
                
                for cursor in tu.cursor.walk_preorder():
                    if cursor.kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL]:
                        if cursor.spelling:
                            class_info = {
                                'name': cursor.spelling,
                                'kind': cursor.kind.name,
                                'file': file_str,
                                'line': cursor.location.line,
                                'column': cursor.location.column,
                                'is_project': self._is_project_file(file_str)
                            }
                            class_entries[cursor.spelling].append(class_info)
                    
                    elif cursor.kind in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD]:
                        if cursor.spelling:
                            func_info = {
                                'name': cursor.spelling,
                                'kind': cursor.kind.name,
                                'file': file_str,
                                'line': cursor.location.line,
                                'column': cursor.location.column,
                                'signature': self._get_function_signature(cursor),
                                'is_project': self._is_project_file(file_str)
                            }
                            func_entries[cursor.spelling].append(func_info)
                
                return (file_str, tu, timestamp, dict(class_entries), dict(func_entries))
            elif tu and len(tu.diagnostics) > 0:
                # Only warn for serious errors, not dependency issues
                serious_errors = [d for d in tu.diagnostics if d.severity >= 3]  # Error or Fatal
                if serious_errors:
                    print(f"Warning: Parse errors in {file_path}: {len(serious_errors)} errors", file=sys.stderr)
            
            return None
        except Exception as e:
            print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
            return None
    
    def _parse_file(self, file_path: Path):
        """Single-threaded file parsing (for refresh operations)"""
        result = self._parse_file_internal(file_path)
        if result:
            file_str, tu, timestamp, class_entries, func_entries = result
            self.translation_units[file_str] = tu
            self.file_timestamps[file_str] = timestamp
            
            # Update indexes for this file
            for name, entries in class_entries.items():
                if name not in self.class_index:
                    self.class_index[name] = []
                self.class_index[name].extend(entries)
            
            for name, entries in func_entries.items():
                if name not in self.function_index:
                    self.function_index[name] = []
                self.function_index[name].extend(entries)
    
    def _ensure_initialized(self):
        """Ensure the analyzer is initialized (lazy loading to avoid timeouts)"""
        if not self.initialization_complete:
            if not self.initialization_started:
                print("Starting project analysis (this may take a moment)...", file=sys.stderr)
                self.initialization_started = True
                self._scan_project()  # Indexes are built during parsing now
                self.initialization_complete = True
                print("Project analysis complete - searches will now be fast!", file=sys.stderr)
    
    def search_classes(self, pattern: str, project_only: bool = True) -> List[Dict[str, Any]]:
        """Search for classes matching pattern"""
        # Ensure initialized on first use
        self._ensure_initialized()
        
        # Check for file changes before searching (throttled)
        current_time = time.time()
        if current_time - self.last_refresh_check > self.refresh_interval:
            self.refresh_if_needed()
            self.last_refresh_check = current_time
        
        results = []
        regex = re.compile(pattern, re.IGNORECASE)
        
        # Search through the pre-built index (much faster)
        for class_name, class_infos in self.class_index.items():
            if regex.search(class_name):
                for class_info in class_infos:
                    # Filter by project_only flag
                    if project_only and not class_info['is_project']:
                        continue
                    results.append(class_info.copy())
        
        return results
    
    def search_functions(self, pattern: str, project_only: bool = True) -> List[Dict[str, Any]]:
        """Search for functions matching pattern"""
        # Ensure initialized on first use
        self._ensure_initialized()
        
        # Check for file changes before searching (throttled)
        current_time = time.time()
        if current_time - self.last_refresh_check > self.refresh_interval:
            self.refresh_if_needed()
            self.last_refresh_check = current_time
        
        results = []
        regex = re.compile(pattern, re.IGNORECASE)
        
        # Search through the pre-built index (much faster)
        for func_name, func_infos in self.function_index.items():
            if regex.search(func_name):
                for func_info in func_infos:
                    # Filter by project_only flag
                    if project_only and not func_info['is_project']:
                        continue
                    results.append(func_info.copy())
        
        return results
    
    def get_class_info(self, class_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific class"""
        for file_path, tu in self.translation_units.items():
            for cursor in tu.cursor.walk_preorder():
                if (cursor.kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL] 
                    and cursor.spelling == class_name):
                    
                    return {
                        'name': cursor.spelling,
                        'kind': cursor.kind.name,
                        'file': file_path,
                        'line': cursor.location.line,
                        'methods': self._get_class_methods(cursor),
                        'members': self._get_class_members(cursor),
                        'base_classes': self._get_base_classes(cursor)
                    }
        return None
    
    def get_function_signature(self, function_name: str) -> List[Dict[str, Any]]:
        """Get signature details for functions with given name"""
        results = []
        
        for file_path, tu in self.translation_units.items():
            for cursor in tu.cursor.walk_preorder():
                if (cursor.kind in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD]
                    and cursor.spelling == function_name):
                    
                    results.append({
                        'name': cursor.spelling,
                        'file': file_path,
                        'line': cursor.location.line,
                        'signature': self._get_function_signature(cursor),
                        'return_type': cursor.result_type.spelling,
                        'parameters': self._get_function_parameters(cursor)
                    })
        
        return results
    
    def find_in_file(self, file_path: str, pattern: str) -> List[Dict[str, Any]]:
        """Search for symbols within a specific file"""
        results = []
        abs_path = str(self.project_root / file_path)
        
        if abs_path in self.translation_units:
            tu = self.translation_units[abs_path]
            regex = re.compile(pattern, re.IGNORECASE)
            
            for cursor in tu.cursor.walk_preorder():
                if (cursor.location.file and 
                    str(cursor.location.file) == abs_path and
                    cursor.spelling and 
                    regex.search(cursor.spelling)):
                    
                    results.append({
                        'name': cursor.spelling,
                        'kind': cursor.kind.name,
                        'line': cursor.location.line,
                        'column': cursor.location.column
                    })
        
        return results
    
    def _get_function_signature(self, cursor) -> str:
        """Extract function signature"""
        try:
            return cursor.type.spelling
        except:
            return f"{cursor.spelling}(...)"
    
    def _get_function_parameters(self, cursor) -> List[Dict[str, str]]:
        """Get function parameters"""
        params = []
        for child in cursor.get_children():
            if child.kind == CursorKind.PARM_DECL:
                params.append({
                    'name': child.spelling,
                    'type': child.type.spelling
                })
        return params
    
    def _get_class_methods(self, cursor) -> List[Dict[str, Any]]:
        """Get class methods"""
        methods = []
        for child in cursor.get_children():
            if child.kind == CursorKind.CXX_METHOD:
                methods.append({
                    'name': child.spelling,
                    'signature': self._get_function_signature(child),
                    'line': child.location.line,
                    'access': self._get_access_specifier(child)
                })
        return methods
    
    def _get_class_members(self, cursor) -> List[Dict[str, Any]]:
        """Get class member variables"""
        members = []
        for child in cursor.get_children():
            if child.kind == CursorKind.FIELD_DECL:
                members.append({
                    'name': child.spelling,
                    'type': child.type.spelling,
                    'line': child.location.line,
                    'access': self._get_access_specifier(child)
                })
        return members
    
    def _get_base_classes(self, cursor) -> List[str]:
        """Get base classes"""
        bases = []
        for child in cursor.get_children():
            if child.kind == CursorKind.CXX_BASE_SPECIFIER:
                bases.append(child.type.spelling)
        return bases
    
    def _get_access_specifier(self, cursor) -> str:
        """Get access level (public/private/protected)"""
        access_map = {
            clang.cindex.AccessSpecifier.PUBLIC: "public",
            clang.cindex.AccessSpecifier.PROTECTED: "protected", 
            clang.cindex.AccessSpecifier.PRIVATE: "private"
        }
        return access_map.get(cursor.access_specifier, "unknown")
    
    def test_compile_files(self, header_info: Dict[str, str], source_info: Dict[str, str], 
                          test_integration: bool = True) -> Dict[str, Any]:
        """
        Test if header/source file pair would compile with the project using libclang.
        
        Args:
            header_info: Dict with 'path' and 'content' keys
            source_info: Dict with 'path' and 'content' keys  
            test_integration: Whether to test integration with existing project
            
        Returns:
            Dict with compilation results, errors, warnings, etc.
        """
        results = {
            "header_compiles": False,
            "source_compiles": False,
            "links_with_project": False,
            "errors": [],
            "warnings": [],
            "missing_dependencies": [],
            "clang_available": True
        }
        
        # Check if libclang is available (same as main analyzer)
        if not hasattr(self, 'index') or not self.index:
            results["clang_available"] = False
            results["errors"].append("libclang not available")
            return results
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create header file
                header_filename = Path(header_info["path"]).name
                header_path = temp_path / header_filename
                
                with open(header_path, 'w', encoding='utf-8') as f:
                    f.write(header_info["content"])
                
                # Test header compilation using libclang
                header_result = self._test_compile_with_libclang(header_path, test_integration)
                results["header_compiles"] = header_result["success"]
                if not header_result["success"]:
                    results["errors"].extend(header_result["errors"])
                results["warnings"].extend(header_result["warnings"])
                
                # Create source file
                source_filename = Path(source_info["path"]).name
                source_path = temp_path / source_filename
                
                # Include the header in the source file
                source_content = f'#include "{header_filename}"\n{source_info["content"]}'
                
                with open(source_path, 'w', encoding='utf-8') as f:
                    f.write(source_content)
                
                # Test source compilation using libclang
                source_result = self._test_compile_with_libclang(source_path, test_integration)
                results["source_compiles"] = source_result["success"]
                if not source_result["success"]:
                    results["errors"].extend(source_result["errors"])
                results["warnings"].extend(source_result["warnings"])
                
                # Extract missing dependencies from errors
                results["missing_dependencies"] = self._extract_missing_dependencies(results["errors"])
                
                # Both files compiled successfully means they can link
                if results["header_compiles"] and results["source_compiles"]:
                    results["links_with_project"] = True
                
        except Exception as e:
            results["errors"].append(f"Test compilation failed: {str(e)}")
        
        return results
    
    def _test_compile_with_libclang(self, file_path: Path, test_integration: bool) -> Dict[str, Any]:
        """Test compilation using libclang (same as main analyzer)"""
        try:
            # Use the same compilation arguments as the main analyzer
            compile_args = []
            
            if test_integration:
                # Add project-specific include paths
                if self.project_root:
                    project_includes = [
                        self.project_root,
                        self.project_root / "include", 
                        self.project_root / "src"
                    ]
                    
                    for include_path in project_includes:
                        if include_path.exists():
                            compile_args.extend([f"-I{include_path}"])
                
                # Add vcpkg includes if available
                if hasattr(self, 'vcpkg_root') and self.vcpkg_root:
                    vcpkg_include = Path(self.vcpkg_root) / "installed" / "x64-windows" / "include"
                    if vcpkg_include.exists():
                        compile_args.append(f"-I{vcpkg_include}")
            
            # Add temp directory to include path for local headers
            temp_dir = file_path.parent
            compile_args.append(f"-I{temp_dir}")
            
            # Add standard C++ settings
            compile_args.extend(["-std=c++17", "-x", "c++"])
            
            # Try to parse the file with libclang
            tu = self.index.parse(str(file_path), args=compile_args)
            
            errors = []
            warnings = []
            
            # Check for diagnostics
            for diag in tu.diagnostics:
                message = f"{file_path.name}:{diag.location.line}:{diag.location.column}: {diag.spelling}"
                
                if diag.severity >= clang.cindex.Diagnostic.Error:
                    errors.append(message)
                elif diag.severity == clang.cindex.Diagnostic.Warning:
                    warnings.append(message)
            
            success = len(errors) == 0
            
            return {
                "success": success,
                "errors": errors,
                "warnings": warnings
            }
            
        except Exception as e:
            return {
                "success": False,
                "errors": [f"libclang compilation test failed: {str(e)}"],
                "warnings": []
            }

    def _extract_missing_dependencies(self, errors: List[str]) -> List[str]:
        """Check if clang++ is available"""
        try:
            # Try to find clang++ in PATH
            clang_path = shutil.which("clang++")
            if clang_path:
                return True
            
            # Try common Windows locations
            common_paths = [
                r"C:\Program Files\LLVM\bin\clang++.exe",
                r"C:\Program Files (x86)\LLVM\bin\clang++.exe",
                r"C:\msys64\ucrt64\bin\clang++.exe",
                r"C:\msys64\mingw64\bin\clang++.exe"
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _get_clang_command(self) -> str:
        """Get the clang++ command to use"""
        # Try PATH first
        clang_path = shutil.which("clang++")
        if clang_path:
            return "clang++"
        
        # Try common Windows locations
        common_paths = [
            r"C:\Program Files\LLVM\bin\clang++.exe",
            r"C:\Program Files (x86)\LLVM\bin\clang++.exe",
            r"C:\msys64\ucrt64\bin\clang++.exe",
            r"C:\msys64\mingw64\bin\clang++.exe"
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        return "clang++"  # Fallback
    
    def _build_compile_args_for_testing(self, include_project_headers: bool = True) -> List[str]:
        """Build compile arguments for testing"""
        args = [
            "-std=c++17",
            "-fsyntax-only",  # Only check syntax, don't generate output
            "-Wall",  # Enable common warnings
            "-Wextra",  # Enable extra warnings
        ]
        
        if include_project_headers:
            # Add project include paths
            args.extend([
                f"-I{self.project_root}",
                f"-I{self.project_root}/src",
            ])
            
            # Add vcpkg includes if available
            if self.vcpkg_root and self.vcpkg_triplet:
                vcpkg_include = self.vcpkg_root / "installed" / self.vcpkg_triplet / "include"
                if vcpkg_include.exists():
                    args.append(f"-I{vcpkg_include}")
        
        # Add preprocessor defines
        args.extend([
            "-DWIN32",
            "-D_WIN32",
            "-D_WINDOWS", 
            "-DNOMINMAX"
        ])
        
        return args
    
    def _test_compile_header(self, header_path: Path, test_integration: bool) -> Dict[str, Any]:
        """Test header file compilation"""
        try:
            clang_cmd = self._get_clang_command()
            compile_args = self._build_compile_args_for_testing(test_integration)
            
            # For header files, we need to create a dummy source file that includes it
            dummy_source = header_path.parent / "dummy_test.cpp"
            with open(dummy_source, 'w') as f:
                f.write(f'#include "{header_path.name}"\nint main() {{ return 0; }}')
            
            cmd = [clang_cmd] + compile_args + [str(dummy_source)]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            # Clean up dummy file
            dummy_source.unlink(missing_ok=True)
            
            return {
                "success": result.returncode == 0,
                "errors": self._parse_compiler_output(result.stderr, "error"),
                "warnings": self._parse_compiler_output(result.stderr, "warning")
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "errors": ["Compilation timeout (>30 seconds)"],
                "warnings": []
            }
        except Exception as e:
            return {
                "success": False,
                "errors": [f"Header compilation test failed: {str(e)}"],
                "warnings": []
            }
    
    def _test_compile_source(self, source_path: Path, test_integration: bool) -> Dict[str, Any]:
        """Test source file compilation"""
        try:
            clang_cmd = self._get_clang_command()
            compile_args = self._build_compile_args_for_testing(test_integration) 
            
            cmd = [clang_cmd] + compile_args + [str(source_path)]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            return {
                "success": result.returncode == 0,
                "errors": self._parse_compiler_output(result.stderr, "error"),
                "warnings": self._parse_compiler_output(result.stderr, "warning")
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False, 
                "errors": ["Compilation timeout (>30 seconds)"],
                "warnings": []
            }
        except Exception as e:
            return {
                "success": False,
                "errors": [f"Source compilation test failed: {str(e)}"],
                "warnings": []
            }
    
    def _test_linking(self, source_path: Path, test_integration: bool) -> Dict[str, Any]:
        """Test linking with project (basic test)"""
        if not test_integration:
            return {"success": True, "errors": [], "warnings": []}
        
        try:
            clang_cmd = self._get_clang_command()
            compile_args = self._build_compile_args_for_testing(test_integration)
            
            # Remove -fsyntax-only for linking test
            compile_args = [arg for arg in compile_args if arg != "-fsyntax-only"]
            
            # Add output file
            output_path = source_path.parent / "test_output.exe"
            compile_args.extend(["-o", str(output_path)])
            
            cmd = [clang_cmd] + compile_args + [str(source_path)]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            # Clean up output file
            output_path.unlink(missing_ok=True)
            
            return {
                "success": result.returncode == 0,
                "errors": self._parse_compiler_output(result.stderr, "error"),
                "warnings": self._parse_compiler_output(result.stderr, "warning")
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "errors": ["Linking timeout (>30 seconds)"],
                "warnings": []
            }
        except Exception as e:
            return {
                "success": False,
                "errors": [f"Linking test failed: {str(e)}"],
                "warnings": []
            }
    
    def _parse_compiler_output(self, output: str, message_type: str) -> List[str]:
        """Parse compiler output for errors or warnings"""
        messages = []
        if not output:
            return messages
        
        lines = output.split('\n')
        for line in lines:
            line = line.strip()
            if message_type.lower() in line.lower() and line:
                # Clean up the message
                messages.append(line)
        
        return messages
    
    def _extract_missing_dependencies(self, errors: List[str]) -> List[str]:
        """Extract missing dependencies from error messages"""
        missing_deps = []
        
        for error in errors:
            # Look for include file not found errors
            if "fatal error:" in error and "file not found" in error:
                # Extract the header name
                import re
                match = re.search(r"'([^']+)'\s+file not found", error)
                if match:
                    missing_deps.append(match.group(1))
            
            # Look for undefined symbol errors
            elif "undefined reference" in error or "unresolved external symbol" in error:
                # Could extract symbol names here in the future
                pass
        
        return list(set(missing_deps))  # Remove duplicates

# Import the enhanced Python analyzer
try:
    # Try package import first (when run as module)
    from mcp_server.cpp_analyzer import CppAnalyzer as EnhancedCppAnalyzer
except ImportError:
    # Fall back to direct import (when run as script)
    from cpp_analyzer import CppAnalyzer as EnhancedCppAnalyzer

# Initialize analyzer
PROJECT_ROOT = os.environ.get('CPP_PROJECT_ROOT', None)

# Initialize analyzer as None - will be set when project directory is specified
analyzer = None

# Track if analyzer has been initialized with a valid project
analyzer_initialized = False

# MCP Server
server = Server("cpp-analyzer")

@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="search_classes",
            description="Search for C++ classes by name pattern (regex supported)",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Class name pattern to search for (supports regex)"
                    },
                    "project_only": {
                        "type": "boolean",
                        "description": "Only search project files (exclude dependencies like vcpkg, system headers). Default: true",
                        "default": True
                    }
                },
                "required": ["pattern"]
            }
        ),
        Tool(
            name="search_functions", 
            description="Search for C++ functions by name pattern (regex supported)",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Function name pattern to search for (supports regex)"
                    },
                    "project_only": {
                        "type": "boolean",
                        "description": "Only search project files (exclude dependencies like vcpkg, system headers). Default: true",
                        "default": True
                    },
                    "class_name": {
                        "type": "string",
                        "description": "Optional: search only for methods within this class"
                    }
                },
                "required": ["pattern"]
            }
        ),
        Tool(
            name="get_class_info",
            description="Get detailed information about a specific class",
            inputSchema={
                "type": "object", 
                "properties": {
                    "class_name": {
                        "type": "string",
                        "description": "Exact class name to analyze"
                    }
                },
                "required": ["class_name"]
            }
        ),
        Tool(
            name="get_function_signature",
            description="Get signature and details for functions with given name",
            inputSchema={
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string", 
                        "description": "Exact function name to analyze"
                    },
                    "class_name": {
                        "type": "string",
                        "description": "Optional: specify class name to get method signatures only from that class"
                    }
                },
                "required": ["function_name"]
            }
        ),
        Tool(
            name="search_symbols",
            description="Search for all symbols (classes and functions) matching a pattern",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Pattern to search for (supports regex)"
                    },
                    "project_only": {
                        "type": "boolean",
                        "description": "Only search project files (exclude dependencies). Default: true",
                        "default": True
                    },
                    "symbol_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["class", "struct", "function", "method"]
                        },
                        "description": "Types of symbols to include. If not specified, includes all types"
                    }
                },
                "required": ["pattern"]
            }
        ),
        Tool(
            name="find_in_file",
            description="Search for symbols within a specific file",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to file from project root"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Symbol pattern to search for in the file"
                    }
                },
                "required": ["file_path", "pattern"]
            }
        ),
        Tool(
            name="set_project_directory",
            description="Set the project directory to analyze (use this first before other commands)",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Absolute path to the C++ project directory"
                    }
                },
                "required": ["project_path"]
            }
        ),
        Tool(
            name="refresh_project",
            description="Manually refresh/re-parse project files to detect changes",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_server_status",
            description="Get MCP server status including parsing progress and index stats",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_class_hierarchy",
            description="Get complete inheritance hierarchy for a C++ class",
            inputSchema={
                "type": "object", 
                "properties": {
                    "class_name": {
                        "type": "string",
                        "description": "Name of the class to analyze"
                    }
                },
                "required": ["class_name"]
            }
        ),
        Tool(
            name="get_derived_classes",
            description="Get all classes that inherit from a given base class",
            inputSchema={
                "type": "object",
                "properties": {
                    "class_name": {
                        "type": "string", 
                        "description": "Name of the base class"
                    },
                    "project_only": {
                        "type": "boolean",
                        "description": "Only include project classes (exclude dependencies). Default: true",
                        "default": True
                    }
                },
                "required": ["class_name"]
            }
        ),
        Tool(
            name="find_callers",
            description="Find all functions that call a specific function",
            inputSchema={
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "Name of the function to find callers for"
                    },
                    "class_name": {
                        "type": "string",
                        "description": "Optional: Class name if searching for a method",
                        "default": ""
                    }
                },
                "required": ["function_name"]
            }
        ),
        Tool(
            name="find_callees",
            description="Find all functions called by a specific function",
            inputSchema={
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "Name of the function to find callees for"
                    },
                    "class_name": {
                        "type": "string",
                        "description": "Optional: Class name if searching for a method",
                        "default": ""
                    }
                },
                "required": ["function_name"]
            }
        ),
        Tool(
            name="get_call_path",
            description="Find call paths from one function to another",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_function": {
                        "type": "string",
                        "description": "Starting function name"
                    },
                    "to_function": {
                        "type": "string",
                        "description": "Target function name"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum search depth (default: 10)",
                        "default": 10
                    }
                },
                "required": ["from_function", "to_function"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    try:
        if name == "set_project_directory":
            project_path = arguments["project_path"]
            if not os.path.exists(project_path):
                return [TextContent(type="text", text=f"Error: Directory '{project_path}' does not exist")]
            
            # Re-initialize analyzer with new path
            global analyzer, analyzer_initialized
            analyzer = EnhancedCppAnalyzer(project_path)
            analyzer_initialized = True
            
            # Start indexing in the background
            indexed_count = analyzer.index_project(force=False, include_dependencies=True)
            
            return [TextContent(type="text", text=f"Set project directory to: {project_path}\nIndexed {indexed_count} C++ files")]
        
        # Check if analyzer is initialized for all other commands
        if not analyzer_initialized or analyzer is None:
            return [TextContent(type="text", text="Error: Project directory not set. Please use 'set_project_directory' first with the path to your C++ project.")]
        
        if name == "search_classes":
            project_only = arguments.get("project_only", True)
            results = analyzer.search_classes(arguments["pattern"], project_only)
            return [TextContent(type="text", text=json.dumps(results, indent=2))]
        
        elif name == "search_functions":
            project_only = arguments.get("project_only", True)
            class_name = arguments.get("class_name", None)
            results = analyzer.search_functions(arguments["pattern"], project_only, class_name)
            return [TextContent(type="text", text=json.dumps(results, indent=2))]
        
        elif name == "get_class_info":
            result = analyzer.get_class_info(arguments["class_name"])
            if result:
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            else:
                return [TextContent(type="text", text=f"Class '{arguments['class_name']}' not found")]
        
        elif name == "get_function_signature":
            function_name = arguments["function_name"]
            class_name = arguments.get("class_name", None)
            results = analyzer.get_function_signature(function_name, class_name)
            return [TextContent(type="text", text=json.dumps(results, indent=2))]
        
        elif name == "search_symbols":
            pattern = arguments["pattern"]
            project_only = arguments.get("project_only", True)
            symbol_types = arguments.get("symbol_types", None)
            results = analyzer.search_symbols(pattern, project_only, symbol_types)
            return [TextContent(type="text", text=json.dumps(results, indent=2))]
        
        elif name == "find_in_file":
            results = analyzer.find_in_file(arguments["file_path"], arguments["pattern"])
            return [TextContent(type="text", text=json.dumps(results, indent=2))]
        
        elif name == "refresh_project":
            modified_count = analyzer.refresh_if_needed()
            return [TextContent(type="text", text=f"Refreshed project. Re-parsed {modified_count} modified/new files.")]
        
        elif name == "get_server_status":
            # Determine analyzer type
            analyzer_type = "python_enhanced"
            
            status = {
                "analyzer_type": analyzer_type,
                "call_graph_enabled": True,
                "usr_tracking_enabled": True
            }
            
            # Add analyzer stats from enhanced Python analyzer
            status.update({
                "parsed_files": len(analyzer.file_index),
                "indexed_classes": len(analyzer.class_index),
                "indexed_functions": len(analyzer.function_index),
                "indexed_symbols": len(analyzer.usr_index),
                "call_graph_size": len(analyzer.call_graph_analyzer.call_graph),
                "project_files": sum(1 for symbols in analyzer.file_index.values() 
                                   for s in symbols if s.is_project)
            })
            return [TextContent(type="text", text=json.dumps(status, indent=2))]
        
        elif name == "get_class_hierarchy":
            class_name = arguments["class_name"]
            hierarchy = analyzer.get_class_hierarchy(class_name)
            if hierarchy:
                return [TextContent(type="text", text=json.dumps(hierarchy, indent=2))]
            else:
                return [TextContent(type="text", text=f"Class '{class_name}' not found")]
        
        elif name == "get_derived_classes":
            class_name = arguments["class_name"]
            project_only = arguments.get("project_only", True)
            derived = analyzer.get_derived_classes(class_name, project_only)
            return [TextContent(type="text", text=json.dumps(derived, indent=2))]
        
        elif name == "find_callers":
            function_name = arguments["function_name"]
            class_name = arguments.get("class_name", "")
            results = analyzer.find_callers(function_name, class_name)
            return [TextContent(type="text", text=json.dumps(results, indent=2))]
        
        elif name == "find_callees":
            function_name = arguments["function_name"]
            class_name = arguments.get("class_name", "")
            results = analyzer.find_callees(function_name, class_name)
            return [TextContent(type="text", text=json.dumps(results, indent=2))]
        
        elif name == "get_call_path":
            from_function = arguments["from_function"]
            to_function = arguments["to_function"]
            max_depth = arguments.get("max_depth", 10)
            paths = analyzer.get_call_path(from_function, to_function, max_depth)
            return [TextContent(type="text", text=json.dumps(paths, indent=2))]
        
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    # Import here to avoid issues if mcp package not installed
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())