#!/usr/bin/env python3
"""
Test script to verify that deleted files are properly removed from MCP server cache.

This script:
1. Creates a temporary C++ file in the project
2. Indexes the project to include the new file
3. Deletes the file
4. Refreshes the indexes
5. Verifies the file is completely removed from all indexes
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.cpp_analyzer import CppAnalyzer


def test_deletion_fix():
    """Test that deleted files are properly removed from indexes"""
    print("Testing deletion fix for MCP C++ analyzer...")
    
    # Use current directory as test project
    project_root = Path(__file__).parent.parent
    print(f"Using project root: {project_root}")
    
    # Create analyzer
    analyzer = CppAnalyzer(str(project_root))
    
    # Create a temporary C++ file
    test_file_content = '''
#include <iostream>

class TestDeletionClass {
public:
    void testDeletionMethod() {
        std::cout << "This file should be deleted!" << std::endl;
    }
};

void testDeletionFunction() {
    TestDeletionClass obj;
    obj.testDeletionMethod();
}
'''
    
    temp_file = project_root / "temp_test_file.cpp"
    try:
        # Step 1: Create the temporary file
        print(f"Creating temporary file: {temp_file}")
        with open(temp_file, 'w') as f:
            f.write(test_file_content)
        
        # Step 2: Index the file
        print("Indexing the temporary file...")
        success, was_cached = analyzer.index_file(str(temp_file), force=True)
        if not success:
            print("ERROR: Failed to index temporary file")
            return False
        
        # Step 3: Verify the file was indexed
        print("Verifying file was indexed...")
        classes_before = analyzer.search_classes("TestDeletionClass", project_only=True)
        functions_before = analyzer.search_functions("testDeletionFunction", project_only=True)
        
        if not classes_before:
            print("ERROR: TestDeletionClass not found after indexing")
            return False
        if not functions_before:
            print("ERROR: testDeletionFunction not found after indexing")
            return False
        
        print(f"[OK] Found class: {classes_before[0]['name']} in {classes_before[0]['file']}")
        print(f"[OK] Found function: {functions_before[0]['name']} in {functions_before[0]['file']}")
        
        # Step 4: Delete the file
        print(f"Deleting temporary file: {temp_file}")
        temp_file.unlink()
        
        # Step 5: Refresh the indexes
        print("Refreshing indexes to detect deleted file...")
        refreshed_count = analyzer.refresh_if_needed()
        print(f"Refreshed {refreshed_count} files")
        
        # Step 6: Verify the file and its symbols are completely removed
        print("Verifying file was completely removed from indexes...")
        classes_after = analyzer.search_classes("TestDeletionClass", project_only=True)
        functions_after = analyzer.search_functions("testDeletionFunction", project_only=True)
        
        # Check if symbols still exist
        if classes_after:
            print(f"ERROR: TestDeletionClass still found after deletion: {classes_after}")
            return False
        if functions_after:
            print(f"ERROR: testDeletionFunction still found after deletion: {functions_after}")
            return False
        
        # Check if file is still tracked
        if str(temp_file) in analyzer.file_hashes:
            print(f"ERROR: Deleted file still in file_hashes: {temp_file}")
            return False
        
        if str(temp_file) in analyzer.translation_units:
            print(f"ERROR: Deleted file still in translation_units: {temp_file}")
            return False
        
        if str(temp_file) in analyzer.file_index:
            print(f"ERROR: Deleted file still in file_index: {temp_file}")
            return False
        
        print("[OK] TestDeletionClass correctly removed from class index")
        print("[OK] testDeletionFunction correctly removed from function index")
        print("[OK] File completely removed from all tracking structures")
        
        # Step 7: Test cache cleanup
        cache_file = analyzer.cache_manager.get_file_cache_path(str(temp_file))
        if cache_file.exists():
            print(f"ERROR: Cache file still exists after deletion: {cache_file}")
            return False
        
        print("[OK] Cache file correctly removed")
        
        print("\nSUCCESS: Deletion fix is working correctly!")
        print("Deleted files are now properly removed from all indexes and cache.")
        return True
        
    except Exception as e:
        print(f"ERROR: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup: Remove temp file if it still exists
        if temp_file.exists():
            print(f"Cleaning up temporary file: {temp_file}")
            temp_file.unlink()


if __name__ == "__main__":
    success = test_deletion_fix()
    sys.exit(0 if success else 1)