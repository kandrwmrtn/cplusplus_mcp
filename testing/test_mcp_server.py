#!/usr/bin/env python3
"""Test MCP server startup"""

import subprocess
import sys
import os

# Test 1: Direct execution
print("Test 1: Direct execution of MCP server")
print("=" * 50)
try:
    result = subprocess.run(
        [r"mcp_env\Scripts\python.exe", r"mcp_server\cpp_mcp_server.py"],
        capture_output=True,
        text=True,
        timeout=5
    )
    print(f"Return code: {result.returncode}")
    print(f"STDOUT:\n{result.stdout}")
    print(f"STDERR:\n{result.stderr}")
except subprocess.TimeoutExpired:
    print("Server is running (timeout after 5 seconds - this is expected for a server)")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 50)
print("Test 2: Testing with CPP_PROJECT_ROOT set")
print("=" * 50)

env = os.environ.copy()
env["CPP_PROJECT_ROOT"] = r"H:\Programming\MPCServers\CPlusPlus-MCP-Server\ChickenrikkeEngine"

try:
    result = subprocess.run(
        [r"mcp_env\Scripts\python.exe", r"mcp_server\cpp_mcp_server.py"],
        capture_output=True,
        text=True,
        timeout=5,
        env=env
    )
    print(f"Return code: {result.returncode}")
    print(f"STDOUT:\n{result.stdout}")
    print(f"STDERR:\n{result.stderr}")
except subprocess.TimeoutExpired:
    print("Server is running (timeout after 5 seconds - this is expected for a server)")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 50)
print("Test 3: Check if ChickenrikkeEngine directory exists")
print("=" * 50)
engine_path = r"H:\Programming\MPCServers\CPlusPlus-MCP-Server\ChickenrikkeEngine"
print(f"Path: {engine_path}")
print(f"Exists: {os.path.exists(engine_path)}")
print(f"Is directory: {os.path.isdir(engine_path)}")