#!/usr/bin/env python3
"""
Download libclang.dll for self-contained MCP server
"""

import os
import urllib.request
import tarfile
import sys

def download_libclang():
    """Download and extract libclang.dll"""
    print("Downloading libclang.dll for Windows...")
    
    # Create directory
    os.makedirs("lib/windows", exist_ok=True)
    
    # Check if already exists
    if os.path.exists("lib/windows/libclang.dll"):
        print("✓ libclang.dll already exists")
        return True
    
    try:
        # Download portable LLVM release
        url = "https://github.com/llvm/llvm-project/releases/download/llvmorg-18.1.8/clang+llvm-18.1.8-x86_64-pc-windows-msvc.tar.xz"
        temp_file = "llvm-temp.tar.xz"
        
        print("Downloading LLVM portable release (~100MB)...")
        urllib.request.urlretrieve(url, temp_file)
        print("Downloaded! Extracting libclang.dll...")
        
        # Extract just libclang.dll
        with tarfile.open(temp_file, 'r:xz') as tar:
            for member in tar.getmembers():
                if member.name.endswith('bin/libclang.dll'):
                    # Extract to lib/windows/libclang.dll
                    with tar.extractfile(member) as source:
                        with open("lib/windows/libclang.dll", "wb") as target:
                            target.write(source.read())
                    break
        
        # Clean up
        os.remove(temp_file)
        print("✓ Successfully extracted libclang.dll")
        return True
        
    except Exception as e:
        print(f"✗ Download failed: {e}")
        print("You can manually download and extract:")
        print("1. Go to: https://github.com/llvm/llvm-project/releases/latest")
        print("2. Download: clang+llvm-*-x86_64-pc-windows-msvc.tar.xz")
        print("3. Extract and copy bin/libclang.dll to lib/windows/libclang.dll")
        return False

if __name__ == "__main__":
    success = download_libclang()
    sys.exit(0 if success else 1)