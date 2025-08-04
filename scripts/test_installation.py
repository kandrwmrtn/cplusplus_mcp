#!/usr/bin/env python3
"""
Test script to verify C++ MCP Server installation
"""
import sys
import os

def test_imports():
    """Test that all required packages can be imported"""
    print("Testing package imports...")
    
    try:
        import mcp
        print("✓ MCP package imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import MCP: {e}")
        return False
    
    try:
        import clang.cindex
        print("✓ libclang Python bindings imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import clang: {e}")
        return False
    
    return True

def test_libclang_library():
    """Test that libclang library can be found and loaded"""
    print("\nTesting libclang library...")
    
    try:
        from clang.cindex import Config
        
        # Get the parent directory path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        
        # Check for bundled libclang
        libclang_paths = []
        if sys.platform == "win32":
            libclang_paths.append(os.path.join(parent_dir, "lib", "windows", "libclang.dll"))
        elif sys.platform == "darwin":
            libclang_paths.append(os.path.join(parent_dir, "lib", "macos", "libclang.dylib"))
        else:
            libclang_paths.extend([
                os.path.join(parent_dir, "lib", "linux", "libclang.so.1"),
                os.path.join(parent_dir, "lib", "linux", "libclang.so")
            ])
        
        bundled_found = False
        for path in libclang_paths:
            if os.path.exists(path):
                print(f"✓ Found bundled libclang at: {path}")
                bundled_found = True
                Config.set_library_file(path)
                break
        
        if not bundled_found:
            print("⚠ No bundled libclang found, will use system library")
        
        # Try to create an index (this will fail if libclang can't be loaded)
        from clang.cindex import Index
        index = Index.create()
        print("✓ libclang library loaded successfully")
        return True
        
    except Exception as e:
        print(f"✗ Failed to load libclang: {e}")
        return False

def test_server_import():
    """Test that the MCP server can be imported"""
    print("\nTesting MCP server import...")
    
    try:
        # We need to test this in a subprocess to avoid libclang conflicts
        import subprocess
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        
        # Run a simple import test in a clean Python process
        test_code = f"""
import sys
sys.path.insert(0, r'{parent_dir}')
from mcp_server import cpp_mcp_server
print("SUCCESS")
"""
        
        result = subprocess.run(
            [sys.executable, "-c", test_code],
            capture_output=True,
            text=True,
            cwd=parent_dir
        )
        
        if result.returncode == 0 and "SUCCESS" in result.stdout:
            print("✓ MCP server module imported successfully")
            return True
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            print(f"✗ Failed to import MCP server: {error_msg}")
            return False
    except Exception as e:
        print(f"✗ Failed to test MCP server import: {e}")
        return False

def test_basic_parsing():
    """Test basic C++ parsing functionality"""
    print("\nTesting basic C++ parsing...")
    
    try:
        from clang.cindex import Index, TranslationUnit
        
        # Create a simple test file content
        test_code = """
        class TestClass {
        public:
            void testMethod() {}
        };
        """
        
        # Create index and parse
        index = Index.create()
        tu = TranslationUnit.from_source(
            'test.cpp',
            args=['-x', 'c++'],
            unsaved_files=[('test.cpp', test_code)]
        )
        
        # Check if parsing succeeded
        if tu:
            print("✓ Basic C++ parsing works")
            return True
        else:
            print("✗ Failed to parse test C++ code")
            return False
            
    except Exception as e:
        print(f"✗ C++ parsing test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("C++ MCP Server Installation Test")
    print("=" * 40)
    
    all_passed = True
    
    # Run tests
    if not test_imports():
        all_passed = False
    
    if not test_libclang_library():
        all_passed = False
    
    if not test_server_import():
        all_passed = False
    
    if not test_basic_parsing():
        all_passed = False
    
    # Summary
    print("\n" + "=" * 40)
    if all_passed:
        print("✓ All tests passed! The C++ MCP Server is ready to use.")
        print("\nNext steps:")
        print("1. Configure Claude Desktop (see README)")
        print("2. Start Claude and set a C++ project directory")
        return 0
    else:
        print("✗ Some tests failed. Please check the errors above.")
        print("\nCommon fixes:")
        print("- Run server_setup.bat to install dependencies")
        print("- Make sure you're in the virtual environment")
        print("- Check that libclang.dll exists in lib\\windows\\")
        return 1

if __name__ == "__main__":
    sys.exit(main())