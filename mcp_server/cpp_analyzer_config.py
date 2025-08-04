"""Configuration loader for C++ analyzer settings."""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional


class CppAnalyzerConfig:
    """Loads and manages configuration for the C++ analyzer."""
    
    CONFIG_FILENAME = "cpp-analyzer-config.json"
    
    DEFAULT_CONFIG = {
        "exclude_directories": [
            ".git",
            ".svn",
            ".hg",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".vs",
            ".vscode",
            ".idea",
            "CMakeFiles",
            "CMakeCache.txt"
        ],
        "dependency_directories": [
            "vcpkg_installed",
            "third_party",
            "ThirdParty",
            "external",
            "External",
            "vendor",
            "dependencies",
            "packages"
        ],
        "exclude_patterns": [],
        "include_dependencies": True,
        "max_file_size_mb": 10
    }
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        # Config file is in the MCP server directory, not the project directory
        mcp_server_root = Path(__file__).parent.parent
        self.config_path = mcp_server_root / self.CONFIG_FILENAME
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    user_config = json.load(f)
                # Merge with defaults
                config = self.DEFAULT_CONFIG.copy()
                config.update(user_config)
                print(f"Loaded project config from: {self.config_path}", file=os.sys.stderr)
                return config
            except Exception as e:
                print(f"Error loading config from {self.config_path}: {e}", file=os.sys.stderr)
                print("Using default configuration", file=os.sys.stderr)
        
        return self.DEFAULT_CONFIG.copy()
    
    def get_exclude_directories(self) -> List[str]:
        """Get list of directories to exclude."""
        return self.config.get("exclude_directories", self.DEFAULT_CONFIG["exclude_directories"])
    
    def get_dependency_directories(self) -> List[str]:
        """Get list of directories that contain dependencies."""
        return self.config.get("dependency_directories", self.DEFAULT_CONFIG["dependency_directories"])
    
    def get_exclude_patterns(self) -> List[str]:
        """Get list of file patterns to exclude."""
        return self.config.get("exclude_patterns", self.DEFAULT_CONFIG["exclude_patterns"])
    
    def get_include_dependencies(self) -> bool:
        """Get whether to include dependencies."""
        return self.config.get("include_dependencies", self.DEFAULT_CONFIG["include_dependencies"])
    
    def get_max_file_size_mb(self) -> float:
        """Get maximum file size in MB."""
        return self.config.get("max_file_size_mb", self.DEFAULT_CONFIG["max_file_size_mb"])
    
    def create_example_config(self) -> None:
        """Create an example configuration file."""
        example_config = {
            "exclude_directories": [
                ".git",
                ".svn", 
                "RepoExamples",
                "ThirdParty",
                "Intermediate",
                "Binaries",
                "DerivedDataCache"
            ],
            "exclude_patterns": [
                "*.generated.h",
                "*.generated.cpp",
                "*_test.cpp"
            ],
            "include_dependencies": True,
            "max_file_size_mb": 10,
            "_comment": "Place this .cpp-analyzer.json file in your project root to customize C++ analyzer behavior"
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(example_config, f, indent=2)
        
        print(f"Created example config at: {self.config_path}", file=os.sys.stderr)