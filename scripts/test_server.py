#!/usr/bin/env python3
"""
Test script for the C++ MCP Server
"""

import sys
import os
import datetime

# Add the parent directory to path so we can import from mcp_server
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Set up logging to file
log_file = os.path.join(parent_dir, 'test_results.log')

class Logger:
    def __init__(self, log_file):
        self.log_file = log_file
        self.console = sys.stdout
    
    def write(self, message):
        # Write to both console and file
        try:
            self.console.write(message)
        except UnicodeEncodeError:
            # Replace Unicode characters with ASCII equivalents
            ascii_message = message.replace('✓', '[OK]').replace('✗', '[FAIL]').replace('⚠️', '[WARN]')
            self.console.write(ascii_message)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(message)
    
    def flush(self):
        self.console.flush()

# Start logging
sys.stdout = Logger(log_file)

# Clear previous log
with open(log_file, 'w', encoding='utf-8') as f:
    f.write(f"=== C++ MCP Server Test Log - {datetime.datetime.now()} ===\n\n")

try:
    # Use our improved analyzer with per-file caching
    from mcp_server.cpp_analyzer import CppAnalyzer
    print("✓ Successfully imported CppAnalyzer with per-file caching")
    
    # Fast analyzer removed - using pure Python implementation
    FAST_ANALYZER_AVAILABLE = False
except Exception as e:
    print(f"✗ Failed to import CppAnalyzer: {e}")
    print("This usually means libclang is not properly configured.")
    sys.exit(1)

def test_compile_functionality(analyzer):
    """Test the compile testing functionality"""
    print("Testing compile functionality...")
    
    # Test 1: Simple valid C++ code
    print("\n--- Test 1: Valid C++ header and source ---")
    header_info = {
        "path": "TestClass.h",
        "content": """#pragma once
#include <string>

class TestClass {
public:
    TestClass(const std::string& name);
    void doSomething();
    const std::string& getName() const;
    
private:
    std::string name_;
};"""
    }
    
    source_info = {
        "path": "TestClass.cpp", 
        "content": """TestClass::TestClass(const std::string& name) : name_(name) {
}

void TestClass::doSomething() {
    // Implementation here
}

const std::string& TestClass::getName() const {
    return name_;
}"""
    }
    
    try:
        result = analyzer.test_compile_files(header_info, source_info, test_integration=True)
        print(f"  Clang available: {result['clang_available']}")
        print(f"  Header compiles: {result['header_compiles']}")
        print(f"  Source compiles: {result['source_compiles']}")
        print(f"  Links with project: {result['links_with_project']}")
        
        if result['errors']:
            print(f"  Errors: {len(result['errors'])}")
            for error in result['errors'][:3]:  # Show first 3 errors
                print(f"    - {error}")
        
        if result['warnings']:
            print(f"  Warnings: {len(result['warnings'])}")
        
        if result['missing_dependencies']:
            print(f"  Missing dependencies: {result['missing_dependencies']}")
            
    except Exception as e:
        print(f"  ✗ Compile test failed: {e}")
    
    # Test 2: Code with syntax errors
    print("\n--- Test 2: Invalid C++ with syntax errors ---")
    invalid_header = {
        "path": "InvalidClass.h",
        "content": """#pragma once

class InvalidClass {
public:
    InvalidClass();
    void badMethod(  // Missing closing parenthesis
    
private:
    int missing_semicolon  // Missing semicolon
};"""
    }
    
    invalid_source = {
        "path": "InvalidClass.cpp",
        "content": """InvalidClass::InvalidClass() {
    return "this is wrong";  // Constructor returning value
}

void InvalidClass::badMethod() {
    undeclared_variable = 42;  // Undeclared variable
}"""
    }
    
    try:
        result = analyzer.test_compile_files(invalid_header, invalid_source, test_integration=False)
        print(f"  Header compiles: {result['header_compiles']}")
        print(f"  Source compiles: {result['source_compiles']}")
        print(f"  Errors found: {len(result['errors'])}")
        
        if result['errors']:
            print("  Sample errors:")
            for error in result['errors'][:2]:  # Show first 2 errors
                print(f"    - {error}")
                
    except Exception as e:
        print(f"  ✗ Invalid code test failed: {e}")
    
    # Test 3: Code with missing includes
    print("\n--- Test 3: Code with missing dependencies ---")
    missing_deps_header = {
        "path": "MissingDeps.h", 
        "content": """#pragma once
#include <nonexistent_header.h>  // This should fail
#include <vector>
#include <boost/algorithm/string.hpp>  // May not be available

class MissingDeps {
public:
    std::vector<std::string> data;
    void processStrings();
};"""
    }
    
    missing_deps_source = {
        "path": "MissingDeps.cpp",
        "content": """void MissingDeps::processStrings() {
    boost::algorithm::to_upper(data[0]);  // May fail if boost not available
}"""
    }
    
    try:
        result = analyzer.test_compile_files(missing_deps_header, missing_deps_source, test_integration=False)
        print(f"  Header compiles: {result['header_compiles']}")
        print(f"  Source compiles: {result['source_compiles']}")
        print(f"  Missing dependencies detected: {result['missing_dependencies']}")
        
        if result['errors']:
            print(f"  Errors: {len(result['errors'])}")
            
    except Exception as e:
        print(f"  ✗ Missing dependencies test failed: {e}")
    
    print("Compile testing completed!")

def test_analyzer():
    print("Testing C++ MCP Server...")
    
    # Use ChickenrikkeEngine directory for testing
    engine_dir = r"H:\Programming\MPCServers\CPlusPlus-MCP-Server\ChickenrikkeEngine"
    print(f"Project root: {engine_dir}")
    
    try:
        # Initialize analyzer with ChickenrikkeEngine directory
        print("Initializing CppAnalyzer...")
        analyzer = CppAnalyzer(engine_dir)
        print("✓ Using Python indexer for analysis")
        print(f"✓ Analyzer initialized successfully")
        
        # Trigger initialization by indexing the project
        print("Triggering project analysis...")
        
        # Index the project (it will automatically use cache if available)
        analyzer.index_project()
        
        print(f"Indexed {analyzer.indexed_file_count} C++ files")
        
        if analyzer.indexed_file_count == 0:
            print("⚠️  No C++ files were parsed. This could mean:")
            print("   - libclang is not working properly")
            print("   - No C++ files found in the project")
            print("   - Compilation errors preventing parsing")
            return
        
        # Show detailed cache status
        print("\n=== Cache Status ===")
        # Cache is stored in the MCP server directory, not the project directory
        cache_dir = analyzer.cache_dir
        if cache_dir.exists():
            print(f"✓ Cache directory exists: {cache_dir}")
            
            # Check files subdirectory
            files_dir = cache_dir / "files"
            if files_dir.exists():
                cache_files = list(files_dir.glob("*.json"))
                print(f"✓ Files cache directory exists with {len(cache_files)} cached files")
                
                # Show sample cache file
                if cache_files:
                    import json
                    sample_file = cache_files[0]
                    try:
                        with open(sample_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        print(f"\nSample cache file: {sample_file.name}")
                        print(f"  Original file: {data.get('file_path', 'N/A')}")
                        print(f"  Symbols found: {len(data.get('symbols', []))}")
                        print(f"  File hash: {data.get('file_hash', 'N/A')[:8]}...")
                    except Exception as e:
                        print(f"  Error reading cache file: {e}")
            else:
                print("⚠️  Files cache directory does not exist")
            
            # Check progress summary
            progress_file = cache_dir / "indexing_progress.json"
            if progress_file.exists():
                try:
                    with open(progress_file, 'r', encoding='utf-8') as f:
                        progress = json.load(f)
                    print(f"\n✓ Progress summary found:")
                    print(f"  Total files: {progress.get('total_files', 0)}")
                    print(f"  Indexed: {progress.get('indexed_files', 0)}")
                    print(f"  Failed: {progress.get('failed_files', 0)}")
                    print(f"  From cache: {progress.get('cache_hits', 0)}")
                    print(f"  Status: {progress.get('status', 'unknown')}")
                except Exception as e:
                    print(f"  Error reading progress file: {e}")
        else:
            print("⚠️  No cache directory found")
        
        # Test class search (project only)
        print("\n=== Testing class search (project only) ===")
        classes_project = analyzer.search_classes("Actor", project_only=True)
        print(f"Found {len(classes_project)} project classes matching 'Actor'")
        for cls in classes_project[:3]:  # Show first 3
            print(f"- {cls['name']} ({cls['kind']}) at {cls['file']}:{cls['line']}")
            print(f"  Is project: {cls['is_project']}")
        
        # Test class search (including dependencies)
        print("\n=== Testing class search (including dependencies) ===")
        classes_all = analyzer.search_classes("Actor", project_only=False)
        print(f"Found {len(classes_all)} total classes matching 'Actor'")
        project_count = sum(1 for cls in classes_all if cls['is_project'])
        dependency_count = len(classes_all) - project_count
        print(f"  - Project classes: {project_count}")
        print(f"  - Dependency classes: {dependency_count}")
        
        # Show mix of project and dependency classes
        for cls in classes_all[:5]:
            source = "PROJECT" if cls['is_project'] else "DEPENDENCY"
            print(f"- {cls['name']} ({source}) at {cls['file']}:{cls['line']}")
        
        # Test function search (project only)
        print("\n=== Testing function search (project only) ===")
        functions_project = analyzer.search_functions("BeginPlay", project_only=True)
        print(f"Found {len(functions_project)} project functions matching 'BeginPlay'")
        for func in functions_project[:3]:  # Show first 3
            print(f"- {func['name']} at {func['file']}:{func['line']}")
            print(f"  Signature: {func['signature']}")
            print(f"  Is project: {func['is_project']}")
        
        # Test broader function search
        print("\n=== Testing broader function search ===")
        update_functions = analyzer.search_functions("Update", project_only=True)
        print(f"Found {len(update_functions)} project functions matching 'Update'")
        for func in update_functions[:3]:
            print(f"- {func['name']} at {func['file']}:{func['line']}")
            print(f"  Signature: {func['signature']}")
        
        # Test class info
        print("\n=== Testing class info ===")
        class_info = analyzer.get_class_info("Actor")
        if class_info:
            print(f"Class: {class_info['name']}")
            # Check if detailed info is available (libclang) or just basic info (Python indexer)
            if 'methods' in class_info:
                print(f"Methods: {len(class_info['methods'])}")
                print(f"Members: {len(class_info['members'])}")
                print(f"Base classes: {class_info['base_classes']}")
            else:
                # Python indexer only provides basic info
                print(f"File: {class_info['file']}:{class_info['line']}")
                print(f"Kind: {class_info['kind']}")
                print("⚠️  Detailed class info (methods/members) not available with Python indexer")
        else:
            print("Actor class not found")
        
        # Test vcpkg detection (not in our analyzer, but that's OK)
        print("\n=== Testing vcpkg integration ===")
        print("⚠️  vcpkg detection not implemented in pure Python analyzer")
        
        # Summary
        print("\n=== Test Summary ===")
        total_files = analyzer.indexed_file_count
        # Count project vs dependency files from results
        all_symbols = analyzer.search_classes(".*", project_only=False) + analyzer.search_functions(".*", project_only=False)
        unique_files = set(s['file'] for s in all_symbols if 'file' in s)
        project_files = sum(1 for f in unique_files if analyzer._is_project_file(f))
        dependency_files = len(unique_files) - project_files
        
        print(f"Total files parsed: {total_files}")
        print(f"  - Project files: {project_files}")
        print(f"  - Dependency files: {dependency_files}")
        print(f"Project classes found: {len(classes_project)}")
        print(f"Total classes found: {len(classes_all)}")
        print(f"Project functions found: {len(functions_project)}")
        
        # Test caching functionality
        print("\n=== Testing cache functionality ===")
        if analyzer.indexed_file_count > 0:
            # Get a sample file that was indexed
            sample_files = list(analyzer.file_hashes.keys())[:1]
            if sample_files:
                test_file = sample_files[0]
                print(f"Testing cache on file: {test_file}")
                
                # Re-index the file (should use cache)
                import time
                start_time = time.time()
                success, _ = analyzer.index_file(test_file)
                elapsed = time.time() - start_time
                
                print(f"  Re-index result: {'Success' if success else 'Failed'}")
                print(f"  Time taken: {elapsed:.3f}s (should be fast if cached)")
                
                # Force re-index without cache
                start_time = time.time()
                success, _ = analyzer.index_file(test_file, force=True)
                elapsed_forced = time.time() - start_time
                
                print(f"  Forced re-index result: {'Success' if success else 'Failed'}")
                print(f"  Time taken: {elapsed_forced:.3f}s")
                print(f"  Cache speedup: {elapsed_forced/elapsed:.1f}x" if elapsed > 0 else "  Cache speedup: N/A")
        
        # Test compile testing functionality
        print("\n=== Testing compile testing functionality ===")
        test_compile_functionality(analyzer)
        
        # Test dependency indexing
        print("\n=== Testing dependency indexing ===")
        print("Checking if dependencies need to be indexed...")
        
        # First, check how many files we would find with dependencies
        original_include_deps = analyzer.include_dependencies
        analyzer.include_dependencies = True
        dep_files = analyzer._find_cpp_files(include_dependencies=True)
        analyzer.include_dependencies = original_include_deps
        
        print(f"Found {len(dep_files)} total files (including dependencies)")
        print(f"Previously indexed: {analyzer.indexed_file_count} files")
        
        if len(dep_files) > analyzer.indexed_file_count:
            print(f"Found {len(dep_files) - analyzer.indexed_file_count} new dependency files to index")
            print("Re-indexing with dependencies included...")
            dep_start = time.time()
            dep_count = analyzer.index_project(force=False, include_dependencies=True)
            dep_time = time.time() - dep_start
            print(f"Indexed {dep_count} files with dependencies in {dep_time:.1f}s")
        else:
            print("No additional dependency files found to index")
            dep_count = analyzer.indexed_file_count
        
        # Test searching with dependencies
        print("\n--- Searching for std classes ---")
        std_classes = analyzer.search_classes("^std::", project_only=False)
        print(f"Found {len(std_classes)} std:: classes")
        if std_classes:
            # Show a few examples
            for cls in std_classes[:3]:
                source = "PROJECT" if cls['is_project'] else "DEPENDENCY"
                print(f"- {cls['name']} ({source}) at {cls['file']}:{cls['line']}")
        
        # Check cache structure
        print("\n--- Checking cache structure ---")
        # Cache is now unified - both project and dependency files use the same cache
        if analyzer.cache_dir.exists():
            files_dir = analyzer.cache_dir / "files"
            if files_dir.exists():
                cache_files = list(files_dir.glob("*.json"))
                print(f"✓ Unified cache directory exists with {len(cache_files)} cached files")
            else:
                print("⚠️  No files cache directory found")
        else:
            print("⚠️  No cache directory found")
        
        # Test new enhanced search features
        print("\n=== Testing enhanced search features ===")
        
        # Test unified symbol search
        print("\n--- Testing search_symbols ---")
        symbol_results = analyzer.search_symbols("Update", project_only=True)
        print(f"Found {len(symbol_results['classes'])} classes and {len(symbol_results['functions'])} functions matching 'Update'")
        if symbol_results['functions']:
            print("Sample functions:")
            for func in symbol_results['functions'][:3]:
                print(f"  - {func['name']} ({func['kind']}) at {func['file']}:{func['line']}")
        
        # Test search with specific symbol types
        print("\n--- Testing search_symbols with type filter ---")
        method_results = analyzer.search_symbols("Update", project_only=True, symbol_types=['method'])
        print(f"Found {len(method_results['functions'])} methods matching 'Update'")
        
        # Test enhanced function search with class_name
        print("\n--- Testing search_functions with class filter ---")
        # Note: This requires proper parent class tracking which is not fully implemented yet
        actor_methods = analyzer.search_functions(".*", project_only=True, class_name="Actor")
        print(f"Found {len(actor_methods)} methods in Actor class")
        print("Note: Class-scoped search requires enhanced indexing to track parent classes")
        
        # Test enhanced get_function_signature
        print("\n--- Testing get_function_signature with class name ---")
        update_sigs = analyzer.get_function_signature("Update", class_name="Actor")
        print(f"Found {len(update_sigs)} Update signatures in Actor class")
        
        print("\n✓ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        print("\nFull error details:")
        traceback.print_exc()

if __name__ == "__main__":
    try:
        test_analyzer()
        print(f"\n=== Test completed. Results saved to: {log_file} ===")
    except Exception as e:
        print(f"\n✗ Critical error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore normal stdout
        sys.stdout = sys.stdout.console if hasattr(sys.stdout, 'console') else sys.__stdout__
        print(f"\nTest results have been saved to: {log_file}")
        print("You can review the full output there even after this window closes.")