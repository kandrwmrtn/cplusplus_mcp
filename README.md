# C++ MCP Server

An MCP (Model Context Protocol) server for analyzing C++ codebases using libclang.

## Why Use This?

Instead of having Claude grep through your C++ codebase trying to understand the structure, this server provides semantic understanding of your code. Claude can instantly find classes, functions, and their relationships without getting lost in thousands of files. It understands C++ syntax, inheritance hierarchies, and call graphs - giving Claude the ability to navigate your codebase like an IDE would.

## Features

Context-efficient C++ code analysis:
- **search_classes** - Find classes by name pattern
- **search_functions** - Find functions by name pattern  
- **get_class_info** - Get detailed class information (methods, members, inheritance)
- **get_function_signature** - Get function signatures and parameters
- **find_in_file** - Search symbols within specific files
- **get_class_hierarchy** - Get complete inheritance hierarchy for a class
- **get_derived_classes** - Find all classes that inherit from a base class
- **find_callers** - Find all functions that call a specific function
- **find_callees** - Find all functions called by a specific function
- **get_call_path** - Find call paths from one function to another

## Prerequisites

- Windows operating system (may work on macOS/Linux but not tested)
- Python 3.9 or higher
- pip (Python package manager)
- Git (for cloning the repository)

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd CPlusPlus-MCP-Server
```

2. Run the setup script (this will create a virtual environment, install dependencies, and download libclang):
```bash
server_setup.bat
```

3. Test the installation (recommended):
```bash
# Activate the virtual environment first
mcp_env\Scripts\activate

# Run the installation test
python scripts\test_installation.py
```

This will verify that all components are properly installed and working. The test script is located at `scripts\test_installation.py`.

## Configuring Claude Code

To use this MCP server with Claude Code, you need to add it to your Claude configuration file.

1. Find and open your Claude configuration file. Common locations include:
   ```
   C:\Users\<YourUsername>\.claude.json
   C:\Users\<YourUsername>\AppData\Roaming\Claude\.claude.json
   %APPDATA%\Claude\.claude.json
   ```
   
   The exact location may vary depending on your Claude installation.
   
2. Add the C++ MCP server to the `mcpServers` section:
   ```json
   {
     "mcpServers": {
       "cpp-analyzer": {
         "command": "python",
         "args": [
           "-m",
           "mcp_server.cpp_mcp_server"
         ],
         "cwd": "YOUR_INSTALLATION_PATH_HERE",
         "env": {
           "PYTHONPATH": "YOUR_INSTALLATION_PATH_HERE"
         }
       }
     }
   }
   ```

   **IMPORTANT:** Replace `YOUR_INSTALLATION_PATH_HERE` with the actual path where you cloned this repository.

3. Restart Claude Desktop for the changes to take effect.

## Usage with Claude

Once configured, you can use the C++ analyzer in your conversations with Claude:

1. First, ask Claude to set your project directory using the MCP tool:
   ```
   "Use the cpp-analyzer tool to set the project directory to C:\path\to\your\cpp\project"
   ```
   
   **Note:** The initial indexing might take a long time for very large projects (several minutes for codebases with thousands of files). The server will cache the results for faster subsequent queries.

2. Then you can ask questions like:
   - "Find all classes containing 'Actor'"
   - "Show me the Component class details"
   - "What's the signature of BeginPlay function?"
   - "Search for physics-related functions"
   - "Show me the inheritance hierarchy for GameObject"
   - "Find all functions that call Update()"
   - "What functions does Render() call?"

## Architecture

- Uses libclang for accurate C++ parsing
- Caches parsed AST for improved performance
- Supports incremental analysis and project-wide search
- Provides detailed symbol information including:
  - Function signatures with parameter types and names
  - Class members, methods, and inheritance
  - Call graph analysis for understanding code flow
  - File locations for easy navigation

## Configuration Options

The server behavior can be configured via `cpp-analyzer-config.json`:

```json
{
  "exclude_directories": [".git", ".svn", "node_modules", "build", "Build"],
  "exclude_patterns": ["*.generated.h", "*.generated.cpp", "*_test.cpp"],
  "dependency_directories": ["vcpkg_installed", "third_party", "external"],
  "include_dependencies": true,
  "max_file_size_mb": 10
}
```

- **exclude_directories**: Directories to skip during project scanning
- **exclude_patterns**: File patterns to exclude from analysis
- **dependency_directories**: Directories containing third-party dependencies
- **include_dependencies**: Whether to analyze files in dependency directories
- **max_file_size_mb**: Maximum file size to analyze (larger files are skipped)

## Troubleshooting

### Common Issues

1. **"libclang not found" error**
   - Run `server_setup.bat` to download libclang automatically
   - If automatic download fails, manually download libclang:
     1. Go to: https://github.com/llvm/llvm-project/releases
     2. Download the appropriate file for your system:
        - **Windows**: `clang+llvm-*-x86_64-pc-windows-msvc.tar.xz`
        - **macOS**: `clang+llvm-*-x86_64-apple-darwin.tar.xz`
        - **Linux**: `clang+llvm-*-x86_64-linux-gnu-ubuntu-*.tar.xz`
     3. Extract and copy the libclang library to the appropriate location:
        - **Windows**: Copy `bin\libclang.dll` to `lib\windows\libclang.dll`
        - **macOS**: Copy `lib\libclang.dylib` to `lib\macos\libclang.dylib`
        - **Linux**: Copy `lib\libclang.so.*` to `lib\linux\libclang.so`

2. **Server fails to start**
   - Check that Python 3.9+ is installed: `python --version`
   - Verify all dependencies are installed: `pip install -r requirements.txt`
   - Run the installation test to identify issues:
     ```bash
     mcp_env\Scripts\activate
     python -m mcp_server.test_installation
     ```

3. **Claude doesn't recognize the server**
   - Ensure the paths in `.claude.json` are absolute paths
   - Restart Claude Desktop after modifying the configuration

4. **Claude uses grep/glob instead of the C++ analyzer**
   - Be explicit in prompts: Say "use the cpp-analyzer to..." when asking about C++ code
   - Add instructions to your project's `CLAUDE.md` file telling Claude to prefer the cpp-analyzer for C++ symbol searches
   - The cpp-analyzer is much faster than grep for finding classes, functions, and understanding code structure