#!/usr/bin/env python3
"""Test if MCP server imports work"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Testing imports...")
    
    # Test mcp package
    import mcp
    print("[OK] mcp package imported")
    
    # Test libclang
    import clang.cindex
    print("[OK] libclang imported")
    
    # Test our modules
    from mcp_server.cpp_analyzer import CppAnalyzer
    print("[OK] CppAnalyzer imported")
    
    # Test MCP server module
    import mcp_server.cpp_mcp_server
    print("[OK] cpp_mcp_server module imported")
    
    print("\nAll imports successful!")
    
except Exception as e:
    print(f"[FAIL] Import failed: {e}")
    import traceback
    traceback.print_exc()