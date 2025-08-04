"""File discovery and filtering for C++ projects."""

import os
import sys
from pathlib import Path
from typing import List, Set


class FileScanner:
    """Handles file discovery and filtering for C++ projects."""
    
    # C++ file extensions
    CPP_EXTENSIONS = {'.cpp', '.cc', '.cxx', '.c++', '.h', '.hpp', '.hxx', '.h++'}
    
    # Directories to exclude (set by configuration)
    EXCLUDE_DIRS = set()
    
    # Directories that contain dependencies (set by configuration)
    DEPENDENCY_DIRS = set()
    
    def __init__(self, project_root: Path, include_dependencies: bool = False):
        self.project_root = project_root
        self.include_dependencies = include_dependencies
    
    def should_skip_directory(self, dir_path: str) -> bool:
        """Check if a directory should be skipped"""
        # Only skip if this directory is directly under the project root
        try:
            rel_path = Path(dir_path).relative_to(self.project_root)
            # If the relative path has no parent, it's a top-level directory
            if len(rel_path.parts) == 1:
                return rel_path.parts[0] in self.EXCLUDE_DIRS
        except ValueError:
            # Directory is outside project root
            pass
        return False
    
    def should_skip_file(self, file_path: str) -> bool:
        """Check if a file should be skipped during indexing"""
        # Skip files outside project root (shouldn't happen, but safety check)
        try:
            rel_path = Path(file_path).relative_to(self.project_root)
        except ValueError:
            # File is outside project root
            if not self.include_dependencies:
                return True
            else:
                return False
        
        # Check if file is in a top-level excluded directory
        if len(rel_path.parts) > 0 and rel_path.parts[0] in self.EXCLUDE_DIRS:
            return True
        
        return False
    
    def find_cpp_files(self) -> List[str]:
        """Find all C++ files in the project"""
        files = []
        
        try:
            for root, dirs, filenames in os.walk(self.project_root):
                # Filter directories in-place to prevent walking into them
                dirs[:] = [d for d in dirs if not self.should_skip_directory(os.path.join(root, d))]
                
                for filename in filenames:
                    if any(filename.endswith(ext) for ext in self.CPP_EXTENSIONS):
                        file_path = os.path.join(root, filename)
                        if not self.should_skip_file(file_path):
                            files.append(file_path)
        except Exception as e:
            print(f"Error scanning directory: {e}", file=sys.stderr)
        
        return files
    
    def is_project_file(self, file_path: str) -> bool:
        """Check if a file is part of the project (not a dependency)"""
        if not file_path:
            return False
        
        # Check if file is under project root
        try:
            rel_path = Path(file_path).relative_to(self.project_root)
            
            # Check if file is in a dependency directory (at any level)
            for part in rel_path.parts:
                if part in self.DEPENDENCY_DIRS:
                    return False
            
            return True
        except ValueError:
            # File is outside project root - it's a dependency
            return False