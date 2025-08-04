# C++ MCP Server

An MCP (Model Context Protocol) server for analyzing C++ codebases using libclang.

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

- Python 3.9 or higher
- pip (Python package manager)
- Git (for cloning the repository)

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd CPlusPlus-MCP-Server
```

2. Create and activate a virtual environment (recommended):
```bash
# Windows
python -m venv mcp_env
mcp_env\Scripts\activate

# Linux/Mac
python -m venv mcp_env
source mcp_env/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the setup script to download libclang:
```bash
# Windows
server_setup.bat

# Linux/Mac
python scripts/download_libclang.py
```

5. Test the server (optional):
```bash
python -m mcp_server.cpp_mcp_server
```

## Configuring Claude Desktop

To use this MCP server with Claude Desktop, you need to add it to your Claude configuration file.

### Windows Configuration

1. Open your Claude configuration file located at:
   ```
   C:\Users\<YourUsername>\.claude.json
   ```
   
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
         "cwd": "H:\\Programming\\MPCServers\\CPlusPlus-MCP-Server",
         "env": {
           "PYTHONPATH": "H:\\Programming\\MPCServers\\CPlusPlus-MCP-Server"
         }
       }
     }
   }
   ```

   Note: Adjust the `cwd` and `PYTHONPATH` paths to match your installation directory.

### Linux/Mac Configuration

1. Open your Claude configuration file located at:
   ```
   ~/.claude.json
   ```
   
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
         "cwd": "/path/to/CPlusPlus-MCP-Server",
         "env": {
           "PYTHONPATH": "/path/to/CPlusPlus-MCP-Server"
         }
       }
     }
   }
   ```

3. Restart Claude Desktop for the changes to take effect.

## Usage with Claude

Once configured, you can use the C++ analyzer in your conversations with Claude:

1. First, set your project directory:
   ```
   Set the C++ project directory to: C:\path\to\your\cpp\project
   ```

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
  "cache_directory": ".mcp_cache",
  "file_extensions": [".cpp", ".cc", ".cxx", ".c++", ".h", ".hpp", ".hxx", ".h++"],
  "exclude_patterns": ["**/build/**", "**/third_party/**", "**/vendor/**"],
  "max_file_size_mb": 10,
  "parse_timeout_seconds": 30
}
```

## Troubleshooting

### Common Issues

1. **"libclang not found" error**
   - Run `server_setup.bat` (Windows) or `python scripts/download_libclang.py` (Linux/Mac)
   - Ensure the `lib` directory contains the appropriate libclang library for your OS

2. **Server fails to start**
   - Check that Python 3.9+ is installed: `python --version`
   - Verify all dependencies are installed: `pip install -r requirements.txt`
   - Check the logs in `.mcp_cache/logs/` for detailed error messages

3. **Claude doesn't recognize the server**
   - Ensure the paths in `.claude.json` are absolute paths
   - Restart Claude Desktop after modifying the configuration
   - Check that the server runs successfully with `python -m mcp_server.cpp_mcp_server`

## License

MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.